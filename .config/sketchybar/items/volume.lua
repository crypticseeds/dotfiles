local icons = {
	_100 = "",
	_66 = "",
	_33 = "",
	_10 = "",
	_0 = "",
}

local volume_slider = SBAR.add("slider", 100, {
	position = "right",
	updates = true,
	label = { drawing = false },
	icon = { drawing = false },
	slider = {
		highlight_color = COLORS.blue,
		width = 0,
		background = {
			height = 6,
			corner_radius = 3,
			color = COLORS.grey,
		},
		knob = {
			string = "⬤",
			drawing = true,
		},
	},
	background = {
		drawing = false,
	},
	padding_left = 2,
	padding_right = 2,
})

local volume_icon = SBAR.add("item", "volume_icon", {
	position = "right",
	icon = {
		string = icons._100,
		font = { family = "JetBrainsMono Nerd Font", size = 15.0 },
		color = COLORS.white,
		padding_left = 2,
		padding_right = 2,
	},
	label = { drawing = false },
	background = {
		drawing = false,
	},
	padding_left = 2,
	padding_right = 2,
})

volume_slider:subscribe("mouse.clicked", function(env)
	SBAR.exec("osascript -e 'set volume output volume " .. env["PERCENTAGE"] .. "'")
end)

volume_slider:subscribe("volume_change", function(env)
	local volume = tonumber(env.INFO)
	local icon = icons._0
	if volume > 60 then
		icon = icons._100
	elseif volume > 30 then
		icon = icons._66
	elseif volume > 10 then
		icon = icons._33
	elseif volume > 0 then
		icon = icons._10
	end

	volume_icon:set({ icon = { string = icon } })
	volume_slider:set({ slider = { percentage = volume } })
end)

local function animate_slider_width(width)
	SBAR.animate("tanh", 30.0, function()
		volume_slider:set({
			slider = { width = width },
		})
	end)
end

volume_slider:subscribe("mouse.exited", function()
	SBAR.delay(0.1, function()
		animate_slider_width(0)
	end)
end)

volume_icon:subscribe("mouse.clicked", function(env)
	if env.BUTTON == "right" then
		SBAR.exec("open /System/Library/PreferencePanes/Sound.prefPane")
	else
		animate_slider_width(100)
	end
end)
