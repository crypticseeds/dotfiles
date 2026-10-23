# Corne keymap (Vial)

The layout for my Corne split keyboard (3x6 + 3 thumbs per side, plus two extra
keys per half), set up with [Vial](https://get.vial.today/). There is no custom
firmware: the keyboard runs its stock Vial firmware, and everything here is a layout
file that Vial writes to the board.

This folder is not a stow package. Nothing in it is linked into `$HOME`.

## Files

| File | What it is |
|---|---|
| `corne-keymap-v2.vil` | The layout to load into Vial. Generated, do not hand-edit. |
| `corne-cheatsheet-v2.html` | Printable cheat sheet of every layer. Open it in a browser. |
| `keymap-v2.json` | Source of the layout: every layer, the macro and the tap dance. Edit this. |
| `make_vil.py` | Builds `corne-keymap-v2.vil` from `keymap-v2.json` and `factory.vil`. |
| `factory.vil` | The board's factory layout as saved by Vial. Supplies the board id, matrix shape and settings, and is the undo button. |

## Load it onto the keyboard

1. Install Vial: `brew install --cask vial` (it is in `packages/Brewfile`).
2. Plug the keyboard in by USB (left half) and open Vial.
3. `File -> Load saved layout` and pick `corne-keymap-v2.vil`. Vial writes it to
   the board at once; no flashing, no reset.
4. Open `corne-cheatsheet-v2.html` to see what is where.

Loading the file also writes the QMK settings stored in it (copied from
`factory.vil`), such as the tapping term (200 ms). If you changed any of them
by hand in `QMK Settings`, check them again after loading.

To go back to factory: load `factory.vil` the same way.

## Change the layout

1. Edit `keymap-v2.json`. Keycodes use Vial spellings (`KC_A`, `LSFT(KC_1)`,
   `MO(1)`, `TG(4)`, `TD(0)`, ...). The `_notes` block at the top of the file
   explains the row and thumb order.
2. Rebuild: `python3 make_vil.py` (Python 3, no packages needed). It checks
   `factory.vil` against the board's known wiring before writing, and prints
   every layer so you can eyeball the result.
3. Load `corne-keymap-v2.vil` in Vial as above.
4. Update `corne-cheatsheet-v2.html` by hand if a key you care about moved.
   Its diagrams are the arrays near the bottom of the file.

## The layout in short

| Layer | How to reach it | What is on it |
|---|---|---|
| 0 Base | - | QWERTY. Left thumbs Cmd, Alt, Enter. Right thumbs Space, Backspace (hold for NumSym), Ctrl. |
| 1 Nav | Hold the left upper extra key | Arrows on H J K L, word jumps on Y O, Home/PgDn/PgUp/End, screenshots on W E R. |
| 2 NumSym | Hold the Backspace thumb | Numpad on the left hand, symbols on the right. `!=` macro on the Fn key, `£` on the Nav key, `$` on Tab. |
| 2 with Alt | Hold the right lower extra key | The same layer with Alt held, for AeroSpace workspaces (Alt+digit). |
| 3 Fn | Hold the right upper extra key | F1-F12, media keys, Ctrl/Cmd swap for Linux on the Esc key. |
| 4 Mouse | Toggle | Pointer on H J K L, wheel below, the three right thumbs are the buttons. |

Toggles and special keys:

- **Number lock:** hold Nav, tap the Backspace thumb. NumSym stays on with
  nothing held (handy for one-time codes). Tap the Backspace thumb to unlock.
  While locked, the Nav key types `£`, so unlock before you need arrows.
- **Mouse:** Nav + Space turns it on; Esc or a tap of Nav turns it off.
- **Ctrl thumb:** tap or hold is Ctrl, double tap sends Ctrl+Space (tap dance
  slot 0). A lone tap waits 200 ms for a possible second tap; chords like
  Ctrl+C are not delayed.

## Needed on the Mac side

- **Input source:** ABC (or U.S.). `£` is sent as Right Option+3, which those
  layouts turn into `£`. On the British layout Option+3 is `#`.
- **Ghostty:** `ghostty-mac/.config/ghostty/config` must have
  `macos-option-as-alt = left`. With `true`, Ghostty treats both Option keys as
  Alt and `£` never gets typed in the terminal. Left Option stays Alt for the
  shell and AeroSpace.
- **AeroSpace:** `alt-3` is left unbound in `aerospace/` so it does not
  capture Option+3. Any new character typed with Option should be sent as
  `RALT(...)` on the keyboard, not `LALT(...)`.
- **Ctrl+Space:** macOS uses it to switch input source when that shortcut is
  enabled (System Settings -> Keyboard -> Keyboard Shortcuts -> Input Sources).
  Keep it off if the double tap Ctrl is meant for something else.
