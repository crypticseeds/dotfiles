-- Editing helpers, all treesitter-based.
return {
	-- <Tab> jumps out of the closing quote/bracket; <S-Tab> jumps back in.
	-- blink owns <Tab> while its menu or a snippet is active and falls back
	-- here otherwise, so this must be loaded (not lazy) for the fallback to exist.
	{
		"abecodes/tabout.nvim",
		lazy = false,
		opts = {
			completion = false, -- blink does not use the native popup menu
			act_as_tab = true, -- nothing to tab out of: behave like a normal <Tab>
		},
	},

	-- Split one-line blocks (args, struct literals, lists) into lines and back
	{
		"Wansmer/treesj",
		keys = {
			{ "<leader>m", function() require("treesj").toggle() end, desc = "Split/join block" },
			{ "<leader>M", function() require("treesj").toggle({ split = { recursive = true } }) end, desc = "Split/join block (recursive)" },
		},
		opts = { use_default_keymaps = false },
	},

	-- Search counts next to matches: [3/12]
	{
		"kevinhwang91/nvim-hlslens",
		keys = {
			{ "n", [[<Cmd>execute('normal! ' . v:count1 . 'n')<CR><Cmd>lua require('hlslens').start()<CR>]], desc = "Next match" },
			{ "N", [[<Cmd>execute('normal! ' . v:count1 . 'N')<CR><Cmd>lua require('hlslens').start()<CR>]], desc = "Previous match" },
			{ "*", [[*<Cmd>lua require('hlslens').start()<CR>]], desc = "Search word forward" },
			{ "#", [[#<Cmd>lua require('hlslens').start()<CR>]], desc = "Search word backward" },
			{ "g*", [[g*<Cmd>lua require('hlslens').start()<CR>]], desc = "Search partial word forward" },
			{ "g#", [[g#<Cmd>lua require('hlslens').start()<CR>]], desc = "Search partial word backward" },
		},
		opts = {},
	},
}
