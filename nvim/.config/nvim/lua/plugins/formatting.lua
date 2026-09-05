-- conform runs the real formatters (goimports, gofumpt, ruff, stylua, prettier)
-- on save, falling back to the LSP for filetypes without one.
return {
	{
		"stevearc/conform.nvim",
		event = "BufWritePre",
		cmd = "ConformInfo",
		keys = {
			{ "<leader>cf", function() require("conform").format({ async = true }) end,
				mode = { "n", "v" }, desc = "Format" },
			{ "<leader>uf", function()
				vim.g.autoformat = not vim.g.autoformat
				vim.notify("Format on save: " .. (vim.g.autoformat and "on" or "off"))
			end, desc = "Toggle format on save" },
		},
		init = function() vim.g.autoformat = true end,
		opts = {
			formatters_by_ft = {
				go = { "goimports", "gofumpt" },
				python = { "ruff_organize_imports", "ruff_format" },
				lua = { "stylua" },
				typescript = { "prettier" },
				typescriptreact = { "prettier" },
				javascript = { "prettier" },
				json = { "prettier" },
				yaml = { "prettier" },
				sh = { "shfmt" },
			},
			default_format_opts = { lsp_format = "fallback" },
			format_on_save = function()
				if vim.g.autoformat then
					return { timeout_ms = 1500 }
				end
			end,
		},
	},

	-- Installs the formatters above (Mason package names).
	-- Eager: it hooks VimEnter to start installing, so lazy-loading disables it.
	{
		"WhoIsSethDaniel/mason-tool-installer.nvim",
		lazy = false,
		dependencies = { "mason-org/mason.nvim" },
		opts = { ensure_installed = { "goimports", "gofumpt", "stylua", "prettier", "shfmt" } },
	},
}
