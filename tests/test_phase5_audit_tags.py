"""Phase 5 audit-mode tagging tests.

Covers:
1. RunSession round-trip preserves the tags field
2. RunSession.new_run accepts tags
3. count_fired_triggers filters records tagged "audit"
4. Audit records do not block normal records in count
"""
from src.loop.session import RunSession
from src.solver.tuner import count_fired_triggers


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


# Test 1: RunSession round-trip preserves tags
s = RunSession(run_id="r1", squad="Rift Walkers", tags=["audit"])
d = s.to_dict()
s2 = RunSession.from_dict(d)
check("RunSession round-trips tags", s2.tags == ["audit"], s2.tags)

# Test 2: new_run accepts tags
s3 = RunSession.new_run("Rift Walkers", tags=["audit", "experimental"])
check("new_run accepts tags",
      "audit" in s3.tags and "experimental" in s3.tags, s3.tags)

# Test 3: count_fired_triggers filters audit records
audit_records = [
    {
        "run_id": "audit_r1", "mission": 0, "trigger": "self_damage_building",
        "auto_fixable_by_tuning": True,
        "replay_file": "nonexistent.json",
        "context": {"tags": ["audit"]},
    },
]
n = count_fired_triggers({}, audit_records, time_limit=1.0)
check("count_fired_triggers skips audit records", n == 0, f"got {n}")

# Test 4: Audit records mixed with normal records — only normal counted
mixed_records = [
    {
        "run_id": "audit_r1", "mission": 0, "trigger": "self_damage_building",
        "auto_fixable_by_tuning": True,
        "replay_file": "nonexistent.json",
        "context": {"tags": ["audit"]},
    },
    {
        "run_id": "normal_r1", "mission": 0, "trigger": "self_damage_building",
        "auto_fixable_by_tuning": True,
        "replay_file": "nonexistent.json",
        "context": {},
    },
]
n = count_fired_triggers({}, mixed_records, time_limit=1.0)
check("count_fired_triggers counts only the normal record", n == 1, f"got {n}")

print(f"\n{passed}/{passed+failed} tests passed")
if failed:
    raise SystemExit(1)
