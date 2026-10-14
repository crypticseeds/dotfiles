-- Session start: Omarchy's autostart minus first-run provisioning, power-profile
-- setup and post-boot hooks (those assume an Omarchy/Arch install).
hl.on("hyprland.start", function()
  -- Apps launched through uwsm/systemd need the session environment.
  hl.exec_cmd("systemctl --user import-environment $(env | cut -d'=' -f 1)")
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")

  -- Bar, notifications, launcher/menus, OSD, clipboard, polkit agent, idle, dock.
  hl.exec_cmd("omarchy-launch-shell")
  hl.exec_cmd(o.launch("omarchy-hyprland-monitor-watch"))
  hl.exec_cmd("command -v udiskie >/dev/null && " .. o.launch("udiskie --automount --no-notify --no-tray"))
end)
