// This computer's CPU and memory as one line, like herdr-gui's sidebar:
// CPU as a graph of recent samples, memory as a bar. Hover for details.
// Reads /proc, so it shows only on Linux.

import { View, div } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { exec, readTextFile, run, theme } from "herdr";

const SAMPLES = 16;
const NARROW = 210;
const RAIL = 100;
const METER_MAX = 56; // CPU graph and MEM bar fill the room left, equally, up to this

export default class SysInfo extends View {
  init(_props, cx) {
    this.cpu = [];
    this.prev = null;
    this.info = null;
    cx.timer.every(2000, (cx) => this.refresh(cx));
    this.refresh(cx);
  }

  refresh(cx) {
    cx.spawn(async (cx) => {
      const [stat, mem, load, up, df] = await Promise.all([
        readTextFile("/proc/stat"), readTextFile("/proc/meminfo"),
        readTextFile("/proc/loadavg"), readTextFile("/proc/uptime"),
        exec("df", ["-B1", "--output=size,avail", "/"]).catch(() => null),
      ]);
      if (!stat || !mem) return;

      const t = stat.split("\n")[0].trim().split(/\s+/).slice(1).map(Number);
      const idle = t[3] + (t[4] || 0);
      const total = t.reduce((a, b) => a + b, 0);
      if (this.prev) {
        const dt = total - this.prev.total;
        const pct = dt > 0 ? Math.round(100 * (1 - (idle - this.prev.idle) / dt)) : 0;
        this.cpu = [...this.cpu, pct].slice(-SAMPLES);
      }
      this.prev = { idle, total };

      const kb = (k) => Number((mem.match(new RegExp(`^${k}:\\s+(\\d+)`, "m")) || [])[1] || 0) * 1024;
      const memTotal = kb("MemTotal"), memUsed = memTotal - kb("MemAvailable");
      const [size, avail] = (df?.stdout.trim().split("\n")[1] || "").trim().split(/\s+/).map(Number);
      this.info = {
        cores: (stat.match(/^cpu\d+ /gm) || []).length,
        load: (load || "").split(" ").slice(0, 3).join(" "),
        memTotal, memUsed,
        diskSize: size || 0, diskFree: avail || 0,
        uptime: Number((up || "0").split(" ")[0]),
      };
      cx.notify();
    });
  }

  tooltip() {
    const i = this.info;
    if (!i) return "This machine";
    const gb = (b) => (b / 2 ** 30).toFixed(1);
    const h = Math.floor(i.uptime / 3600), m = Math.floor((i.uptime % 3600) / 60);
    const up = h >= 24 ? `${Math.floor(h / 24)}d ${h % 24}h` : `${h}h ${m}m`;
    const lines = [
      "This machine",
      `CPU ${this.cpu.at(-1) ?? 0}% of ${i.cores} cores · load ${i.load}`,
      `Memory ${gb(i.memUsed)} GB of ${gb(i.memTotal)} GB (${Math.round(100 * i.memUsed / i.memTotal)}%)`,
    ];
    if (i.diskSize) {
      lines.push(`Disk ${Math.round(i.diskFree / 1e9)} GB free of ${Math.round(i.diskSize / 1e9)} GB ` +
        `(${Math.round(100 * (1 - i.diskFree / i.diskSize))}% used)`);
    }
    lines.push(`Up ${up}`);
    return lines.join("\n");
  }

  render(_cx) {
    const t = theme();
    // Red at 80% and up, yellow from 50%, the plain text color below.
    const level = (v) => (v >= 80 ? t.ansi1 : v >= 50 ? t.ansi3 : t.foreground);
    const cpu = this.cpu.at(-1) ?? 0;
    const memPct = this.info ? Math.round(100 * this.info.memUsed / this.info.memTotal) : 0;
    const samples = [...Array(SAMPLES - this.cpu.length).fill(0), ...this.cpu];
    const graph = h_flex().flex_1().max_w(METER_MAX).h(10).gap(1).items_end().children(
      samples.map((v, n) => div().id(`cpu-${n}`).flex_1().h(Math.max(1, Math.round(v / 10))).bg(level(v))));
    const bar = div().flex_1().max_w(METER_MAX).h(4).rounded(2).bg(t.raised).child(
      div().h_full().w(`${memPct}%`).rounded(2).bg(level(memPct)));
    const pct = (v) => div().w(32).flex_none().text_color(level(v)).child(`${v}%`);
    const label = (s) => div().w(28).flex_none().text_color(t.foreground).child(s);
    const cpuRow = [label("CPU"), graph, pct(cpu)];
    const memRow = [label("MEM"), bar, pct(memPct)];

    // The tooltip sits on an inner row with a hover style, like the shipped mods' tooltips.
    let inner;
    if (this.mode === "rail") {
      // Collapsed sidebar: a letter and the colored percentage per line.
      const short = (s, v) => h_flex().gap(2).children([div().text_color(t.foreground).child(s), pct(v).w("auto")]);
      inner = v_flex().gap(2).py(3).items_center().text_size(10).children([short("C", cpu), short("M", memPct)]);
    } else if (this.mode === "stack") {
      inner = v_flex().gap(2).py(3).children([h_flex().gap(4).items_center().children(cpuRow),
        h_flex().gap(4).items_center().children(memRow)]);
    } else {
      inner = h_flex().h(22).gap(4).items_center().children([...cpuRow, ...memRow]);
    }
    inner = inner.id("sysinfo").flex_1().px(this.mode === "rail" ? 0 : 6).rounded(6)
      .when(this.mode !== "rail", (el) => el.text_size(12))
      .hover((s) => s.bg(t.hover)).tooltip(this.tooltip());
    return h_flex().id("root").size_full().px(this.mode === "rail" ? 2 : 6).items_center()
      .on_size_change((size, cx) => this.fit(size.width, cx)).child(inner);
  }

  // Below NARROW px the line can't fit, so MEM drops under CPU and the block grows to hold it.
  // Below RAIL px (the collapsed sidebar) only a letter and the percentage fit.
  fit(width, cx) {
    const mode = width < RAIL ? "rail" : width < NARROW ? "stack" : "line";
    if (mode === this.mode) return;
    this.mode = mode;
    run("layout.resize", { id: "sysinfo", px: mode === "line" ? 28 : 46 });
    cx.notify();
  }
}
