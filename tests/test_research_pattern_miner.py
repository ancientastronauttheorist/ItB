"""Phase 4 P4-1a — pattern miner tests.

The miner is pure — every test passes files in via tmp_path and
asserts the returned Python. No live corpora, no git, no solver.

Coverage map:

- signature helpers are stable under key reordering / list/tuple
  coercion (otherwise deny-list lookups drift on cosmetic rewrites).
- Vision-side and failure_db-side signatures build correctly and
  collapse same-shape entries across runs.
- Thresholds gate the output: below threshold → absent; at/above →
  present with the right board_refs and count.
- The deny list is consulted *before* counting, so a rejected
  candidate can't accidentally re-appear because its count grew.
- failure_db entries without an action_index or with a non-attack
  trigger are silently skipped (they can't be patched by a weapon
  override).
- Vision and failure_db sources never get merged into one signature
  even when every other field coincides — different thresholds
  apply and mixing them would let the looser source fake the count.
- Output is deterministic across runs (branch hashes depend on it).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research import pattern_miner as pm


# ── helpers ─────────────────────────────────────────────────────────────────


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def _write_solve(root: Path, run_id: str, mission: int, turn: int, actions: list[dict]) -> None:
    d = root / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / f"m{mission:02d}_turn_{turn:02d}_solve.json").write_text(json.dumps({
        "run_id": run_id,
        "mission_index": mission,
        "turn": turn,
        "data": {"actions": actions},
    }))


# ── signature stability ─────────────────────────────────────────────────────


def test_bucket_is_order_independent_for_dicts():
    """Signatures must not drift when the mismatch writer reorders
    keys in the ``rust_value`` dict — otherwise deny-list entries
    silently stop matching after a serializer tweak."""
    a = pm._bucket({"push_dir": "inward", "expected": [1, 4]})
    b = pm._bucket({"expected": [1, 4], "push_dir": "inward"})
    assert a == b


def test_bucket_preserves_list_order():
    # ``[min, max]`` ranges would fold into each other if we sorted.
    assert pm._bucket([1, 4]) != pm._bucket([4, 1])


def test_signature_hash_is_8_chars_and_stable():
    sig = pm.DiffSignature("vision", "Prime_Shift", "damage", "1", "5")
    h = sig.hash8()
    assert len(h) == 8
    assert sig.hash8() == h  # pure function, no randomness


# ── Vision signature extraction ─────────────────────────────────────────────


def test_signature_from_vision_happy_path():
    mm = {
        "weapon_id": "Prime_Shift",
        "field": "damage",
        "rust_value": 1,
        "vision_value": 5,
    }
    sig = pm.signature_from_vision(mm)
    assert sig is not None
    assert sig.source == "vision"
    assert sig.weapon_id == "Prime_Shift"
    assert sig.field == "damage"
    assert sig.rust_bucket == "1"
    assert sig.vision_bucket == "5"


def test_signature_from_vision_unknown_weapon_keys_by_display_name():
    """unknown_weapon rows can't use weapon_id (empty), so the miner
    keys them by the Vision-seen display name. Two runs reporting the
    same mystery weapon must collapse to one signature."""
    a = pm.signature_from_vision({
        "weapon_id": "",
        "field": "unknown_weapon",
        "vision_value": "Death Ray",
        "display_name": "Death Ray",
    })
    b = pm.signature_from_vision({
        "weapon_id": "",
        "field": "unknown_weapon",
        "vision_value": "death ray",  # case drift
        "display_name": "death ray",
    })
    assert a is not None and b is not None
    assert a.weapon_id == b.weapon_id


def test_signature_from_vision_returns_none_for_missing_fields():
    assert pm.signature_from_vision({"weapon_id": "X"}) is None
    assert pm.signature_from_vision({"field": "damage"}) is None  # missing wid


# ── failure_db signature extraction ─────────────────────────────────────────


def test_signature_from_failure_resolves_weapon_id(tmp_path: Path):
    _write_solve(tmp_path, "RUN1", 0, 1, [
        {"mech_uid": 0, "weapon_id": "Prime_Shift"},
        {"mech_uid": 1, "weapon_id": "Brute_Grapple"},
    ])
    loader = pm.SolveLoader(tmp_path)
    f = {
        "trigger": "per_sub_action_desync_attack",
        "run_id": "RUN1", "mission": 0, "turn": 1, "action_index": 1,
        "category": "damage_amount",
        "diff": {"tile_diffs": [{"field": "fire"}],
                 "unit_diffs": [{"field": "hp"}],
                 "scalar_diffs": []},
    }
    sig = pm.signature_from_failure(f, solve_loader=loader)
    assert sig is not None
    assert sig.weapon_id == "Brute_Grapple"
    assert sig.field == "damage_amount"
    # Shape bucket is sorted & joined — stable across call-sites.
    assert "fire" in sig.vision_bucket
    assert "hp" in sig.vision_bucket


def test_signature_from_failure_skips_movement_desyncs(tmp_path: Path):
    loader = pm.SolveLoader(tmp_path)
    f = {
        "trigger": "per_sub_action_desync_move",
        "run_id": "R", "mission": 0, "turn": 1, "action_index": 0,
        "category": "tile_status", "diff": {},
    }
    assert pm.signature_from_failure(f, solve_loader=loader) is None


def test_signature_from_failure_skips_no_action_index(tmp_path: Path):
    loader = pm.SolveLoader(tmp_path)
    f = {
        "trigger": "grid_critical",
        "run_id": "R", "mission": 0, "turn": 1,
        "category": "strategic_decline", "diff": {},
    }
    assert pm.signature_from_failure(f, solve_loader=loader) is None


def test_signature_from_failure_skips_missing_solve(tmp_path: Path):
    # Solve file doesn't exist — loader returns empty actions, signature None.
    loader = pm.SolveLoader(tmp_path)
    f = {
        "trigger": "per_sub_action_desync_attack",
        "run_id": "GHOST", "mission": 0, "turn": 1, "action_index": 0,
        "category": "damage_amount", "diff": {},
    }
    assert pm.signature_from_failure(f, solve_loader=loader) is None


# ── mining: thresholds ──────────────────────────────────────────────────────


def test_mine_vision_damage_stages_on_single_hit(tmp_path: Path):
    """Vision's damage read is essentially ground truth; default
    threshold is 1 so a single high-severity row should stage."""
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"},
    ])
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list=set())
    assert len(out) == 1
    c = out[0]
    assert c.signature.weapon_id == "Prime_Shift"
    assert c.signature.field == "damage"
    assert c.count == 1


def test_mine_vision_footprint_requires_two_hits(tmp_path: Path):
    """Footprint reads are pixel-counted and noisier — default
    threshold is 2."""
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Punchmech", "field": "footprint_size",
         "rust_value": "[1,1]", "vision_value": 3, "severity": "medium"},
    ])
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list=set())
    assert out == []  # one hit is below threshold

    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Punchmech", "field": "footprint_size",
         "rust_value": "[1,1]", "vision_value": 3, "severity": "medium"},
        {"run_id": "R2", "weapon_id": "Prime_Punchmech", "field": "footprint_size",
         "rust_value": "[1,1]", "vision_value": 3, "severity": "medium"},
    ])
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list=set())
    assert len(out) == 1
    assert out[0].count == 2


def test_mine_failure_db_requires_three_boards(tmp_path: Path):
    fp = tmp_path / "fd.jsonl"
    solves_root = tmp_path / "rec"
    for i in range(3):
        rid = f"RUN{i}"
        _write_solve(solves_root, rid, 0, 1, [
            {"mech_uid": 0, "weapon_id": "Prime_Shift"},
        ])
    _write_jsonl(fp, [
        {"trigger": "per_sub_action_desync_attack", "run_id": f"RUN{i}",
         "mission": 0, "turn": 1, "action_index": 0, "category": "damage_amount",
         "diff": {"tile_diffs": [{"field": "building_hp"}], "unit_diffs": [], "scalar_diffs": []}}
        for i in range(2)  # only 2 boards — under threshold
    ])
    out = pm.mine(vision_path=tmp_path / "no.jsonl", failure_path=fp,
                  recordings_root=solves_root, deny_list=set())
    assert out == []

    _write_jsonl(fp, [
        {"trigger": "per_sub_action_desync_attack", "run_id": f"RUN{i}",
         "mission": 0, "turn": 1, "action_index": 0, "category": "damage_amount",
         "diff": {"tile_diffs": [{"field": "building_hp"}], "unit_diffs": [], "scalar_diffs": []}}
        for i in range(3)
    ])
    out = pm.mine(vision_path=tmp_path / "no.jsonl", failure_path=fp,
                  recordings_root=solves_root, deny_list=set())
    assert len(out) == 1
    assert out[0].count == 3
    assert len(out[0].board_refs) == 3


def test_mine_deduplicates_boards_not_hits(tmp_path: Path):
    """Two failure_db rows on the SAME (run, mission, turn) count
    as one board — otherwise a single noisy turn fakes the count."""
    fp = tmp_path / "fd.jsonl"
    solves_root = tmp_path / "rec"
    _write_solve(solves_root, "RUN1", 0, 1, [
        {"weapon_id": "Prime_Shift"},
    ])
    _write_jsonl(fp, [
        {"trigger": "per_sub_action_desync_attack", "run_id": "RUN1",
         "mission": 0, "turn": 1, "action_index": 0, "category": "damage_amount",
         "diff": {"tile_diffs": [{"field": "building_hp"}], "unit_diffs": [], "scalar_diffs": []}}
    ] * 5)
    out = pm.mine(vision_path=tmp_path / "no.jsonl", failure_path=fp,
                  recordings_root=solves_root, deny_list=set())
    assert out == []  # 5 duplicates = 1 board, still below threshold


# ── mining: deny list ───────────────────────────────────────────────────────


def test_mine_respects_deny_list(tmp_path: Path):
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"},
    ])
    # First, mine without deny to learn the signature hash.
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list=set())
    assert len(out) == 1
    h = out[0].hash8

    # Now add that hash to the deny list — candidate should disappear.
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list={h})
    assert out == []


def test_signature_from_staged_entry_round_trips():
    """A staged candidate built by ``_mismatch_to_candidate`` must
    reconstruct the same signature that the original mismatch would
    produce — otherwise ``review_overrides reject`` writes a deny
    hash the miner never matches."""
    from src.solver.weapon_overrides import _mismatch_to_candidate
    mm = {
        "weapon_id": "Prime_Shift", "field": "damage",
        "rust_value": 1, "vision_value": 5,
        "severity": "high", "confidence": 1.0, "display_name": "Vice Fist",
    }
    staged = _mismatch_to_candidate(mm, run_id="R1")
    sig_original = pm.signature_from_vision(mm)
    sig_staged = pm.signature_from_staged_entry(staged)
    assert sig_original == sig_staged
    assert sig_original.hash8() == sig_staged.hash8()


def test_signature_from_staged_entry_returns_none_for_legacy_rows():
    """Pre-P3-5 staged entries (or hand-edited ones) won't carry
    ``source_mismatch``. The helper must return None cleanly so the
    reject path can skip the deny-list write instead of crashing."""
    assert pm.signature_from_staged_entry({"weapon_id": "Prime_Shift"}) is None
    assert pm.signature_from_staged_entry({}) is None


def test_append_to_deny_list_writes_hash_and_metadata(tmp_path: Path):
    p = tmp_path / "deny.jsonl"
    sig = pm.DiffSignature("vision", "Prime_Shift", "damage", "1", "5")
    rec = pm.append_to_deny_list(sig, reason="looks like a real sim bug", path=p)
    assert rec["signature_hash"] == sig.hash8()
    assert rec["weapon_id"] == "Prime_Shift"
    assert rec["reason"] == "looks like a real sim bug"

    # Round-trip: load_deny_list sees the same hash.
    assert pm.load_deny_list(p) == {sig.hash8()}


def test_append_to_deny_list_appends_never_overwrites(tmp_path: Path):
    p = tmp_path / "deny.jsonl"
    sig_a = pm.DiffSignature("vision", "Prime_Shift", "damage", "1", "5")
    sig_b = pm.DiffSignature("vision", "Brute_Grapple", "damage", "1", "3")
    pm.append_to_deny_list(sig_a, path=p)
    pm.append_to_deny_list(sig_b, path=p)
    lines = p.read_text().strip().split("\n")
    assert len(lines) == 2
    assert pm.load_deny_list(p) == {sig_a.hash8(), sig_b.hash8()}


def test_load_deny_list_reads_jsonl(tmp_path: Path):
    p = tmp_path / "deny.jsonl"
    p.write_text(
        json.dumps({"signature_hash": "abc12345", "weapon_id": "X"}) + "\n"
        + json.dumps({"hash8": "def67890", "weapon_id": "Y"}) + "\n"
        + "\n"  # blank line survives
        + "not json\n"  # malformed line survives
    )
    out = pm.load_deny_list(p)
    assert out == {"abc12345", "def67890"}


def test_load_deny_list_missing_file_is_empty(tmp_path: Path):
    assert pm.load_deny_list(tmp_path / "nope.jsonl") == set()


# ── mining: vision and failure_db do not merge ──────────────────────────────


def test_mine_keeps_vision_and_failure_sources_separate(tmp_path: Path):
    """Even when weapon_id + field coincide, a vision hit and a
    failure_db hit have different thresholds — merging them would let
    the lower-threshold source spoof the count."""
    vp = tmp_path / "mm.jsonl"
    fp = tmp_path / "fd.jsonl"
    solves = tmp_path / "rec"
    _write_solve(solves, "RUN1", 0, 1, [{"weapon_id": "Prime_Shift"}])
    _write_jsonl(vp, [
        {"run_id": "VR1", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"},
    ])
    _write_jsonl(fp, [
        {"trigger": "per_sub_action_desync_attack", "run_id": "RUN1",
         "mission": 0, "turn": 1, "action_index": 0, "category": "damage",
         "diff": {}}
    ])
    out = pm.mine(vision_path=vp, failure_path=fp,
                  recordings_root=solves, deny_list=set())
    # Vision fires (threshold=1, count=1). failure_db doesn't (threshold=3, count=1).
    assert len(out) == 1
    assert out[0].signature.source == "vision"


# ── mining: determinism ─────────────────────────────────────────────────────


def test_mine_output_is_deterministic(tmp_path: Path):
    """PR branch hashes depend on this — two invocations with the same
    input must return identical candidate ordering."""
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"},
        {"run_id": "R2", "weapon_id": "Brute_Grapple", "field": "damage",
         "rust_value": 1, "vision_value": 3, "severity": "high"},
    ])
    a = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                recordings_root=tmp_path, deny_list=set())
    b = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                recordings_root=tmp_path, deny_list=set())
    assert [c.signature for c in a] == [c.signature for c in b]
    assert [c.board_refs for c in a] == [c.board_refs for c in b]


# ── mining: timestamp cutoff ────────────────────────────────────────────────


def _write_failure_rows_at(
    fp: Path,
    solves_root: Path,
    weapon_id: str,
    timestamps: list[str],
) -> None:
    """Helper: N failure_db rows across N distinct runs, each with
    a timestamp and a solve.json resolving to ``weapon_id``."""
    rows = []
    for i, ts in enumerate(timestamps):
        rid = f"RUN_{i}"
        _write_solve(solves_root, rid, 0, 1, [{"weapon_id": weapon_id}])
        rows.append({
            "trigger": "per_sub_action_desync_attack", "run_id": rid,
            "mission": 0, "turn": 1, "action_index": 0,
            "category": "damage_amount",
            "timestamp": ts,
            "diff": {"tile_diffs": [{"field": "building_hp"}],
                     "unit_diffs": [], "scalar_diffs": []},
        })
    _write_jsonl(fp, rows)


def test_mine_filters_failure_rows_before_cutoff(tmp_path: Path):
    """Rows stamped before ``min_timestamp`` describe sim output the
    current solver no longer produces — they must not count toward
    thresholds, otherwise a fix that shipped last week keeps faking
    signal forever."""
    fp = tmp_path / "fd.jsonl"
    solves = tmp_path / "rec"
    _write_failure_rows_at(fp, solves, "Prime_Shift", [
        "2026-04-10T10:00:00",  # pre-cutoff
        "2026-04-11T10:00:00",  # pre-cutoff
        "2026-04-14T10:00:00",  # post-cutoff
        "2026-04-15T10:00:00",  # post-cutoff
    ])
    out = pm.mine(
        vision_path=tmp_path / "no.jsonl", failure_path=fp,
        recordings_root=solves, deny_list=set(),
        min_timestamp="2026-04-13T21:31:37",
    )
    # 2 post-cutoff rows < threshold (3) → no candidate surfaces.
    assert out == []

    # Widen the corpus so post-cutoff alone crosses threshold:
    _write_failure_rows_at(fp, solves, "Prime_Shift", [
        "2026-04-10T10:00:00",
        "2026-04-11T10:00:00",
        "2026-04-14T10:00:00",
        "2026-04-15T10:00:00",
        "2026-04-16T10:00:00",
    ])
    out = pm.mine(
        vision_path=tmp_path / "no.jsonl", failure_path=fp,
        recordings_root=solves, deny_list=set(),
        min_timestamp="2026-04-13T21:31:37",
    )
    assert len(out) == 1
    assert out[0].count == 3  # only the 3 post-cutoff boards


def test_mine_cutoff_none_disables_filter(tmp_path: Path):
    """Explicit ``min_timestamp=None`` is the historical-audit mode —
    every row counts regardless of age."""
    fp = tmp_path / "fd.jsonl"
    solves = tmp_path / "rec"
    _write_failure_rows_at(fp, solves, "Prime_Shift", [
        "2026-04-10T10:00:00",
        "2026-04-11T10:00:00",
        "2026-04-12T10:00:00",
    ])
    out = pm.mine(
        vision_path=tmp_path / "no.jsonl", failure_path=fp,
        recordings_root=solves, deny_list=set(),
        min_timestamp=None,
    )
    assert len(out) == 1
    assert out[0].count == 3


def test_mine_cutoff_unset_loads_config(tmp_path: Path, monkeypatch):
    """When callers don't pass ``min_timestamp``, mine() must read
    ``data/mining_cutoff.json`` — otherwise the CLI default silently
    becomes "no filter" and stale rows leak back in."""
    fp = tmp_path / "fd.jsonl"
    solves = tmp_path / "rec"
    cfg = tmp_path / "mining_cutoff.json"
    cfg.write_text(json.dumps({"min_timestamp": "2026-04-13T21:31:37"}))
    monkeypatch.setattr(pm, "DEFAULT_CUTOFF_PATH", cfg)

    _write_failure_rows_at(fp, solves, "Prime_Shift", [
        "2026-04-10T10:00:00",  # pre
        "2026-04-11T10:00:00",  # pre
        "2026-04-12T10:00:00",  # pre
    ])
    out = pm.mine(
        vision_path=tmp_path / "no.jsonl", failure_path=fp,
        recordings_root=solves, deny_list=set(),
    )
    assert out == []  # all rows pre-cutoff, silently filtered


def test_mine_cutoff_does_not_filter_vision(tmp_path: Path):
    """Vision mismatches don't carry a ``timestamp`` on the same
    semantic — they're comparator output against the *current* Rust
    build. Applying the cutoff to them would silently erase every
    fresh Vision hit."""
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": "R1", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"},
    ])
    out = pm.mine(
        vision_path=vp, failure_path=tmp_path / "no.jsonl",
        recordings_root=tmp_path, deny_list=set(),
        min_timestamp="2099-01-01T00:00:00",  # future cutoff
    )
    assert len(out) == 1  # vision still fires


def test_load_min_timestamp_missing_file_returns_none(tmp_path: Path):
    assert pm.load_min_timestamp(tmp_path / "nope.json") is None


def test_load_min_timestamp_malformed_returns_none(tmp_path: Path):
    p = tmp_path / "broken.json"
    p.write_text("{not json")
    assert pm.load_min_timestamp(p) is None

    p.write_text(json.dumps([1, 2, 3]))  # wrong top-level type
    assert pm.load_min_timestamp(p) is None


def test_load_min_timestamp_reads_value(tmp_path: Path):
    p = tmp_path / "cutoff.json"
    p.write_text(json.dumps({"min_timestamp": "2026-04-13T21:31:37"}))
    assert pm.load_min_timestamp(p) == "2026-04-13T21:31:37"


def test_normalize_ts_strips_timezone_offset():
    """Cutoff config may carry a TZ offset; failure_db rows don't.
    Both must compare as naive-local-time ISO strings."""
    assert pm._normalize_ts("2026-04-13T21:31:37-05:00") == "2026-04-13T21:31:37"
    assert pm._normalize_ts("2026-04-13T21:31:37+00:00") == "2026-04-13T21:31:37"
    assert pm._normalize_ts("2026-04-13T21:31:37Z") == "2026-04-13T21:31:37"
    assert pm._normalize_ts("2026-04-13T21:31:37") == "2026-04-13T21:31:37"
    # Date hyphens inside YYYY-MM-DD must survive.
    assert pm._normalize_ts("2026-04-13") == "2026-04-13"


def test_mine_caps_samples_per_candidate(tmp_path: Path):
    vp = tmp_path / "mm.jsonl"
    _write_jsonl(vp, [
        {"run_id": f"R{i}", "weapon_id": "Prime_Shift", "field": "damage",
         "rust_value": 1, "vision_value": 5, "severity": "high"}
        for i in range(10)
    ])
    out = pm.mine(vision_path=vp, failure_path=tmp_path / "no.jsonl",
                  recordings_root=tmp_path, deny_list=set(), sample_cap=2)
    assert len(out) == 1
    assert len(out[0].sample_entries) == 2
    assert out[0].count == 10
