-- Types, hover, go-to. Lint/format/imports belong to ruff.
---@type vim.lsp.Config
return {
	settings = {
		pyright = { disableOrganizeImports = true },
		python = {
			analysis = {
				autoSearchPaths = true,
				useLibraryCodeForTypes = true,
				diagnosticMode = "openFilesOnly",
			},
		},
	},
}
