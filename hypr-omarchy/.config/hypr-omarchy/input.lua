-- Keyboard: US layout, as in the regular setup. Omarchy's default kb_options
-- ("omarchy:shift_caps_compose") needs XKB files only an Omarchy install has, so clear it.
-- Omarchy's repeat rate (40/s after 250 ms), numlock and touchpad defaults stay.
hl.config({
  input = {
    kb_layout = "us",
    kb_variant = "",
    kb_options = "",
  },
})

-- WezTerm: smoother touchpad scrolling, like Omarchy sets for its terminals.
o.window("org\\.wezfurlong\\.wezterm", { scroll_touchpad = 1.5 })
