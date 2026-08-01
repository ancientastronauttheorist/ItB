"""Bridge identity contract for the separately constructed native tutorial."""

from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _load_mission_bridge_id():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 tutorial identity harness requires lupa.lua51")
    source = MODLOADER.read_text()
    start = source.index("local function mission_bridge_id")
    end = source.index("\nlocal function dump_state()", start)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    helper = runtime.execute(source[start:end] + "\nreturn mission_bridge_id")
    return helper, runtime


def test_tutorial_without_create_mission_id_gets_exact_bridge_identity():
    helper, runtime = _load_mission_bridge_id()

    assert helper(runtime.table_from({"Name": "Tutorial"})) == "Mission_Tutorial"
    assert helper(runtime.table_from({"ID": "", "Name": "Tutorial"})) == (
        "Mission_Tutorial"
    )


def test_bridge_identity_preserves_explicit_ids_and_does_not_guess_other_names():
    helper, runtime = _load_mission_bridge_id()

    assert helper(
        runtime.table_from({"ID": "Mission_Wind", "Name": "Tutorial"})
    ) == "Mission_Wind"
    assert helper(runtime.table_from({"ID": "", "Name": "Other"})) == ""
    assert helper(None) is None


def test_dump_state_uses_normalized_identity_for_public_payload():
    source = MODLOADER.read_text()

    assert "local mission_id = mission_bridge_id(_ITB_CURRENT_MISSION)" in source
    assert "state.mission_id = mission_id" in source
