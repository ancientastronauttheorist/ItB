"""Freshness and ACK checks for the callback-manifest side-band file."""

from __future__ import annotations

import json

import pytest

from src.bridge import protocol


@pytest.fixture(autouse=True)
def _fresh_mission_heartbeat(monkeypatch):
    monkeypatch.setattr(
        protocol, "is_bridge_alive", lambda max_stale_sec=0: True
    )


def _payload(*, roots: int = 2, functions: int = 3) -> dict:
    return {
        "schema_version": 1,
        "summary": {
            "root_count": roots,
            "function_count": functions,
        },
    }


def test_request_callback_manifest_requires_new_file_and_matching_ack(
    tmp_path, monkeypatch
):
    result_file = tmp_path / "callback.json"
    commands: list[str] = []

    def write(command: str) -> None:
        commands.append(command)
        result_file.write_text(json.dumps(_payload()), encoding="utf-8")

    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_MANIFEST roots=2 functions=3",
    )

    ack, payload = protocol.request_observatory_callback_manifest(timeout=0.2)

    assert commands == ["OBS_CALLBACK_MANIFEST"]
    assert ack == "OK OBS_CALLBACK_MANIFEST roots=2 functions=3"
    assert payload == _payload()


def test_request_callback_manifest_rejects_stale_result(tmp_path, monkeypatch):
    result_file = tmp_path / "callback.json"
    result_file.write_text(json.dumps(_payload()), encoding="utf-8")
    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", lambda command: None)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_MANIFEST roots=2 functions=3",
    )

    with pytest.raises(TimeoutError, match="Fresh callback manifest"):
        protocol.request_observatory_callback_manifest(timeout=0.1)


def test_request_callback_manifest_rejects_invalid_json(tmp_path, monkeypatch):
    result_file = tmp_path / "callback.json"

    def write(command: str) -> None:
        result_file.write_text("{invalid", encoding="utf-8")

    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_MANIFEST roots=2 functions=3",
    )

    with pytest.raises(protocol.BridgeError, match="not valid JSON"):
        protocol.request_observatory_callback_manifest(timeout=0.2)


def test_request_callback_manifest_rejects_ack_payload_drift(
    tmp_path, monkeypatch
):
    result_file = tmp_path / "callback.json"

    def write(command: str) -> None:
        result_file.write_text(json.dumps(_payload()), encoding="utf-8")

    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_MANIFEST roots=2 functions=4",
    )

    with pytest.raises(protocol.BridgeError, match="does not match"):
        protocol.request_observatory_callback_manifest(timeout=0.2)


def test_request_callback_manifest_rejects_unexpected_ack(tmp_path, monkeypatch):
    result_file = tmp_path / "callback.json"
    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", lambda command: None)
    monkeypatch.setattr(protocol, "wait_for_ack", lambda timeout: "OK")

    with pytest.raises(protocol.BridgeError, match="unexpected"):
        protocol.request_observatory_callback_manifest(timeout=0.2)


def test_request_callback_manifest_refuses_missing_mission_heartbeat(
    monkeypatch,
):
    writes: list[str] = []
    monkeypatch.setattr(
        protocol, "is_bridge_alive", lambda max_stale_sec=0: False
    )
    monkeypatch.setattr(protocol, "write_command", writes.append)
    with pytest.raises(protocol.BridgeError, match="active mission heartbeat"):
        protocol.request_observatory_callback_manifest(timeout=0.2)
    assert writes == []


def test_request_callback_manifest_cancels_its_pending_command_on_ack_timeout(
    tmp_path, monkeypatch
):
    result_file = tmp_path / "callback.json"
    command_file = tmp_path / "itb_cmd.txt"

    def write(command: str) -> None:
        protocol._seq_counter = 41
        command_file.write_text(
            "#41 OBS_CALLBACK_MANIFEST", encoding="utf-8"
        )

    def timeout_without_poller(timeout: float) -> str:
        raise TimeoutError("no poller")

    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "CMD_FILE", command_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(protocol, "wait_for_ack", timeout_without_poller)

    with pytest.raises(TimeoutError, match="no poller"):
        protocol.request_observatory_callback_manifest(timeout=0.2)
    assert not command_file.exists()


def test_timeout_cleanup_preserves_a_different_pending_command(
    tmp_path, monkeypatch
):
    result_file = tmp_path / "callback.json"
    command_file = tmp_path / "itb_cmd.txt"

    def write(command: str) -> None:
        protocol._seq_counter = 42
        command_file.write_text(
            "#42 OBS_CALLBACK_MANIFEST", encoding="utf-8"
        )

    def timeout_after_replacement(timeout: float) -> str:
        command_file.write_text("#43 LUA return 'other'", encoding="utf-8")
        raise TimeoutError("replaced")

    monkeypatch.setattr(protocol, "CALLBACK_MANIFEST_FILE", result_file)
    monkeypatch.setattr(protocol, "CMD_FILE", command_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(protocol, "wait_for_ack", timeout_after_replacement)

    with pytest.raises(TimeoutError, match="replaced"):
        protocol.request_observatory_callback_manifest(timeout=0.2)
    assert command_file.read_text(encoding="utf-8") == "#43 LUA return 'other'"


def test_startup_request_is_exact_fsynced_create_only(tmp_path, monkeypatch):
    request_file = tmp_path / "itb_observatory_callback_manifest.request"
    monkeypatch.setattr(protocol, "BRIDGE_DIR", tmp_path)
    monkeypatch.setattr(
        protocol, "CALLBACK_MANIFEST_REQUEST_FILE", request_file
    )

    result = protocol.arm_observatory_callback_manifest_startup()

    assert result == request_file
    assert request_file.read_bytes() == (
        b"observatory-callback-manifest-request/1\n"
    )
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.arm_observatory_callback_manifest_startup()
    assert request_file.read_bytes() == protocol.CALLBACK_MANIFEST_REQUEST_BYTES
