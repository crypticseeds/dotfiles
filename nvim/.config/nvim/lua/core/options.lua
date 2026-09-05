-- Only deviations from Neovim defaults (:h option-list)

vim.o.number = true
vim.o.relativenumber = true
vim.o.signcolumn = "yes"
vim.o.cursorline = true

-- Go's ftplugin switches to tabs
vim.o.tabstop = 4
vim.o.softtabstop = 4
vim.o.shiftwidth = 4
vim.o.expandtab = true
vim.o.breakindent = true
vim.o.wrap = false

vim.o.ignorecase = true
vim.o.smartcase = true
vim.o.inccommand = "split"

vim.o.splitright = true
vim.o.splitbelow = true
vim.o.winborder = "rounded"
vim.o.laststatus = 3 -- one statusline for all windows

vim.o.swapfile = false
vim.o.undofile = true

vim.o.scrolloff = 10
vim.o.updatetime = 250
vim.o.confirm = true
vim.o.title = true

-- Tabs left invisible on purpose (Go)
vim.o.list = true
vim.opt.listchars = { trail = "·", nbsp = "␣" }

vim.o.foldlevel = 99
vim.o.foldlevelstart = 99

-- Scheduled: querying the clipboard at startup is slow
vim.schedule(function()
	vim.o.clipboard = "unnamedplus"
end)
