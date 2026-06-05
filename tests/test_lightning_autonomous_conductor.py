from __future__ import annotations

from types import SimpleNamespace

from src.loop.lightning_conductor import (
    AutonomousLightningConfig,
    AutonomousLightningConductor,
    _hard_stop,
    _telemetry_run_id,
    _timer_label,
    _timer_seconds,
)


class FakeTelemetry:
    def __init__(self, run_id: str = "lw_test") -> None:
        self.run_dir = f"recordings/{run_id}"
        self.telemetry_dir = f"{self.run_dir}/telemetry"
        self.events: list[tuple[str, dict]] = []

    def event(self, name: str, **payload):
        self.events.append((name, payload))


def make_conductor(**kwargs) -> AutonomousLightningConductor:
    conductor = AutonomousLightningConductor(
        AutonomousLightningConfig(
            screenshots=False,
            achievement_sync=False,
            max_attempts=1,
            max_segments=1,
            **kwargs,
        )
    )
    conductor.telemetry = FakeTelemetry()
    return conductor


def test_telemetry_run_id_preserves_real_session_id():
    session = SimpleNamespace(run_id="20260605_120000_123")

    assert _telemetry_run_id(session) == "20260605_120000_123"


def test_telemetry_run_id_replaces_generic_lw_session_id():
    session = SimpleNamespace(run_id="lw")

    run_id = _telemetry_run_id(session)

    assert run_id.startswith("lightning_")
    assert run_id != "lw"


def test_autonomous_starts_when_initial_screen_is_setup():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "SKIPPED",
                "reason": "visible_ui_not_pause_guard_eligible",
                "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
            },
        ),
        cmd_verify_setup_screen=record("verify_setup", {"status": "PASS"}),
        cmd_lightning_start_run=record("start_run", {"status": "OK"}),
        cmd_lightning_preflight=record("preflight", {"status": "PASS"}),
        cmd_lightning_segment=record(
            "segment",
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "pause_guard": {
                    "status": "OK",
                    "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
                },
            },
        ),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor()._run_inner(commands)

    assert result["status"] == "PARKED_SAFE"
    assert [name for name, _ in calls[:5]] == [
        "pause_guard",
        "lightning_ui",
        "verify_setup",
        "start_run",
        "preflight",
    ]
    assert calls[1] == ("lightning_ui", {"args": (), "control": "setup_start"})


def test_autonomous_starts_from_setup_despite_stale_live_bridge():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "BLOCKED",
                "reason": "live_combat_phase",
                "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
                "last_poll": {
                    "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
                    "live_snapshot": {
                        "phase": "combat_player",
                        "mission_id": "Mission_Volatile",
                    },
                },
            },
        ),
        cmd_verify_setup_screen=record("verify_setup", {"status": "PASS"}),
        cmd_lightning_start_run=record("start_run", {"status": "OK"}),
        cmd_lightning_preflight=record("preflight", {"status": "PASS"}),
        cmd_lightning_segment=record(
            "segment",
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "pause_guard": {
                    "status": "OK",
                    "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
                },
            },
        ),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor()._run_inner(commands)

    assert result["status"] == "PARKED_SAFE"
    assert [name for name, _ in calls[:4]] == [
        "pause_guard",
        "lightning_ui",
        "verify_setup",
        "start_run",
    ]


def test_autonomous_blocks_and_pauses_on_bridge_snapshot_unavailable():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        ),
        cmd_lightning_preflight=record("preflight", {"status": "PASS"}),
        cmd_lightning_segment=record(
            "segment",
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "bridge_snapshot_unavailable",
                "pause_guard": {
                    "status": "SKIPPED",
                    "reason": "visible_ui_not_pause_guard_eligible",
                    "visible_ui": {"status": "OK", "visible_ui": "new_game_setup"},
                },
            },
        ),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor()._run_inner(commands)

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "hard_gate"
    assert calls[-1] == ("lightning_ui", {"args": ("ensure_pause",)})


def test_autonomous_passes_segment_timeout_as_wall_cap():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        ),
        cmd_lightning_preflight=record("preflight", {"status": "PASS"}),
        cmd_lightning_segment=record(
            "segment",
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "pause_guard": {
                    "status": "OK",
                    "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
                },
            },
        ),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor(segment_timeout=123.0)._run_inner(commands)

    assert result["status"] == "PARKED_SAFE"
    segment_call = next(payload for name, payload in calls if name == "segment")
    assert segment_call["max_wall_seconds"] == 123.0


def test_autonomous_prefers_explicit_max_wall_seconds():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        ),
        cmd_lightning_preflight=record("preflight", {"status": "PASS"}),
        cmd_lightning_segment=record(
            "segment",
            {
                "status": "LIGHTNING_SEGMENT_STOPPED",
                "reason": "max_steps_reached",
                "pause_guard": {
                    "status": "OK",
                    "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
                },
            },
        ),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor(max_wall_seconds=77.0, segment_timeout=123.0)._run_inner(commands)

    assert result["status"] == "PARKED_SAFE"
    segment_call = next(payload for name, payload in calls if name == "segment")
    assert segment_call["max_wall_seconds"] == 77.0


def test_autonomous_restarts_when_first_island_gate_is_missed():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        _load_session=lambda: SimpleNamespace(islands_completed=[]),
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        ),
        cmd_lightning_preflight=record(
            "preflight",
            {"status": "PASS", "effective_timer": {"game_seconds": 901.0}},
        ),
        cmd_lightning_segment=record("segment", {"status": "SHOULD_NOT_RUN"}),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor(first_island_gate_seconds=900.0)._run_inner(commands)

    assert result["status"] == "RESTART_RECOMMENDED"
    assert result["reason"] == "first_island_pace_gate"
    assert result["game_timer"] == "0:15:01"
    assert ("segment", {"args": ()}) not in calls
    assert calls[-1] == ("lightning_ui", {"args": ("ensure_pause",)})


def test_autonomous_restarts_when_second_island_start_gate_is_missed():
    calls: list[tuple[str, dict]] = []

    def record(name, payload):
        def fn(*args, **kwargs):
            calls.append((name, {"args": args, **kwargs}))
            return payload

        return fn

    commands = SimpleNamespace(
        _load_session=lambda: SimpleNamespace(islands_completed=["archive"]),
        cmd_lightning_pause_guard=record(
            "pause_guard",
            {
                "status": "OK",
                "reason": "already_paused",
                "visible_ui": {"status": "OK", "visible_ui": "pause_menu"},
            },
        ),
        cmd_lightning_preflight=record(
            "preflight",
            {"status": "PASS", "effective_timer": {"game_seconds": 1006.0}},
        ),
        cmd_lightning_segment=record("segment", {"status": "SHOULD_NOT_RUN"}),
        cmd_lightning_ui=record("lightning_ui", {"status": "OK"}),
    )

    result = make_conductor(second_island_start_gate_seconds=1005.0)._run_inner(commands)

    assert result["status"] == "RESTART_RECOMMENDED"
    assert result["reason"] == "second_island_start_pace_gate"
    assert result["gate_timer"] == "0:16:45"
    assert calls[-1] == ("lightning_ui", {"args": ("ensure_pause",)})


def test_timer_helpers_read_real_segment_last_attempt_budget():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_auto_start_not_allowed",
        "last_attempt": {
            "budget": {
                "game_seconds": 940.267,
                "game_timer": "0:15:40",
            },
        },
    }

    assert _timer_seconds(segment) == 940.267
    assert _timer_label(segment) == "0:15:40"


def test_timer_helpers_read_nested_resume_guard_visible_budget():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "route_auto_start_not_allowed",
        "last_attempt": {
            "budget": {
                "game_seconds": 786.395,
                "game_timer": "0:13:06",
            },
            "resume_guard": {
                "visible_timer_budget": {
                    "game_seconds": 947.0,
                    "game_timer": "0:15:47",
                },
            },
        },
    }

    assert _timer_seconds(segment) == 947.0
    assert _timer_label(segment) == "0:15:47"


def test_hard_stop_detects_nested_post_enemy_attempt():
    segment = {
        "status": "LIGHTNING_SEGMENT_STOPPED",
        "reason": "combat_loop_returned",
        "last_attempt": {
            "status": "POST_ENEMY_AUDIT_MISSED_WINDOW",
            "blocking": True,
        },
    }

    assert _hard_stop(segment)
