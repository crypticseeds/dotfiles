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
		string = "􀧓",
		padding_right = DEFAULT_ITEM.icon.padding_right * 0.5,
	},
	label = { padding_right = 0 },
})

local function cpu_update()
	SBAR.exec("ps -A -o %cpu | awk '{s+=$1} END {print s}'", function(total_load)
		local load = tonumber(total_load) or 0
		local used = math.floor(load / core_count)
		local color = (used > 80 and 0xffff4444) or (used > 60 and 0xffffa500) or nil
		cpu:set({
			icon = { color = color or DEFAULT_ITEM.icon.color },
			label = { string = math.floor(used) .. "%", color = color or DEFAULT_ITEM.label.color },
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
		string = "􀫦",
		padding_right = DEFAULT_ITEM.icon.padding_right * 0.5,
	},
	label = { padding_right = 0 },
})

local function memory_update()
	SBAR.exec("memory_pressure | grep 'System-wide memory free percentage:' | awk '{print 100-$5}'", function(result)
		local used = tonumber(result) or 0
		local color = (used > 80 and 0xffff4444) or (used > 60 and 0xffffa500) or nil
		memory:set({
			icon = { color = color or DEFAULT_ITEM.icon.color },
			label = { string = math.floor(used) .. "%", color = color or DEFAULT_ITEM.label.color },
		})
	end)
end

memory:subscribe("routine", memory_update)

-- ==========================================================
-- NETWORK INDICATOR (Stacked Up/Down)
-- ==========================================================

-- 1. Configuration
local interface = "en0" -- WiFi usually en0, Ethernet might be en1
local popup_width = 50 -- Fixed width to prevent jitter when numbers change
local position = "left"

-- 2. Helper: Format speed (kbps vs Mbps)
local function format_speed(speed_val)
	local speed = tonumber(speed_val) or 0
	if speed > 999 then
		return string.format("%4.0f Mbps", speed / 1000)
	else
		return string.format("%4.0f kbps", speed)
	end
end

-- 3. Create Network Items
local pad_r = 4
local arrow_shift = pad_r * 0.75
-- Top Layer: Upload Speed
local network_up = SBAR.add("item", "network_up", {
	position = position,
	width = 0, -- Width 0 allows it to overlap with the item below it
	update_freq = 2,
	y_offset = 5, -- Shift Up
	label = {
		font = { size = DEFAULT_ITEM.label.font.size * 0.75 },
		string = "0 kbps",
		width = popup_width,
	},
	icon = {
		font = { size = DEFAULT_ITEM.icon.font.size * 0.75 },
		string = "",
		color = COLORS.disabled_color,
		highlight_color = COLORS.accent_color,
		padding_right = pad_r,
	},
})

-- Bottom Layer: Download Speed
local network_down = SBAR.add("item", "network_down", {
	position = position,
	y_offset = -5, -- Shift Down
	label = {
		font = { size = DEFAULT_ITEM.label.font.size * 0.75 },
		string = "   0 kbps",
		width = popup_width,
	},
	icon = {
		font = { size = DEFAULT_ITEM.icon.font.size * 0.75 },
		string = "",
		color = COLORS.disabled_color,
		highlight_color = COLORS.accent_color,
		padding_left = DEFAULT_ITEM.icon.padding_left + arrow_shift,
		padding_right = pad_r - arrow_shift,
	},
})

-- 4. Update Logic
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
		if delta_t <= 0 then
			delta_t = 1
		end

		local down = (ibytes - last_ibytes) / delta_t / 1024 * 8 -- kbps
		local up = (obytes - last_obytes) / delta_t / 1024 * 8 -- kbps

		if last_ibytes == 0 then
			down, up = 0, 0
		end

		last_ibytes = ibytes
		last_obytes = obytes
		last_time = current_time

		-- Update Down (Bottom)
		network_down:set({
			label = { string = format_speed(down) },
			icon = { highlight = (down > 0) }, -- Highlight icon if active
		})

		-- Update Up (Top)
		network_up:set({
			label = { string = format_speed(up) },
			icon = { highlight = (up > 0) }, -- Highlight icon if active
		})
	end)
end

network_up:subscribe("routine", network_update)

-- ==========================================================
-- FINAL BRACKET (Unified Background)
-- ==========================================================

-- Wrap CPU, RAM, and Network into one single bracket
SBAR.add("bracket", "resources.bracket", {
	"cpu",
	"memory",
	"network_up", -- Top part of stack
	"network_down", -- Bottom part of stack (defines the width)
}, {
	background = { drawing = true },
})

-- ==========================================================
-- FORCE INITIAL UPDATES
-- ==========================================================
-- Call these immediately so we don't wait 2-5s for the first numbers
cpu_update()
memory_update()
network_update()
