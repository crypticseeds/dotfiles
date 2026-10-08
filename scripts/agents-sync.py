#!/usr/bin/env python3
"""Sync agent skills (and later links, MCP servers, plugins) from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] {fetch|link|mcp|plugins|all}
"""
import argparse
import json
import os
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
        git(cache, "fetch", "-q", "--depth", "1", url, entry["ref"])
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


def install(src, target, entry, skill_path):
    """Copy src to target atomically enough, then write marker and .gitignore."""
    tmp = target + ".tmp-sync"
    if os.path.isdir(tmp):
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(".git"))
    with open(os.path.join(tmp, MARKER), "w") as f:
        json.dump({"repo": entry["repo"], "path": skill_path,
                   "ref": entry["ref"]}, f, indent=2)
        f.write("\n")
    with open(os.path.join(tmp, ".gitignore"), "w") as f:
        f.write("*\n")
    if os.path.isdir(target):
        shutil.rmtree(target)
    os.rename(tmp, target)


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
    if os.path.exists(target) and marker is None:
        print("WARN  %s exists and is not managed by the manifest, skipping" % target)
        return
    if marker and marker.get("ref") == entry["ref"] and marker.get("repo") == entry["repo"]:
        print("unchanged  %s" % name)
        return
    if dry:
        print("would install  %s (%s@%s)" % (name, entry["repo"], entry["ref"][:12]))
        return
    install(src, target, entry, skill_path)
    print("installed  %s (%s@%s)" % (name, entry["repo"], entry["ref"][:12]))


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


STEPS = [("fetch", fetch), ("link", stub("link")), ("mcp", stub("mcp")),
         ("plugins", stub("plugins"))]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would change, write nothing")
    p.add_argument("step", choices=[s for s, _ in STEPS] + ["all"])
    args = p.parse_args()
    with open(MANIFEST) as f:
        manifest = json.load(f)
    rc = 0
    for name, fn in STEPS:
        if args.step in (name, "all"):
            rc = fn(manifest, args.dry_run) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
