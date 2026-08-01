from copy import deepcopy
from pathlib import Path

import pytest

from src.bridge.reader import _normalize_mission_hacking_ids
from src.model.board import Board

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _load_hacking_identity_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Mission_Hacking harness requires lupa.lua51")

    source = MODLOADER.read_text()
    start = source.index("local function mission_hacking_ids")
    end = source.index("\nlocal function dump_state()", start)
    helper = source[start:end]
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    return runtime.execute(
        helper + "\nreturn mission_hacking_ids"
    ), runtime


def _payload(**overrides):
    data = {
        "mission_id": "Mission_Hacking",
        "mission_hacking_bot_id": 41,
        "mission_hacking_hack_id": 40,
        "tiles": [],
        "units": [],
    }
    data.update(overrides)
    return data


def test_lua_hacking_identity_exports_only_a_complete_exact_pair():
    helper, runtime = _load_hacking_identity_helper()

    assert helper(
        "Mission_Hacking",
        runtime.table_from({"BotID": 41, "HackID": 40}),
    ) == (41, 40)

    invalid = [
        ("Mission_Wind", {"BotID": 41, "HackID": 40}),
        ("Mission_Hacking", {"BotID": 41}),
        ("Mission_Hacking", {"BotID": -1, "HackID": 40}),
        ("Mission_Hacking", {"BotID": 41.5, "HackID": 40}),
        ("Mission_Hacking", {"BotID": 40, "HackID": 40}),
        ("Mission_Hacking", {"BotID": 65536, "HackID": 40}),
    ]
    for mission_id, identity in invalid:
        assert helper(mission_id, runtime.table_from(identity)) == (None, None)


def test_modloader_serializes_the_hacking_identity_pair_together():
    source = MODLOADER.read_text()

    assert "local bot_id, hack_id = mission_hacking_ids(mission.ID, mission)" in source
    assert "state.mission_hacking_bot_id = bot_id" in source
    assert "state.mission_hacking_hack_id = hack_id" in source


@pytest.mark.parametrize(
    "overrides",
    [
        {"mission_id": "Mission_Wind"},
        {"mission_hacking_hack_id": None},
        {"mission_hacking_bot_id": -1},
        {"mission_hacking_bot_id": True},
        {"mission_hacking_bot_id": 41.5},
        {"mission_hacking_bot_id": 40},
        {"mission_hacking_bot_id": 65536},
    ],
)
def test_reader_drops_partial_or_malformed_hacking_identity(overrides):
    data = _payload(**overrides)

    _normalize_mission_hacking_ids(data)

    assert "mission_hacking_bot_id" not in data
    assert "mission_hacking_hack_id" not in data


def test_reader_keeps_a_valid_hacking_identity_pair():
    data = _payload()

    _normalize_mission_hacking_ids(data)

    assert data["mission_hacking_bot_id"] == 41
    assert data["mission_hacking_hack_id"] == 40


def test_python_board_import_and_copy_preserve_only_valid_hacking_identity():
    valid = Board.from_bridge_data(_payload())
    copied = valid.copy()

    assert (valid.mission_hacking_bot_id, valid.mission_hacking_hack_id) == (41, 40)
    assert (copied.mission_hacking_bot_id, copied.mission_hacking_hack_id) == (41, 40)

    invalid_payloads = [
        _payload(mission_id="Mission_Wind"),
        _payload(mission_hacking_hack_id=None),
        _payload(mission_hacking_bot_id=-1),
        _payload(mission_hacking_bot_id=40),
    ]
    for data in invalid_payloads:
        board = Board.from_bridge_data(deepcopy(data))
        assert board.mission_hacking_bot_id is None
        assert board.mission_hacking_hack_id is None
