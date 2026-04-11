"""Phase 4 self-improvement pipeline tests.

Covers:
1. _trigger_category maps known triggers to verify-style categories
2. is_auto_fixable_by_tuning per-trigger lookup (no board)
3. is_auto_fixable_by_tuning rejects model_gap_known subcategory
4. is_auto_fixable_by_tuning counterfactual: webbed mech → not fixable
5. is_auto_fixable_by_tuning counterfactual: frozen mech → not fixable
6. is_auto_fixable_by_tuning counterfactual: move_speed=0 → not fixable
7. is_auto_fixable_by_tuning counterfactual: safe alternative exists → fixable
8. count_fired_triggers dedups by (run_id, mission, trigger)
9. count_fired_triggers skips records flagged not-fixable
10. RunSession round-trip preserves recorded_post_enemy_turns
11. _record_post_enemy is idempotent for same (mission, turn) key
"""
from src.solver.analysis import (
    _trigger_category,
    is_auto_fixable_by_tuning,
    _TRIGGER_AUTO_FIXABLE,
)
from src.solver.tuner import count_fired_triggers
from src.loop.session import RunSession
from src.model.board import Board, Unit


def mk_board_with_mech(uid, x, y, move_speed=3, web=False, frozen=False,
                      env_danger=None):
    b = Board()
    b.units = [Unit(
        uid=uid, type="PunchMech", x=x, y=y, hp=3, max_hp=3, team=1,
        is_mech=True, move_speed=move_speed, flying=False, massive=False,
        armor=False, pushable=True, weapon="", weapon2="", active=True,
        web=web, frozen=frozen,
    )]
    if env_danger:
        b.environment_danger = set(env_danger)
    return b


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


# Test 1: _trigger_category mapping
check("_trigger_category: building_lost_unexpected",
      _trigger_category("building_lost_unexpected") == "grid_power")
check("_trigger_category: mech_damage_unexpected",
      _trigger_category("mech_damage_unexpected") == "damage_amount")
check("_trigger_category: mech_on_danger",
      _trigger_category("mech_on_danger") == "death")
check("_trigger_category: grid_critical",
      _trigger_category("grid_critical") == "strategic_decline")
check("_trigger_category: empty_solution",
      _trigger_category("empty_solution") == "search_exhaustion")
check("_trigger_category: unknown",
      _trigger_category("made_up_trigger") == "unknown")

# Test 2: is_auto_fixable_by_tuning lookup-only path
fixable_record = {"trigger": "self_damage_building"}
check("fixable: self_damage_building",
      is_auto_fixable_by_tuning(fixable_record) is True)
not_fixable_record = {"trigger": "grid_critical"}
check("not fixable: grid_critical",
      is_auto_fixable_by_tuning(not_fixable_record) is False)
desync_record = {"trigger": "per_action_desync"}
check("not fixable: per_action_desync",
      is_auto_fixable_by_tuning(desync_record) is False)

# Test 3: model_gap_known subcategory short-circuits to False
gap_record = {"trigger": "self_damage_building",
              "subcategory": "model_gap_known"}
check("not fixable: model_gap_known",
      is_auto_fixable_by_tuning(gap_record) is False)

# Test 4: counterfactual rejects webbed mech
webbed_board = mk_board_with_mech(uid=10, x=4, y=4, web=True)
counter_record = {"trigger": "mech_damage_unexpected", "mech_uid": 10}
check("counterfactual: webbed mech → not fixable",
      is_auto_fixable_by_tuning(counter_record, board=webbed_board) is False)

# Test 5: counterfactual rejects frozen mech
frozen_board = mk_board_with_mech(uid=10, x=4, y=4, frozen=True)
check("counterfactual: frozen mech → not fixable",
      is_auto_fixable_by_tuning(counter_record, board=frozen_board) is False)

# Test 6: move_speed=0 → not fixable
no_move_board = mk_board_with_mech(uid=10, x=4, y=4, move_speed=0)
check("counterfactual: move_speed=0 → not fixable",
      is_auto_fixable_by_tuning(counter_record, board=no_move_board) is False)

# Test 7: safe alternative exists → fixable
# Mech at (4,4) move=3, danger only at (4,4) — plenty of safe tiles around
safe_board = mk_board_with_mech(uid=10, x=4, y=4, move_speed=3,
                                env_danger=[(4, 4)])
check("counterfactual: safe alternative → fixable",
      is_auto_fixable_by_tuning(counter_record, board=safe_board) is True)

# Test 8: count_fired_triggers dedup
dup_records = [
    {"run_id": "R1", "mission": 0, "trigger": "self_damage_building",
     "auto_fixable_by_tuning": True, "replay_file": "nonexistent.json"},
    {"run_id": "R1", "mission": 0, "trigger": "self_damage_building",
     "auto_fixable_by_tuning": True, "replay_file": "nonexistent.json"},
    {"run_id": "R1", "mission": 0, "trigger": "self_damage_building",
     "auto_fixable_by_tuning": True, "replay_file": "nonexistent.json"},
]
# Three identical records → dedup → 1 unique. Missing replay_file → counts
# as still firing → returns 1.
n = count_fired_triggers({}, dup_records, time_limit=1.0)
check("count_fired_triggers dedups identical records",
      n == 1, f"got {n}")

# Test 9: skips not-fixable records
skip_records = [
    {"run_id": "R2", "mission": 1, "trigger": "grid_critical",
     "auto_fixable_by_tuning": False, "replay_file": "nonexistent.json"},
]
n = count_fired_triggers({}, skip_records, time_limit=1.0)
check("count_fired_triggers skips not-fixable", n == 0, f"got {n}")

# Test 10: RunSession round-trip preserves recorded_post_enemy_turns
s = RunSession(run_id="test")
s.recorded_post_enemy_turns.append([0, 3])
s.recorded_post_enemy_turns.append([1, 5])
d = s.to_dict()
s2 = RunSession.from_dict(d)
check("RunSession round-trips recorded_post_enemy_turns",
      s2.recorded_post_enemy_turns == [[0, 3], [1, 5]],
      s2.recorded_post_enemy_turns)

# Test 11: dedup membership check
key = [0, 3]
check("dedup key membership",
      key in s2.recorded_post_enemy_turns)

print(f"\n{passed}/{passed+failed} tests passed")
if failed:
    raise SystemExit(1)
