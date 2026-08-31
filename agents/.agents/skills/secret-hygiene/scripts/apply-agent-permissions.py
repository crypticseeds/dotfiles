#!/usr/bin/env python3
"""Apply the vetted secret-hygiene permission policy to opencode agent configs.

Replaces the `bash` and `read` permission blocks in persona (*.jsonc) and
subagent (*.md frontmatter) files. Role permissions (`edit`, `task`, `*`) are
left untouched -- a reviewer stays a reviewer, a worker stays a worker.

Both blocks are required. `bash` denies stop leaking COMMANDS; `read` denies
stop an agent simply opening the secret FILE with a read tool, which no bash
rule can prevent.

Usage:
    python3 apply-agent-permissions.py <config-dir> [--check]

    <config-dir>   directory containing personas/*.jsonc and/or agent/*.md
    --check        report only, exit 1 if any file is non-compliant

Idempotent. Always re-run against the file that scaffolds NEW agents
(e.g. TEMPLATE.jsonc) -- it alone determines what future agents inherit.
"""
import argparse
import pathlib
import re
import sys

BASH_DENIES = [
    # secret disclosure
    "*doppler secrets*", "*doppler configure*", "*doppler *--plain*",
    "env", "printenv*", "export -p", "ps e*", "history*",
    "gh auth token*", "cat /proc/*/environ*",
    # secret files, via ANY command (cat/grep/less/vim/...)
    "*.env*", "*id_rsa*", "*id_ed25519*", "*.pem*", "*.doppler*",
    "*/.config/gh/*", "*/.aws/credentials*", "*/.netrc*",
    # environment dumps
    "docker inspect*", "docker exec * env*",
    "systemctl show*", "systemctl cat*",
    # destruction
    "rm -rf *", "rm -fr *", "rm -r *", "shred*", "truncate*",
    "mkfs*", "fdisk*", "parted*", "dd if=*of=/dev/*",
    "find * -delete*", "find * -exec rm*",
    "chown -R *", "chmod 777*", "chmod -R 777*",
    # data loss
    "git reset --hard*", "git clean -f*", "git checkout -- *",
    "git restore *", "git branch -D*",
    "git push --force*", "git push -f*",
    "docker system prune*", "docker volume rm*", "docker rm -f*",
    "docker compose down -v*", "docker-compose down -v*",
    "kubectl delete*", "crontab -r*",
    # availability / privilege
    "sudo*", "pkill*", "killall*",
    "systemctl stop*", "systemctl disable*", "systemctl mask*",
    "ufw disable*", "iptables *", "tailscale down*", "tailscale logout*",
    "apt purge*", "apt-get purge*",
    "curl *| sh*", "curl *| bash*", "wget *| sh*", "wget *| bash*",
]

READ_RULES = [
    ("*", "allow"),
    ("*.env", "deny"), ("*.env.*", "deny"),
    ("**/*.env", "deny"), ("**/*.env.*", "deny"),
    ("*.env.example", "allow"), ("**/*.env.example", "allow"),
    ("**/*.pem", "deny"), ("**/*.key", "deny"),
    ("**/id_rsa", "deny"), ("**/id_ed25519", "deny"),
    ("**/.netrc", "deny"), ("**/.doppler.yaml", "deny"),
    ("**/credentials", "deny"),
]


def json_block(ind, name, pairs):
    j = ind + "  "
    body = ",\n".join('%s"%s": "%s"' % (j, k, v) for k, v in pairs)
    return '%s"%s": {\n%s\n%s}' % (ind, name, body, ind)


def yaml_block(ind, name, pairs):
    j = ind + "  "
    return "%s%s:\n" % (ind, name) + "".join(
        '%s"%s": %s\n' % (j, k, v) for k, v in pairs)


def replace_json(text, name, pairs):
    # Match either block form ("name": { ... }) or scalar ("name": "allow").
    m = re.search(r'^([ \t]*)"%s":\s*(\{|"[a-zA-Z]+")' % name, text, re.M)
    if not m:
        return text, False
    if m.group(2) != "{":
        return (text[:m.start()] + json_block(m.group(1), name, pairs)
                + text[m.end():], True)
    depth, k = 0, m.end() - 1
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return text[:m.start()] + json_block(m.group(1), name, pairs) + text[k + 1:], True


def replace_yaml(text, name, pairs):
    # Match either block form (`name:` + indented children) or scalar
    # (`name: allow`). Missing the scalar case silently creates a duplicate
    # key, and the scalar wins -- so the deny rules never take effect.
    m = re.search(r'^([ \t]*)%s:[ \t]*(\S.*)?$' % name, text, re.M)
    if not m:
        return text, False
    ind = m.group(1)
    lines = text[m.start():].splitlines(keepends=True)
    consumed = lines[0]
    if not m.group(2):
        for ln in lines[1:]:
            if ln.strip() == "" or len(ln) - len(ln.lstrip()) > len(ind):
                consumed += ln
            else:
                break
    return (text[:m.start()] + yaml_block(ind, name, pairs)
            + text[m.start() + len(consumed):], True)


def process(path, check):
    text = original = path.read_text()
    is_json = path.suffix == ".jsonc"
    rep = replace_json if is_json else replace_yaml
    bash_pairs = [("*", "allow")] + [(d, "deny") for d in BASH_DENIES]

    text, had_bash = rep(text, "bash", bash_pairs)
    text, had_read = rep(text, "read", READ_RULES)

    # Insert whichever block is absent, directly under `permission:`.
    for name, pairs, had in (("bash", bash_pairs, had_bash),
                             ("read", READ_RULES, had_read)):
        if had:
            continue
        if is_json:
            text = re.sub(
                r'^([ \t]*)"permission":[ \t]*\{[ \t]*\n',
                lambda mo: mo.group(0) + json_block(mo.group(1) + "  ", name, pairs) + ",\n",
                text, count=1, flags=re.M)
        else:
            text = re.sub(
                r'^([ \t]*)permission:[ \t]*\n',
                lambda mo: mo.group(0) + yaml_block(mo.group(1) + "  ", name, pairs),
                text, count=1, flags=re.M)

    if text == original:
        return "ok"
    if check:
        return "non-compliant"
    path.write_text(text)
    return "updated"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config_dir")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.config_dir).expanduser()
    files = sorted(root.rglob("*.jsonc")) + sorted(root.rglob("*.md"))
    if not files:
        print("no persona (*.jsonc) or subagent (*.md) files under %s" % root)
        return 1

    bad = 0
    for f in files:
        if ".bak" in f.name:
            continue
        status = process(f, args.check)
        if status != "ok":
            print("  %-12s %s" % (status, f.relative_to(root)))
        if status == "non-compliant":
            bad += 1
    print("%d files scanned; %d non-compliant" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
