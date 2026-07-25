from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _load_metadata_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Tides harness requires lupa.lua51")

    source = MODLOADER.read_text()
    start = source.index("local function mission_tides_index")
    end = source.index("\nlocal function dump_state()", start)
    helper = source[start:end]
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    return runtime.execute(
        helper + "\nreturn mission_tides_index"
    ), runtime


def test_tides_metadata_exports_exact_integer_index():
    helper, runtime = _load_metadata_helper()

    assert helper("Mission_Tides", runtime.table_from({"Index": 1})) == 1
    assert helper("Mission_Tides", runtime.table_from({"Index": 4})) == 4


def test_tides_metadata_omits_terratide_and_other_missions():
    helper, runtime = _load_metadata_helper()

    assert helper(
        "Mission_Terratide",
        runtime.table_from({"Index": 4}),
    ) is None
    assert helper("Mission_Wind", runtime.table_from({"Index": 4})) is None


def test_tides_metadata_rejects_missing_fractional_and_out_of_range_indices():
    helper, runtime = _load_metadata_helper()

    assert helper("Mission_Tides", runtime.table_from({})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 0})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 2.5})) is None
    assert helper("Mission_Tides", runtime.table_from({"Index": 9})) is None


def test_modloader_serializes_only_the_mission_scoped_tides_index():
    source = MODLOADER.read_text()

    assert "state.environment_tides_index = index" in source
    assert "state.environment_permanent_spawn_blocks" not in source
