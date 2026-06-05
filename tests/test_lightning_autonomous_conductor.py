from __future__ import annotations

from types import SimpleNamespace

from src.loop.lightning_conductor import (
    AutonomousLightningConfig,
    AutonomousLightningConductor,
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
    assert [name for name, _ in calls[:4]] == [
        "pause_guard",
        "verify_setup",
        "start_run",
        "preflight",
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
