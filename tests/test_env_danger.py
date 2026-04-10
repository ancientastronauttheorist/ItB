"""Phase 1 env_danger validation tests.

Tests:
1. Mech on lethal env_danger tile MUST move off (PunchMech-class fix)
2. Mech on non-lethal env_danger should also try to move off (1 dmg is bad)
3. Lethal env_danger kills ground enemies during enemy phase
4. Non-lethal env_danger damages ground enemies during enemy phase
5. Lethal env_danger kills flying enemies (air strike from above)
6. Non-lethal env_danger SKIPS flying enemies (tidal wave doesn't reach)
7. Backwards-compat: v1 env_danger only (no v2) defaults to lethal
"""
import json
import itb_solver

def make(env_v1=None, env_v2=None, mech_pos=(0,0), mech_move=1, mech_hp=3,
         enemy_pos=None, enemy_type='Scorpion1', flying=False):
    units = [{
        "uid": 0, "type": "PunchMech", "x": mech_pos[0], "y": mech_pos[1],
        "hp": mech_hp, "max_hp": mech_hp, "team": 1, "mech": True,
        "move": mech_move, "active": True, "weapons": ["Prime_Punchmech"]
    }]
    if enemy_pos:
        units.append({
            "uid": 1, "type": enemy_type, "x": enemy_pos[0], "y": enemy_pos[1],
            "hp": 2, "max_hp": 2, "team": 6, "mech": False,
            "move": 3, "active": False, "flying": flying,
            "weapons": [enemy_type + "Atk1"], "queued_target": [-1, -1]
        })
    board = {
        "grid_power": 5, "grid_power_max": 7, "turn": 1, "total_turns": 5,
        "tiles": [{"x": 0, "y": 0, "terrain": "building", "building_hp": 1}],
        "units": units, "spawning_tiles": [],
    }
    if env_v1: board["environment_danger"] = env_v1
    if env_v2: board["environment_danger_v2"] = env_v2
    return board

def solve(b):
    return json.loads(itb_solver.solve(json.dumps(b), 5.0))

passed = 0
failed = 0

# Test 1: Mech on lethal env tile must move
b = make(env_v2=[[4,4,99,1]], mech_pos=(4,4), mech_move=4)
r = solve(b)
mech_a = next((a for a in r['actions'] if a['mech_uid'] == 0), None)
move_to = tuple(mech_a['move_to']) if mech_a else None
if move_to and move_to != (4, 4):
    print(f"  PASS Test 1: Mech moved off lethal env (4,4) → {move_to}")
    passed += 1
else:
    print(f"  FAIL Test 1: Mech move_to={move_to}")
    failed += 1

# Test 2: Mech on non-lethal env tile should try to move (1 dmg is still bad)
b = make(env_v2=[[4,4,1,0]], mech_pos=(4,4), mech_move=4, mech_hp=1)  # 1 hp = death from 1 damage
r = solve(b)
mech_a = next((a for a in r['actions'] if a['mech_uid'] == 0), None)
move_to = tuple(mech_a['move_to']) if mech_a else None
if move_to and move_to != (4, 4):
    print(f"  PASS Test 2: 1HP mech moved off non-lethal env → {move_to}")
    passed += 1
else:
    print(f"  FAIL Test 2: 1HP mech move_to={move_to}")
    failed += 1

# Test 3: Lethal env kills ground enemy (delta should be ~+100 saving HP penalty)
no_env = solve(make(enemy_pos=(7,7), enemy_type='Scorpion1'))
with_env = solve(make(enemy_pos=(7,7), enemy_type='Scorpion1', env_v2=[[7,7,99,1]]))
delta = with_env['score'] - no_env['score']
if delta > 50:
    print(f"  PASS Test 3: Lethal env killed ground enemy (delta=+{delta:.0f})")
    passed += 1
else:
    print(f"  FAIL Test 3: delta={delta:.0f} (expected positive)")
    failed += 1

# Test 4: Non-lethal env damages ground enemy (delta should be positive — enemy on danger bonus + reduced HP)
with_env = solve(make(enemy_pos=(7,7), enemy_type='Scorpion1', env_v2=[[7,7,1,0]]))
delta = with_env['score'] - no_env['score']
if delta > 50:
    print(f"  PASS Test 4: Non-lethal env damaged ground enemy (delta=+{delta:.0f})")
    passed += 1
else:
    print(f"  FAIL Test 4: delta={delta:.0f}")
    failed += 1

# Test 5: Lethal env kills flying enemy (air strike)
no_env_fly = solve(make(enemy_pos=(7,7), enemy_type='Hornet1', flying=True))
with_env_fly = solve(make(enemy_pos=(7,7), enemy_type='Hornet1', flying=True, env_v2=[[7,7,99,1]]))
delta = with_env_fly['score'] - no_env_fly['score']
if delta > 50:
    print(f"  PASS Test 5: Lethal env killed flying enemy (delta=+{delta:.0f})")
    passed += 1
else:
    print(f"  FAIL Test 5: delta={delta:.0f}")
    failed += 1

# Test 6: Non-lethal env SKIPS flying enemy (tidal wave doesn't hit)
with_env_fly = solve(make(enemy_pos=(7,7), enemy_type='Hornet1', flying=True, env_v2=[[7,7,1,0]]))
delta = with_env_fly['score'] - no_env_fly['score']
if abs(delta) < 50:
    print(f"  PASS Test 6: Flying enemy survived non-lethal env (delta={delta:+.0f})")
    passed += 1
else:
    print(f"  FAIL Test 6: delta={delta:+.0f} (expected ~0)")
    failed += 1

# Test 7: Backwards compat — v1 only (no v2) defaults to lethal
b = make(env_v1=[[4,4]], mech_pos=(4,4), mech_move=4)
r = solve(b)
mech_a = next((a for a in r['actions'] if a['mech_uid'] == 0), None)
move_to = tuple(mech_a['move_to']) if mech_a else None
if move_to and move_to != (4, 4):
    print(f"  PASS Test 7: v1-only env_danger defaulted to lethal → mech moved to {move_to}")
    passed += 1
else:
    print(f"  FAIL Test 7: move_to={move_to}")
    failed += 1

print(f"\n{passed}/{passed+failed} tests passed")
exit(0 if failed == 0 else 1)
