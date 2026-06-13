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
