"""Read the pinned Windows build's native-only enemy-spawn inputs.

The ordinary Lua bridge can call ``Board:IsDangerous`` and
``Board:IsBlocked`` directly, but it has no getter for the Point-keyed
``BlockSpawn`` map or for the direct spawn-marker vector used by native spawn
validity.  This module reads those two structures out of process with a
query/read-only Windows handle.  It never writes game memory and never emits a
process address or pointer.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


ANALYSIS_KIND = "live_native_enemy_spawn_inputs"
CANDIDATE_REPLAY_ANALYSIS_KIND = "live_native_enemy_spawn_candidate_replay"
SCHEMA_VERSION = 1
EXPECTED_EXECUTABLE_SHA256 = (
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
)
EXPECTED_EXECUTABLE_SIZE = 5_530_112
EXPECTED_IMAGE_SIZE = 0x0056F000
EXPECTED_BUILD_ID = "13725832"

BOARD_PLAYER_VTABLE_RVA = 0x00430148
BOARD_PRIMARY_VTABLE_RVA = 0x0042E2FC
BOARD_SECONDARY_VTABLE_RVA = 0x0042E258
HOST_GLOBAL_RVA = 0x004B9CF8
HOST_GAME_APP_OFFSET = 0x18
GAME_APP_VTABLE_RVA = 0x00435014
GAME_APP_SCREEN_ROOT_OFFSET = 0x10
SCREEN_ROOT_VTABLE_RVA = 0x0043544C
SCREEN_ROOT_ACTIVE_SCREEN_OFFSET = 0xC204
BOARD_PLAYER_BOARD_OFFSET = 0x04
BOARD_PLAYER_STATE_OFFSET = 0x0FC8
BOARD_SECONDARY_VTABLE_OFFSET = 0x0C
BOARD_BLOCK_SPAWN_MAP_OFFSET = 0x7458
BOARD_SPAWN_VECTOR_BEGIN_OFFSET = 0x2D50
BOARD_SPAWN_VECTOR_END_OFFSET = 0x2D54
BOARD_SPAWN_VECTOR_CAPACITY_OFFSET = 0x2D58

TREE_LEFT_OFFSET = 0x00
TREE_PARENT_OFFSET = 0x04
TREE_RIGHT_OFFSET = 0x08
TREE_IS_NIL_OFFSET = 0x0D
TREE_POINT_X_OFFSET = 0x10
TREE_POINT_Y_OFFSET = 0x14
TREE_VALUE_OFFSET = 0x18
TREE_NODE_SIZE = 0x1C

MAX_USER_POINTER = 0x7FFF0000


class NativeSpawnInputReaderError(RuntimeError):
    """Raised when exact build identity or memory structure checks fail."""


class ProcessReader(Protocol):
    pid: int

    def read(self, address: int, size: int) -> bytes | None: ...


class ModuleLike(Protocol):
    base: int
    size: int
    path: str


def _read_exact(reader: ProcessReader, address: int, size: int, label: str) -> bytes:
    value = reader.read(address, size)
    if value is None or len(value) != size:
        raise NativeSpawnInputReaderError(f"could not read {label}")
    return value


def _u32(reader: ProcessReader, address: int, label: str) -> int:
    return struct.unpack("<I", _read_exact(reader, address, 4, label))[0]


def _i32_at(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def _valid_pointer(value: int) -> bool:
    return 0x00010000 <= value < MAX_USER_POINTER and value % 4 == 0


def _active_board_from_controller_chain(
    reader: ProcessReader,
    module: ModuleLike,
) -> tuple[int, int]:
    """Resolve the active Board through the exact pinned battle-controller chain."""
    host = _u32(reader, module.base + HOST_GLOBAL_RVA, "battle host singleton")
    if not _valid_pointer(host):
        raise NativeSpawnInputReaderError("battle host singleton is unavailable")

    game_app = _u32(reader, host + HOST_GAME_APP_OFFSET, "game app pointer")
    if not _valid_pointer(game_app):
        raise NativeSpawnInputReaderError("active game app is unavailable")
    if _u32(reader, game_app, "game app vtable") != module.base + GAME_APP_VTABLE_RVA:
        raise NativeSpawnInputReaderError("active game app identity differs")

    screen_root = _u32(
        reader,
        game_app + GAME_APP_SCREEN_ROOT_OFFSET,
        "screen root pointer",
    )
    if not _valid_pointer(screen_root):
        raise NativeSpawnInputReaderError("screen root is unavailable")
    if (
        _u32(reader, screen_root, "screen root vtable")
        != module.base + SCREEN_ROOT_VTABLE_RVA
    ):
        raise NativeSpawnInputReaderError("screen root identity differs")

    board_player = _u32(
        reader,
        screen_root + SCREEN_ROOT_ACTIVE_SCREEN_OFFSET,
        "active BoardPlayer pointer",
    )
    if not _valid_pointer(board_player):
        raise NativeSpawnInputReaderError("active BoardPlayer is unavailable")
    if (
        _u32(reader, board_player, "BoardPlayer vtable")
        != module.base + BOARD_PLAYER_VTABLE_RVA
    ):
        raise NativeSpawnInputReaderError("active BoardPlayer identity differs")

    state = _i32_at(
        _read_exact(
            reader,
            board_player + BOARD_PLAYER_STATE_OFFSET,
            4,
            "BoardPlayer state",
        ),
        0,
    )
    if not (0 <= state <= 6):
        raise NativeSpawnInputReaderError("active BoardPlayer state differs")
    board = _u32(
        reader,
        board_player + BOARD_PLAYER_BOARD_OFFSET,
        "BoardPlayer Board pointer",
    )
    if not _valid_pointer(board):
        raise NativeSpawnInputReaderError("active Board is unavailable")
    if _u32(reader, board, "Board primary vtable") != module.base + BOARD_PRIMARY_VTABLE_RVA:
        raise NativeSpawnInputReaderError("active Board primary identity differs")
    if (
        _u32(
            reader,
            board + BOARD_SECONDARY_VTABLE_OFFSET,
            "Board secondary vtable",
        )
        != module.base + BOARD_SECONDARY_VTABLE_RVA
    ):
        raise NativeSpawnInputReaderError("active Board secondary identity differs")
    return state, board


def _read_block_spawn_values(
    reader: ProcessReader,
    board: int,
) -> dict[tuple[int, int], int]:
    head = _u32(
        reader,
        board + BOARD_BLOCK_SPAWN_MAP_OFFSET,
        "BlockSpawn map head",
    )
    if not _valid_pointer(head):
        raise NativeSpawnInputReaderError("BlockSpawn map head is invalid")
    head_data = _read_exact(reader, head, TREE_NODE_SIZE, "BlockSpawn map sentinel")
    if head_data[TREE_IS_NIL_OFFSET] == 0:
        raise NativeSpawnInputReaderError("BlockSpawn map sentinel flag differs")
    root = struct.unpack_from("<I", head_data, TREE_PARENT_OFFSET)[0]
    if not _valid_pointer(root):
        raise NativeSpawnInputReaderError("BlockSpawn map root is invalid")

    values: dict[tuple[int, int], int] = {}
    visited: set[int] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node == head:
            continue
        if not _valid_pointer(node) or node in visited or len(visited) >= 64:
            raise NativeSpawnInputReaderError("BlockSpawn tree shape differs")
        visited.add(node)
        data = _read_exact(reader, node, TREE_NODE_SIZE, "BlockSpawn map node")
        if data[TREE_IS_NIL_OFFSET] != 0:
            raise NativeSpawnInputReaderError("BlockSpawn map node is nil")
        left = struct.unpack_from("<I", data, TREE_LEFT_OFFSET)[0]
        right = struct.unpack_from("<I", data, TREE_RIGHT_OFFSET)[0]
        x = _i32_at(data, TREE_POINT_X_OFFSET)
        y = _i32_at(data, TREE_POINT_Y_OFFSET)
        value = _i32_at(data, TREE_VALUE_OFFSET)
        point = (x, y)
        if not (0 <= x < 8 and 0 <= y < 8) or point in values:
            raise NativeSpawnInputReaderError("BlockSpawn map Point set differs")
        values[point] = value
        stack.extend((right, left))

    expected = {(x, y) for x in range(8) for y in range(8)}
    if set(values) != expected or len(visited) != 64:
        raise NativeSpawnInputReaderError(
            "BlockSpawn map does not cover the complete 8x8 Board"
        )
    return values


def _read_spawn_marker_vector(
    reader: ProcessReader,
    board: int,
) -> tuple[tuple[int, int], ...]:
    begin = _u32(
        reader,
        board + BOARD_SPAWN_VECTOR_BEGIN_OFFSET,
        "spawn-marker vector begin",
    )
    end = _u32(
        reader,
        board + BOARD_SPAWN_VECTOR_END_OFFSET,
        "spawn-marker vector end",
    )
    capacity = _u32(
        reader,
        board + BOARD_SPAWN_VECTOR_CAPACITY_OFFSET,
        "spawn-marker vector capacity",
    )
    if begin == end:
        if begin == 0:
            if capacity != 0:
                raise NativeSpawnInputReaderError(
                    "empty spawn-marker vector differs"
                )
        elif (
            not _valid_pointer(begin)
            or not _valid_pointer(capacity)
            or capacity < end
            or (capacity - begin) % 8 != 0
        ):
            raise NativeSpawnInputReaderError("empty spawn-marker vector differs")
        return ()
    if (
        not _valid_pointer(begin)
        or not _valid_pointer(end)
        or not _valid_pointer(capacity)
        or not (begin < end <= capacity)
        or (end - begin) % 8 != 0
        or (capacity - begin) % 8 != 0
    ):
        raise NativeSpawnInputReaderError("spawn-marker vector shape differs")
    count = (end - begin) // 8
    if count > 64:
        raise NativeSpawnInputReaderError("spawn-marker vector is oversized")
    data = _read_exact(reader, begin, count * 8, "spawn-marker vector")
    points = tuple(
        struct.unpack_from("<ii", data, index * 8)
        for index in range(count)
    )
    if (
        len(set(points)) != len(points)
        or any(not (0 <= x < 8 and 0 <= y < 8) for x, y in points)
    ):
        raise NativeSpawnInputReaderError("spawn-marker vector Points differ")
    return points


def capture_native_spawn_inputs_from_reader(
    reader: ProcessReader,
    module: ModuleLike,
    *,
    process_start_unix: float | None = None,
    captured_at: datetime | None = None,
) -> dict[str, Any]:
    """Capture native values after the caller has verified module identity."""
    if module.size != EXPECTED_IMAGE_SIZE:
        raise NativeSpawnInputReaderError("live Breach.exe image size differs")
    state, board = _active_board_from_controller_chain(reader, module)
    block_values = _read_block_spawn_values(reader, board)
    markers = _read_spawn_marker_vector(reader, board)
    state_after, board_after = _active_board_from_controller_chain(reader, module)
    block_values_after = _read_block_spawn_values(reader, board_after)
    markers_after = _read_spawn_marker_vector(reader, board_after)
    if board_after != board or state_after != state:
        raise NativeSpawnInputReaderError(
            "active Board changed during native spawn-input capture"
        )
    if block_values_after != block_values or markers_after != markers:
        raise NativeSpawnInputReaderError(
            "native spawn inputs changed during capture"
        )
    when = captured_at or datetime.now(tz=timezone.utc)
    ordered_values = [
        [x, y, block_values[(x, y)]]
        for x in range(8)
        for y in range(8)
    ]
    nonzero_values = [entry for entry in ordered_values if entry[2] != 0]
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": ANALYSIS_KIND,
        "build_identity": {
            "platform": "windows",
            "build_id": EXPECTED_BUILD_ID,
            "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
            "executable_size": EXPECTED_EXECUTABLE_SIZE,
            "image_size": EXPECTED_IMAGE_SIZE,
        },
        "process_identity": {
            "pid": int(reader.pid),
            "process_start_unix": (
                round(float(process_start_unix), 6)
                if process_start_unix is not None
                else None
            ),
        },
        "captured_at_utc": when.astimezone(timezone.utc).isoformat(),
        "current_snapshot_only": True,
        "board_player_state": state,
        "block_spawn_values_complete": True,
        "block_spawn_values": ordered_values,
        "nonzero_block_spawn_values": nonzero_values,
        "existing_spawn_marker_vector_complete": True,
        "existing_spawn_marker_vector": [[x, y] for x, y in markers],
        "integrity": {
            "active_board_resolution": "pinned_host_game_screen_chain",
            "active_board_stable_during_capture": True,
            "native_inputs_stable_during_capture": True,
            "validated_vtable_count": 5,
            "block_spawn_cell_count": len(block_values),
            "spawn_marker_count": len(markers),
            "process_access": "query_and_read_only",
            "game_memory_written": False,
            "addresses_or_pointers_published": False,
        },
    }


def _verify_executable(path: Path) -> None:
    try:
        if path.is_symlink() or not path.is_file():
            raise NativeSpawnInputReaderError("Breach.exe is not a regular file")
        data = path.read_bytes()
    except OSError as exc:
        raise NativeSpawnInputReaderError(f"could not read Breach.exe: {exc}") from exc
    if len(data) != EXPECTED_EXECUTABLE_SIZE:
        raise NativeSpawnInputReaderError("Breach.exe size differs")
    if hashlib.sha256(data).hexdigest() != EXPECTED_EXECUTABLE_SHA256:
        raise NativeSpawnInputReaderError("Breach.exe SHA-256 differs")


def _runtime_overlay_identity(executable: Path) -> dict[str, Any]:
    modloader = executable.parent / "scripts" / "modloader.lua"
    try:
        if modloader.is_symlink() or not modloader.is_file():
            return {"path": "scripts/modloader.lua", "present": False}
        before = modloader.stat()
        data = modloader.read_bytes()
        after = modloader.stat()
    except OSError as exc:
        raise NativeSpawnInputReaderError(
            f"could not read installed modloader.lua: {exc}"
        ) from exc
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(data) != before.st_size
    ):
        raise NativeSpawnInputReaderError(
            "installed modloader.lua changed while being read"
        )
    return {
        "path": "scripts/modloader.lua",
        "present": True,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def capture_live_native_spawn_inputs(pid: int | None = None) -> dict[str, Any]:
    """Open the live Windows process read-only and capture native inputs."""
    import os

    if os.name != "nt":
        raise NativeSpawnInputReaderError(
            "live native spawn-input capture requires Windows"
        )
    from scripts.itb_timer_memory_probe import (  # local import: Windows only
        WindowsProcessReader,
        _find_breach_pid_windows,
    )

    process_id = pid if pid is not None else _find_breach_pid_windows()
    if type(process_id) is not int or process_id <= 0:
        raise NativeSpawnInputReaderError("Breach.exe is not running")
    try:
        with WindowsProcessReader(process_id) as reader:
            module = reader.module("Breach.exe")
            if module is None:
                raise NativeSpawnInputReaderError("live Breach.exe module is unavailable")
            executable = Path(module.path)
            _verify_executable(executable)
            result = capture_native_spawn_inputs_from_reader(
                reader,
                module,
                process_start_unix=reader.process_start_time_unix(),
            )
            result["runtime_overlay_identity"] = _runtime_overlay_identity(
                executable
            )
            return result
    except NativeSpawnInputReaderError:
        raise
    except (OSError, RuntimeError) as exc:
        raise NativeSpawnInputReaderError(str(exc)) from exc


def block_spawn_mapping_from_capture(
    capture: Mapping[str, Any],
) -> dict[tuple[int, int], int]:
    """Validate and unpack a capture for candidate-boundary replay."""
    if not isinstance(capture, Mapping):
        raise NativeSpawnInputReaderError("native spawn capture must be a mapping")
    if (
        capture.get("schema_version") != SCHEMA_VERSION
        or capture.get("analysis_kind") != ANALYSIS_KIND
        or capture.get("current_snapshot_only") is not True
        or capture.get("block_spawn_values_complete") is not True
    ):
        raise NativeSpawnInputReaderError("native spawn capture header differs")
    raw = capture.get("block_spawn_values")
    if not isinstance(raw, list):
        raise NativeSpawnInputReaderError("BlockSpawn capture must be a list")
    values: dict[tuple[int, int], int] = {}
    for entry in raw:
        if (
            not isinstance(entry, list)
            or len(entry) != 3
            or any(type(value) is not int for value in entry)
        ):
            raise NativeSpawnInputReaderError("BlockSpawn capture entry differs")
        x, y, value = entry
        if not (0 <= x < 8 and 0 <= y < 8) or (x, y) in values:
            raise NativeSpawnInputReaderError("BlockSpawn capture Point set differs")
        values[(x, y)] = value
    if set(values) != {(x, y) for x in range(8) for y in range(8)}:
        raise NativeSpawnInputReaderError("BlockSpawn capture is incomplete")
    return values


def spawn_marker_points_from_capture(
    capture: Mapping[str, Any],
) -> tuple[tuple[int, int], ...]:
    if capture.get("existing_spawn_marker_vector_complete") is not True:
        raise NativeSpawnInputReaderError("spawn-marker vector capture is incomplete")
    raw = capture.get("existing_spawn_marker_vector")
    if not isinstance(raw, list):
        raise NativeSpawnInputReaderError("spawn-marker vector must be a list")
    points: list[tuple[int, int]] = []
    for entry in raw:
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or any(type(value) is not int for value in entry)
        ):
            raise NativeSpawnInputReaderError("spawn-marker Point differs")
        point = (entry[0], entry[1])
        if point in points or not (0 <= point[0] < 8 and 0 <= point[1] < 8):
            raise NativeSpawnInputReaderError("spawn-marker Point set differs")
        points.append(point)
    return tuple(points)


def _bridge_candidate_projection(
    bridge_data: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(bridge_data, Mapping):
        raise NativeSpawnInputReaderError("bridge state must be a mapping")
    return {
        "mission_id": bridge_data.get("mission_id"),
        "phase": bridge_data.get("phase"),
        "turn": bridge_data.get("turn"),
        "tiles": bridge_data.get("tiles"),
        "native_enemy_spawn_inputs": bridge_data.get(
            "native_enemy_spawn_inputs"
        ),
    }


def combine_current_bridge_native_capture(
    bridge_before: Mapping[str, Any],
    native_capture: Mapping[str, Any],
    bridge_after: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an exact current-pool replay from a stable bridge sandwich."""
    before_projection = _bridge_candidate_projection(bridge_before)
    after_projection = _bridge_candidate_projection(bridge_after)
    if before_projection != after_projection:
        raise NativeSpawnInputReaderError(
            "bridge spawn inputs changed during native capture"
        )
    expected_build_identity = {
        "platform": "windows",
        "build_id": EXPECTED_BUILD_ID,
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": EXPECTED_EXECUTABLE_SIZE,
        "image_size": EXPECTED_IMAGE_SIZE,
    }
    if native_capture.get("build_identity") != expected_build_identity:
        raise NativeSpawnInputReaderError("native capture build identity differs")
    overlay_identity = native_capture.get("runtime_overlay_identity")
    if not isinstance(overlay_identity, Mapping) or (
        overlay_identity.get("path") != "scripts/modloader.lua"
        or overlay_identity.get("present") is not True
        or type(overlay_identity.get("size")) is not int
        or overlay_identity.get("size", 0) <= 0
        or not isinstance(overlay_identity.get("sha256"), str)
        or len(overlay_identity.get("sha256", "")) != 64
    ):
        raise NativeSpawnInputReaderError("native capture overlay identity differs")
    integrity = native_capture.get("integrity")
    if not isinstance(integrity, Mapping) or (
        integrity.get("active_board_stable_during_capture") is not True
        or integrity.get("native_inputs_stable_during_capture") is not True
        or integrity.get("game_memory_written") is not False
    ):
        raise NativeSpawnInputReaderError("native capture integrity differs")

    from src.observatory.enemy_spawn_candidate_boundary import (
        EnemySpawnCandidateBoundaryError,
        replay_current_bridge_enemy_spawn_candidate_pool,
    )

    try:
        replay = replay_current_bridge_enemy_spawn_candidate_pool(
            before_projection,
            block_spawn_values=block_spawn_mapping_from_capture(native_capture),
            existing_spawn_marker_points=spawn_marker_points_from_capture(
                native_capture
            ),
        )
    except EnemySpawnCandidateBoundaryError as exc:
        raise NativeSpawnInputReaderError(str(exc)) from exc

    canonical = json.dumps(
        before_projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_kind": CANDIDATE_REPLAY_ANALYSIS_KIND,
        "build_identity": dict(native_capture["build_identity"]),
        "runtime_overlay_identity": dict(overlay_identity),
        "process_identity": native_capture.get("process_identity"),
        "captured_at_utc": native_capture.get("captured_at_utc"),
        "current_snapshot_only": True,
        "future_forecast": False,
        "bridge_state_identity": {
            "mission_id": before_projection["mission_id"],
            "phase": before_projection["phase"],
            "turn": before_projection["turn"],
            "projection_sha256": hashlib.sha256(canonical).hexdigest(),
            "before_timestamp": bridge_before.get("timestamp"),
            "after_timestamp": bridge_after.get("timestamp"),
            "stable_across_native_capture": True,
        },
        "bridge_input": before_projection,
        "native_input_capture": dict(native_capture),
        "candidate_replay": replay,
        "integrity": {
            "bridge_refresh_sandwich": True,
            "bridge_projection_stable": True,
            "native_board_stable": True,
            "native_inputs_stable": True,
            "future_forecast": False,
        },
    }


def validate_current_bridge_native_capture_artifact(
    artifact: Mapping[str, Any],
) -> dict[str, Any]:
    """Recompute and exactly match a serialized combined capture artifact."""
    if not isinstance(artifact, Mapping):
        raise NativeSpawnInputReaderError("combined capture must be a mapping")
    if (
        artifact.get("schema_version") != SCHEMA_VERSION
        or artifact.get("analysis_kind") != CANDIDATE_REPLAY_ANALYSIS_KIND
        or artifact.get("current_snapshot_only") is not True
        or artifact.get("future_forecast") is not False
    ):
        raise NativeSpawnInputReaderError("combined capture header differs")
    bridge_input = artifact.get("bridge_input")
    native_capture = artifact.get("native_input_capture")
    identity = artifact.get("bridge_state_identity")
    if not isinstance(bridge_input, Mapping) or not isinstance(identity, Mapping):
        raise NativeSpawnInputReaderError("combined capture inputs differ")
    before = dict(bridge_input)
    after = dict(bridge_input)
    before["timestamp"] = identity.get("before_timestamp")
    after["timestamp"] = identity.get("after_timestamp")
    expected = combine_current_bridge_native_capture(
        before,
        native_capture,
        after,
    )
    if dict(artifact) != expected:
        raise NativeSpawnInputReaderError(
            "combined capture does not match deterministic replay"
        )
    return expected
