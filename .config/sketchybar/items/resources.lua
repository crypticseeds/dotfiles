-- ==========================================================
-- CPU INDICATOR
-- ==========================================================

local core_count = 1 -- default fallback
local handle = io.popen("sysctl -n machdep.cpu.thread_count")
if handle then
	local result = handle:read("*a")
	core_count = tonumber(result) or 1
	handle:close()
end

local cpu = SBAR.add("item", "cpu", {
	position = "left",
	update_freq = 2,
	icon = {
		string = "", -- Nerd Font CPU icon
		font = { family = "JetBrainsMono Nerd Font", size = 15.0 },
		padding_right = DEFAULT_ITEM.icon.padding_right * 0.5,
		color = COLORS.white,
	},
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 14.0 },
		padding_right = 0,
		color = COLORS.white,
	},
})

local function cpu_update()
	SBAR.exec("ps -A -o %cpu | awk '{s+=$1} END {print s}'", function(total_load)
		local load = tonumber(total_load) or 0
		local used = math.floor(load / core_count)
		-- Adaptive colors from Catppuccin theme
		local color = (used > 80 and COLORS.red) or (used > 60 and COLORS.orange) or COLORS.white
		cpu:set({
			icon = { color = color },
			label = { string = math.floor(used) .. "%", color = color },
		})
	end)
end

cpu:subscribe("routine", cpu_update)

-- ==========================================================
-- RAM / MEMORY INDICATOR
-- ==========================================================

local memory = SBAR.add("item", "memory", {
	position = "left",
	update_freq = 5,
	icon = {
		string = "", -- Nerd Font Memory/Chip icon
		font = { family = "JetBrainsMono Nerd Font", size = 15.0 },
		padding_right = DEFAULT_ITEM.icon.padding_right * 0.5,
		color = COLORS.white,
	},
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 14.0 },
		padding_right = 0,
		color = COLORS.white,
	},
})

local function memory_update()
	SBAR.exec("memory_pressure | grep 'System-wide memory free percentage:' | awk '{print 100-$5}'", function(result)
		local used = tonumber(result) or 0
		local color = (used > 80 and COLORS.red) or (used > 60 and COLORS.orange) or COLORS.white
		memory:set({
			icon = { color = color },
			label = { string = math.floor(used) .. "%", color = color },
		})
	end)
end

memory:subscribe("routine", memory_update)

-- ==========================================================
-- NETWORK INDICATOR (Stacked Up/Down)
-- ==========================================================

local interface = "en0"
local popup_width = 60
local position = "left"

local function format_speed(speed_val)
	local speed = tonumber(speed_val) or 0
	if speed > 999 then
		return string.format("%4.0f Mbps", speed / 1000)
	else
		return string.format("%4.0f kbps", speed)
	end
end

local pad_r = -4

-- Top Layer: Upload Speed
local network_up = SBAR.add("item", "network_up", {
	position = position,
	width = 0,
	update_freq = 2,
	y_offset = 4,
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 9.0 },
		string = "0 kbps",
		width = popup_width,
		color = COLORS.white,
	},
	icon = {
		font = { family = "JetBrainsMono Nerd Font", size = 9.0 },
		string = "",
		color = COLORS.white,
		padding_right = pad_r,
	},
})

-- Bottom Layer: Download Speed
local network_down = SBAR.add("item", "network_down", {
	position = position,
	y_offset = -4,
	label = {
		font = { family = "JetBrainsMono Nerd Font", size = 9.0 },
		string = "0 kbps",
		width = popup_width,
		color = COLORS.white,
	},
	icon = {
		font = { family = "JetBrainsMono Nerd Font", size = 9.0 },
		string = "",
		color = COLORS.white,
		padding_right = pad_r,
	},
})

local last_ibytes = 0
local last_obytes = 0
local last_time = os.time()

local function network_update()
	SBAR.exec("netstat -I " .. interface .. " -b -n | tail -n 1 | awk '{print $7, $10}'", function(result)
		local ibytes, obytes = result:match("(%d+)%s+(%d+)")
		ibytes = tonumber(ibytes) or 0
		obytes = tonumber(obytes) or 0

		local current_time = os.time()
		local delta_t = os.difftime(current_time, last_time)
		if delta_t <= 0 then delta_t = 1 end

		local down = (ibytes - last_ibytes) / delta_t / 1024 * 8
		local up = (obytes - last_obytes) / delta_t / 1024 * 8

		if last_ibytes == 0 then down, up = 0, 0 end

		last_ibytes, last_obytes, last_time = ibytes, obytes, current_time

		network_down:set({
			label = { string = format_speed(down) },
		})
		network_up:set({
			label = { string = format_speed(up) },
		})
	end)
end

network_up:subscribe("routine", network_update)

-- Force initial updates
cpu_update()
memory_update()
network_update()
