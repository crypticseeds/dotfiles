#!/usr/bin/env python3
"""Sync agent skills, links, MCP servers and Claude plugins from the manifest.

Source of truth: agents/.agents/manifest.json. Stdlib only, Python 3.9 safe.
Usage: agents-sync.py [--dry-run] [--project DIR] {fetch|link|mcp|project|plugins|all|check}
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


def marker_for(entry, skill_path):
    m = {"repo": entry["repo"], "path": skill_path, "ref": entry["ref"]}
    if entry.get("rewrite"):
        m["rewrite"] = entry["rewrite"]
    return m


def apply_rewrite(root, rewrite):
    """Replace each literal key with its value in every UTF-8 text file under root."""
    for d, _, files in os.walk(root):
        for fn in files:
            p = os.path.join(d, fn)
            if os.path.islink(p):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue
            new = text
            for old, repl in rewrite.items():
                new = new.replace(old, repl)
            if new != text:
                atomic_write(p, new)


def install(src, target, entry, skill_path):
    """Build into <target>.tmp-sync, then swap in; never leave a half-deleted target."""
    tmp, old = target + ".tmp-sync", target + ".old-sync"
    remove(tmp)
    remove(old)
    had_old = os.path.lexists(target)
    try:
        shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(".git", ".gitignore"))
        if entry.get("rewrite"):
            apply_rewrite(tmp, entry["rewrite"])
        with open(os.path.join(tmp, ".gitignore"), "w") as f:
            f.write("*\n")
        with open(os.path.join(tmp, MARKER), "w") as f:
            json.dump(marker_for(entry, skill_path), f)
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
    elif marker == marker_for(entry, skill_path) and os.path.isfile(os.path.join(target, "SKILL.md")):
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
            rw = entry.get("rewrite", {})
            if not (isinstance(rw, dict) and all(isinstance(k, str) and k and isinstance(v, str)
                                                 for k, v in rw.items())):
                raise RuntimeError("rewrite must map non-empty strings to strings")
            if dry:
                print("would fetch  %s (%s@%s)" % (label, entry["repo"], entry["ref"][:12]))
                continue
            os.makedirs(skills_dir, exist_ok=True)
            base = os.path.join(checkout(entry), entry["path"])
            if "name" in entry:
                sync_skill(entry, entry["name"], base, entry["path"], skills_dir)
                continue
            names = entry["only"] if "only" in entry else sorted(
                n for n in os.listdir(base) if os.path.isfile(os.path.join(base, n, "SKILL.md")))
            for name in names:
                sync_skill(entry, name, os.path.join(base, name),
                           os.path.normpath(os.path.join(entry["path"], name)), skills_dir)
        except (subprocess.CalledProcessError, OSError, RuntimeError) as e:
            detail = getattr(e, "stderr", None)
            print("ERROR  %s: %s" % (label, detail.decode(errors="replace").strip() if detail else e))
            failed = True
    report_stale(manifest, skills_dir)
    return 1 if failed else 0


def stale_skills(manifest, skills_dir):
    """Skills the sync installed (they carry its marker) that no manifest entry claims any more."""
    stale = []
    for n in sorted(os.listdir(skills_dir)) if os.path.isdir(skills_dir) else []:
        marker = read_marker(os.path.join(skills_dir, n))
        if not n.endswith(SYNC_SUFFIXES) and marker is not None and owner(manifest, n, marker) is None:
            stale.append(n)
    return stale


def remove_command(skills_dir, names):
    """Never delete: print the command so the user decides. `make skills` prunes the links."""
    return "rm -r %s && make -C %s skills" % (
        " ".join(shlex.quote(os.path.join(skills_dir, n)) for n in names), shlex.quote(REPO))


def report_stale(manifest, skills_dir):
    stale = stale_skills(manifest, skills_dir)
    for n in stale:
        print("WARN  %s is no longer in the manifest (not removed)" % os.path.join(skills_dir, n))
    if stale:
        print("      remove with: %s" % remove_command(skills_dir, stale))


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
# ${VAR} in a header value names an env var (a Doppler name); it is rendered
# into each harness's own reference syntax and never resolved by the sync.
ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def mcp_error(e):
    if not isinstance(e, dict):
        return "entry must be an object"
    headers = e.get("headers", {})
    if not isinstance(headers, dict) or not all(isinstance(v, str) for v in headers.values()):
        return "'headers' must be an object of strings"
    rest = dict((k, v) for k, v in e.items() if k != "headers")
    if "${" in json.dumps(rest) or any("${" in ENV_REF.sub("", v) for v in headers.values()):
        return "'${' is only allowed as ${VAR} inside header values"
    if ("command" in e) == ("url" in e):
        return "needs exactly one of 'command' or 'url'"
    if headers and "url" not in e:
        return "'headers' needs 'url'"
    for key in ("args", "except", "harnesses"):
        v = e.get(key, [])
        if not isinstance(v, list) or (key != "args" and any(x not in MCP_HARNESSES for x in v)):
            return "'%s' must be a list%s" % (key, "" if key == "args" else " of harness names")
    if not isinstance(e.get("project", False), bool):
        return "'project' must be true or false"
    targets = mcp_targets(e)
    if headers and "hermes" in targets and not e.get("project"):  # hermes has no project config
        # `hermes config get` prints resolved values, so ${VAR} headers can't be compared
        return "hermes does not support 'headers' here; add \"hermes\" to 'except'"
    if "codex" in targets and any(ENV_REF.search(v) and not codex_env(k, v)
                                  for k, v in headers.items()):
        return ("codex takes only a whole ${VAR} header value or 'Authorization: Bearer "
                "${VAR}'; add \"codex\" to 'except'")
    return None


def mcp_targets(e):
    """Harnesses an entry applies to (before presence and transport limits)."""
    return set(e.get("harnesses", MCP_HARNESSES)) - set(e.get("except", []))


def codex_env(header, value):
    """('bearer'|'env', VAR) when codex can express this header from an env var, else None."""
    m = re.fullmatch(r"Bearer " + ENV_REF.pattern, value)
    if header.lower() == "authorization" and m:
        return "bearer", m.group(1)
    m = ENV_REF.fullmatch(value)
    return ("env", m.group(1)) if m else None


def mcp_entries(manifest, report=True):
    """Valid manifest MCP entries and the number of invalid ones (skipped)."""
    entries, bad = {}, 0
    for name, e in (manifest.get("mcp") or {}).items():
        err = mcp_error(e)
        if err is None:
            entries[name] = e
            continue
        bad += 1
        if report:
            print("ERROR  mcp %s: %s" % (name, err))
    return entries, bad


def applicable(entries, harness):
    """Global (non-project) entries for a harness."""
    return dict((n, e) for n, e in entries.items()
                if not e.get("project") and harness in mcp_targets(e)
                and (harness != "hermes" or "url" in e))


def hermes_home():
    return os.environ.get("HERMES_HOME") or os.path.join(home(), ".hermes")


def mcp_present():
    """A harness counts as present when its CLI is installed (on PATH or in its installer's
    default dir) or its config dir exists: a fresh install has no config dir until first run."""
    h = home()

    def cli_or_dir(names, bindirs, cfg):
        return (any(shutil.which(n) for n in names)
                or any(os.access(os.path.join(h, d, n), os.X_OK) for d in bindirs for n in names)
                or os.path.isdir(os.path.join(h, *cfg)))
    local = [os.path.join(".local", "bin")]
    return {"claude": shutil.which("claude") is not None,
            "codex": cli_or_dir(["codex"], local, [".codex"]),
            "cursor": cli_or_dir(["cursor-agent", "cursor"], local, [".cursor"]),
            "omp": cli_or_dir(["omp"], local, [".omp"]),
            "opencode": cli_or_dir(["opencode"], [os.path.join(".opencode", "bin")] + local,
                                   [".config", "opencode"]),
            "hermes": shutil.which("hermes") is not None and os.path.isdir(hermes_home())}


def say(dry, verb, where, name):
    past = {"add": "added", "update": "updated", "remove": "removed"}[verb]
    print("%s  %s: %s" % ("would " + verb if dry else past, where, name))


def env_headers(e, fmt):
    """Header dict with each ${VAR} rewritten as fmt % VAR ({} without headers)."""
    h = e.get("headers")
    if not h:
        return {}
    return {"headers": dict((k, ENV_REF.sub(lambda m: fmt % m.group(1), v))
                            for k, v in h.items())}


def render_json(harness, e):
    cmd, args = e.get("command"), e.get("args", [])
    if harness == "opencode":  # v2 shape, under mcp.servers
        if cmd:
            return {"type": "local", "command": [cmd] + args}
        out = dict({"type": "remote", "url": e["url"]}, **env_headers(e, "{env:%s}"))
        if "headers" in e and e.get("auth") != "oauth":
            out["oauth"] = False  # header credential only: skip v2's default OAuth discovery
        return out
    if harness == "cursor":
        if cmd:
            return {"command": cmd, "args": args}
        return dict({"url": e["url"]}, **env_headers(e, "${env:%s}"))
    if cmd:  # claude, omp
        return {"type": "stdio", "command": cmd, "args": args}
    return dict({"type": "http", "url": e["url"]}, **env_headers(e, "${%s}"))


def same(harness, current, wanted):
    if harness == "claude":  # claude adds fields of its own; compare ours only
        return isinstance(current, dict) and all(current.get(k) == v for k, v in wanted.items())
    return current == wanted


def claude_config():
    """The global config file Claude Code actually uses: a legacy <config dir>/.config.json,
    when present, wins over .claude.json (Claude's own rule)."""
    cfg_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    legacy = os.path.join(cfg_dir or os.path.join(home(), ".claude"), ".config.json")
    if os.path.exists(legacy):
        return legacy
    return os.path.join(cfg_dir or home(), ".claude.json")


def load_servers(harness):
    """(path, document, legacy, servers) of a JSON-config harness; missing file = empty."""
    h = home()
    path = {"claude": claude_config(),
            "cursor": os.path.join(h, ".cursor", "mcp.json"),
            "omp": os.path.join(h, ".omp", "agent", "mcp.json"),
            "opencode": os.path.join(h, ".config", "opencode", "opencode.json")}[harness]
    if harness == "claude" and path.endswith(".config.json"):
        print("WARN  claude: uses %s, so .claude.json (and the MCPs in it) is ignored; an "
              "empty or stray one is usually a sandbox leftover" % path)
    key = "mcp" if harness == "opencode" else "mcpServers"
    doc, servers, legacy = read_servers(path, key, harness == "opencode")
    return path, doc, legacy, servers


def read_servers(path, key, opencode):
    """(document, servers, legacy) of a JSON MCP file; a missing file is empty. `servers` is the
    live dict inside the document. opencode v2 keeps servers under mcp.servers; `legacy` is the
    mcp object itself, where v1 kept them (None for other harnesses)."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        doc = {"$schema": SCHEMA} if opencode else {}
    except (OSError, ValueError) as e:
        raise RuntimeError("cannot parse %s: %s" % (path, e))
    parent = doc.setdefault(key, {}) if isinstance(doc, dict) else None
    servers = parent.setdefault("servers", {}) if opencode and isinstance(parent, dict) else parent
    if not isinstance(servers, dict):
        raise RuntimeError("%s: unexpected structure" % path)
    return doc, servers, (parent if opencode else None)


def drop_legacy(legacy, name, dry, where):
    """Remove a v1 opencode entry (mcp.<name>) that mcp.servers.<name> now replaces."""
    if legacy is not None and isinstance(legacy.get(name), dict) and name not in ("servers", "timeout"):
        print("%s  %s: %s (v1 entry moved to mcp.servers)" % ("would migrate" if dry else "migrated",
                                                             where, name))
        del legacy[name]
        return True
    return False


def mcp_json(harness, want, dry):
    """claude (via its CLI), cursor, omp, opencode: create or update manifest names."""
    path, doc, legacy, servers = load_servers(harness)
    changed = False
    for name in sorted(want):
        changed = drop_legacy(legacy, name, dry, harness) or changed
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
        static, env = [], []
        for k, v in sorted((e.get("headers") or {}).items()):
            kind, var = codex_env(k, v) or (None, None)
            if kind == "bearer":
                lines.append("bearer_token_env_var = %s" % json.dumps(var))
            elif kind == "env":
                env.append((k, var))
            else:
                static.append((k, v))
        for key, pairs in (("http_headers", static), ("env_http_headers", env)):
            if pairs:
                lines.append("%s = { %s }" % (key, ", ".join(
                    "%s = %s" % (json.dumps(k), json.dumps(v)) for k, v in pairs)))
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


def mcp_codex(want, dry, path=None, where="codex", prune=False):
    """Regenerate the managed block. Names in it that are not in `want` are kept, or with
    `prune` (a project file, whose block holds only that project's list) removed."""
    path = path or os.path.join(home(), ".codex", "config.toml")
    lines, start, end, chunks, outside = codex_read(path)
    final = {} if prune else dict((n, c) for n, c in chunks.items() if n not in outside)
    for name in sorted(set(chunks) - set(want) if prune else ()):
        say(dry, "remove", where, name)
    for name in sorted(want):
        if name in outside:
            print("WARN  %s: %s has a [mcp_servers.%s] table outside the managed "
                  "block, not managed" % (where, name, name))
            continue
        final[name] = codex_chunk(name, want[name])
        if chunks.get(name) != final[name]:
            say(dry, "update" if name in chunks else "add", where, name)
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


_OPENCODE_V1 = []


def opencode_v1():
    """True when the installed opencode is v1: the sync writes v2's mcp.servers layout, which v1
    cannot read. Unknown or missing counts as v2."""
    if not _OPENCODE_V1:
        exe = shutil.which("opencode") or os.path.join(home(), ".opencode", "bin", "opencode")
        try:
            out = subprocess.run([exe, "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 timeout=60).stdout.decode(errors="replace")
        except (OSError, subprocess.TimeoutExpired):
            out = ""
        m = re.search(r"(\d+)\.\d+", out)
        _OPENCODE_V1.append(bool(m) and int(m.group(1)) < 2)
    return _OPENCODE_V1[0]


def opencode_v1_skip(present):
    if present["opencode"] and opencode_v1():
        print("WARN  opencode: v1 installed; this sync writes the v2 layout, so opencode is skipped "
              "(upgrade: curl -fsSL https://opencode.ai/v2/install | bash)")
        present["opencode"] = False


def mcp(manifest, dry):
    entries, bad = mcp_entries(manifest)
    rc = 1 if bad else 0
    present = mcp_present()
    opencode_v1_skip(present)
    for harness in MCP_HARNESSES:
        if not present[harness]:
            if harness != "opencode" or not opencode_v1():  # v1 already has its WARN
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


# --- project MCPs ------------------------------------------------------------
# A repo opts in with .agents/project.json: {"mcp": ["aws", "eks"]}, naming manifest
# entries marked "project": true. Those entries are never installed globally; in an
# opted-in repo they are present exactly when listed (removed when dropped from the list).
PROJECT_FILE = os.path.join(".agents", "project.json")
PROJECTS_ROOT = "REPOS"  # opted-in repos are found one level below ~/REPOS
# (harnesses that read the file, file in the repo, servers key, renderer)
PROJECT_JSON = ((("claude", "omp"), ".mcp.json", "mcpServers", "claude"),
                (("cursor",), os.path.join(".cursor", "mcp.json"), "mcpServers", "cursor"),
                (("opencode",), "opencode.json", "mcp", "opencode"))
PROJECT_CODEX = os.path.join(".codex", "config.toml")


def project_dirs():
    root = os.path.join(home(), PROJECTS_ROOT)
    if not os.path.isdir(root):
        return []
    return sorted(d for d in (os.path.join(root, n) for n in os.listdir(root))
                  if os.path.isfile(os.path.join(d, PROJECT_FILE)))


def project_list(d, entries):
    """Names a repo's .agents/project.json enables; each must be a project entry."""
    path = os.path.join(d, PROJECT_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise RuntimeError("cannot parse %s: %s" % (path, e))
    names = doc.get("mcp", []) if isinstance(doc, dict) else None
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise RuntimeError("%s: 'mcp' must be a list of names" % path)
    bad = [n for n in names if not entries.get(n, {}).get("project")]
    if bad:
        raise RuntimeError("%s: not a \"project\": true manifest MCP: %s" % (path, ", ".join(bad)))
    return set(names)


def project_json(d, readers, rel, key, render_as, want, managed, dry):
    """Merge `want` into one JSON file of a repo; managed names not wanted are removed."""
    path = os.path.join(d, rel)
    where = os.path.join(os.path.basename(d), rel)
    doc, servers, legacy = read_servers(path, key, render_as == "opencode")
    changed = False
    for name in sorted(managed):
        changed = drop_legacy(legacy, name, dry, where) or changed
        e = want.get(name)
        if e is not None and mcp_targets(e) & set(readers):
            new = render_json(render_as, e)
            if servers.get(name) != new:
                say(dry, "update" if name in servers else "add", where, name)
                servers[name] = new
                changed = True
        elif name in servers:
            say(dry, "remove", where, name)
            del servers[name]
            changed = True
    if changed and not dry:
        atomic_write(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def project(d, entries, present, dry):
    listed = project_list(d, entries)
    managed = set(n for n, e in entries.items() if e.get("project"))
    want = dict((n, entries[n]) for n in listed)
    for readers, rel, key, render_as in PROJECT_JSON:
        if any(present[h] for h in readers):
            project_json(d, readers, rel, key, render_as, want, managed, dry)
    if present["codex"]:
        mcp_codex(dict((n, e) for n, e in want.items() if "codex" in mcp_targets(e)), dry,
                  path=os.path.join(d, PROJECT_CODEX),
                  where=os.path.join(os.path.basename(d), PROJECT_CODEX), prune=True)


def projects(manifest, dry, dirs=None):
    """Write each opted-in repo's project MCP files (Hermes has no project config)."""
    entries = mcp_entries(manifest, report=False)[0]  # the mcp step reports invalid entries
    rc = 0
    present = mcp_present()
    opencode_v1_skip(present)
    for d in dirs if dirs is not None else project_dirs():
        try:
            project(os.path.abspath(d), entries, present, dry)
        except (OSError, RuntimeError, ValueError) as e:
            print("ERROR  project %s: %s" % (d, e))
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
            want = {"repo": e.get("repo"), "path": entry_path(e, n), "ref": e.get("ref"),
                    "rewrite": e.get("rewrite")}
            if marker is None:
                out.append("skill %s has no %s marker" % (n, MARKER))
            for key in want if marker else ():
                if marker.get(key) != want[key]:
                    out.append("skill %s: marker %s %s differs from manifest %s"
                               % (n, key, marker.get(key), want[key]))
    stale = stale_skills(manifest, sdir)
    for n in stale:
        out.append("stale skill: %s (installed by the sync, no longer in the manifest)" % n)
    if stale:
        out.append("remove stale skills with: %s" % remove_command(sdir, stale))
    host = socket.gethostname()
    for e in manifest.get("skills", []):
        for n in [e["name"]] if "name" in e else e.get("only", []):
            if n not in on_disk and ("hosts" not in e or host in e["hosts"]):
                out.append("missing skill: %s (in manifest, not in %s)" % (n, sdir))


def drift_mcp(manifest, out):
    """Whatever `mcp` / `project --dry-run` would change is drift (they only read)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mcp(manifest, True)
        projects(manifest, True)
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


STEPS = [("fetch", fetch), ("link", link), ("mcp", mcp), ("project", projects),
         ("plugins", plugins)]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true",
                   help="print what would change, write nothing")
    p.add_argument("--manifest", default=MANIFEST, help=argparse.SUPPRESS)
    p.add_argument("--project", action="append", metavar="DIR",
                   help="with step project: sync only this repo (repeatable)")
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
            rc = (fn(manifest, args.dry_run, args.project) if name == "project"
                  else fn(manifest, args.dry_run)) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
