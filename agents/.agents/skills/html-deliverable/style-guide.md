# DevOpsFoundry Style Guide

Companion to the versioned HTML style guide in `.design-previews/`
(`style-guide-v<N>.html`, highest N is current — currently **v13**).
This file always reflects the most recent locked state. The HTML is the
visual source of truth; when they disagree, the HTML wins.

## Status legend

- **LOCKED** — decided, do not revisit without explicit instruction
- **TESTING** — locked provisionally, being lived with
- **OPEN** — still being explored

## Decision register (v13)

Read this before changing anything. These were argued through several
rounds and reversed more than once; the current state is intentional.

| Decision | Locked as | Supersedes |
|---|---|---|
| Button system | **Square sweep only** — `.btn`, `.solid`, `.sm` | filled chrome variant |
| Button border | **1.5px** via `--btn-bw`, one weight for every button | — |
| Focus ring | **1px accent outline** | unspecified |
| Icon stroke | **1.75** — Lucide | 1.5 · 2 |
| Icon size | **20px standalone, 18px for controls inside a section rule** | flat 20px |
| Toggle position | **Always the final element on the right of any bar. Nothing after it** | — |
| Accent | Mode-aware — `#e07000` light / `#ff8100` dark | v4 single-accent |
| Section label | Ink brackets + accent bold word, 14px/700 | all-ink variant |
| Accent square | Right end of the section rule | "right side stays empty" |
| Primary button | Square-sweep fill, black text on hover | hard-shadow button |
| Mode toggle | Bare Lucide sun/moon — no background, no border | bordered text button |
| Table-grid highlight | **Dropped** — all cells equal weight | second-accent fill cell |
| Semantic colours | added / open / data / removed, both modes | — |
| Amber | In palette, parked, no assigned role | — |
| Body weight | 450 dark / 400 light, dimming kept | flat 400 |

**The accent is mode-aware on purpose.** A single value was tested in both
directions and rendered side by side: `#ff8100` everywhere is too weak on
cream (2.30:1), `#e07000` everywhere loses the fire in dark (6.12:1 vs
7.91:1). Do not "simplify" this back to one value — it is not an oversight.

## Colors

| Token | Light (cream) | Dark | Status |
|---|---|---|---|
| Background | `#faf5ec` | `#0a0a0a` | LOCKED |
| Surface | `#f4ecdf` | `#141414` | LOCKED |
| Ink (text) | `#000000` | `#eeeae4` | LOCKED |
| Ink-body (long-form) | `#1a1a1a` | `#cfc9c0` | LOCKED |
| Muted text | `#4d4947` | `#a8a29b` | LOCKED |
| Accent | `#e07000` | `#ff8100` | LOCKED — mode-aware |
| Accent pressed | `#c96400` | `#ee7800` | LOCKED |
| On-accent | `#000000` | `#000000` | LOCKED |
| Component border | `#202020` | `#4d4947` | LOCKED |
| Section rule | `#202020` | `#6b6560` | LOCKED |
| Hairline | `#00000022` | `#ffffff24` | LOCKED |

### Semantic set — LOCKED

| Role | Light | Dark | Use |
|---|---|---|---|
| added | `#007038` | `#00c26e` | success, diff `+`, uptime |
| open | `#00667a` | `#00abd6` | pending, in-progress |
| data | `#7340bf` | `#af85ff` | links, charts, info |
| removed | `#c2334a` | `#ff6b81` | error, diff `−`, failing |
| amber | `#7d6410` | `#e8b13b` | **PARKED — no assigned role** |

Rules:

- Dark `added` is the terminal green and doubles as the success colour.
- Every semantic colour sits in the same contrast band as the accent so
  nothing shouts louder than the brand. Verified pairwise: minimum
  separation ΔE2000 **30.7 dark**, **25.3 light** (ΔE < 25 = confusable).
- **Amber restriction:** in dark, amber is ΔE 18.6 from the accent — below
  the confusion threshold and untunable. Never use it as a small status
  marker next to an orange one. Large fills, chart series and highlights
  are fine. In light the separation is ΔE 31.0, so this applies to dark only.
- Semantic colours are used as **text and small markers**, not as fills. If
  one is ever used as a fill, text on it must be black in dark / cream in
  light — never white. White on dark `--data` is only 2.76:1.
- **No gradients, ever.** See `AGENTS.md`.

## Typography

- **Geist Mono**, Google Fonts, true variable axis `300–700` — LOCKED.
- **Body weight is mode-aware: 450 dark / 400 light** — LOCKED.
  Light-on-dark type optically erodes, so the same weight reads thinner in
  dark. Any value on the axis is available; you are not limited to 400/500.
- **`--ink-body` dimming is kept** — LOCKED. Added weight compensates
  rather than replaces it.

| Role | Spec |
|---|---|
| display | clamp(34–64px) / 700 / −0.03em |
| h2 | clamp(24–36px) / 700 / −0.02em |
| h3 | 20px / 700 |
| body-expanded | 18px / 1.56 / 450 dark · 400 light · max 62ch |
| label-01 | 14px / 700 / +0.5px / uppercase |
| eyebrow | 11–12px / 600 / +0.12em / uppercase |
| code-01 | 14px / 1.7 |

## Section device — LOCKED

Two levels on every section:

1. Bracket label — `[ WORD ]` with the **square brackets in `--ink`** and the
   **word in `--accent`, bold 700, 14px**, +0.5px tracking, uppercase.
2. Full-width 1px `--rule` beneath it, with the uppercase eyebrow descriptor
   at the **left** and the **8px accent square at the right**.

The square closes the line rather than leading it.

**Known cost, accepted:** `#e07000` on cream is **2.98:1**, below the 4.5:1
bar for normal text, and 14px does not qualify for the 3.0:1 large-text
exemption (that needs 18.66px bold). This is a deliberate brand decision. The
accent word is short, bold, uppercase and always paired with ink brackets and
a full-strength square. If a page needs the label to pass outright, raise it
to **19px bold** — do not change the colour.

## Buttons — LOCKED (v10)

**There is one button: the square sweep.** No filled, flat or non-sweeping
button exists anywhere in this system. Consistency is the point — a second
personality in the chrome is what makes an interface feel assembled rather
than designed.

| Variant | Use |
|---|---|
| `.btn` | Default. Outline, transparent ground, accent label |
| `.btn.solid` | Inverted. **One primary action per view** — use sparingly |
| `.btn.sm` | Chrome scale, for topbars and dense UI. Same sweep, same border |

- **1.5px** `--btn-bw` accent border, 0px radius, transparent ground
- Uppercase mono, 13px / 600 / +0.1em (`.sm` is 11px / 700)
- Hover: an accent **square** sweeps in from the bottom-right corner
- **Hover label is black, never white** — black on accent is 8.39:1, white
  is 2.50:1
- Honours `prefers-reduced-motion` by filling instantly instead of sweeping

**Known cost of 1.5px, accepted.** A border cannot occupy half a device
pixel. At **2x it renders as 3 device pixels** — the intended lighter weight.
At **1x it rounds down to 1px**, matching the structural border, so buttons
stop out-weighing panels and table grids. At 110%/125% zoom it can round
either way. If 1x traffic proves significant, revisit the weight then — but
not by reaching for another fraction: 1.25px and 1.75px never resolve cleanly
at any common ratio.

**Never hard-code the line-height.** It is
`calc(3em - (var(--btn-bw) * 2))`. Earlier revisions hard-coded
`calc(3em - 4px)`, which silently pushes the label off centre the moment the
border weight changes.

## Focus — LOCKED (v13)

```css
:focus-visible { outline:1px solid var(--accent); outline-offset:3px; }
```

- **1px accent.** Lighter than the 1.5px button border on purpose: the ring
  sits outside the element and only appears on keyboard focus, so it does not
  need to compete with the border.
- **Declare it once, globally.** A page that styles focus per component will
  eventually miss one, and the missed control falls through to the browser
  default blue — a colour in no palette. That has already happened once.
- Never `outline: none` without an equally visible replacement.

## Shape & structure

- Border radius: **strict 0px everywhere** — LOCKED. Only exception: the
  macOS traffic-light dots in the terminal component.
- Separation vs borders are separate concerns:
  - Section separation uses `--rule` — always clearly visible.
  - Component borders (terminal, table-grids, panels, footer) use `--border`.
  - Quiet hairlines stay on low-emphasis containers and list separators.
- Selection cue: 1px accent border marks the active item; any paired marker
  is a square `■`, never a round bullet — LOCKED.

## Components

- **Terminal typing** — LOCKED: macOS-style window (traffic lights,
  structural border, NO window shadow, mono 14/1.7) typing commands with a
  blinking **underline** cursor. Every line is a `$` prompt with an
  accent-coloured sigil. No diff `-`/`+` syntax. Pure JS/CSS; honours
  `prefers-reduced-motion`.
- **Table-grid cards** — collapsed shared 1px borders, **all cells equal
  weight**. The highlight cell was dropped; if one card must lead, use the
  accent selection border, not a coloured fill.
- **Numbered feature rows** — `■ 01` accent square + mono number + heading +
  muted body, hairline separators. Only for real sequences.
- **Site footer** — single quiet line: copyright left, bare Lucide 20/1.75
  social icons right (LinkedIn, GitHub, X, Medium), accent on hover.

## Icons

- **Lucide only**, `strokeWidth={1.75}` — LOCKED.
  **Size is `20px` standalone, `18px` for an interactive control embedded in a
  section rule** — LOCKED (v11). At 20px a control overpowers the 11px eyebrow
  it sits beside. The exception is scoped narrowly: controls in rules only,
  never standalone icons.
  Unlike the button border, an SVG stroke is antialiased rather than snapped
  to whole device pixels, so 1.75 renders as a genuine intermediate weight at
  every pixel ratio. No display-dependency caveat applies.
- Ink by default, accent when interactive or highlighted.
- Light/dark toggle: bare sun/moon icon, **no background, no border, no
  track**; hover turns it accent-coloured — LOCKED. A pill/switch style was
  explored and rejected: it needs rounded corners and would cost a second
  exception to the 0px radius rule.
- **Toggle position — LOCKED (v10):** the mode toggle is **always the final
  element on the right of any bar it appears in. Nothing comes after it.**
  Applies to the site header, style guide chrome and generated feedback
  pages alike. Any action that would otherwise sit at the far right (contact,
  copy, save, submit) goes immediately *before* the toggle, and that action
  is a `.btn.sm` — never a bespoke bar button.

## Header — LOCKED

Two-tier terminal header:

- Tier 1 (microbar): surface bg, component border below; left
  `femi@devopsfoundry:~$ ...` prompt string; right `■ LONDON, UK`.
- Tier 2 (nav): brand left (accent square logo placeholder); items
  HOME · PROJECTS · BLOG — all identical in style; active page gets accent
  border + small accent `■`; bare sun/moon toggle last.
- Compact: microbar ~6px vertical padding, nav row ~12px.
- Sticky, flat background, no blur. Mobile: microbar keeps location; nav
  collapses to brand + toggle + mono MENU (no hamburger).

## Signature element

GitHub contribution graph recoloured to the orange "foundry-heated" ramp
(surface → accent at 20/40/67/100%), mode-aware like the accent — LOCKED.
Real data tracked in issue #46.

## Modes

Light and dark are both first-class; every design must hold up in both —
LOCKED.

## Accessibility register

Known costs, accepted knowingly:

| Item | Measure | Status |
|---|---|---|
| 1.5px button border at 1x | rounds to 1px | Accepted — display-dependent; revisit if 1x traffic proves significant |
| Accent text on cream | 2.98:1 | Accepted — section-label word only |
| Accent text on near-black | 7.91:1 | Passes |
| Black on accent fill | 8.39:1 | Passes — why hover text is black |
| White on accent fill | 2.50:1 | **Forbidden** |
| White on dark `--data` | 2.76:1 | **Forbidden** — black in dark, cream in light |
| Body text, both modes | ≥ 9:1 | Passes |
| Semantic colours, both modes | ≥ 5.0:1 | Passes |
| Amber vs accent, dark | ΔE 18.6 | Restricted — see Colors |

## Page flow — homepage

Agreed structure (implementation phased):

1. **Hero** — profile summary, resume download, contact CTA, terminal as the
   desktop right column
2. **Credentials** — one thin quiet line of certifications under the hero.
   Not a section; supporting evidence for the hero
3. **Capabilities** — compressed table-grid, short
4. **Projects** — max 3 side by side, latest featured, links to `/projects`
5. **Blog** — latest posts, links to `/blog`
6. **GitHub activity** — small and centred, heated ramp
7. **Contact** — compact; backend already built, presentation only

## Parked / inspiration (not in use — keep for later)

- **Stat tiles with one accent-filled cell** — future enhancement candidate.
- **Off-white section bands** — cream stays; fallback for another project.
- **IBM Plex Sans + Mono pairing** — keep for a future project.
- **Proportional serif for long-form body** — mono at 18px is tiring over
  800+ words. The system-font stack (Iowan Old Style / Palatino / Book
  Antiqua) was rejected as unreliable across platforms. If revisited,
  self-host a real face.

## Process reminders

- Design deliverables are versioned HTML previews, never markdown:
  next number = new version, never overwrite (`AGENTS.md` has the full rule).
- Screenshot and self-review light + dark + mobile before showing work.
- Verify tokens resolve via computed styles, not by eye — a selector that
  never matches renders silently unstyled.
- **Measure weights, do not eyeball them.** Border widths snap to whole
  device pixels; read `getComputedStyle().borderTopWidth` back off the live
  page before claiming two weights differ.
- For multi-decision reviews, use the `html-deliverable` skill in feedback
  mode: an HTML page with persisted choices, per-section comments and a
  plain-text export the user can paste back.
- `.design-previews/` is **gitignored**. It is not backed up by git. Treat it
  as fragile.

## Known drift — not yet reconciled

`AGENTS.md` still describes an older state: `strokeWidth={1.5}`, a second
accent colour, a radius escape hatch, and `#ee7800` as a plain pressed
value rather than the mode-aware dark accent. The style guide wins where they
disagree. Left alone deliberately; reconcile when `AGENTS.md` is next revised.
