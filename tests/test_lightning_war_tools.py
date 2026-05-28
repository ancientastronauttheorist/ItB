from __future__ import annotations

import json
from types import SimpleNamespace

from src.loop import commands
from src.loop.session import RunSession


def test_lightning_loop_clicks_end_turn_plan(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0, "clicks": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        if calls["auto_turn"] == 1:
            return {
                "status": "PLAN",
                "turn": 1,
                "actions_completed": 3,
                "score": 123,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 2}

    def fake_click(plan):
        calls["clicks"] += 1
        return {"status": "OK", "x": 341, "y": 152}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(commands, "_click_end_turn_from_plan_result", fake_click)
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(max_turns=3)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["end_turn_clicks"] == 1
    assert calls == {"auto_turn": 2, "clicks": 1}


def test_lightning_quiet_call_counts_output_without_result_json(capsys):
    def noisy_command():
        commands._print_result({"status": "OK", "bulk": "x" * 10_000})
        print("small progress line")
        return {"status": "OK"}

    result, output = commands._lightning_quiet_call(noisy_command, quiet=True)

    assert result == {"status": "OK"}
    assert output == {
        "captured_stdout_lines": 1,
        "captured_stdout_chars": len("small progress line\n"),
    }
    assert capsys.readouterr().out == ""


def test_lightning_loop_quiet_compacts_last_turn_result(monkeypatch, capsys):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    def fake_auto_turn(**kwargs):
        return {
            "status": "PLAN",
            "turn": 1,
            "actions_completed": 3,
            "score": 123,
            "batch": [{"type": "left_click", "window_x": 126, "window_y": 120}],
            "codex_computer_use_batch": [{"x": 126, "y": 120}],
            "fuzzy_detections": [{"large": "x" * 10_000}],
            "threat_audit": {"entries": [{}, {}]},
            "debug_bulk": "x" * 10_000,
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)

    result = commands.cmd_lightning_loop(
        max_turns=1,
        click_end_turn=False,
        quiet=True,
    )

    assert result["reason"] == "end_turn_plan_ready_no_click"
    assert result["last_turn_result"]["batch"][0]["window_x"] == 126
    assert result["last_turn_result"]["fuzzy_detections_count"] == 1
    assert result["last_turn_result"]["threat_audit_entries"] == 2
    assert "debug_bulk" not in result["last_turn_result"]
    assert "LIGHTNING LOOP START" not in capsys.readouterr().out


def test_lightning_loop_passes_dirty_consent_to_first_turn_only(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    def fake_auto_turn(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "status": "PLAN",
                "turn": 4,
                "actions_completed": 3,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 5}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(
        max_turns=2,
        allow_dirty_plan=True,
        candidate_rank=7,
        dirty_consent_id="abc123",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
    )

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 7
    assert calls[0]["dirty_consent_id"] == "abc123"
    assert calls[0]["allow_protected_objective_loss"] is True
    assert calls[0]["allow_objective_loss"] is True
    assert calls[1]["allow_dirty_plan"] is False
    assert calls[1]["candidate_rank"] is None
    assert calls[1]["dirty_consent_id"] is None


def test_lightning_loop_passes_speed_loss_policy_to_every_turn(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    def fake_auto_turn(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "status": "PLAN",
                "turn": 1,
                "actions_completed": 3,
                "batch": [{"type": "left_click", "x": 341, "y": 152}],
            }
        return {"status": "TERMINAL_OR_MISSION_END", "turn": 2}

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "OK", "reason": "phase_changed"},
    )

    result = commands.cmd_lightning_loop(
        max_turns=2,
        lightning_speed_loss_policy=True,
    )

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert [call["lightning_speed_loss_policy"] for call in calls] == [True, True]


def test_lightning_ui_clicks_known_control_dry_run():
    result = commands.cmd_lightning_ui("deploy_confirm", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "deploy_confirm"
    assert result["window_x"] == 106
    assert result["window_y"] == 164


def test_lightning_ui_clicks_deploy_slot_alias_dry_run():
    result = commands.cmd_lightning_ui("deploy1", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "deploy_slot_1"
    assert result["window_x"] == 102
    assert result["window_y"] == 388


def test_lightning_ui_clicks_understood_alias_dry_run():
    result = commands.cmd_lightning_ui("understood", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "modal_understood"
    assert result["window_x"] == 666
    assert result["window_y"] == 518


def test_lightning_ui_clicks_panel_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("perfect_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "panel_continue"
    assert result["window_x"] == 846
    assert result["window_y"] == 550


def test_lightning_ui_clicks_ceo_continue_alias_dry_run():
    result = commands.cmd_lightning_ui("ceo_continue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "bottom_continue"
    assert result["window_x"] == 1005
    assert result["window_y"] == 676


def test_lightning_ui_clicks_pod_open_alias_dry_run():
    result = commands.cmd_lightning_ui("open_pod", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "pod_open_door"
    assert result["window_x"] == 965
    assert result["window_y"] == 485


def test_lightning_ui_clicks_dialogue_textbox_alias_dry_run():
    result = commands.cmd_lightning_ui("dialogue", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "dialogue_textbox"
    assert result["window_x"] == 520
    assert result["window_y"] == 205


def test_lightning_ui_clicks_mission_preview_board_alias_dry_run():
    result = commands.cmd_lightning_ui("start_mission", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "mission_preview_board"
    assert result["window_x"] == 815
    assert result["window_y"] == 468


def test_lightning_ui_clicks_perfect_grid_reward_alias_dry_run():
    result = commands.cmd_lightning_ui("grid_reward", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "perfect_reward_grid"
    assert result["window_x"] == 817
    assert result["window_y"] == 480


def test_lightning_ui_clicks_leave_island_alias_dry_run():
    result = commands.cmd_lightning_ui("next_island", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "leave_island"
    assert result["window_x"] == 641
    assert result["window_y"] == 704


def test_lightning_ui_clicks_leave_confirm_alias_dry_run():
    result = commands.cmd_lightning_ui("confirm_leave", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "leave_confirm_yes"
    assert result["window_x"] == 568
    assert result["window_y"] == 444


def test_lightning_ui_clicks_rst_island_alias_dry_run():
    result = commands.cmd_lightning_ui("rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["control"] == "island_rst"
    assert result["window_x"] == 345
    assert result["window_y"] == 508


def test_lightning_ui_clicks_known_control_sequence_dry_run():
    result = commands.cmd_lightning_ui("menu_continue+rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "island_rst",
    ]
    assert result["sequence"][1]["window_x"] == 345


def test_lightning_ui_burst_to_rst_dry_run():
    result = commands.cmd_lightning_ui("to_rst", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["burst"] == "to_rst"
    assert [item["name"] for item in result["sequence"]] == [
        "menu_continue",
        "island_rst",
    ]


def test_lightning_ui_ensure_pause_dry_run_plans_pause(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_ui("ensure_pause", dry_run=True)

    assert result["status"] == "DRY_RUN"
    assert result["planned_control"] == "pause"
    assert result["visible_ui"]["visible_ui"] == "island_map_or_unknown"


def test_lightning_ui_ensure_pause_recognizes_pause_menu(monkeypatch):
    session = RunSession(run_id="lw", squad="Blitzkrieg", difficulty=0)

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_write_guard",
        lambda *args, **kwargs: {"status": "OK", "path": "guard.json"},
    )

    result = commands.cmd_lightning_ui("ensure_pause")

    assert result["status"] == "OK"
    assert result["already_paused"] is True
    assert result["reason"] == "already_paused"


def test_lightning_ui_handle_screen_clicks_visible_panel(monkeypatch):
    calls = []

    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "promotion_panel",
            "recommended_control": "modal_understood",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append((control, kwargs))
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_ui("handle_screen")

    assert result["status"] == "OK"
    assert result["control"] == "modal_understood"
    assert calls == [("modal_understood", {"dry_run": False})]


def test_lightning_peek_dry_run_plans_micro_burst(monkeypatch, tmp_path):
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )

    result = commands.cmd_lightning_peek(
        "turn3",
        out_dir=str(tmp_path),
        dry_run=True,
    )

    assert result["status"] == "DRY_RUN"
    assert result["planned_controls"] == ["menu_continue", "screenshot", "pause"]
    assert result["screenshot_path"].endswith("_turn3.png")


def test_lightning_peek_refuses_when_not_paused(monkeypatch):
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    )

    result = commands.cmd_lightning_peek("not_paused")

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "not_in_pause_menu"


def test_lightning_peek_captures_between_continue_and_pause(monkeypatch, tmp_path):
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "screenshot_path": str(path)},
    )
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_peek(
        "evidence",
        out_dir=str(tmp_path),
        note="micro peek test",
    )

    assert result["status"] == "OK"
    assert clicks == ["menu_continue", "pause"]
    assert result["evidence_ui"]["visible_ui"] == "island_map_or_unknown"
    assert result["note_written"] is True
    assert (tmp_path / "notes.md").exists()


def test_lightning_peek_pauses_even_when_capture_fails(monkeypatch, tmp_path):
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "ERROR", "error": "boom"},
    )

    result = commands.cmd_lightning_peek("capture_fail", out_dir=str(tmp_path))

    assert result["status"] == "ERROR"
    assert result["reason"] == "screenshot_failed"
    assert clicks == ["menu_continue", "pause"]
    assert result["note_written"] is False


def test_lightning_peek_blocks_when_pause_not_verified(monkeypatch, tmp_path):
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pause_menu",
                "recommended_control": "menu_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )

    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click._get_window_bounds",
        lambda app_name: {"x": 10, "y": 20, "width": 1280, "height": 748},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_click_control_with_bounds",
        lambda control, **kwargs: {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_capture_window_screenshot",
        lambda path, **kwargs: {"status": "OK", "screenshot_path": str(path)},
    )
    monkeypatch.setattr(
        commands,
        "_classify_lightning_ui_image",
        lambda path: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_peek("not_repaused", out_dir=str(tmp_path))

    assert result["status"] == "BLOCKED"
    assert result["reason"] == "pause_not_verified_after_peek"


def test_lightning_attempt_pause_on_stop_attaches_guard(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {"status": "OK", "top3": [{"mission_id": "Mission_Train"}]},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(pause_on_stop=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["pause_guard"] == {"status": "OK", "reason": "pause_clicked"}


def test_lightning_attempt_resumes_from_pause_before_routing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {"status": "OK", "top3": [{"mission_id": "Mission_Train"}]},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(
        resume_if_paused=True,
        pause_on_stop=True,
    )

    assert calls == ["menu_continue"]
    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["resume_guard"]["reason"] == "resumed_from_pause"


def test_lightning_attempt_dry_run_reports_resume_needed(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "pause_menu",
            "recommended_control": "menu_continue",
        },
    )

    result = commands.cmd_lightning_attempt(resume_if_paused=True, dry_run=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_UI_READY"
    assert result["resume_guard"]["status"] == "DRY_RUN"
    assert result["resume_guard"]["planned_control"] == "menu_continue"


def test_lightning_ui_classifier_scales_retina_pause_menu(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (12, 14, 20))
    draw = ImageDraw.Draw(image)
    cx, cy = 491 * scale, 251 * scale
    w, h = 320 * scale, 100 * scale
    rect = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    draw.rectangle(rect, fill=(22, 29, 42), outline=(85, 110, 165), width=10)
    draw.rectangle(
        [cx - 90 * scale, cy - 18 * scale, cx + 90 * scale, cy + 18 * scale],
        fill=(235, 235, 235),
    )
    path = tmp_path / "pause_menu.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "pause_menu"
    assert result["recommended_control"] == "menu_continue"
    assert result["dark_overlay_fraction"] >= 0.70


def test_lightning_ui_classifier_rejects_live_combat_button_shapes(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (70, 90, 70))
    draw = ImageDraw.Draw(image)
    cx, cy = 1005 * scale, 676 * scale
    w, h = 300 * scale, 100 * scale
    rect = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    draw.rectangle(rect, fill=(20, 28, 40), outline=(85, 110, 165), width=10)
    draw.rectangle(
        [cx - 80 * scale, cy - 16 * scale, cx + 80 * scale, cy + 16 * scale],
        fill=(240, 240, 240),
    )
    path = tmp_path / "combat_like.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map_or_unknown"
    assert result["recommended_control"] is None
    assert result["dark_overlay_fraction"] < 0.60


def test_lightning_ui_classifier_detects_visible_island_map(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (24, 30, 42))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [
            (570 * scale, 250 * scale),
            (810 * scale, 220 * scale),
            (960 * scale, 520 * scale),
            (770 * scale, 650 * scale),
            (580 * scale, 500 * scale),
        ],
        fill=(185, 45, 50),
    )
    draw.polygon(
        [
            (900 * scale, 460 * scale),
            (1060 * scale, 500 * scale),
            (1020 * scale, 640 * scale),
            (880 * scale, 610 * scale),
        ],
        fill=(55, 135, 70),
    )
    path = tmp_path / "island_map.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "island_map"
    assert result["recommended_control"] is None


def test_lightning_ui_classifier_prioritizes_mission_preview(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    # A dialogue box can make the pause-menu crop look button-like; the
    # explicit Start Mission detector should win.
    draw.rectangle(
        [
            (491 - 160) * scale,
            (251 - 50) * scale,
            (491 + 160) * scale,
            (251 + 50) * scale,
        ],
        fill=(20, 26, 38),
        outline=(85, 110, 165),
        width=10,
    )
    cx, cy = 815 * scale, 468 * scale
    draw.rectangle(
        [cx - 160 * scale, cy - 32 * scale, cx + 160 * scale, cy + 32 * scale],
        fill=(235, 220, 35),
    )
    path = tmp_path / "mission_preview.png"
    image.save(path)

    result = commands._classify_lightning_ui_image(path)

    assert result["visible_ui"] == "mission_preview_panel"
    assert result["recommended_control"] == "mission_preview_board"


def test_lightning_start_mission_target_detects_yellow_text(tmp_path):
    from PIL import Image, ImageDraw

    scale = 2
    image = Image.new("RGB", (1280 * scale, 748 * scale), (8, 10, 14))
    draw = ImageDraw.Draw(image)
    cx, cy = 930 * scale, 545 * scale
    draw.rectangle(
        [cx - 120 * scale, cy - 28 * scale, cx + 120 * scale, cy + 28 * scale],
        fill=(235, 220, 35),
    )
    path = tmp_path / "start_text.png"
    image.save(path)

    result = commands._lightning_start_mission_target(path)

    assert result["status"] == "OK"
    assert 900 <= result["window_x"] <= 960
    assert 520 <= result["window_y"] <= 570


def test_lightning_attempt_deploys_confirms_and_runs_loop(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 4,
        },
    )

    def fake_deploy(**kwargs):
        calls.append(("deploy", kwargs))
        return {"status": "OK"}

    def fake_click(name, **kwargs):
        calls.append(("click", name))
        return {"status": "OK", "control": name}

    def fake_loop(**kwargs):
        calls.append(("loop", kwargs))
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_deploy_recommended", fake_deploy)
    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        fake_click,
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["reason"] == "combat_loop_returned"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]
    assert calls[1] == ("click", "deploy_confirm")
    assert result["action"]["max_wait_floor"] == 30.0
    assert calls[2][1]["max_wait"] == 30.0


def test_lightning_attempt_deploys_when_bridge_reports_enemy_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
        },
    )

    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]


def test_lightning_attempt_finishes_partial_deployment_before_waiting(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 1,
            "mech_count": 1,
            "deployment_zone_count": 5,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "finish_deployment_then_combat"
    assert [call[0] for call in calls] == ["deploy", "click", "loop"]
    assert calls[2][1]["max_wait"] == 30.0


def test_lightning_attempt_does_not_deploy_from_unknown_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not deploy")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "deployment_bridge_state_uncertain"


def test_lightning_attempt_does_not_deploy_from_visible_island_map(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 0,
            "deployment_zone_count": 11,
            "in_active_mission": True,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not deploy")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "deployment_bridge_state_uncertain"


def test_lightning_attempt_uses_visible_island_map_when_bridge_missing(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_NEEDS_UI"
    assert result["reason"] == "bridge_snapshot_unavailable_visible_island_map"
    assert result["snapshot"]["visible_ui"]["visible_ui"] == "island_map"


def test_lightning_attempt_clicks_preview_then_deploys(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []
    snapshots = iter(
        [
            {
                "status": "OK",
                "phase": "unknown",
                "turn": 0,
                "active_mechs": 0,
                "mech_count": 0,
                "deployment_zone_count": 10,
                "in_active_mission": True,
            },
            {
                "status": "OK",
                "phase": "combat_player",
                "turn": 0,
                "active_mechs": 0,
                "mech_count": 0,
                "deployment_zone_count": 10,
                "in_active_mission": True,
            },
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(commands, "_lightning_live_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "mission_preview_panel",
            "recommended_control": "mission_preview_board",
        },
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda name, **kwargs: calls.append(("click", name)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_deploy_recommended",
        lambda **kwargs: calls.append(("deploy", kwargs)) or {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: calls.append(("loop", kwargs)) or {"status": "OK"},
    )

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert calls[0] == ("click", "mission_preview_board")
    assert calls[1][0] == "deploy"
    assert calls[2] == ("click", "deploy_confirm")
    assert calls[3][0] == "loop"


def test_lightning_attempt_runs_combat_loop_on_active_turn(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )

    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)

    result = commands.cmd_lightning_attempt(
        time_limit=1.5,
        max_turns=4,
        allow_dirty_plan=True,
        candidate_rank=2,
        dirty_consent_id="dirty-ok",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "combat_loop"
    assert calls[0]["time_limit"] == 1.5
    assert calls[0]["max_turns"] == 4
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 2
    assert calls[0]["dirty_consent_id"] == "dirty-ok"
    assert calls[0]["allow_protected_objective_loss"] is True
    assert calls[0]["allow_objective_loss"] is True


def test_lightning_attempt_runs_loop_through_enemy_phase(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_enemy",
            "turn": 0,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 8,
        },
    )
    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)

    result = commands.cmd_lightning_attempt(max_wait=10)

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["action"]["action"] == "wait_then_combat_loop"
    assert result["action"]["max_wait_floor"] == 30.0
    assert calls[0]["max_wait"] == 30.0


def test_lightning_attempt_stops_quickly_on_player_phase_without_active_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 2,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    def fake_loop(**kwargs):
        calls.append(kwargs)
        return {"status": "LIGHTNING_LOOP_STOPPED", "reason": "mission_end"}

    monkeypatch.setattr(commands, "cmd_lightning_loop", fake_loop)
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "island_map_or_unknown",
            "recommended_control": None,
        },
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_STOPPED"
    assert result["reason"] == "player_turn_no_active_mechs"
    assert calls == []


def test_lightning_attempt_clears_safe_panel_when_no_active_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    clicks = []
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "pod_open_panel",
                "recommended_control": "pod_open_door",
            },
            {
                "status": "OK",
                "visible_ui": "pod_open_panel",
                "recommended_control": "pod_open_door",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 3,
            "active_mechs": 0,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: next(visible_states),
    )
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: clicks.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_attempt(auto_clear_panels=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "auto_clear_safe_panel_during_no_active_mechs"
    assert result["action"]["clear_result"]["reason"] == "panel_chain_cleared"
    assert clicks == ["pod_open_door"]


def test_lightning_attempt_recommends_route_on_island_map(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 0,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: {"status": "OK", "top3": [{"mission_id": "Mission_Train"}]},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {"status": "OK", "visible_ui": "island_map_or_unknown"},
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_ROUTE_READY"
    assert result["recommendation"]["top3"][0]["mission_id"] == "Mission_Train"


def test_lightning_attempt_panel_precedes_route_recommendation(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_visible_ui_snapshot",
        lambda: {
            "status": "OK",
            "visible_ui": "promotion_panel",
            "recommended_control": "modal_understood",
            "confidence": 1.2,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt()

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_READY"
    assert result["recommended_control"] == "modal_understood"


def test_lightning_attempt_auto_clears_safe_panel(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "confidence": 1.2,
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
                "confidence": 1.2,
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
                "confidence": 0.1,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["action"]["control"] == "reward_continue"
    assert calls == ["reward_continue"]
    assert result["pause_guard"]["status"] == "OK"


def test_lightning_attempt_auto_clears_chained_pod_panels(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "unknown",
            "turn": 4,
            "deployment_zone_count": 0,
            "island_map_count": 3,
        },
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "pod_open_panel",
                "recommended_control": "pod_open_door",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(
        commands,
        "cmd_recommend_mission",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not route")),
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert calls == ["reward_continue", "pod_open_door", "reward_continue"]
    assert result["action"]["clear_result"]["reason"] == "panel_chain_cleared"


def test_lightning_attempt_auto_clears_safe_panel_without_bridge(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = []

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {"status": "NO_BRIDGE"},
    )
    visible_states = iter(
        [
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "reward_panel",
                "recommended_control": "reward_continue",
            },
            {
                "status": "OK",
                "visible_ui": "island_map_or_unknown",
                "recommended_control": None,
            },
        ]
    )
    monkeypatch.setattr(commands, "_lightning_visible_ui_snapshot", lambda: next(visible_states))
    monkeypatch.setattr(
        "src.control.mac_click.click_known_window_control",
        lambda control, **kwargs: calls.append(control)
        or {"status": "OK", "control": control},
    )

    result = commands.cmd_lightning_attempt(auto_clear_panels=True)

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "auto_clear_safe_panel_without_bridge"
    assert result["action"]["control"] == "reward_continue"
    assert calls == ["reward_continue"]


def test_lightning_attempt_auto_clears_post_combat_panels(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"clear": 0}

    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "cmd_lightning_preflight",
        lambda **kwargs: {"status": "PASS"},
    )
    monkeypatch.setattr(
        commands,
        "_lightning_live_snapshot",
        lambda: {
            "status": "OK",
            "phase": "combat_player",
            "turn": 4,
            "active_mechs": 3,
            "mech_count": 3,
            "deployment_zone_count": 0,
        },
    )
    monkeypatch.setattr(
        commands,
        "cmd_lightning_loop",
        lambda **kwargs: {
            "status": "LIGHTNING_LOOP_STOPPED",
            "reason": "terminal_or_mission_end",
        },
    )

    def fake_clear(**kwargs):
        calls["clear"] += 1
        return {
            "status": "OK",
            "reason": "panel_chain_cleared",
            "steps": [
                {
                    "control": "reward_continue",
                    "click_result": {"status": "OK"},
                }
            ],
        }

    monkeypatch.setattr(commands, "_lightning_clear_visible_panel_chain", fake_clear)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )

    result = commands.cmd_lightning_attempt(
        auto_clear_panels=True,
        pause_on_stop=True,
    )

    assert result["status"] == "LIGHTNING_ATTEMPT_PANEL_CLEARED"
    assert result["reason"] == "post_combat_auto_clear_safe_panel"
    assert result["action"]["post_combat_clear_result"]["reason"] == "panel_chain_cleared"
    assert result["pause_guard"]["status"] == "OK"
    assert calls["clear"] == 1


def test_lightning_segment_continues_panel_clear_to_route_ready(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_PANEL_CLEARED",
                "reason": "auto_clear_safe_panel",
                "action": {
                    "action": "clear_visible_panel",
                    "clear_result": {"status": "OK", "steps": [{}]},
                },
            },
            {
                "status": "LIGHTNING_ATTEMPT_ROUTE_READY",
                "recommendation": {
                    "top3": [{"mission_id": "Mission_Train", "region_id": 2}],
                },
            },
        ]
    )
    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment()

    assert result["reason"] == "route_ready"
    assert result["steps_attempted"] == 2
    assert result["steps"][0]["panel_clear_steps"] == 1
    assert result["steps"][1]["top_mission"] == "Mission_Train"
    assert calls[0]["run_preflight"] is True
    assert calls[1]["run_preflight"] is False
    assert all(call["pause_on_stop"] is False for call in calls)
    assert all(call["lightning_speed_loss_policy"] is True for call in calls)
    assert result["pause_guard"]["status"] == "OK"


def test_lightning_segment_dirty_consent_survives_panel_clear_until_combat(monkeypatch):
    attempts = iter(
        [
            {
                "status": "LIGHTNING_ATTEMPT_PANEL_CLEARED",
                "reason": "auto_clear_safe_panel",
                "action": {"action": "clear_visible_panel"},
            },
            {
                "status": "LIGHTNING_ATTEMPT_STOPPED",
                "reason": "combat_loop_returned",
                "action": {
                    "action": "combat_loop",
                    "combat_loop": {"reason": "SAFETY_BLOCKED"},
                },
            },
        ]
    )
    calls = []

    def fake_attempt(**kwargs):
        calls.append(kwargs)
        return next(attempts)

    monkeypatch.setattr(commands, "cmd_lightning_attempt", fake_attempt)
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "pause_clicked"},
    )
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)

    result = commands.cmd_lightning_segment(
        allow_dirty_plan=True,
        candidate_rank=17,
        dirty_consent_id="dirty-ok",
        allow_protected_objective_loss=True,
        allow_objective_loss=True,
    )

    assert result["reason"] == "combat_loop_returned"
    assert result["dirty_consent_still_pending"] is False
    assert calls[0]["allow_dirty_plan"] is True
    assert calls[0]["candidate_rank"] == 17
    assert calls[0]["dirty_consent_id"] == "dirty-ok"
    assert calls[1]["allow_dirty_plan"] is True
    assert calls[1]["candidate_rank"] == 17
    assert calls[1]["dirty_consent_id"] == "dirty-ok"


def test_lightning_segment_stops_on_visible_map_without_bridge(monkeypatch):
    monkeypatch.setattr(
        commands,
        "cmd_lightning_attempt",
        lambda **kwargs: {
            "status": "LIGHTNING_ATTEMPT_NEEDS_UI",
            "reason": "bridge_snapshot_unavailable_visible_island_map",
        },
    )
    monkeypatch.setattr(
        commands,
        "_lightning_ensure_pause_state",
        lambda **kwargs: {"status": "OK", "reason": "already_paused"},
    )

    result = commands.cmd_lightning_segment(max_steps=3)

    assert result["reason"] == "visible_island_map_without_bridge"
    assert result["steps_attempted"] == 1
    assert result["pause_guard"]["status"] == "OK"


def test_deploy_recommended_skips_already_placed_mechs(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    placed = {0: (2, 3)}
    deploy_calls = []

    def board():
        return SimpleNamespace(
            units=[
                SimpleNamespace(uid=uid, type=f"Mech{uid}", is_mech=True, hp=3, x=x, y=y)
                for uid, (x, y) in placed.items()
            ]
        )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            board(),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 3], [2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
            {"uid": 2, "type": "RockartMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 3, "hazard": None, "hazard_warning": False},
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y))
        placed[uid] = (x, y)
        return "OK"

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "OK"
    assert deploy_calls == [(1, 2, 4), (2, 3, 3)]
    assert [entry["uid"] for entry in result["deployments"]] == [1, 2]
    assert result["existing_deployments"] == {"0": [2, 3]}


def test_deploy_recommended_recovers_when_timeout_still_places_mech(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    placed = {}
    deploy_calls = []

    def board():
        return SimpleNamespace(
            units=[
                SimpleNamespace(uid=uid, type=f"Mech{uid}", is_mech=True, hp=3, x=x, y=y)
                for uid, (x, y) in placed.items()
            ]
        )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            board(),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda max_stale_sec=1.0: True)
    monkeypatch.setattr(
        commands,
        "_deployment_click_fallback",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("should recover through bridge read")
        ),
    )
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y))
        placed[uid] = (x, y)
        if uid == 0:
            raise TimeoutError("late ACK")
        return "OK"

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "OK"
    assert deploy_calls == [(0, 2, 4), (1, 3, 3)]
    assert result["deployments"][0]["timeout_recovered"] is True
    assert result["deployments"][0]["ack"].startswith("ACK_TIMEOUT_BUT_PLACED")


def test_deploy_recommended_uses_ui_fallback_when_bridge_deploy_times_out(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    deploy_calls = []
    fallback_calls = []

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "refresh_bridge_state", lambda: None)
    monkeypatch.setattr(
        commands,
        "read_bridge_state",
        lambda: (
            SimpleNamespace(units=[]),
            {
                "turn": 0,
                "phase": "combat_player",
                "deployment_zone": [[2, 4], [3, 3], [3, 4]],
            },
        ),
    )
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda max_stale_sec=1.0: False)
    monkeypatch.setattr(
        commands,
        "_clear_pending_bridge_command",
        lambda reason: {"status": "OK", "reason": reason, "cleared": ["cmd"]},
    )
    monkeypatch.setattr(
        commands,
        "_deployable_mechs",
        lambda _board, _session, profile="Alpha": [
            {"uid": 0, "type": "ElectricMech"},
            {"uid": 1, "type": "WallMech"},
            {"uid": 2, "type": "RockartMech"},
        ],
    )
    monkeypatch.setattr(
        commands,
        "recommend_deploy_tiles",
        lambda _board, _zone: [
            {"x": 2, "y": 4, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 3, "hazard": None, "hazard_warning": False},
            {"x": 3, "y": 4, "hazard": None, "hazard_warning": False},
        ],
    )

    def fake_deploy(uid, x, y, *, timeout=None):
        deploy_calls.append((uid, x, y, timeout))
        raise TimeoutError("deployment bridge asleep")

    def fake_fallback(pairs, *, reason, dry_run=False):
        fallback_calls.append({
            "pairs": [
                (int(mech["uid"]), int(tile["x"]), int(tile["y"]))
                for mech, tile in pairs
            ],
            "reason": reason,
        })
        return {
            "status": "OK",
            "reason": reason,
            "steps": [
                {
                    "uid": int(mech["uid"]),
                    "mech_type": mech["type"],
                    "bridge": [int(tile["x"]), int(tile["y"])],
                    "visual": commands._visual_tile(int(tile["x"]), int(tile["y"])),
                }
                for mech, tile in pairs
            ],
        }

    monkeypatch.setattr(commands, "deploy_mech", fake_deploy)
    monkeypatch.setattr(commands, "_deployment_click_fallback", fake_fallback)

    result = commands.cmd_deploy_recommended()

    assert result["status"] == "WARN"
    assert result["reason"] == "bridge_deploy_timed_out_used_ui_fallback"
    assert deploy_calls == [
        (0, 2, 4, commands._LIGHTNING_DEPLOY_BRIDGE_TIMEOUT_SECONDS)
    ]
    assert fallback_calls == [
        {
            "pairs": [(0, 2, 4), (1, 3, 3), (2, 3, 4)],
            "reason": "bridge_deploy_timeout_uid_0",
        }
    ]
    assert [entry["uid"] for entry in result["deployments"]] == [0, 1, 2]
    assert all(entry["ui_fallback"] for entry in result["deployments"])
    assert result["stale_bridge_cleanup"]["cleared"] == ["cmd"]


def test_dirty_consented_ordinary_grid_loss_satisfies_threat_audit():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "D4"}],
    }
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
        ],
        "current": {
            "grid_power": 5,
            "building_hp_total": 9,
            "buildings_alive": 6,
        },
        "predicted": {
            "grid_power": 4,
            "building_hp_total": 8,
            "buildings_alive": 6,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=False,
    ) is True
    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=True,
    ) is False


def test_lightning_speed_loss_policy_allows_train_speed_trade():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_destroyed", "blocking": True},
            {"kind": "building_hp_loss", "blocking": True},
            {"kind": "protected_objective_unit_lost", "blocking": True},
        ],
        "current": {
            "mission_id": "Mission_Train",
            "grid_power": 2,
            "buildings_alive": 7,
            "building_hp_total": 9,
            "protected_objective_units_alive": 1,
            "mechs_alive": 3,
        },
        "predicted": {
            "mission_id": "Mission_Train",
            "grid_power": 1,
            "buildings_alive": 6,
            "building_hp_total": 8,
            "protected_objective_units_alive": 0,
            "mechs_alive": 3,
        },
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is True
    summary = commands._lightning_speed_loss_summary(plan_safety)
    assert summary["status"] == "ALLOWED"
    assert summary["losses"]["grid_power"] == 1
    assert summary["losses"]["protected_objective_units_alive"] == 1


def test_lightning_speed_loss_policy_rejects_timeline_collapse():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "grid_timeline_collapse", "blocking": True},
        ],
        "current": {"grid_power": 1, "mechs_alive": 3},
        "predicted": {"grid_power": 0, "mechs_alive": 3},
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is False


def test_lightning_speed_loss_policy_rejects_mech_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "mech_lost", "blocking": True},
        ],
        "current": {"grid_power": 3, "mechs_alive": 3},
        "predicted": {"grid_power": 2, "mechs_alive": 2},
    }

    assert commands._allow_lightning_war_speed_loss(session, plan_safety) is False


def test_lightning_speed_policy_satisfies_threat_audit_without_dirty_consent():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    threat_audit = {
        "still_threatened_count": 1,
        "entries": [{"target_visual": "E7"}],
    }
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "grid_damage", "blocking": True},
            {"kind": "building_destroyed", "blocking": True},
            {"kind": "protected_objective_unit_lost", "blocking": True},
        ],
        "current": {
            "grid_power": 2,
            "buildings_alive": 7,
            "building_hp_total": 9,
            "protected_objective_units_alive": 1,
        },
        "predicted": {
            "grid_power": 1,
            "buildings_alive": 6,
            "building_hp_total": 8,
            "protected_objective_units_alive": 0,
        },
    }

    assert commands._threat_audit_requires_block(
        threat_audit,
        plan_safety,
        session,
        dirty_consent_validated=False,
        lightning_speed_loss_allowed=True,
    ) is False


def test_lightning_war_allows_pod_only_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "pod_unrecovered_final", "blocking": True},
        ],
    }

    assert commands._allow_lightning_war_pod_loss(session, plan_safety) is True


def test_lightning_war_pod_loss_allowance_does_not_cover_grid_loss():
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    plan_safety = {
        "blocking": True,
        "violations": [
            {"kind": "pod_unrecovered_final", "blocking": True},
            {"kind": "grid_damage", "blocking": True},
        ],
    }

    assert commands._allow_lightning_war_pod_loss(session, plan_safety) is False


def test_lightning_attempt_blocks_on_wall_budget(monkeypatch):
    old_session = RunSession(
        run_id="20000101_000000_000",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    monkeypatch.setattr(commands, "_load_session", lambda: old_session)

    result = commands.cmd_lightning_attempt(max_wall_seconds=1)

    assert result["status"] == "LIGHTNING_ATTEMPT_BUDGET_EXCEEDED"


def test_lightning_loop_blocks_pending_research(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[{"status": "pending", "type": "RockLauncher"}],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)

    result = commands.cmd_lightning_loop(max_turns=1)

    assert result["status"] == "RESEARCH_REQUIRED"
    assert result["pending_research_count"] == 1


def test_lightning_loop_ignores_background_mech_weapon_research(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
        research_queue=[
            {
                "status": "pending",
                "type": "ElectricMech",
                "kind": "mech_weapon",
                "slot": 1,
            }
        ],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "cmd_auto_turn",
        lambda **kwargs: {"status": "TERMINAL_OR_MISSION_END", "turn": 1},
    )

    result = commands.cmd_lightning_loop(max_turns=1)

    assert result["reason"] == "TERMINAL_OR_MISSION_END"
    assert result["turns_attempted"] == 1


def test_click_end_turn_prefers_window_local_coordinates(monkeypatch):
    calls = []

    def fake_window_click(x, y, **kwargs):
        calls.append((x, y, kwargs))
        return {"status": "OK", "window_x": x, "window_y": y}

    monkeypatch.setattr(
        "src.control.mac_click.click_window_point",
        fake_window_click,
    )

    result = commands._click_end_turn_from_plan_result(
        {
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                    "description": "Click End Turn",
                }
            ]
        }
    )

    assert result["status"] == "OK"
    assert calls == [(126, 120, {"description": "Click End Turn", "dry_run": False})]


def test_lightning_loop_stops_when_end_turn_click_not_observed(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        return {
            "status": "PLAN",
            "turn": 2,
            "actions_completed": 3,
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                }
            ],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {"status": "END_TURN_CLICK_NOT_OBSERVED"},
    )

    result = commands.cmd_lightning_loop(max_turns=3)

    assert result["reason"] == "end_turn_click_not_observed"
    assert result["end_turn_clicks"] == 1
    assert result["turns"][0]["end_turn_observed"]["status"] == (
        "END_TURN_CLICK_NOT_OBSERVED"
    )
    assert calls["auto_turn"] == 1


def test_lightning_loop_treats_unknown_after_end_turn_as_mission_end(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )
    calls = {"auto_turn": 0}

    def fake_auto_turn(**kwargs):
        calls["auto_turn"] += 1
        return {
            "status": "PLAN",
            "turn": 4,
            "actions_completed": 3,
            "batch": [
                {
                    "type": "left_click",
                    "x": 341,
                    "y": 152,
                    "window_x": 126,
                    "window_y": 120,
                }
            ],
        }

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(commands, "cmd_auto_turn", fake_auto_turn)
    monkeypatch.setattr(
        commands,
        "_click_end_turn_from_plan_result",
        lambda plan: {"status": "OK"},
    )
    monkeypatch.setattr(
        commands,
        "_observe_end_turn_after_click",
        lambda turn_result: {
            "status": "OK",
            "reason": "phase_changed",
            "samples": [{"phase": "unknown", "turn": 4, "active_mechs": 0}],
        },
    )

    result = commands.cmd_lightning_loop(max_turns=3)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["end_turn_clicks"] == 1
    assert calls["auto_turn"] == 1


def test_lightning_loop_treats_unknown_phase_error_as_mission_end(monkeypatch):
    session = RunSession(
        run_id="lw",
        squad="Blitzkrieg",
        difficulty=0,
        achievement_targets=["Lightning War"],
    )

    monkeypatch.setattr(commands, "is_bridge_active", lambda: True)
    monkeypatch.setattr(commands, "_load_session", lambda: session)
    monkeypatch.setattr(commands, "cmd_bridge_speed", lambda mode: {"status": "OK"})
    monkeypatch.setattr(
        commands,
        "cmd_auto_turn",
        lambda **kwargs: {
            "error": "Not in combat_player phase: unknown",
            "phase": "unknown",
        },
    )

    result = commands.cmd_lightning_loop(max_turns=1)

    assert result["reason"] == "terminal_or_mission_end"
    assert result["turns"][0]["terminal_transition"] is True


def test_recommend_mission_reports_no_available_after_stale_filter(tmp_path):
    payload = {
        "grid_power": 7,
        "units": [
            {"mech": True, "hp": 3, "weapons": ["Prime_Lightning"]},
        ],
        "island_map": [
            {
                "region_id": 1,
                "mission_id": "Mission_Satellite",
                "bonus_objective_ids": [1],
                "environment": "Env_Null",
                "state": "hover_preview",
            },
            {
                "region_id": 2,
                "mission_id": "Mission_Repair",
                "bonus_objective_ids": [],
                "environment": "Env_RepairMission",
                "current": True,
            },
        ],
    }
    path = tmp_path / "stale_island_map.json"
    path.write_text(json.dumps(payload))

    result = commands.cmd_recommend_mission(
        island_map_json=str(path),
        routing="lightning_war",
    )

    assert result["status"] == "NO_AVAILABLE_MISSIONS"
    assert result["available"] == 2
