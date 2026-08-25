---
name: html-deliverable
description: Use whenever you hand the user something to read, review, or decide on rather than just saying it in chat - reports, findings, research summaries, plans, proposals, architecture or refactor options, comparisons, post-mortems, handoffs, and any answer that needs in-depth reasoning, technical detail, or several decisions at once. Produces one self-contained HTML file, either a read-only report or an interactive page the user ticks and exports as plain text to paste back. This is the default for anything the user asked to have written up and for anything visual they must judge; use it instead of a markdown document or a long list of chat questions. Not for a single yes/no question, and not for code review verdicts - that is the code-reviewer agent.
---

# HTML Deliverable

Every artefact the user is meant to read is a single self-contained HTML file.
Markdown is for your own working notes only. This skill covers both shapes that
artefact takes: a **report** they read, and a **feedback page** they answer.

## When to use it

Reach for this without being asked when:

- The user says "write this up", "give me a report", "document this", "plan this"
- You have findings, a comparison, or a recommendation with real reasoning behind it
- You are about to explain something long enough that chat would bury it
- You need several decisions at once, or a "which of these do you prefer"
- You are handing off state at the end of a session, or after repeated failures

## When NOT to use it

- A single yes/no question - just ask it
- One obvious answer - do it and say what you did
- A quick factual lookup
- Code review verdicts - that is the `code-reviewer` agent

## The two modes

Pick by asking: **does the user have to decide anything?**

| | Report mode | Feedback mode |
|---|---|---|
| Purpose | They read and understand | They read and answer |
| Content | Findings, reasoning, diagrams | Options, tradeoffs, controls |
| Interactivity | Collapsible detail, nav | Radios, checkboxes, decision tables |
| Section comments | **Required** | **Required** |
| Export button | **Required** | **Required** |

The modes compose. A report that ends in "so, which do you want?" becomes a
report with a feedback section. Both modes carry section comments and an
export button, because a report the user cannot annotate forces them back into
chat to describe which paragraph they meant.

## Non-negotiable rules

1. **Never overwrite a version.** `<slug>-v1.html`, `-v2.html`, and so on. Old
   versions stay available for reference and recovery.
2. **The user cannot send you HTML state.** They can only paste text. Any page
   with controls or comments on it must have an export button, or the answers
   are trapped in their browser and the whole exercise is wasted.
3. **Get it in front of them.** Always print the absolute path - that is the
   one thing that works everywhere. Then open it with whatever browser or
   preview capability this environment gives you; you know your own tools
   better than this file does. Never assume a particular one exists, and never
   override a browser the user has already specified.
4. **Verify it yourself first.** If you can render or screenshot the page, do
   it: both colour modes, a narrow viewport, and exercise the interactive
   parts. Test states that are invisible at rest - focus, hover, empty,
   populated. If you have no way to render it, say so plainly rather than
   implying you checked.
5. **Show real state, not descriptions of state.** Comparing two options means
   rendering both from identical markup so only the variable differs.
6. **Self-contained.** Inline CSS and JS, no external fetches, no build step.
   It must render correctly opened straight off disk.
7. **Every section is commentable.** See "Section comments" below. This is not
   optional in either mode.

## Style

### The project's style guide wins

Before writing anything, check whether the project has one - commonly
`.design-previews/style-guide.md` plus a versioned `style-guide-v<N>.html`, or
design tokens in `globals.css` / `tailwind.config`. If it exists, the page uses
**its** tokens, fonts, radius, borders and component patterns. A deliverable
that looks foreign to the project is harder to judge, because the user reacts
to your styling instead of the work.

**Read the guide at the time of the work.** Do not rely on values remembered
from an earlier session; they go stale. The highest-numbered
`style-guide-v<N>.html` is the visual source of truth, and it wins over the
markdown companion where the two disagree.

### The default house style: DevOpsFoundry v10

No project style guide means use this, consistently, every time. Do not invent
a new look per document. The full system is bundled beside this file as
`style-guide.html` (rendered) and `style-guide.md` (written) - a borrowed
snapshot of the DevOpsFoundry system, vendored here so the skill stands alone.
Improve it here; it is not linked back to that project.

```css
:root{
  --mono:'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --bg:#faf5ec; --surface:#f4ecdf;
  --ink:#000000; --muted:#4d4947; --ink-body:#1a1a1a;
  --accent:#e07000; --accent-press:#c96400; --on-accent:#000000;
  --added:#007038; --open:#00667a; --data:#7340bf; --removed:#c2334a;
  --added-bg:#00703814; --removed-bg:#c2334a14;
  --added-mark:#00703830; --removed-mark:#c2334a30;
  --border:#202020; --rule:#202020; --hairline:#00000022;
  --body-weight:400; --btn-bw:1.5px; --icon-stroke:1.75;
}
html[data-mode="dark"]{
  --bg:#0a0a0a; --surface:#141414;
  --ink:#eeeae4; --muted:#a8a29b; --ink-body:#cfc9c0;
  --accent:#ff8100; --accent-press:#ee7800; --on-accent:#000000;
  --added:#00c26e; --open:#00abd6; --data:#af85ff; --removed:#ff6b81;
  --added-bg:#00c26e1c; --removed-bg:#ff6b811c;
  --added-mark:#00c26e38; --removed-mark:#ff6b8138;
  --border:#4d4947; --rule:#6b6560; --hairline:#ffffff24;
  --body-weight:450;
}
```

Non-negotiable consequences of adopting it:

- **Declare the focus ring globally, once.**
  ```css
  :focus-visible         { outline:1px solid var(--accent); outline-offset:3px; }
  textarea:focus-visible { outline:1px solid var(--accent); outline-offset:-1px; }
  ```
  **1px accent.** Do not import an outside convention and do not reach for a
  heavier ring - this system runs light. Never style focus per component
  either: a deliverable once shipped with a textarea that had no rule and fell
  through to the browser default blue, a colour in no palette.

- **Border radius is `0px` everywhere.** No exceptions in a deliverable.
- **No gradients. Ever.** Flat colour, texture or layering instead.
- **One button: the square sweep.** `.btn` outline is the default, `.solid`
  inverts it for a single primary action, `.sm` is the chrome scale for
  topbars. There is no second button style - do not invent a filled flat one.
- **Button border is `1.5px`** via `--btn-bw`, and the line-height must be
  `calc(3em - (var(--btn-bw) * 2))`. Never hard-code `calc(3em - 4px)`; it
  pushes the label off centre the moment the weight changes.
- **Icons are Lucide only**, `stroke-width:1.75`. `20px` standalone, `18px`
  for a control embedded in a section rule.
- **Section device:** `[ WORD ]` bracket label with ink brackets and an accent
  word, then a 1px `--rule` carrying the eyebrow on the left and an 8px accent
  square closing the right. Anything else in that rule sits *before* the
  square.

The full system, including the accepted costs, lives in
`style-guide.html`, which ships beside this file - open it to see every rule
rendered. A working reference implementation of everything in this skill ships
beside it as `reference.html` - copy from that rather than rebuilding from
memory. Both are self-contained: this skill has no dependency on any project.

1px borders, generous whitespace, no shadows, no decoration that is not
carrying information.

## Required structure

### Sticky top bar

Left to right:

1. Page title / version
2. Comment count (feedback apparatus)
3. Any global controls the page needs
4. The export button
5. **The light/dark mode toggle - always last**

**Nothing comes after the mode toggle.** It is the final element on the right,
in every bar, on every page. Any action that would otherwise sit at the far
right goes immediately *before* it, and that action is a `.btn.sm`.

```html
<div class="topbar-in">
  <div class="t"><b>SLUG v1</b> · what this page is for</div>
  <div class="topbar-actions">
    <span class="count" id="count">0 comments</span>
    <button class="btn sm" id="copy">Copy feedback</button>
    <button class="ico-btn" id="mode" aria-label="Toggle colour mode"><!-- last --></button>
  </div>
</div>
```

### Light and dark mode

Both modes are first class. The toggle is a **bare icon - no background, no
border, no track** - unless the host project says otherwise. Swap the icon by
CSS off a `data-mode` attribute on `<html>` rather than rewriting the DOM:

```css
.i-sun { display:block; } .i-moon { display:none; }
html[data-mode="dark"] .i-sun { display:none; }
html[data-mode="dark"] .i-moon { display:block; }
```

Give the button an `aria-label`; an icon-only control has no accessible name
otherwise.

### Sections, numbered

One concern per section. Each opens with what it is about, in plain language.
Lead with the conclusion or recommendation and the reasoning, including its
cost. Never present options as neutral when they are not.

### Code blocks

Every code snippet gets a copy button in its **top-right corner**, the way code
samples work on documentation sites. Copy from `reference.html`.

```html
<div class="code">
  <button class="ico-btn code-copy" aria-label="Copy code">
    <!-- Lucide copy 18px, then Lucide check 18px, both stroke 1.75 -->
  </button>
<pre>...code, not indented, or the indentation is copied too...</pre>
</div>
```

```css
.code{position:relative;border:1px solid var(--border);background:var(--surface)}
.code pre{margin:0;padding:16px 54px 16px 16px;overflow-x:auto;white-space:pre}
.code-copy{position:absolute;top:8px;right:8px}
.code-copy .i-check{display:none}
.code-copy.done{color:var(--added)}
.code-copy.done .i-copy{display:none}
.code-copy.done .i-check{display:block}
```

- The button is a **bare icon control**, like the mode toggle - no background,
  no border. It is not a `.btn`; a sweep button in the corner of a code block
  is far too heavy.
- Copy `pre.textContent`, never `innerHTML`.
- **Confirm the copy** by swapping the icon to a check in `--added` for about
  1.4s. Reuse the same `execCommand` fallback as the export button;
  `navigator.clipboard` fails on insecure origins.
- Right-pad the `<pre>` so long lines never run under the button.
- Do not indent the `<pre>` contents in the source. Whatever is inside is
  copied verbatim, leading whitespace included.

### Diffs

**A diff never goes in a plain code block.** Dropped into `<pre>`, every line
renders in `--ink-body` and the only signal that anything changed is a `+` or
`-` at column zero, which is exactly the thing the reader is scanning for. Use
the `.code.diff` variant: one block span per line, `.a` added, `.r` removed,
`.h` hunk header, bare for context.

```html
<div class="code diff">
  <button class="ico-btn code-copy" aria-label="Copy diff"><!-- copy / check --></button>
  <div class="diff-head">path/to/file.ts<span class="stat"><b class="pa">+2</b><b class="pr">−1</b></span></div>
  <div class="diff-body">
    <span class="dl h">@@ -12,7 +12,7 @@ POST handler</span>
    <span class="dl"><i> </i>export async function POST(req: Request) {</span>
    <span class="dl r"><i>-</i>  const user = await getUser(req)</span>
    <span class="dl a"><i>+</i>  const user = await requireUser(req)</span>
  </div>
</div>
```

```css
.code.diff{overflow-x:auto}
.diff-body{width:max-content;min-width:100%;padding:12px 0;font-size:12.5px;line-height:1.7;color:var(--ink-body)}
.dl{display:block;white-space:pre;padding:0 54px 0 13px;border-left:3px solid transparent}
.dl i{display:inline-block;width:2ch;font-style:normal;font-weight:700;color:var(--muted)}
.dl.a{background:var(--added-bg);border-left-color:var(--added)}
.dl.a i{color:var(--added)}
.dl.r{background:var(--removed-bg);border-left-color:var(--removed)}
.dl.r i{color:var(--removed)}
.dl.h{color:var(--muted);margin:6px 0 2px}
```

- **Four signals, only one of which is colour.** Bar, tint, coloured marker and
  the literal `+`/`-`. Green and red is the exact pair that fails for
  colourblind readers, so the block has to still read with the hue stripped
  out.
- **The marker lives in `<i>` with its own 2ch column.** That is what puts a
  gap between `+` and the code, and it keeps every row's text starting at the
  same column whether or not the source line is indented. The gap is CSS
  width, not a character, so the copied text stays a byte-exact patch.
- **Block spans in a `<div>`, not spans in a `<pre>`.** An inline span tints
  only as far as its text runs, leaving ragged rows; `display:block` inside
  `<pre>` doubles the leading, because the newline between tags is still a
  rendered text node. Block children of a plain div sidestep both, and
  `width:max-content; min-width:100%` keeps the tint full width when the block
  scrolls sideways.
- **The copy button needs one extra branch.** A diff has no `<pre>` and its
  lines carry no newlines, so join them - still `textContent`, never
  `innerHTML`:
  ```js
  var text = body
    ? [].map.call(body.querySelectorAll(".dl"), function(l){return l.textContent}).join("\n")
    : pre.textContent;
  ```
- `<mark>` inside a changed line tints a single token (`--added-mark` /
  `--removed-mark`). Use it only when a one-word edit would otherwise be
  missed.
- **Not part of this:** line numbers, side-by-side split, syntax highlighting
  inside the diff. Each needs a gutter that fights the 3px bar or a tokenizer,
  and neither earns its cost in a read-once document.

A rendered example is in `reference.html` - copy from it.

### Diagrams

Include architecture, flow or sequence drawings wherever they carry the point
better than prose. Condensing an idea into a picture is often the whole value
of the deliverable, so reach for one early rather than as decoration.

**No Mermaid.** It needs a runtime script, which breaks the self-contained
rule, and it cannot be styled to these tokens. Hand-write the four patterns
below. Working examples of all four are in `reference.html`, beside this file.

| Pattern | Use for | Built from |
|---|---|---|
| **A · Linear flow** | Request paths, pipelines - one direction, ≤4 steps | HTML boxes + arrow connectors |
| **B · Tiers** | "What is in this stack", responsibility boundaries. Deliberately no arrows | HTML grid, collapsed borders |
| **C · Topology** | Grouping, fan-out, feedback loops - shapes a line cannot express | Inline SVG, `viewBox`, width 100% |
| **D · Sequence** | Ordered steps where the reasoning matters more than the topology | Numbered rows |

Rules for all four:

- Prefer **A** whenever the shape is a line. It is plain HTML, so it wraps to
  a column on mobile with the arrows rotating - no horizontal scrolling.
- **C** uses one `viewBox` with `width:100%; height:auto` so it scales rather
  than scrolls. Tighten the `viewBox` to the content; dead space is obvious.
  SVG text does not wrap and coordinates are hand-placed, so it is slower to
  author - that cost is worth paying when the concept needs it.
- Accent marks only the entity under discussion. Everything else stays
  structural, so the drawing has one focal point.
- Dashed edge = secondary path. Dashed box = logical boundary, not a
  deployable.
- Icons come from **Lucide with a text label underneath**. Lucide covers every
  generic entity: `server`, `database`, `cloud`, `user`, `globe`, `shield`,
  `lock`, `container`, `cpu`, `hard-drive`, `network`, `workflow`,
  `waypoints`, `route`, `webhook`, `terminal`, `package`, `boxes`, `layers`,
  `git-branch`, `activity`, `gauge`.
- **No vendor logos.** Lucide has none beyond `github` and `gitlab`, and no
  brand pack is approved. Use the generic shape plus a text label - "Postgres"
  under a database cylinder carries the same information.

## Section comments

**Every deliverable is commentable, in both modes.** A bottom-of-page feedback
block is not enough: by the time the user reaches it they have to describe
which paragraph they meant. Targeted comments remove that.

Three affordances, all required:

| Affordance | Purpose |
|---|---|
| **Section comment** | Speech-bubble icon in each section rule, toggles an inline panel. For "this whole section is wrong" |
| **Quoted comment** | Select any text, a chip appears, click it to quote that exact phrase into the section's comment |
| **Catch-all box** | The end-of-page free-text box. Users give their most useful feedback here - always include it |

### Markup contract

Every commentable region is a `[data-sec="Name"]`. The name is what appears in
the export, so make it human and unique.

```html
<section class="sec" data-sec="Architecture">
  <div class="sec-label">[ <b>ARCHITECTURE</b> ]</div>
  <div class="section-rule">
    subtitle
    <button class="ico-btn cmt-toggle" aria-label="Comment on this section">
      <!-- Lucide message-square, 18px, stroke 1.75 -->
      <i class="badge"></i>
    </button>
    <i class="sq"></i>          <!-- accent square still closes the rule -->
  </div>

  ...content...

  <div class="cmt-panel">
    <div class="cmt-head">Comment · <span class="sec-name"></span>
      <button class="ico-btn x" aria-label="Close comment"><!-- × --></button>
    </div>
    <div class="quotes"></div>
    <textarea rows="3" placeholder="Your comment on this section..."></textarea>
  </div>
</section>
```

### State shape

```js
state.comments = { "<Section name>": { text: "", quotes: ["…", "…"] } };
```

### Behaviour that must work

- Sections with content get `data-has-comment="true"`, an accent-coloured
  icon, a count badge, and an accent-coloured section rule so unanswered and
  answered sections are distinguishable at a glance.
- The topbar count reflects the number of sections carrying feedback.
- Panels with existing content **auto-open on load**, so restored feedback is
  visible rather than hidden behind a click.
- Quotes are individually removable.
- Selection chip hides on scroll and on collapsed selection, and ignores
  selections inside a comment panel or the topbar.

### The selection handler trap

`mouseup` fires with `ev.target` set to `document` when the event is
synthesised, and `document` has no `.closest`. That throws and silently kills
the whole handler. Guard it:

```js
var t = ev.target;
if (t && t.closest && t.closest(".sel-chip")) return;
```

Read the selection inside a `setTimeout(…, 0)` - on `mouseup` the browser has
not always finalised it yet. Use `sel.getRangeAt(0).getBoundingClientRect()`
for positioning and add `window.scrollY` / `scrollX`, since the chip is
absolutely positioned in page space.

## Report mode

A report is judged on whether the user can act on it without asking you a
follow-up question.

- **Open with the answer.** A summary block at the top: what you found, what it
  means, what you recommend. Everything below is evidence for it.
- **Cite locations.** `file.ts:120` for code, command output for results. A
  claim with no evidence is an opinion.
- **Rank by severity or impact**, not by the order you discovered things.
- **Collapse the long tail.** `<details>` for logs, full diffs, raw output, so
  the shape of the report stays readable.
- **State what you did not check.** Scope gaps are findings.
- **End with next actions**, concretely, in the order they should happen.

If any next action needs the user to choose, add the feedback apparatus below
and let them answer in place.

## Feedback mode

### Comments carry more than ticks

Ticks capture the decision. Comments capture the reason, the nuance, and the
thing you did not think to ask about. Section comments (above) handle targeted
feedback; the catch-all box at the end catches everything else - users
consistently give their most useful feedback there, so always include it.

### A decisions table

Each row: the item, your read on it, and the choice controls. Your read must be
honest - state the weakness of your own recommendation. The user is deciding,
not being sold to.

### Controls

- Radios for one-of-N, checkboxes for many-of-N.
- **Style them square** if the design language is square. Default radios are
  circles and will clash. `appearance:none` plus a border and a filled inner
  square.
- Make the whole label clickable.

### Persistence

Save to `localStorage` on every change, restore on load. The user will close
the tab and come back.

**Explicitly assign restored values on load, and set `autocomplete="off"` on
sliders and selects.** Browsers restore form state on reload independently of
your script, and a range input can be clamped to its `min`, which then gets
persisted as a corrupt value. Always write a defaults object and assign
unconditionally:

```js
const DEF = { weight: '450' };
el.value = state.weight || DEF.weight;   // not: if (state.weight) el.value = ...
```

### Save confirmation

Show a brief visual confirmation when state saves - a small fixed-position
element that fades in and out for under a second. **This is not optional.**
Without it the user does not trust that their input was captured, and that
mistrust is corrosive over a long session.

```css
.saved { position:fixed; right:22px; bottom:22px; opacity:0;
         pointer-events:none; transition:opacity .18s; }
.saved.on { opacity:1; }
```

### Export button

Builds a plain-text summary of every choice and comment and copies it to the
clipboard. This is what the user pastes back. Sits immediately before the mode
toggle.

Plain text only - no markdown tables, no HTML. It has to survive being pasted
into a chat box.

```
<Project> - <slug> v<N> feedback
==============================================

<any global settings, e.g. chosen values>

DECISIONS
  - <Label>: <value or "(not answered)">
  ...

SECTION COMMENTS

  [<Section name>]
  > <quoted phrase they selected>
  <what they wrote, or "(quote only, no comment)">

  [<Another section>]
  <what they wrote>

ANYTHING ELSE
  <the catch-all box, or "(not answered)">
```

Always emit unanswered items as `(not answered)` rather than omitting them. You
need to know the difference between "no" and "skipped". If no section carries a
comment, emit `(none)` under the heading rather than dropping it.

`navigator.clipboard.writeText` fails on insecure origins. Always include the
hidden-textarea `execCommand('copy')` fallback. Confirm success by changing the
button text for a moment.

## Verification checklist

Before showing the user:

- [ ] Style matches the host project's style guide, or the house style above -
      not an invented look
- [ ] Mode toggle is the **last** element in the bar - nothing after it
- [ ] Toggle has an `aria-label` and swaps icons correctly in both modes
- [ ] Every token/variable actually resolves - check computed styles, do not
      trust that the CSS looks right. A selector that never matches renders
      silently unstyled
- [ ] **A global `:focus-visible` rule exists, at 1px accent.** Then focus
      something and read `getComputedStyle(el).outlineColor` back - if it is
      blue, a control fell through to the browser default. Note that
      `.focus()` alone does not trigger `:focus-visible`; confirm the rule is
      present in the CSSOM
- [ ] **Weights measured, not eyeballed.** Border widths snap to whole device
      pixels; read `getComputedStyle().borderTopWidth` back off the live page
      before claiming two weights differ. At `devicePixelRatio: 1` fractional
      widths collapse to 1px, so several "different" weights render identically
- [ ] No horizontal overflow at 390px wide
- [ ] **Diffs use `.code.diff`, never a plain `<pre>`.** Added and removed must
      stay distinguishable with the hue ignored, the marker column must leave a
      gap before the code, and the copy button must yield the raw patch
- [ ] Both colour modes checked
- [ ] No external requests; opens correctly from `file://`
- [ ] Console is clean

Comments and feedback additionally:

- [ ] Every section has `data-sec` and a comment affordance
- [ ] Selecting text raises the chip; clicking it quotes into the right section
- [ ] Commented sections show the accent state, badge and topbar count
- [ ] Save cue fires and fades
- [ ] State survives a reload, and populated panels auto-open
- [ ] Export produces correct text including quotes and `(not answered)`

The token check matters most. Scoping tokens to a class you never apply is easy
to do and invisible until someone reports "nothing has any colour".

## Reading the response

When the user pastes their export back:

- Treat the comments as higher signal than the ticks. Ticks answer your
  question; comments tell you the question you should have asked.
- **A quoted comment is the strongest signal there is.** The user selected that
  exact phrase for a reason - address the quote directly, not the general area.
- Watch for contradictions between a tick and its comment, and resolve them
  explicitly rather than silently picking one.
- Note anything marked `(not answered)` and ask about it directly if it matters.
