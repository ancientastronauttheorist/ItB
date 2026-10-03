"""Fresh-generation budgets include the real refresh/ACK call chain."""
import json

from src.bridge import protocol


def _setup(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text('{"generation":0}', encoding="utf-8")
    clock = [0.0]
    monkeypatch.setattr(protocol, "STATE_FILE", state)
    monkeypatch.setattr(protocol, "STATE_TMP", tmp_path / "missing.json")
    monkeypatch.setattr(protocol, "write_command", lambda _command: None)
    monkeypatch.setattr(protocol.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(protocol.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay))
    return state, clock


def test_ack_receives_remaining_total_budget(tmp_path, monkeypatch):
    state, clock = _setup(tmp_path, monkeypatch)
    budgets = []
    def ack(*, timeout):
        budgets.append(timeout)
        clock[0] += 0.3
        state.write_text(json.dumps({"generation": 1, "new": True}), encoding="utf-8")
        return "OK"
    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    assert protocol.refresh_bridge_state_fresh(timeout=0.5, total_budget=True)
    assert budgets == [0.5]


def test_expired_ack_does_not_admit_fresh_generation(tmp_path, monkeypatch):
    state, clock = _setup(tmp_path, monkeypatch)
    def ack(*, timeout):
        assert timeout == 0.02
        clock[0] += 0.03
        state.write_text('{"generation":1,"new":true}', encoding="utf-8")
        return "OK"
    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    assert not protocol.refresh_bridge_state_fresh(timeout=0.02, total_budget=True)


def test_command_publication_latency_is_subtracted_from_ack(tmp_path, monkeypatch):
    state, clock = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(protocol, "write_command", lambda _command: clock.__setitem__(0, clock[0] + 0.05))
    def ack(*, timeout):
        assert timeout == 0.45
        state.write_text('{"generation":1,"new":true}', encoding="utf-8")
        return "OK"
    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    assert protocol.refresh_bridge_state_fresh(timeout=0.5, total_budget=True)


def test_command_publication_can_exhaust_budget_before_ack(tmp_path, monkeypatch):
    _state, clock = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(protocol, "write_command", lambda _command: clock.__setitem__(0, clock[0] + 0.05))
    def unexpected_ack(**_kwargs):
        raise AssertionError("ACK wait must not restart an exhausted budget")
    monkeypatch.setattr(protocol, "wait_for_ack", unexpected_ack)
    assert not protocol.refresh_bridge_state_fresh(timeout=0.02, total_budget=True)


def test_generation_wait_uses_only_budget_left_after_ack(tmp_path, monkeypatch):
    _state, clock = _setup(tmp_path, monkeypatch)
    def ack(*, timeout):
        clock[0] += 0.4
        return "OK"
    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    assert not protocol.refresh_bridge_state_fresh(timeout=0.5, total_budget=True)
    assert clock[0] == 0.5


def test_legacy_refresh_budget_retains_five_second_ack(tmp_path, monkeypatch):
    state, _clock = _setup(tmp_path, monkeypatch)
    def ack(*, timeout):
        assert timeout == 5.0
        state.write_text('{"generation":1,"new":true}', encoding="utf-8")
        return "OK"
    monkeypatch.setattr(protocol, "wait_for_ack", ack)
    assert protocol.refresh_bridge_state_fresh(timeout=0.2)
