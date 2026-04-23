"""Phase 2 per-action verification loop tests.

Covers:
1. parse_tiles_from_events extracts coords from event strings
2. snapshot_after_action: empty events still captures the mech tile
3. diff_states: identical state → empty diff
4. diff_states: HP diff → damage_amount
5. diff_states: position diff (Vek) → push_dir
6. diff_states: alive flip → death (and other diffs suppressed)
7. diff_states: dead-mech equivalence (both dead = no diff)
8. diff_states: mech still active when expected inactive → click_miss
9. diff_states: building_hp diff → grid_power
10. diff_states: tile fire flag diff → tile_status
11. diff_states: tile acid diff → tile_status w/ model_gap_known subcategory
12. classify_diff: click_miss subsumes other categories
"""
from src.solver.verify import (
    SOLVE_RECORD_SCHEMA_VERSION,
    parse_tiles_from_events,
    snapshot_after_action,
    diff_states,
    classify_diff,
    predicted_states_from_solve_record,
    DiffResult,
)
from src.model.board import Board, Unit, BoardTile


def make_board(units=None, grid_power=7):
    b = Board()
    b.grid_power = grid_power
    b.grid_power_max = 7
    if units:
        b.units = list(units)
    return b


def mk_unit(uid, type_, x, y, hp=3, max_hp=3, team=1, is_mech=True,
            active=True, flying=False, fire=False, acid=False,
            frozen=False, shield=False, web=False):
    return Unit(
        uid=uid, type=type_, x=x, y=y, hp=hp, max_hp=max_hp, team=team,
        is_mech=is_mech, move_speed=3, flying=flying, massive=False,
        armor=False, pushable=True, weapon="", weapon2="", active=active,
        shield=shield, acid=acid, frozen=frozen, fire=fire, web=web,
    )


passed = 0
failed = 0


def check(name, cond, *details):
    global passed, failed
    if cond:
        print(f"  PASS {name}")
        passed += 1
    else:
        print(f"  FAIL {name}: {details}")
        failed += 1


# Test 1: parse_tiles_from_events
events = [
    "Killed Hornet at (3,5)",
    "Building destroyed at (4, 2) (1 grid damage)",
    "Pushed Hornet (3,5)->(3,6)",
    "Death explosion at (7,7) from Hornet",
    "no coords here",
]
tiles = parse_tiles_from_events(events)
check("parse_tiles extracts all coords",
      set(tiles) == {(3, 5), (4, 2), (3, 6), (7, 7)})

# Test 2: snapshot captures mech tile even with no events
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
mech_tile_in_snap = any(t["x"] == 4 and t["y"] == 4 for t in snap["tiles_changed"])
check("snapshot captures mech tile with empty events", mech_tile_in_snap)
check("snapshot has correct unit count", len(snap["units"]) == 1)
check("snapshot includes grid_power", snap["grid_power"] == 7)

# Test 3: identical state → empty diff
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
b2 = make_board(units=[mk_unit(1, "PunchMech", 4, 4)])
diff = diff_states(snap, b2)
check("identical states → empty diff", diff.is_empty(),
      f"unit_diffs={diff.unit_diffs}")

# Test 4: HP diff → damage_amount
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4, hp=3)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
b2 = make_board(units=[mk_unit(1, "PunchMech", 4, 4, hp=1)])
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("HP diff → damage_amount",
      cls["top_category"] == "damage_amount",
      cls)

# Test 5: Vek position diff → push_dir
vek = mk_unit(2, "Hornet1", 5, 5, team=6, is_mech=False)
b = make_board(units=[vek])
snap = snapshot_after_action(b, 0, mech_uid=99, events=["Hornet at (5,5)"])
vek2 = mk_unit(2, "Hornet1", 6, 5, team=6, is_mech=False)
b2 = make_board(units=[vek2])
diff = diff_states(snap, b2)
cls = classify_diff(diff)
check("Vek pos diff → push_dir",
      cls["top_category"] == "push_dir",
      cls)

# Test 6: alive flip → death (suppresses other field diffs)
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4, hp=3)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
b2 = make_board(units=[mk_unit(1, "PunchMech", 4, 4, hp=0, active=False)])
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("alive flip → death", cls["top_category"] == "death", cls)
death_diffs = [d for d in diff.unit_diffs if d["field"] == "alive"]
check("alive flip records single alive diff (HP suppressed)",
      len(death_diffs) == 1 and len(diff.unit_diffs) == 1, diff.unit_diffs)

# Test 7: dead-mech equivalence — both dead, no diff
mech_dead_pred = mk_unit(1, "PunchMech", 4, 4, hp=0, active=False)
mech_dead_actual = mk_unit(1, "PunchMech", 4, 4, hp=0, active=True)
b = make_board(units=[mech_dead_pred])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
b2 = make_board(units=[mech_dead_actual])
diff = diff_states(snap, b2)
check("dead-mech equivalence (both dead = empty diff)", diff.is_empty(),
      diff.unit_diffs)

# Test 8: mech still active when expected inactive → click_miss
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4, active=False)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
b2 = make_board(units=[mk_unit(1, "PunchMech", 4, 4, active=True)])
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("mech still active → click_miss", cls["top_category"] == "click_miss", cls)

# Test 9: building_hp diff → grid_power
b = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b.tile(2, 2).terrain = "building"
b.tile(2, 2).building_hp = 1
snap = snapshot_after_action(b, 0, mech_uid=1, events=["damaged at (2,2)"])
b2 = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b2.tile(2, 2).terrain = "rubble"
b2.tile(2, 2).building_hp = 0
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("building_hp diff → grid_power",
      cls["top_category"] in ("grid_power", "terrain"),
      cls)
# building_hp differs AND terrain differs — both fire
check("building_hp diff records building_hp field",
      any(d["field"] == "building_hp" for d in diff.tile_diffs),
      diff.tile_diffs)

# Test 10: tile fire flag diff → tile_status
b = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b.tile(3, 3).on_fire = False
snap = snapshot_after_action(b, 0, mech_uid=1, events=["fire at (3,3)"])
b2 = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b2.tile(3, 3).on_fire = True
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("tile fire diff → tile_status",
      cls["top_category"] == "tile_status",
      cls)

# Test 11: tile acid diff → tile_status with model_gap_known subcategory
b = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b.tile(3, 3).acid = False
snap = snapshot_after_action(b, 0, mech_uid=1, events=["acid at (3,3)"])
b2 = make_board(units=[mk_unit(1, "PunchMech", 0, 0)])
b2.tile(3, 3).acid = True
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("tile acid diff → tile_status",
      cls["top_category"] == "tile_status", cls)
check("tile acid diff → model_gap_known subcategory",
      cls["subcategory"] == "model_gap_known" and cls["model_gap"] is True,
      cls)

# Test 12: click_miss subsumes other categories
b = make_board(units=[mk_unit(1, "PunchMech", 4, 4, active=False, hp=3)])
snap = snapshot_after_action(b, 0, mech_uid=1, events=[])
# Mech still active AND took damage — click_miss should subsume damage_amount
b2 = make_board(units=[mk_unit(1, "PunchMech", 4, 4, active=True, hp=2)])
diff = diff_states(snap, b2)
cls = classify_diff(diff, mech_uid=1)
check("click_miss subsumes other categories",
      cls["categories"] == ["click_miss"], cls)

# Test 13: predicted_states_from_solve_record — pre-versioning records
# (no schema_version field) still yield their predicted_states.
pre_version_record = {
    "label": "solve",
    "data": {
        "score": 1234,
        "predicted_states": [{"post_attack": {"units": []}}],
    },
}
states = predicted_states_from_solve_record(pre_version_record)
check("pre-versioning record: predicted_states readable",
      len(states) == 1 and states[0]["post_attack"]["units"] == [])

# Test 14: predicted_states_from_solve_record — explicit v1 record.
v1_record = {
    "label": "solve",
    "data": {
        "schema_version": 1,
        "score": 1234,
        "predicted_states": [{"post_attack": {"units": []}},
                             {"post_attack": {"units": [1]}}],
    },
}
states = predicted_states_from_solve_record(v1_record)
check("v1 record: predicted_states readable",
      len(states) == 2)

# Test 15: predicted_states_from_solve_record — malformed record → [].
check("malformed record (non-dict) returns empty list",
      predicted_states_from_solve_record(None) == [])
check("malformed record (missing data) returns empty list",
      predicted_states_from_solve_record({"label": "solve"}) == [])

# Test 16: schema constant matches the documented current version.
check("SOLVE_RECORD_SCHEMA_VERSION == 1 (bump when shape changes)",
      SOLVE_RECORD_SCHEMA_VERSION == 1)

# Test 17: unknown future schema version still yields any present
# predicted_states (v2 keeps the field for backward reads per design).
v2_forward_record = {
    "label": "solve",
    "data": {
        "schema_version": 2,
        "predicted_states": [{"post_attack": {}}],
        "beam": {"top_k": []},
    },
}
states = predicted_states_from_solve_record(v2_forward_record)
check("future v2 record: chosen-plan predicted_states still readable",
      len(states) == 1)

print(f"\n{passed}/{passed+failed} tests passed")
if failed:
    raise SystemExit(1)
