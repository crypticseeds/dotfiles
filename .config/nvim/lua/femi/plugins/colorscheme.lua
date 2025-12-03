return {
  -- THEME NAME: catppuccin
  {
    "catppuccin/nvim",
    name = "catppuccin",
    priority = 1000,
    config = function()
      local mocha = require("catppuccin.palettes").get_palette("mocha")
      require("catppuccin").setup({
        flavour = "mocha",
        integrations = {
            -- Add integrations here
            cmp = true,
            gitsigns = true,
            nvimtree = true,
            treesitter = true,
        },
      })
    end,
  },

  -- THEME NAME: solarized-osaka
  {
    "craftzdog/solarized-osaka.nvim",
    lazy = false,
    config = function()
      require("solarized-osaka").setup({
        transparent = false,
        terminal_colors = true,
        styles = {
          comments = { italic = true },
          keywords = { italic = false },
          functions = {},
          variables = {},
          sidebars = "dark",
          floats = "dark",
        },
        sidebars = { "qf", "help" },
        day_brightness = 0.3,
        hide_inactive_statusline = false,
        dim_inactive = false,
        lualine_bold = false,
        on_highlights = function(hl, c)
          local prompt = "#2d3149"
          hl.TelescopeNormal        = { bg = c.bg_dark, fg = c.fg_dark }
          hl.TelescopeBorder        = { bg = c.bg_dark, fg = c.bg_dark }
          hl.TelescopePromptNormal  = { bg = c.bg_dark }
          hl.TelescopePromptBorder  = { bg = c.bg_dark, fg = c.bg_dark }
          hl.TelescopePromptTitle   = { bg = prompt, fg = "#2C94DD" }
          hl.TelescopePreviewTitle  = { bg = c.bg_dark, fg = c.bg_dark }
          hl.TelescopeResultsTitle  = { bg = c.bg_dark, fg = c.bg_dark }
        end,
      })
    end,
  },

  -- THEME NAME: tokyonight
  {
    "folke/tokyonight.nvim",
    name = "folkeTokyonight",
    config = function()
      local transparent = false
      local bg = "#011628"
      local bg_dark = "#011423"
      local bg_highlight = "#143652"
      local bg_search = "#0A64AC"
      local bg_visual = "#275378"
      local fg = "#CBE0F0"
      local fg_dark = "#B4D0E9"
      local fg_gutter = "#627E97"
      local border = "#547998"

      require("tokyonight").setup({
        style = "night",
        transparent = transparent,
        styles = {
          comments = { italic = false },
          keywords = { italic = false },
          sidebars = transparent and "transparent" or "dark",
          floats = transparent and "transparent" or "dark",
        },
        on_colors = function(colors)
          colors.bg             = transparent and colors.none or bg
          colors.bg_dark        = transparent and colors.none or bg_dark
          colors.bg_float       = transparent and colors.none or bg_dark
          colors.bg_highlight   = bg_highlight
          colors.bg_popup       = bg_dark
          colors.bg_search      = bg_search
          colors.bg_sidebar     = transparent and colors.none or bg_dark
          colors.bg_statusline  = transparent and colors.none or bg_dark
          colors.bg_visual      = bg_visual
          colors.border         = border
          colors.fg             = fg
          colors.fg_dark        = fg_dark
          colors.fg_float       = fg
          colors.fg_gutter      = fg_gutter
          colors.fg_sidebar     = fg_dark
        end,
      })
    end,
  },
}
