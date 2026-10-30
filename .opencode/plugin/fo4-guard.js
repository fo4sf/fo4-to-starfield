// Refuses every shell call that tools/ai-team/guard/allowlist.py does not allow. OpenCode runs the "tool.execute.before"
// hook before a tool call, and a throw there stops the call. The checker is a separate process that reads the command
// on stdin (no shell is involved), and only an exit code of 0 lets a call through: a missing Python, a timeout or
// unreadable output all refuse.
import { spawnSync } from "node:child_process";
import path from "node:path";

export const Fo4Guard = async ({ worktree, directory }) => {
  const root = worktree || directory;
  const checker = path.join(root, "tools", "ai-team", "guard", "allowlist.py");
  return {
    "tool.execute.before": async (input, output) => {
      // run-lead.ps1 sets FO4SF_UNATTENDED=1. In those runs the Lead may not hand work to fo4-implement, which can edit
      // code and run the tests it edited; the prompt already says so, and this makes it hold without the prompt.
      if (process.env.FO4SF_UNATTENDED === "1" && input.tool === "task" &&
          JSON.stringify(output?.args ?? {}).includes("fo4-implement")) {
        throw new Error("guard refused the command: unattended runs do not delegate to fo4-implement");
      }
      const command = output?.args?.command;
      if (input.tool !== "bash" && typeof command !== "string") return;
      // The working-directory argument's name is not pinned across OpenCode versions, so check whichever one is set.
      const args = output?.args || {};
      const workdir = args.workdir ?? args.cwd ?? args.dir ?? args.directory;
      const call = { root, command, workdir };
      const run = spawnSync(process.env.FO4SF_PYTHON || "python", ["-I", checker], {
        input: JSON.stringify(call),
        encoding: "utf8",
        timeout: 15000,
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
