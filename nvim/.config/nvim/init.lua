-- Minimal Neovim config for Go / Python / TypeScript. Requires nvim 0.12+.
--
--   lua/core/        options, keymaps, autocmds
--   lua/plugins/     one file per concern (lazy.nvim specs)
--   after/lsp/       per-server settings, merged over nvim-lspconfig defaults
--   after/ftplugin/  per-filetype settings
--
-- LSP servers and formatters: Mason (:Mason). Parsers: :TSInstall (needs the
-- tree-sitter CLI). Health: :checkhealth. Terminal needs a Nerd Font.
-- macOS:  brew install neovim tree-sitter-cli ripgrep go node lazygit
-- Linux:  apt install neovim ripgrep golang nodejs npm; npm i -g tree-sitter-cli

vim.g.mapleader = " "
vim.g.maplocalleader = " "

require("core.options")
require("core.keymaps")
require("core.autocmds")

local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not vim.uv.fs_stat(lazypath) then
	vim.fn.system({
		"git", "clone", "--filter=blob:none",
		"https://github.com/folke/lazy.nvim.git", "--branch=stable", lazypath,
	})
end
vim.opt.rtp:prepend(lazypath)

require("lazy").setup({
	spec = { { import = "plugins" } },
	install = { colorscheme = { "gruvbox-material" } },
	checker = { enabled = false }, -- update with :Lazy update
	change_detection = { notify = false },
})
