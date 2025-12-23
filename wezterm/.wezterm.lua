-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices.

-- For example, changing the initial geometry for new windows:
config.initial_cols = 100
config.initial_rows = 30

-- Appearance
config.font = wezterm.font 'MesloLGS Nerd Font Mono'
config.font_size = 16
config.color_scheme = 'Catppuccin Mocha'
config.window_decorations = 'RESIZE'
config.hide_tab_bar_if_only_one_tab = true
config.native_macos_fullscreen_mode = false
config.default_cursor_style = 'BlinkingUnderline'
config.window_close_confirmation = 'NeverPrompt'
-- config.font = wezterm.font_with_fallback({
--     'Hack Nerd Font Mono',
--     'HackNerdFontMono-Regular',
--   })

-- Finally, return the configuration to wezterm:
return config