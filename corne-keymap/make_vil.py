#!/usr/bin/env python3
"""Build a loadable Vial .vil for this Corne from keymap-v2.json and factory.vil.

Usage:
    python3 make_vil.py                      # uses the defaults below
    python3 make_vil.py factory.vil keymap-v2.json corne-keymap-v2.vil

factory.vil is a "File -> Save current layout" from Vial with layer 0 still on the
factory QWERTY layout. It supplies the board id, matrix shape, macros, combos and
settings, which are copied through. The key layout and explicitly configured
macro and tap dance slots are replaced; other slots are preserved.

MATRIX below is this board's wiring (flat 4 rows x 12 columns), read from the
factory save and cross-checked against Vial's picture. The letters are verified
against the factory layer 0 before anything is written.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULTS = ("factory.vil", "keymap-v2.json", "corne-keymap-v2.vil")

# physical position -> (row, col)
MATRIX = {
    # left hand: rows read outer, pinky, ring, middle, index, inner
    "left":         [[(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
                     [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5)],
                     [(2, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5)]],
    "left_extra":   [(3, 0), (3, 1)],            # upper, lower
    "left_thumbs":  [(3, 3), (3, 4), (3, 5)],    # outer, middle, inner
    # right hand: rows read inner, index, middle, ring, pinky, outer
    # (the right outer column is wired into the thumb row: cols 9, 10, 11)
    "right":        [[(0, 7), (0, 8), (0, 9), (0, 10), (0, 11), (3, 9)],
                     [(1, 7), (1, 8), (1, 9), (1, 10), (1, 11), (3, 10)],
                     [(2, 7), (2, 8), (2, 9), (2, 10), (2, 11), (3, 11)]],
    "right_extra":  [(0, 6), (1, 6)],            # upper, lower
    "right_thumbs": [(3, 6), (3, 7), (3, 8)],    # inner, middle, outer
}

# what the factory layer 0 must contain at the letter positions
LETTERS = {
    "left":  [[None, "KC_Q", "KC_W", "KC_E", "KC_R", "KC_T"],
              [None, "KC_A", "KC_S", "KC_D", "KC_F", "KC_G"],
              [None, "KC_Z", "KC_X", "KC_C", "KC_V", "KC_B"]],
    "right": [["KC_Y", "KC_U", "KC_I", "KC_O", "KC_P", None],
              ["KC_H", "KC_J", "KC_K", "KC_L", "KC_SCOLON", None],
              ["KC_N", "KC_M", "KC_COMMA", "KC_DOT", "KC_SLASH", None]],
}

# short QMK names -> the ids Vial registers (it accepts these directly)
LONG = {
    "KC_ESC": "KC_ESCAPE", "KC_CAPS": "KC_CAPSLOCK", "KC_LSFT": "KC_LSHIFT", "KC_RSFT": "KC_RSHIFT",
    "KC_LCTL": "KC_LCTRL", "KC_RCTL": "KC_RCTRL", "KC_ENT": "KC_ENTER", "KC_SPC": "KC_SPACE",
    "KC_BSPC": "KC_BSPACE", "KC_QUOT": "KC_QUOTE", "KC_DEL": "KC_DELETE", "KC_SCLN": "KC_SCOLON",
    "KC_COMM": "KC_COMMA", "KC_SLSH": "KC_SLASH", "KC_RGHT": "KC_RIGHT", "KC_PGDN": "KC_PGDOWN",
    "KC_LBRC": "KC_LBRACKET", "KC_RBRC": "KC_RBRACKET", "KC_GRV": "KC_GRAVE", "KC_BSLS": "KC_BSLASH",
    "KC_MINS": "KC_MINUS", "KC_EQL": "KC_EQUAL", "CW_TOGG": "QK_CAPS_WORD_TOGGLE", "CG_TOGG": "MAGIC_TOGGLE_CTL_GUI",
}


def fail(msg):
    sys.exit("\nSTOP: " + msg + "\n")


def normalize(kc):
    """Rewrite short QMK names (also inside LSFT(...), LT1(...), LGUI_T(...)) to Vial's ids."""
    return re.sub(r"[A-Z_0-9]+", lambda m: LONG.get(m.group(0), m.group(0)), kc)


def check_shape(layer):
    ok = (len(layer.get("left", [])) == 3 and all(len(r) == 6 for r in layer["left"])
          and len(layer.get("right", [])) == 3 and all(len(r) == 6 for r in layer["right"])
          and len(layer.get("left_extra", [])) == 2 and len(layer.get("right_extra", [])) == 2
          and len(layer.get("left_thumbs", [])) == 3 and len(layer.get("right_thumbs", [])) == 3)
    if not ok:
        fail("Layer '%s' in the keymap JSON has the wrong shape: each hand needs 3 rows of 6, "
             "2 extras and 3 thumbs." % layer.get("name", "?"))


def verify_factory(layer0):
    bad = []
    for side in ("left", "right"):
        for ri in range(3):
            for ci in range(6):
                want = LETTERS[side][ri][ci]
                if want is None:
                    continue
                r, c = MATRIX[side][ri][ci]
                got = layer0[r][c]
                if got != want:
                    bad.append("%s row %d col %d: expected %s, found %s" % (side, ri, ci, want, got))
    if bad:
        fail("Layer 0 of the factory save does not match this board's known wiring:\n  "
             + "\n  ".join(bad) + "\nReset layer 0 to factory QWERTY in Vial, save again, and rerun.")


def positions(layer):
    """Yield (row, col, keycode) for one keymap layer."""
    for side in ("left", "right"):
        for ri in range(3):
            for ci in range(6):
                r, c = MATRIX[side][ri][ci]
                yield r, c, layer[side][ri][ci]
    for key in ("left_extra", "right_extra", "left_thumbs", "right_thumbs"):
        for (r, c), kc in zip(MATRIX[key], layer[key]):
            yield r, c, kc


def main():
    args = list(sys.argv[1:]) + list(DEFAULTS[len(sys.argv) - 1:])
    fac_path, map_path, out_path = [a if os.path.isabs(a) else os.path.join(HERE, a) for a in args[:3]]
    if not os.path.exists(fac_path):
        fail("No factory save at %s.\nIn Vial: File -> Save current layout, and save it there." % fac_path)
    with open(fac_path, encoding="utf-8") as f:
        factory = json.load(f)
    with open(map_path, encoding="utf-8") as f:
        keymap = json.load(f)
    layers = keymap["layers"]

    template = factory["layout"][0]
    if len(template) != 4 or any(len(r) != 12 for r in template):
        fail("Expected a 4x12 matrix in the factory save, found %dx%s. This script is specific to that wiring."
             % (len(template), [len(r) for r in template]))
    verify_factory(template)
    for layer in layers:
        check_shape(layer)
    if len(layers) > len(factory["layout"]):
        fail("The keymap defines %d layers but the board has %d." % (len(layers), len(factory["layout"])))

    out_layers = []
    for li in range(len(factory["layout"])):
        grid = [[(-1 if v == -1 else "KC_TRNS") for v in row] for row in template]
        if li < len(layers):
            for r, c, kc in positions(layers[li]):
                if template[r][c] == -1:
                    fail("Layer '%s' places a key on an unwired position (%d,%d)." % (layers[li]["name"], r, c))
                grid[r][c] = normalize(kc)
        out_layers.append(grid)

    out = dict(factory)
    out["layout"] = out_layers
    out["macro"] = list(factory["macro"])
    for slot, actions in keymap.get("macros", {}).items():
        index = int(slot)
        if not 0 <= index < len(out["macro"]):
            fail("Macro slot %s is not available on this board." % slot)
        if out["macro"][index] and out["macro"][index] != actions:
            fail("Macro slot %s already contains a different factory macro." % slot)
        out["macro"][index] = actions
    out["tap_dance"] = list(factory["tap_dance"])
    for slot, td in keymap.get("tap_dances", {}).items():
        index = int(slot)
        if not 0 <= index < len(out["tap_dance"]):
            fail("Tap dance slot %s is not available on this board." % slot)
        keys = [normalize(td.get(k, "KC_NO")) for k in ("tap", "hold", "double_tap", "tap_hold")]
        out["tap_dance"][index] = keys + [td.get("term", 200)]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)

    used = sorted({kc for grid in out_layers for row in grid for kc in row if kc not in (-1, "KC_TRNS")})
    print("Keycodes written (an unknown spelling would load as an empty key):\n  " + " ".join(used))
    for li, layer in enumerate(layers):
        print("\nlayer %d  %s" % (li, layer["name"]))
        for row in out_layers[li]:
            print("  " + " ".join("%14s" % ("." if v == -1 else v.replace("KC_TRNS", "-")) for v in row))
    print("\nWrote %s: %d layers, %d defined, the rest transparent." % (out_path, len(out_layers), len(layers)))
    print("Next: Vial -> File -> Load saved layout -> pick that file. It writes to the board at once.")


if __name__ == "__main__":
    main()
