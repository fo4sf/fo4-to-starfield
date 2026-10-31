// Refuses every shell call that tools/ai-team/guard/allowlist.py does not allow, and every file write it refuses.
// OpenCode runs the "tool.execute.before" hook before a tool call (and before its own permission check), and a throw
// there stops the call. The checker is a separate process that reads the call on stdin (no shell is involved), and only
// an exit code of 0 together with its {"allowed": true} lets a call through: a missing Python, a timeout, unreadable
// output or a program that only exits 0 all refuse.
//
// OpenCode only logs a plugin that fails to load and carries on without it. So the plugin also marks every model request
// with a header (chat.headers), and the guardian proxy refuses inference without it (config.json "require_guard_header"):
// a local session whose guard did not load gets no model, so no tool call happens either. A Claude request goes to
// Anthropic, not the proxy, so nothing checks the header there: terminal.ps1 checks that this file and
// fo4-cloud-cap.js exist, clears OPENCODE_PURE and turns OpenCode's auto-update off in its window.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

const GUARD_HEADER = "X-FO4SF-Guard";
const GUARD_VALUE = "fo4-guard/1";
// OpenCode 1.18.35's built-in tools other than the shell. Any other tool (an MCP server's, or a custom tool from a
// config folder) is refused: the guard cannot tell what it runs. (Not exported: OpenCode calls every exported function
// as a plugin.)
const BUILT_IN = new Set(["invalid", "question", "read", "glob", "grep", "edit", "write", "task", "webfetch", "todowrite",
  "websearch", "skill", "apply_patch", "lsp", "plan_exit"]);

// The tools that write files, and where each names its paths. A patch names them inside its text; a write that names no
// file is refused, since there is nothing to check. (Not exported: OpenCode calls every exported function as a plugin.)
const WRITE_TOOLS = new Set(["edit", "write", "multiedit", "patch", "apply_patch"]);
// A header line, read the way OpenCode 1.18.35 reads one (it splits the text on "\n" only and trims the rest of the
// line). Spaces around the "***" and the colon vary between patch writers, so the match does not depend on them: it
// takes every line OpenCode takes as a header, and more.
const PATCH_FILE = /^\s*\*\*\*\s*(?:Add File|Update File|Delete File|Move to)\s*:\s*(.+?)\s*$/i;
// Any other line break or control character in a patch is refused: a "\r" or U+2028 would end the path here but not in
// OpenCode, so the guard would check one file while OpenCode writes another.
const PATCH_CONTROL = /[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u2028\u2029]/;

function writtenPaths(args) {
  const paths = [];
  for (const key of ["filePath", "file_path", "path"]) {
    if (typeof args?.[key] === "string") paths.push(args[key]);
  }
  for (const key of ["patchText", "patch", "input"]) {
    if (typeof args?.[key] === "string") {
      if (PATCH_CONTROL.test(args[key])) {
        throw new Error("guard refused the command: a patch with a control character or a line break other than \\n");
      }
      for (const line of args[key].split("\n")) {
        const m = PATCH_FILE.exec(line);
        if (m) paths.push(m[1]);
      }
    }
  }
  return paths;
}

export const Fo4Guard = async ({ worktree, directory }) => {
  const root = worktree || directory;
  const checker = path.join(root, "tools", "ai-team", "guard", "allowlist.py");
  if (!existsSync(checker)) throw new Error(`fo4-guard: no checker at ${checker}`);   // no plugin, so no header
  // The wait for the checker: 60 s, as 15 s ran out on the team PC at over 90% RAM (30 Oct). Tests shorten it for a
  // hung checker; it is never longer.
  const timeout = Math.min(60000, Math.max(1000, Number(process.env.FO4SF_GUARD_TIMEOUT_MS) || 60000));
  const ask = (call) => {
    const python = process.env.FO4SF_PYTHON || "";
    // OpenCode runs on Bun, which cannot start the Microsoft Store's python.exe alias: every call would come back
    // with no verdict, so say what to fix instead
    if (/[\\/]WindowsApps[\\/]/i.test(python)) {
      throw new Error("guard refused the command: FO4SF_PYTHON is the Microsoft Store python alias, which OpenCode " +
        "cannot start: set it to the python.exe that python -c \"import sys; print(sys.executable)\" prints, in the " +
        "window that starts OpenCode");
    }
    // Only a full path: a bare name is looked up when the checker starts, and on Windows that lookup may try the
    // session's folder (the repo, which agents can write) before PATH. run-lead.ps1 always passes one.
    if (!path.isAbsolute(python)) {
      throw new Error(`guard refused the command: FO4SF_PYTHON ${python ? "is not a full path" : "is not set"}: set ` +
        "it to the python.exe that python -c \"import sys; print(sys.executable)\" prints, in the window that starts " +
        "OpenCode");
    }
    const run = spawnSync(python, ["-I", checker], {
      input: JSON.stringify(call),
      encoding: "utf8",
      timeout,
      windowsHide: true,
    });
    let verdict = null;
    try {
      verdict = JSON.parse(run.stdout);
    } catch {
      // no verdict: described below
    }
    // the exit code and the checker's own verdict, so a wrong program that exits 0 refuses too
    if (run.status === 0 && verdict?.allowed === true) return;
    let reason = typeof verdict?.reason === "string" ? verdict.reason : null;   // "" is no reason either
    if (!reason) {
      // the guard failed closed; say what became of the checker, so a broken Python can be told from a refusal
      const how = run.error ? run.error.code || run.error.message
        : run.signal ? `stopped by ${run.signal}` : `exit ${run.status}`;
      const err = String(run.stderr || "").replace(/[^\x20-\x7e]+/g, " ").trim().slice(0, 300);
      reason = `no verdict from the guard (${python}: ${how}${err ? "; " + err : ""})`;
    }
    throw new Error(`guard refused the command: ${reason}`);
  };
  return {
    "chat.headers": async (_input, output) => {
      output.headers[GUARD_HEADER] = GUARD_VALUE;
    },
    "tool.execute.before": async (input, output) => {
      const args = output?.args || {};
      const unattended = process.env.FO4SF_UNATTENDED === "1";
      // run-lead.ps1 sets FO4SF_UNATTENDED=1. In those runs the Lead may not hand work to fo4-implement, which can edit
      // code and run the tests it edited; the prompt already says so, and this makes it hold without the prompt.
      // OpenCode looks a subagent up by its exact name, so an exact compare covers every way to start it.
      if (unattended && input.tool === "task" && args.subagent_type === "fo4-implement") {
        throw new Error("guard refused the command: unattended runs do not delegate to fo4-implement");
      }
      if (WRITE_TOOLS.has(input.tool)) return ask({ root, directory, write: writtenPaths(args) });
      // The shell tool is "bash" in OpenCode 1.18.35, for PowerShell too. Other tools with a "command" argument (task
      // records the slash command that started it) are not shell calls.
      if (input.tool !== "bash") {
        if (BUILT_IN.has(input.tool)) return;
        throw new Error(`guard refused the command: the tool ${JSON.stringify(input.tool)} is not one the guard knows`);
      }
      // The working-directory argument's name is not pinned across OpenCode versions, so check whichever one is set.
      const workdir = args.workdir ?? args.cwd ?? args.dir ?? args.directory;
      // terminal.ps1 sets FO4SF_OWNER_PRESENT=1 for the owner's own terminal; an unattended run never counts as one.
      const owner_present = process.env.FO4SF_OWNER_PRESENT === "1" && !unattended;
      return ask({ root, directory, command: args.command, workdir, owner_present });
    },
  };
};

export default Fo4Guard;
