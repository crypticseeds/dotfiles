// The focused agent's icon and, for Claude, its usage in the status bar: context, 5-hour and
// 7-day limits as bars. Other agents show only their icon until they have a usage source.
// Claude Code hands these only to its status line, so ~/.claude/statusline-command.sh
// writes them to ~/.cache/agent-usage/claude.json; this reads that file when it changes.

import { View, div, image, svg } from "gpui-kit";
import { h_flex } from "gpui-base";
import { agents, focused, home, readTextFile, theme, watchFolder } from "herdr";

const BAR_W = 40;

export default class Usage extends View {
  init(_props, cx) {
    this.dir = `${home()}/.cache/agent-usage`;
    this.data = null;
    this.load(cx);
    cx.spawn(async (cx) => {
      for (;;) {
        await watchFolder(this.dir);
        await this.read();
        cx.notify();
      }
    });
    // Reset countdowns move even when the file doesn't.
    cx.timer.every(60000, (cx) => cx.notify());
  }

  load(cx) {
    cx.spawn(async (cx) => {
      await this.read();
      cx.notify();
    });
  }

  async read() {
    const text = await readTextFile(`${this.dir}/claude.json`);
    try {
      this.data = text ? JSON.parse(text) : null;
    } catch {
      // A partial write; keep the last good reading.
    }
  }

  render(_cx) {
    const t = theme();
    // The agent in the focused pane; on a plain shell, keep the last agent so it doesn't flicker.
    const pane = focused()?.pane;
    this.agent = agents().find((a) => a.pane === pane) ?? this.agent;
    const a = this.agent;
    const p = a?.program;
    const pic = !p?.icon ? null : p.tint ? svg(p.icon).size(14).flex_none().text_color(t.foreground)
      : image(p.icon).w(14).h(14).flex_none();
    const claude = !a || a.app === "claude-code";
    const d = claude ? this.data : null;
    if (!d) {
      return h_flex().size_full().px(12).items_center().justify_end().child(
        h_flex().id("usage").gap(6).items_center().text_size(12).text_color(t.dim)
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
      d.ctx != null ? `Context ${Math.round(d.ctx)}% (latest session)` : null,
      d.five != null ? `5-hour limit ${Math.round(d.five)}%, resets in ${left(d.five_reset)}` : null,
      d.week != null ? `7-day limit ${Math.round(d.week)}%, resets in ${left(d.week_reset)}` : null,
      `Updated ${Math.round((Date.now() / 1000 - d.at) / 60)}m ago`,
    ].filter(Boolean).join("\n");

    return h_flex().size_full().px(6).items_center().justify_end().child(
      h_flex().id("usage").h(22).px(6).gap(10).items_center().rounded(6).text_size(12)
        .hover((s) => s.bg(t.hover)).tooltip(tip)
        .when(pic != null, (el) => el.child(pic))
        .children([meter("ctx", d.ctx), meter("5h", d.five, d.five_reset), meter("7d", d.week, d.week_reset)]
          .filter(Boolean)));
  }
}
