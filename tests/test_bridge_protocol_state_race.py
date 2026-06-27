import json
import time
from pathlib import Path

from src.bridge import protocol


def test_read_state_ignores_disappearing_tmp_candidate(tmp_path, monkeypatch):
    state_file = tmp_path / "itb_state.json"
    tmp_file = tmp_path / "itb_state.json.tmp"
    state_file.write_text(json.dumps({"phase": "combat_player"}), encoding="utf-8")

    monkeypatch.setattr(protocol, "_state_candidates", lambda: [tmp_file, state_file])

    assert protocol.read_state() == {"phase": "combat_player"}


def test_is_bridge_active_ignores_candidate_disappearing_after_sort(monkeypatch):
    class ExistingLog:
        def exists(self):
            return True

    class DisappearingPath:
        def __init__(self):
            self.calls = 0

        def stat(self):
            self.calls += 1
            if self.calls == 1:
                return type("Stat", (), {"st_mtime": time.time()})()
            raise FileNotFoundError("tmp disappeared")

    disappearing = DisappearingPath()
    stable = Path(__file__)

    monkeypatch.setattr(protocol, "LOG_FILE", ExistingLog())
    monkeypatch.setattr(protocol, "_state_candidates", lambda: [disappearing, stable])

    assert protocol.is_bridge_active()
