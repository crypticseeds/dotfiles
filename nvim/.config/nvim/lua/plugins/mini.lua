-- mini.icons     icon provider (also serves plugins that expect nvim-web-devicons)
-- mini.pairs     auto-close ( [ { " ' ` while typing
-- mini.ai        text objects: cia (argument), daf (function call), vif, plus n/l for next/last
-- mini.bufremove close a buffer without closing its window
return {
	"nvim-mini/mini.nvim",
	lazy = false,
	priority = 1000, -- icons must be ready before plugins that draw them
	config = function()
		require("mini.icons").setup()
		MiniIcons.mock_nvim_web_devicons()
		require("mini.pairs").setup()
		require("mini.ai").setup({ n_lines = 300 })
		require("mini.bufremove").setup()
		vim.keymap.set("n", "<leader>bd", function() MiniBufremove.delete() end, { desc = "Close buffer" })
	end,
}
