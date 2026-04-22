-- Clock item based on clock.sh style
local clock = SBAR.add("item", "clock", {
	position = "right",
	update_freq = 10,
	icon = {
		string = "",
		font = { family = "JetBrainsMono Nerd Font", size = 15.0 },
		color = COLORS.white,
		padding_left = 10,
		padding_right = 4,
	},
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 14.0 },
		color = COLORS.white,
		padding_left = 4,
		padding_right = 10,
	},
	background = {
		color = COLORS.black,
		corner_radius = 5,
		drawing = true,
	},
	padding_left = 5,
	padding_right = 5,
})

local function update_clock()
	clock:set({ label = { string = os.date("%d/%m %H:%M") } })
end

clock:subscribe({ "routine", "system_woke" }, update_clock)

clock:subscribe("mouse.clicked", function()
	SBAR.exec("open -a Calendar")
end)

update_clock()
