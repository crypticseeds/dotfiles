return {
	"saghen/blink.cmp",
	event = "InsertEnter",
	version = "1.*", -- use prebuilt fuzzy-matcher binaries from releases
	dependencies = { "rafamadriz/friendly-snippets" },
	opts = {
		keymap = {
			-- <CR> accepts, <C-e> cancels, <Tab>/<S-Tab> snippet jumps
			preset = "enter",
			["<C-j>"] = { "select_next", "fallback" },
			["<C-k>"] = { "select_prev", "fallback" },
		},
		appearance = {
			nerd_font_variant = "mono",
		},
		completion = {
			documentation = { auto_show = true, auto_show_delay_ms = 200 },
			menu = { border = "rounded" },
		},
		sources = {
			default = { "lsp", "path", "snippets", "buffer" },
		},
		signature = { enabled = true },
	},
}
