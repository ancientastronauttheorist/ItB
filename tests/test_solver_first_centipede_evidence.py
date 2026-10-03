"""Check retained original return evidence, separately from Rust semantics."""

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data/solver_first/s1_centipede_order_evidence.json"


def _canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def _queue(event):
    summary = event["payload"]["primitive_summary"]
    assert summary["effect"] == []
    return [{field["name"]: field["value"] for field in entry["fields"]}
            for entry in summary["q_effect"]]


def _assert_return(event, expected):
    assert event["context"]["source"] == expected["function_id"]
    assert event["context"]["call_site"] == expected["call_site"]
    for key in ("mission_id", "phase", "turn"):
        assert event[key] == expected[key]
    for key in ("skill_id", "origin", "target"):
        assert event["payload"][key] == expected[key]
    assert _queue(event) == expected["q_effect"]
    assert all(len(fields) == 25 for fields in _queue(event))
    assert hashlib.sha256(_canonical(event["payload"]["primitive_summary"])).hexdigest() == expected["primitive_summary_sha256"]


def test_original_return_source_pins_and_repetition():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert len(evidence["source_pins"]) == 23
    traces = []
    for pin in evidence["source_pins"]:
        path = (ROOT / pin["path"]).resolve()
        assert path.is_relative_to(ROOT)
        raw = path.read_bytes()
        assert len(raw) == pin["size"]
        assert hashlib.sha256(raw).hexdigest() == pin["sha256"]
        if path.name == "exact_hook_trace.json":
            traces.append(json.loads(raw))
    assert len(traces) == 2
    expected = evidence["original_return"]
    for trace in traces:
        events = trace["events"]
        assert hashlib.sha256(_canonical(events)).hexdigest() == evidence["pairs"][0]["events_sha256"]
        event = next(event for event in events if event["seq"] == expected["seq"])
        _assert_return(event, expected)
        calls = [event for event in events if event["payload"].get("skill_id") == "CentipedeAtk2"]
        assert len(calls) == 48
        assert all(_queue(event) == expected["q_effect"] for event in calls)
    assert traces[0]["events"] == traces[1]["events"]
    assert evidence["accounting"]["distinct_return_scenarios"] == 1
    assert evidence["accounting"]["execution_transition_admissions"] == 0


@pytest.mark.parametrize("mutation", ["reverse_sides", "change_damage", "remove_acid"])
def test_original_queue_comparison_detects_perturbations(mutation):
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    expected = evidence["original_return"]
    pin = next(pin for pin in evidence["source_pins"] if pin["path"].endswith("get_skill_effect_pair002/exact_hook_trace.json"))
    trace = json.loads((ROOT / pin["path"]).read_bytes())
    event = next(event for event in trace["events"] if event["seq"] == expected["seq"])
    changed = event["payload"]["primitive_summary"]["q_effect"]
    if mutation == "reverse_sides":
        changed[1], changed[2] = changed[2], changed[1]
    else:
        field = next(field for field in changed[1]["fields"]
                     if field["name"] == ("iDamage" if mutation == "change_damage" else "iAcid"))
        field["value"] = field["value"] + 1 if mutation == "change_damage" else 0
    with pytest.raises(AssertionError):
        _assert_return(event, expected)
