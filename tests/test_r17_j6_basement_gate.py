"""Round 17 J6 tests:
1. Basement security gate resolved dynamically via terminal XLKR (GetLinkedRef), never hardcoded as primary.
2. Terminal 0x00E35E never registers OnLockStateChanged (and defensively unregisters it).
3. OnLockStateChanged NEVER calls TryOpenS6BasementGate, Lock, Unlock, SetLockLevel, or SetOpen; 10 queued
   OnLockStateChanged events advance stage 45 at most once.
4. Terminal & Bobby Pin routes make at most ONE Lock(False, False, False) call, zero Unlock(), zero SetLockLevel(),
   zero SetOpen(True), zero terminal lock calls, and log `s6 basement_gate unlocked reason=terminal|lockpick`.
5. Fusion Core pickup is order-independent: taking the core BEFORE stage 45 auto-completes obj 90 and shows obj 95
   as soon as the basement gate opens (stage 45 -> stage 50).
"""
import os
from pathlib import Path
import unittest
from types import SimpleNamespace

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)
MIN00_PSC = os.path.join(REPO, "scripts", "mission", "FO4SF_Min00Quest.psc")

import sys
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)
import test_mission  # noqa: E402


class _LockableRef:
    def __init__(self, label, *, locked=True, linked=None, event_queue=None):
        self.label = label
        self.locked = bool(locked)
        self.linked = linked
        self.blocked = None
        self.lock_calls = []
        self.unlock_calls = []
        self.set_lock_level_calls = []
        self.set_open_calls = []
        self.event_queue = event_queue if event_queue is not None else []

    def GetLinkedRef(self, _kw=None):
        return self.linked

    def IsLocked(self):
        return self.locked

    def BlockActivation(self, abBlocked=True, abHide=False):
        self.blocked = (bool(abBlocked), bool(abHide))

    def Lock(self, abLock=True, abAsOwner=False, abTraverseLinkedLockables=True):
        self.lock_calls.append((bool(abLock), bool(abAsOwner), bool(abTraverseLinkedLockables)))
        self.locked = bool(abLock)
        # Starfield queues OnLockStateChanged AFTER Lock() completes; traversal also queues on linked ref
        self.event_queue.append(self)
        if abTraverseLinkedLockables and self.linked is not None:
            self.event_queue.append(self.linked)

    def Unlock(self, abAsOwner=False):
        self.unlock_calls.append(bool(abAsOwner))
        self.Lock(False, abAsOwner, True)

    def SetLockLevel(self, aiLockLevel):
        self.set_lock_level_calls.append(int(aiLockLevel))

    def SetOpen(self, abOpen=True):
        self.set_open_calls.append(bool(abOpen))


class J6BasementGateTests(unittest.TestCase):
    def _build_env(self, *, initial_stage=40, gate_locked=True, has_bobby_pin=True, has_fusion_core=False):
        psc_src = Path(MIN00_PSC).read_text(encoding="utf-8")
        event_queue = []
        gate = _LockableRef("Gate_00EDF0", locked=gate_locked, event_queue=event_queue)
        term = _LockableRef("Term_00E35E", locked=True, linked=gate, event_queue=event_queue)
        gate.linked = term
        bobby_pin = object()
        fusion_core = object()
        player = SimpleNamespace(
            items={bobby_pin: 1 if has_bobby_pin else 0, fusion_core: 1 if has_fusion_core else 0},
            GetItemCount=lambda item: player.items.get(item, 0),
        )
        registered = []
        unregistered = []
        stages_set = []
        objectives_done = []
        objectives_disp = []
        logs = []
        displayed_set = set()

        def lookup_form(fid, plg):
            if (fid, plg) == (0x00E35E, "FO4Port.esm"):
                return term
            if (fid, plg) == (0x00EDF0, "FO4Port.esm"):
                return gate
            if (fid, plg) == (0x0008A5, "FO4SFCoreValues.esm"):
                return bobby_pin
            if (fid, plg) == (0x000809, "FO4SFPowerArmor.esm"):
                return fusion_core
            return None

        ns = {
            "EnableS6ToS9Full": True,
            "KeeperOnly": False,
            "StopAtFusionCorePowerArmor": True,
            "BobbyPinId": 0x0008A5,
            "SturgesRef": None,
            "s6RoomEventsRegistered": False,
            "s6FullStage": initial_stage,
            "applied": initial_stage,
            "s6BasementUnlockedPending": False,
            "s6BasementGateOpening": False,
            "s6FusionCorePickedPending": False,
            "obj90DisplayedOnce": False,
            "obj95DisplayedOnce": False,
            "Trace": logs.append,
            "LookupOptionalForm": lookup_form,
            "ResolveActivePrestonScene": lambda *a: None,
            "RegisterForRemoteEvent": lambda obj, ev: registered.append((obj, str(ev))),
            "UnregisterForRemoteEvent": lambda obj, ev: unregistered.append((obj, str(ev))),
            "Debug": SimpleNamespace(Notification=lambda *a: None),
            "IsTestModeEnabled": lambda: False,
            "EffectiveStage": lambda: ns["s6FullStage"],
            "SetStage": lambda st: stages_set.append(int(st)),
            "SetObjectiveCompleted": lambda obj: objectives_done.append(int(obj)),
            "IsObjectiveDisplayed": lambda obj: int(obj) in displayed_set,
            "SetObjectiveDisplayed": lambda obj, disp=True, force=False: (
                objectives_disp.append((int(obj), bool(disp), bool(force))),
                displayed_set.add(int(obj)) if disp else displayed_set.discard(int(obj)),
            ),
            "SetActive": lambda *_a: None,
            "Game": SimpleNamespace(GetPlayer=lambda: player),
        }

        import re
        wrapped = psc_src
        ev_act = re.search(r"Event ObjectReference\.OnActivate\((.*?)\)\n(.*?)EndEvent", wrapped, re.S)
        ev_lock = re.search(r"Event ObjectReference\.OnLockStateChanged\((.*?)\)\n(.*?)EndEvent", wrapped, re.S)
        wrapped += (
            f"\nFunction OnActivateEv({ev_act[1]})\n{ev_act[2]}EndFunction\n"
            f"\nFunction OnLockStateEv({ev_lock[1]})\n{ev_lock[2]}EndFunction\n"
        )
        code = test_mission._translate_mission_psc(
            wrapped,
            (
                "RegisterS6RoomEvents", "PlayerHasBobbyPin", "PlayerHasFusionCore",
                "ResolveS6BasementGate", "RecordS6BasementGateUnlocked",
                "AdvanceS6BasementGateOpened", "AdvanceS6FusionCorePicked",
                "TryOpenS6BasementGate", "OnActivateEv", "OnLockStateEv",
            ),
            ("s6RoomEventsRegistered", "s6FullStage", "applied", "s6BasementUnlockedPending",
             "s6BasementGateOpening", "s6FusionCorePickedPending", "obj90DisplayedOnce", "obj95DisplayedOnce"),
        )
        exec(compile(code, MIN00_PSC, "exec"), ns)
        return SimpleNamespace(
            ns=ns, term=term, gate=gate, player=player, bobby_pin=bobby_pin, fusion_core=fusion_core,
            event_queue=event_queue, registered=registered, unregistered=unregistered,
            stages_set=stages_set, objectives_done=objectives_done, objectives_disp=objectives_disp, logs=logs,
        )

    def test_terminal_registration_and_single_lock_call_plus_10_queued_events(self):
        env = self._build_env(initial_stage=40, gate_locked=True)
        ns = env.ns
        ns["RegisterS6RoomEvents"]()
        self.assertIn((env.term, "OnActivate"), env.registered)
        self.assertNotIn((env.term, "OnLockStateChanged"), env.registered)
        self.assertIn((env.term, "OnLockStateChanged"), env.unregistered)
        self.assertIn((env.gate, "OnLockStateChanged"), env.registered)

        # Activate terminal -> calls TryOpenS6BasementGate("terminal") -> one Lock(False, False, False) on linked gate
        ns["OnActivateEv"](env.term, env.player)
        self.assertEqual(env.gate.lock_calls, [(False, False, False)])
        self.assertEqual(env.gate.unlock_calls, [])
        self.assertEqual(env.gate.set_lock_level_calls, [])
        self.assertEqual(env.gate.set_open_calls, [])
        self.assertEqual(env.term.lock_calls, [])
        self.assertEqual(env.term.unlock_calls, [])
        self.assertEqual(env.term.set_lock_level_calls, [])
        self.assertIn("s6 basement_gate unlocked reason=terminal", env.logs)
        self.assertEqual(env.stages_set, [45])

        # Deliver queued event + 10 extra synthetic lock-state events -> ZERO TryOpen/Lock calls, stage set ONLY once
        for sender in list(env.event_queue) + [env.gate] * 10 + [env.term] * 5:
            ns["OnLockStateEv"](sender)
        self.assertEqual(env.gate.lock_calls, [(False, False, False)])
        self.assertEqual(env.stages_set, [45])
        self.assertIn((env.gate, "OnLockStateChanged"), env.unregistered)

    def test_bobby_pin_route_makes_one_lock_call_and_logs_lockpick(self):
        env = self._build_env(initial_stage=40, gate_locked=True, has_bobby_pin=True)
        env.ns["OnActivateEv"](env.gate, env.player)
        self.assertEqual(env.gate.lock_calls, [(False, False, False)])
        self.assertEqual(env.gate.unlock_calls, [])
        self.assertEqual(env.gate.set_lock_level_calls, [])
        self.assertEqual(env.gate.set_open_calls, [])
        self.assertEqual(env.gate.blocked, (False, False))
        self.assertIn("s6 basement_gate unlocked reason=lockpick", env.logs)
        self.assertEqual(env.stages_set, [45])

    def test_fusion_core_picked_before_gate_stage_advances_stage50_on_gate_open(self):
        env = self._build_env(initial_stage=40, gate_locked=True, has_fusion_core=True)
        # Pick up core BEFORE gate opens (s6FullStage == 40 < 45)
        self.assertTrue(env.ns["AdvanceS6FusionCorePicked"]())
        self.assertTrue(env.ns["s6FusionCorePickedPending"])
        self.assertEqual(env.stages_set, [])
        # Unlock gate via terminal -> stage 45 immediately cascades into stage 50 + obj 90 done + obj 95 shown
        env.ns["TryOpenS6BasementGate"]("terminal")
        self.assertEqual(env.stages_set, [45, 50])
        self.assertIn(87, env.objectives_done)
        self.assertIn(90, env.objectives_done)
        self.assertIn((95, True, False), env.objectives_disp)


if __name__ == "__main__":
    unittest.main()
