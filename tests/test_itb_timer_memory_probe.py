from __future__ import annotations

import argparse

from scripts import itb_timer_memory_probe as probe


def test_extract_context_timers_reads_pause_menu_playtime_words():
    timers = probe._extract_context_timers("Timeline Playtime\n0h 0m 38s\n")

    assert timers == [
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 0m 38s",
            "seconds": 38.0,
            "game_timer": "0:00:38",
            "text_offset": 18,
        }
    ]


class FakeReader:
    def __init__(self, memory: dict[int, bytes]):
        self.memory = memory

    def read(self, address: int, size: int) -> bytes | None:
        data = self.memory.get(address)
        return data[:size] if data is not None else None

    def regions(self, *, max_region_size: int):
        for address, data in self.memory.items():
            if len(data) <= max_region_size:
                yield address, len(data), 0


class SequencedReader:
    def __init__(self, sequence: list[bytes]):
        self.sequence = sequence
        self.index = 0

    def read(self, address: int, size: int) -> bytes | None:
        if not self.sequence:
            return None
        data = self.sequence[min(self.index, len(self.sequence) - 1)]
        self.index += 1
        return data[:size]


def test_read_timeline_playtime_address_reads_calibrated_string():
    result = probe.read_timeline_playtime_address(
        FakeReader({0x138A5900: b"0h 1m 04s\x00"}),
        0x138A5900,
    )

    assert result["status"] == "OK"
    assert result["address"] == "0x00000000138a5900"
    assert result["raw"] == "0h 1m 04s"
    assert result["seconds"] == 64.0
    assert result["game_timer"] == "0:01:04"


def test_read_address_parser_accepts_hex_address():
    args = probe.build_parser().parse_args(["read-address", "0x138a5900"])

    assert args.command == "read-address"
    assert args.address == 0x138A5900


def test_scan_context_timers_reports_byte_address_with_multibyte_prefix():
    prefix = b"\xc3\xa9Timeline Playtime\n"
    data = prefix + b"0h 1m 04s\x00"

    hits = probe.scan_context_timers(
        FakeReader({0x1000: data}),
        max_region_size=1024,
        max_hits=10,
    )

    timeline_hits = [
        hit for hit in hits
        if hit["source"] == "visible_timeline_playtime_string"
    ]
    assert timeline_hits
    assert timeline_hits[0]["address"] == f"0x{0x1000 + len(prefix):016x}"


def test_select_visible_timer_context_prefers_timeline_playtime_words():
    context = [
        {
            "source": "GameData.current.time",
            "raw": 15465366.0,
            "seconds": 15465.366,
            "game_timer": "4:17:45",
        },
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 0m 38s",
            "seconds": 38.0,
            "game_timer": "0:00:38",
        },
    ]

    selected = probe.select_visible_timer_context(context)

    assert selected is not None
    assert selected["seconds"] == 38.0
    assert selected["sources"] == {"visible_timeline_playtime_string": 1}


def test_select_visible_timer_context_filters_placeholders_and_over_limit_values():
    context = [
        {
            "source": "visible_timeline_playtime_string",
            "raw": "55h 55m 55s",
            "seconds": 201355.0,
            "game_timer": "55:55:55",
        },
        {
            "source": "visible_timer_string",
            "raw": "16:16:16",
            "seconds": 58576.0,
            "game_timer": "16:16:16",
        },
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 0m 44s",
            "seconds": 44.0,
            "game_timer": "0:00:44",
        },
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 0m 44s",
            "seconds": 44.0,
            "game_timer": "0:00:44",
        },
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 2m 20s",
            "seconds": 140.0,
            "game_timer": "0:02:20",
        },
    ]

    selected = probe.select_visible_timer_context(context)

    assert selected is not None
    assert selected["seconds"] == 44.0
    assert selected["raw_values"] == {"0h 0m 44s": 2}


def test_select_visible_timer_context_prefers_timeline_playtime_over_generic_strings():
    context = [
        *[
            {
                "source": "visible_timer_string",
                "raw": "0:00:07",
                "seconds": 7.0,
                "game_timer": "0:00:07",
            }
            for _ in range(18)
        ],
        *[
            {
                "source": "visible_timeline_playtime_string",
                "raw": "0h 0m 44s",
                "seconds": 44.0,
                "game_timer": "0:00:44",
            }
            for _ in range(7)
        ],
    ]

    selected = probe.select_visible_timer_context(context)

    assert selected is not None
    assert selected["seconds"] == 44.0
    assert selected["sources"] == {"visible_timeline_playtime_string": 7}


def test_resolve_expected_seconds_prefers_timeline_playtime_over_generic_strings():
    context = [
        *[
            {
                "source": "visible_timer_string",
                "raw": "0:00:07",
                "seconds": 7.0,
                "game_timer": "0:00:07",
            }
            for _ in range(18)
        ],
        {
            "source": "visible_timeline_playtime_string",
            "raw": "0h 1m 04s",
            "seconds": 64.0,
            "game_timer": "0:01:04",
        },
    ]
    args = argparse.Namespace(
        expected_seconds=None,
        expected_timer=None,
        expected_selection="mode",
        max_visible_timer_seconds=probe.DEFAULT_MAX_VISIBLE_TIMER_SECONDS,
    )

    seconds, selection = probe.resolve_expected_seconds(args, context)

    assert seconds == 64.0
    assert selection["sources"] == {"visible_timeline_playtime_string": 1}


def test_select_visible_timer_context_returns_none_without_visible_candidates():
    selected = probe.select_visible_timer_context(
        [
            {
                "source": "GameData.current.time",
                "raw": 15465366.0,
                "seconds": 15465.366,
                "game_timer": "4:17:45",
            }
        ]
    )

    assert selected is None


def test_decode_numeric_timer_normalizes_integer_milliseconds():
    kind = probe.NUMERIC_TIMER_KIND_BY_NAME["u32_milliseconds"]
    data = (44_250).to_bytes(4, "little")

    raw, seconds = probe._decode_numeric_timer(data, 0, kind)

    assert raw == 44_250
    assert seconds == 44.25


def test_scan_numeric_timer_candidates_reads_multiple_representations():
    data = bytearray(64)
    data[0:4] = probe.struct.pack("<f", 44.0)
    data[8:16] = probe.struct.pack("<d", 44.0)
    data[16:20] = (44_000).to_bytes(4, "little")

    result = probe.scan_numeric_timer_candidates(
        FakeReader({0x2000: bytes(data)}),
        expected_seconds=44.0,
        seconds_window=0.5,
        max_timer_seconds=1800.0,
        max_region_size=1024,
        max_candidates_per_kind=10,
        kinds=(
            probe.NUMERIC_TIMER_KIND_BY_NAME["f32_seconds"],
            probe.NUMERIC_TIMER_KIND_BY_NAME["f64_seconds"],
            probe.NUMERIC_TIMER_KIND_BY_NAME["u32_milliseconds"],
        ),
        include_readonly=True,
    )

    kinds = {candidate["kind"] for candidate in result["candidates"]}
    assert {"f32_seconds", "f64_seconds", "u32_milliseconds"} <= kinds
    assert result["candidate_count_by_kind"]["u32_milliseconds"] >= 1


def test_score_numeric_tracks_rejects_moving_wrong_start_value():
    candidate = {
        "address": "0x0000000000002000",
        "kind": "f32_seconds",
        "distance_seconds": 17.0,
    }
    tracks = [
        {
            "candidate": candidate,
            "first_seconds": 27.0,
            "last_seconds": 32.0,
            "delta_seconds": 5.0,
            "elapsed_seconds": 5.0,
            "live_delta_error_seconds": 0.0,
            "monotonic": True,
            "moving_like_timer": True,
            "seconds": [27.0, 28.0, 29.0, 30.0, 31.0, 32.0],
        }
    ]
    current = {
        probe._numeric_candidate_key(candidate): {
            "read_ok": True,
            "seconds": 32.0,
        }
    }

    result = probe._score_numeric_tracks(
        tracks=tracks,
        start_truth_seconds=44.0,
        final_truth_seconds=49.0,
        current_values=current,
        stable_values=current,
        max_results=10,
    )

    assert result[0]["status"] == "moving_wrong_start_value"
    assert result[0]["start_error_seconds"] == 17.0


def test_score_numeric_tracks_accepts_cycle_candidate():
    candidate = {
        "address": "0x0000000000002000",
        "kind": "f64_seconds",
        "distance_seconds": 0.1,
    }
    tracks = [
        {
            "candidate": candidate,
            "first_seconds": 44.1,
            "last_seconds": 49.05,
            "delta_seconds": 4.95,
            "elapsed_seconds": 5.0,
            "live_delta_error_seconds": 0.05,
            "monotonic": True,
            "moving_like_timer": True,
            "seconds": [44.1, 45.0, 46.0, 47.0, 48.0, 49.05],
        }
    ]
    current = {
        probe._numeric_candidate_key(candidate): {
            "read_ok": True,
            "seconds": 49.0,
        }
    }
    stable = {
        probe._numeric_candidate_key(candidate): {
            "read_ok": True,
            "seconds": 49.01,
        }
    }

    result = probe._score_numeric_tracks(
        tracks=tracks,
        start_truth_seconds=44.0,
        final_truth_seconds=49.0,
        current_values=current,
        stable_values=stable,
        max_results=10,
    )

    assert result[0]["status"] == "validated_cycle_candidate"


class ProofReader(FakeReader):
    def __init__(self, memory: dict[int, bytes]):
        super().__init__(memory)
        self._module = probe.ModuleInfo(
            base=0x400000,
            size=123456,
            path=r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe",
        )

    def module(self):
        return self._module

    def process_start_time_unix(self):
        return 1781469000.0


def test_session_clock_proof_round_trips_validated_candidate():
    candidate = {
        "address": "0x0000000000002000",
        "region_base": "0x0000000000001000",
        "offset": 0x1000,
        "kind": "f32_seconds",
        "distance_seconds": 0.1,
    }
    score_payload = {
        "source_scan": "scan.json",
        "source_track": "track.json",
        "results": [
            {
                "status": "validated_cycle_candidate",
                "candidate": candidate,
                "current_seconds": 49.0,
                "stable_seconds": 49.0,
                "paused_delta_seconds": 0.0,
            }
        ],
    }
    reader = ProofReader({0x2000: probe.struct.pack("<f", 49.0)})
    module = reader.module()

    proof = probe.build_session_clock_proof(
        score_payload=score_payload,
        source_score_path="score.json",
        pid=123,
        reader=reader,
        module=module,
    )
    validation = probe.validate_session_clock_proof_with_reader(
        proof,
        pid=123,
        reader=reader,
        module=module,
        expected_seconds=49.0,
    )

    assert proof["address"] == "0x0000000000002000"
    assert proof["kind"] == "f32_seconds"
    assert proof["process_identity"]["pid"] == 123
    assert validation["status"] == "OK"
    assert validation["game_timer"] == "0:00:49"


def test_session_clock_proof_rejects_process_identity_mismatch():
    candidate = {
        "address": "0x0000000000002000",
        "kind": "f32_seconds",
    }
    proof = {
        "process_identity": {
            "pid": 123,
            "process_start_unix": 1781469000.0,
            "module": {
                "path": r"B:\SteamLibrary\steamapps\common\Into the Breach\Breach.exe",
                "size": 123456,
            },
        },
        "candidate": candidate,
    }
    reader = ProofReader({0x2000: probe.struct.pack("<f", 49.0)})

    validation = probe.validate_session_clock_proof_with_reader(
        proof,
        pid=456,
        reader=reader,
        module=reader.module(),
    )

    assert validation["status"] == "INVALID"
    assert validation["reason"] == "pid_mismatch"


def test_bulk_numeric_tracks_prefers_moving_candidate_over_static_copy():
    static = {
        "address": "0x0000000000002000",
        "region_base": "0x0000000000002000",
        "offset": 0,
        "kind": "f32_seconds",
        "distance_seconds": 0.0,
    }
    moving = {
        "address": "0x0000000000002004",
        "region_base": "0x0000000000002000",
        "offset": 4,
        "kind": "f32_seconds",
        "distance_seconds": 0.0,
    }
    sequence = [
        probe.struct.pack("<ff", 44.0, 44.0 + idx * 0.05)
        for idx in range(12)
    ]

    result = probe._candidate_bulk_tracks(
        SequencedReader(sequence),
        [static, moving],
        samples=12,
        interval_seconds=0.05,
        max_span_bytes=64,
    )

    assert result["track_count"] == 2
    assert result["tracks"][0]["candidate"]["address"] == moving["address"]
    assert result["tracks"][0]["moving_like_timer"] is True
    static_track = next(
        track for track in result["tracks"]
        if track["candidate"]["address"] == static["address"]
    )
    assert static_track["moving_like_timer"] is False
    assert static_track["delta_seconds"] == 0.0


def test_numeric_parser_accepts_ground_truth_scan_command():
    args = probe.build_parser().parse_args(
        [
            "scan-numeric",
            "--ground-truth-address",
            "0x138a5900",
            "--kinds",
            "f64_seconds,u32_milliseconds",
        ]
    )

    assert args.command == "scan-numeric"
    assert args.ground_truth_address == 0x138A5900
    assert args.kinds == "f64_seconds,u32_milliseconds"


def test_numeric_parser_accepts_direct_track_address():
    args = probe.build_parser().parse_args(
        ["track-address", "0x122e5dbc", "f32_seconds"]
    )

    assert args.command == "track-address"
    assert args.address == 0x122E5DBC
    assert args.kind == "f32_seconds"


def test_numeric_parser_accepts_bulk_track_command():
    args = probe.build_parser().parse_args(
        [
            "track-numeric-bulk",
            "scan.json",
            "--candidate-limit",
            "50000",
            "--max-span-bytes",
            "1048576",
        ]
    )

    assert args.command == "track-numeric-bulk"
    assert args.candidates == "scan.json"
    assert args.candidate_limit == 50000
    assert args.max_span_bytes == 1048576


def test_numeric_parser_accepts_session_clock_proof_command():
    args = probe.build_parser().parse_args(
        [
            "session-clock-proof",
            "--score",
            "score.json",
            "--output",
            "proof.json",
        ]
    )

    assert args.command == "session-clock-proof"
    assert args.score == "score.json"
    assert args.output == "proof.json"


def test_macos_pid_finder_ignores_unrelated_breach_process(monkeypatch):
    class Result:
        stdout = (
            "21633 /System/Cryptexes/App/usr/libexec/PasswordBreachAgent\n"
            "57315 /Users/me/Library/Application Support/Steam/steamapps/common/"
            "Into the Breach/Into the Breach.app/Contents/MacOS/Into the Breach\n"
        )

    monkeypatch.setattr(probe.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert probe._find_breach_pid_macos() == 57315


def test_open_process_reader_uses_macos_reader(monkeypatch):
    opened = {}

    class FakeMacReader:
        def __init__(self, pid):
            opened["pid"] = pid

    monkeypatch.setattr(probe.os, "name", "posix")
    monkeypatch.setattr(probe.sys, "platform", "darwin")
    monkeypatch.setattr(probe, "MacProcessReader", FakeMacReader)

    reader = probe.open_process_reader(57315)

    assert isinstance(reader, FakeMacReader)
    assert opened["pid"] == 57315
