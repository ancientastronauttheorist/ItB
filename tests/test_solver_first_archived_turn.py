"""Archive admission and original-observation comparison sensitivity.

These test the grader, not a separate combat model or original engine replay.
"""
from copy import deepcopy

import pytest

from src.observatory.solver_first_archived_turn import compare_projection, load_trials, read_pinned


@pytest.fixture(scope="module")
def trials():
    return load_trials()[0]


def test_rejects_modified_source_and_escape(tmp_path):
    (tmp_path / "source.json").write_text('{"value":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="source identity differs"):
        read_pinned(tmp_path, "source.json", "0" * 64)
    with pytest.raises(ValueError, match="escapes repository"):
        read_pinned(tmp_path, "../source.json", "0" * 64)


@pytest.mark.parametrize("fault", ["hp", "terrain", "active"])
def test_original_projection_detects_perturbations(trials, fault):
    original = trials[0]["actual"]
    candidate = deepcopy(original)
    if fault == "terrain":
        next(t for t in candidate["tiles"] if (t["x"], t["y"]) == (3, 3))["terrain"] = "ground"
    else:
        actor = next(u for u in candidate["units"] if u["uid"] == 0)
        actor[fault] = 3 if fault == "hp" else False
    result = compare_projection(trials[0]["before"], candidate, original)
    assert len(result["mismatches"]) == 1
    assert result["mismatches"][0]["field"] == fault
    assert not result["full_state_equivalence"]


def test_missing_actual_getter_is_not_a_match(trials):
    actual = deepcopy(trials[0]["actual"])
    del actual["units"][0]["active"]
    with pytest.raises(ValueError, match="direct actor field missing"):
        compare_projection(trials[0]["before"], trials[0]["actual"], actual)


def test_incomplete_tile_observation_is_rejected(trials):
    actual = deepcopy(trials[0]["actual"])
    actual["tiles"].pop()
    with pytest.raises(ValueError, match="terrain observation incomplete"):
        compare_projection(trials[0]["before"], trials[0]["actual"], actual)


def test_omitted_actual_status_stays_unknown(trials):
    actual = trials[0]["actual"]
    candidate = deepcopy(actual)
    next(t for t in candidate["tiles"] if (t["x"], t["y"]) == (3, 1))["acid"] = True
    result = compare_projection(trials[0]["before"], candidate, actual)
    diff = next(d for d in result["ungraded_endpoint_differences"] if d.get("tile") == [3, 1] and d["field"] == "acid")
    assert diff["actual"] is None and diff["actual_exported"] is False


def test_phase_without_active_actor_does_not_admit_decision_state(trials):
    assert [compare_projection(t["before"], t["actual"], t["actual"])["next_decision_ready"] for t in trials] == [True, False, False]
