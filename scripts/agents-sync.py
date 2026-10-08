#!/usr/bin/env python3
"""Sync agent skills, links and MCP servers (later plugins) from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] {fetch|link|mcp|plugins|all}
"""
import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile

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


MCP_START = "# >>> agents-sync managed MCP (do not edit)"
MCP_END = "# <<< agents-sync managed MCP"
MCP_HARNESSES = ("claude", "codex", "cursor", "omp", "opencode", "hermes")
SCHEMA = {"opencode": "https://opencode.ai/config.json"}


def state_path():
    return os.path.join(home(), ".cache", "dotfiles-skills", "state.json")


def load_state():
    try:
        with open(state_path()) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    """Atomic 2-space JSON write (tmp + rename), keeping the file mode."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".agents-sync-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".agents-sync-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def mcp_entries(manifest):
    """Validated neutral entries; returns (entries, had_error)."""
    entries, bad = {}, False
    for name, e in (manifest.get("mcp") or {}).items():
        try:
            if "${" in json.dumps(e):
                raise RuntimeError("contains '${': env/header substitution is not supported")
            if ("command" in e) == ("url" in e):
                raise RuntimeError("needs exactly one of 'command' or 'url'")
            if "command" in e and not isinstance(e.get("args", []), list):
                raise RuntimeError("'args' must be a list")
        except (RuntimeError, TypeError) as err:
            print("ERROR  mcp %s: %s" % (name, err))
            bad = True
            continue
        entries[name] = e
    return entries, bad


def applicable(entries, harness):
    out = {}
    for name, e in entries.items():
        if "harnesses" in e and harness not in e["harnesses"]:
            continue
        if harness in e.get("except", []):
            continue
        out[name] = e
    return out


def render_json(harness, e):
    """Per-harness JSON form of a neutral entry."""
    if harness == "opencode":
        if "command" in e:
            return {"type": "local", "command": [e["command"]] + e.get("args", []),
                    "enabled": True}
        return {"type": "remote", "url": e["url"], "enabled": True}
    if harness == "cursor":
        if "command" in e:
            return {"command": e["command"], "args": e.get("args", [])}
        return {"url": e["url"]}
    # claude, omp
    if "command" in e:
        return {"type": "stdio", "command": e["command"], "args": e.get("args", [])}
    return {"type": "http", "url": e["url"]}


def plan_owned(harness, want, existing, owned):
    """Split by ownership: (names to write, owned names to remove).

    existing: names present in the harness; owned: names this sync wrote.
    A same-name entry that is not ours is never written (WARN).
    """
    apply_, drop = [], []
    for name in want:
        if name in existing and name not in owned:
            print("WARN  %s: %s exists and is not managed, skipping" % (harness, name))
        else:
            apply_.append(name)
    for name in sorted(owned):
        if name not in want:
            drop.append(name)
    return apply_, drop


def mcp_json_file(harness, path, want, owned, dry):
    """cursor / omp / opencode: merge into one JSON object key. Returns new owned."""
    try:
        with open(path) as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            raise ValueError("top level is not an object")
    except FileNotFoundError:
        doc = {}
        if harness in SCHEMA:
            doc["$schema"] = SCHEMA[harness]
    except (OSError, ValueError) as e:
        raise RuntimeError("cannot parse %s: %s" % (path, e))
    key = "mcp" if harness == "opencode" else "mcpServers"
    servers = doc.get(key)
    if servers is None:
        servers = {}
    if not isinstance(servers, dict):
        raise RuntimeError("%s: '%s' is not an object" % (path, key))
    apply_, drop = plan_owned(harness, want, servers, owned)
    new_owned, changed = [], False
    for name in apply_:
        rendered = render_json(harness, want[name])
        new_owned.append(name)
        if servers.get(name) == rendered:
            print("unchanged  %s: %s" % (harness, name))
            continue
        print("%s  %s: %s" % ("would %s" % ("update" if name in servers else "add")
                              if dry else ("updated" if name in servers else "added"),
                              harness, name))
        servers[name] = rendered
        changed = True
    for name in drop:
        if name in servers:
            print("%s  %s: %s" % ("would remove" if dry else "removed", harness, name))
            del servers[name]
            changed = True
    if changed and not dry:
        doc[key] = servers
        write_json(path, doc)
    return new_owned


CODEX_TABLE = re.compile(
    r'^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*(?:\]|\.)')


def toml_name(name):
    return name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)


def render_codex(want):
    lines = [MCP_START]
    for i, name in enumerate(sorted(want)):
        e = want[name]
        if i:
            lines.append("")
        lines.append("[mcp_servers.%s]" % toml_name(name))
        if "command" in e:
            lines.append("command = %s" % json.dumps(e["command"]))
            lines.append("args = [%s]" % ", ".join(json.dumps(a) for a in e.get("args", [])))
        else:
            lines.append("url = %s" % json.dumps(e["url"]))
    lines.append(MCP_END)
    return lines


def mcp_codex(path, want, dry):
    """Managed block inside config.toml; text outside it is never changed."""
    try:
        with open(path) as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        lines = [""]
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline is re-added on write
    start = end = None
    for i, ln in enumerate(lines):
        if ln.strip() == MCP_START and start is None:
            start = i
        elif ln.strip() == MCP_END and start is not None and end is None:
            end = i
    if (start is None) != (end is None):
        raise RuntimeError("%s: unbalanced agents-sync markers" % path)
    outside = lines[:start] + lines[end + 1:] if start is not None else lines
    inside = lines[start + 1:end] if start is not None else []
    old = set()
    for ln in inside:
        m = CODEX_TABLE.match(ln)
        if m:
            old.add(m.group(1) or m.group(2))
    unmanaged = set()
    for ln in outside:
        m = CODEX_TABLE.match(ln)
        if m:
            unmanaged.add(m.group(1) or m.group(2))
    apply_, drop = plan_owned("codex", want, unmanaged, set())
    final = dict((n, want[n]) for n in apply_)
    block = render_codex(final) if final else []
    if start is not None:
        new = lines[:start] + block + lines[end + 1:]
        if not block and start > 0 and lines[start - 1] == "" and end + 1 >= len(lines):
            del new[start - 1]
    elif block:
        new = lines + ([""] if lines and lines[-1] != "" else []) + block
    else:
        new = lines
    for name in sorted(set(final) - old):
        print("%s  codex: %s" % ("would add" if dry else "added", name))
    for name in sorted(old - set(final)):
        print("%s  codex: %s" % ("would remove" if dry else "removed", name))
    if new == lines:
        for name in sorted(final):
            print("unchanged  codex: %s" % name)
        return sorted(final)
    if old == set(final):
        print("%s  codex: managed block" % ("would update" if dry else "updated"))
    if not dry:
        write_text(path, "\n".join(new) + "\n")
    return sorted(final)


def run_cli(argv, dry):
    """Run (or, in dry-run, print) a mutating CLI call; raises on failure."""
    text = " ".join(shlex.quote(a) for a in argv)
    if dry:
        print("would run  %s" % text)
        return
    r = subprocess.run(argv, cwd=home(), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError("%s failed: %s" % (text, r.stderr.decode(errors="replace").strip()
                                              or r.stdout.decode(errors="replace").strip()))
    print("ran  %s" % text)


def mcp_claude(want, owned, dry):
    try:
        with open(os.path.join(home(), ".claude.json")) as f:
            servers = (json.load(f).get("mcpServers") or {})
    except FileNotFoundError:
        servers = {}
    except (OSError, ValueError, AttributeError) as e:
        raise RuntimeError("cannot parse ~/.claude.json: %s" % e)
    apply_, drop = plan_owned("claude", want, servers, owned)
    new_owned = []
    for name in apply_:
        rendered = render_json("claude", want[name])
        cur = servers.get(name)
        new_owned.append(name)
        if cur is not None and all(cur.get(k) == v for k, v in rendered.items()):
            print("unchanged  claude: %s" % name)
            continue
        if cur is not None:
            run_cli(["claude", "mcp", "remove", "--scope", "user", name], dry)
        run_cli(["claude", "mcp", "add-json", "--scope", "user", name,
                 json.dumps(rendered)], dry)
    for name in drop:
        if name in servers:
            run_cli(["claude", "mcp", "remove", "--scope", "user", name], dry)
    return new_owned


def hermes_existing(path):
    """Read-only scan of config.yaml: {name: {key: scalar}} under mcp_servers."""
    out, in_block, child_indent, name = {}, False, None, None
    try:
        with open(path) as f:
            text = f.read().split("\n")
    except OSError:
        return out
    for ln in text:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip())
        if indent == 0:
            in_block = ln.split("#")[0].rstrip() == "mcp_servers:"
            child_indent = None
            continue
        if not in_block:
            continue
        key, _, val = ln.strip().partition(":")
        val = val.split(" #")[0].strip().strip("'\"")
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            name = key.strip("'\"")
            out[name] = {}
        elif name is not None:
            out[name][key] = val
    return out


def mcp_hermes(want, owned, dry):
    cfg = os.path.join(os.environ.get("HERMES_HOME") or os.path.join(home(), ".hermes"),
                       "config.yaml")
    existing = hermes_existing(cfg)
    remote = {}
    for name, e in want.items():
        if "url" in e:
            remote[name] = e
        else:
            print("skip  hermes: %s (stdio MCPs are not written for hermes)" % name)
    apply_, drop = plan_owned("hermes", remote, existing, owned)
    new_owned = []
    for name in apply_:
        e = remote[name]
        values = [("url", e["url"]), ("enabled", "true")]
        if e.get("auth"):
            values.append(("auth", e["auth"]))
        new_owned.append(name)
        cur = existing.get(name, {})
        todo = [(k, v) for k, v in values if cur.get(k) != v]
        if not todo:
            print("unchanged  hermes: %s" % name)
            continue
        for k, v in todo:
            run_cli(["hermes", "config", "set", "--force",
                     "mcp_servers.%s.%s" % (name, k), v], dry)
    for name in drop:
        if name in existing:
            run_cli(["hermes", "config", "unset", "mcp_servers.%s" % name], dry)
    return new_owned


def mcp(manifest, dry):
    h = home()
    entries, bad = mcp_entries(manifest)
    rc = 1 if bad else 0
    state = load_state()
    owned_all = state.get("mcp") if isinstance(state.get("mcp"), dict) else {}
    present = {
        "claude": shutil.which("claude") is not None,
        "codex": os.path.isdir(os.path.join(h, ".codex")),
        "cursor": os.path.isdir(os.path.join(h, ".cursor")),
        "omp": os.path.isdir(os.path.join(h, ".omp")),
        "opencode": os.path.isdir(os.path.join(h, ".config", "opencode")),
        "hermes": shutil.which("hermes") is not None
        and os.path.isdir(os.path.join(h, ".hermes")),
    }
    for harness in MCP_HARNESSES:
        if not present[harness]:
            print("skip  %s (not installed)" % harness)
            continue
        want = applicable(entries, harness)
        owned = set(owned_all.get(harness, []))
        try:
            if harness == "claude":
                new = mcp_claude(want, owned, dry)
            elif harness == "codex":
                new = mcp_codex(os.path.join(h, ".codex", "config.toml"), want, dry)
            elif harness == "hermes":
                new = mcp_hermes(want, owned, dry)
            else:
                path = {"cursor": os.path.join(h, ".cursor", "mcp.json"),
                        "omp": os.path.join(h, ".omp", "agent", "mcp.json"),
                        "opencode": os.path.join(h, ".config", "opencode",
                                                 "opencode.json")}[harness]
                new = mcp_json_file(harness, path, want, owned, dry)
        except (OSError, RuntimeError) as e:
            print("ERROR  %s: %s" % (harness, e))
            rc = 1
            continue  # keep the old record: nothing was confirmed
        owned_all[harness] = sorted(new)
    if not dry:
        state["mcp"] = owned_all
        if state != load_state():
            write_json(state_path(), state)
    return rc


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


STEPS = [("fetch", fetch), ("link", link), ("mcp", mcp),
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
