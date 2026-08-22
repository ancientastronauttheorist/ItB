from __future__ import annotations

import json
from pathlib import Path

from scripts.itb_observatory_callback_trial import main
from src.observatory.controller_bundle import build_controller_bundle


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "observatory" / "inventories" / (
    "windows_build_13725832_31fe35265598_local_modified.json"
)
BINDINGS = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260822T021034Z_callback_bindings.json"
)
JOIN = ROOT / "data" / "observatory" / "captures" / (
    "windows_build_13725832_owner_local_modified_"
    "20260821T201929Z_callback_join.json"
)


def test_prepare_pair_builds_a_complete_immutable_packet(tmp_path):
    controller = tmp_path / "controller.lua"
    controller.write_text(
        build_controller_bundle(
            runtime_path=ROOT / "src" / "bridge" / "observatory_trace.lua",
            controller_path=ROOT
            / "src"
            / "bridge"
            / "observatory_callback_controller.lua",
        ),
        encoding="utf-8",
    )
    output = tmp_path / "pair"
    code = main(
        [
            "prepare-pair",
            "--inventory",
            str(INVENTORY),
            "--controller-artifact",
            str(controller),
            "--installed-modloader",
            str(ROOT / "src" / "bridge" / "modloader.lua"),
            "--trial-host",
            str(ROOT / "src" / "bridge" / "observatory_callback_trial_host.lua"),
            "--bindings",
            str(BINDINGS),
            "--callback-join",
            str(JOIN),
            "--capture-track",
            "owner_local_modified",
            "--capture-id",
            "callback-cli-001",
            "--callback-family",
            "score_positioning",
            "--mission-id",
            "Mission_Test",
            "--mission-slot",
            "island0_mission1",
            "--turn",
            "2",
            "--master-seed",
            "-17",
            "--region-id",
            "Archive_A",
            "--ai-seed",
            "81",
            "--timeline-fingerprint",
            "a" * 64,
            "--output-root",
            str(output),
        ]
    )
    assert code == 0
    plan_path = output / "itb_observatory_callback_callback-cli-001_pair_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["callback_family"] == "score_positioning"
    assert plan["conditions"] == ["control", "exact_hook"]
    assert len(plan["artifacts"]["arm_packet"]["sha256"]) == 64
    assert len(plan["artifacts"]["capsule"]["sha256"]) == 64

    # Every durable file is create-only; rerunning cannot overwrite the plan.
    assert main(
        [
            "arm-request",
            "--bridge-root",
            str(output),
            "--condition",
            "control",
            "--activation-nonce",
            plan["activation_nonce"],
            "--capsule-sha256",
            plan["artifacts"]["capsule"]["sha256"],
        ]
    ) == 0
