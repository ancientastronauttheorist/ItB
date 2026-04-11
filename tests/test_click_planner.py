"""Phase 3 click planner tests.

Covers:
1. classify_weapon for normal/dash/repair/passive/empty/unknown
2. plan_single_mech: select-only when board doesn't contain the mech
3. plan_single_mech: normal weapon → select → move → arm → target
4. plan_single_mech: normal weapon, no move (already at move_to)
5. plan_single_mech: dash weapon (charge) → select → arm → target only
6. plan_single_mech: repair → select → optional move → repair button
7. plan_single_mech: repair without move
8. plan_single_mech: passive → select only
9. plan_single_mech: secondary weapon goes to slot 2
10. plan_end_turn always emits one click at the End Turn position
"""

# Mock window detection BEFORE importing the executor module so the
# cached lookups don't try to talk to Quartz.
class _FakeWindow:
    x = 0
    y = 0
    width = 1280
    height = 748


import src.control.executor as executor
executor._cached_window = _FakeWindow()
executor._cached_grid = object()  # any non-None sentinel

from src.solver.solver import MechAction
from src.control.executor import (
    plan_single_mech,
    plan_end_turn,
    grid_to_mcp,
    classify_weapon,
    _ui_weapon_slot_1,
    _ui_weapon_slot_2,
    _ui_repair_button,
    _ui_end_turn,
)
from src.model.board import Board, Unit


def mk_unit(uid, type_, x, y, weapon="", weapon2="", is_mech=True, hp=3):
    return Unit(
        uid=uid, type=type_, x=x, y=y, hp=hp, max_hp=hp,
        team=1 if is_mech else 6, is_mech=is_mech, move_speed=3,
        flying=False, massive=False, armor=False, pushable=True,
        weapon=weapon, weapon2=weapon2, active=True,
    )


def mk_board(units):
    b = Board()
    b.units = list(units)
    return b


def mk_action(mech_uid, mech_type, move_to, weapon, target):
    return MechAction(
        mech_uid=mech_uid, mech_type=mech_type,
        move_to=move_to, weapon=weapon, target=target,
        description=f"{mech_type} {weapon} -> {target}",
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


# Test 1: classify_weapon coverage
check("classify normal", classify_weapon("Prime_Punchmech") == "normal")
check("classify dash (charge)", classify_weapon("Brute_Beetle") == "dash")
check("classify dash (leap)", classify_weapon("Prime_Leap") == "dash")
check("classify repair", classify_weapon("_REPAIR") == "repair")
check("classify passive", classify_weapon("Passive_Electric") == "passive")
check("classify empty -> normal", classify_weapon("") == "normal")
check("classify unknown -> normal", classify_weapon("Bogus_Weapon") == "normal")

# Test 2: empty plan when mech not on board
b = mk_board([])
a = mk_action(99, "PunchMech", (3, 5), "Prime_Punchmech", (4, 5))
plan = plan_single_mech(a, b)
check("missing mech -> empty plan", plan == [], plan)

# Test 3: normal weapon flow
mech = mk_unit(0, "PunchMech", 3, 4, weapon="Prime_Punchmech")
b = mk_board([mech])
a = mk_action(0, "PunchMech", (3, 5), "Prime_Punchmech", (4, 5))
plan = plan_single_mech(a, b)
check("normal: 4 clicks (select+move+arm+target)", len(plan) == 4, len(plan), plan)
check("normal: first click selects mech tile",
      plan[0]["x"] == grid_to_mcp(3, 4)[0] and plan[0]["y"] == grid_to_mcp(3, 4)[1])
check("normal: second click moves to dest",
      plan[1]["x"] == grid_to_mcp(3, 5)[0] and plan[1]["y"] == grid_to_mcp(3, 5)[1])
check("normal: third click arms primary slot",
      (plan[2]["x"], plan[2]["y"]) == _ui_weapon_slot_1())
check("normal: fourth click fires at target",
      plan[3]["x"] == grid_to_mcp(4, 5)[0] and plan[3]["y"] == grid_to_mcp(4, 5)[1])

# Test 4: normal weapon, no move (move_to == current pos)
mech = mk_unit(0, "PunchMech", 3, 4, weapon="Prime_Punchmech")
b = mk_board([mech])
a = mk_action(0, "PunchMech", (3, 4), "Prime_Punchmech", (4, 4))
plan = plan_single_mech(a, b)
check("normal no-move: 3 clicks (select+arm+target)", len(plan) == 3, plan)

# Test 5: dash weapon — no separate move click
mech = mk_unit(0, "ChargeMech", 2, 2, weapon="Brute_Beetle")
b = mk_board([mech])
a = mk_action(0, "ChargeMech", (2, 5), "Brute_Beetle", (2, 5))
plan = plan_single_mech(a, b)
check("dash: 3 clicks (select+arm+target)", len(plan) == 3, plan)
check("dash: no move click",
      not any("Move to" in c["description"] for c in plan), plan)

# Test 6: repair with move
mech = mk_unit(0, "PunchMech", 1, 1)
b = mk_board([mech])
a = mk_action(0, "PunchMech", (2, 2), "_REPAIR", (-1, -1))
plan = plan_single_mech(a, b)
check("repair w/ move: 3 clicks (select+move+repair)", len(plan) == 3, plan)
check("repair: last click is repair button",
      (plan[-1]["x"], plan[-1]["y"]) == _ui_repair_button())

# Test 7: repair without move
mech = mk_unit(0, "PunchMech", 1, 1)
b = mk_board([mech])
a = mk_action(0, "PunchMech", (1, 1), "_REPAIR", (-1, -1))
plan = plan_single_mech(a, b)
check("repair no move: 2 clicks (select+repair)", len(plan) == 2, plan)

# Test 8: passive → select only
mech = mk_unit(0, "PunchMech", 1, 1)
b = mk_board([mech])
a = mk_action(0, "PunchMech", (1, 1), "Passive_Electric", (-1, -1))
plan = plan_single_mech(a, b)
check("passive: 1 click (select only)", len(plan) == 1, plan)

# Test 9: secondary weapon → slot 2
mech = mk_unit(0, "PunchMech", 3, 4,
               weapon="Prime_Punchmech", weapon2="Brute_Tankmech")
b = mk_board([mech])
a = mk_action(0, "PunchMech", (3, 4), "Brute_Tankmech", (5, 4))
plan = plan_single_mech(a, b)
arm_click = next(c for c in plan if "Arm" in c["description"])
check("secondary weapon → slot 2",
      (arm_click["x"], arm_click["y"]) == _ui_weapon_slot_2(), arm_click)

# Test 10: end turn always emits exactly one click at the end-turn pos
plan = plan_end_turn()
check("end_turn: 1 click", len(plan) == 1, plan)
check("end_turn: at end-turn UI position",
      (plan[0]["x"], plan[0]["y"]) == _ui_end_turn())
check("end_turn: type is left_click", plan[0]["type"] == "left_click")

print(f"\n{passed}/{passed+failed} tests passed")
if failed:
    raise SystemExit(1)
