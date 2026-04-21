"""Community-notes fetcher tests — Missing wire #4.

Covers the three pieces that close this wire:

1. ``community_fetch.build_queries`` — returns WebFetch-ready search
   URLs for Steam forum + Reddit on a named target.
2. ``community_fetch.normalize_notes`` — flattens harness-supplied
   WebFetch results into typed note records.
3. ``community_fetch.classify_confidence`` — picks a confidence band
   from the three sources (tooltip / wiki / community).

The ``cmd_research_attach_community`` glue is smoke-tested too,
asserting the wiki_raw record round-trips with a ``community_notes``
field populated.

See ``docs/self_healing_loop_design.md`` §External research and
CLAUDE.md rule 20.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.research import community_fetch


# ── build_queries ────────────────────────────────────────────────────────────


def test_build_queries_empty_name_returns_empty():
    assert community_fetch.build_queries("") == {}
    assert community_fetch.build_queries("   ") == {}


def test_build_queries_returns_steam_and_reddit_urls():
    q = community_fetch.build_queries("Firefly Leader")
    assert "steam_forum" in q
    assert "reddit" in q
    assert "590380" in q["steam_forum"]  # ITB Steam app id
    assert "IntoTheBreach" in q["reddit"]


def test_build_queries_url_encodes_spaces_and_specials():
    q = community_fetch.build_queries("Alpha Beetle / Leader")
    # Plus sign or percent-encoded space — either is fine; what matters is
    # that the raw space doesn't break the URL.
    assert " " not in q["steam_forum"]
    assert " " not in q["reddit"]


# ── normalize_notes ──────────────────────────────────────────────────────────


def test_normalize_notes_empty_input():
    assert community_fetch.normalize_notes({}) == []
    assert community_fetch.normalize_notes(None) == []
    assert community_fetch.normalize_notes([]) == []  # not a dict — rejected


def test_normalize_notes_basic_shape():
    raw = {
        "steam_forum": {
            "url": "https://steam/thread/1",
            "excerpt": "Alpha Beetle damages mountains",
            "confidence": 0.8,
        },
        "reddit": {
            "url": "https://reddit.com/r/IntoTheBreach/x",
            "excerpt": "confirmed mountain damage",
            "confidence": 0.65,
        },
    }
    notes = community_fetch.normalize_notes(raw)
    assert len(notes) == 2
    # Sorted by source for deterministic ordering.
    assert notes[0]["source"] == "reddit"
    assert notes[1]["source"] == "steam_forum"
    assert notes[1]["excerpt"] == "Alpha Beetle damages mountains"
    assert notes[1]["confidence"] == 0.8


def test_normalize_notes_drops_empty_excerpts():
    raw = {
        "steam_forum": {"url": "x", "excerpt": "", "confidence": 0.9},
        "reddit": {"url": "y", "excerpt": "real content", "confidence": 0.5},
    }
    notes = community_fetch.normalize_notes(raw)
    assert [n["source"] for n in notes] == ["reddit"]


def test_normalize_notes_clamps_confidence():
    raw = {
        "steam_forum": {"url": "x", "excerpt": "a", "confidence": 1.5},  # over
        "reddit": {"url": "y", "excerpt": "b", "confidence": -0.2},  # under
    }
    notes = community_fetch.normalize_notes(raw)
    by_source = {n["source"]: n for n in notes}
    assert by_source["steam_forum"]["confidence"] == 1.0
    assert by_source["reddit"]["confidence"] == 0.0


def test_normalize_notes_handles_missing_confidence():
    raw = {"steam_forum": {"url": "x", "excerpt": "ok"}}
    notes = community_fetch.normalize_notes(raw)
    assert notes[0]["confidence"] == 0.5  # default


def test_drop_low_confidence():
    notes = [
        {"source": "a", "url": "", "excerpt": "x", "confidence": 0.1},
        {"source": "b", "url": "", "excerpt": "y", "confidence": 0.5},
        {"source": "c", "url": "", "excerpt": "z", "confidence": 0.8},
    ]
    kept = community_fetch.drop_low_confidence(notes)
    assert [n["source"] for n in kept] == ["b", "c"]


# ── classify_confidence ──────────────────────────────────────────────────────


def test_classify_confirmed_when_all_three_sources():
    assert community_fetch.classify_confidence(
        tooltip_ok=True, wiki_ok=True, community_count=2,
    ) == "confirmed"


def test_classify_likely_when_tooltip_plus_wiki():
    assert community_fetch.classify_confidence(
        tooltip_ok=True, wiki_ok=True, community_count=0,
    ) == "likely"


def test_classify_speculative_when_community_only():
    assert community_fetch.classify_confidence(
        tooltip_ok=False, wiki_ok=False, community_count=3,
    ) == "speculative"


def test_classify_none_when_nothing():
    assert community_fetch.classify_confidence(
        tooltip_ok=False, wiki_ok=False, community_count=0,
    ) == "none"


def test_classify_likely_on_partial_agreement():
    # Tooltip-only or wiki-only without community notes still earns
    # "likely" — we have at least one authoritative source. Better than
    # none; not confirmed until the community agrees.
    assert community_fetch.classify_confidence(
        tooltip_ok=True, wiki_ok=False, community_count=0,
    ) == "likely"


# ── cmd_research_attach_community smoke test ────────────────────────────────


def test_attach_community_writes_notes_to_wiki_raw(monkeypatch, tmp_path):
    from src.loop import commands as loop_commands
    from src.loop.session import RunSession
    from src.research import wiki_client

    # Redirect wiki_raw cache to tmp_path so we don't touch real data.
    monkeypatch.setattr(wiki_client, "WIKI_CACHE_DIR", tmp_path)

    s = RunSession()
    s.enqueue_research("Firefly Leader", None, current_turn=1)
    entry = s.research_queue[0]
    entry["research_id"] = "abc123"
    entry["status"] = "in_progress"
    entry["result"] = {
        "community_queries": {
            "target_name": "Firefly Leader",
            "queries": {"steam_forum": "x", "reddit": "y"},
        },
        "parsed": {"name_tag": {"confidence": 0.8}},
        "wiki_fallback": {"title": "Firefly Leader"},
    }

    # Monkeypatch session loader so cmd sees our session.
    monkeypatch.setattr(loop_commands, "_load_session", lambda: s)

    notes = {
        "steam_forum": {
            "url": "https://steamcommunity.com/x",
            "excerpt": "Leader spawns on mission 3",
            "confidence": 0.9,
        },
        "reddit": {
            "url": "https://reddit.com/y",
            "excerpt": "irrelevant joke thread",
            "confidence": 0.1,  # dropped
        },
    }
    out = loop_commands.cmd_research_attach_community("abc123", notes)

    assert out["research_id"] == "abc123"
    assert out["target_name"] == "Firefly Leader"
    assert out["attached_count"] == 1  # only steam_forum cleared threshold
    assert out["dropped_count"] == 1
    assert out["confidence_band"] == "confirmed"  # tooltip + wiki + community

    # File landed in the redirected cache dir with community_notes merged.
    cache = wiki_client._cache_path("Firefly Leader", cache_dir=tmp_path)
    assert cache.exists()
    written = json.loads(cache.read_text())
    assert "community_notes" in written
    assert len(written["community_notes"]) == 1
    assert written["community_notes"][0]["source"] == "steam_forum"


def test_attach_community_rejects_unknown_research_id(monkeypatch):
    from src.loop import commands as loop_commands
    from src.loop.session import RunSession

    s = RunSession()
    monkeypatch.setattr(loop_commands, "_load_session", lambda: s)

    out = loop_commands.cmd_research_attach_community("nope", {})
    assert "error" in out
    assert "nope" in out["error"]
