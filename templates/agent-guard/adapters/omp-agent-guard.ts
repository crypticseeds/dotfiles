// omp extension: runs the shared agent guard (agent_guard.py, installed root-owned by
// templates/agent-permissions/regen-agent-host.sh) on every bash tool call, before it runs.
// Install: regen-agent-host.sh copies this file to ~/.omp/agent/extensions/agent-guard.ts (omp loads every
// .ts file in that directory; restart omp). Uses omp's `tool_call` extension event: returning
// { block: true, reason } stops the call and returns the reason to the model as the tool error.
// Fails closed: a missing guard, a spawn error, a timeout or any exit code other than 0 (allow) and 2
// (deny) blocks the call. (omp itself also blocks when a handler throws or exceeds toolCallTimeoutMs, 30 s.)
// Not covered: omp's python/eval-style tools, which are not the bash tool. ~/.omp is user-writable, so
// an agent running as that user can remove this file; omp has no managed (root-owned) extension path.
import { existsSync } from "node:fs"
import { spawnSync } from "node:child_process"
import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent"

const GUARD = "/usr/local/lib/agent-guard/agent_guard.py"

export default function agentGuard(omp: ExtensionAPI): void {
  omp.on("tool_call", async (event, ctx) => {
    if (event.toolName !== "bash") return undefined
    if (!existsSync(GUARD)) {
      return { block: true, reason: `agent guard: ${GUARD} is missing, failing closed (run regen-agent-host.sh)` }
    }
    const input = event.input as { command?: string; cwd?: string }
    const run = spawnSync("python3", [GUARD, "--neutral"], {
      input: JSON.stringify({ command: String(input.command ?? ""), cwd: input.cwd ?? ctx.cwd, harness: "omp" }),
      encoding: "utf8",
      timeout: 25_000,
    })
    if (run.error) {
      return { block: true, reason: `agent guard: could not run ${GUARD} (${run.error.message}), failing closed` }
    }
    if (run.status === 0) return undefined
    const reason = run.status === 2 ? run.stdout.trim() : `exit ${run.status}: ${run.stderr.trim()}`
    return { block: true, reason: reason || "agent guard: denied" }
  })
}
