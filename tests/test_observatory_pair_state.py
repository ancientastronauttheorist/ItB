from __future__ import annotations

import json

import pytest

from scripts import itb_observatory_pair_state as pair_state


def _save_root(tmp_path):
    root = tmp_path / "Into The Breach"
    profile = root / "profile_Alpha"
    profile.mkdir(parents=True)
    (profile / "saveData.lua").write_text("GameData = {}\n", encoding="utf-8")
    nested = profile / "nested"
    nested.mkdir()
    (nested / "state.bin").write_bytes(b"state\x00bytes")
    for name in pair_state.TOP_LEVEL_FILES:
        (root / name).write_text(f"{name}\n", encoding="utf-8")
    return root


def test_snapshot_verify_and_restore_exact_profile(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pair_state, "_game_running", lambda: False)
    save_root = _save_root(tmp_path)
    snapshot_root = tmp_path / "snapshot"
    assert pair_state.main(
        [
            "snapshot",
            "--save-root",
            str(save_root),
            "--output-root",
            str(snapshot_root),
            "--capture-track",
            "owner_local_modified",
        ]
    ) == 0
    manifest = json.loads(
        (snapshot_root / pair_state.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert manifest["capture_track"] == "owner_local_modified"
    assert manifest["file_count"] == 5
    assert len(manifest["tree_sha256"]) == 64
    assert pair_state.main(
        ["verify", "--save-root", str(save_root), "--snapshot-root", str(snapshot_root)]
    ) == 0
    proof_output = tmp_path / "start-state-proof.json"
    assert pair_state.main(
        [
            "prove",
            "--save-root",
            str(save_root),
            "--snapshot-root",
            str(snapshot_root),
            "--proof-output",
            str(proof_output),
        ]
    ) == 0
    proof = json.loads(proof_output.read_text(encoding="utf-8"))
    assert proof["game_stopped"] is True
    assert proof["manifest"] == manifest
    assert len(proof["manifest_sha256"]) == 64

    save_data = save_root / "profile_Alpha" / "saveData.lua"
    save_data.write_text("changed\n", encoding="utf-8")
    extra = save_root / "profile_Alpha" / "runtime_extra.txt"
    extra.write_text("remove on restore\n", encoding="utf-8")
    unrelated = save_root / "do_not_remove.txt"
    unrelated.write_text("preserve\n", encoding="utf-8")
    assert pair_state.main(
        ["verify", "--save-root", str(save_root), "--snapshot-root", str(snapshot_root)]
    ) == 2
    assert pair_state.main(
        ["restore", "--save-root", str(save_root), "--snapshot-root", str(snapshot_root)]
    ) == 2
    assert pair_state.main(
        [
            "restore",
            "--save-root",
            str(save_root),
            "--snapshot-root",
            str(snapshot_root),
            "--allow-restore",
        ]
    ) == 0
    assert save_data.read_text(encoding="utf-8") == "GameData = {}\n"
    assert not extra.exists()
    assert unrelated.read_text(encoding="utf-8") == "preserve\n"
    assert pair_state.main(
        ["verify", "--save-root", str(save_root), "--snapshot-root", str(snapshot_root)]
    ) == 0
    capsys.readouterr()


def test_snapshot_refuses_running_game_or_existing_output(
    tmp_path,
    monkeypatch,
):
    save_root = _save_root(tmp_path)
    snapshot_root = tmp_path / "snapshot"
    monkeypatch.setattr(pair_state, "_game_running", lambda: True)
    assert pair_state.main(
        [
            "snapshot",
            "--save-root",
            str(save_root),
            "--output-root",
            str(snapshot_root),
            "--capture-track",
            "owner_local_modified",
        ]
    ) == 2
    monkeypatch.setattr(pair_state, "_game_running", lambda: False)
    snapshot_root.mkdir()
    assert pair_state.main(
        [
            "snapshot",
            "--save-root",
            str(save_root),
            "--output-root",
            str(snapshot_root),
            "--capture-track",
            "owner_local_modified",
        ]
    ) == 2


def test_start_state_proof_refuses_a_running_game(tmp_path, monkeypatch):
    save_root = _save_root(tmp_path)
    snapshot_root = tmp_path / "snapshot"
    monkeypatch.setattr(pair_state, "_game_running", lambda: False)
    assert pair_state.main(
        [
            "snapshot",
            "--save-root",
            str(save_root),
            "--output-root",
            str(snapshot_root),
            "--capture-track",
            "owner_local_modified",
        ]
    ) == 0
    monkeypatch.setattr(pair_state, "_game_running", lambda: True)

    with pytest.raises(pair_state.PairStateError, match="before proving"):
        pair_state.build_start_state_verification_proof(save_root, snapshot_root)


def test_session_sandbox_preserves_strategy_and_resets_execution_state(tmp_path):
    source = tmp_path / "active_session.json"
    output = tmp_path / "pair_control_session.json"
    source.write_text(
        json.dumps(
            {
                "run_id": "live-run",
                "mission_index": 7,
                "current_mission": "Mission_Power",
                "current_turn": 1,
                "tags": ["achievement"],
                "achievement_targets": ["hold_the_door"],
                "dirty_consent_used": ["used-token"],
                "actions_executed": 3,
                "active_solution": {"turn": 1},
                "held_end_turn_block": {"blocking": True},
                "end_turn_plan_ledger": [{"turn": 1}],
                "post_enemy_block": {"blocking": True},
                "recorded_post_enemy_turns": [[7, 1]],
            }
        ),
        encoding="utf-8",
    )

    assert pair_state.main(
        [
            "session-sandbox",
            "--source-session",
            str(source),
            "--output-session",
            str(output),
            "--experiment-id",
            "pair012_control",
        ]
    ) == 0
    sandbox = json.loads(output.read_text(encoding="utf-8"))
    assert sandbox["run_id"] == "live-run-observatory-pair012_control"
    assert sandbox["mission_index"] == 7
    assert sandbox["tags"] == ["achievement"]
    assert sandbox["achievement_targets"] == ["hold_the_door"]
    assert sandbox["dirty_consent_used"] == []
    assert sandbox["actions_executed"] == 0
    assert sandbox["active_solution"] is None
    assert sandbox["held_end_turn_block"] is None
    assert sandbox["end_turn_plan_ledger"] is None
    assert sandbox["post_enemy_block"] is None
    assert sandbox["recorded_post_enemy_turns"] == []
    assert pair_state.main(
        [
            "session-sandbox",
            "--source-session",
            str(source),
            "--output-session",
            str(output),
            "--experiment-id",
            "pair012_control",
        ]
    ) == 2


def test_game_running_ignores_tasklist_no_match_diagnostic(monkeypatch):
    class Result:
        returncode = 0
        stdout = (
            'INFO: No tasks are running which match the specified criteria '
            '"Breach.exe".\n'
        )

    monkeypatch.setattr(pair_state.os, "name", "nt")
    monkeypatch.setattr(pair_state.subprocess, "run", lambda *args, **kwargs: Result())
    assert pair_state._game_running() is False


def test_game_running_accepts_exact_csv_image_name(monkeypatch):
    class Result:
        returncode = 0
        stdout = '"Breach.exe","3888","Console","4","123,456 K"\n'

    monkeypatch.setattr(pair_state.os, "name", "nt")
    monkeypatch.setattr(pair_state.subprocess, "run", lambda *args, **kwargs: Result())
    assert pair_state._game_running() is True


def test_game_running_fails_closed_when_tasklist_fails(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(pair_state.os, "name", "nt")
    monkeypatch.setattr(pair_state.subprocess, "run", lambda *args, **kwargs: Result())

    with pytest.raises(pair_state.PairStateError, match="tasklist failed"):
        pair_state._game_running()


@pytest.mark.parametrize("relative", ("../outside", "/absolute", "a/../../outside"))
def test_safe_member_rejects_path_escape(tmp_path, relative):
    with pytest.raises(pair_state.PairStateError):
        pair_state._safe_member(tmp_path.resolve(), relative)
