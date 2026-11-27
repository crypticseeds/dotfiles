# GitHub access for agents launched with agent-launch (nono)

Status: option B (nono credential proxy) chosen by the owner, validated 2026-11-27, implemented in
`zsh/.config/nono/profiles/pi-agent-host.json` and `zsh/.local/bin/agent-launch` (uncommitted).

## Design

- The GitHub PAT (`GH_TOKEN`, Doppler `harness/dev`) stays the only credential, so its scopes are
  the access control. It never enters the sandbox.
- Two nono credential routes, both sourced with `cmd://`: the supervisor (outside Landlock) runs
  `doppler secrets get GH_TOKEN` on first use and caches it in memory for 15 minutes.
  - `github` -> `https://api.github.com`, header `Authorization: token <PAT>` (gh, API).
  - `github_git` -> `https://github.com`, basic auth `x-access-token:<PAT>` (git push/fetch over HTTPS).
- The child gets a phantom `GH_TOKEN` (`ghp_` + session token), not the PAT. `~/.doppler`,
  `~/.config/gh` and the real token stay unreadable.
- The proxy adds the PAT to every request to those two hosts, whether or not the client sends the
  placeholder (a push with no credential helper still authenticated). Unsetting `GH_TOKEN` in a
  session does not remove its GitHub access; the launch flags are what decide it.
- `--subagent` workers are read-only on GitHub: `agent-launch` adds `--allow-endpoint` rules
  (`gh_api:GET:/**`, `gh_git:GET:/**`, `gh_git:POST:/*/*/git-upload-pack`). Other requests go out
  without the PAT and GitHub refuses them (401). Verified 2026-11-27: worker `gh api user`, `ls-remote`
  and upload-pack work; `POST /markdown` and `git-receive-pack` get 401; the orchestrator gets 200 on
  both. GraphQL is a POST, so `gh pr view`/`gh pr list` do not work for workers; they read through
  `gh api` REST calls (or the GitHub MCP tools, which MCPHub authenticates separately).
- `GH_CONFIG_DIR=~/.local/state/agent-gh`: gh refuses to start without a readable config dir, and
  `~/.config/gh` is denied because `hosts.yml` can hold a login. The new dir holds only gh settings
  (it stayed empty in testing); auth comes from `GH_TOKEN` alone.

## Validation (2026-11-27)

Run through `hc run` (outside Claude's sandbox), first with a scratch profile, then with the exact
argv `agent-launch claude` produces, harness binary swapped for a probe script, workspace `~/REPOS/buzz`:

| Check | Result |
|-------|--------|
| `/etc/agent-guard/policy.json`, `~/.agents/AGENTS.md` readable | yes |
| `ls ~/.doppler` | Permission denied |
| `gh api user` | `crypticseeds` |
| `git push --dry-run https://github.com/crypticseeds/dotfiles HEAD:refs/heads/agent/push-check` (normal gitconfig) | authenticated, `[new branch]` |
| Same push outside nono with no credentials (control) | `could not read Username` |
| pypi.org, registry.npmjs.org, api.anthropic.com, example.com in proxy mode | reachable |

Same probe through `agent-launch` for codex, opencode and omp: all pass. The opencode and omp packs
declare their own `network.credentials` (empty) and their own `github` route, which replaced the
inherited ones. So the routes are named `gh_api`/`gh_git` and turned on by `agent-launch`
(`--credential gh_api --credential gh_git`) instead of by the profile's credentials list.

Not yet validated: a real Claude session doing a non-dry-run push and `gh pr create`.

## Friction found along the way (to fix, smallest first)

1. `agent-launch` in `~/dotfiles` cannot start: the base `deny` on `~/.zshrc` resolves into
   `~/dotfiles/zsh/.zshrc`, inside the workspace grant, and Landlock refuses deny-inside-allow.
2. nono denies writes to any `.git/config`, so `git init` (and `git config` writes) fail in the sandbox.
3. Guard: `git-in` only accepts repos under `~/REPOS`; `GIT_CONFIG_GLOBAL=` prefixes are refused;
   any `hc` command inside a loop or chain is refused (one call per terminal to clean up).
4. nono's post-run "Review denied paths" prompt blocks non-interactive runs (hc probes hang until
   killed); `--no-diagnostics` did not suppress it.
5. `/var/run/nscd/socket` connects are denied (harmless noise in every session summary).
6. **Biggest blocker.** Claude's own Bash sandbox still fails inside nono (verified 2026-11-27 with a
   real `agent-launch claude` session on Haiku): `Sandbox is required but failed to initialize: listen
   EACCES: permission denied 127.0.0.1`. Claude's sandbox binds a loopback proxy and nono forbids the
   listen. Only Claude's sandbox-excluded commands (git, gh, hc) run; `ls`, `python3` and file writes
   fail. The skills' "use a direct Claude session" note is still correct. Fix options: let nono allow
   loopback listen for the claude launch, or turn Claude's own sandbox off under nono (nono already
   sandboxes; the managed settings currently require it).
7. The codex pack grants `~/dotfiles/agents/.agents` read-write, so a Codex session can edit the
   global AGENTS.md, skills and subagents. The read-only `--read` from agent-launch does not narrow it.

## Hot reload (upstream contribution idea)

Landlock can only tighten a running process, never loosen it, so a profile edit cannot widen a live
session. nono already has the hook for expansion without restart: `security.capability_elevation`
(seccomp-notify, Linux) pauses a denied access and asks the supervisor, and `approval_backends` can
answer instead of the terminal. An approval backend that re-reads the current profile on each
request would give expansion-only hot reload: newly granted paths work without restarting the
agent; removals still need a restart. Credential routes and `credential_capture` would need the
supervisor to reload them too.

## Next

- Done: AGENTS.md (Runtime Safety exception: keep the placeholder `GH_TOKEN` under agent-launch)
  and the herdr-app skill say `gh` and `git push` work inside agent-launch.
- Fix friction items 1, 2 and 4, then decide on 7.
