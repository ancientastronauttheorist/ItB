from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import itb_observatory_spawn_coordinate_capsule_campaign_run as campaign_run


def _args(tmp_path, monkeypatch) -> argparse.Namespace:
    artifact_root = tmp_path / "external-campaign"
    artifact_root.mkdir()
    repo = tmp_path / "repo"
    captures = repo / "data" / "observatory" / "captures"
    captures.mkdir(parents=True)
    monkeypatch.setattr(campaign_run, "ROOT", repo)
    return argparse.Namespace(
        artifact_root=artifact_root,
        repository_campaign_root=captures / "campaign",
        receipt_output=captures / "campaign-receipt.json",
        save_root=tmp_path / "save",
        snapshot_root=tmp_path / "snapshot",
        source_session=tmp_path / "session.json",
        executable=tmp_path / "Breach.exe",
        build_receipt=tmp_path / "build.json",
        module=tmp_path / "observer.dll",
        profile="Alpha",
        time_limit=10.0,
        max_wait=5.0,
        process_wait=5.0,
        bridge_wait=5.0,
        close_wait=5.0,
        wait_poll_interval=0.05,
        candidate_rank=None,
        allow_dirty_plan=False,
        dirty_consent_id=None,
        dirty_consent_map=None,
        allow_protected_objective_loss=False,
        allow_objective_loss=False,
        allow_timeline_collapse=False,
        allow_mech_loss=False,
        frontier_diagnostics=True,
    )


def test_campaign_run_uses_counterbalanced_order_restores_imports_and_seals(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path, monkeypatch)
    calls: list[str] = []

    def run_condition(condition_args):
        pair_name = f"pair{condition_args.pair_id[-3:]}"
        key = f"{pair_name}/{condition_args.condition}"
        calls.append(key)
        root = args.artifact_root / pair_name / condition_args.condition
        root.mkdir(parents=True)
        lifecycle = root / "lifecycle.json"
        lifecycle.write_text(json.dumps({"condition": key}), encoding="utf-8")
        digest = campaign_run._sha256(lifecycle)
        return 0, {
            "valid_lifecycle": True,
            "lifecycle_output": {"path": str(lifecycle), "sha256": digest},
        }

    monkeypatch.setattr(campaign_run.condition_runner, "run", run_condition)
    monkeypatch.setattr(
        campaign_run,
        "_final_restore",
        lambda _args: calls.append("final-restore")
        or {"verified_at": "2026-08-29T13:00:00+00:00"},
    )
    monkeypatch.setattr(
        campaign_run,
        "build_spawn_coordinate_capsule_campaign_receipt",
        lambda path, **_kwargs: calls.append(f"validate:{path.name}")
        or {"kind": "synthetic-receipt"},
    )

    def publish(value, output):
        calls.append("publish")
        output.write_text(json.dumps(value), encoding="utf-8")
        return output, campaign_run._sha256(output)

    monkeypatch.setattr(
        campaign_run,
        "publish_spawn_coordinate_capsule_campaign_receipt",
        publish,
    )

    code, result = campaign_run.run(args)

    expected_order = [
        f"{pair_name}/{condition}"
        for pair_name, order in campaign_run.PAIR_SPECS.items()
        for condition in order
    ]
    assert code == 0
    assert result["valid_campaign"] is True
    assert calls[:9] == expected_order
    assert calls[9:] == ["final-restore", "validate:campaign", "publish"]
    assert args.repository_campaign_root.is_dir()
    assert args.receipt_output.is_file()
    lifecycle = json.loads(
        (args.artifact_root / "campaign_lifecycle.json").read_text(encoding="utf-8")
    )
    assert lifecycle["condition_order"] == expected_order


def test_campaign_run_stops_after_rejection_but_attempts_final_restore(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path, monkeypatch)
    calls: list[str] = []

    def reject(condition_args):
        calls.append(condition_args.condition)
        return 2, {"valid_lifecycle": False}

    monkeypatch.setattr(campaign_run.condition_runner, "run", reject)
    monkeypatch.setattr(
        campaign_run,
        "_final_restore",
        lambda _args: calls.append("final-restore")
        or {"verified_at": "2026-08-29T13:00:00+00:00"},
    )

    code, result = campaign_run.run(args)

    assert code == 2
    assert result["valid_campaign"] is False
    assert calls == ["control", "final-restore"]
    assert not args.repository_campaign_root.exists()
    assert (args.artifact_root / "campaign_lifecycle.json").is_file()


def test_campaign_run_attempts_final_restore_when_condition_raises(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path, monkeypatch)
    calls: list[str] = []

    def fail(_condition_args):
        calls.append("condition")
        raise RuntimeError("condition crashed")

    monkeypatch.setattr(campaign_run.condition_runner, "run", fail)
    monkeypatch.setattr(
        campaign_run,
        "_final_restore",
        lambda _args: calls.append("final-restore")
        or {"verified_at": "2026-08-29T13:00:00+00:00"},
    )

    code, result = campaign_run.run(args)

    assert code == 2
    assert result["errors"]["conditions"] == "condition crashed"
    assert calls == ["condition", "final-restore"]


def test_campaign_run_routes_one_exact_dirty_consent_id_per_condition(
    tmp_path,
    monkeypatch,
):
    args = _args(tmp_path, monkeypatch)
    args.allow_dirty_plan = True
    args.candidate_rank = 0
    args.dirty_consent_map = tmp_path / "dirty-consent-map.json"
    expected_keys = campaign_run._condition_keys()
    expected_tokens = {
        key: f"{index:016x}" for index, key in enumerate(expected_keys, start=1)
    }
    args.dirty_consent_map.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "observatory_spawn_coordinate_capsule_dirty_consent_map",
                "conditions": expected_tokens,
            }
        ),
        encoding="utf-8",
    )
    observed: dict[str, str] = {}

    def run_condition(condition_args):
        pair_name = f"pair{condition_args.pair_id[-3:]}"
        key = f"{pair_name}/{condition_args.condition}"
        observed[key] = condition_args.dirty_consent_id
        root = args.artifact_root / pair_name / condition_args.condition
        root.mkdir(parents=True)
        lifecycle = root / "lifecycle.json"
        lifecycle.write_text(json.dumps({"condition": key}), encoding="utf-8")
        return 0, {
            "valid_lifecycle": True,
            "lifecycle_output": {
                "path": str(lifecycle),
                "sha256": campaign_run._sha256(lifecycle),
            },
        }

    monkeypatch.setattr(campaign_run.condition_runner, "run", run_condition)
    monkeypatch.setattr(
        campaign_run,
        "_final_restore",
        lambda _args: {"verified_at": "2026-08-29T13:00:00+00:00"},
    )
    monkeypatch.setattr(
        campaign_run,
        "build_spawn_coordinate_capsule_campaign_receipt",
        lambda _path, **_kwargs: {"kind": "synthetic-receipt"},
    )

    def publish(value, output):
        output.write_text(json.dumps(value), encoding="utf-8")
        return output, campaign_run._sha256(output)

    monkeypatch.setattr(
        campaign_run,
        "publish_spawn_coordinate_capsule_campaign_receipt",
        publish,
    )

    code, result = campaign_run.run(args)

    assert code == 0
    assert result["valid_campaign"] is True
    assert observed == expected_tokens


@pytest.mark.parametrize(
    ("allow_dirty_plan", "dirty_consent_id", "map_value", "message"),
    [
        (True, "abc", None, "single dirty consent ID"),
        (True, None, None, "requires --dirty-consent-map"),
        (False, None, {}, "requires --allow-dirty-plan"),
        (
            True,
            None,
            {
                "schema_version": 1,
                "kind": "observatory_spawn_coordinate_capsule_dirty_consent_map",
                "conditions": {"pair001/control": "1" * 16},
            },
            "exactly the nine campaign conditions",
        ),
    ],
)
def test_campaign_run_rejects_unsafe_dirty_consent_shapes_before_any_condition(
    tmp_path,
    monkeypatch,
    allow_dirty_plan,
    dirty_consent_id,
    map_value,
    message,
):
    args = _args(tmp_path, monkeypatch)
    args.allow_dirty_plan = allow_dirty_plan
    args.dirty_consent_id = dirty_consent_id
    if map_value is not None:
        args.dirty_consent_map = tmp_path / "dirty-consent-map.json"
        args.dirty_consent_map.write_text(json.dumps(map_value), encoding="utf-8")

    with pytest.raises(campaign_run.CapsuleCampaignRunError, match=message):
        campaign_run.run(args)
