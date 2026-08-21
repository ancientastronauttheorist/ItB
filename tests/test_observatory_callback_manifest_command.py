"""CLI command behavior for validated inert callback manifests."""

from __future__ import annotations

import hashlib
import json

from src.loop import commands
from src.observatory.runtime_callback_manifest import METHOD_ORDER, STATUSES


def _manifest(*, capped: bool = False) -> dict:
    status = "function_cap" if capped else "resolved"
    functions = [] if capped else [
        {
            "function_id": "fn-0001",
            "debug_status": "available",
            "source": "@scripts/global.lua",
            "source_truncated": False,
            "short_src": "scripts/global.lua",
            "short_src_truncated": False,
            "linedefined": 446,
            "lastlinedefined": 465,
            "what": "Lua",
            "what_truncated": False,
            "name": "ScorePositioning",
            "name_truncated": False,
            "namewhat": "global",
            "namewhat_truncated": False,
        }
    ]
    methods = []
    for method in METHOD_ORDER:
        is_positioning = method == "ScorePositioning"
        methods.append(
            {
                "method": method,
                "status": status if is_positioning else "missing",
                "replaced": False,
                "resolution_depth": 0,
                "function_id": (
                    "fn-0001" if is_positioning and not capped else ""
                ),
                "expected_function_id": "",
                "expected_truncated": False,
            }
        )
    counts = {item: 0 for item in sorted(STATUSES)}
    for method in methods:
        counts[method["status"]] += 1
    return {
        "schema_version": 1,
        "runtime_version": "observatory-callback-manifest/1",
        "method_order": list(METHOD_ORDER),
        "limits": {
            "max_roots": 256,
            "max_depth": 16,
            "max_functions": 1024,
            "max_text_bytes": 512,
        },
        "roots": [
            {
                "root_id": "global.ScorePositioning",
                "methods": methods,
            }
        ],
        "functions": functions,
        "summary": {
            "root_count": 1,
            "method_count": 4,
            "function_count": len(functions),
            "replaced_count": 0,
            "status_counts": counts,
        },
    }


def test_command_validates_and_summarizes_fresh_manifest(
    tmp_path, monkeypatch
):
    manifest = _manifest()
    result_file = tmp_path / "callback.json"
    result_file.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(commands, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda **kwargs: True)
    monkeypatch.setattr(
        commands,
        "bridge_observatory_callback_manifest",
        lambda **kwargs: (
            "OK OBS_CALLBACK_MANIFEST roots=1 functions=1",
            manifest,
        ),
    )

    result = commands.cmd_observatory_callback_manifest()

    assert result["status"] == "OK"
    assert result["summary"]["root_count"] == 1
    assert result["root_ids"] == ["global.ScorePositioning"]
    assert len(result["manifest_sha256"]) == 64


def test_command_marks_function_cap_as_incomplete(tmp_path, monkeypatch):
    manifest = _manifest(capped=True)
    result_file = tmp_path / "callback.json"
    result_file.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(commands, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(commands, "is_bridge_alive", lambda **kwargs: True)
    monkeypatch.setattr(
        commands,
        "bridge_observatory_callback_manifest",
        lambda **kwargs: (
            "OK OBS_CALLBACK_MANIFEST roots=1 functions=0",
            manifest,
        ),
    )

    result = commands.cmd_observatory_callback_manifest()

    assert result["status"] == "INCOMPLETE"
    assert result["reason"] == "runtime function catalog reached its hard cap"


def test_command_refuses_stale_bridge(monkeypatch):
    monkeypatch.setattr(commands, "is_bridge_alive", lambda **kwargs: False)
    result = commands.cmd_observatory_callback_manifest()
    assert result["status"] == "NO_BRIDGE"
    assert "accepted, inventoried Observatory capture track" in result["next_step"]
    assert "arm the fixed startup request" in result["next_step"]
    assert "unpaused deployment or active mission" in result["next_step"]


def test_arm_startup_command_reports_exact_request_identity(tmp_path, monkeypatch):
    request_file = tmp_path / "itb_observatory_callback_manifest.request"

    def arm():
        request_file.write_bytes(commands.CALLBACK_MANIFEST_REQUEST_BYTES)
        return request_file

    monkeypatch.setattr(
        commands, "arm_observatory_callback_manifest_startup", arm
    )
    result = commands.cmd_observatory_callback_manifest_arm_startup()

    assert result["status"] == "ARMED"
    assert result["request_file"] == str(request_file)
    assert result["request_sha256"] == hashlib.sha256(
        commands.CALLBACK_MANIFEST_REQUEST_BYTES
    ).hexdigest()


def test_arm_startup_command_reports_create_only_collision(monkeypatch):
    def collide():
        raise commands.BridgeError("request already exists")

    monkeypatch.setattr(
        commands, "arm_observatory_callback_manifest_startup", collide
    )
    result = commands.cmd_observatory_callback_manifest_arm_startup()
    assert result == {"status": "ERROR", "error": "request already exists"}
