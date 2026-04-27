local battery = SBAR.add("item", "battery", {
	position = "right",
	update_freq = 120,
	icon = {
		font = {
			family = "JetBrainsMono Nerd Font",
			size = 15.0,
		},
		color = COLORS.white,
		padding_left = 4,
		padding_right = 4,
	},
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 14.0 },
		color = COLORS.white,
		padding_left = 4,
		padding_right = 4,
		drawing = false,
	},
	background = {
		drawing = false,
	},
	padding_left = 2,
	padding_right = 2,
})

local function battery_update()
	SBAR.exec("pmset -g batt", function(batt_info)
		local found, _, charge = batt_info:find("(%d+)%%")

		if found then
			local charge_num = tonumber(charge)
			local is_charging = batt_info:find("AC Power")

			local color = COLORS.white
			local icon = ""

			if charge_num >= 80 then
				icon = ""
				color = COLORS.green
			elseif charge_num >= 70 then
				icon = ""
				color = COLORS.yellow
			elseif charge_num >= 40 then
				icon = ""
				color = COLORS.orange
			elseif charge_num >= 10 then
				icon = ""
				color = COLORS.red
			else
				icon = ""
				color = COLORS.red
			end

			if is_charging then
				icon = ""
				color = COLORS.yellow
			end

			-- Apply the updates
			battery:set({
				icon = {
					string = icon,
					color = color,
				},
				label = { string = charge .. "%", color = color },
			})
		end
	end)
end

-- Show percentage when hovering, hide when leaving
battery:subscribe("mouse.entered", function()
	battery:set({
		label = { drawing = true },
	})
end)

battery:subscribe("mouse.exited", function()
	battery_update()
	battery:set({
		label = { drawing = false },
	})
end)

battery:subscribe({ "routine", "power_source_change", "system_woke" }, battery_update)

battery_update()
