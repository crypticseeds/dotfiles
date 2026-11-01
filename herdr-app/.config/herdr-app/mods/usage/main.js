// The focused agent's icon and, for Claude, its usage in the status bar: context, 5-hour and
// 7-day limits as bars. Other agents show only their icon until they have a usage source.
//
// Context needs no setup: Claude Code records each running process in ~/.claude/sessions/<pid>.json
// (its session id and folder), and every reply's token use in that session's log. The context
// window is the model's published size. The 5h and 7d limits reach only Claude's status line, so
// they show when ~/.claude/statusline-command.sh writes ~/.cache/agent-usage/claude-<terminal>.json.

import { View, div, image, svg } from "gpui-kit";
import { h_flex } from "gpui-base";
import { agents, exec, focused, run, theme, window } from "herdr";

const BAR_W = 40;

// Current Claude models have a 1M context window; older ones 200K.
const windowOf = (model) => (/^claude-(fable|mythos|opus-5|opus-4-[678]|sonnet-5|sonnet-4-6|haiku-5)/.test(model ?? "") ? 1e6 : 2e5);

// Run on the agent's machine with the terminal's pid: finds the Claude process under that
// terminal, then prints the last log line that carries token usage.
const LAST_USAGE = `root=$1
for f in "$HOME"/.claude/sessions/*.json; do
  p=\${f##*/}; p=\${p%.json}
  case $p in ''|*[!0-9]*) continue ;; esac
  q=$p
  while [ -n "$q" ] && [ "$q" -gt 1 ]; do
    if [ "$q" = "$root" ]; then
      sid=$(sed -n 's/.*"sessionId":"\\([^"]*\\)".*/\\1/p' "$f")
      cwd=$(sed -n 's/.*"cwd":"\\([^"]*\\)".*/\\1/p' "$f")
      tac "$HOME/.claude/projects/$(printf %s "$cwd" | sed 's/[^A-Za-z0-9]/-/g')/$sid.jsonl" 2>/dev/null | grep -m1 '"usage"'
      exit 0
    fi
    q=$(ps -o ppid= -p "$q" | tr -d ' ')
  done
done`;

export default class Usage extends View {
  init(_props, cx) {
    this.data = {}; // agent address -> { ctx, five, five_reset, week, week_reset }
    cx.timer.every(3000, (cx) => this.read(cx));
  }

  // The focused Claude's numbers, read on its machine when its address is `machine/t7`.
  read(cx) {
    const a = this.agent;
    if (a?.app !== "claude-code") return;
    const [on, id] = a.address.includes("/") ? a.address.split("/") : [null, a.address];
    cx.spawn(async (cx) => {
      const pid = JSON.parse((await exec("hc", ["get", a.address, "--json"]).catch(() => null))?.stdout || "{}").pid;
      const [log, limits] = await Promise.all([
        pid ? exec("sh", ["-c", LAST_USAGE, "sh", String(pid)], { on }).catch(() => null) : null,
        exec("sh", ["-c", `cat "$HOME/.cache/agent-usage/claude-${id}.json"`], { on }).catch(() => null),
      ]);
      const parse = (r) => { try { return JSON.parse(r?.stdout ?? ""); } catch { return null; } };
      const d = { ...(parse(limits) ?? {}) };
      const m = parse(log)?.message;
      // No live Claude under that terminal (it exited, or it's a plain shell): show nothing.
      if (!m?.usage) {
        delete this.data[a.address];
        cx.notify();
        return;
      }
      const u = m.usage;
      d.ctx = (100 * ((u.input_tokens ?? 0) + (u.cache_read_input_tokens ?? 0) + (u.cache_creation_input_tokens ?? 0))) / windowOf(m.model);
      this.data[a.address] = d;
      cx.notify();
    });
  }

  render(_cx) {
    const t = theme();
    // The agent in the focused pane; none there (a plain shell), nothing shown.
    const f = focused();
    this.agent = agents().find((a) => a.pane === f?.pane || a.address === f?.agent) ?? null;
    const a = this.agent;
    if (!a) return this.frame(t, div());
    const p = a?.program;
    const pic = !p?.icon ? null : p.tint ? svg(p.icon).size(14).flex_none().text_color(t.foreground)
      : image(p.icon).w(14).h(14).flex_none();
    const d = this.data[a.address];
    if (a.app === "claude-code" && !d) return this.frame(t, div()); // not seen running yet, or gone
    if (!d) {
      return this.frame(t, h_flex().id("usage").gap(6).items_center().text_size(12).text_color(t.dim)
        .tooltip(`${p?.name ?? "Agent"}: no usage data`)
        .when(pic != null, (el) => el.child(pic)).child("no usage data"));
    }
    // Red at 80% and up, yellow from 50%, the plain text color below.
    const level = (v) => (v >= 80 ? t.ansi1 : v >= 50 ? t.ansi3 : t.foreground);
    const left = (epoch) => {
      const s = Math.max(0, epoch - Date.now() / 1000);
      const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
      return h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : `${h}h ${m}m`;
    };
    const meter = (name, v, reset) => {
      if (v == null) return null;
      const p = Math.round(v);
      return h_flex().gap(4).items_center()
        .child(div().text_color(t.foreground).child(name))
        .child(div().w(BAR_W).h(4).rounded(2).bg(t.raised)
          .child(div().h_full().w(`${Math.min(p, 100)}%`).rounded(2).bg(level(p))))
        .child(div().text_color(level(p)).child(`${p}%`))
        .when(reset != null, (el) => el.child(div().text_color(t.dim).child(left(reset))));
    };
    const tip = [
      "Claude",
      d.ctx != null ? `Context ${Math.round(d.ctx)}% of this session's window` : null,
      d.five != null ? `5-hour limit ${Math.round(d.five)}%, resets in ${left(d.five_reset)}` : null,
      d.week != null ? `7-day limit ${Math.round(d.week)}%, resets in ${left(d.week_reset)}` : null,
      d.at != null ? `Limits updated ${Math.round((Date.now() / 1000 - d.at) / 60)}m ago` : null,
    ].filter(Boolean).join("\n");

    return this.frame(t, h_flex().id("usage").h(22).px(6).gap(10).items_center().rounded(6).text_size(12)
      .hover((s) => s.bg(t.hover)).tooltip(tip)
      .when(pic != null, (el) => el.child(pic))
      .children([meter("ctx", d.ctx), meter("5h", d.five, d.five_reset), meter("7d", d.week, d.week_reset)]
        .filter(Boolean)));
  }

  // Styled like the status bar it continues (background, top border), with the Ctrl Shift P hint
  // that creamy-status no longer draws at the far right end.
  frame(t, content) {
    return h_flex().size_full().pl(6).pr(14).gap(16).items_center().justify_end()
      .bg(t.chrome).border_t(1).border_color(t.border)
      .child(content)
      .child(div().id("palette").text_size(11.8).text_color(t.dim).on_click(() => run("app.palette"))
        .child(`${window()?.platform === "macos" ? "\u2318" : "Ctrl"} Shift P  commands`));
  }
}
