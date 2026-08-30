"""Bridge IPC protocol — file paths, polling, and synchronization.

The Lua bridge communicates via files in /tmp/:
  - itb_state.json: Game state (Lua writes, Python reads)
  - itb_cmd.txt:    Commands (Python writes, Lua reads)
  - itb_ack.txt:    Acknowledgments (Lua writes, Python reads)
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from src.itb_paths import get_bridge_dir

BRIDGE_DIR = get_bridge_dir()
STATE_FILE = BRIDGE_DIR / "itb_state.json"
STATE_TMP = BRIDGE_DIR / "itb_state.json.tmp"
CMD_FILE = BRIDGE_DIR / "itb_cmd.txt"
CMD_TMP = BRIDGE_DIR / "itb_cmd.txt.tmp"
ACK_FILE = BRIDGE_DIR / "itb_ack.txt"
LOG_FILE = BRIDGE_DIR / "itb_bridge.log"
HEARTBEAT_FILE = BRIDGE_DIR / "itb_bridge_heartbeat"
CALLBACK_MANIFEST_FILE = BRIDGE_DIR / "itb_observatory_callback_manifest.json"
CALLBACK_MANIFEST_TMP = BRIDGE_DIR / "itb_observatory_callback_manifest.json.tmp"
CALLBACK_MANIFEST_REQUEST_FILE = (
    BRIDGE_DIR / "itb_observatory_callback_manifest.request"
)
CALLBACK_MANIFEST_REQUEST_TOKEN = "observatory-callback-manifest-request/1"
CALLBACK_MANIFEST_REQUEST_BYTES = (
    CALLBACK_MANIFEST_REQUEST_TOKEN + "\n"
).encode("ascii")
CALLBACK_BINDINGS_FILE = BRIDGE_DIR / "itb_observatory_callback_bindings.json"
CALLBACK_BINDINGS_TMP = BRIDGE_DIR / "itb_observatory_callback_bindings.json.tmp"
CALLBACK_BINDINGS_REQUEST_FILE = (
    BRIDGE_DIR / "itb_observatory_callback_bindings.request"
)
CALLBACK_BINDINGS_REQUEST_TOKEN = "observatory-callback-bindings-request/1"
CALLBACK_BINDINGS_REQUEST_BYTES = (
    CALLBACK_BINDINGS_REQUEST_TOKEN + "\n"
).encode("ascii")
NATIVE_CONTINUE_REQUEST_FILE = (
    BRIDGE_DIR / "itb_observatory_native_continue.request"
)
NATIVE_CONTINUE_REQUEST_TOKEN = "observatory-native-continue-request/1"
NATIVE_CONTINUE_REQUEST_BYTES = (
    NATIVE_CONTINUE_REQUEST_TOKEN + "\n"
).encode("ascii")
NATIVE_RNG_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_native_rng_snapshot.json"
)
NATIVE_RNG_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_native_rng_snapshot.json.tmp"
)
SPAWN_SPAN_LEDGER_FILE = (
    BRIDGE_DIR / "itb_observatory_spawn_span_ledger.json"
)
SPAWN_SPAN_LEDGER_TMP = (
    BRIDGE_DIR / "itb_observatory_spawn_span_ledger.json.tmp"
)
SPAWN_REPLAY_LEDGER_FILE = (
    BRIDGE_DIR / "itb_observatory_spawn_replay_ledger.json"
)
SPAWN_REPLAY_LEDGER_TMP = (
    BRIDGE_DIR / "itb_observatory_spawn_replay_ledger.json.tmp"
)
SELECTED_QUEUE_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_selected_queue_snapshot.json"
)
SELECTED_QUEUE_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_selected_queue_snapshot.json.tmp"
)
ENEMY_TOURNAMENT_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_enemy_tournament_snapshot.json"
)
ENEMY_TOURNAMENT_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_enemy_tournament_snapshot.json.tmp"
)
ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_enemy_materialized_effect_snapshot.json"
)
ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_enemy_materialized_effect_snapshot.json.tmp"
)
ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_enemy_materialized_effect_rejected_snapshot.json"
)
ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_enemy_materialized_effect_rejected_snapshot.json.tmp"
)
SCORE_POSITIONING_X87_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_score_positioning_x87_snapshot.json"
)
SCORE_POSITIONING_X87_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_score_positioning_x87_snapshot.json.tmp"
)
SPAWN_COORDINATE_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_spawn_coordinate_snapshot.json"
)
SPAWN_COORDINATE_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_spawn_coordinate_snapshot.json.tmp"
)
SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE = (
    BRIDGE_DIR / "itb_observatory_spawn_coordinate_capsule_snapshot.json"
)
SPAWN_COORDINATE_CAPSULE_SNAPSHOT_TMP = (
    BRIDGE_DIR / "itb_observatory_spawn_coordinate_capsule_snapshot.json.tmp"
)
_OBSERVATORY_CAPTURE_ID_RE = re.compile(
    r"[a-z][a-z0-9_.-]{0,95}\Z"
)
OBSERVATORY_NATIVE_RNG_SEED = 324_508_639

# State file must be newer than this many seconds
STALENESS_THRESHOLD = 300.0  # 5 minutes

# Command sequence counter for ACK correlation
_seq_counter = 0


class BridgeError(Exception):
    """Raised when the bridge returns an ERROR ACK."""
    pass


def is_bridge_active() -> bool:
    """Check if the Lua bridge is running.

    Checks two things:
    1. Bridge log file exists (written on game startup)
    2. State file exists (written when in a mission)
    """
    if not LOG_FILE.exists():
        return False
    state_mtime = _newest_state_mtime()
    if state_mtime is None:
        return False
    # State file must not be ancient unless the heartbeat proves the Lua
    # bridge is still ticking. On island-map screens the bridge may not dump
    # combat JSON until prompted, but a fresh heartbeat means refresh can work.
    age = time.time() - state_mtime
    if age < STALENESS_THRESHOLD:
        return True
    return is_bridge_alive(max_stale_sec=5.0)


def _state_candidates() -> list[Path]:
    return [p for p in (STATE_FILE, STATE_TMP) if p.exists()]


def _state_candidates_newest_first() -> list[Path]:
    candidates: list[tuple[float, Path]] = []
    for path in _state_candidates():
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            # The bridge writes the tmp file atomically and may rename/remove it
            # between the exists() check and stat(); ignore that transient race.
            continue
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates]


def _newest_state_path() -> Path | None:
    candidates = _state_candidates_newest_first()
    if not candidates:
        return None
    return candidates[0]


def _newest_state_mtime() -> float | None:
    for path in _state_candidates_newest_first():
        try:
            return path.stat().st_mtime
        except OSError:
            # The newest candidate can still disappear after sorting if the
            # bridge renames/removes the tmp file between calls.
            continue
    return None


def _read_json_file(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return None


def is_bridge_alive(max_stale_sec: float = 5.0) -> bool:
    """Check if the Lua bridge heartbeat is fresh (game loop is ticking).

    The heartbeat file is written every BaseUpdate tick by modloader.lua.
    If it's stale, the bridge is stuck or the game has closed.
    """
    try:
        if not HEARTBEAT_FILE.exists():
            return False
        age = time.time() - HEARTBEAT_FILE.stat().st_mtime
        return age < max_stale_sec
    except OSError:
        return False


def refresh_bridge_state() -> bool:
    """Request a fresh state dump from the bridge.

    Sends a no-op LUA command which triggers dump_state() as a side effect.
    Returns True if state was refreshed.
    """
    write_command("LUA return 'refresh'")
    try:
        wait_for_ack(timeout=5.0)
        return True
    except (TimeoutError, BridgeError):
        return False


def refresh_bridge_state_fresh(timeout: float = 2.0) -> bool:
    """Request a dump and wait until a new readable state generation lands.

    The Lua command handler writes its ACK immediately before ``dump_state``.
    Waiting only for the ACK can therefore race and reread the previous JSON.
    Capture every state candidate's file generation before the command, then
    require a changed, parseable candidate after the ACK.
    """

    def generations() -> dict[str, tuple[int, int]]:
        observed: dict[str, tuple[int, int]] = {}
        for path in (STATE_FILE, STATE_TMP):
            try:
                stat = path.stat()
            except OSError:
                continue
            observed[str(path)] = (stat.st_mtime_ns, stat.st_size)
        return observed

    before = generations()
    if refresh_bridge_state() is not True:
        return False
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        after = generations()
        for path_text, generation in after.items():
            if before.get(path_text) == generation:
                continue
            if _read_json_file(Path(path_text)) is not None:
                return True
        time.sleep(0.02)
    return False


def _file_generation(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _cancel_pending_command(expected: str) -> bool:
    """Remove only the still-pending command generation we wrote."""
    try:
        if CMD_FILE.read_text(encoding="utf-8") != expected:
            return False
        CMD_FILE.unlink()
    except FileNotFoundError:
        return False
    except OSError:
        return False
    return True


def request_observatory_callback_manifest(
    timeout: float = 10.0,
) -> tuple[str, dict]:
    """Request one fresh, read-only runtime callback manifest.

    The Lua bridge publishes the potentially large JSON document atomically to
    a dedicated result file before sending a short ACK.  Requiring a changed
    file generation prevents a successful ACK from ever reusing stale output.
    """
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "callback manifest requires an unpaused active mission heartbeat"
        )
    before = _file_generation(CALLBACK_MANIFEST_FILE)
    write_command("OBS_CALLBACK_MANIFEST")
    pending_command = f"#{_seq_counter} OBS_CALLBACK_MANIFEST"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_CALLBACK_MANIFEST roots=(\d+) functions=(\d+)", ack
    )
    if match is None:
        raise BridgeError(f"unexpected callback manifest ACK: {ack}")
    expected_roots = int(match.group(1))
    expected_functions = int(match.group(2))

    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(CALLBACK_MANIFEST_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            payload = json.loads(
                CALLBACK_MANIFEST_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"callback manifest result is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise BridgeError("callback manifest result must be a JSON object")
        summary = payload.get("summary")
        if not isinstance(summary, dict) or (
            summary.get("root_count") != expected_roots
            or summary.get("function_count") != expected_functions
        ):
            raise BridgeError(
                "callback manifest result does not match its ACK summary"
            )
        return ack, payload
    raise TimeoutError(
        f"Fresh callback manifest result timeout after {timeout:.0f}s"
    )


def request_observatory_callback_bindings(
    timeout: float = 15.0,
) -> tuple[str, dict]:
    """Request one fresh, inert callback-slot manifest."""
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "callback bindings require an unpaused active mission heartbeat"
        )
    before = _file_generation(CALLBACK_BINDINGS_FILE)
    write_command("OBS_CALLBACK_BINDINGS")
    pending_command = f"#{_seq_counter} OBS_CALLBACK_BINDINGS"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_CALLBACK_BINDINGS roots=(\d+) functions=(\d+) slots=(\d+)",
        ack,
    )
    if match is None:
        raise BridgeError(f"unexpected callback bindings ACK: {ack}")
    expected_roots, expected_functions, expected_slots = map(int, match.groups())
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(CALLBACK_BINDINGS_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            payload = json.loads(CALLBACK_BINDINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"callback bindings result is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise BridgeError("callback bindings result must be a JSON object")
        summary = payload.get("summary")
        if not isinstance(summary, dict) or (
            summary.get("root_count") != expected_roots
            or summary.get("function_count") != expected_functions
            or summary.get("slot_count") != expected_slots
        ):
            raise BridgeError(
                "callback bindings result does not match its ACK summary"
            )
        return ack, payload
    raise TimeoutError(
        f"Fresh callback bindings result timeout after {timeout:.0f}s"
    )


def arm_observatory_native_rng(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Arm the fixed, build-keyed one-shot native RNG observer."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("native RNG capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "native RNG observer requires an unpaused active mission heartbeat"
        )
    if NATIVE_RNG_SNAPSHOT_FILE.exists() or NATIVE_RNG_SNAPSHOT_TMP.exists():
        raise BridgeError("native RNG snapshot output already exists")
    command = f"OBS_NATIVE_RNG_ARM {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = f"OK OBS_NATIVE_RNG_ARM capture={capture_id}"
    if ack != expected:
        raise BridgeError(f"unexpected native RNG arm ACK: {ack}")
    return ack


def seed_observatory_native_rng(*, timeout: float = 10.0) -> str:
    """Apply the fixed build-keyed seed immediately before End Turn."""
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "native RNG seed control requires an unpaused mission heartbeat"
        )
    write_command("OBS_NATIVE_RNG_SEED")
    pending_command = f"#{_seq_counter} OBS_NATIVE_RNG_SEED"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = f"OK OBS_NATIVE_RNG_SEED seed={OBSERVATORY_NATIVE_RNG_SEED}"
    if ack != expected:
        raise BridgeError(f"unexpected native RNG seed ACK: {ack}")
    return ack


def seed_and_arm_observatory_native_rng(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Atomically apply the fixed seed and arm the native RNG observer."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("native RNG capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "native RNG seed-and-arm requires an unpaused active mission heartbeat"
        )
    if NATIVE_RNG_SNAPSHOT_FILE.exists() or NATIVE_RNG_SNAPSHOT_TMP.exists():
        raise BridgeError("native RNG snapshot output already exists")
    command = f"OBS_NATIVE_RNG_SEED_AND_ARM {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = (
        f"OK OBS_NATIVE_RNG_SEED_AND_ARM capture={capture_id} "
        f"seed={OBSERVATORY_NATIVE_RNG_SEED}"
    )
    if ack != expected:
        raise BridgeError(f"unexpected native RNG seed-and-arm ACK: {ack}")
    return ack


def seed_and_arm_observatory_native_rng_spawn_span(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Atomically seed, arm RNG observation, and wrap exact NextPawn."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("native RNG spawn-span capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "native RNG spawn-span observer requires an unpaused mission heartbeat"
        )
    outputs = (
        NATIVE_RNG_SNAPSHOT_FILE,
        NATIVE_RNG_SNAPSHOT_TMP,
        SPAWN_SPAN_LEDGER_FILE,
        SPAWN_SPAN_LEDGER_TMP,
    )
    if any(path.exists() for path in outputs):
        raise BridgeError("native RNG spawn-span output already exists")
    command = f"OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = (
        f"OK OBS_NATIVE_RNG_SEED_AND_ARM_SPAWN_SPAN capture={capture_id} "
        f"seed={OBSERVATORY_NATIVE_RNG_SEED}"
    )
    if ack != expected:
        raise BridgeError(f"unexpected native RNG spawn-span arm ACK: {ack}")
    return ack


def arm_observatory_native_rng_spawn_replay(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Atomically arm native RNG observation and exact spawn replay capture."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("native RNG spawn-replay capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "native RNG spawn-replay observer requires an unpaused mission heartbeat"
        )
    outputs = (
        NATIVE_RNG_SNAPSHOT_FILE,
        NATIVE_RNG_SNAPSHOT_TMP,
        SPAWN_REPLAY_LEDGER_FILE,
        SPAWN_REPLAY_LEDGER_TMP,
    )
    if any(path.exists() for path in outputs):
        raise BridgeError("native RNG spawn-replay output already exists")
    command = f"OBS_NATIVE_RNG_ARM_SPAWN_REPLAY {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = f"OK OBS_NATIVE_RNG_ARM_SPAWN_REPLAY capture={capture_id}"
    if ack != expected:
        raise BridgeError(f"unexpected native RNG spawn-replay arm ACK: {ack}")
    return ack


def prepare_observatory_spawn_replay_control(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Load replay artifacts inertly and prepare native End Turn gameflow."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-replay control capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "spawn-replay control requires an unpaused mission heartbeat"
        )
    outputs = (
        NATIVE_RNG_SNAPSHOT_FILE,
        NATIVE_RNG_SNAPSHOT_TMP,
        SPAWN_REPLAY_LEDGER_FILE,
        SPAWN_REPLAY_LEDGER_TMP,
    )
    if any(path.exists() for path in outputs):
        raise BridgeError("spawn-replay control output already exists")
    command = f"OBS_SPAWN_REPLAY_CONTROL {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = (
        f"OK OBS_SPAWN_REPLAY_CONTROL capture={capture_id} dormant=true"
    )
    if ack != expected:
        raise BridgeError(f"unexpected spawn-replay control ACK: {ack}")
    return ack


def status_observatory_native_rng(*, timeout: float = 10.0) -> tuple[str, dict]:
    """Read the fixed native observer's bounded status table."""
    write_command("OBS_NATIVE_RNG_STATUS")
    pending_command = f"#{_seq_counter} OBS_NATIVE_RNG_STATUS"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    prefix = "OK OBS_NATIVE_RNG_STATUS "
    if not ack.startswith(prefix):
        raise BridgeError(f"unexpected native RNG status ACK: {ack}")
    try:
        payload = json.loads(ack[len(prefix) :])
    except json.JSONDecodeError as exc:
        raise BridgeError(f"native RNG status ACK is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BridgeError("native RNG status must be a JSON object")
    return ack, payload


def finish_observatory_native_rng(
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict]:
    """Restore the native hook and require one fresh complete snapshot."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("native RNG capture ID is invalid")
    before = _file_generation(NATIVE_RNG_SNAPSHOT_FILE)
    write_command("OBS_NATIVE_RNG_FINISH")
    pending_command = f"#{_seq_counter} OBS_NATIVE_RNG_FINISH"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_NATIVE_RNG_FINISH capture=([a-z][a-z0-9_.-]{0,95}) "
        r"records=(0|[1-9][0-9]*) complete=true",
        ack,
    )
    if match is None or match.group(1) != capture_id:
        raise BridgeError(f"unexpected native RNG finish ACK: {ack}")
    expected_records = int(match.group(2))
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(NATIVE_RNG_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            payload = json.loads(
                NATIVE_RNG_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"native RNG snapshot is not valid JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise BridgeError("native RNG snapshot must be a JSON object")
        summary = payload.get("summary")
        integrity = payload.get("integrity")
        if (
            payload.get("capture_id") != capture_id
            or payload.get("kind") != "native_rng_core_observer_snapshot"
            or not isinstance(summary, dict)
            or summary.get("record_count") != expected_records
            or not isinstance(integrity, dict)
            or integrity.get("complete") is not True
            or integrity.get("hook_bytes_restored") is not True
            or integrity.get("patch_installed") is not False
        ):
            raise BridgeError(
                "native RNG snapshot does not match its complete ACK"
            )
        return ack, payload
    raise TimeoutError(
        f"Fresh native RNG snapshot timeout after {timeout:.0f}s"
    )


def finish_observatory_native_rng_spawn_span(
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict, dict]:
    """Restore both observers and require their two fresh create-only outputs."""
    before = _file_generation(SPAWN_SPAN_LEDGER_FILE)
    ack, snapshot = finish_observatory_native_rng(capture_id, timeout=timeout)
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SPAWN_SPAN_LEDGER_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            ledger = json.loads(SPAWN_SPAN_LEDGER_FILE.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(f"spawn span ledger is not valid JSON: {exc}") from exc
        if (
            not isinstance(ledger, dict)
            or ledger.get("schema_version") != 1
            or ledger.get("kind") != "spawn_rng_span_ledger"
            or ledger.get("capture_id") != capture_id
            or ledger.get("write_mode") != "create_only"
            or ledger.get("raw_record_count")
                != snapshot.get("summary", {}).get("record_count")
            or ledger.get("integrity", {}).get("complete") is not True
        ):
            raise BridgeError("spawn span ledger does not match its native snapshot")
        return ack, snapshot, ledger
    raise TimeoutError(f"Fresh spawn span ledger timeout after {timeout:.0f}s")


def finish_observatory_native_rng_spawn_replay(
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict, dict]:
    """Restore both replay boundaries and retrieve their fresh outputs."""
    before = _file_generation(SPAWN_REPLAY_LEDGER_FILE)
    ack, snapshot = finish_observatory_native_rng(capture_id, timeout=timeout)
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SPAWN_REPLAY_LEDGER_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            ledger = json.loads(
                SPAWN_REPLAY_LEDGER_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"spawn replay ledger is not valid JSON: {exc}"
            ) from exc
        if (
            not isinstance(ledger, dict)
            or ledger.get("schema_version") != 1
            or ledger.get("kind") != "spawn_rng_replay_ledger"
            or ledger.get("capture_id") != capture_id
            or ledger.get("write_mode") != "create_only"
            or ledger.get("raw_record_count")
                != snapshot.get("summary", {}).get("record_count")
            or ledger.get("integrity", {}).get("complete") is not True
        ):
            raise BridgeError(
                "spawn replay ledger does not match its native snapshot"
            )
        return ack, snapshot, ledger
    raise TimeoutError(
        f"Fresh spawn replay ledger timeout after {timeout:.0f}s"
    )


def arm_observatory_score_positioning_x87(
    capture_id: str,
    *,
    timeout: float = 15.0,
) -> str:
    """Arm the exact one-shot x87 observer immediately before End Turn."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("ScorePositioning x87 capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "ScorePositioning x87 arm requires an unpaused mission heartbeat"
        )
    if (
        SCORE_POSITIONING_X87_SNAPSHOT_FILE.exists()
        or SCORE_POSITIONING_X87_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("ScorePositioning x87 snapshot output already exists")
    command = f"OBS_SCORE_POSITIONING_X87_ARM {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    expected = (
        f"OK OBS_SCORE_POSITIONING_X87_ARM capture={capture_id} "
        "state=capturing records=0"
    )
    if ack != expected:
        raise BridgeError(f"unexpected ScorePositioning x87 arm ACK: {ack}")
    return ack


def status_observatory_score_positioning_x87(
    capture_id: str,
    *,
    timeout: float = 10.0,
) -> tuple[str, dict]:
    """Read the exact x87 observer state without finalizing it."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("ScorePositioning x87 capture ID is invalid")
    command = f"OBS_SCORE_POSITIONING_X87_STATUS {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SCORE_POSITIONING_X87_STATUS "
        r"capture=([a-z][a-z0-9_.-]{0,95}) "
        r"state=(capturing|draining) records=([01]) "
        r"mode=(pending|nearest_even|down|up|toward_zero)",
        ack,
    )
    if match is None or match.group(1) != capture_id:
        raise BridgeError(f"unexpected ScorePositioning x87 status ACK: {ack}")
    state = match.group(2)
    records = int(match.group(3))
    mode = match.group(4)
    if (records, state, mode) not in {
        (0, "capturing", "pending"),
        (1, "draining", "nearest_even"),
        (1, "draining", "down"),
        (1, "draining", "up"),
        (1, "draining", "toward_zero"),
    }:
        raise BridgeError("ScorePositioning x87 status fields are inconsistent")
    return ack, {"state": state, "record_count": records, "rounding_mode": mode}


def finish_observatory_score_positioning_x87(
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict]:
    """Clear DR0/VEH, verify restoration, and read one fresh x87 snapshot."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("ScorePositioning x87 capture ID is invalid")
    before = _file_generation(SCORE_POSITIONING_X87_SNAPSHOT_FILE)
    command = f"OBS_SCORE_POSITIONING_X87_FINISH {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SCORE_POSITIONING_X87_FINISH "
        r"capture=([a-z][a-z0-9_.-]{0,95}) records=1 "
        r"mode=(nearest_even|down|up|toward_zero) "
        r"control_word=([0-9]{1,5}) complete=true",
        ack,
    )
    if match is None or match.group(1) != capture_id:
        raise BridgeError(f"unexpected ScorePositioning x87 finish ACK: {ack}")
    expected_mode = match.group(2)
    expected_control_word = int(match.group(3))
    if expected_control_word > 0xFFFF:
        raise BridgeError("ScorePositioning x87 ACK control word is invalid")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SCORE_POSITIONING_X87_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                SCORE_POSITIONING_X87_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"ScorePositioning x87 snapshot is not valid JSON: {exc}"
            ) from exc
        observation = (
            snapshot.get("observation") if isinstance(snapshot, dict) else None
        )
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind") != "native_score_positioning_x87_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or snapshot.get("summary", {}).get("record_count") != 1
            or not isinstance(observation, dict)
            or observation.get("rounding_mode") != expected_mode
            or observation.get("control_word") != expected_control_word
        ):
            raise BridgeError(
                "ScorePositioning x87 snapshot does not match its ACK"
            )
        return ack, snapshot
    raise TimeoutError(
        f"Fresh ScorePositioning x87 snapshot timeout after {timeout:.0f}s"
    )


def run_observatory_score_positioning_x87_trial(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 75.0,
) -> tuple[str, dict | None]:
    """Run one fixed one-enemy x87 control, dormant, or armed trial."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("ScorePositioning x87 trial condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("ScorePositioning x87 capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "ScorePositioning x87 trial requires an unpaused active mission heartbeat"
        )
    if (
        SCORE_POSITIONING_X87_SNAPSHOT_FILE.exists()
        or SCORE_POSITIONING_X87_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("ScorePositioning x87 snapshot output already exists")
    before = _file_generation(SCORE_POSITIONING_X87_SNAPSHOT_FILE)
    command = f"OBS_SCORE_POSITIONING_X87_TRIAL {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SCORE_POSITIONING_X87_TRIAL "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
        r"at=([0-7]),([0-7]) consumed_spawns=(\d+) records=([01]) "
        r"mode=(unobserved|nearest_even|down|up|toward_zero) "
        r"control_word=(\d{1,5}) complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected ScorePositioning x87 trial ACK: {ack}")
    expected_records = int(match.group(7))
    expected_mode = match.group(8)
    expected_control_word = int(match.group(9))
    if condition != "armed":
        if (
            expected_records != 0
            or expected_mode != "unobserved"
            or expected_control_word != 0
            or _file_generation(SCORE_POSITIONING_X87_SNAPSHOT_FILE) != before
        ):
            raise BridgeError(
                "unarmed ScorePositioning x87 trial published observer output"
            )
        return ack, None
    if (
        expected_records != 1
        or expected_mode == "unobserved"
        or expected_control_word > 0xFFFF
    ):
        raise BridgeError("armed ScorePositioning x87 trial fields are inconsistent")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SCORE_POSITIONING_X87_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                SCORE_POSITIONING_X87_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"ScorePositioning x87 snapshot is not valid JSON: {exc}"
            ) from exc
        observation = (
            snapshot.get("observation") if isinstance(snapshot, dict) else None
        )
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind") != "native_score_positioning_x87_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or snapshot.get("summary", {}).get("record_count") != 1
            or not isinstance(observation, dict)
            or observation.get("rounding_mode") != expected_mode
            or observation.get("control_word") != expected_control_word
        ):
            raise BridgeError(
                "ScorePositioning x87 trial snapshot does not match its ACK"
            )
        return ack, snapshot
    raise TimeoutError(
        f"Fresh ScorePositioning x87 trial snapshot timeout after {timeout:.0f}s"
    )


def run_observatory_selected_queue_trial(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 75.0,
) -> tuple[str, dict | None]:
    """Run one fixed synthetic selected-record/queue trial to completion."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("selected/queue condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("selected/queue capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "selected/queue trial requires an unpaused active mission heartbeat"
        )
    if SELECTED_QUEUE_SNAPSHOT_FILE.exists() or SELECTED_QUEUE_SNAPSHOT_TMP.exists():
        raise BridgeError("selected/queue snapshot output already exists")
    before = _file_generation(SELECTED_QUEUE_SNAPSHOT_FILE)
    command = f"OBS_SELECTED_QUEUE_TRIAL {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SELECTED_QUEUE_TRIAL condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
        r"at=([0-7]),([0-7]) consumed_spawns=(\d+) records=(\d+) "
        r"complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected selected/queue trial ACK: {ack}")
    expected_records = int(match.group(7))
    if condition != "armed":
        if expected_records != 0 or _file_generation(SELECTED_QUEUE_SNAPSHOT_FILE) != before:
            raise BridgeError("unarmed selected/queue trial published observer output")
        return ack, None
    if expected_records != 2:
        raise BridgeError("armed selected/queue trial did not report one exact pair")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SELECTED_QUEUE_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                SELECTED_QUEUE_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"selected/queue snapshot is not valid JSON: {exc}"
            ) from exc
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind")
                != "native_selected_queue_hw_observer_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or snapshot.get("summary", {}).get("record_count")
                != expected_records
        ):
            raise BridgeError("selected/queue snapshot does not match its ACK")
        return ack, snapshot
    raise TimeoutError(f"Fresh selected/queue snapshot timeout after {timeout:.0f}s")


def run_observatory_enemy_tournament_trial(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 75.0,
) -> tuple[str, dict | None]:
    """Run one fixed complete enemy-record tournament trial to completion."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("enemy-tournament condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("enemy-tournament capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "enemy-tournament trial requires an unpaused active mission heartbeat"
        )
    if (
        ENEMY_TOURNAMENT_SNAPSHOT_FILE.exists()
        or ENEMY_TOURNAMENT_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("enemy-tournament snapshot output already exists")
    before = _file_generation(ENEMY_TOURNAMENT_SNAPSHOT_FILE)
    command = f"OBS_ENEMY_TOURNAMENT_TRIAL {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_ENEMY_TOURNAMENT_TRIAL condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
        r"at=([0-7]),([0-7]) consumed_spawns=(\d+) candidates=(\d+) "
        r"selected=(\d+) queue=(\d+) complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected enemy-tournament trial ACK: {ack}")
    candidate_count = int(match.group(7))
    selected_count = int(match.group(8))
    queue_count = int(match.group(9))
    if condition != "armed":
        if (
            candidate_count != 0
            or selected_count != 0
            or queue_count != 0
            or _file_generation(ENEMY_TOURNAMENT_SNAPSHOT_FILE) != before
        ):
            raise BridgeError("unarmed enemy-tournament trial published observer output")
        return ack, None
    if not 1 <= candidate_count <= 256 or selected_count != 1 or queue_count != 1:
        raise BridgeError("armed enemy-tournament trial did not report one exact capture")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(ENEMY_TOURNAMENT_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                ENEMY_TOURNAMENT_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"enemy-tournament snapshot is not valid JSON: {exc}"
            ) from exc
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind") != "native_enemy_tournament_hw_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or snapshot.get("summary", {}).get("candidate_count")
                != candidate_count
            or snapshot.get("summary", {}).get("selected_count") != 1
            or snapshot.get("summary", {}).get("queue_count") != 1
        ):
            raise BridgeError("enemy-tournament snapshot does not match its ACK")
        return ack, snapshot
    raise TimeoutError(
        f"Fresh enemy-tournament snapshot timeout after {timeout:.0f}s"
    )


def run_observatory_enemy_materialized_effect_trial(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 75.0,
) -> tuple[str, dict | None]:
    """Run one fixed selected-SkillEffect materialization trial."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("enemy materialized-effect condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("enemy materialized-effect capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "enemy materialized-effect trial requires an unpaused active "
            "mission heartbeat"
        )
    if (
        ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE.exists()
        or ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_TMP.exists()
        or ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_FILE.exists()
        or ENEMY_MATERIALIZED_EFFECT_REJECTED_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("enemy materialized-effect snapshot output already exists")
    before = _file_generation(ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE)
    command = f"OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_ENEMY_MATERIALIZED_EFFECT_TRIAL "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
        r"at=([0-7]),([0-7]) consumed_spawns=(\d+) candidates=(\d+) "
        r"selected=(\d+) materialized=(\d+) queue=(\d+) complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected enemy materialized-effect trial ACK: {ack}")
    candidate_count = int(match.group(7))
    selected_count = int(match.group(8))
    materialized_count = int(match.group(9))
    queue_count = int(match.group(10))
    if condition != "armed":
        if (
            candidate_count != 0
            or selected_count != 0
            or materialized_count != 0
            or queue_count != 0
            or _file_generation(ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE) != before
        ):
            raise BridgeError(
                "unarmed enemy materialized-effect trial published observer output"
            )
        return ack, None
    if (
        not 1 <= candidate_count <= 256
        or selected_count != 1
        or materialized_count != 1
        or queue_count != 1
    ):
        raise BridgeError(
            "armed enemy materialized-effect trial did not report one exact capture"
        )
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                ENEMY_MATERIALIZED_EFFECT_SNAPSHOT_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"enemy materialized-effect snapshot is not valid JSON: {exc}"
            ) from exc
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind")
                != "native_enemy_materialized_effect_hw_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or snapshot.get("summary", {}).get("candidate_count")
                != candidate_count
            or snapshot.get("summary", {}).get("selected_count") != 1
            or snapshot.get("summary", {}).get("materialized_effect_count") != 1
            or snapshot.get("summary", {}).get("queue_count") != 1
        ):
            raise BridgeError(
                "enemy materialized-effect snapshot does not match its ACK"
            )
        return ack, snapshot
    raise TimeoutError(
        f"Fresh enemy materialized-effect snapshot timeout after {timeout:.0f}s"
    )


def run_observatory_enemy_callback_trial(
    condition: str,
    family: str,
    capture_id: str,
    activation_nonce: str,
    capsule_sha256: str,
    *,
    timeout: float = 75.0,
) -> tuple[str, dict, dict | None]:
    """Run one callback family over the fixed synthetic Firefly scenario."""
    families = {
        "get_target_area",
        "enemy_target_score",
        "get_skill_effect",
        "score_positioning",
    }
    if condition not in {"control", "exact_hook"}:
        raise BridgeError("enemy callback condition is invalid")
    if family not in families:
        raise BridgeError("enemy callback family is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("enemy callback capture ID is invalid")
    if (
        type(activation_nonce) is not str
        or re.fullmatch(r"[0-9a-f]{32,64}", activation_nonce) is None
    ):
        raise BridgeError("enemy callback activation nonce is invalid")
    if (
        type(capsule_sha256) is not str
        or re.fullmatch(r"[0-9a-f]{64}", capsule_sha256) is None
    ):
        raise BridgeError("enemy callback capsule SHA-256 is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "enemy callback trial requires an unpaused active mission heartbeat"
        )

    result_path = (
        BRIDGE_DIR
        / f"itb_observatory_callback_trial_{capture_id}_{condition}.json"
    )
    result_tmp = result_path.with_name(result_path.name + ".tmp")
    trace_path = BRIDGE_DIR / f"itb_observatory_trace_{capture_id}_0.raw"
    trace_tmp = trace_path.with_name(trace_path.name + ".tmp")
    if any(path.exists() for path in (result_path, result_tmp, trace_path, trace_tmp)):
        raise BridgeError("enemy callback trial output already exists")
    result_before = _file_generation(result_path)
    trace_before = _file_generation(trace_path)
    command = (
        f"OBS_ENEMY_CALLBACK_TRIAL {condition} {family} {capture_id} "
        f"{activation_nonce} {capsule_sha256}"
    )
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_ENEMY_CALLBACK_TRIAL condition=(control|exact_hook) "
        r"family=(get_target_area|enemy_target_score|get_skill_effect|score_positioning) "
        r"capture=([a-z][a-z0-9._-]{0,95}) pawn=(\d+) type=Firefly1 "
        r"at=([0-7]),([0-7]) consumed_spawns=(\d+) attempts=(\d+) "
        r"events=(\d+) complete=true",
        ack,
    )
    if (
        match is None
        or match.group(1) != condition
        or match.group(2) != family
        or match.group(3) != capture_id
    ):
        raise BridgeError(f"unexpected enemy callback trial ACK: {ack}")
    attempts = int(match.group(8))
    events = int(match.group(9))
    if condition == "control":
        if attempts != 0 or events != 0:
            raise BridgeError("control enemy callback trial emitted observations")
    elif attempts < 1 or events != attempts:
        raise BridgeError("exact enemy callback trial is incomplete")

    result_generation = _file_generation(result_path)
    if result_generation is None or result_generation == result_before:
        raise BridgeError("enemy callback result was not published freshly")
    result = _read_json_file(result_path)
    if (
        not isinstance(result, dict)
        or result.get("schema_version") != 1
        or result.get("kind") != "observatory_callback_trial_result"
        or result.get("status") != "complete"
        or result.get("condition") != condition
        or result.get("capture_id") != capture_id
        or result.get("callback_family") != family
        or result.get("attempted_calls") != attempts
        or result.get("raw_event_count") != events
        or result.get("serialization_errors") != 0
        or result.get("slots_restored") is not True
    ):
        raise BridgeError("enemy callback result does not match its ACK")

    if condition == "control":
        if _file_generation(trace_path) != trace_before:
            raise BridgeError("control enemy callback trial published a trace")
        return ack, result, None
    trace_generation = _file_generation(trace_path)
    if trace_generation is None or trace_generation == trace_before:
        raise BridgeError("enemy callback trace was not published freshly")
    trace = _read_json_file(trace_path)
    summary = trace.get("summary") if isinstance(trace, dict) else None
    attempted = trace.get("attempted_calls") if isinstance(trace, dict) else None
    trace_events = trace.get("events") if isinstance(trace, dict) else None
    if (
        not isinstance(trace, dict)
        or trace.get("raw_schema_version") != 1
        or trace.get("controller_version")
            != "observatory-callback-controller/1"
        or trace.get("capture_id") != capture_id
        or trace.get("checkpoint_seq") != 0
        or not isinstance(trace_events, list)
        or len(trace_events) != events
        or not isinstance(attempted, dict)
        or attempted.get(family) != attempts
        or any(
            value != (attempts if key == family else 0)
            for key, value in attempted.items()
        )
        or not isinstance(summary, dict)
        or summary.get("accepted_events") != events
        or summary.get("dropped_events") != 0
        or summary.get("filtered_events") != 0
        or summary.get("serialization_errors") != 0
        or summary.get("restore_conflicts") != 0
        or summary.get("stop_reasons") != []
        or summary.get("truncation_reasons") != []
    ):
        raise BridgeError("enemy callback trace does not match its ACK")
    for index, event in enumerate(trace_events):
        if (
            not isinstance(event, dict)
            or event.get("seq") != index
            or event.get("kind") != family
            or event.get("mission_id") != "Mission_Power"
            or event.get("phase") != "combat_enemy"
            or not isinstance(event.get("context"), dict)
            or not isinstance(event.get("payload"), dict)
        ):
            raise BridgeError("enemy callback trace event stream is invalid")
    return ack, result, trace


def prepare_observatory_spawn_coordinate(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 10.0,
) -> str:
    """Seed and optionally arm the coordinate observer immediately pre-turn."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("spawn-coordinate condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "spawn-coordinate prepare requires an unpaused active mission heartbeat"
        )
    if (
        SPAWN_COORDINATE_SNAPSHOT_FILE.exists()
        or SPAWN_COORDINATE_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("spawn-coordinate snapshot output already exists")
    command = f"OBS_SPAWN_COORDINATE_PREPARE {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_COORDINATE_PREPARE "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) seed=324508639 "
        r"armed=(true|false)",
        ack,
    )
    expected_armed = "true" if condition == "armed" else "false"
    if (
        match is None
        or match.group(1) != condition
        or match.group(2) != capture_id
        or match.group(3) != expected_armed
    ):
        raise BridgeError(f"unexpected spawn-coordinate prepare ACK: {ack}")
    return ack


def finish_observatory_spawn_coordinate(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict | None]:
    """Restore the observer and retrieve its fresh snapshot when armed."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("spawn-coordinate condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capture ID is invalid")
    before = _file_generation(SPAWN_COORDINATE_SNAPSHOT_FILE)
    command = f"OBS_SPAWN_COORDINATE_FINISH {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_COORDINATE_FINISH "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) records=(\d+) "
        r"scheduler=(\d+) fallback=(\d+) standard=(\d+) selectors=(\d+) "
        r"complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected spawn-coordinate finish ACK: {ack}")
    record_count = int(match.group(3))
    scheduler_count = int(match.group(4))
    fallback_count = int(match.group(5))
    standard_count = int(match.group(6))
    selector_count = int(match.group(7))
    if condition != "armed":
        if (
            any(
                value != 0
                for value in (
                    record_count,
                    scheduler_count,
                    fallback_count,
                    standard_count,
                    selector_count,
                )
            )
            or _file_generation(SPAWN_COORDINATE_SNAPSHOT_FILE) != before
        ):
            raise BridgeError("unarmed spawn-coordinate boundary published output")
        return ack, None
    if (
        not 1 <= record_count <= 256
        or record_count != scheduler_count + fallback_count + standard_count
        or selector_count != fallback_count + standard_count
        or selector_count < 1
    ):
        raise BridgeError("armed spawn-coordinate boundary counts differ")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SPAWN_COORDINATE_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                SPAWN_COORDINATE_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"spawn-coordinate snapshot is not valid JSON: {exc}"
            ) from exc
        summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind")
                != "native_spawn_coordinate_hw_observer_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or summary.get("record_count") != record_count
            or summary.get("scheduler_count") != scheduler_count
            or summary.get("selector_fallback_count") != fallback_count
            or summary.get("selector_standard_count") != standard_count
            or summary.get("selector_count") != selector_count
        ):
            raise BridgeError("spawn-coordinate snapshot does not match its ACK")
        return ack, snapshot
    raise TimeoutError(
        f"Fresh spawn-coordinate snapshot timeout after {timeout:.0f}s"
    )


def abort_observatory_spawn_coordinate(
    capture_id: str,
    *,
    timeout: float = 10.0,
) -> str:
    """Restore an armed coordinate observer without publishing evidence."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capture ID is invalid")
    command = f"OBS_SPAWN_COORDINATE_ABORT {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_COORDINATE_ABORT "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) restored=true",
        ack,
    )
    if match is None or match.group(2) != capture_id:
        raise BridgeError(f"unexpected spawn-coordinate abort ACK: {ack}")
    return ack


def check_observatory_spawn_coordinate_capsule_load(
    *, timeout: float = 10.0
) -> str:
    """Load the inert capsule DLL and prove it remains dormant and unconsumed."""
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "spawn-coordinate capsule load check requires an active heartbeat"
        )
    command = "OBS_SPAWN_CAPSULE_LOAD_CHECK"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    if ack != (
        "OK OBS_SPAWN_CAPSULE_LOAD_CHECK "
        "state=dormant consumed=false armed=false"
    ):
        raise BridgeError(f"unexpected spawn-coordinate capsule load ACK: {ack}")
    return ack


def prepare_observatory_spawn_coordinate_capsule(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 10.0,
) -> str:
    """Seed and optionally arm the selector-entry Board/RNG capsule observer."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("spawn-coordinate capsule condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capsule capture ID is invalid")
    if not is_bridge_alive(max_stale_sec=5.0):
        raise BridgeError(
            "spawn-coordinate capsule prepare requires an active mission heartbeat"
        )
    if (
        SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE.exists()
        or SPAWN_COORDINATE_CAPSULE_SNAPSHOT_TMP.exists()
    ):
        raise BridgeError("spawn-coordinate capsule snapshot output already exists")
    command = f"OBS_SPAWN_CAPSULE_PREPARE {condition} {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_CAPSULE_PREPARE "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) seed=324508639 "
        r"armed=(true|false)",
        ack,
    )
    expected_armed = "true" if condition == "armed" else "false"
    if (
        match is None
        or match.group(1) != condition
        or match.group(2) != capture_id
        or match.group(3) != expected_armed
    ):
        raise BridgeError(f"unexpected spawn-coordinate capsule prepare ACK: {ack}")
    return ack


def finish_observatory_spawn_coordinate_capsule(
    condition: str,
    capture_id: str,
    *,
    timeout: float = 30.0,
) -> tuple[str, dict | None]:
    """Restore the capsule observer and retrieve fresh armed evidence."""
    if condition not in {"control", "dormant", "armed"}:
        raise BridgeError("spawn-coordinate capsule condition is invalid")
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capsule capture ID is invalid")
    before = _file_generation(SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE)
    command = f"OBS_SPAWN_CAPSULE_FINISH {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_CAPSULE_FINISH "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) draws=(\d+) "
        r"scheduler=(\d+) fallback=(\d+) standard=(\d+) selectors=(\d+) "
        r"capsules=(\d+) complete=true",
        ack,
    )
    if match is None or match.group(1) != condition or match.group(2) != capture_id:
        raise BridgeError(f"unexpected spawn-coordinate capsule finish ACK: {ack}")
    draw_count = int(match.group(3))
    scheduler_count = int(match.group(4))
    fallback_count = int(match.group(5))
    standard_count = int(match.group(6))
    selector_count = int(match.group(7))
    capsule_count = int(match.group(8))
    if condition != "armed":
        if (
            any(
                value != 0
                for value in (
                    draw_count,
                    scheduler_count,
                    fallback_count,
                    standard_count,
                    selector_count,
                    capsule_count,
                )
            )
            or _file_generation(SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE) != before
        ):
            raise BridgeError(
                "unarmed spawn-coordinate capsule boundary published output"
            )
        return ack, None
    if (
        not 1 <= draw_count <= 256
        or draw_count != scheduler_count + fallback_count + standard_count
        or selector_count != fallback_count + standard_count
        or not 1 <= selector_count <= 64
        or capsule_count != selector_count
    ):
        raise BridgeError("armed spawn-coordinate capsule boundary counts differ")
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        generation = _file_generation(SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE)
        if generation is None or generation == before:
            time.sleep(0.02)
            continue
        try:
            snapshot = json.loads(
                SPAWN_COORDINATE_CAPSULE_SNAPSHOT_FILE.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BridgeError(
                f"spawn-coordinate capsule snapshot is not valid JSON: {exc}"
            ) from exc
        summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("schema_version") != 1
            or snapshot.get("kind")
                != "native_spawn_coordinate_capsule_hw_observer_snapshot"
            or snapshot.get("capture_id") != capture_id
            or snapshot.get("integrity", {}).get("complete") is not True
            or summary.get("draw_record_count") != draw_count
            or summary.get("scheduler_count") != scheduler_count
            or summary.get("selector_fallback_count") != fallback_count
            or summary.get("selector_standard_count") != standard_count
            or summary.get("selector_count") != selector_count
            or summary.get("capsule_count") != capsule_count
        ):
            raise BridgeError(
                "spawn-coordinate capsule snapshot does not match its ACK"
            )
        return ack, snapshot
    raise TimeoutError(
        f"Fresh spawn-coordinate capsule snapshot timeout after {timeout:.0f}s"
    )


def abort_observatory_spawn_coordinate_capsule(
    capture_id: str,
    *,
    timeout: float = 10.0,
) -> str:
    """Restore an armed capsule observer without publishing evidence."""
    if (
        type(capture_id) is not str
        or _OBSERVATORY_CAPTURE_ID_RE.fullmatch(capture_id) is None
    ):
        raise BridgeError("spawn-coordinate capsule capture ID is invalid")
    command = f"OBS_SPAWN_CAPSULE_ABORT {capture_id}"
    write_command(command)
    pending_command = f"#{_seq_counter} {command}"
    try:
        ack = wait_for_ack(timeout=timeout)
    except TimeoutError:
        _cancel_pending_command(pending_command)
        raise
    match = re.fullmatch(
        r"OK OBS_SPAWN_CAPSULE_ABORT "
        r"condition=(control|dormant|armed) "
        r"capture=([a-z][a-z0-9._-]{0,95}) restored=true",
        ack,
    )
    if match is None or match.group(2) != capture_id:
        raise BridgeError(f"unexpected spawn-coordinate capsule abort ACK: {ack}")
    return ack


def arm_observatory_callback_manifest_startup() -> Path:
    """Create the exact one-shot request consumed on the next game load.

    Publication is create-only so an existing or user-created request is never
    replaced.  The Lua loader accepts only these fixed ASCII bytes (with a
    terminal newline) and removes the request before executing the literal
    no-argument Observatory command.
    """
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CALLBACK_MANIFEST_REQUEST_FILE, "xb") as file:
            file.write(CALLBACK_MANIFEST_REQUEST_BYTES)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError as exc:
        raise BridgeError(
            "callback manifest startup request already exists"
        ) from exc
    except OSError as exc:
        raise BridgeError(
            f"cannot arm callback manifest startup request: {exc}"
        ) from exc
    return CALLBACK_MANIFEST_REQUEST_FILE


def arm_observatory_callback_bindings_startup() -> Path:
    """Create the fixed one-shot slot-manifest request for next game load."""
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CALLBACK_BINDINGS_REQUEST_FILE, "xb") as file:
            file.write(CALLBACK_BINDINGS_REQUEST_BYTES)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError as exc:
        raise BridgeError("callback bindings startup request already exists") from exc
    except OSError as exc:
        raise BridgeError(
            f"cannot arm callback bindings startup request: {exc}"
        ) from exc
    return CALLBACK_BINDINGS_REQUEST_FILE


def arm_observatory_native_continue_startup() -> Path:
    """Create the fixed request for one build-keyed title Continue action."""
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(NATIVE_CONTINUE_REQUEST_FILE, "xb") as file:
            file.write(NATIVE_CONTINUE_REQUEST_BYTES)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError as exc:
        raise BridgeError("native Continue startup request already exists") from exc
    except OSError as exc:
        raise BridgeError(
            f"cannot arm native Continue startup request: {exc}"
        ) from exc
    return NATIVE_CONTINUE_REQUEST_FILE


def read_state() -> dict | None:
    """Read the current game state JSON. Returns None if unavailable."""
    for path in _state_candidates_newest_first():
        payload = _read_json_file(path)
        if payload is not None:
            return payload
    return None


def write_command(cmd: str) -> None:
    """Write a command with sequence ID (atomic via tmp+rename).

    Prepends a sequence ID (#NNN) for ACK correlation.
    Clears any stale ACK file first to prevent reading the previous
    command's response as this command's ACK (race condition fix).
    """
    global _seq_counter
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

    # Clear stale ACK to prevent reading previous command's response
    try:
        ACK_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    time.sleep(0.05)  # brief settle time

    _seq_counter += 1
    full_cmd = f"#{_seq_counter} {cmd}"

    with open(CMD_TMP, "w", encoding="utf-8") as f:
        f.write(full_cmd)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(CMD_TMP), str(CMD_FILE))


def wait_for_ack(timeout: float = 10.0) -> str:
    """Poll for ACK file. Returns content after stripping sequence ID.

    Two-tier timeout: at 20s, checks the bridge heartbeat. If the heartbeat
    is stale (Lua stopped ticking), fails fast. If fresh, keeps waiting up
    to the full timeout (legitimate slow animations can take 30s+).

    Raises TimeoutError if no ACK within timeout.
    Raises BridgeError if ACK indicates an error.
    """
    deadline = time.time() + timeout
    heartbeat_check_at = time.time() + 20.0
    heartbeat_checked = False
    while time.time() < deadline:
        if ACK_FILE.exists():
            try:
                content = ACK_FILE.read_text(encoding="utf-8").strip()
                ACK_FILE.unlink()

                # Strip sequence ID prefix (#NNN)
                if content.startswith("#"):
                    space_idx = content.find(" ")
                    if space_idx > 0:
                        seq_str = content[1:space_idx]
                        content = content[space_idx + 1:]
                        # Verify sequence match (skip stale ACKs)
                        try:
                            if int(seq_str) != _seq_counter:
                                continue
                        except ValueError:
                            pass

                # Check for error
                if content.startswith("ERROR"):
                    raise BridgeError(content)

                return content
            except BridgeError:
                raise
            except IOError:
                pass
        # Two-tier: early fail if bridge heartbeat is stale
        if not heartbeat_checked and time.time() >= heartbeat_check_at:
            heartbeat_checked = True
            if not is_bridge_alive(max_stale_sec=5.0):
                raise TimeoutError(
                    f"Bridge heartbeat stale after 20s — Lua stopped ticking"
                )
        time.sleep(0.1)
    raise TimeoutError(f"Bridge ACK timeout after {timeout:.0f}s")


def wait_for_fresh_state(timeout: float = 10.0) -> dict | None:
    """Wait for a state file newer than now. Returns parsed JSON or None."""
    start = time.time()
    deadline = start + timeout
    while time.time() < deadline:
        for path in _state_candidates_newest_first():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= start:
                payload = _read_json_file(path)
                if payload is not None:
                    return payload
        time.sleep(0.2)
    return None
