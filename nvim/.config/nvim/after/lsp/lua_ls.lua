---@type vim.lsp.Config
return {
	settings = {
		Lua = {
			completion = { callSnippet = "Replace" },
			workspace = { checkThirdParty = false },
		},
	},
}
