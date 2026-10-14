-- Same as the regular setup: every monitor at its preferred mode, auto scale.
-- List monitors and modes with: hyprctl monitors all
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

-- A specific monitor:
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })
