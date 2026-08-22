from __future__ import annotations

import json

import pytest

from src.bridge import protocol


@pytest.fixture(autouse=True)
def _fresh_heartbeat(monkeypatch):
    monkeypatch.setattr(protocol, "is_bridge_alive", lambda max_stale_sec=0: True)


def _payload() -> dict:
    return {
        "schema_version": 1,
        "summary": {"root_count": 2, "function_count": 3, "slot_count": 4},
    }


def test_request_callback_bindings_requires_fresh_matching_sideband(
    tmp_path, monkeypatch
):
    result_file = tmp_path / "bindings.json"
    commands: list[str] = []

    def write(command: str) -> None:
        commands.append(command)
        result_file.write_text(json.dumps(_payload()), encoding="utf-8")

    monkeypatch.setattr(protocol, "CALLBACK_BINDINGS_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_BINDINGS roots=2 functions=3 slots=4",
    )
    ack, payload = protocol.request_observatory_callback_bindings(timeout=0.2)
    assert commands == ["OBS_CALLBACK_BINDINGS"]
    assert ack.endswith("roots=2 functions=3 slots=4")
    assert payload == _payload()


def test_request_callback_bindings_rejects_ack_payload_drift(tmp_path, monkeypatch):
    result_file = tmp_path / "bindings.json"

    def write(command: str) -> None:
        result_file.write_text(json.dumps(_payload()), encoding="utf-8")

    monkeypatch.setattr(protocol, "CALLBACK_BINDINGS_FILE", result_file)
    monkeypatch.setattr(protocol, "write_command", write)
    monkeypatch.setattr(
        protocol,
        "wait_for_ack",
        lambda timeout: "OK OBS_CALLBACK_BINDINGS roots=2 functions=3 slots=5",
    )
    with pytest.raises(protocol.BridgeError, match="does not match"):
        protocol.request_observatory_callback_bindings(timeout=0.2)


def test_binding_startup_request_is_exact_fsynced_create_only(tmp_path, monkeypatch):
    request = tmp_path / "itb_observatory_callback_bindings.request"
    monkeypatch.setattr(protocol, "BRIDGE_DIR", tmp_path)
    monkeypatch.setattr(protocol, "CALLBACK_BINDINGS_REQUEST_FILE", request)
    assert protocol.arm_observatory_callback_bindings_startup() == request
    assert request.read_bytes() == b"observatory-callback-bindings-request/1\n"
    with pytest.raises(protocol.BridgeError, match="already exists"):
        protocol.arm_observatory_callback_bindings_startup()
