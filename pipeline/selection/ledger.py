"""Local append-only, hash-chained manual selection ledger.

An operator's identity/review assertions are trusted local inputs, not remote
authentication. This ledger never publishes a forecast or modifies WP03 history.
Exclusive file locking and compare-and-swap heads serialize operator decisions.
"""

from __future__ import annotations

import fcntl
from datetime import UTC, datetime
from pathlib import Path

from pipeline.benchmark.artifacts import CONTRACT, digest, read_json, verify_lock, write_once
from pipeline.benchmark.promotion import review_gate
from pipeline.selection.outputs import HORIZONS


class Ledger:
    def __init__(self, root: Path):
        self.root = Path(root)

    def events(self):
        events = []
        previous = None
        for index, path in enumerate(sorted(self.root.glob("[0-9]*.json"))):
            event = read_json(path)
            body = {k: v for k, v in event.items() if k != "sha256"}
            if event["sequence"] != index or event["previous"] != previous or digest(body) != event["sha256"]:
                raise ValueError("selection ledger integrity failure")
            previous = event["sha256"]
            events.append(event)
        return events

    def snapshot(self):
        state = {"models": {}, "active": {}, "history": {}, "approvals": {}, "head": None}
        for e in self.events():
            payload, action = e["payload"], e["action"]
            identity = payload["identity"]
            if action in {"register", "bootstrap"}:
                state["models"][identity] = {**payload, "state": "champion" if action == "bootstrap" else "proposed"}
            elif action == "challenge":
                state["models"][identity]["state"] = "challenger"
            elif action == "approve":
                state["approvals"][identity] = payload
            if action in {"bootstrap", "promote", "rollback"}:
                horizon = state["models"][identity]["horizon"]
                old = state["active"].get(horizon)
                if old:
                    state["models"][old]["state"] = "retired"
                state["active"][horizon] = identity
                state["models"][identity]["state"] = "champion"
                state["history"].setdefault(horizon, []).append(identity)
            state["head"] = e["sha256"]
        return state

    def append(self, action, payload, *, actor, reason, expected_head):
        if not actor.strip() or not reason.strip():
            raise ValueError("named actor and audit reason required")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = self.snapshot()
            if state["head"] != expected_head:
                raise ValueError("stale selection head")
            self._validate(action, payload, actor, state)
            event = {
                "sequence": len(self.events()),
                "previous": state["head"],
                "at": datetime.now(UTC).isoformat(),
                "action": action,
                "actor": actor,
                "reason": reason,
                "payload": payload,
            }
            event["sha256"] = digest(event)
            write_once(self.root / f"{event['sequence']:06d}.json", event)
            return event["sha256"]

    @staticmethod
    def _validate(action, p, actor, state):
        identity = p["identity"]
        if not isinstance(identity, str) or not identity:
            raise ValueError("model identity required")
        if action in {"register", "bootstrap"}:
            if identity in state["models"] or p["horizon"] not in HORIZONS:
                raise ValueError("duplicate model or invalid horizon")
            for key in ("model_sha256", "calibrator_sha256", "config_sha256", "dataset_sha256", "split_sha256"):
                value = p["lineage"].get(key, "")
                if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                    raise ValueError(f"missing lineage: {key}")
            if p["author"] != actor:
                raise ValueError("registration actor must match author")
            if action == "bootstrap":
                expected = {"pre_weekend": "standings", "post_qualifying": "qualifying"}[p["horizon"]]
                if p.get("baseline") != expected or p["horizon"] in state["active"]:
                    raise ValueError("bootstrap only the fixed fallback when no pointer exists")
            return
        model = state["models"].get(identity)
        if model is None:
            raise ValueError("unknown model")
        horizon = model["horizon"]
        if action == "challenge":
            if model["state"] != "proposed":
                raise ValueError("only proposed models can become challengers")
        elif action == "approve":
            if model["state"] != "challenger" or actor == model["author"]:
                raise ValueError("independent review of a challenger required")
            evidence = p["evidence"]
            binding = {"identity": identity, "horizon": horizon, "lineage": model["lineage"]}
            if p.get("binding_sha256") != digest(binding) or p.get("incumbent") != state["active"].get(horizon):
                raise ValueError("approval does not bind the candidate and current incumbent")
            if (
                not p.get("review_reference")
                or p.get("baseline") != {"pre_weekend": "standings", "post_qualifying": "qualifying"}[horizon]
            ):
                raise ValueError("review reference and frozen baseline required")
            verify_lock()
            if not review_gate(evidence, read_json(CONTRACT / "config.json"))["eligible_for_independent_review"]:
                raise ValueError("locked promotion gate failed")
        elif action == "promote":
            approval = state["approvals"].get(identity)
            if model["state"] != "challenger" or approval is None:
                raise ValueError("independently approved challenger required")
            if approval["incumbent"] != state["active"].get(horizon):
                raise ValueError("incumbent changed since approval; new review required")
        elif action == "rollback":
            if identity not in state["history"].get(horizon, []) or model["state"] != "retired":
                raise ValueError("rollback requires a prior champion of this horizon")
        else:
            raise ValueError("unknown selection action")
