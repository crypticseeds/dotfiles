-- Global keymaps. Plugin keymaps live in their plugin spec; LSP keymaps in
-- plugins/lsp.lua. <leader>fk searches all of them.

local map = vim.keymap.set

map("n", "<Esc>", "<cmd>nohlsearch<CR>", { desc = "Clear search highlight" })
map("i", "<C-c>", "<Esc>")
map("n", "Q", "<nop>")

map("n", "<C-d>", "<C-d>zz", { desc = "Half page down" })
map("n", "<C-u>", "<C-u>zz", { desc = "Half page up" })

-- Windows. Ctrl-j/k are herdr workspace keys; use Ctrl-w j/k there.
map("n", "<C-h>", "<C-w>h", { desc = "Focus left window" })
map("n", "<C-l>", "<C-w>l", { desc = "Focus right window" })
map("n", "<leader>sv", "<C-w>v", { desc = "Split vertically" })
map("n", "<leader>sh", "<C-w>s", { desc = "Split horizontally" })
map("n", "<leader>se", "<C-w>=", { desc = "Equalize splits" })
map("n", "<leader>sx", "<cmd>close<CR>", { desc = "Close split" })

-- Tabs
map("n", "<leader>to", "<cmd>tabnew<CR>", { desc = "New tab" })
map("n", "<leader>tx", "<cmd>tabclose<CR>", { desc = "Close tab" })
map("n", "<leader>tn", "<cmd>tabnext<CR>", { desc = "Next tab" })
map("n", "<leader>tp", "<cmd>tabprevious<CR>", { desc = "Previous tab" })
map("n", "<leader>tf", "<cmd>tabnew %<CR>", { desc = "Open buffer in new tab" })

-- Visual editing
map("v", "J", ":m '>+1<CR>gv=gv", { desc = "Move selection down" })
map("v", "K", ":m '<-2<CR>gv=gv", { desc = "Move selection up" })
map("v", "<", "<gv", { desc = "Dedent" })
map("v", ">", ">gv", { desc = "Indent" })

-- Entering insert mode on a blank line indents it first
for _, key in ipairs({ "i", "a", "A", "I" }) do
	map("n", key, function()
		return vim.fn.getline("."):match("^%s*$") and [["_cc]] or key
	end, { expr = true })
end

-- Registers: small deletes don't clobber the last yank
map("x", "<leader>p", [["_dP]], { desc = "Paste over selection, keep yank" })
map({ "n", "v" }, "<leader>d", [["_d]], { desc = "Delete without yanking" })
map("n", "x", [["_x]])

map("n", "<leader>rw", [[:%s/\<<C-r><C-w>\>/<C-r><C-w>/gI<Left><Left><Left>]],
	{ desc = "Replace word under cursor" })

map("n", "<leader>fp", function()
	local path = vim.fn.expand("%:~")
	vim.fn.setreg("+", path)
	vim.notify("Copied " .. path)
end, { desc = "Copy file path" })
map("n", "<leader>x", "<cmd>!chmod +x %<CR>", { silent = true, desc = "chmod +x" })

-- Built-in undo tree (nvim 0.12)
vim.cmd.packadd("nvim.undotree")
map("n", "<leader>u", function() require("undotree").open() end, { desc = "Undo tree" })
