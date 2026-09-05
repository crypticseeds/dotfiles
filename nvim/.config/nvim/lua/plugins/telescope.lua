-- Fuzzy finder. A picker opens in insert mode: just type to filter, <C-n>/<C-p>
-- or arrows to move, <CR> opens, <Esc> closes. <C-x> split, <C-v> vsplit, <C-t> tab.
-- master is the maintained branch; the README's 0.1.x is frozen and breaks
-- with nvim-treesitter main.
return {
	"nvim-telescope/telescope.nvim",
	branch = "master",
	cmd = "Telescope",
	dependencies = {
		"nvim-lua/plenary.nvim",
		{
			"nvim-telescope/telescope-fzf-native.nvim",
			build = "make",
			cond = function() return vim.fn.executable("make") == 1 end,
		},
	},
	keys = {
		{ "<leader>ff", "<cmd>Telescope find_files<cr>", desc = "Files" },
		{ "<leader>fg", "<cmd>Telescope live_grep<cr>", desc = "Grep" },
		{ "<leader>fw", "<cmd>Telescope grep_string<cr>", desc = "Grep word under cursor", mode = { "n", "x" } },
		{ "<leader>fb", "<cmd>Telescope buffers<cr>", desc = "Buffers" },
		{ "<leader>fr", "<cmd>Telescope oldfiles<cr>", desc = "Recent files" },
		{ "<leader>fd", "<cmd>Telescope diagnostics<cr>", desc = "Diagnostics" },
		{ "<leader>fh", "<cmd>Telescope help_tags<cr>", desc = "Help" },
		{ "<leader>fk", "<cmd>Telescope keymaps<cr>", desc = "Keymaps" },
		{ "<leader>fn", function()
			require("telescope.builtin").find_files({ cwd = vim.fn.stdpath("config") })
		end, desc = "Config files" },
	},
	opts = {
		defaults = {
			path_display = { "filename_first" },
			file_ignore_patterns = { "^.git/", "node_modules/", "%.venv/" },
			mappings = { i = { ["<Esc>"] = "close" } }, -- <C-n>/<C-p> or arrows to move
		},
		pickers = {
			find_files = { hidden = true },
			buffers = { sort_mru = true, ignore_current_buffer = true },
		},
	},
	config = function(_, opts)
		require("telescope").setup(opts)
		pcall(require("telescope").load_extension, "fzf")
	end,
}
