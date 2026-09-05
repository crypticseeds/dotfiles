local aug = vim.api.nvim_create_augroup("autocmds", {})

vim.api.nvim_create_autocmd("TextYankPost", {
	group = aug,
	desc = "Highlight yanked text",
	callback = function() vim.hl.on_yank() end,
})

vim.api.nvim_create_autocmd("BufReadPost", {
	group = aug,
	desc = "Restore cursor position",
	callback = function(ev)
		local mark = vim.api.nvim_buf_get_mark(ev.buf, '"')
		if mark[1] > 0 and mark[1] <= vim.api.nvim_buf_line_count(ev.buf) then
			pcall(vim.api.nvim_win_set_cursor, 0, mark)
		end
	end,
})

-- Cursorline only in the active window
vim.api.nvim_create_autocmd({ "WinEnter", "BufEnter" }, {
	group = aug,
	callback = function() vim.wo.cursorline = true end,
})
vim.api.nvim_create_autocmd("WinLeave", {
	group = aug,
	callback = function() vim.wo.cursorline = false end,
})
