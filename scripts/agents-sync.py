#!/usr/bin/env python3
"""Sync agent skills, links, MCP servers and Claude plugins from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] {fetch|link|mcp|plugins|all|check}
`check` is a read-only drift report and is not part of `all`.
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
        with open(state_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_write(path, text):
    """Atomic write (tmp + rename); existing files keep their mode, new ones get 0644."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".agents-sync-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, os.stat(path).st_mode & 0o7777 if os.path.exists(path) else 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.lexists(tmp):
            os.unlink(tmp)
        raise


def write_json(path, data):
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_text(path, text):
    atomic_write(path, text)


def string_list(value):
    return (isinstance(value, list)
            and all(isinstance(x, str) and x in MCP_HARNESSES for x in value))


def mcp_entries(manifest, quiet=False):
    """Validated neutral entries; returns (entries, names that failed validation)."""
    entries, bad = {}, set()
    for name, e in (manifest.get("mcp") or {}).items():
        try:
            if not isinstance(e, dict):
                raise RuntimeError("entry must be an object")
            if "${" in json.dumps(e):
                raise RuntimeError("contains '${': env/header substitution is not supported")
            if ("command" in e) == ("url" in e):
                raise RuntimeError("needs exactly one of 'command' or 'url'")
            if "command" in e and not isinstance(e.get("args", []), list):
                raise RuntimeError("'args' must be a list")
            for key in ("except", "harnesses"):
                if key in e and not string_list(e[key]):
                    raise RuntimeError("'%s' must be a list of %s" % (key, "/".join(MCP_HARNESSES)))
        except RuntimeError as err:
            if not quiet:
                print("ERROR  mcp %s: %s" % (name, err))
            bad.add(name)
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


def plan_owned(harness, want, existing, owned, frozen=()):
    """Split by ownership: (names to write, owned names to remove).

    existing: names present in the harness; owned: names this sync wrote.
    A same-name entry that is not ours is never written (WARN). Frozen names
    (invalid manifest entries) are neither updated nor removed.
    """
    apply_, drop = [], []
    for name in want:
        if name in existing and name not in owned:
            print("WARN  %s: %s exists and is not managed, skipping" % (harness, name))
        else:
            apply_.append(name)
    for name in sorted(owned):
        if name in frozen:
            print("skip  %s: %s (invalid manifest entry)" % (harness, name))
        elif name not in want:
            drop.append(name)
    return apply_, drop


def mcp_json_file(harness, path, want, owned, dry, frozen):
    """cursor / omp / opencode: merge into one JSON object key.

    owned is the live ownership record: names are added before the write and
    dropped only after their removal was written.
    """
    try:
        with open(path, encoding="utf-8") as f:
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
    apply_, drop = plan_owned(harness, want, servers, owned, frozen)
    changed = False
    for name in apply_:
        rendered = render_json(harness, want[name])
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
        owned.update(apply_)  # record before the write
        doc[key] = servers
        write_json(path, doc)
    owned.update(apply_)
    owned.difference_update(drop)


CODEX_TABLE = re.compile(
    r'^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|([A-Za-z0-9_-]+))\s*(?:\]|\.)')
TOML_KEYPART = re.compile(
    r'''\s*(?:"((?:[^"\\]|\\.)*)"|'([^']*)'|([A-Za-z0-9_-]+))\s*''')


def toml_key(text, pos=0):
    """Parse a dotted TOML key from text[pos:]; returns (parts, end) or (None, pos)."""
    parts = []
    while True:
        m = TOML_KEYPART.match(text, pos)
        if not m:
            return None, pos
        parts.append(next(g for g in m.groups() if g is not None))
        pos = m.end()
        if pos < len(text) and text[pos] == ".":
            pos += 1
            continue
        return parts, pos


def codex_references(lines):
    """Server names referenced outside the managed block (any TOML spelling).

    Raises RuntimeError for a line mentioning mcp_servers that cannot be classified.
    """
    names, in_parent = set(), False
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            dbl = s.startswith("[[")
            inner = s[2 if dbl else 1:]
            parts, end = toml_key(inner)
            rest = inner[end:].lstrip() if parts else ""
            if parts and rest.startswith("]") and "mcp_servers" not in parts[1:]:
                in_parent = parts == ["mcp_servers"]
                if parts[0] == "mcp_servers" and len(parts) > 1:
                    names.add(parts[1])
                continue
            if "mcp_servers" in s:
                raise RuntimeError("cannot classify line mentioning mcp_servers: %s" % s)
            in_parent = False
            continue
        parts, end = toml_key(s)
        if parts and s[end:].startswith("="):
            if in_parent:
                names.add(parts[0])
            elif parts[0] == "mcp_servers":
                if len(parts) < 2:
                    raise RuntimeError("cannot classify line mentioning mcp_servers: %s" % s)
                names.add(parts[1])
            continue
        if "mcp_servers" in s:
            raise RuntimeError("cannot classify line mentioning mcp_servers: %s" % s)
    return names


def toml_name(name):
    return name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)


def render_codex(want, kept=None):
    """Managed block; kept = {name: verbatim lines} for frozen (invalid) entries."""
    kept = kept or {}
    lines = [MCP_START]
    for i, name in enumerate(sorted(set(want) | set(kept))):
        e = want.get(name)
        if i:
            lines.append("")
        if e is None:
            lines.extend(kept[name])
            continue
        lines.append("[mcp_servers.%s]" % toml_name(name))
        if "command" in e:
            lines.append("command = %s" % json.dumps(e["command"]))
            lines.append("args = [%s]" % ", ".join(json.dumps(a) for a in e.get("args", [])))
        else:
            lines.append("url = %s" % json.dumps(e["url"]))
    lines.append(MCP_END)
    return lines


def mcp_codex(path, want, owned, dry, frozen):
    """Managed block inside config.toml; text outside it is never changed."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        lines = [""]
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline is re-added on write
    starts = [i for i, ln in enumerate(lines) if ln.strip() == MCP_START]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == MCP_END]
    if (len(starts) > 1 or len(ends) > 1 or len(starts) != len(ends)
            or (starts and starts[0] > ends[0])):
        raise RuntimeError("corrupted agents-sync markers, refusing")
    start = starts[0] if starts else None
    end = ends[0] if ends else None
    outside = lines[:start] + lines[end + 1:] if start is not None else lines
    inside = lines[start + 1:end] if start is not None else []
    old, chunks, cur = set(), {}, None
    for ln in inside:
        m = CODEX_TABLE.match(ln)
        if m:
            cur = m.group(1) or m.group(2)
            old.add(cur)
            chunks[cur] = []
        if cur is not None and ln.strip():
            chunks[cur].append(ln)
    kept = dict((n, chunks[n]) for n in sorted(old & set(frozen)))
    for name in kept:
        print("skip  codex: %s (invalid manifest entry)" % name)
    unmanaged = codex_references(outside)
    apply_, _ = plan_owned("codex", want, unmanaged, set())
    final = dict((n, want[n]) for n in apply_)
    block = render_codex(final, kept) if final or kept else []
    if start is not None:
        new = lines[:start] + block + lines[end + 1:]
        if not block and start > 0 and lines[start - 1] == "" and end + 1 >= len(lines):
            del new[start - 1]
    elif block:
        new = lines + ([""] if lines and lines[-1] != "" else []) + block
    else:
        new = lines
    final_all = set(final) | set(kept)
    for name in sorted(set(final) - old):
        print("%s  codex: %s" % ("would add" if dry else "added", name))
    for name in sorted(old - final_all):
        print("%s  codex: %s" % ("would remove" if dry else "removed", name))
    if new == lines:
        for name in sorted(final):
            print("unchanged  codex: %s" % name)
    else:
        if old == final_all:
            print("%s  codex: managed block" % ("would update" if dry else "updated"))
        if not dry:
            owned.update(final_all)  # record before the write
            write_text(path, "\n".join(new) + "\n")
    owned.clear()
    owned.update(final_all)


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


def mcp_claude(want, owned, dry, frozen):
    try:
        with open(os.path.join(home(), ".claude.json"), encoding="utf-8") as f:
            servers = (json.load(f).get("mcpServers") or {})
        if not isinstance(servers, dict):
            raise ValueError("mcpServers is not an object")
    except FileNotFoundError:
        servers = {}
    except (OSError, ValueError, AttributeError) as e:
        raise RuntimeError("cannot parse ~/.claude.json: %s" % e)
    apply_, drop = plan_owned("claude", want, servers, owned, frozen)
    for name in apply_:
        rendered = render_json("claude", want[name])
        cur = servers.get(name)
        if (isinstance(cur, dict)
                and all(cur.get(k) == v for k, v in rendered.items())):
            print("unchanged  claude: %s" % name)
            owned.add(name)
            continue
        owned.add(name)  # record before the first mutating call
        if name in servers:
            run_cli(["claude", "mcp", "remove", "--scope", "user", name], dry)
        run_cli(["claude", "mcp", "add-json", "--scope", "user", name,
                 json.dumps(rendered)], dry)
    for name in drop:
        if name in servers:
            run_cli(["claude", "mcp", "remove", "--scope", "user", name], dry)
        owned.discard(name)  # only after the removal succeeded


def hermes_home():
    return os.environ.get("HERMES_HOME") or os.path.join(home(), ".hermes")


def hermes_existing(path):
    """Read-only scan of config.yaml: {name: {key: scalar}} under mcp_servers.

    Only keys directly under a server (one indent level) are read.
    """
    out, in_block, child_indent, sub_indent, name = {}, False, None, None, None
    with open(path, encoding="utf-8") as f:
        text = f.read().split("\n")
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
            name, sub_indent = key.strip("'\""), None
            out[name] = {}
        elif name is not None:
            if sub_indent is None:
                sub_indent = indent
            if indent == sub_indent and not key.startswith("-"):
                out[name][key] = val
    return out


def mcp_hermes(want, owned, dry, frozen):
    cfg = os.path.join(hermes_home(), "config.yaml")
    try:
        existing = hermes_existing(cfg)
    except FileNotFoundError:
        existing = {}
    remote = {}
    for name, e in want.items():
        if "url" in e:
            remote[name] = e
        else:
            print("skip  hermes: %s (stdio MCPs are not written for hermes)" % name)
    apply_, drop = plan_owned("hermes", remote, existing, owned, frozen)
    for name in apply_:
        e = remote[name]
        values = [("url", e["url"]), ("enabled", "true")]
        if e.get("auth"):
            values.append(("auth", e["auth"]))
        cur = existing.get(name, {})
        todo = [(k, v) for k, v in values
                if (cur.get(k, "").lower() not in ("true", "yes") if k == "enabled"
                    else cur.get(k) != v)]
        if not todo:
            print("unchanged  hermes: %s" % name)
            owned.add(name)
            continue
        owned.add(name)  # record before the first mutating call
        for k, v in todo:
            run_cli(["hermes", "config", "set", "--force",
                     "mcp_servers.%s.%s" % (name, k), v], dry)
    for name in drop:
        if name in existing:
            run_cli(["hermes", "config", "unset", "mcp_servers.%s" % name], dry)
        owned.discard(name)  # only after the removal succeeded


def mcp_present():
    h = home()
    return {
        "claude": shutil.which("claude") is not None,
        "codex": os.path.isdir(os.path.join(h, ".codex")),
        "cursor": os.path.isdir(os.path.join(h, ".cursor")),
        "omp": os.path.isdir(os.path.join(h, ".omp")),
        "opencode": os.path.isdir(os.path.join(h, ".config", "opencode")),
        "hermes": shutil.which("hermes") is not None
        and os.path.isdir(hermes_home()),
    }


def mcp_json_path(harness):
    h = home()
    return {"cursor": os.path.join(h, ".cursor", "mcp.json"),
            "omp": os.path.join(h, ".omp", "agent", "mcp.json"),
            "opencode": os.path.join(h, ".config", "opencode",
                                     "opencode.json")}[harness]


def mcp(manifest, dry):
    h = home()
    entries, frozen = mcp_entries(manifest)
    rc = 1 if frozen else 0
    state = load_state()
    recorded = state.get("mcp") if isinstance(state.get("mcp"), dict) else {}
    present = mcp_present()
    for harness in MCP_HARNESSES:
        if not present[harness]:
            print("skip  %s (not installed)" % harness)
            continue
        want = applicable(entries, harness)
        owned = set(recorded.get(harness, []))
        try:
            if harness == "claude":
                mcp_claude(want, owned, dry, frozen)
            elif harness == "codex":
                mcp_codex(os.path.join(h, ".codex", "config.toml"), want, owned, dry,
                          frozen)
            elif harness == "hermes":
                mcp_hermes(want, owned, dry, frozen)
            else:
                mcp_json_file(harness, mcp_json_path(harness), want, owned, dry,
                              frozen)
        except (OSError, RuntimeError, ValueError) as e:
            print("ERROR  %s: %s" % (harness, e))
            rc = 1
        finally:
            # persist what we may have written, even after a partial failure
            if not dry:
                recorded[harness] = sorted(owned)
                state["mcp"] = recorded
                if state != load_state():
                    write_json(state_path(), state)
    return rc


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


def read_json_keys(path, *keys):
    """Keys of the object at path[keys...]; missing file or key = empty set."""
    try:
        with open(path, encoding="utf-8") as f:
            node = json.load(f)
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as e:
        raise RuntimeError("cannot parse %s: %s" % (path, e))
    for k in keys:
        node = node.get(k) if isinstance(node, dict) else None
    if node is None:
        return set()
    if not isinstance(node, dict):
        raise RuntimeError("%s: unexpected structure" % path)
    return set(node)


def plugin_state():
    """(installed marketplaces, installed plugins) from Claude's own state files."""
    d = os.path.join(home(), ".claude", "plugins")
    return (read_json_keys(os.path.join(d, "known_marketplaces.json")),
            read_json_keys(os.path.join(d, "installed_plugins.json"), "plugins"))


def plugins(manifest, dry):
    if shutil.which("claude") is None:
        print("skip  plugins (claude not on PATH)")
        return 0
    cfg = manifest.get("plugins") or {}
    try:
        known, installed = plugin_state()
    except RuntimeError as e:
        print("ERROR  plugins: %s" % e)
        return 1
    rc = 0
    todo = [(["claude", "plugin", "marketplace", "add", repo], name)
            for name, repo in sorted((cfg.get("marketplaces") or {}).items())
            if name not in known]
    todo += [(["claude", "plugin", "install", p], p)
             for p in cfg.get("enabled") or [] if p not in installed]
    for argv, _ in todo:
        try:
            run_cli(argv, dry)
        except RuntimeError as e:
            print("ERROR  plugins: %s" % e)
            rc = 1
    if not todo:
        print("unchanged  plugins")
    return rc


def manifest_skills(manifest, skills_dir):
    """Skills the manifest expects on this host.

    Returns (expected, markers): expected = {name: (repo, path|None, ref|None)};
    markers = {name: marker} for every dir in skills_dir that has one. Group
    members are known only by `only` or, for `all` groups, by their marker.
    """
    host = socket.gethostname()
    markers = {}
    if os.path.isdir(skills_dir):
        for n in os.listdir(skills_dir):
            m = read_marker(os.path.join(skills_dir, n))
            if m is not None:
                markers[n] = m
    expected = {}
    for e in manifest.get("skills", []):
        if "hosts" in e and host not in e["hosts"]:
            continue
        if e.get("local"):
            expected[e["name"]] = None
        elif "name" in e:
            expected[e["name"]] = (e.get("repo"), e.get("path"), e.get("ref"))
        elif "only" in e:
            for n in e["only"]:
                expected[n] = (e.get("repo"), os.path.normpath(
                    os.path.join(e.get("path", "."), n)), e.get("ref"))
        else:
            for n, m in markers.items():
                if (m.get("repo") == e.get("repo")
                        and os.path.normpath(os.path.dirname(m.get("path", "")) or ".")
                        == os.path.normpath(e.get("path", "."))):
                    expected[n] = (e.get("repo"), None, e.get("ref"))
    return expected, markers


def tracked_in_repo(name):
    r = subprocess.run(["git", "ls-files", "agents/.agents/skills/" + name],
                       cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return bool(r.stdout.strip())


def drift_skills(manifest, out):
    h = home()
    sdir = os.path.join(h, ".agents", "skills")
    expected, markers = manifest_skills(manifest, sdir)
    on_disk = []
    if os.path.isdir(sdir):
        on_disk = sorted(n for n in os.listdir(sdir)
                         if not n.startswith(".") and not n.endswith(SYNC_SUFFIXES)
                         and os.path.isdir(os.path.join(sdir, n)))
    for n in on_disk:
        if n not in expected and not tracked_in_repo(n):
            out.append("unmanaged skill: %s (not in repo or manifest)" % n)
    for n, exp in sorted(expected.items()):
        if n not in on_disk:
            out.append("missing skill: %s (in manifest, not in %s)" % (n, sdir))
        elif exp is not None:
            m = markers.get(n)
            if m is None:
                out.append("skill %s has no %s marker" % (n, MARKER))
                continue
            for key, want in zip(("repo", "path", "ref"), exp):
                if want is not None and m.get(key) != want:
                    out.append("skill %s: marker %s %s differs from manifest %s"
                               % (n, key, m.get(key), want))
    links = [("claude", os.path.join(h, ".claude", "skills"), True),
             ("codex", os.path.join(h, ".codex", "skills"), True),
             ("hermes", os.path.join(h, ".hermes", "skills"),
              os.path.isdir(os.path.join(h, ".hermes")))]
    names = [n for n in on_disk if os.path.isfile(os.path.join(sdir, n, "SKILL.md"))]
    for harness, tdir, enabled in links:
        if not enabled:
            continue
        for n in names:
            allowed = harness_filter(manifest, n, os.path.join(sdir, n))
            path = os.path.join(tdir, n)
            if ((allowed is None or harness in allowed)
                    and os.path.lexists(path) and not os.path.islink(path)):
                out.append("real %s occupies link slot: %s"
                           % ("directory" if os.path.isdir(path) else "file", path))


def mcp_existing(harness):
    """Read-only: server names currently configured for a harness."""
    h = home()
    if harness == "claude":
        return read_json_keys(os.path.join(h, ".claude.json"), "mcpServers")
    if harness == "codex":
        try:
            with open(os.path.join(h, ".codex", "config.toml"), encoding="utf-8") as f:
                return codex_references(f.read().split("\n"))
        except FileNotFoundError:
            return set()
    if harness == "hermes":
        try:
            return set(hermes_existing(os.path.join(hermes_home(), "config.yaml")))
        except FileNotFoundError:
            return set()
    key = "mcp" if harness == "opencode" else "mcpServers"
    return read_json_keys(mcp_json_path(harness), key)


def drift_mcp(manifest, out):
    entries, bad = mcp_entries(manifest, quiet=True)
    for n in sorted(bad):
        out.append("invalid manifest MCP entry: %s" % n)
    state = load_state()
    recorded = state.get("mcp") if isinstance(state.get("mcp"), dict) else {}
    present = mcp_present()
    names = set(entries) | bad
    for harness in MCP_HARNESSES:
        if not present[harness]:
            continue
        try:
            existing = mcp_existing(harness)
        except (OSError, RuntimeError, ValueError) as e:
            out.append("cannot read %s MCP config: %s" % (harness, e))
            continue
        owned = set(recorded.get(harness, []))
        for n in sorted(existing - owned - names):
            out.append("unmanaged MCP: %s in %s" % (n, harness))
        want = applicable(entries, harness)
        if harness == "hermes":
            want = dict((n, e) for n, e in want.items() if "url" in e)
        for n in sorted(set(want) - existing):
            out.append("missing MCP: %s in %s" % (n, harness))


def drift_plugins(manifest, out):
    cfg = manifest.get("plugins") or {}
    enabled = set(cfg.get("enabled") or [])
    if shutil.which("claude") is not None:
        try:
            known, installed = plugin_state()
        except RuntimeError as e:
            out.append("cannot read Claude plugin state: %s" % e)
        else:
            for m in sorted(set(cfg.get("marketplaces") or {}) - known):
                out.append("marketplace not added: %s" % m)
            for p in sorted(enabled - installed):
                out.append("plugin not installed: %s" % p)
            for p in sorted(installed - enabled):
                out.append("unmanaged plugin installed: %s (not in manifest)" % p)
    path = os.path.join(REPO, "claude", ".claude", "settings.json")
    try:
        with open(path, encoding="utf-8") as f:
            ep = json.load(f).get("enabledPlugins") or {}
    except (OSError, ValueError, AttributeError):
        return
    in_settings = set(k for k, v in ep.items() if v is True)
    for p in sorted(in_settings - enabled):
        out.append("settings.json enables %s, not in manifest" % p)
    for p in sorted(enabled - in_settings):
        out.append("manifest enables %s, not enabled in settings.json" % p)


def check(manifest):
    """Read-only drift report: WARN lines, or OK; never writes, always exit 0."""
    out = []
    for fn in (drift_skills, drift_mcp, drift_plugins):
        try:
            fn(manifest, out)
        except (OSError, RuntimeError, ValueError) as e:
            out.append("%s failed: %s" % (fn.__name__, e))
    for line in out:
        print("WARN  drift: %s" % line)
    if not out:
        print("OK    drift: none")
    return 0


STEPS = [("fetch", fetch), ("link", link), ("mcp", mcp), ("plugins", plugins)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would change, write nothing")
    p.add_argument("step", choices=[s for s, _ in STEPS] + ["all", "check"])
    p.add_argument("--manifest", default=MANIFEST, help=argparse.SUPPRESS)
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
            print("WARN  manifest unreadable, linking without harness filters")
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
