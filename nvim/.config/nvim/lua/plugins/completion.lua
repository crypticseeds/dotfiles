-- blink.cmp registers its LSP capabilities itself on nvim 0.11+.
-- <CR>/<Tab> accept, <C-n>/<C-p> or arrows move, <C-e> dismiss, <C-space> toggle docs.
return {
	"saghen/blink.cmp",
	event = { "InsertEnter", "CmdlineEnter" },
	version = "1.*", -- prebuilt fuzzy matcher
	dependencies = { "rafamadriz/friendly-snippets", "folke/lazydev.nvim" },
	opts = {
		keymap = {
			preset = "enter",
			["<Tab>"] = { "select_and_accept", "snippet_forward", "fallback" },
			["<S-Tab>"] = { "snippet_backward", "fallback" },
		},
		appearance = { nerd_font_variant = "mono" },
		completion = {
			menu = {
				draw = {
					treesitter = { "lsp" },
					columns = { { "kind_icon" }, { "label", "label_description", gap = 1 }, { "kind" } },
				},
			},
			documentation = { auto_show = true, auto_show_delay_ms = 200 },
		},
		cmdline = {
			enabled = true,
			keymap = { preset = "cmdline" },
			completion = { menu = { auto_show = true } },
		},
		signature = { enabled = true },
		sources = {
			default = { "lazydev", "lsp", "path", "snippets", "buffer" },
			providers = {
				lazydev = { module = "lazydev.integrations.blink", score_offset = 100 },
			},
		},
	},
}
