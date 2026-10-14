-- Keybinding overrides on top of Omarchy's defaults. See every binding with SUPER + K.
-- Omarchy's scheme is kept as-is: SUPER + RETURN terminal, SUPER + W / Q close,
-- SUPER + C / V copy and paste, SUPER + T float, SUPER + M minimize to the dock,
-- SUPER + L cycle the workspace layout, SUPER + SPACE menu, SUPER + ALT + SPACE apps,
-- SUPER + ESCAPE lock/suspend/logout/shutdown.
-- Add with o.bind, replace with o.rebind (same arguments), remove with hl.unbind.

-- Omarchy-only apps and features this setup doesn't install.
hl.unbind("SUPER + CTRL + Q")         -- calculator (omacalc)
hl.unbind("XF86Calculator")           -- calculator (omacalc)
hl.unbind("SUPER + SHIFT + CTRL + A") -- agent picker (omarchy-agent)
hl.unbind("SUPER + CTRL + R")         -- reminders (plugin disabled in shell.json)
hl.unbind("SUPER + CTRL + ALT + R")
hl.unbind("SUPER + SHIFT + CTRL + R")
hl.unbind("SUPER + CTRL + ALT + W")   -- weather notification
hl.unbind("SUPER + CTRL + ALT + E")   -- world clock panel

-- File manager: Strata (installed by `make hypr-omarchy`); Nautilus if it isn't there.
local strata = os.getenv("HOME") .. "/.local/bin/strata"
local strata_file = io.open(strata, "r")
if strata_file then
  strata_file:close()
  o.rebind("SUPER + SHIFT + F", "File manager", { launch = strata })
  o.rebind("SUPER + ALT + SHIFT + F", "File manager (cwd)",
    "uwsm-app -- " .. strata .. " \"$(omarchy-cmd-terminal-cwd)\"")
end

-- Examples:
-- o.bind("SUPER + SHIFT + R", "SSH", "wezterm ssh your-server")
-- o.rebind("SUPER + SHIFT + N", "Editor", { launch = "zed" })
