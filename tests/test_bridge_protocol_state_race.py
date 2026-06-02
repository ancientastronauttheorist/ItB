import json

from src.bridge import protocol


def test_read_state_ignores_disappearing_tmp_candidate(tmp_path, monkeypatch):
    state_file = tmp_path / "itb_state.json"
    tmp_file = tmp_path / "itb_state.json.tmp"
    state_file.write_text(json.dumps({"phase": "combat_player"}), encoding="utf-8")

    monkeypatch.setattr(protocol, "_state_candidates", lambda: [tmp_file, state_file])

    assert protocol.read_state() == {"phase": "combat_player"}
