-- Merged over nvim-lspconfig defaults. Formatting is done by conform.
---@type vim.lsp.Config
return {
	settings = {
		gopls = {
			gofumpt = true,
			staticcheck = true,
			completeUnimported = true,
			usePlaceholders = true,
			analyses = { unusedparams = true, unusedwrite = true },
			hints = { -- off until <leader>uh
				parameterNames = true,
				assignVariableTypes = true,
				compositeLiteralFields = true,
			},
		},
	},
}
