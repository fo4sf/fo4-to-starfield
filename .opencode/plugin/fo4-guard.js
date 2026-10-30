// Refuses every shell call that tools/ai-team/guard/allowlist.py does not allow, and every file write it refuses.
// OpenCode runs the "tool.execute.before" hook before a tool call, and a throw there stops the call. The checker is a
// separate process that reads the call on stdin (no shell is involved), and only an exit code of 0 lets a call through:
// a missing Python, a timeout or unreadable output all refuse.
import { spawnSync } from "node:child_process";
import path from "node:path";

// The tools that write files, and where each names its paths. A patch names them inside its text; a write that names no
// file is refused, since there is nothing to check. (Not exported: OpenCode calls every exported function as a plugin.)
const WRITE_TOOLS = new Set(["edit", "write", "multiedit", "patch", "apply_patch"]);
const PATCH_FILE = /^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$/gm;

function writtenPaths(args) {
  const paths = [];
  for (const key of ["filePath", "file_path", "path"]) {
    if (typeof args?.[key] === "string") paths.push(args[key]);
  }
  for (const key of ["patchText", "patch", "input"]) {
    if (typeof args?.[key] === "string") {
      for (const m of args[key].matchAll(PATCH_FILE)) paths.push(m[1].trim());
    }
  }
  return paths;
}

export const Fo4Guard = async ({ worktree, directory }) => {
  const root = worktree || directory;
  const checker = path.join(root, "tools", "ai-team", "guard", "allowlist.py");
  const ask = (call) => {
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
  };
  return {
    "tool.execute.before": async (input, output) => {
      const unattended = process.env.FO4SF_UNATTENDED === "1";
      // run-lead.ps1 sets FO4SF_UNATTENDED=1. In those runs the Lead may not hand work to fo4-implement, which can edit
      // code and run the tests it edited; the prompt already says so, and this makes it hold without the prompt.
      if (unattended && input.tool === "task" && JSON.stringify(output?.args ?? {}).includes("fo4-implement")) {
        throw new Error("guard refused the command: unattended runs do not delegate to fo4-implement");
      }
      const args = output?.args || {};
      if (WRITE_TOOLS.has(input.tool)) {
        return ask({ root, write: writtenPaths(args) });
      }
      const command = args.command;
      if (input.tool !== "bash" && typeof command !== "string") return;
      // The working-directory argument's name is not pinned across OpenCode versions, so check whichever one is set.
      const workdir = args.workdir ?? args.cwd ?? args.dir ?? args.directory;
      // terminal.ps1 sets FO4SF_OWNER_PRESENT=1 for the owner's own terminal; an unattended run never counts as one.
      const owner_present = process.env.FO4SF_OWNER_PRESENT === "1" && !unattended;
      return ask({ root, command, workdir, owner_present });
    },
  };
};

export default Fo4Guard;
