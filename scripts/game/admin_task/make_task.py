"""Write the Task Scheduler definition of the owner's elevated test run (docs/testing/admin-task.md). It only writes an
XML file; the owner creates the task from it in an admin prompt, which is the one elevation they approve.

usage:
  python scripts/game/admin_task/make_task.py --user <DOMAIN\\user> --checkout <runner checkout> --python <python.exe>
         --campaign <campaign.json> --out <NEW task.xml>
  then, by the owner, in an elevated prompt:   schtasks /create /tn "FO4SF\\ElevatedRun" /xml <task.xml>
  started on demand only:                       schtasks /run /tn "FO4SF\\ElevatedRun"
  removed:                                      schtasks /delete /tn "FO4SF\\ElevatedRun" /f

The task has no trigger: it never starts on its own. It runs only while the user is logged on (an interactive token,
so the game shows on the user's desktop and the runner's input reaches it), with the highest privileges the user
has, one instance at a time, for at most 8 hours. Its only action is
  <python> scripts\\game\\campaign_arm.py run --campaign <campaign.json>
in <checkout>: the campaign check (caps, the installed set, holds), then each queue with one launch and a stop at the
first crash. Every path is fixed in the definition; a changed path needs a new definition and a new approval.
"""
import argparse
import os
import re
import sys
from xml.sax.saxutils import escape

TASK = "FO4SF\\ElevatedRun"
LIMIT = "PT8H"
SAFE = re.compile(r"[A-Za-z]:\\[A-Za-z0-9 _.\\()-]+")      # a plain absolute Windows path, nothing to quote or expand
USER = re.compile(r"[A-Za-z0-9_.-]+\\[A-Za-z0-9_. -]+")


def check(user, checkout, python, campaign):
    bad = []
    if not USER.fullmatch(user or ""):
        bad.append(f"--user {user!r}: want DOMAIN\\user (whoami)")
    for name, v in (("--checkout", checkout), ("--python", python), ("--campaign", campaign)):
        if not SAFE.fullmatch(v or "") or ".." in v.split("\\"):
            bad.append(f"{name} {v!r}: want a plain absolute path (letters, digits, space, _ . - ( ))")
    if python and not python.lower().endswith("\\python.exe"):
        bad.append(f"--python {python!r}: want a python.exe")
    if campaign and not campaign.lower().endswith(".json"):
        bad.append(f"--campaign {campaign!r}: want the campaign .json")
    return bad


def xml(user, checkout, python, campaign):
    args = f'scripts\\game\\campaign_arm.py run --campaign "{campaign}"'
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>fo4-to-starfield: one elevated test campaign, started on demand by the owner (campaign_arm.py run).</Description>
    <URI>\\{escape(TASK)}</URI>
  </RegistrationInfo>
  <Triggers />
  <Principals>
    <Principal id="Author">
      <UserId>{escape(user)}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>{LIMIT}</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(python)}</Command>
      <Arguments>{escape(args)}</Arguments>
      <WorkingDirectory>{escape(checkout)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--user", required=True)
    ap.add_argument("--checkout", required=True)
    ap.add_argument("--python", required=True)
    ap.add_argument("--campaign", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    bad = check(a.user, a.checkout, a.python, a.campaign)
    if bad:
        sys.exit("refused: " + "; ".join(bad))
    if os.path.exists(a.out):
        sys.exit(f"{a.out} exists: a new file only")
    with open(a.out, "w", encoding="utf-16", newline="\r\n") as f:   # schtasks /xml reads UTF-16 with a BOM
        f.write(xml(a.user, a.checkout, a.python, a.campaign))
    print(f"wrote {a.out}: task {TASK}, on demand only, highest privileges while {a.user} is logged on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
