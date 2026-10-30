// Refuses every shell call that tools/ai-team/guard/allowlist.py does not allow. OpenCode runs the "tool.execute.before"
// hook before a tool call (and before its own permission check), and a throw there stops the call. The checker is a
// separate process that reads the command on stdin (no shell is involved), and only an exit code of 0 lets a call
// through: a missing Python, a timeout or unreadable output all refuse.
//
// OpenCode only logs a plugin that fails to load and carries on without it. So the plugin also marks every model request
// with a header (chat.headers), and the guardian proxy refuses inference without it (config.json "require_guard_header"):
// a session whose guard did not load gets no model, so no tool call happens either.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const GUARD_HEADER = "X-FO4SF-Guard";
const GUARD_VALUE = "fo4-guard/1";

export const Fo4Guard = async ({ worktree, directory }) => {
  const root = worktree || directory;
  const checker = path.join(root, "tools", "ai-team", "guard", "allowlist.py");
  if (!existsSync(checker)) throw new Error(`fo4-guard: no checker at ${checker}`);   // no plugin, so no header
  // Tests shorten the wait for a hung checker; it is never longer than 15 s.
  const timeout = Math.min(15000, Math.max(1000, Number(process.env.FO4SF_GUARD_TIMEOUT_MS) || 15000));
  return {
    "chat.headers": async (_input, output) => {
      output.headers[GUARD_HEADER] = GUARD_VALUE;
    },
    "tool.execute.before": async (input, output) => {
      const args = output?.args || {};
      // run-lead.ps1 sets FO4SF_UNATTENDED=1. In those runs the Lead may not hand work to fo4-implement, which can edit
      // code and run the tests it edited; the prompt already says so, and this makes it hold without the prompt.
      // OpenCode looks a subagent up by its exact name, so an exact compare covers every way to start it.
      if (process.env.FO4SF_UNATTENDED === "1" && input.tool === "task" && args.subagent_type === "fo4-implement") {
        throw new Error("guard refused the command: unattended runs do not delegate to fo4-implement");
      }
      // The shell tool is "bash" in OpenCode 1.18.35, for PowerShell too. Other tools with a "command" argument (task
      // records the slash command that started it) are not shell calls.
      if (input.tool !== "bash") return;
      // The working-directory argument's name is not pinned across OpenCode versions, so check whichever one is set.
      const workdir = args.workdir ?? args.cwd ?? args.dir ?? args.directory;
      const call = { root, directory, command: args.command, workdir };
      const run = spawnSync(process.env.FO4SF_PYTHON || "python", ["-I", checker], {
        input: JSON.stringify(call),
        encoding: "utf8",
        timeout,
        windowsHide: true,
      });
      if (run.status === 0) return;
      let reason = "no verdict from the guard";
      try {
        reason = JSON.parse(run.stdout).reason || reason;
      } catch {
        // keep the default reason: the guard failed closed
      }
      throw new Error(`guard refused the command: ${reason}`);
    },
  };
};

export default Fo4Guard;
