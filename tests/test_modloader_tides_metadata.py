from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _load_metadata_helpers():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Tides harness requires lupa.lua51")

    source = MODLOADER.read_text()
    start = source.index("local function mission_tides_index")
    end = source.index("\nlocal function dump_state()", start)
    helper = source[start:end]
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    index_helper, planned_helper = runtime.execute(
        helper + "\nreturn mission_tides_index, mission_tides_planned"
    )
    return index_helper, planned_helper, runtime


def test_tides_metadata_exports_exact_integer_index_for_inherited_missions():
    helper, _, runtime = _load_metadata_helpers()

    assert helper("Mission_Tides", runtime.table_from({"Index": 1})) == 1
    assert helper("Mission_Tides", runtime.table_from({"Index": 4})) == 4
    assert helper("Mission_Terratide", runtime.table_from({"Index": 4})) == 4


def test_tides_metadata_omits_unrelated_missions():
    helper, _, runtime = _load_metadata_helpers()

    assert helper("Mission_Wind", runtime.table_from({"Index": 4})) is None


def test_tides_metadata_rejects_missing_fractional_and_out_of_range_indices():
    helper, _, runtime = _load_metadata_helpers()

    assert helper("Mission_Tides", runtime.table_from({})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 0})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 2.5})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 9})) is None
    assert helper("Mission_Terratide", runtime.table_from({"Index": 0})) is None
    assert helper("Mission_Terratide", runtime.table_from({"Index": 9})) is None


def test_tides_metadata_exports_exact_planned_state_for_inherited_missions():
    _, helper, runtime = _load_metadata_helpers()

    assert helper(
        "Mission_Tides", runtime.table_from({"Planned": True})
    ) is True
    assert helper(
        "Mission_Terratide", runtime.table_from({"Planned": False})
    ) is False
    assert helper("Mission_Wind", runtime.table_from({"Planned": True})) is None
    assert helper("Mission_Tides", runtime.table_from({"Planned": 1})) is None


def test_modloader_serializes_only_the_mission_scoped_inherited_tides_index():
    source = MODLOADER.read_text()

    assert "state.environment_tides_index = index" in source
    assert "state.environment_tides_planned = planned" in source
    assert "state.environment_permanent_spawn_blocks" not in source
