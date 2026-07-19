return {
	"neovim/nvim-lspconfig",
	event = { "BufReadPre", "BufNewFile" },
	dependencies = { "saghen/blink.cmp" },
	config = function()
		-- Diagnostics UI
		vim.diagnostic.config({
			virtual_text = true,
			severity_sort = true,
			float = { border = "rounded", source = true },
			signs = {
				text = {
					[vim.diagnostic.severity.ERROR] = " ",
					[vim.diagnostic.severity.WARN] = " ",
					[vim.diagnostic.severity.HINT] = "󰠠 ",
					[vim.diagnostic.severity.INFO] = " ",
				},
			},
		})

		-- Advertise blink.cmp completion capabilities to every server
		vim.lsp.config("*", {
			capabilities = require("blink.cmp").get_lsp_capabilities(),
		})

		-- Server-specific tweaks
		vim.lsp.config("lua_ls", {
			settings = {
				Lua = {
					diagnostics = { globals = { "vim" } },
					completion = { callSnippet = "Replace" },
				},
			},
		})

		-- Buffer-local keymaps, only when an LSP attaches
		vim.api.nvim_create_autocmd("LspAttach", {
			group = vim.api.nvim_create_augroup("femi-lsp-attach", { clear = true }),
			callback = function(event)
				local map = function(keys, fn, desc, mode)
					vim.keymap.set(mode or "n", keys, fn, { buffer = event.buf, desc = "LSP: " .. desc })
				end
				local picker = require("snacks").picker

				map("gd", picker.lsp_definitions, "Goto Definition")
				map("gD", vim.lsp.buf.declaration, "Goto Declaration")
				map("gr", picker.lsp_references, "References")
				map("gi", picker.lsp_implementations, "Goto Implementation")
				map("gy", picker.lsp_type_definitions, "Type Definition")
				map("K", vim.lsp.buf.hover, "Hover Docs")
				map("<leader>ca", vim.lsp.buf.code_action, "Code Action", { "n", "v" })
				map("<leader>rn", vim.lsp.buf.rename, "Rename Symbol")
				map("<leader>ss", picker.lsp_symbols, "Document Symbols")
				map("<leader>D", picker.diagnostics_buffer, "Buffer Diagnostics")
			end,
		})
	end,
}
