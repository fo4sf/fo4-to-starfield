"""The controller lease (docs/ai/leader-core.md §1 and §6, task T2): who may send input to the game, until when.

One file beside the ledger, <leader dir>/controller.json, is the lease the scripts read (cycle.ps1 and watchdog.ps1
through scripts/game/lease.py); every claim, renewal and release is first appended to the ledger as a
controller_claimed / controller_renewed / controller_released event (state.fold reads those), then the file is
replaced atomically. The ledger is the record and the file its cache: a crash between the two writes leaves the event
in the ledger and the file behind, never the other way round.

Rules (leader-core.md §1): a lease is held until it expires; one that expired without a release is `ambiguous`, and
nothing that sends input runs on it; another owner's claim is refused while a lease is held or ambiguous unless it is
forced with a reason (the reason goes into the ledger); the holder renews while held and may re-claim its own expired
lease (the gap is recorded); only the holder releases, unless forced. Every timestamp is aware UTC.

Nothing here touches the game. Whether a script consults the lease at all is the opt-in switch of leader-core.md §6
(FO4SF_LEASE_DIR); unset, the scripts behave as they did before this module existed.
"""
import argparse
import datetime
import json
import os
from dataclasses import asdict, dataclass

from .model import Event, now_iso, parse_iso
from .state import Ledger

LEASE_FILE = "controller.json"
LEDGER_FILE = "ledger.jsonl"
DEFAULT_TTL_S = 3600


class LeaseRefused(Exception):
    """A claim, renewal or release the rules refuse; str(e) is the reason."""


@dataclass
class Lease:
    owner: str
    purpose: str
    claimed: str                 # aware UTC iso
    expires: str
    ttl_s: int = DEFAULT_TTL_S
    renewed: str = None
    released: str = None
    forced: bool = False
    reason: str = ""

    def status(self, now=None):
        """'held' | 'released' | 'ambiguous' (expired without a release: nothing may send input on it)."""
        if self.released:
            return "released"
        if parse_iso(self.expires) <= parse_iso(now or now_iso()):
            return "ambiguous"
        return "held"

    def last_activity(self):
        return max((x for x in (self.claimed, self.renewed, self.released) if x), key=parse_iso)

    def to_json(self):
        return json.dumps(asdict(self), sort_keys=True, indent=1)

    @classmethod
    def from_json(cls, text):
        d = json.loads(text)
        if not isinstance(d, dict) or not all(d.get(k) for k in ("owner", "purpose", "claimed", "expires")):
            raise ValueError("not a lease: owner, purpose, claimed and expires are required")
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class Controller:
    def __init__(self, leader_dir, by=None):
        self.dir = os.path.abspath(leader_dir)
        self.lease_path = os.path.join(self.dir, LEASE_FILE)
        self.ledger = Ledger(os.path.join(self.dir, LEDGER_FILE))
        self.by = by or "controller"

    def read(self):
        """The lease on disk, None when there is none. An unreadable file raises ValueError; the gate treats that as
        ambiguous (nothing runs on a lease that cannot be read)."""
        if not os.path.exists(self.lease_path):
            return None
        with open(self.lease_path, encoding="utf-8") as f:
            return Lease.from_json(f.read())

    def status(self, now=None):
        lease = self.read()
        return "none" if lease is None else lease.status(now)

    def _write(self, event, lease):
        self.ledger.append(event)                                   # the record first
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.lease_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(lease.to_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.lease_path)                            # then the cache, atomically
        return lease

    def claim(self, owner, purpose, ttl_s=DEFAULT_TTL_S, now=None, force=False, reason=""):
        if not owner or not purpose:
            raise LeaseRefused("a claim names its owner and its purpose")
        if int(ttl_s) <= 0:
            raise LeaseRefused("the lease's ttl is a positive number of seconds")
        if force and not reason.strip():
            raise LeaseRefused("a forced claim needs a reason: it goes into the ledger")
        now = now or now_iso()
        current = self.read()
        st = "none" if current is None else current.status(now)
        fields = {"owner": owner, "purpose": purpose, "ttl_s": int(ttl_s), "forced": bool(force)}
        if st == "held" and current.owner != owner:
            if not force:
                raise LeaseRefused(f"held by {current.owner} until {current.expires} for {current.purpose}")
            fields.update(previous_owner=current.owner, previous_expires=current.expires, reason=reason)
        elif st == "ambiguous":
            gap = int((parse_iso(now) - parse_iso(current.expires)).total_seconds())
            if current.owner != owner and not force:
                raise LeaseRefused(f"ambiguous: {current.owner}'s lease expired {current.expires} without a release "
                                   f"({gap} s ago); {current.owner} releases it, or claim with --force and a reason")
            fields.update(previous_owner=current.owner, expired_for_s=gap, reason=reason)
        elif st == "held":                                          # the holder claims again: its own lease replaced
            fields["previous_expires"] = current.expires
        expires = (parse_iso(now) + datetime.timedelta(seconds=int(ttl_s))).isoformat()
        lease = Lease(owner=owner, purpose=purpose, claimed=now, expires=expires, ttl_s=int(ttl_s),
                      forced=bool(force), reason=reason)
        return self._write(Event("controller_claimed", self.by, t=now, fields=dict(fields, expires=expires)), lease)

    def renew(self, owner, ttl_s=None, now=None):
        now = now or now_iso()
        current = self.read()
        st = "none" if current is None else current.status(now)
        if st != "held" or current.owner != owner:
            raise LeaseRefused(self._not_held(current, st, owner))
        ttl = int(ttl_s or current.ttl_s or DEFAULT_TTL_S)
        expires = (parse_iso(now) + datetime.timedelta(seconds=ttl)).isoformat()
        lease = Lease(**dict(asdict(current), expires=expires, renewed=now, ttl_s=ttl))
        return self._write(Event("controller_renewed", self.by, t=now, fields={"owner": owner, "expires": expires}), lease)

    def release(self, owner, now=None, force=False, reason=""):
        now = now or now_iso()
        current = self.read()
        st = "none" if current is None else current.status(now)
        if st in ("none", "released"):
            raise LeaseRefused(self._not_held(current, st, owner))
        if current.owner != owner:
            if not force:
                raise LeaseRefused(f"held by {current.owner}, not {owner}: only the holder releases, or --force with a reason")
            if not reason.strip():
                raise LeaseRefused("a forced release needs a reason: it goes into the ledger")
        lease = Lease(**dict(asdict(current), released=now))
        ev = Event("controller_released", self.by, t=now, fields={
            "owner": current.owner, "released_by": owner, "forced": current.owner != owner, "reason": reason})
        return self._write(ev, lease)

    def valid_for(self, owner, now=None):
        """None while `owner` holds an unexpired lease; else the reason nothing may send input in that name."""
        try:
            current = self.read()
            st = "none" if current is None else current.status(now)
        except ValueError as e:
            return f"lease file unreadable ({e}): treated as ambiguous"
        if st == "held" and current.owner == owner:
            return None
        return self._not_held(current, st, owner)

    @staticmethod
    def _not_held(current, st, owner):
        if st == "none":
            return "no lease: claim one first"
        if st == "released":
            return f"released by {current.owner} at {current.released}: claim one first"
        if st == "ambiguous":
            return f"ambiguous: {current.owner}'s lease expired {current.expires} without a release"
        return f"held by {current.owner} until {current.expires} for {current.purpose}, not by {owner}"


def main(argv=None):
    """lease.py <command> --dir <leader folder> ...; exit 0 ok, 1 refused or not valid, 2 usage."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dir", required=True, help="the leader folder: ledger.jsonl and controller.json live there")
    common.add_argument("--by", default="", help="who writes the ledger events (default: the owner given, else lease)")
    ap = argparse.ArgumentParser(prog="lease.py", description="the controller lease (docs/ai/leader-core.md section 6)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("claim", parents=[common], help="claim the lease (refused while someone else holds one)")
    c.add_argument("--owner", required=True)
    c.add_argument("--purpose", required=True)
    c.add_argument("--ttl", type=int, default=DEFAULT_TTL_S, help=f"seconds until it expires (default {DEFAULT_TTL_S})")
    c.add_argument("--force", action="store_true", help="take an expired or held lease; needs --reason")
    c.add_argument("--reason", default="")
    r = sub.add_parser("renew", parents=[common], help="extend the holder's lease")
    r.add_argument("--owner", required=True)
    r.add_argument("--ttl", type=int, default=None, help="seconds from now (default: the lease's own ttl)")
    d = sub.add_parser("release", parents=[common], help="release the lease (the holder, or --force with --reason)")
    d.add_argument("--owner", required=True)
    d.add_argument("--force", action="store_true")
    d.add_argument("--reason", default="")
    s = sub.add_parser("status", parents=[common], help="print the lease; --require OWNER exits 0 only while OWNER holds it")
    s.add_argument("--require", metavar="OWNER", default="")
    s.add_argument("--json", action="store_true", help="one JSON line: status, lease, last_activity, dir")
    a = ap.parse_args(argv)
    ctl = Controller(a.dir, by=a.by or getattr(a, "owner", "") or "lease")
    try:
        if a.cmd == "claim":
            lease = ctl.claim(a.owner, a.purpose, a.ttl, force=a.force, reason=a.reason)
            print(f"claimed by {lease.owner} until {lease.expires}: {lease.purpose}")
        elif a.cmd == "renew":
            lease = ctl.renew(a.owner, a.ttl)
            print(f"renewed for {lease.owner} until {lease.expires}")
        elif a.cmd == "release":
            lease = ctl.release(a.owner, force=a.force, reason=a.reason)
            print(f"released: {lease.owner}'s lease at {lease.released}")
        else:
            try:
                lease = ctl.read()
                st = "none" if lease is None else lease.status()
            except ValueError as e:
                lease, st = None, f"unreadable: {e}"
            if a.json:
                print(json.dumps({"status": st, "lease": asdict(lease) if lease else None,
                                  "last_activity": lease.last_activity() if lease else None, "dir": ctl.dir},
                                 sort_keys=True))
            else:
                print(f"{st}" if lease is None else f"{st}: {lease.owner} until {lease.expires} for {lease.purpose}")
            if a.require:
                why = ctl.valid_for(a.require)
                if why:
                    print(f"not valid for {a.require}: {why}")
                    return 1
                print(f"valid for {a.require} until {lease.expires}")
        return 0
    except LeaseRefused as e:
        print(f"refused: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
