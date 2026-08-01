from pathlib import Path

import pytest

try:
    from lupa import lua51
except ImportError:  # pragma: no cover - optional local test dependency
    lua51 = None


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _load_terraform_grass_helper():
    if lua51 is None:
        pytest.skip("exact Lua 5.1 Terraformer harness requires lupa.lua51")

    source = MODLOADER.read_text()
    start = source.index("local function mission_terraform_grass_tiles")
    end = source.index("\n-- Exact identity for Mission_Hacking", start)
    runtime = lua51.LuaRuntime(unpack_returned_tuples=True)
    helper = runtime.execute(
        source[start:end] + "\nreturn mission_terraform_grass_tiles"
    )
    return helper, runtime


def _fake_board(runtime, points):
    lua_points = runtime.table()
    for index, (x, y, custom) in enumerate(points, start=1):
        lua_points[index] = runtime.table_from(
            {"x": x, "y": y, "custom": custom}
        )
    make_board = runtime.execute(
        """
        return function(points)
            local zone = {}
            function zone:size() return #points end
            function zone:index(i) return points[i] end

            local board = {}
            function board:GetZone(name)
                if name ~= "grass" then error("wrong zone") end
                return zone
            end
            function board:GetCustomTile(point)
                return point.custom
            end
            return board
        end
        """
    )
    return make_board(lua_points)


def _coordinates(lua_table):
    return [
        (lua_table[index][1], lua_table[index][2])
        for index in range(1, len(lua_table) + 1)
    ]


def test_terraform_grass_helper_exports_only_live_custom_points_in_zone():
    helper, runtime = _load_terraform_grass_helper()
    board = _fake_board(runtime, [
        (7, 3, "ground_grass.png"),
        (2, 5, ""),
        (1, 1, "ground_grass.png"),
        (7, 3, "ground_grass.png"),
    ])

    result = helper("Mission_Terraform", board)

    assert _coordinates(result) == [(1, 1), (7, 3)]
    assert helper("Mission_Wind", board) is None


def test_terraform_grass_helper_distinguishes_authoritative_empty_from_failure():
    helper, runtime = _load_terraform_grass_helper()

    result = helper("Mission_Terraform", _fake_board(runtime, []))

    assert result is not None
    assert len(result) == 0
    malformed = _fake_board(runtime, [(8, 1, "ground_grass.png")])
    assert helper("Mission_Terraform", malformed) is None


def test_modloader_serializes_authoritative_terraform_grass_remainder():
    source = MODLOADER.read_text()

    assert "state.terraform_grass_live = true" in source
    assert "state.terraform_grass_tiles = terraform_grass_tiles" in source
    assert "tile.grass = true" in source
