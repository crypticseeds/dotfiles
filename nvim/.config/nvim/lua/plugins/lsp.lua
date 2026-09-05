-- Mason installs servers, nvim-lspconfig provides their defaults,
-- mason-lspconfig runs vim.lsp.enable() for installed ones.
-- Per-server settings: after/lsp/<server>.lua. Add a server: one line below.
return {
	{
		"mason-org/mason-lspconfig.nvim",
		event = "VeryLazy", -- not BufRead: installs even when nvim opens without a file
		cmd = { "Mason", "LspInstall" },
		dependencies = {
			-- eager: registers :Mason* commands and puts mason/bin on PATH at startup
			{ "mason-org/mason.nvim", lazy = false, opts = {} },
			"neovim/nvim-lspconfig",
		},
		opts = {
			ensure_installed = { "gopls", "pyright", "ruff", "lua_ls", "ts_ls" },
		},
		config = function(_, opts)
			require("mason-lspconfig").setup(opts)

			vim.diagnostic.config({
				severity_sort = true,
				virtual_text = { source = "if_many" },
				float = { source = "if_many" },
				signs = {
					text = {
						[vim.diagnostic.severity.ERROR] = " ",
						[vim.diagnostic.severity.WARN] = " ",
						[vim.diagnostic.severity.INFO] = " ",
						[vim.diagnostic.severity.HINT] = "󰠠 ",
					},
				},
			})

			-- Built-in: K hover, grn rename, gra code action, <C-s> signature, [d ]d.
			-- List-style built-ins are replaced with telescope pickers.
			vim.api.nvim_create_autocmd("LspAttach", {
				group = vim.api.nvim_create_augroup("lsp-attach", {}),
				callback = function(ev)
					local client = assert(vim.lsp.get_client_by_id(ev.data.client_id))
					local function bmap(lhs, rhs, desc)
						vim.keymap.set("n", lhs, rhs, { buffer = ev.buf, desc = "LSP: " .. desc })
					end
					local function tb(picker)
						return function() require("telescope.builtin")[picker]() end
					end

					bmap("gd", tb("lsp_definitions"), "Definition")
					bmap("gD", vim.lsp.buf.declaration, "Declaration")
					bmap("grr", tb("lsp_references"), "References")
					bmap("gri", tb("lsp_implementations"), "Implementations")
					bmap("grt", tb("lsp_type_definitions"), "Type definition")
					bmap("gO", tb("lsp_document_symbols"), "Document symbols")
					bmap("<leader>fs", tb("lsp_dynamic_workspace_symbols"), "Workspace symbols")
					bmap("<leader>cd", vim.diagnostic.open_float, "Line diagnostics")

					-- ruff and pyright both attach to Python; pyright owns hover
					if client.name == "ruff" then
						client.server_capabilities.hoverProvider = false
					end

					if client:supports_method("textDocument/inlayHint") then
						bmap("<leader>uh", function()
							local on = vim.lsp.inlay_hint.is_enabled({ bufnr = ev.buf })
							vim.lsp.inlay_hint.enable(not on, { bufnr = ev.buf })
						end, "Toggle inlay hints")
					end
				end,
			})
		end,
	},

	-- Neovim API types for lua_ls when editing this config
	{
		"folke/lazydev.nvim",
		ft = "lua",
		opts = {
			library = { { path = "${3rd}/luv/library", words = { "vim%.uv" } } },
		},
	},
}
