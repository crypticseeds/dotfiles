#!/usr/bin/env bash
# Run this inside the Linux (Fedora) VM before relying on the Claude sandbox and the
# permission files. It only reads state and prints; it changes nothing.
#   bash linux-preflight.sh
set -u
fails=0
ok()   { printf '  ok    %s\n' "$1"; }
bad()  { printf '  FIX   %s\n' "$1"; fails=$((fails + 1)); }
note() { printf '  note  %s\n' "$1"; }

echo "Sandbox prerequisites (without these Claude's sandbox cannot start)"
command -v bwrap >/dev/null && ok "bubblewrap installed" || bad "sudo dnf install bubblewrap"
command -v socat >/dev/null && ok "socat installed" || bad "sudo dnf install socat"
n=$(sysctl -n user.max_user_namespaces 2>/dev/null || echo 0)
[ "${n:-0}" -gt 0 ] 2>/dev/null && ok "user namespaces enabled ($n)" || bad "user namespaces disabled: sysctl user.max_user_namespaces"
if command -v bwrap >/dev/null; then
  bwrap --ro-bind / / --dev /dev true 2>/dev/null \
    && ok "bwrap can create a sandbox" \
    || bad "bwrap cannot create a sandbox (user namespaces, SELinux or container limits)"
fi

command -v python3 >/dev/null && ok "python3 present (the SSO login hook needs it)" || bad "sudo dnf install python3"

echo "Isolation from the Mac host"
if [ -n "${SSH_AUTH_SOCK:-}" ]; then
  bad "SSH_AUTH_SOCK is set: if you ssh in with agent forwarding, an agent here can sign with your Mac's keys. Use 'ssh -a' / ForwardAgent no"
else
  ok "no SSH agent forwarded"
fi
if [ -d /mnt/hgfs ] && [ -n "$(ls -A /mnt/hgfs 2>/dev/null)" ]; then
  bad "VMware shared folders are mounted at /mnt/hgfs: turn off Shared Folders in Fusion (VM Settings > Sharing)"
else
  ok "no VMware shared folders mounted"
fi
pgrep -x vmtoolsd >/dev/null && note "VMware Tools running: in Fusion turn off copy/paste and drag-and-drop (VM Settings > Isolation) so a clipboard read cannot see the Mac's clipboard"

echo "Host hardening"
[ "$(getenforce 2>/dev/null)" = "Enforcing" ] && ok "SELinux enforcing" || bad "SELinux is not enforcing"
[ "$(id -u)" -ne 0 ] && ok "not running as root" || bad "running as root: use a normal user for agents"
if sudo -n true 2>/dev/null; then
  bad "passwordless sudo works for this user: the user agents run as should not have it"
else
  ok "no passwordless sudo"
fi
command -v podman >/dev/null && ok "podman present (rules cover it; it runs outside the sandbox)"

echo
if [ "$fails" -eq 0 ]; then echo "All checks passed."; else echo "$fails item(s) to fix."; fi
exit "$fails"
