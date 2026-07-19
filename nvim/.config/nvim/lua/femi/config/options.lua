-- vim.opt.guicursor = ""
-- vim.opt.guicursor = "n-v-c-sm-i-ci-ve-r-cr-o:hor10"

vim.opt.number = true
vim.opt.relativenumber = true

vim.opt.title = true
vim.opt.tabstop = 4
vim.opt.softtabstop = 4
vim.opt.shiftwidth = 4
vim.opt.expandtab = true
vim.opt.autoindent = true
vim.opt.breakindent = true
vim.opt.smartindent = true
vim.opt.wrap = false
vim.opt.incsearch = true
vim.opt.ignorecase = true
vim.opt.smartcase = true
vim.opt.inccommand = "split"
vim.opt.backup = false
vim.opt.scrolloff = 10
vim.opt.splitkeep = "cursor" -- Ensures the cursor stays at the same position on screen

-- Show Command
vim.opt.showcmd = true

-- backspace
vim.opt.backspace = { "start", "eol", "indent" }

-- clipboard
vim.opt.clipboard:append("unnamedplus") --use system clipboard as default
vim.opt.hlsearch = true

--split windows
vim.opt.splitright = true --split vertical window to the right
vim.opt.splitbelow = true --split horizontal window to the bottom

-- for easy mouse resizing, just incase
vim.opt.mouse = "a"

-- gets rid of line with white spaces
vim.g.editorconfig = true