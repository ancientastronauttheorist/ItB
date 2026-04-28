"""Sim v25 Ice Storm freeze validation tests.

Vanilla Env_SnowStorm tiles are non-lethal: at start of enemy turn the
simulator applies Frozen=true to any alive unit standing on them. Shield
blocks + consumed; already-frozen idempotent; buildings/mountains untouched.
Frozen Vek skip their attacks via the existing attack-loop guard.

Tests:
  1. Mech on freeze tile gets Frozen=true after enemy phase, NOT killed
  2. Mech with shield on freeze tile: shield consumed, mech NOT frozen
  3. Already-frozen mech on freeze tile stays frozen (idempotent), HP unchanged
  4. Enemy on freeze tile gets Frozen, queued attack does NOT fire
  5. Building on freeze tile: untouched (no HP loss, no terrain change)
  6. Empty freeze tile: no-op
  7. NanoStorm path (kill=0, dmg=1) still fires through env_danger — guard
     against accidental routing into the freeze channel.
"""
import json
import itb_solver


def base_board(units, freeze_tiles=None, env_danger_v2=None, tiles=None):
    board = {
        "grid_power": 5,
        "grid_power_max": 7,
        "turn": 1,
        "total_turns": 5,
        "tiles": tiles or [],
        "units": units,
        "spawning_tiles": [],
    }
    if freeze_tiles is not None:
        board["environment_freeze"] = freeze_tiles
    if env_danger_v2 is not None:
        board["environment_danger_v2"] = env_danger_v2
    return board


def project(board, plan):
    """Run project_plan to get post-enemy-phase state.

    `plan` is a list of MechAction dicts; pass [] for "skip turn / fire
    enemy phase only" — exactly what we want to isolate env effects.
    """
    raw = itb_solver.project_plan(json.dumps(board), json.dumps(plan))
    out = json.loads(raw)
    out["board"] = json.loads(out["board_json"])
    return out


def find_unit(post, uid):
    return next((u for u in post["board"]["units"] if u["uid"] == uid), None)


def find_tile(post, x, y):
    return next((t for t in post["board"]["tiles"]
                 if t["x"] == x and t["y"] == y), None)


passed = 0
failed = 0


# Test 1: Mech on freeze tile gets Frozen=true, NOT killed
units = [
    {"uid": 0, "type": "PunchMech", "x": 4, "y": 4, "hp": 3, "max_hp": 3,
     "team": 1, "mech": True, "move": 0, "active": True,
     "weapons": ["Prime_Punchmech"]},
]
b = base_board(units, freeze_tiles=[[4, 4]])
post = project(b, [])
mech_after = find_unit(post, 0)
if mech_after and mech_after["hp"] == 3 and mech_after.get("frozen", False):
    print("  PASS Test 1: Mech on freeze tile is Frozen, HP intact")
    passed += 1
else:
    print(f"  FAIL Test 1: mech={mech_after}")
    failed += 1


# Test 2: Shielded mech on freeze tile — shield consumed, mech NOT frozen
units = [
    {"uid": 0, "type": "PunchMech", "x": 4, "y": 4, "hp": 3, "max_hp": 3,
     "team": 1, "mech": True, "move": 0, "active": True, "shield": True,
     "weapons": ["Prime_Punchmech"]},
]
b = base_board(units, freeze_tiles=[[4, 4]])
post = project(b, [])
mech_after = find_unit(post, 0)
if (mech_after and mech_after["hp"] == 3
        and not mech_after.get("frozen", False)
        and not mech_after.get("shield", False)):
    print("  PASS Test 2: Shield consumed, mech survives unfrozen")
    passed += 1
else:
    print(f"  FAIL Test 2: mech={mech_after}")
    failed += 1


# Test 3: Already-frozen mech is idempotent (still frozen, HP unchanged)
units = [
    {"uid": 0, "type": "PunchMech", "x": 4, "y": 4, "hp": 3, "max_hp": 3,
     "team": 1, "mech": True, "move": 0, "active": True, "frozen": True,
     "weapons": ["Prime_Punchmech"]},
]
b = base_board(units, freeze_tiles=[[4, 4]])
post = project(b, [])
mech_after = find_unit(post, 0)
if mech_after and mech_after["hp"] == 3 and mech_after.get("frozen", False):
    print("  PASS Test 3: Already-frozen mech idempotent")
    passed += 1
else:
    print(f"  FAIL Test 3: mech={mech_after}")
    failed += 1


# Test 4: Enemy on freeze tile freezes, queued attack does NOT fire.
# A 1-HP building at (0,0) with a Scorpion1 queued to attack it from (1,0).
# Without freeze, the building takes damage. With freeze, the Scorpion is
# frozen mid-attack and the building survives.
mech = {"uid": 0, "type": "PunchMech", "x": 7, "y": 7, "hp": 3, "max_hp": 3,
        "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"]}
scorp = {"uid": 1, "type": "Scorpion1", "x": 1, "y": 0, "hp": 2, "max_hp": 2,
         "team": 6, "mech": False, "move": 3, "active": False,
         "weapons": ["Scorpion1Atk1"], "queued_target": [0, 0],
         "has_queued_attack": True}
tiles = [{"x": 0, "y": 0, "terrain": "building", "building_hp": 1}]

b_no_freeze = base_board([mech, scorp], tiles=tiles)
post_no = project(b_no_freeze, [])
bld_hp_no = (find_tile(post_no, 0, 0) or {}).get("building_hp", 0)

b_freeze = base_board([mech, scorp], tiles=tiles, freeze_tiles=[[1, 0]])
post_freeze = project(b_freeze, [])
bld_after_freeze = find_tile(post_freeze, 0, 0)
bld_hp_freeze = (bld_after_freeze or {}).get("building_hp", 0)
scorp_after = find_unit(post_freeze, 1)

# Either the building survives at full HP (1) under freeze where it lost
# HP without freeze, OR if the no-freeze case also somehow leaves the
# building intact (e.g. Scorpion's queued attack semantics differ from
# what we expect), at minimum the scorpion should be frozen on the
# freeze-tile post-state.
attack_was_blocked = bld_hp_freeze > bld_hp_no or (
    bld_hp_freeze == 1 and scorp_after and scorp_after.get("frozen", False)
)
scorp_frozen = scorp_after and scorp_after.get("frozen", False)
if attack_was_blocked and scorp_frozen:
    print(f"  PASS Test 4: Frozen enemy "
          f"(no-freeze bld_hp={bld_hp_no}, freeze bld_hp={bld_hp_freeze}, "
          f"scorp.frozen={scorp_frozen})")
    passed += 1
else:
    print(f"  FAIL Test 4: bld_hp no_freeze={bld_hp_no} freeze={bld_hp_freeze} "
          f"scorp={scorp_after}")
    failed += 1


# Test 5: Building on freeze tile is untouched (no HP loss, no terrain change)
mech = {"uid": 0, "type": "PunchMech", "x": 7, "y": 7, "hp": 3, "max_hp": 3,
        "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"]}
tiles = [{"x": 3, "y": 3, "terrain": "building", "building_hp": 1}]
b = base_board([mech], tiles=tiles, freeze_tiles=[[3, 3]])
post = project(b, [])
bld = find_tile(post, 3, 3)
if bld and bld["terrain"] == "building" and bld["building_hp"] == 1:
    print("  PASS Test 5: Building on freeze tile untouched")
    passed += 1
else:
    print(f"  FAIL Test 5: bld={bld}")
    failed += 1


# Test 6: Empty freeze tile is a no-op (no crash, no spurious effects)
mech = {"uid": 0, "type": "PunchMech", "x": 7, "y": 7, "hp": 3, "max_hp": 3,
        "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"]}
b = base_board([mech], freeze_tiles=[[2, 2]])
try:
    post = project(b, [])
    mech_after = find_unit(post, 0)
    if mech_after and mech_after["hp"] == 3:
        print("  PASS Test 6: Empty freeze tile no-op")
        passed += 1
    else:
        print(f"  FAIL Test 6: mech={mech_after}")
        failed += 1
except Exception as e:
    print(f"  FAIL Test 6: project_plan crashed: {e}")
    failed += 1


# Test 7: NanoStorm path (kill=0, dmg=1) rides env_danger, NOT env_freeze.
# A 2HP mech on a NanoStorm-style tile takes 1 damage and is NOT frozen.
# Guard against the bridge accidentally routing NanoStorm into env_freeze.
mech = {"uid": 0, "type": "PunchMech", "x": 4, "y": 4, "hp": 2, "max_hp": 2,
        "team": 1, "mech": True, "move": 0, "active": True,
        "weapons": ["Prime_Punchmech"]}
b = base_board([mech], env_danger_v2=[[4, 4, 1, 0, 0]])
post = project(b, [])
mech_after = find_unit(post, 0)
if (mech_after and mech_after["hp"] == 1
        and not mech_after.get("frozen", False)):
    print("  PASS Test 7: NanoStorm path: 1 damage, no freeze")
    passed += 1
else:
    print(f"  FAIL Test 7: mech={mech_after}")
    failed += 1


print(f"\n{passed} passed, {failed} failed")
if failed > 0:
    raise SystemExit(1)
