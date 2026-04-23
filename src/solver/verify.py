"""Per-action diff engine for the post-action verification loop.

Compares a predicted board snapshot (captured inside ``replay_solution``
after each ``simulate_action`` call) against the actual game state read
back from the bridge. Used by ``cmd_verify_action`` to detect desyncs
between solver predictions and reality without ever re-solving mid-turn.

Design notes:
  - Snapshots are JSON-friendly dicts so they live in solve recordings.
  - The diff only inspects units present in either snapshot, plus tiles
    that the action's events touched. We never scan all 64 tiles.
  - Dead-mech equivalence: a unit dead in both snapshots collapses to a
    single "dead" state — we don't false-positive on its ``active`` flag.
  - The Python sim has known model gaps (ACID transfer, Tyrant Psion,
    Vek spawns). Diffs originating from those are tagged
    ``model_gap_known`` so the tuner can filter them out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Solve-record schema version. Bump when the shape of the ``data`` block
# written by cmd_solve changes in a way readers must adapt to.
#
#   version 1 (current): flat top-1 plan. ``data.predicted_states`` holds
#     a list of per-action snapshots for the single chosen plan.
#   version 2 (reserved, beam lands in Task #10): ``data.beam`` carries
#     top-K plans and per-depth projections; ``data.predicted_states``
#     stays populated with the chosen plan's states for backward reads.
#
# Readers must route through ``predicted_states_from_solve_record`` so
# the adapter can evolve centrally.
SOLVE_RECORD_SCHEMA_VERSION = 1
_KNOWN_SOLVE_SCHEMA_VERSIONS = {1}


# Simulator semantic version. Bump every time the Rust or Python simulator
# changes behavior in a way that would make pre-bump predictions invalid
# for post-bump corpus analysis. Examples that require a bump:
#   - Storm Generator passive implemented (was silent)
#   - Psion regen actually applied (was a no-op)
#   - Spartan Shield damage + flip semantics fixed
#   - Any PushDir::Flip change
#   - Any change to simulate_enemy_attacks, apply_damage, apply_push paths
# Weight-tuning changes do NOT require a bump; this is semantic, not scoring.
#
# The tuner and analysis tools pin their corpus to a simulator_version so
# pre-bump failure_db rows don't contaminate post-bump optimization.
# v3 (2026-04-23): pilot passives wired into the simulator
#   - Pilot_Soldier (Camila Vera): web immunity at the apply_weapon_status /
#     enemy web hooks
#   - Pilot_Rock (Ariadne): fire immunity at every fire-apply site (weapon,
#     tile catch on push/move/throw, enemy weapon fire) + fire-tick skip
#   - Pilot_Repairman (Harold Schmidt): Repair pushes all 4 adjacent tiles
# Any board with one of these pilots can now produce a different predicted
# state than v2. Pre-v3 rows archived to failure_db_snapshot_sim_v2.jsonl.
#
# v4 (2026-04-23, Rift Walkers simulator pass):
#   - Ranged_Rocket places smoke on the tile directly behind the shooter
#     (new SMOKE_BEHIND_SHOOTER weapon flag).
#   - Jet_BombDrop (Aerial Bombs) places smoke on transit tile(s), not
#     the landing tile.
#   - Sim now enforces Jet_BombDrop landing-tile legality (mountain or
#     occupied landing = target rejected at enumeration time). Behavior
#     was correct in production via Board::is_blocked; debug_assert added
#     to guard against regressions.
#   - effectively_flying() = flying && !frozen is now used in
#     apply_damage_core, apply_throw, and apply_push deadly-terrain checks:
#     frozen flying Vek pushed/thrown into water drown (they were
#     previously predicted to survive).
#   - Massive trait's drown-immunity is now correctly scoped to Water/Lava
#     only — Massive units die in chasms (Seismic/Cataclysm/push) and from
#     lethal Tidal Wave. Previously apply_push/apply_throw killed Massive
#     units on ALL deadly ground (over-killing in Water/Lava).
# Pre-v4 rows archived to failure_db_snapshot_sim_v3.jsonl.
SIMULATOR_VERSION = 4


def predicted_states_from_solve_record(record: dict) -> list:
    """Return the per-action predicted_states list from a solve recording.

    Handles both pre-versioning recordings (missing schema_version, treat
    as v1) and current recordings (schema_version=1). Future beam-shape
    records (v2) will also expose predicted_states for the chosen plan;
    this helper is the single extension point.

    Returns an empty list if the record is malformed or the schema is
    unknown — callers should check length before indexing.
    """
    if not isinstance(record, dict):
        return []
    data = record.get("data") or {}
    if not isinstance(data, dict):
        return []
    version = data.get("schema_version", 1)
    if version not in _KNOWN_SOLVE_SCHEMA_VERSIONS:
        # Unknown future version — return what's present so readers can
        # at least attempt a diff, but they'll see a truncated list if
        # the new shape moved predicted_states elsewhere.
        return data.get("predicted_states") or []
    return data.get("predicted_states") or []

# Matches "(x,y)" with optional whitespace, e.g. "Killed Hornet at (3, 5)".
_COORD_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def parse_tiles_from_events(events: list[str]) -> list[tuple[int, int]]:
    """Extract every (x, y) coordinate mentioned in event strings.

    Returns a sorted list of unique on-board coordinates.
    """
    tiles: set[tuple[int, int]] = set()
    for ev in events:
        for m in _COORD_RE.finditer(ev):
            x, y = int(m.group(1)), int(m.group(2))
            if 0 <= x < 8 and 0 <= y < 8:
                tiles.add((x, y))
    return sorted(tiles)


def snapshot_after_move(
    board,
    action_index: int,
    mech_uid: int,
    move_events: list[str],
) -> dict:
    """Capture board snapshot after only the move phase.

    Lighter than snapshot_after_action — captures the mech's new position
    and any tile effects from moving (pod collection). Used by the
    verify-after-every-sub-action loop to check the move landed correctly
    before proceeding to the attack phase.
    """
    touched: set[tuple[int, int]] = set(parse_tiles_from_events(move_events))

    for u in board.units:
        if u.uid == mech_uid:
            touched.add((u.x, u.y))
            break

    expanded: set[tuple[int, int]] = set()
    for tx, ty in touched:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    expanded.add((nx, ny))

    units_snapshot = []
    for u in board.units:
        units_snapshot.append({
            "uid": u.uid,
            "type": u.type,
            "pos": [u.x, u.y],
            "hp": u.hp,
            "max_hp": u.max_hp,
            "alive": u.hp > 0,
            "active": getattr(u, "active", True),
            "is_mech": u.is_mech,
            "team": u.team,
            "status": {
                "fire": u.fire,
                "acid": u.acid,
                "frozen": u.frozen,
                "shield": u.shield,
                "web": u.web,
            },
        })

    tiles_snapshot = []
    for (x, y) in sorted(expanded):
        t = board.tile(x, y)
        tiles_snapshot.append({
            "x": x,
            "y": y,
            "terrain": t.terrain,
            "building_hp": t.building_hp,
            "fire": t.on_fire,
            "acid": t.acid,
            "smoke": t.smoke,
            "has_pod": t.has_pod,
        })

    return {
        "action_index": action_index,
        "mech_uid": mech_uid,
        "snapshot_phase": "after_move",
        "units": units_snapshot,
        "tiles_changed": tiles_snapshot,
        "grid_power": board.grid_power,
    }


def snapshot_after_action(
    board,
    action_index: int,
    mech_uid: int,
    events: list[str],
) -> dict:
    """Capture a JSON-friendly board snapshot after a mech action mutates it.

    Captures EVERY unit (alive or dead) so diff_states can detect
    death/spawn mismatches, but only the tiles touched by the action's
    events (parsed from the events strings, plus a 1-tile buffer for
    chain effects). The mech's current tile is always included.
    """
    touched: set[tuple[int, int]] = set(parse_tiles_from_events(events))

    # Always capture the mech's current tile (move-only actions emit no
    # events but we still want the destination).
    for u in board.units:
        if u.uid == mech_uid:
            touched.add((u.x, u.y))
            break

    # 1-tile buffer for chain effects (Blast Psion explosions, push cascades).
    expanded: set[tuple[int, int]] = set()
    for tx, ty in touched:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < 8 and 0 <= ny < 8:
                    expanded.add((nx, ny))

    units_snapshot = []
    for u in board.units:
        units_snapshot.append({
            "uid": u.uid,
            "type": u.type,
            "pos": [u.x, u.y],
            "hp": u.hp,
            "max_hp": u.max_hp,
            "alive": u.hp > 0,
            "active": getattr(u, "active", True),
            "is_mech": u.is_mech,
            "team": u.team,
            "status": {
                "fire": u.fire,
                "acid": u.acid,
                "frozen": u.frozen,
                "shield": u.shield,
                "web": u.web,
            },
        })

    tiles_snapshot = []
    for (x, y) in sorted(expanded):
        t = board.tile(x, y)
        tiles_snapshot.append({
            "x": x,
            "y": y,
            "terrain": t.terrain,
            "building_hp": t.building_hp,
            "fire": t.on_fire,
            "acid": t.acid,
            "smoke": t.smoke,
            "has_pod": t.has_pod,
        })

    return {
        "action_index": action_index,
        "mech_uid": mech_uid,
        "snapshot_phase": "after_mech_action",
        "units": units_snapshot,
        "tiles_changed": tiles_snapshot,
        "grid_power": board.grid_power,
    }


@dataclass
class DiffResult:
    """Aggregated diff between a predicted snapshot and an actual Board."""

    unit_diffs: list[dict] = field(default_factory=list)
    tile_diffs: list[dict] = field(default_factory=list)
    scalar_diffs: list[dict] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.unit_diffs or self.tile_diffs or self.scalar_diffs)

    def total_count(self) -> int:
        return (
            len(self.unit_diffs)
            + len(self.tile_diffs)
            + len(self.scalar_diffs)
        )

    def to_dict(self) -> dict:
        return {
            "unit_diffs": self.unit_diffs,
            "tile_diffs": self.tile_diffs,
            "scalar_diffs": self.scalar_diffs,
            "total_count": self.total_count(),
        }


def diff_states(predicted: dict, actual_board) -> DiffResult:
    """Diff a predicted snapshot dict against an actual Board object.

    The actual Board is the live game state from ``read_bridge_state``.
    Only units in either snapshot are inspected, and only tiles in
    ``predicted.tiles_changed`` are checked (no full 64-tile scan).
    """
    result = DiffResult()

    pred_units = {u["uid"]: u for u in predicted.get("units", [])}
    actual_units = {u.uid: u for u in actual_board.units}

    for uid in set(pred_units) | set(actual_units):
        pu = pred_units.get(uid)
        au = actual_units.get(uid)

        if pu is None and au is None:
            continue

        # Unit only in actual: a Vek that spawned mid-turn. Per-action
        # snapshots are pre-end-turn, so this should be rare; flag it.
        if pu is None:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "missing_in_predicted",
                "predicted": "absent",
                "actual": "present",
            })
            continue

        # Unit only in predicted: removed by the actual game.
        # Dead enemies are expected to be absent from the bridge —
        # the game engine removes dead Vek entirely (only mech wrecks persist).
        if au is None:
            pu_alive = pu.get("alive", True)
            pu_hp = pu.get("hp", 1)
            if not pu_alive or pu_hp <= 0:
                continue  # expected: dead enemy gone from bridge
            result.unit_diffs.append({
                "uid": uid,
                "type": pu.get("type"),
                "field": "missing_in_actual",
                "predicted": "present",
                "actual": "absent",
            })
            continue

        # Dead-mech equivalence: if both report dead, ignore everything else.
        pu_alive = pu.get("alive", True)
        au_alive = au.hp > 0
        if not pu_alive and not au_alive:
            continue

        if pu_alive != au_alive:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "alive",
                "predicted": pu_alive,
                "actual": au_alive,
            })
            # Other field diffs are noise once alive status diverges.
            continue

        if pu.get("hp") != au.hp:
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "hp",
                "predicted": pu.get("hp"),
                "actual": au.hp,
            })

        pu_pos = tuple(pu.get("pos", [-1, -1]))
        if pu_pos != (au.x, au.y):
            result.unit_diffs.append({
                "uid": uid,
                "type": au.type,
                "field": "pos",
                "predicted": list(pu_pos),
                "actual": [au.x, au.y],
            })

        # Active flag is only meaningful for mechs.
        if au.is_mech:
            pu_active = pu.get("active", True)
            au_active = getattr(au, "active", True)
            if pu_active != au_active:
                result.unit_diffs.append({
                    "uid": uid,
                    "type": au.type,
                    "field": "active",
                    "predicted": pu_active,
                    "actual": au_active,
                })

        pu_status = pu.get("status", {})
        for sf in ("fire", "acid", "frozen", "shield", "web"):
            pv = pu_status.get(sf, False)
            av = getattr(au, sf, False)
            if pv != av:
                result.unit_diffs.append({
                    "uid": uid,
                    "type": au.type,
                    "field": f"status.{sf}",
                    "predicted": pv,
                    "actual": av,
                })

    for pt in predicted.get("tiles_changed", []):
        x, y = pt["x"], pt["y"]
        if not (0 <= x < 8 and 0 <= y < 8):
            continue
        at = actual_board.tile(x, y)

        if pt.get("terrain") != at.terrain:
            result.tile_diffs.append({
                "x": x, "y": y,
                "field": "terrain",
                "predicted": pt.get("terrain"),
                "actual": at.terrain,
            })
        if pt.get("building_hp", 0) != at.building_hp:
            result.tile_diffs.append({
                "x": x, "y": y,
                "field": "building_hp",
                "predicted": pt.get("building_hp", 0),
                "actual": at.building_hp,
            })
        for pred_field, actual_attr in (
            ("fire", "on_fire"),
            ("acid", "acid"),
            ("smoke", "smoke"),
            ("has_pod", "has_pod"),
        ):
            pv = pt.get(pred_field, False)
            av = getattr(at, actual_attr, False)
            if pv != av:
                result.tile_diffs.append({
                    "x": x, "y": y,
                    "field": pred_field,
                    "predicted": pv,
                    "actual": av,
                })

    if predicted.get("grid_power") != actual_board.grid_power:
        result.scalar_diffs.append({
            "field": "grid_power",
            "predicted": predicted.get("grid_power"),
            "actual": actual_board.grid_power,
        })

    return result


# Top-label priority — set by Phase 2's plan, see plan §2C.
_CATEGORY_PRIORITY = [
    "click_miss",
    "mech_position_wrong",
    "move_blocked",
    "death",
    "damage_amount",
    "push_dir",
    "grid_power",
    "status",
    "terrain",
    "tile_status",
    "spawn",
    "pod",
]


def classify_diff(diff: DiffResult, mech_uid: int = None, phase: str = "action") -> dict:
    """Classify a diff into a top category, all categories, and a subcategory.

    Args:
        diff: The DiffResult to classify.
        mech_uid: UID of the acting mech (for mech-specific classification).
        phase: "move", "attack", or "action" (combined). Controls category
               selection for mech position diffs.

    Returns a dict with:
        top_category: str — single label by priority order
        categories:   sorted list[str] — every category that fired
        subcategory:  str | None — e.g. "model_gap_known" for ACID transfer
        model_gap:    bool — true if any diff matches a known sim gap
    """
    categories: set[str] = set()

    for ud in diff.unit_diffs:
        f = ud["field"]
        utype = ud.get("type", "") or ""
        is_mech_diff = mech_uid is not None and ud["uid"] == mech_uid

        if f == "pos":
            if is_mech_diff or "Mech" in utype:
                if phase == "move":
                    categories.add("mech_position_wrong")
                else:
                    categories.add("click_miss")
            else:
                categories.add("push_dir")
        elif f == "active" and is_mech_diff:
            categories.add("click_miss")
        elif f == "alive":
            categories.add("death")
        elif f == "hp":
            categories.add("damage_amount")
        elif f.startswith("status."):
            categories.add("status")
        elif f in ("missing_in_actual", "missing_in_predicted"):
            categories.add("spawn")

    for td in diff.tile_diffs:
        f = td["field"]
        if f == "terrain":
            categories.add("terrain")
        elif f == "building_hp":
            categories.add("grid_power")
        elif f == "has_pod":
            categories.add("pod")
        elif f in ("fire", "acid", "smoke"):
            categories.add("tile_status")

    for sd in diff.scalar_diffs:
        if sd["field"] == "grid_power":
            categories.add("grid_power")
        elif sd["field"] == "spawning_tiles":
            categories.add("spawn")

    # Click_miss subsumes everything: if the mech never moved, nothing
    # downstream of it should have happened either.
    if "click_miss" in categories:
        categories = {"click_miss"}

    top = next((c for c in _CATEGORY_PRIORITY if c in categories), "unknown")

    # Model-gap detection — diffs the Python sim is known to miss.
    subcategory = None
    model_gap = False
    for td in diff.tile_diffs:
        if td["field"] == "acid":
            # ACID tile transfer (when an ACID Vek dies on a tile) is
            # not modeled in Python sim. Tag it so the tuner ignores it.
            subcategory = "model_gap_known"
            model_gap = True
            break

    return {
        "top_category": top,
        "categories": sorted(categories),
        "subcategory": subcategory,
        "model_gap": model_gap,
    }
