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
| Interactivity | Collapsible detail, nav | Radios, checkboxes, comment boxes |
| Export button | Not needed | **Mandatory** |

The modes compose. A report that ends in "so, which do you want?" becomes a
report with a feedback section - and the moment it has one control, it needs
the export button.

## Non-negotiable rules

1. **Never overwrite a version.** `<slug>-v1.html`, `-v2.html`, and so on. Old
   versions stay available for reference and recovery.
2. **The user cannot send you HTML state.** They can only paste text. Any page
   with controls on it must have an export button, or the answers are trapped
   in their browser and the whole exercise is wasted.
3. **Open it for them.** `open <path>` after writing. Do not wait to be asked.
4. **Verify it yourself first.** Screenshot it, look at it, check both colour
   modes and a narrow viewport, fix problems before showing the user.
5. **Show real state, not descriptions of state.** Comparing two options means
   rendering both from identical markup so only the variable differs.
6. **Self-contained.** Inline CSS and JS, no external fetches, no build step.
   It must render correctly opened straight off disk.

## Style

### The project's style guide wins

Before writing anything, check whether the project has one - commonly
`.design-previews/style-guide.md` plus a versioned `style-guide-v<N>.html`, or
design tokens in `globals.css` / `tailwind.config`. If it exists, the page uses
**its** tokens, fonts, radius, borders and component patterns. A deliverable
that looks foreign to the project is harder to judge, because the user reacts
to your styling instead of the work.

### Otherwise, the house style

No project style guide means use this, consistently, every time. Do not invent
a new look per document.

```css
:root {
  --bg:#fbfbfa; --panel:#fff; --ink:#1a1a19; --muted:#6b6b66;
  --line:#e3e3df; --accent:#2f6f4f; --warn:#8a5a1f; --bad:#98342c;
  --radius:6px;
  --font:ui-sans-serif,-apple-system,"Segoe UI",Inter,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,monospace;
}
html[data-mode="dark"]{
  --bg:#141413; --panel:#1c1c1a; --ink:#eceae4; --muted:#9a9a92;
  --line:#2e2e2b; --accent:#6aa583; --warn:#c9964a; --bad:#d1706a;
}
body{ background:var(--bg); color:var(--ink); font:15px/1.6 var(--font); }
main{ max-width:860px; margin:0 auto; padding:32px 20px 96px; }
```

1px borders, generous whitespace, no shadows, no gradients, no decoration that
is not carrying information.

## Required structure

### Sticky top bar

Left to right:

1. Page title / version
2. Any global controls the page needs
3. The export button (feedback mode)
4. **The light/dark mode toggle - always last**

**Nothing comes after the mode toggle.** It is the final element on the right,
in every bar, on every page.

```html
<div class="topbar-in">
  <div class="t"><b>SLUG v1</b> · what this page is for</div>
  <div class="bar-actions">
    <button id="copy">Copy feedback</button>
    <button id="mode" aria-label="Toggle colour mode"><!-- icon last --></button>
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

### Diagrams

Include architecture, flow or sequence drawings wherever they carry the point
better than prose. Inline SVG or plain HTML/CSS boxes - same file, no library.

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

### A comment box per section

Ticks capture the decision. Comments capture the reason, the nuance, and the
thing you did not think to ask about. A free-text box at the end catches
everything else - users consistently give their most useful feedback there, so
always include it.

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

COMMENTS

  [<Section name>]
  <what they wrote>
```

Always emit unanswered items as `(not answered)` rather than omitting them. You
need to know the difference between "no" and "skipped".

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
- [ ] No horizontal overflow at 390px wide
- [ ] Both colour modes checked
- [ ] No external requests; opens correctly from `file://`
- [ ] Console is clean

Feedback mode additionally:

- [ ] Save cue fires and fades
- [ ] State survives a reload
- [ ] Export produces correct text including unanswered items

The token check matters most. Scoping tokens to a class you never apply is easy
to do and invisible until someone reports "nothing has any colour".

## Reading the response

When the user pastes their export back:

- Treat the comments as higher signal than the ticks. Ticks answer your
  question; comments tell you the question you should have asked.
- Watch for contradictions between a tick and its comment, and resolve them
  explicitly rather than silently picking one.
- Note anything marked `(not answered)` and ask about it directly if it matters.
