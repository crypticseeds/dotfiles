-- main branch: the plugin only installs parsers; highlighting and folds are
-- native (vim.treesitter.start). Compiling parsers needs the tree-sitter CLI.
return {
	"nvim-treesitter/nvim-treesitter",
	branch = "main",
	lazy = false, -- main does not support lazy-loading
	build = ":TSUpdate",
	config = function()
		-- install() skips parsers that are already present
		local parsers = {
			"bash", "dockerfile", "go", "gomod", "gosum", "gowork", "json",
			"markdown", "markdown_inline", "python", "toml", "tsx", "typescript", "yaml",
		}
		if vim.fn.executable("tree-sitter") == 1 then
			require("nvim-treesitter").install(parsers)
		else
			vim.notify("tree-sitter CLI not found; parsers not installed. brew install tree-sitter-cli",
				vim.log.levels.WARN)
		end

		vim.api.nvim_create_autocmd("FileType", {
			group = vim.api.nvim_create_augroup("treesitter", {}),
			callback = function(ev)
				if pcall(vim.treesitter.start, ev.buf) then
					vim.wo[0][0].foldexpr = "v:lua.vim.treesitter.foldexpr()"
					vim.wo[0][0].foldmethod = "expr"
				end
			end,
		})
	end,
}
