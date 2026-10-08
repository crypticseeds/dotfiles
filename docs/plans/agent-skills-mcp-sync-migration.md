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

Hand-added MCPs whose name is in the manifest are updated to the manifest
definition automatically on the next sync, so nothing needs removing by hand.
Note: omp's hand-made `linear` loses its custom OAuth callback port when the
sync replaces it with the manifest entry. Hand-added MCPs whose name is not in
the manifest are left alone.

## 4. Sync and verify

```sh
cd ~/dotfiles && make install    # or: make agents-sync && make doctor
```

Expected: no `WARN ... not managed` lines for skills; MCPs named in the manifest
now match it in every installed harness; doctor's Drift section shows
`OK    drift: none` or only items you chose to keep.
New remote MCPs (linear, firecrawl, tinyfish) in codex/cursor/omp/opencode ask
for an OAuth login on first use.

## 5. After every machine is migrated (repo change, once)

Delete the block marked "Remove after the one-time migration" from the root
`.gitignore` (fetched skills carry their own `.gitignore`).
