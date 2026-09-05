-- gitsigns: change markers in the gutter, hunk navigation/staging, line blame.
-- lazygit: full git UI (commit, branch, rebase, push) in a float.
return {
	{
		"lewis6991/gitsigns.nvim",
		event = { "BufReadPre", "BufNewFile" },
		opts = {
			on_attach = function(bufnr)
				local gs = require("gitsigns")
				local function bmap(mode, lhs, rhs, desc)
					vim.keymap.set(mode, lhs, rhs, { buffer = bufnr, desc = "Git: " .. desc })
				end
				bmap("n", "]h", function() gs.nav_hunk("next") end, "Next hunk")
				bmap("n", "[h", function() gs.nav_hunk("prev") end, "Previous hunk")
				bmap("n", "<leader>hs", gs.stage_hunk, "Stage hunk (toggle)")
				bmap("n", "<leader>hr", gs.reset_hunk, "Reset hunk")
				bmap("n", "<leader>hp", gs.preview_hunk, "Preview hunk")
				bmap("n", "<leader>hb", function() gs.blame_line({ full = true }) end, "Blame line")
				bmap("n", "<leader>hd", gs.diffthis, "Diff file")
			end,
		},
	},
	{
		"kdheepak/lazygit.nvim",
		cmd = "LazyGit",
		dependencies = { "nvim-lua/plenary.nvim" },
		keys = { { "<leader>lg", "<cmd>LazyGit<cr>", desc = "Lazygit" } },
	},
}
