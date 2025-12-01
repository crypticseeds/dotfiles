#!/bin/bash

# ===== START: ERROR HANDLING IMPROVEMENTS =====
# Added CONFIG_DIR fallback and error suppression for robustness
# TO REVERT: Change CONFIG_DIR line back to: CONFIG_DIR="$HOME/.config/sketchybar"
#            And remove all "2>/dev/null" redirects
CONFIG_DIR="${CONFIG_DIR:-$HOME/.config/sketchybar}"
# ===== END: ERROR HANDLING IMPROVEMENTS =====

update_space_icons() {
    local sid=$1
    # ===== START: ERROR HANDLING =====
    # Added error suppression (2>/dev/null) to prevent script failures
    # TO REVERT: Remove "2>/dev/null" from the aerospace command below
    local apps=$(aerospace list-windows --workspace "$sid" 2>/dev/null | awk -F'|' '{gsub(/^ *| *$/, "", $2); print $2}')
    # ===== END: ERROR HANDLING =====

    # ===== START: ERROR HANDLING =====
    # Added error suppression to prevent sketchybar errors from breaking the script
    # TO REVERT: Remove "2>/dev/null" from sketchybar commands below
    sketchybar --set space.$sid drawing=on 2>/dev/null
    # ===== END: ERROR HANDLING =====

    if [ "${apps}" != "" ]; then
        icon_strip=" "
        while read -r app; do
            # ===== START: ERROR HANDLING =====
            # Added check to skip empty app names and suppress errors
            # TO REVERT: Change back to: icon_strip+=" $($CONFIG_DIR/plugins/icon_map_fn.sh "$app")"
            if [ -n "$app" ]; then
                icon_strip+=" $($CONFIG_DIR/plugins/icon_map_fn.sh "$app" 2>/dev/null)"
            fi
            # ===== END: ERROR HANDLING =====
        done <<<"${apps}"
    else
        icon_strip=""
    fi
    # ===== START: ERROR HANDLING =====
    # Added error suppression
    # TO REVERT: Remove "2>/dev/null"
    sketchybar --set space.$sid label="$icon_strip" 2>/dev/null
    # ===== END: ERROR HANDLING =====
}

# Update all workspaces to ensure clean state
# ===== START: ERROR HANDLING =====
# Added error suppression to prevent failures if aerospace commands fail
# TO REVERT: Remove "2>/dev/null" from aerospace commands below
for monitor in $(aerospace list-monitors --format "%{monitor-appkit-nsscreen-screens-id}" 2>/dev/null); do
    for sid in $(aerospace list-workspaces --monitor "$monitor" 2>/dev/null); do
        update_space_icons "$sid"
    done
done
# ===== END: ERROR HANDLING =====
