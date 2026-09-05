-- Sidebar file tree (left), files open on the right, tree follows the current file.
-- In the tree: Enter open, a add, r rename, d delete, m move, h/l collapse/expand,
-- H dotfiles, I gitignored, q close, ? help. Type to filter.
return {
	"folke/snacks.nvim",
	lazy = false, -- replaces netrw for `nvim <dir>`
	priority = 900,
	opts = {
		explorer = { enabled = true },
		picker = { sources = { explorer = { hidden = true } } },
	},
	keys = {
		{ "<leader>e", function() Snacks.explorer.reveal():focus() end, desc = "File tree" },
		{ "<leader>E", function() Snacks.explorer() end, desc = "Toggle file tree" },
	},
}
