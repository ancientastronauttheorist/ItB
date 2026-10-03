"""Sealed original turn observations and explicitly partial diagnostic replay.

This importer never plans or operates the game. Historical inputs are oracle
diagnostics: the player-observation boundary still rejects their provenance.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPSULE = "data/observatory/captures/windows_build_13725832_owner_local_modified_20260829_spawn_coordinate_capsule"
PINS = {
    CAPSULE + "_receipt.json": "c529484cd2bb1061ef2e3f3ccce80a61e5b9df94815b38ffcb8aa682ab7ef2a1",
    CAPSULE + "_cleanup_receipt.json": "ef3873d612b8b1a52b562600b17f92b04523f8ccb88a6245f40f3cc3b7928204",
    "src/bridge/modloader.lua": "93f99e8854e8f01bc0c64b0c07eff5aa1fe078f7e821a60de133db7ec375986c",
}
EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
UNIT_FIELDS = ("type", "x", "y", "hp", "active", "team", "mech")


def digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def read_pinned(root: Path, path: str, expected: str, size: int | None = None):
    target = (root / path).resolve()
    require(target.is_relative_to(root.resolve()), "source path escapes repository")
    raw = target.read_bytes()
    require(digest(raw) == expected and (size is None or len(raw) == size), "source identity differs: " + path)
    return json.loads(raw)


def compare_projection(before: dict, predicted: dict, actual: dict) -> dict:
    """Grade direct live getters; retain other endpoint differences separately.

    Sparse Rust terrain output represents omitted Ground tiles. Actual tiles
    must be complete. Actual status omission is never filled with false.
    """
    actors = [u for u in before["units"] if u.get("mech") and u.get("active")]
    require(len(actors) == 3, "declared three-mech domain differs")
    pred_units = {u["uid"]: u for u in predicted["units"]}
    actual_units = {u["uid"]: u for u in actual["units"]}
    require(len(pred_units) == len(predicted["units"]) and len(actual_units) == len(actual["units"]), "duplicate unit identity")
    actual_tiles = {(t["x"], t["y"]): t for t in actual["tiles"]}
    pred_tiles = {(t["x"], t["y"]): t for t in predicted["tiles"]}
    require(set(actual_tiles) == {(x, y) for x in range(8) for y in range(8)}, "actual terrain observation incomplete")
    require(len(actual_tiles) == len(actual["tiles"]) and len(pred_tiles) == len(predicted["tiles"]), "duplicate tile identity")
    checks = []
    for label, actor in enumerate(sorted(actors, key=lambda u: (u["x"], u["y"], u["type"]))):
        uid = actor["uid"]
        require(uid in pred_units and uid in actual_units, "declared actor missing at endpoint")
        for field in UNIT_FIELDS:
            require(field in pred_units[uid] and field in actual_units[uid], "direct actor field missing: " + field)
            checks.append(dict(actor_label=label, field=field, predicted=pred_units[uid][field], actual=actual_units[uid][field]))
    for pos, tile in sorted(actual_tiles.items()):
        require(tile["terrain"] in {"ground", "building", "rubble", "water", "mountain"}, "terrain domain differs")
        checks.append(dict(tile=list(pos), field="terrain", predicted=pred_tiles.get(pos, {}).get("terrain", "ground"), actual=tile["terrain"]))
    # Differences outside the admitted projection remain visible, without a
    # mismatched phase being reclassified as a passing complete transition.
    differences = []
    for field in ("grid_power", "spawning_tiles"):
        if predicted.get(field) != actual.get(field):
            differences.append(dict(scope="scalar", field=field, predicted=predicted.get(field), actual=actual.get(field)))
    for uid in sorted(set(pred_units) | set(actual_units)):
        a, p = actual_units.get(uid), pred_units.get(uid)
        if a is None or p is None:
            differences.append(dict(scope="unit", uid=uid, field="roster", predicted_type=p and p["type"], actual_type=a and a["type"]))
            continue
        for field in ("x", "y", "hp", "max_hp", "move", "active", "acid", "fire", "frozen", "shield", "grappled", "queued_target", "weapons"):
            # JSON absence is explicit evidence uncertainty, not Boolean false.
            if p.get(field) != a.get(field):
                differences.append(dict(scope="unit", uid=uid, field=field, predicted=p.get(field), actual=a.get(field), actual_exported=field in a, predicted_exported=field in p))
    for pos, a in sorted(actual_tiles.items()):
        p = pred_tiles.get(pos, {})
        for field in ("building_hp", "acid", "smoke", "fire", "frozen", "shield"):
            if p.get(field) != a.get(field):
                differences.append(dict(scope="tile", tile=list(pos), field=field, predicted=p.get(field), actual=a.get(field), actual_exported=field in a, predicted_exported=field in p))
    mismatches = [c for c in checks if c["predicted"] != c["actual"]]
    ready = actual.get("phase") == "combat_player" and any(u.get("active") and u.get("hp", 0) > 0 for u in actual["units"] if u.get("mech"))
    return dict(checks=checks, checks_attempted=len(checks), mismatches=mismatches,
                ungraded_endpoint_differences=differences, full_state_equivalence=False,
                next_decision_ready=ready,
                alignment_rejection=None if ready else "combat_player alone is insufficient: no living mech is active in the recorded outcome")


def load_trials(root: Path = ROOT) -> tuple[list[dict], list[dict]]:
    receipt = read_pinned(root, CAPSULE + "_receipt.json", PINS[CAPSULE + "_receipt.json"])
    cleanup = read_pinned(root, CAPSULE + "_cleanup_receipt.json", PINS[CAPSULE + "_cleanup_receipt.json"])
    require(digest((root / "src/bridge/modloader.lua").read_bytes()) == PINS["src/bridge/modloader.lua"], "archived loader source differs")
    require(receipt["build_identity"]["executable_sha256"] == EXE_SHA, "original build differs")
    # Loader installation was attested by cleanup, independently of the
    # campaign receipt. Do not infer it merely from today's checkout.
    require(cleanup["install_restore"]["installed_modloader_before_sha256"] == PINS["src/bridge/modloader.lua"], "loader installation attestation missing")
    pins = [dict(path=p, sha256=h) for p, h in PINS.items()]
    trials = []
    for pair in receipt["pairs"]:
        artifacts = pair["artifacts"]
        records = {}
        for name in ("trial", "lifecycle", "outcome", "session", "start_state_proof", "recording_board", "recording_solve_input", "recording_solve", "recording_threat_audit", "recording_resist_probe"):
            pin = artifacts["control_" + name]
            # The resist probe is append-only JSONL, not a JSON object.
            if name == "recording_resist_probe":
                raw = (root / pin["path"]).read_bytes()
                require(len(raw) == pin["size"] and digest(raw) == pin["sha256"], "resist probe differs")
                records[name] = [json.loads(line) for line in raw.decode().splitlines() if line]
            else:
                records[name] = read_pinned(root, pin["path"], pin["sha256"], pin["size"])
            pins.append(dict(pin))
        trial, lifecycle = records["trial"], records["lifecycle"]
        state_record, plan_record = records["recording_solve_input"], records["recording_solve"]
        outcome, boundary = records["outcome"], trial["boundary"]
        require(trial["condition"] == "control" and trial["status"] == "complete" and trial["valid_trial"], "control trial not complete")
        require(lifecycle["valid_lifecycle"] and lifecycle["process_identity"] == trial["process_identity"], "process/lifecycle join differs")
        require(trial["process_identity"]["executable_sha256"] == EXE_SHA and trial["process_identity"]["executable_size"] == 5530112, "trial original build differs")
        require(trial["outcome"]["sha256"] == artifacts["control_outcome"]["sha256"], "trial outcome join differs")
        require(boundary["state"] == "complete" and boundary["delivery_confirmation"] == "delivered_confirmed" and boundary["end_turn_status"] == "OK", "End Turn delivery incomplete")
        require("armed=false" in boundary["prepare_ack"] and "complete=true" in boundary["finish_ack"], "control intervention identity differs")
        require(trial["auto_turn"]["actions_completed"] == 3 and trial["auto_turn"]["desyncs_detected"] == 0 and trial["auto_turn"]["re_solves"] == 0, "action summary outside domain")
        require(state_record["run_id"] == plan_record["run_id"] == records["session"]["run_id"], "recording/session join differs")
        before = state_record["data"]["bridge_state"]
        require(before["mission_id"] == outcome["mission_id"] == "Mission_Power" and before["turn"] == 1 and outcome["turn"] == 2 and outcome["phase"] == "combat_player", "turn/mission boundary differs")
        plan = [{k: a[k] for k in ("mech_uid", "move_to", "weapon_id", "target", "target2") if k in a} for a in plan_record["data"]["actions"]]
        require(len(plan) == 3 and plan_record["data"]["score"] == trial["auto_turn"]["score"], "recorded plan/summary join differs")
        trials.append(dict(id=trial["capture_id"], before=before, plan=plan, actual=outcome,
                           input_timestamp=state_record["timestamp"], plan_timestamp=plan_record["timestamp"],
                           trial_timestamp=trial["created_at"], raw_outcome_timestamp=outcome["timestamp"],
                           original_simulator_version=state_record["data"]["simulator_version"],
                           delivery_confirmation=boundary["delivery_confirmation"], end_turn_ack=boundary["end_turn_ack"],
                           prepare_ack=boundary["prepare_ack"], finish_ack=boundary["finish_ack"]))
    require(len(trials) == 3, "declared control sample size differs")
    return trials, pins
