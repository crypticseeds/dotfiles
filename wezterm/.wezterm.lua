-- Pull in the wezterm API
local wezterm = require 'wezterm'

-- This will hold the configuration.
local config = wezterm.config_builder()

-- This is where you actually apply your config choices.

-- For example, changing the initial geometry for new windows:
config.initial_cols = 100
config.initial_rows = 30

-- Set Defualt Working Directory
config.default_cwd = wezterm.home_dir .. '/MEGA'

-- Appearance
config.font = wezterm.font 'JetBrainsMono Nerd Font'
config.font_size = 16
config.color_scheme = 'Catppuccin Mocha'
-- config.color_scheme = 'Gruvbox dark, hard (base16)'
config.window_decorations = 'RESIZE'
config.hide_tab_bar_if_only_one_tab = true
config.native_macos_fullscreen_mode = false
config.default_cursor_style = 'BlinkingUnderline'
config.window_close_confirmation = 'NeverPrompt'
-- config.font = wezterm.font_with_fallback({
--     'Hack Nerd Font Mono',
--     'HackNerdFontMono-Regular',
--   })

-- Key bindings
-- Make Alt/Option+Arrow move by word, matching Terminal.app/iTerm/Zed behavior.
-- Sends ESC-b / ESC-f, which zsh (emacs mode) binds to backward-word / forward-word.
config.keys = {
  { key = 'LeftArrow', mods = 'OPT', action = wezterm.action.SendString '\x1bb' },
  { key = 'RightArrow', mods = 'OPT', action = wezterm.action.SendString '\x1bf' },
  -- Uncomment to make Alt/Option+Up/Down act as plain Up/Down (history navigation)
  -- instead of printing stray A/B characters:
  -- { key = 'UpArrow', mods = 'OPT', action = wezterm.action.SendString '\x1b[A' },
  -- { key = 'DownArrow', mods = 'OPT', action = wezterm.action.SendString '\x1b[B' },
}

-- Finally, return the configuration to wezterm:
return config
