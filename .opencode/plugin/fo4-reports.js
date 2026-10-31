// Keeps a subagent's report when OpenCode compacts the subagent's session right after it (OpenCode 1.18.35, read from
// its code). OpenCode compacts a session once a step's tokens, its thinking included, reach the context minus the output
// limit (65536 - 32000 = 33,536 for the 35B), and it checks after a final answer too. It then writes a summary and, as
// there is no user message to replay, adds "Continue if you have next steps..." so the model answers once more. The
// task tool hands the Lead the newest text in the subagent's session: that answer, or with no "Continue" the summary,
// instead of the report. So when a subagent's session compacts after an answer that finished, this plugin turns the
// "Continue" off (the subagent stops at the summary, as it had stopped at its report) and puts the report back in the
// task tool's result. A compaction in the middle of a task, and any in the owner's own session, run as OpenCode makes
// them. A subagent session that the plugin did not see start (one resumed after OpenCode restarted) is left alone too.
//
// Events, from the plugin "event" hook: session.created / session.updated {info: session}, with info.parentID for a
// subagent's session; message.updated {info: message}, an assistant message with summary true for a compaction's
// summary and finish set once its step ends; message.part.updated {part}, a text part with its messageID, sessionID and
// text. The task tool's result has metadata.sessionId (the subagent's session) and the report inside <task_result>.

const CHILDREN = new Set();   // subagent sessions
const LAST = new Map();       // session -> {id, finish, text} of its newest assistant message that is not a summary
const KEPT = new Map();       // subagent session -> the report its compaction would have replaced

export const Fo4Reports = async () => ({
  event: async ({ event }) => {
    const p = event?.properties || {};
    if (event?.type === "session.created" || event?.type === "session.updated") {
      if (p.info?.id && p.info.parentID) CHILDREN.add(p.info.id);
    } else if (event?.type === "message.updated") {
      const m = p.info;
      if (m?.role !== "assistant" || m.summary) return;
      const last = LAST.get(m.sessionID);
      if (last?.id !== m.id) {
        LAST.set(m.sessionID, { id: m.id, finish: m.finish, text: undefined });
        KEPT.delete(m.sessionID);     // the subagent works again (a resumed task): an older report is not this one
      } else last.finish = m.finish;
    } else if (event?.type === "message.part.updated") {
      const part = p.part;
      const last = LAST.get(part?.sessionID);
      if (part?.type === "text" && last?.id === part.messageID && typeof part.text === "string") last.text = part.text;
    }
  },
  "experimental.compaction.autocontinue": async (input, output) => {
    const last = LAST.get(input?.sessionID);
    if (!CHILDREN.has(input?.sessionID) || input.overflow || last?.finish !== "stop" || !last.text) return;
    KEPT.set(input.sessionID, last.text);
    output.enabled = false;
  },
  "tool.execute.after": async (input, output) => {
    if (input?.tool !== "task" || typeof output?.output !== "string") return;
    const id = output.metadata?.sessionId;
    const report = KEPT.get(id);
    if (report === undefined) return;
    KEPT.delete(id);
    const open = output.output.indexOf("<task_result>");
    const close = output.output.lastIndexOf("</task_result>");
    if (open < 0 || close < open) return;
    output.output = output.output.slice(0, open + "<task_result>".length) + "\n" + report + "\n" +
      output.output.slice(close);
  },
});

export default Fo4Reports;
