#!/usr/bin/env python3
"""Sync agent skills (and later links, MCP servers, plugins) from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] {fetch|link|mcp|plugins|all}
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "agents", ".agents", "manifest.json")
MARKER = ".managed-by-manifest"
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")


def home():
    return os.path.expanduser("~")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def has_commit(cwd, ref):
    r = subprocess.run(["git", "cat-file", "-e", ref + "^{commit}"], cwd=cwd,
                       env=GIT_ENV, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    return r.returncode == 0


def checkout(entry):
    """Shallow, sparse checkout of entry['ref'] into the cache; return its dir."""
    cache = os.path.join(home(), ".cache", "dotfiles-skills",
                         entry["repo"].replace("/", "__"))
    os.makedirs(cache, exist_ok=True)
    if not os.path.isdir(os.path.join(cache, ".git")):
        git(cache, "init", "-q")
    if not has_commit(cache, entry["ref"]):
        url = "https://github.com/%s.git" % entry["repo"]
        git(cache, "-c", "http.lowSpeedLimit=1000", "-c",
            "http.lowSpeedTime=30", "fetch", "-q", "--depth", "1", url, entry["ref"])
    if entry["path"] == ".":
        git(cache, "sparse-checkout", "disable")
    else:
        git(cache, "sparse-checkout", "set", "--cone", entry["path"])
    git(cache, "checkout", "-q", "--force", "--detach", entry["ref"])
    return cache


def read_marker(target):
    try:
        with open(os.path.join(target, MARKER)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def remove(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.unlink(path)
    elif os.path.lexists(path):
        shutil.rmtree(path)


def install(src, target, entry, skill_path):
    """Build into <target>.tmp-sync, then swap in; never leave a half-deleted target."""
    tmp, old = target + ".tmp-sync", target + ".old-sync"
    remove(tmp)
    remove(old)
    try:
        os.makedirs(tmp)
        # ignore file first, so a stale tmp dir never shows up in git
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("*\n")
        shutil.copytree(src, tmp, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git"))
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("*\n")
        with open(os.path.join(tmp, MARKER), "w") as f:
            json.dump({"repo": entry["repo"], "path": skill_path,
                       "ref": entry["ref"]}, f, indent=2)
            f.write("\n")
    except BaseException:
        remove(tmp)
        raise
    had_old = os.path.lexists(target)
    if had_old:
        os.rename(target, old)
    try:
        os.rename(tmp, target)
    except BaseException:
        if had_old:
            os.rename(old, target)
        remove(tmp)
        raise
    remove(old)


def skill_dirs(base, entry):
    """Names of skill dirs (containing SKILL.md) selected by a group entry."""
    names = sorted(n for n in os.listdir(base)
                   if os.path.isfile(os.path.join(base, n, "SKILL.md")))
    if "only" in entry:
        missing = [n for n in entry["only"] if n not in names]
        if missing:
            raise RuntimeError("not found in %s: %s" % (entry["repo"], missing))
        return list(entry["only"])
    return names


def sync_skill(entry, name, src, skill_path, skills_dir, dry):
    target = os.path.join(skills_dir, name)
    marker = read_marker(target)
    if os.path.lexists(target) and (os.path.islink(target) or marker is None):
        print("WARN  %s exists and is not managed by the manifest, skipping" % target)
        return
    if (marker and marker.get("ref") == entry["ref"]
            and marker.get("repo") == entry["repo"]
            and marker.get("path") == skill_path
            and os.path.isfile(os.path.join(target, "SKILL.md"))):
        print("unchanged  %s" % name)
        return
    if dry:
        print("would install  %s (%s@%s)" % (name, entry["repo"], entry["ref"][:12]))
        return
    install(src, target, entry, skill_path)
    print("installed  %s (%s@%s)" % (name, entry["repo"], entry["ref"][:12]))


def validate(entry):
    for key in ("repo", "ref", "path"):
        if not entry.get(key):
            raise RuntimeError("missing '%s'" % key)
    if not re.fullmatch(r"[0-9a-f]{40}", entry["ref"]):
        raise RuntimeError("ref is not a 40-hex commit SHA: %r" % entry["ref"])


def fetch(manifest, dry):
    skills_dir = os.path.join(home(), ".agents", "skills")
    host = socket.gethostname()
    failed = False
    for entry in manifest.get("skills", []):
        label = entry.get("name") or entry.get("group")
        if entry.get("local"):
            continue
        if "hosts" in entry and host not in entry["hosts"]:
            print("skip  %s (host %s not in %s)" % (label, host, entry["hosts"]))
            continue
        try:
            validate(entry)
            if dry:
                if "name" in entry:
                    sync_skill(entry, entry["name"], None, entry["path"],
                               skills_dir, True)
                else:
                    print("would fetch group  %s (%s@%s)"
                          % (label, entry["repo"], entry["ref"][:12]))
                continue
            os.makedirs(skills_dir, exist_ok=True)
            cache = checkout(entry)
            base = os.path.join(cache, entry["path"])
            if "name" in entry:
                sync_skill(entry, entry["name"], base, entry["path"],
                           skills_dir, False)
            else:
                for name in skill_dirs(base, entry):
                    sub = os.path.normpath(os.path.join(entry["path"], name))
                    sync_skill(entry, name, os.path.join(base, name), sub,
                               skills_dir, False)
        except (subprocess.CalledProcessError, OSError, RuntimeError) as e:
            detail = getattr(e, "stderr", None)
            if detail:
                detail = detail.decode(errors="replace").strip()
            print("ERROR  %s: %s" % (label, detail or e))
            failed = True
    return 1 if failed else 0


def stub(step):
    def run(manifest, dry):
        print("%s: not implemented yet (T2/T3/T4)" % step)
        return 0
    return run


HARNESSES = ("claude", "codex", "hermes")
SYNC_SUFFIXES = (".tmp-sync", ".old-sync")


def harness_filter(manifest, name, src):
    """Harnesses a skill may link into: None = all, else the manifest list."""
    marker = read_marker(src)
    for entry in manifest.get("skills", []):
        if "harnesses" not in entry:
            continue
        if "name" in entry:
            if entry["name"] == name:
                return entry["harnesses"]
        elif (marker and marker.get("repo") == entry.get("repo")
              and marker.get("path") == os.path.normpath(
                  os.path.join(entry.get("path", "."), name))
              and name in entry.get("only", [name])):
            return entry["harnesses"]
    return None


def link(manifest, dry):
    h = home()
    src_dir = os.path.join(h, ".agents", "skills")
    names = []
    if os.path.isdir(src_dir):
        names = sorted(n for n in os.listdir(src_dir)
                       if not n.endswith(SYNC_SUFFIXES)
                       and os.path.isfile(os.path.join(src_dir, n, "SKILL.md")))
    targets = [("claude", os.path.join(h, ".claude", "skills"), True),
               ("codex", os.path.join(h, ".codex", "skills"), True),
               ("hermes", os.path.join(h, ".hermes", "skills"),
                os.path.isdir(os.path.join(h, ".hermes")))]
    rc = 0
    for harness, tdir, enabled in targets:
        if not enabled:
            continue
        try:
            link_target(manifest, dry, harness, tdir, src_dir, names)
        except OSError as e:
            print("ERROR  %s: %s" % (harness, e))
            rc = 1
    return rc


def link_target(manifest, dry, harness, tdir, src_dir, names):
    if not os.path.isdir(tdir):
        if dry:
            print("would mkdir  %s" % tdir)
        else:
            os.makedirs(tdir)
    # prune: dangling links that point into ~/.agents/skills/ only
    if os.path.isdir(tdir):
        for n in sorted(os.listdir(tdir)):
            path = os.path.join(tdir, n)
            if (os.path.islink(path) and not os.path.exists(path)
                    and os.path.realpath(path).startswith(
                        os.path.realpath(src_dir) + os.sep)):
                print("%s  %s" % ("would prune" if dry else "pruned", path))
                if not dry:
                    os.unlink(path)
    for name in names:
        src = os.path.join(src_dir, name)
        allowed = harness_filter(manifest, name, src)
        path = os.path.join(tdir, name)
        if allowed is not None and harness not in allowed:
            if (os.path.islink(path)
                    and os.path.realpath(path) == os.path.realpath(src)):
                print("%s  %s" % ("would unlink" if dry else "unlinked", path))
                if not dry:
                    os.unlink(path)
            continue
        if os.path.islink(path):
            if os.path.realpath(path) == os.path.realpath(src):
                continue
            print("WARN  %s is a symlink to elsewhere, not linked" % path)
        elif os.path.lexists(path):
            kind = "directory" if os.path.isdir(path) else "file"
            print("WARN  %s is a real %s, not linked" % (path, kind))
        elif dry:
            print("would link  %s -> %s" % (path, src))
        else:
            os.symlink(src, path)
            print("linked  %s" % path)


STEPS = [("fetch", fetch), ("link", link), ("mcp", stub("mcp")),
         ("plugins", stub("plugins"))]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would change, write nothing")
    p.add_argument("step", choices=[s for s, _ in STEPS] + ["all"])
    p.add_argument("--manifest", default=MANIFEST, help=argparse.SUPPRESS)
    args = p.parse_args()
    try:
        with open(args.manifest) as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        print("ERROR  manifest %s: %s" % (args.manifest, e))
        if args.step in ("link", "all"):
            print("WARN  manifest unreadable, linking without harness filters")
            link({}, args.dry_run)
        return 1
    rc = 0
    for name, fn in STEPS:
        if args.step in (name, "all"):
            rc = fn(manifest, args.dry_run) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
