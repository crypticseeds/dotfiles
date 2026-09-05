return {
	"MeanderingProgrammer/render-markdown.nvim",
	ft = "markdown",
	dependencies = { "nvim-treesitter/nvim-treesitter", "nvim-mini/mini.nvim" },
	keys = {
		{ "<leader>um", "<cmd>RenderMarkdown toggle<cr>", desc = "Toggle markdown rendering", ft = "markdown" },
	},
	---@module 'render-markdown'
	---@type render.md.UserConfig
	opts = {
		completions = { blink = { enabled = true } },
		heading = { sign = false },
		code = { sign = false, width = "block", right_pad = 1 },
	},
}
