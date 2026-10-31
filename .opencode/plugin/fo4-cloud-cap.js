// Holds what the local team spends on Claude (the anthropic provider in opencode.json, on the owner's API key) to
// tools/ai-team/config.json's cloud.monthly_cap_usd, and keeps it to the owner's terminal (OpenCode 1.18.35, read from
// its code). OpenCode prices each step from its own model list, adds the step's cost to the assistant message and
// publishes the message (message.updated, info.cost so far, info.providerID); the plugin adds what each update grew by
// to this month's tally (UTC) in the team's state folder, outside the repo, which every OpenCode window shares.
// Before each model request OpenCode calls chat.params; for an anthropic model the plugin throws there, so the request
// fails before it is sent, when the session is not the owner's terminal (FO4SF_OWNER_PRESENT is set only by
// terminal.ps1, FO4SF_UNATTENDED by run-lead.ps1), when this month's tally has reached the cap, or when the cap or the
// tally cannot be read or written. Not counted: a session title OpenCode writes with a small model (not a message), and
// a message's cost from before this OpenCode started is counted again if the message grows (more, never less). A
// request already running when the cap is reached finishes. The spend limit the owner sets in the Anthropic Console
// for the key's workspace is the hard cap behind this one. The local models (provider guardian) are never touched.

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
    if (t?.month !== month()) return 0;
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
