"""The deployment gate (docs/ai/leader-core.md §7; the owner's brief §7; task T3): before any live task every check
is PASS, or the gate refuses and the ledger says why.

Pure Python: the checks read nothing themselves. A *probe* object supplies the readings (the runner's PreflightProbe
in scripts/game/testqueue.py reads the PC; the tests use a fake), so the Windows-only parts (Plugins.txt under
%LOCALAPPDATA%, Starfield.exe's version, the Saves folder, the ini files, the Guardian database) stay in the adapter.
A reading the probe cannot give is UNKNOWN, and UNKNOWN refuses exactly like FAIL ("any unknown → refuse").

The probe interface (every method may raise; the gate turns an exception into UNKNOWN for that check):
  queue, state                       the queue.json and state.json dicts
  staged_plugin_sha256()             sha256 of the staged FO4Port.esm, None when it is not there
  deploy_manifest()                  Data/FO4Port.deploy.json as a dict, None when nothing is deployed
  experiment_inputs(exp_dir, plugins)  exp_install.source_inventory of the staged experiment
  install_record()                   Data/FO4SFExp.install.json as {exp_dir, plugins, source_inputs, complete}, None when absent
  plugins_txt_lines()                the lines of Plugins.txt ([] when the file does not exist yet), None when it cannot be located
  plugin_masters(name)               the masters of a staged experiment plugin (TES4 MAST)
  implicit(name)                     True for a plugin the game loads on its own (Starfield.esm, SFBGS*, ...)
  game_version()                     Starfield.exe's file version, None when unreadable
  ledger_game_version()              the game_version of the ledger's current build pin, None when none
  lease_status()                     ("ok", detail) | ("fail", why) | ("unknown", why)
  stop_dirs()                        [(stop file path, folder exists, folder writable), ...]
  guardian()                         (mode: running|paused|stopped|unreadable|missing, database path)
  save_present(name)                 True / False, None when the Saves folder is not there
  ini_texts()                        the texts of the ini files that exist (StarfieldCustom.ini in My Games, Starfield.ini)
"""
import os
import re
from dataclasses import dataclass, field

from .model import Event

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"
CHECKS = ("pin", "deploy", "experiment", "plugins_active", "load_order", "game_version", "lease", "stop_controls",
          "guardian", "recovery_save", "log_capture")
DEPLOY_PLUGIN = "FO4Port.esm"
BRIDGE_PLUGIN = "FO4SFBridge.esm"
PAPYRUS_KEYS = (("bEnableLogging", "1"), ("bEnableTrace", "1"), ("bLoadDebugInformation", "1"))   # make_bridge.py


@dataclass
class Check:
    name: str
    status: str
    detail: str
    expected: object = None
    observed: object = None

    def line(self):
        return f"{self.status:7} {self.name}: {self.detail}"


@dataclass
class Report:
    checks: list = field(default_factory=list)

    @property
    def ok(self):
        return bool(self.checks) and all(c.status == PASS for c in self.checks)

    @property
    def failing(self):
        return [c for c in self.checks if c.status != PASS]

    def lines(self):
        head = "preflight: " + ("every check passed" if self.ok
                                else "REFUSED: " + ", ".join(f"{c.name} {c.status}" for c in self.failing))
        return [head] + ["  " + c.line() for c in self.checks]

    def blocker_event(self, by):
        """The ledger line a refusal leaves: which checks failed, with their reasons as the evidence."""
        return Event("blocker_opened", by, fields={
            "blocker": "preflight", "owner": by, "evidence": [c.line() for c in self.failing],
            "checks": {c.name: c.status for c in self.checks}})


def _name(line):
    return line.strip().lstrip("*").strip().casefold()


def _active(line):
    return line.strip().startswith("*")


def papyrus_logging_on(text):
    """True when the [Papyrus] section of an ini text sets every key the bridge's user log needs (make_bridge.py ini)."""
    section, got = False, {}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s.casefold() == "[papyrus]"
            continue
        if section:
            m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m:
                got[m.group(1).casefold()] = m.group(2)
    return all(got.get(k.casefold()) == v for k, v in PAPYRUS_KEYS)


# ---------------------------------------------------------------------------------------------------- the checks
def check_pin(p):
    want = (p.queue or {}).get("plugin_sha256")
    if not want:
        return Check("pin", UNKNOWN, "the queue pins no plugin_sha256")
    got = p.staged_plugin_sha256()
    if not got:
        return Check("pin", UNKNOWN, f"staged {DEPLOY_PLUGIN} not found under {p.queue.get('staging')!r}", want)
    if got != want:
        return Check("pin", FAIL, f"staged {DEPLOY_PLUGIN} is {got[:8]}, the queue pinned {want[:8]}", want, got)
    return Check("pin", PASS, f"staged {DEPLOY_PLUGIN} is the pinned build {want[:8]}", want, got)


def check_deploy(p):
    want = (p.queue or {}).get("plugin_sha256") or ""
    man = p.deploy_manifest()
    if man is None:
        return Check("deploy", PASS, "nothing deployed: cycle.ps1 deploys the pinned staging at the launch")
    if man.get("complete") is not True:
        return Check("deploy", FAIL, "an interrupted install sits in the game folder (deploy_starfield.py uninstall first)")
    got = ((man.get("artifacts") or {}).get(DEPLOY_PLUGIN) or {}).get("sha256")
    if not got:
        return Check("deploy", UNKNOWN, f"the deploy manifest carries no sha256 for {DEPLOY_PLUGIN}")
    if want and got != want:
        return Check("deploy", FAIL, f"deployed {DEPLOY_PLUGIN} is {got[:8]}, the queue pinned {want[:8]} (a running game "
                                     f"on it would be judged as the wrong build: uninstall, or launch fresh)", want, got)
    return Check("deploy", PASS, f"deployed {DEPLOY_PLUGIN} is the pinned build {got[:8]}", want, got)


def check_experiment(p):
    q = p.queue or {}
    pin = q.get("experiment_identity")
    if not pin:
        if q.get("pre_launch"):
            return Check("experiment", UNKNOWN, "the queue installs an experiment (pre_launch) but pins no "
                                                "experiment_identity: nothing can verify what gets installed")
        return Check("experiment", PASS, "no experiment: the pinned build alone")
    now = p.experiment_inputs(pin["exp_dir"], pin["plugins"])
    if now != pin["inputs"]:
        diff = sorted(k for k in set(now) | set(pin["inputs"]) if now.get(k) != pin["inputs"].get(k))
        return Check("experiment", FAIL, f"staged experiment {pin['exp_dir']} changed since planning: {diff[:5]}")
    rec = p.install_record()
    if rec is None:
        return Check("experiment", PASS, f"staged experiment unchanged since planning; installed at the launch "
                                         f"({len(pin['plugins'])} plugin(s))")
    if rec.get("error"):
        return Check("experiment", UNKNOWN, f"install record unreadable: {rec['error']}")
    if rec.get("complete") is not True:
        return Check("experiment", FAIL, "the experiment install record is incomplete (exp_install.py uninstall first)")
    if os.path.normcase(os.path.abspath(rec.get("exp_dir") or "")) != os.path.normcase(os.path.abspath(pin["exp_dir"])):
        return Check("experiment", FAIL, f"installed experiment {rec.get('exp_dir')!r} is not the pinned {pin['exp_dir']!r}")
    if [str(x).casefold() for x in rec.get("plugins") or []] != [x.casefold() for x in pin["plugins"]]:
        return Check("experiment", FAIL, f"installed plugins {rec.get('plugins')} are not the pinned {pin['plugins']}")
    if (rec.get("source_inputs") or {}) != pin["inputs"]:
        return Check("experiment", FAIL, "the installed experiment's inputs are not the pinned ones (re-install)")
    return Check("experiment", PASS, "staged and installed experiment are the pinned one")


def _planned_plugins(p):
    q = p.queue or {}
    pin = q.get("experiment_identity") or {}
    plugins = list(pin.get("plugins") or [])
    if not plugins:
        rec = p.install_record()
        if rec and not rec.get("error"):
            plugins = list(rec.get("plugins") or [])
    return plugins


def check_plugins_active(p):
    lines = p.plugins_txt_lines()
    if lines is None:
        return Check("plugins_active", UNKNOWN, "Plugins.txt cannot be located (LOCALAPPDATA)")
    wanted = _planned_plugins(p) + [DEPLOY_PLUGIN] + ([BRIDGE_PLUGIN] if (p.queue or {}).get("bridge") else [])
    inactive, dup, later, active = [], [], [], []
    for name in wanted:
        at = [ln for ln in lines if _name(ln) == name.casefold()]
        if len(at) > 1:
            dup.append(name)
        elif not at:
            later.append(name)
        elif not _active(at[0]):
            inactive.append(name)
        else:
            active.append(name)
    if inactive or dup:
        why = []
        if inactive:
            why.append(f"inactive in Plugins.txt: {', '.join(inactive)} (Starfield deactivated them on a load? "
                       f"exp_install.py active / cycle.ps1 exit 8)")
        if dup:
            why.append(f"duplicated in Plugins.txt: {', '.join(dup)}")
        return Check("plugins_active", FAIL, "; ".join(why), wanted, lines)
    return Check("plugins_active", PASS, f"active now: {', '.join(active) or 'none'}; installed at the launch: "
                                         f"{', '.join(later) or 'none'}", wanted, lines)


def check_load_order(p):
    lines = p.plugins_txt_lines()
    if lines is None:
        return Check("load_order", UNKNOWN, "Plugins.txt cannot be located (LOCALAPPDATA)")
    plugins = _planned_plugins(p)
    pos = {_name(ln): k for k, ln in enumerate(lines) if _active(ln)}
    missing, reorder = [], []
    for name in plugins:
        for m in p.plugin_masters(name):
            if p.implicit(m):
                continue
            if m.casefold() not in pos:
                if m.casefold() == DEPLOY_PLUGIN.casefold() and DEPLOY_PLUGIN.casefold() not in pos:
                    continue                              # the deploy at the launch activates it; order moves it after
                missing.append(f"{name} needs {m}")
            elif name.casefold() in pos and pos[m.casefold()] > pos[name.casefold()]:
                reorder.append(f"{name} before its master {m}")
    if missing:
        return Check("load_order", FAIL, "master neither active nor implicit: " + "; ".join(missing) +
                     " (cycle.ps1 would exit 7)", plugins, lines)
    notes = []
    if reorder:
        notes.append("exp_install.py order moves at the launch: " + "; ".join(reorder))
    if (p.queue or {}).get("bridge") and BRIDGE_PLUGIN.casefold() in pos and pos[BRIDGE_PLUGIN.casefold()] != max(pos.values()):
        notes.append("the bridge is not last: bridge_install.py order moves it at the launch")
    order = [_name(ln) for ln in lines if _active(ln)]
    idx = (p.queue or {}).get("plugin_index")
    return Check("load_order", PASS, f"active order now: {order or 'empty'}; planned index {idx!r} is not verified "
                                     f"against the game's implicit plugins (unresolved)" + ("; " + "; ".join(notes) if notes else ""),
                 plugins, order)


def check_game_version(p):
    want = (p.queue or {}).get("game_version") or p.ledger_game_version()
    if not want:
        return Check("game_version", UNKNOWN, 'no game version pinned: add "game_version" (Starfield.exe file version, '
                                              'e.g. 1.16.244.0) to queue.json or pin it in the ledger')
    got = p.game_version()
    if not got:
        return Check("game_version", UNKNOWN, "Starfield.exe's version is not readable here (Windows only)", want)
    if str(got).strip() != str(want).strip():
        return Check("game_version", FAIL, f"Starfield.exe is {got}, the pin is {want}", want, got)
    return Check("game_version", PASS, f"Starfield.exe is the pinned {want}", want, got)


def check_lease(p):
    st, detail = p.lease_status()
    return Check("lease", {"ok": PASS, "fail": FAIL}.get(st, UNKNOWN), detail)


def check_stop_controls(p):
    dirs = list(p.stop_dirs())
    if not dirs:
        return Check("stop_controls", UNKNOWN, "no STOP file locations known")
    bad = []
    for path, exists, writable in dirs[:2]:                   # the queue's STOP and the chain's STOP_ALL must work
        if not exists or not writable:
            bad.append(path)
    for path, exists, writable in dirs[2:]:                   # the state folder's, when the folder is there
        if exists and not writable:
            bad.append(path)
    if bad:
        return Check("stop_controls", FAIL, "a STOP file could not be created at: " + ", ".join(bad))
    return Check("stop_controls", PASS, "STOP files can be created at " + ", ".join(path for path, _, _ in dirs))


def check_guardian(p):
    mode, db = p.guardian()
    if mode == "running":
        return Check("guardian", PASS, f"Resource Guardian running ({db})")
    if mode == "missing":
        return Check("guardian", FAIL, f"Resource Guardian database not found at {db} (tools/ai-team guardian.py status)")
    if mode == "unreadable":
        return Check("guardian", FAIL, f"Resource Guardian database unreadable at {db}")
    return Check("guardian", FAIL, f"Resource Guardian mode {mode}")


def check_recovery_save(p):
    name = (p.queue or {}).get("save")
    if not name:
        return Check("recovery_save", UNKNOWN, "the queue names no dedicated save")
    present = p.save_present(name)
    if present is None:
        return Check("recovery_save", UNKNOWN, "the Saves folder is not there (My Games\\Starfield\\Saves)")
    if present:
        return Check("recovery_save", PASS, f"dedicated save {name} present")
    if (p.state or {}).get("save_file") is True:
        return Check("recovery_save", FAIL, f"dedicated save {name} was created by an earlier run and is gone")
    return Check("recovery_save", PASS, f"dedicated save {name} not there yet: created on the first launch")


def check_log_capture(p):
    if not (p.queue or {}).get("bridge"):
        return Check("log_capture", PASS, "no bridge pinned: reads go through the console capture")
    texts = list(p.ini_texts())
    if not texts:
        return Check("log_capture", UNKNOWN, "no StarfieldCustom.ini or Starfield.ini found to check the [Papyrus] keys")
    if any(papyrus_logging_on(t) for t in texts):
        return Check("log_capture", PASS, "[Papyrus] logging keys set: the bridge's user log is written")
    keys = " ".join(f"{k}={v}" for k, v in PAPYRUS_KEYS)
    return Check("log_capture", FAIL, f"[Papyrus] {keys} missing from StarfieldCustom.ini and Starfield.ini "
                                      f"(scripts/bridge/make_bridge.py ini): the bridge's log would stay empty")


CHECK_FUNCS = {"pin": check_pin, "deploy": check_deploy, "experiment": check_experiment,
               "plugins_active": check_plugins_active, "load_order": check_load_order,
               "game_version": check_game_version, "lease": check_lease, "stop_controls": check_stop_controls,
               "guardian": check_guardian, "recovery_save": check_recovery_save, "log_capture": check_log_capture}


def run_gate(probe, names=CHECKS):
    """Every check, in order; a check that raises is UNKNOWN with the exception, never a crash of the caller."""
    rep = Report()
    for name in names:
        try:
            rep.checks.append(CHECK_FUNCS[name](probe))
        except Exception as e:                            # noqa: BLE001 (one broken reading must not hide the rest)
            rep.checks.append(Check(name, UNKNOWN, f"reading failed: {type(e).__name__}: {e}"))
    return rep
