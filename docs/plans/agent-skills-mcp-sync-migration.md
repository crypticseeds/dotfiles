# One-time migration: hand-installed skills, plugins and MCPs -> manifest sync

For the owner to run, once per machine, after `feat/agent-skills-mcp-sync`
reaches the branch the live `~/dotfiles` checkout is on. Every step is a
command to run yourself; agents do not run these (deletions, live config).

`make doctor` lists the drift before and after: its "Drift" section is the
checklist. Run it first and last.

## 0. Before merging the branch (repo change, once)

Hand the three committed third-party skills over to the manifest, so a fresh
machine fetches them pinned instead of carrying stale copies:

```sh
cd ~/dotfiles/.worktrees/agent-skills-mcp-sync
git rm -r -q agents/.agents/skills/find-skills agents/.agents/skills/shadcn agents/.agents/skills/code-review
git commit -m "chore(agents): hand third-party skills over to the manifest"
```

On a live machine these three disappear from `~/.agents/skills` on pull and
come back (pinned, with marker) on the next `make agents-sync`.

## 1. Per machine: remove unmarked copies the fetcher must not overwrite

The fetcher never replaces a skill dir without `.managed-by-manifest`, and
`make skills` never replaces a real dir with a link. The old installers left
real copies, so remove them (the sync re-creates each one, pinned):

```sh
cd ~/.agents/skills && rm -rf amazon-bedrock aws-* launch-with-aws setting-up-cloudwatch-observability signing-in-to-aws herdr
cd ~/.claude/skills && rm -rf amazon-bedrock aws-* launch-with-aws setting-up-cloudwatch-observability signing-in-to-aws
# pi reads ~/.agents/skills natively; its own dir only holds duplicates
cd ~/.pi/agent/skills && rm -rf amazon-bedrock aws-* launch-with-aws setting-up-cloudwatch-observability signing-in-to-aws && rm -f find-skills herdr shadcn
# Hermes: replace the copied Buzz skills with manifest links (Pi only)
cd ~/.hermes/skills && rm -rf hermes-in-buzz buzz-media-attachments buzz-self-hosting
```

## 2. Per machine: Claude plugins

aws-core duplicates the AWS skills (now from the manifest) and ships its own
aws-mcp (now from the manifest). superpowers is installed twice.

```sh
claude plugin disable aws-core@claude-plugins-official
claude plugin uninstall superpowers@anthropic-plugin-directory
```

`~/.claude/settings.json` is a symlink into the repo, so the disable writes
`"aws-core@claude-plugins-official": false` into the tracked
`claude/.claude/settings.json`: commit that change once (doctor only compares
plugins set to `true`, so it stops reporting aws-core).

## 3. Per machine: hand-added MCPs

The sync never modifies an MCP it did not write. Decide per entry:

| Harness | Entry | Action |
|---|---|---|
| Claude | `aws-mcp` (old `mcp-proxy-for-aws@latest`, no `--skip-auth`, fails without AWS creds) | remove, so the manifest version takes over: `claude mcp remove --scope user aws-mcp` |
| opencode | `aws-mcp` in `~/.config/opencode/opencode.json` (same old form) | remove: `python3 -c "import json,os;p=os.path.expanduser('~/.config/opencode/opencode.json');d=json.load(open(p));d.get('mcp',{}).pop('aws-mcp',None);json.dump(d,open(p,'w'),indent=2)"` |
| omp | `linear` with an OAuth callback port | keep (hand-managed, has settings the manifest lacks) |
| Hermes | `firecrawl` (OAuth, already logged in) | keep (identical to the manifest entry) |

## 4. Sync and verify

```sh
cd ~/dotfiles && make install    # or: make agents-sync && make doctor
```

Expected: no `WARN ... exists and is not managed` lines except the kept
entries from step 3; doctor's Drift section shows only those (or `OK drift: none`).
New remote MCPs (linear, firecrawl, tinyfish) in codex/cursor/omp/opencode ask
for an OAuth login on first use.

## 5. After every machine is migrated (repo change, once)

Delete the block marked "Remove after the one-time migration" from the root
`.gitignore` (fetched skills carry their own `.gitignore`).
