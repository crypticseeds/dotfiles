return {
	"mason-org/mason-lspconfig.nvim",
	event = { "BufReadPre", "BufNewFile" },
	cmd = { "Mason", "MasonInstall", "MasonUpdate" },
	dependencies = {
		{ "mason-org/mason.nvim", opts = {} },
		"neovim/nvim-lspconfig",
	},
	opts = {
		-- Language servers to auto-install and enable (uses lspconfig names)
		ensure_installed = {
			"lua_ls",
			"gopls",
			"ts_ls",
			"pyright",
			"bashls",
			"html",
			"cssls",
			"jsonls",
			"yamlls",
		},
		-- v2 default: automatically runs vim.lsp.enable() for installed servers
		automatic_enable = true,
	},
}
