local wifi = SBAR.add("item", "wifi", {
	position = "right",
	update_freq = 120,
	icon = {
		string = "",
		font = { family = "JetBrainsMono Nerd Font", size = 15.0 },
		color = 0xff39FF14, -- Neon Green as seen in wifi.sh
		padding_left = 4,
		padding_right = 4,
	},
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 14.0 },
		color = COLORS.white,
		drawing = false,
		padding_right = 4,
	},
	background = { drawing = false },
	padding_left = 2,
	padding_right = 2,
})

local ip_address = ""

local function wifi_update()
	SBAR.exec([[networksetup -getairportpower en0; echo "---"; ipconfig getifaddr en0; echo "---"; ipconfig getsummary en0 | awk -F': ' '/ SSID : / {print $2}']], function(result)
		local power = result:match("Wi%-Fi Power %(en0%): (%a+)")
		local ip = result:match("%-%-%-\n([%d%.]+)\n%-%-%-")

		-- SSID extraction: get everything after the second --- separator
		local ssid = ""
		local parts = {}
		for part in result:gmatch("([^\n]*)\n?") do
			table.insert(parts, part)
		end

		-- Very crude but effective way to find SSID after the last ---
		local found_sep = 0
		for _, v in ipairs(parts) do
			if v == "---" then
				found_sep = found_sep + 1
			elseif found_sep == 2 then
				ssid = v
				break
			end
		end

		ip_address = ip or ""
		ssid = (ssid or ""):gsub("^%s*", ""):gsub("%s*$", "")

		local color = COLORS.white
		local icon = ""
		local label = ""

		if power == "Off" then
			color = COLORS.red
			icon = "󰖪"
			label = "Off"
		elseif ssid ~= "" then
			color = 0xff39FF14 -- Neon Green
			icon = ""
			label = ssid
		else
			color = COLORS.white
			icon = ""
			label = "Not Connected"
		end

		wifi:set({
			icon = { string = icon, color = color },
			label = { string = label },
		})
	end)
end

wifi:subscribe("mouse.entered", function()
	wifi:set({ label = { string = ip_address, drawing = true } })
end)

wifi:subscribe("mouse.exited", function()
	wifi_update()
	wifi:set({ label = { drawing = false } })
end)

wifi:subscribe({ "routine", "system_woke", "wifi_change", "network_change" }, wifi_update)

wifi_update()
