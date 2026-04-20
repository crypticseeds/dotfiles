-- =============================================================================
-- Display Auto-Rotation Manager
-- Watches for display connection/disconnection events and applies rotation
-- based on which displays are connected:
--   - Only LG connected  → no rotation needed (default)
--   - Only HS connected  → no rotation needed (default)
--   - Both connected     → HS rotates to 90°, LG stays at 0°
-- =============================================================================

-- Full path to betterdisplaycli binary (avoids PATH issues in Hammerspoon)
local BD = "/usr/local/bin/betterdisplaycli"

-- BetterDisplay tagIDs - stable identifiers that persist across reboots
-- Find these in BetterDisplay UI or via: betterdisplaycli get --identifiers
local LG_TAG = 2
local HS_TAG = 3

-- -----------------------------------------------------------------------------
-- applyDisplayProfile()
-- Detects which displays are connected and applies the correct rotation.
-- Called automatically on display change events and once on Hammerspoon launch.
-- Can also be called manually from the Hammerspoon console for testing.
-- -----------------------------------------------------------------------------
function applyDisplayProfile()
    -- 2 second delay to allow displays to fully initialize before querying
    hs.timer.doAfter(2, function()

        -- Query connection status for each display
        local lgOutput = hs.execute(BD .. " get --tagID=" .. LG_TAG .. " --connected")
        local hsOutput = hs.execute(BD .. " get --tagID=" .. HS_TAG .. " --connected")

        -- betterdisplaycli returns "on" if connected, "off" if not
        local lgFound = lgOutput and lgOutput:match("on") ~= nil
        local hsFound = hsOutput and hsOutput:match("on") ~= nil

        if lgFound and hsFound then
            -- Both displays connected: rotate HS to 90°
            hs.execute(BD .. " set --tagID=" .. HS_TAG .. " --rotation=90")
        else
            -- Single display or neither: ensure HS is reset to 0°
            -- This handles the case where HS was previously rotated
            -- and LG is then disconnected
            hs.execute(BD .. " set --tagID=" .. HS_TAG .. " --rotation=0")
        end
    end)
end

-- -----------------------------------------------------------------------------
-- Display watcher
-- Fires applyDisplayProfile() on any display connection/disconnection event.
-- This is event driven, not polling - no performance impact when idle.
-- -----------------------------------------------------------------------------
local displayWatcher = hs.screen.watcher.new(applyDisplayProfile)
displayWatcher:start()

-- Apply profile on Hammerspoon launch in case displays are already connected
applyDisplayProfile()