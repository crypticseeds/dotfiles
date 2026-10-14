-- Omarchy-style Hyprland session, kept beside the regular setup in ~/.config/hypr.
-- Start it with `hypr-omarchy` (sets OMARCHY_PATH, runs Hyprland under uwsm with this file).
--
-- It loads Omarchy's Hyprland defaults from a pinned checkout ($OMARCHY_PATH,
-- installed by `make hypr-omarchy`) and runs the Omarchy shell (bar, notifications,
-- launcher, OSD, dock). Left out, because they assume an Omarchy/Arch install:
-- first-run provisioning, post-boot hooks, dictation, the agent console and the
-- preinstalled app/webapp bindings. The overrides in this directory load after the
-- defaults, so Omarchy updates can't rewrite them.

local home = os.getenv("HOME")
local omarchy_path = os.getenv("OMARCHY_PATH")
if not omarchy_path then
  error("OMARCHY_PATH is not set: start this session with `hypr-omarchy`")
end

-- Re-run our own modules on `hyprctl reload` (bootstrap.lua only clears Omarchy's).
for module in pairs(package.loaded) do
  if module:sub(1, 13) == "hypr-omarchy." then
    package.loaded[module] = nil
  end
end
dofile(omarchy_path .. "/default/hypr/bootstrap.lua")

-- Only the essential app bindings (terminal, browser, file manager, editor).
omarchy_preinstalled_bindings = false

require("default.hypr.helpers")
local require_optional = require("default.hypr.require_optional")

require("default.hypr.bindings.media")
require("default.hypr.bindings.clipboard")
require("default.hypr.bindings.input-method")
require("default.hypr.bindings.jis")
require("default.hypr.bindings.tiling")
require("default.hypr.bindings.utilities")
require_optional.module("default.hypr.bindings.applications")
require("default.hypr.envs")
require("default.hypr.looknfeel")
require("default.hypr.input")
require("default.hypr.windows")
require_optional.module("omarchy.current.theme.hyprland")

-- Our replacements for Omarchy-only commands (lock, screenshot) win over $OMARCHY_PATH/bin.
local our_bin = home .. "/.config/hypr-omarchy/bin"
local path = {}
for entry in (os.getenv("PATH") or "/usr/local/bin:/usr/bin"):gmatch("[^:]+") do
  if entry ~= our_bin and entry ~= omarchy_path .. "/bin" then
    table.insert(path, entry)
  end
end
table.insert(path, 1, omarchy_path .. "/bin")
table.insert(path, 1, our_bin)
hl.env("PATH", table.concat(path, ":"))

require("hypr-omarchy.autostart")
require("hypr-omarchy.monitors")
require("hypr-omarchy.input")
require("hypr-omarchy.bindings")
require("hypr-omarchy.looknfeel")

-- Must stay last: toggles load the saved per-workspace layouts (tiling/scrolling/floating).
require("default.hypr.toggles")
