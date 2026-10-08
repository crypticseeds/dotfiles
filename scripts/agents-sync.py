#!/usr/bin/env python3
"""Sync agent skills, links, MCP servers and Claude plugins from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] {fetch|link|mcp|plugins|all|check}
`check` is a read-only drift report and is not part of `all`.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "agents", ".agents", "manifest.json")
MARKER = ".managed-by-manifest"
SYNC_SUFFIXES = (".tmp-sync", ".old-sync")
GIT_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")

def home():
    return os.path.expanduser("~")

def atomic_write(path, text):
    """Write via tmp + rename; existing files keep their mode, new ones get 0644."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".agents-sync-tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, os.stat(path).st_mode & 0o7777 if os.path.exists(path) else 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise

def cli(argv):
    try:
        return subprocess.run(argv, cwd=home(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    except subprocess.TimeoutExpired:
        raise RuntimeError("%s failed: timed out after 300s" % " ".join(argv))

def run_cli(argv, dry):
    """Run (or, in dry-run, print) a mutating CLI call; raises on failure."""
    text = " ".join(shlex.quote(a) for a in argv)
    if dry:
        print("would run  %s" % text)
        return
    r = cli(argv)
    if r.returncode != 0:
        raise RuntimeError("%s failed: %s" % (text, (r.stderr or r.stdout).decode(errors="replace").strip()))
    print("ran  %s" % text)

# --- fetch -------------------------------------------------------------------
def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def checkout(entry):
    """Shallow, sparse checkout of entry['ref'] into the cache; return its dir."""
    cache = os.path.join(home(), ".cache", "dotfiles-skills",
                         entry["repo"].replace("/", "__"))
    os.makedirs(cache, exist_ok=True)
    if not os.path.isdir(os.path.join(cache, ".git")):
        git(cache, "init", "-q")
    try:
        git(cache, "cat-file", "-e", entry["ref"] + "^{commit}")
    except subprocess.CalledProcessError:
        git(cache, "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30", "fetch", "-q",
            "--depth", "1", "https://github.com/%s.git" % entry["repo"], entry["ref"])
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
    had_old = os.path.lexists(target)
    try:
        shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(".git", ".gitignore"))
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("*\n")
        with open(os.path.join(tmp, MARKER), "w") as f:
            json.dump({"repo": entry["repo"], "path": skill_path, "ref": entry["ref"]}, f)
            f.write("\n")
        if had_old:
            os.rename(target, old)
        os.rename(tmp, target)
    except BaseException:
        if had_old and not os.path.lexists(target):
            os.rename(old, target)
        remove(tmp)
        raise
    remove(old)

def sync_skill(entry, name, src, skill_path, skills_dir):
    target = os.path.join(skills_dir, name)
    marker = read_marker(target)
    if os.path.lexists(target) and (os.path.islink(target) or marker is None):
        print("WARN  %s exists and is not managed by the manifest, skipping" % target)
    elif (marker and marker.get("ref") == entry["ref"] and marker.get("repo") == entry["repo"]
          and marker.get("path") == skill_path and os.path.isfile(os.path.join(target, "SKILL.md"))):
        print("unchanged  %s" % name)
    else:
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
            missing = [k for k in ("repo", "ref", "path") if not entry.get(k)]
            if missing:
                raise RuntimeError("missing %s" % ", ".join(missing))
            if not re.fullmatch(r"[0-9a-f]{40}", entry["ref"]):
                raise RuntimeError("ref is not a 40-hex commit SHA: %r" % entry["ref"])
            if dry:
                print("would fetch  %s (%s@%s)" % (label, entry["repo"], entry["ref"][:12]))
                continue
            os.makedirs(skills_dir, exist_ok=True)
            base = os.path.join(checkout(entry), entry["path"])
            if "name" in entry:
                sync_skill(entry, entry["name"], base, entry["path"], skills_dir)
                continue
            names = entry.get("only") or sorted(
                n for n in os.listdir(base) if os.path.isfile(os.path.join(base, n, "SKILL.md")))
            for name in names:
                sync_skill(entry, name, os.path.join(base, name),
                           os.path.normpath(os.path.join(entry["path"], name)), skills_dir)
        except (subprocess.CalledProcessError, OSError, RuntimeError) as e:
            detail = getattr(e, "stderr", None)
            print("ERROR  %s: %s" % (label, detail.decode(errors="replace").strip() if detail else e))
            failed = True
    return 1 if failed else 0

# --- link --------------------------------------------------------------------
def owner(manifest, name, marker):
    """The manifest skill entry that provides skills/<name>, or None."""
    marker = marker or {}
    for e in manifest.get("skills", []):
        if e.get("name") == name:
            return e
        if ("name" not in e and marker.get("repo") == e.get("repo")
                and marker.get("path") == entry_path(e, name)
                and name in e.get("only", [name])):
            return e
    return None

def entry_path(e, name):
    return e.get("path") if "name" in e else os.path.normpath(os.path.join(e.get("path", "."), name))

def link(manifest, dry):
    h = home()
    src_dir = os.path.join(h, ".agents", "skills")
    names = sorted(n for n in os.listdir(src_dir) if not n.endswith(SYNC_SUFFIXES)
                   and os.path.isfile(os.path.join(src_dir, n, "SKILL.md"))
                   ) if os.path.isdir(src_dir) else []
    targets = [("claude", os.path.join(h, ".claude", "skills")),
               ("codex", os.path.join(h, ".codex", "skills"))]
    if os.path.isdir(hermes_home()):
        targets.append(("hermes", os.path.join(h, ".hermes", "skills")))
    rc = 0
    for harness, tdir in targets:
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
    for n in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
        path = os.path.join(tdir, n)  # prune dangling links into ~/.agents/skills only
        if (os.path.islink(path) and not os.path.exists(path)
                and os.path.realpath(path).startswith(os.path.realpath(src_dir) + os.sep)):
            print("%s  %s" % ("would prune" if dry else "pruned", path))
            if not dry:
                os.unlink(path)
    for name in names:
        src = os.path.join(src_dir, name)
        path = os.path.join(tdir, name)
        allowed = (owner(manifest, name, read_marker(src)) or {}).get("harnesses")
        ours = os.path.islink(path) and os.path.realpath(path) == os.path.realpath(src)
        if allowed is not None and harness not in allowed:
            if ours:
                print("%s  %s" % ("would unlink" if dry else "unlinked", path))
                if not dry:
                    os.unlink(path)
        elif ours:
            continue
        elif os.path.lexists(path):
            kind = "a symlink to elsewhere" if os.path.islink(path) else (
                "a real directory" if os.path.isdir(path) else "a real file")
            print("WARN  %s is %s, not linked" % (path, kind))
        elif dry:
            print("would link  %s -> %s" % (path, src))
        else:
            os.symlink(src, path)
            print("linked  %s" % path)

# --- mcp ---------------------------------------------------------------------
# Every manifest MCP applicable to a present harness is managed there: created
# if missing, updated if different, left alone if equal. Names not in the
# manifest are never touched, and nothing is ever removed.

MCP_START = "# >>> agents-sync managed MCP (do not edit)"
MCP_END = "# <<< agents-sync managed MCP"
MCP_HARNESSES = ("claude", "codex", "cursor", "omp", "opencode", "hermes")
SCHEMA = "https://opencode.ai/config.json"
CODEX_TABLE = re.compile(
    r'^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*(?:\]|\.)', re.M)

def mcp_error(e):
    if not isinstance(e, dict):
        return "entry must be an object"
    if "${" in json.dumps(e):
        return "contains '${': env/header substitution is not supported"
    if ("command" in e) == ("url" in e):
        return "needs exactly one of 'command' or 'url'"
    for key in ("args", "except", "harnesses"):
        v = e.get(key, [])
        if not isinstance(v, list) or (key != "args" and any(x not in MCP_HARNESSES for x in v)):
            return "'%s' must be a list%s" % (key, "" if key == "args" else " of harness names")
    return None

def mcp_entries(manifest):
    """Valid manifest MCP entries and the number of invalid ones (skipped)."""
    entries, bad = {}, 0
    for name, e in (manifest.get("mcp") or {}).items():
        err = mcp_error(e)
        if err is None:
            entries[name] = e
            continue
        bad += 1
        print("ERROR  mcp %s: %s" % (name, err))
    return entries, bad

def applicable(entries, harness):
    return dict((n, e) for n, e in entries.items()
                if harness in e.get("harnesses", MCP_HARNESSES)
                and harness not in e.get("except", [])
                and (harness != "hermes" or "url" in e))

def hermes_home():
    return os.environ.get("HERMES_HOME") or os.path.join(home(), ".hermes")

def mcp_present():
    h = home()
    return {"claude": shutil.which("claude") is not None,
            "codex": os.path.isdir(os.path.join(h, ".codex")),
            "cursor": os.path.isdir(os.path.join(h, ".cursor")),
            "omp": shutil.which("omp") is not None or os.path.isdir(os.path.join(h, ".omp")),
            "opencode": os.path.isdir(os.path.join(h, ".config", "opencode")),
            "hermes": shutil.which("hermes") is not None and os.path.isdir(hermes_home())}

def say(dry, verb, harness, name):
    past = {"add": "added", "update": "updated"}[verb]
    print("%s  %s: %s" % ("would " + verb if dry else past, harness, name))

def render_json(harness, e):
    cmd, args = e.get("command"), e.get("args", [])
    if harness == "opencode":
        if cmd:
            return {"type": "local", "command": [cmd] + args, "enabled": True}
        return {"type": "remote", "url": e["url"], "enabled": True}
    if harness == "cursor":
        return {"command": cmd, "args": args} if cmd else {"url": e["url"]}
    if cmd:  # claude, omp
        return {"type": "stdio", "command": cmd, "args": args}
    return {"type": "http", "url": e["url"]}

def same(harness, current, wanted):
    if harness == "claude":  # claude adds fields of its own; compare ours only
        return isinstance(current, dict) and all(current.get(k) == v for k, v in wanted.items())
    return current == wanted

def load_servers(harness):
    """(path, document, key, servers) of a JSON-config harness; missing file = empty."""
    h = home()
    path = {"claude": os.path.join(h, ".claude.json"),
            "cursor": os.path.join(h, ".cursor", "mcp.json"),
            "omp": os.path.join(h, ".omp", "agent", "mcp.json"),
            "opencode": os.path.join(h, ".config", "opencode", "opencode.json")}[harness]
    key = "mcp" if harness == "opencode" else "mcpServers"
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        doc = {"$schema": SCHEMA} if harness == "opencode" else {}
    except (OSError, ValueError) as e:
        raise RuntimeError("cannot parse %s: %s" % (path, e))
    servers = doc.get(key) or {} if isinstance(doc, dict) else None
    if not isinstance(servers, dict):
        raise RuntimeError("%s: unexpected structure" % path)
    return path, doc, key, servers

def mcp_json(harness, want, dry):
    """claude (via its CLI), cursor, omp, opencode: create or update manifest names."""
    path, doc, key, servers = load_servers(harness)
    changed = False
    for name in sorted(want):
        new = render_json(harness, want[name])
        if same(harness, servers.get(name), new):
            continue
        if harness == "claude":
            if name in servers:
                run_cli(["claude", "mcp", "remove", "--scope", "user", name], dry)
            run_cli(["claude", "mcp", "add-json", "--scope", "user", name,
                     json.dumps(new)], dry)
        else:
            say(dry, "update" if name in servers else "add", harness, name)
            servers[name] = new
            changed = True
    if changed and not dry:
        doc[key] = servers
        atomic_write(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")

def toml_name(name):
    return name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)

def codex_chunk(name, e):
    lines = ["[mcp_servers.%s]" % toml_name(name)]
    if "command" in e:
        lines.append("command = %s" % json.dumps(e["command"]))
        lines.append("args = [%s]" % ", ".join(json.dumps(a) for a in e.get("args", [])))
    else:
        lines.append("url = %s" % json.dumps(e["url"]))
    return lines

def codex_read(path):
    """(lines, start, end, chunks, outside): file lines, block marker indexes
    (None without a block), the block's {name: lines}, and server names with a
    table outside the block."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        lines = []
    if lines and lines[-1] == "":
        lines.pop()
    starts = [i for i, ln in enumerate(lines) if ln.strip() == MCP_START]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == MCP_END]
    if len(starts) > 1 or len(starts) != len(ends) or (starts and starts[0] > ends[0]):
        raise RuntimeError("corrupted agents-sync markers in %s, refusing" % path)
    start, end = (starts[0], ends[0]) if starts else (None, None)
    inside = lines[start + 1:end] if starts else []
    outside = lines[:start] + lines[end + 1:] if starts else lines
    chunks, cur = {}, None
    for ln in inside:
        m = CODEX_TABLE.match(ln)
        if m:
            cur = m.group(1) or m.group(2)
            chunks.setdefault(cur, [])
        if cur is not None and ln.strip():
            chunks[cur].append(ln)
    names = set(a or b for a, b in CODEX_TABLE.findall("\n".join(outside)))
    return lines, start, end, chunks, names

def mcp_codex(want, dry):
    """Regenerate the managed block; names in it that are not in `want` are kept."""
    path = os.path.join(home(), ".codex", "config.toml")
    lines, start, end, chunks, outside = codex_read(path)
    final = dict((n, c) for n, c in chunks.items() if n not in outside)
    for name in sorted(want):
        if name in outside:
            print("WARN  codex: %s has a [mcp_servers.%s] table outside the managed "
                  "block, not managed" % (name, name))
            continue
        final[name] = codex_chunk(name, want[name])
        if chunks.get(name) != final[name]:
            say(dry, "update" if name in chunks else "add", "codex", name)
    block = [MCP_START]
    for i, name in enumerate(sorted(final)):
        block += ([""] if i else []) + final[name]
    block.append(MCP_END)
    if start is not None:
        new = lines[:start] + block + lines[end + 1:]
    elif final:
        new = lines + ([""] if lines and lines[-1] != "" else []) + block
    else:
        new = lines
    if new != lines and not dry:
        atomic_write(path, "\n".join(new) + "\n")

def hermes_todo(name, e):
    values = [("url", e["url"]), ("enabled", "true")]
    if e.get("auth"):
        values.append(("auth", e["auth"]))
    todo = []
    for k, v in values:
        r = cli(["hermes", "config", "get", "mcp_servers.%s.%s" % (name, k)])
        cur = r.stdout.decode(errors="replace").strip().strip("'\"") if r.returncode == 0 else ""
        if cur.lower() not in ("true", "yes") if k == "enabled" else cur != v:
            todo.append((k, v))
    return todo

def mcp_hermes(want, dry):
    for name in sorted(want):
        for k, v in hermes_todo(name, want[name]):
            run_cli(["hermes", "config", "set", "--force",
                     "mcp_servers.%s.%s" % (name, k), v], dry)

def mcp(manifest, dry):
    entries, bad = mcp_entries(manifest)
    rc = 1 if bad else 0
    present = mcp_present()
    for harness in MCP_HARNESSES:
        if not present[harness]:
            print("skip  %s (not installed)" % harness)
            continue
        want = applicable(entries, harness)
        try:
            if harness == "codex":
                mcp_codex(want, dry)
            elif harness == "hermes":
                mcp_hermes(want, dry)
            else:
                mcp_json(harness, want, dry)
        except (OSError, RuntimeError, ValueError) as e:
            print("ERROR  %s: %s" % (harness, e))
            rc = 1
    return rc

# --- plugins -----------------------------------------------------------------
def plugin_state():
    """(installed marketplaces, installed plugins) from Claude's own state files."""
    d = os.path.join(home(), ".claude", "plugins")
    out = []
    for name, key in (("known_marketplaces.json", None), ("installed_plugins.json", "plugins")):
        try:
            with open(os.path.join(d, name), encoding="utf-8") as f:
                node = json.load(f)
        except FileNotFoundError:
            node = {}
        except (OSError, ValueError) as e:
            raise RuntimeError("cannot parse %s: %s" % (os.path.join(d, name), e))
        node = node.get(key) if key and isinstance(node, dict) else node
        out.append(set(node) if isinstance(node, dict) else set())
    return out

def plugins(manifest, dry):
    """Add missing marketplaces and install missing enabled plugins; never uninstall."""
    if shutil.which("claude") is None:
        print("skip  plugins (claude not on PATH)")
        return 0
    cfg = manifest.get("plugins") or {}
    try:
        known, installed = plugin_state()
    except RuntimeError as e:
        print("ERROR  plugins: %s" % e)
        return 1
    todo = [["claude", "plugin", "marketplace", "add", repo]
            for name, repo in sorted((cfg.get("marketplaces") or {}).items())
            if name not in known]
    todo += [["claude", "plugin", "install", p]
             for p in cfg.get("enabled") or [] if p not in installed]
    rc = 0
    for argv in todo:
        try:
            run_cli(argv, dry)
        except RuntimeError as e:
            print("ERROR  plugins: %s" % e)
            rc = 1
    return rc

# --- check -------------------------------------------------------------------
def tracked_in_repo(name):
    r = subprocess.run(["git", "ls-files", "agents/.agents/skills/" + name],
                       cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return bool(r.stdout.strip())

def drift_skills(manifest, out):
    sdir = os.path.join(home(), ".agents", "skills")
    on_disk = sorted(n for n in os.listdir(sdir) if not n.startswith(".")
                     and not n.endswith(SYNC_SUFFIXES)
                     and os.path.isdir(os.path.join(sdir, n))) if os.path.isdir(sdir) else []
    for n in on_disk:
        marker = read_marker(os.path.join(sdir, n))
        e = owner(manifest, n, marker)
        if e is None:
            if marker is None and not tracked_in_repo(n):
                out.append("unmanaged skill: %s (not in repo or manifest)" % n)
        elif not e.get("local"):
            want = {"repo": e.get("repo"), "path": entry_path(e, n), "ref": e.get("ref")}
            if marker is None:
                out.append("skill %s has no %s marker" % (n, MARKER))
            for key in want if marker else ():
                if marker.get(key) != want[key]:
                    out.append("skill %s: marker %s %s differs from manifest %s"
                               % (n, key, marker.get(key), want[key]))
    host = socket.gethostname()
    for e in manifest.get("skills", []):
        for n in [e["name"]] if "name" in e else e.get("only", []):
            if n not in on_disk and ("hosts" not in e or host in e["hosts"]):
                out.append("missing skill: %s (in manifest, not in %s)" % (n, sdir))

def drift_mcp(manifest, out):
    """Whatever `mcp --dry-run` would change is drift (it only reads)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mcp(manifest, True)
    for line in buf.getvalue().splitlines():
        if line.startswith(("would ", "ERROR")):
            out.append("MCP out of sync: %s" % line)

def drift_plugins(manifest, out):
    if shutil.which("claude") is not None:
        installed = plugin_state()[1]
        for p in (manifest.get("plugins") or {}).get("enabled") or []:
            if p not in installed:
                out.append("plugin not installed: %s" % p)

def check(manifest):
    """Read-only drift report: WARN lines, or OK; never writes, always exit 0."""
    out = []
    for fn in (drift_skills, drift_mcp, drift_plugins):
        try:
            fn(manifest, out)
        except Exception as e:
            print("WARN  drift: %s failed: %s" % (fn.__name__, e))
    print("\n".join("WARN  drift: " + line for line in out) or "OK    drift: none")
    return 0


STEPS = [("fetch", fetch), ("link", link), ("mcp", mcp), ("plugins", plugins)]

def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would change, write nothing")
    p.add_argument("--manifest", default=MANIFEST, help=argparse.SUPPRESS)
    p.add_argument("step", choices=[s for s, _ in STEPS] + ["all", "check"])
    args = p.parse_args()
    try:
        with open(args.manifest) as f:
            manifest = json.load(f)
    except (OSError, ValueError) as e:
        if args.step == "check":
            print("WARN  drift: manifest %s unreadable: %s" % (args.manifest, e))
            return 0
        print("ERROR  manifest %s: %s" % (args.manifest, e))
        if args.step in ("link", "all"):
            link({}, args.dry_run)
        return 1
    if args.step == "check":
        return check(manifest)
    rc = 0
    for name, fn in STEPS:
        if args.step in (name, "all"):
            rc = fn(manifest, args.dry_run) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
