from __future__ import annotations

import copy
import struct
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.observatory.native_spawn_input_reader import (
    ANALYSIS_KIND,
    BOARD_BLOCK_SPAWN_MAP_OFFSET,
    BOARD_PLAYER_BOARD_OFFSET,
    BOARD_PLAYER_STATE_OFFSET,
    BOARD_PLAYER_VTABLE_RVA,
    BOARD_PRIMARY_VTABLE_RVA,
    BOARD_SECONDARY_VTABLE_OFFSET,
    BOARD_SECONDARY_VTABLE_RVA,
    BOARD_SPAWN_VECTOR_BEGIN_OFFSET,
    BOARD_SPAWN_VECTOR_CAPACITY_OFFSET,
    BOARD_SPAWN_VECTOR_END_OFFSET,
    EXPECTED_IMAGE_SIZE,
    GAME_APP_SCREEN_ROOT_OFFSET,
    GAME_APP_VTABLE_RVA,
    HOST_GAME_APP_OFFSET,
    HOST_GLOBAL_RVA,
    NativeSpawnInputReaderError,
    SCREEN_ROOT_ACTIVE_SCREEN_OFFSET,
    SCREEN_ROOT_VTABLE_RVA,
    TREE_IS_NIL_OFFSET,
    TREE_NODE_SIZE,
    block_spawn_mapping_from_capture,
    capture_native_spawn_inputs_from_reader,
    spawn_marker_points_from_capture,
)


MODULE_BASE = 0x00400000
BOARD_PLAYER = 0x10000000
BOARD = 0x11000000
TREE = 0x12000000
VECTOR = 0x13000000
HOST = 0x14000000
GAME_APP = 0x15000000
SCREEN_ROOT = 0x16000000


class FakeReader:
    def __init__(self) -> None:
        self.pid = 4242
        self.segments: dict[int, bytearray] = {}

    def add(self, base: int, size: int) -> bytearray:
        value = bytearray(size)
        self.segments[base] = value
        return value

    def read(self, address: int, size: int) -> bytes | None:
        for base, data in self.segments.items():
            if base <= address and address + size <= base + len(data):
                offset = address - base
                return bytes(data[offset : offset + size])
        return None

    def regions(self, *, max_region_size: int) -> list[tuple[int, int, int]]:
        return [
            (base, len(data), 0x04)
            for base, data in sorted(self.segments.items())
            if len(data) <= max_region_size
        ]


def _put_u32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", data, offset, value)


def _put_i32(data: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<i", data, offset, value)


def _fixture() -> tuple[FakeReader, SimpleNamespace]:
    reader = FakeReader()
    board_player = reader.add(BOARD_PLAYER, 0x2000)
    board = reader.add(BOARD, 0x8000)
    tree = reader.add(TREE, 0x1000)
    vector = reader.add(VECTOR, 0x100)
    host_global = reader.add(MODULE_BASE + HOST_GLOBAL_RVA, 4)
    host = reader.add(HOST, 0x20)
    game_app = reader.add(GAME_APP, 0x80)
    screen_root = reader.add(SCREEN_ROOT, SCREEN_ROOT_ACTIVE_SCREEN_OFFSET + 4)

    _put_u32(host_global, 0, HOST)
    _put_u32(host, HOST_GAME_APP_OFFSET, GAME_APP)
    _put_u32(game_app, 0, MODULE_BASE + GAME_APP_VTABLE_RVA)
    _put_u32(game_app, GAME_APP_SCREEN_ROOT_OFFSET, SCREEN_ROOT)
    _put_u32(screen_root, 0, MODULE_BASE + SCREEN_ROOT_VTABLE_RVA)
    _put_u32(screen_root, SCREEN_ROOT_ACTIVE_SCREEN_OFFSET, BOARD_PLAYER)

    _put_u32(board_player, 0, MODULE_BASE + BOARD_PLAYER_VTABLE_RVA)
    _put_u32(board_player, BOARD_PLAYER_BOARD_OFFSET, BOARD)
    _put_i32(board_player, BOARD_PLAYER_STATE_OFFSET, 2)
    _put_u32(board, 0, MODULE_BASE + BOARD_PRIMARY_VTABLE_RVA)
    _put_u32(
        board,
        BOARD_SECONDARY_VTABLE_OFFSET,
        MODULE_BASE + BOARD_SECONDARY_VTABLE_RVA,
    )

    head = TREE
    tree[TREE_IS_NIL_OFFSET] = 1
    node_addresses = [TREE + 0x20 * (index + 1) for index in range(64)]

    def build(low: int, high: int, parent: int) -> int:
        if low >= high:
            return head
        middle = (low + high) // 2
        address = node_addresses[middle]
        offset = address - TREE
        left = build(low, middle, address)
        right = build(middle + 1, high, address)
        _put_u32(tree, offset + 0x00, left)
        _put_u32(tree, offset + 0x04, parent)
        _put_u32(tree, offset + 0x08, right)
        tree[offset + TREE_IS_NIL_OFFSET] = 0
        x, y = divmod(middle, 8)
        _put_i32(tree, offset + 0x10, x)
        _put_i32(tree, offset + 0x14, y)
        _put_i32(
            tree,
            offset + 0x18,
            1 if (x, y) == (1, 2) else 2 if (x, y) == (4, 5) else 0,
        )
        return address

    root = build(0, 64, head)
    _put_u32(tree, 0x00, node_addresses[0])
    _put_u32(tree, 0x04, root)
    _put_u32(tree, 0x08, node_addresses[-1])
    _put_u32(board, BOARD_BLOCK_SPAWN_MAP_OFFSET, head)

    struct.pack_into("<iiii", vector, 0, 6, 2, 7, 3)
    _put_u32(board, BOARD_SPAWN_VECTOR_BEGIN_OFFSET, VECTOR)
    _put_u32(board, BOARD_SPAWN_VECTOR_END_OFFSET, VECTOR + 16)
    _put_u32(board, BOARD_SPAWN_VECTOR_CAPACITY_OFFSET, VECTOR + 32)

    module = SimpleNamespace(
        base=MODULE_BASE,
        size=EXPECTED_IMAGE_SIZE,
        path=r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe",
    )
    return reader, module


def test_read_only_capture_recovers_all_cells_and_direct_marker_order():
    reader, module = _fixture()
    result = capture_native_spawn_inputs_from_reader(
        reader,
        module,
        process_start_unix=1000.25,
        captured_at=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert result["analysis_kind"] == ANALYSIS_KIND
    assert result["process_identity"] == {
        "pid": 4242,
        "process_start_unix": 1000.25,
    }
    assert result["captured_at_utc"] == "2026-08-29T12:00:00+00:00"
    assert result["board_player_state"] == 2
    assert len(result["block_spawn_values"]) == 64
    assert result["nonzero_block_spawn_values"] == [[1, 2, 1], [4, 5, 2]]
    assert result["existing_spawn_marker_vector"] == [[6, 2], [7, 3]]
    assert result["integrity"] == {
        "active_board_resolution": "pinned_host_game_screen_chain",
        "active_board_stable_during_capture": True,
        "native_inputs_stable_during_capture": True,
        "validated_vtable_count": 5,
        "block_spawn_cell_count": 64,
        "spawn_marker_count": 2,
        "process_access": "query_and_read_only",
        "game_memory_written": False,
        "addresses_or_pointers_published": False,
    }
    assert block_spawn_mapping_from_capture(result)[(4, 5)] == 2
    assert spawn_marker_points_from_capture(result) == ((6, 2), (7, 3))


def test_reader_ignores_unrelated_boardplayer_shaped_allocations():
    reader, module = _fixture()
    second = reader.add(0x17000000, 0x2000)
    _put_u32(second, 0, MODULE_BASE + BOARD_PLAYER_VTABLE_RVA)
    _put_u32(second, BOARD_PLAYER_BOARD_OFFSET, BOARD)
    _put_i32(second, BOARD_PLAYER_STATE_OFFSET, 2)

    result = capture_native_spawn_inputs_from_reader(reader, module)
    assert result["integrity"]["active_board_resolution"] == (
        "pinned_host_game_screen_chain"
    )


def test_reader_fails_closed_when_active_controller_chain_differs():
    reader, module = _fixture()
    screen_root = reader.segments[SCREEN_ROOT]
    _put_u32(screen_root, 0, MODULE_BASE + SCREEN_ROOT_VTABLE_RVA + 4)

    with pytest.raises(NativeSpawnInputReaderError, match="screen root identity"):
        capture_native_spawn_inputs_from_reader(reader, module)


def test_reader_fails_closed_on_partial_block_map_or_bad_marker_vector():
    reader, module = _fixture()
    tree = reader.segments[TREE]
    first_node = 0x20
    _put_i32(tree, first_node + 0x10, 8)
    with pytest.raises(NativeSpawnInputReaderError, match="Point set"):
        capture_native_spawn_inputs_from_reader(reader, module)

    reader, module = _fixture()
    board = reader.segments[BOARD]
    _put_u32(board, BOARD_SPAWN_VECTOR_END_OFFSET, VECTOR + 10)
    with pytest.raises(NativeSpawnInputReaderError, match="vector shape"):
        capture_native_spawn_inputs_from_reader(reader, module)

    reader, module = _fixture()
    board = reader.segments[BOARD]
    _put_u32(board, BOARD_SPAWN_VECTOR_BEGIN_OFFSET, 0)
    _put_u32(board, BOARD_SPAWN_VECTOR_END_OFFSET, 0)
    _put_u32(board, BOARD_SPAWN_VECTOR_CAPACITY_OFFSET, VECTOR)
    with pytest.raises(NativeSpawnInputReaderError, match="empty spawn-marker"):
        capture_native_spawn_inputs_from_reader(reader, module)


def test_capture_unpackers_reject_header_cell_and_marker_drift():
    reader, module = _fixture()
    result = capture_native_spawn_inputs_from_reader(reader, module)

    altered = copy.deepcopy(result)
    altered["current_snapshot_only"] = False
    with pytest.raises(NativeSpawnInputReaderError, match="header"):
        block_spawn_mapping_from_capture(altered)

    altered = copy.deepcopy(result)
    altered["block_spawn_values"].pop()
    with pytest.raises(NativeSpawnInputReaderError, match="incomplete"):
        block_spawn_mapping_from_capture(altered)

    altered = copy.deepcopy(result)
    altered["existing_spawn_marker_vector"].append([8, 0])
    with pytest.raises(NativeSpawnInputReaderError, match="Point"):
        spawn_marker_points_from_capture(altered)
