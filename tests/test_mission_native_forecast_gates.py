"""Hard stops for native mission phases the solver cannot forecast yet."""

from types import SimpleNamespace

import pytest

from src.loop import commands
from src.loop.session import RunSession
from src.strategy.mission_picker import NATIVE_FORECAST_GATED_MISSION_IDS


MISSION_GAPS = {
    "Mission_BlobBoss": "mission_blob_boss_five_death_counter_unmodeled",
    "Mission_Fence": "mission_fence_edge_walls_unmodeled",
    "Mission_Laser": "mission_laser_queued_beam_unmodeled",
    "Mission_Respawn": "mission_respawn_resurrection_unmodeled",
    "Mission_SpiderBoss": "mission_spider_boss_recurring_egg_spawns_unmodeled",
    "Mission_SlugBoss": "mission_slug_boss_recurring_egg_spawns_unmodeled",
    "Mission_Tutorial": "mission_tutorial_scripted_lifecycle_unmodeled",
}


def _gate(mission_id: str) -> dict:
    return commands._mission_native_forecast_block(
        SimpleNamespace(mission_id=mission_id), {"mission_id": mission_id},
    )


def test_native_forecast_gate_catalogs_match_and_modeled_finals_remain_ungated():
    assert set(MISSION_GAPS) == set(commands._MISSION_NATIVE_FORECAST_GAPS)
    assert set(MISSION_GAPS) == set(NATIVE_FORECAST_GATED_MISSION_IDS)
    assert _gate("Mission_Final") is None
    assert "Mission_Final" not in NATIVE_FORECAST_GATED_MISSION_IDS
    assert _gate("Mission_Final_Cave") is None
    assert "Mission_Final_Cave" not in NATIVE_FORECAST_GATED_MISSION_IDS


def _patch_solve_inputs(monkeypatch, mission_id: str, board=None):
    session = RunSession(run_id="native-forecast", squad="Random", difficulty=0)
    board = board or SimpleNamespace(mission_id=mission_id, mechs=lambda: [])
    data = {
        "mission_id": mission_id,
        "phase": "combat_player",
        "tiles": [],
        "units": [],
    }
    monkeypatch.setattr(commands, "_check_wheel_sim_version", lambda: None)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands, "_enrich_bridge_mech_weapons_from_save", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        commands,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commands, "_final_post_enemy_audit_gate", lambda *_args, **_kwargs: None
    )


@pytest.mark.parametrize("mission_id,gap_kind", MISSION_GAPS.items())
def test_cmd_solve_returns_exact_non_overridable_native_forecast_gate(
    monkeypatch, mission_id, gap_kind,
):
    _patch_solve_inputs(monkeypatch, mission_id)

    result = commands.cmd_solve()

    assert result == {
        "error": "RESEARCH_REQUIRED",
        "requires_research": True,
        "blocking": True,
        "non_overridable": True,
        "reason": "mission_native_forecast_unproven",
        "mission_id": mission_id,
        "forecast_complete": False,
        "forecast_gaps": [{"kind": gap_kind}],
        "next": (
            "Capture and model this mission's native phase before allowing "
            "solver forecasts or End Turn delivery."
        ),
    }


@pytest.mark.parametrize("mission_id,gap_kind", MISSION_GAPS.items())
def test_auto_turn_preserves_native_forecast_gate_metadata(
    monkeypatch, mission_id, gap_kind,
):
    session = RunSession(run_id="native-auto", squad="Random", difficulty=0)
    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_read_save_file_difficulty", lambda _profile: None)
    monkeypatch.setattr(
        commands,
        "cmd_read",
        lambda **_kwargs: {
            "status": "OK",
            "phase": "combat_player",
            "active_mechs": 1,
            "turn": 2,
        },
    )
    monkeypatch.setattr(commands, "cmd_solve", lambda **_kwargs: _gate(mission_id))

    result = commands.cmd_auto_turn(wait_for_turn=False)

    assert result["error"] == "Solve: RESEARCH_REQUIRED"
    assert result["requires_research"] is True
    assert result["blocking"] is True
    assert result["non_overridable"] is True
    assert result["reason"] == "mission_native_forecast_unproven"
    assert result["mission_id"] == mission_id
    assert result["forecast_complete"] is False
    assert result["forecast_gaps"] == [{"kind": gap_kind}]


@pytest.mark.parametrize("mission_id,gap_kind", MISSION_GAPS.items())
@pytest.mark.parametrize(
    "command_name,kwargs,block_key",
    [
        ("cmd_click_end_turn", {}, None),
        ("cmd_end_turn", {}, None),
        ("cmd_dispatch_end_turn", {"execute": False}, "block"),
        ("cmd_dispatch_end_turn", {"execute": True}, "plan"),
    ],
)
def test_public_end_turn_paths_block_native_forecast_before_plan_or_dispatch(
    monkeypatch, mission_id, gap_kind, command_name, kwargs, block_key,
):
    data = {
        "mission_id": mission_id,
        "phase": "combat_player",
        "in_active_mission": True,
        "turn": 2,
        "tiles": [],
        "units": [],
    }
    board = SimpleNamespace(mission_id=mission_id)
    session = RunSession(run_id="native-held", squad="Random", difficulty=0)
    session.current_mission = mission_id

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "_post_enemy_block_result", lambda _session: None)
    monkeypatch.setattr(commands, "_refresh_end_turn_bridge_state", lambda: True)
    monkeypatch.setattr(commands, "read_bridge_state", lambda: (board, data))
    monkeypatch.setattr(
        commands, "_enrich_bridge_mech_weapons_from_save", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        commands,
        "_enrich_bridge_limited_mission_weapons_from_save",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        commands,
        "plan_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not plan End Turn")),
    )
    monkeypatch.setattr(
        commands,
        "execute_bridge_end_turn",
        lambda: (_ for _ in ()).throw(AssertionError("must not dispatch End Turn")),
    )

    result = getattr(commands, command_name)(**kwargs)
    block = result if block_key is None else result[block_key]

    assert block["status"] == "END_TURN_BLOCKED"
    assert block["reason"] == "held_end_turn_mission_native_unproven"
    forecast = block["mission_native_forecast"]
    assert forecast["requires_research"] is True
    assert forecast["blocking"] is True
    assert forecast["non_overridable"] is True
    assert forecast["mission_id"] == mission_id
    assert forecast["forecast_complete"] is False
    assert forecast["forecast_gaps"] == [{"kind": gap_kind}]


def test_exact_non_target_mission_is_unaffected(monkeypatch):
    assert _gate("Mission_Artillery") is None
    _patch_solve_inputs(monkeypatch, "Mission_Artillery")

    result = commands.cmd_solve()

    assert result["error"].startswith("No active mechs ")


@pytest.mark.parametrize("mission_id", MISSION_GAPS)
def test_lightning_route_veto_recognizes_native_forecast_gate_from_id_alone(mission_id):
    assert commands._lightning_route_auto_start_veto_reason(
        {"mission_id": mission_id},
        routing="lightning_war",
    ) == f"native_forecast_gate:{mission_id}"


@pytest.mark.parametrize("mission_id", MISSION_GAPS)
def test_lightning_boss_preview_cannot_clear_native_forecast_gate(mission_id):
    recommendation = {
        "source": "bridge_preview",
        "top3": [{"mission_id": mission_id, "boss": True}],
    }

    assert commands._lightning_auto_start_preview_block_reason(
        recommendation,
        mission_id,
        routing="lightning_war",
    ) == f"native_forecast_gate:{mission_id}"


def test_lightning_boss_preview_keeps_ordinary_boss_auto_start_behavior():
    recommendation = {
        "source": "bridge_preview",
        "top3": [{"mission_id": "Mission_TestBoss", "boss": True}],
    }

    assert commands._lightning_auto_start_preview_block_reason(
        recommendation,
        "Mission_TestBoss",
        routing="lightning_war",
    ) is None


@pytest.mark.parametrize("mission_id", MISSION_GAPS)
def test_lightning_forced_preview_keeps_native_forecast_route_veto(mission_id):
    """A single forced bridge preview cannot trade forecast safety for speed."""
    result = commands._lightning_speed_route_status(
        [
            {
                "mission_id": mission_id,
                "score": -1000,
            }
        ],
        "lightning_war",
        source="bridge_preview",
    )

    assert result["status"] == "AUTO_START_BLOCKED"
    assert result["auto_start_allowed"] is False
    assert result["reason"] == f"native_forecast_gate:{mission_id}"


def test_lightning_forced_preview_still_allows_ordinary_speed_route():
    """The native-gate exception does not weaken normal forced-preview routing."""
    result = commands._lightning_speed_route_status(
        [{"mission_id": "Mission_Artillery", "score": 99, "mission_tags": []}],
        "lightning_war",
        source="bridge_preview",
    )

    assert result["status"] == "AUTO_START_OK"
    assert result["auto_start_allowed"] is True
    assert result["reason"] == "forced_bridge_preview_route"


@pytest.mark.parametrize("mission_id", MISSION_GAPS)
def test_lightning_forced_preview_candidate_preserves_native_forecast_veto(mission_id):
    """The route-candidate handoff keeps the veto after status ranking."""
    candidate = {
        "forced_preview_route": True,
        "forced_preview_ambiguous": False,
        "route_option": {
            "mission_id": mission_id,
        },
    }

    assert commands._lightning_candidate_auto_block_reason(candidate) == (
        f"native_forecast_gate:{mission_id}"
    )
    assert commands._lightning_candidate_auto_allowed(candidate) is False


def test_lightning_forced_preview_candidate_still_allows_ordinary_speed_route():
    candidate = {
        "forced_preview_route": True,
        "forced_preview_ambiguous": False,
        "route_option": {"mission_id": "Mission_Artillery"},
    }

    assert commands._lightning_candidate_auto_block_reason(candidate) is None
    assert commands._lightning_candidate_auto_allowed(candidate) is True
