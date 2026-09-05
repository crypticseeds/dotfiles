-- Gruvbox Material hard: same palette as the Zed "Gruvbox Dark Hard Seeds" theme
return {
	"sainnhe/gruvbox-material",
	lazy = false,
	priority = 1000,
	config = function()
		vim.o.background = "dark"
		vim.g.gruvbox_material_background = "hard"
		vim.g.gruvbox_material_better_performance = 1
		-- pure black background like the Zed variant:
		-- vim.g.gruvbox_material_colors_override = { bg0 = { "#000000", "0" } }
		vim.cmd.colorscheme("gruvbox-material")
	end,
}
