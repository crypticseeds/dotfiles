return {
	-- Statusline: mode | branch, diff, diagnostics | file ... encoding, OS, filetype | % | line:col
	{
		"nvim-lualine/lualine.nvim",
		event = "VeryLazy",
		opts = function()
			local theme = require("lualine.themes.gruvbox-material")
			theme.visual.a, theme.command.a = theme.command.a, theme.visual.a -- blue visual, red command

			-- OS logo from mini.icons: macos, or the distro ID from /etc/os-release
			-- (ubuntu, fedora, ...); unknown names fall back to the linux tux.
			local os_name = "linux"
			if vim.uv.os_uname().sysname == "Darwin" then
				os_name = "macos"
			else
				local f = io.open("/etc/os-release")
				if f then
					local content = f:read("*a")
					f:close()
					os_name = content:match('^ID="?([%w%-]+)') or content:match('\nID="?([%w%-]+)') or "linux"
				end
			end
			local os_icon, os_hl, is_default = MiniIcons.get("os", os_name)
			if is_default then
				os_icon, os_hl = MiniIcons.get("os", "linux")
			end
			-- fg only, as a table: a highlight-group string makes lualine drop the separators
			local os_fg = vim.api.nvim_get_hl(0, { name = os_hl, link = false }).fg

			return {
				options = {
					theme = theme,
					component_separators = { left = "", right = "|" },
				},
				sections = {
					lualine_x = {
						"encoding",
						{ function() return os_icon end, color = { fg = os_fg and ("#%06x"):format(os_fg) } },
						{ "filetype", fmt = function(ft) return ft:sub(1, 1):upper() .. ft:sub(2) end },
					},
				},
			}
		end,
	},

	-- Press <leader> and pause: shows what can follow. Only on <leader>, so it
	-- never pops up mid-edit after d / c / g / z.
	{
		"folke/which-key.nvim",
		event = "VeryLazy",
		opts = {
			delay = 300,
			triggers = { { "<leader>", mode = { "n", "v" } } },
			spec = {
				{ "<leader>b", group = "buffer" },
				{ "<leader>c", group = "code" },
				{ "<leader>f", group = "find" },
				{ "<leader>h", group = "git hunk" },
				{ "<leader>r", group = "replace" },
				{ "<leader>s", group = "split" },
				{ "<leader>t", group = "tab" },
				{ "<leader>u", group = "toggle" },
			},
		},
	},

	-- Highlights TODO / FIXME / NOTE / HACK in comments
	{
		"folke/todo-comments.nvim",
		event = { "BufReadPost", "BufNewFile" },
		dependencies = { "nvim-lua/plenary.nvim" },
		opts = { signs = false },
		keys = {
			{ "]t", function() require("todo-comments").jump_next() end, desc = "Next todo" },
			{ "[t", function() require("todo-comments").jump_prev() end, desc = "Previous todo" },
			{ "<leader>ft", "<cmd>TodoTelescope<cr>", desc = "Todos" },
		},
	},
}
