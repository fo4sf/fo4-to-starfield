// Holds what the local team spends on Claude (the anthropic provider in opencode.json, on the owner's API key) to
// tools/ai-team/config.json's cloud.monthly_cap_usd, and keeps it to the owner's terminal (OpenCode 1.18.35, read from
// its code). OpenCode prices each step with the model's cost (opencode.json gives both Claude models theirs, which wins
// over OpenCode's model list: its built-in list has no Haiku 5.5, and an unpriced model costs 0), adds the step's cost
// to the assistant message and publishes the message (message.updated, info.cost so far, info.providerID); the plugin
// adds what each update grew by to this month's tally (UTC) in the team's state folder, outside the repo, which every
// OpenCode window shares. Before each model request OpenCode calls chat.params; for an anthropic model the plugin
// throws there, so the request fails before it is sent, when the session is not the owner's terminal
// (FO4SF_OWNER_PRESENT is set only by terminal.ps1, FO4SF_UNATTENDED by run-lead.ps1), when the model has no input or
// output price (it would count $0), when this month's tally has reached the cap, or when the cap or the tally cannot be
// read or written. The tally counts less than the bill in these cases: a session title OpenCode writes with a small
// model (not a message); a step stopped (Esc) or failed mid-stream (its cost is added only when it finishes); two
// windows finishing a step at the same instant (no lock: one update can be lost); a step whose tally write failed (it
// is not retried, and that window then refuses Claude until it restarts); `opencode agent create` (no chat.params).
// A message's cost from before this OpenCode started is counted again if the message grows (more, never less). Requests
// already running when the cap is reached finish: a Lead turn with three subagents can run many steps at once. The
// spend limit the owner sets in the Anthropic Console for the key's workspace is the hard cap behind this one. The
// local models (provider guardian) are never touched.

import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const PROVIDER = "anthropic";

function stateDir() {                     // as tools/ai-team/guardian/store.py
  return process.env.FO4_AI_TEAM_STATE ||
    path.join(process.env.LOCALAPPDATA || os.homedir(), "fo4-ai-team", "state");
}

const month = () => new Date().toISOString().slice(0, 7);

export const Fo4CloudCap = async ({ worktree, directory }) => {
  const root = worktree || directory;
  let cap = NaN;
  try {
    cap = JSON.parse(readFileSync(path.join(root, "tools", "ai-team", "config.json"), "utf8")).cloud.monthly_cap_usd;
  } catch {}
  const ledger = path.join(stateDir(), "cloud-spend.json");
  const seen = new Map();                 // assistant message id -> its cost already counted
  let broken = "";                        // why the tally cannot be trusted

  const spent = () => {                   // this month's tally in US dollars; throws when the file cannot be read
    if (!existsSync(ledger)) return 0;
    const t = JSON.parse(readFileSync(ledger, "utf8"));
    if (!/^\d{4}-\d{2}$/.test(t?.month)) throw new Error("no month in it");   // test() reads a number as text
    if (t.month > month()) throw new Error(`it is for ${t.month}, a later month: check the PC's clock`);
    if (t.month < month()) return 0;      // an earlier month: this one starts at 0
    if (typeof t.usd !== "number" || !Number.isFinite(t.usd) || t.usd < 0) throw new Error("no usd in it");
    return t.usd;
  };
  const add = (usd) => {
    const total = spent() + usd;
    mkdirSync(path.dirname(ledger), { recursive: true });
    const tmp = `${ledger}.${process.pid}.tmp`;
    writeFileSync(tmp, JSON.stringify({ month: month(), usd: total }));
    renameSync(tmp, ledger);
  };

  return {
    event: async ({ event }) => {
      if (event?.type !== "message.updated") return;
      const m = event.properties?.info;
      if (m?.role !== "assistant" || m.providerID !== PROVIDER || typeof m.cost !== "number") return;
      const grew = m.cost - (seen.get(m.id) ?? 0);
      if (!(grew > 0)) return;
      seen.set(m.id, m.cost);
      try {
        add(grew);
      } catch (err) {
        broken = `the tally ${ledger} could not be updated (${err.message})`;
      }
    },
    "chat.params": async (input) => {
      if (input?.model?.providerID !== PROVIDER) return;
      const no = (why) => { throw new Error(`fo4-cloud-cap refused the Claude request: ${why}`); };
      if (process.env.FO4SF_UNATTENDED === "1" || process.env.FO4SF_OWNER_PRESENT !== "1") {
        no("Claude runs only in the owner's terminal (FO4SF AI menu), never unattended");
      }
      if (!Number.isFinite(cap) || cap <= 0) {             // Number.isFinite is false for a string too
        no("no cloud.monthly_cap_usd in tools/ai-team/config.json");
      }
      const priced = (usd) => Number.isFinite(usd) && usd > 0;   // false for a missing, 0 or non-number price
      if (!priced(input.model.cost?.input) || !priced(input.model.cost?.output)) {
        no(`OpenCode has no price for ${input.model.id}, so its spend would count as $0 (opencode.json gives each ` +
           "Claude model its cost)");
      }
      if (broken) no(broken);
      let usd;
      try {
        usd = spent();
      } catch (err) {
        no(`the tally ${ledger} cannot be read (${err.message})`);
      }
      if (usd >= cap) {
        no(`this month's Claude spend is $${usd.toFixed(2)} of the $${cap} cap (tools/ai-team/config.json ` +
           "cloud.monthly_cap_usd); it starts again next month (UTC)");
      }
    },
  };
};

export default Fo4CloudCap;
