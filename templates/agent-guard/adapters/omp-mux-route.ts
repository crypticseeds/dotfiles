// omp extension: multiplexer routing (docs/plans/mux-routing-enforcement.md). Inside Herdr Core or the Herdr
// TUI, delegated agents and long or background jobs run as visible multiplexer children, not as omp's own.
//  - before_agent_start appends the host's rules (agent-route rules) to the system prompt of every prompt, so
//    they survive resume and compaction. Nothing is added outside Herdr.
//  - tool_call blocks the `task` (subagent) tool and bash with `async: true`; the reason is the redirect
//    message with the exact hc / herdr command, returned to the model as the tool error.
// Install: regen-agent-host.sh copies this file to ~/.omp/agent/extensions/mux-route.ts (omp loads every .ts
// file in that directory; restart omp); elsewhere copy it by hand. Not a security boundary, so it fails open:
// agent-route (herdr/.local/bin, stowed to ~/.local/bin) not installed, a spawn error, a timeout or any exit
// code other than 2 allows the call. Not covered: the `agent()` call inside omp's eval tool.
import { existsSync } from "node:fs"
import { spawnSync } from "node:child_process"
import { homedir } from "node:os"
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent"

const ROUTE = `${homedir()}/.local/bin/agent-route`
const RULES_TTL_MS = 5 * 60_000

let rules: { text: string; at: number } | undefined

function rulesText(): string {
  if (rules && Date.now() - rules.at < RULES_TTL_MS) return rules.text
  let text = ""
  if (existsSync(ROUTE)) {
    const run = spawnSync("python3", [ROUTE, "rules"], { encoding: "utf8", timeout: 20_000 })
    if (!run.error && run.status === 0) text = run.stdout.trim()
  }
  rules = { text, at: Date.now() }
  return text
}

export default function muxRoute(omp: ExtensionAPI): void {
  omp.on("before_agent_start", async (event) => {
    const text = rulesText()
    if (!text) return undefined
    return { systemPrompt: [...event.systemPrompt, text] }
  })
  omp.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "task" && event.toolName !== "bash") return undefined
    const input = event.input as { async?: boolean; cwd?: string }
    if (event.toolName === "bash" && input.async !== true) return undefined
    if (!existsSync(ROUTE)) return undefined
    const run = spawnSync("python3", [ROUTE, "check", "--neutral"], {
      input: JSON.stringify({ tool: event.toolName, input, cwd: input.cwd ?? ctx.cwd, harness: "omp" }),
      encoding: "utf8",
      timeout: 25_000,
    })
    if (run.error || run.status !== 2) return undefined
    return { block: true, reason: run.stdout.trim() || "multiplexer routing: use the Herdr multiplexer for this" }
  })
}
