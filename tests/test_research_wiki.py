"""Phase 2 #P2-6 Fandom wiki client tests.

All tests use a monkey-patched fetcher so nothing hits the live API.
The fetcher takes ``(title, timeout)`` and returns a dict matching
the MediaWiki formatversion=2 response shape.

Invariants:

1. ``fetch_raw`` caches the response to ``data/wiki_raw/<title>.json``
   and returns the cache on subsequent calls (no second network hit).
2. ``refresh=True`` bypasses the cache.
3. ``extract_wikitext`` handles missing pages, empty revisions, and
   both formatversion shapes.
4. ``pick_ae_section`` returns the AE-only text when the page has one,
   falls back to the full text otherwise, and stops at the next
   same-level heading.
5. ``parse_infobox`` splits on ``|`` while respecting nested templates
   and wiki links.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.research import wiki_client as wc


def _payload(title: str, wikitext: str) -> dict:
    """Build a MediaWiki formatversion=2 response."""
    return {
        "query": {
            "pages": [
                {
                    "pageid": 1,
                    "title": title,
                    "revisions": [{"content": wikitext}],
                }
            ]
        }
    }


def _missing_payload(title: str) -> dict:
    return {
        "query": {"pages": [{"title": title, "missing": True}]}
    }


# ── fetch + cache ────────────────────────────────────────────────────────────


def test_fetch_raw_writes_cache(tmp_path: Path):
    calls: list[str] = []

    def fake(title, _timeout):
        calls.append(title)
        return _payload(title, "hello")

    out = wc.fetch_raw("Vice Fist", cache_dir=tmp_path, fetcher=fake)
    assert out["query"]["pages"][0]["revisions"][0]["content"] == "hello"
    # Cache file written
    p = wc._cache_path("Vice Fist", cache_dir=tmp_path)
    assert p.exists()
    assert calls == ["Vice Fist"]


def test_fetch_raw_uses_cache_on_second_call(tmp_path: Path):
    calls: list[str] = []

    def fake(title, _timeout):
        calls.append(title)
        return _payload(title, "A")

    wc.fetch_raw("Firefly", cache_dir=tmp_path, fetcher=fake)
    wc.fetch_raw("Firefly", cache_dir=tmp_path, fetcher=fake)
    wc.fetch_raw("Firefly", cache_dir=tmp_path, fetcher=fake)
    # Network was only hit once.
    assert calls == ["Firefly"]


def test_fetch_raw_refresh_bypasses_cache(tmp_path: Path):
    calls: list[int] = []

    def fake(title, _timeout):
        calls.append(1)
        return _payload(title, f"revision {len(calls)}")

    wc.fetch_raw("X", cache_dir=tmp_path, fetcher=fake)
    wc.fetch_raw("X", cache_dir=tmp_path, fetcher=fake, refresh=True)
    assert len(calls) == 2


def test_cache_path_url_encodes_unsafe_title(tmp_path: Path):
    # Titles with slashes would otherwise escape the cache dir.
    p = wc._cache_path("Some/Title With Space", cache_dir=tmp_path)
    assert p.parent == tmp_path
    assert "/" not in p.name or p.name.count("/") == 0
    assert "%" in p.name  # URL-encoded


# ── wikitext extraction ────────────────────────────────────────────────────


def test_extract_wikitext_happy_path():
    assert wc.extract_wikitext(_payload("X", "body text")) == "body text"


def test_extract_wikitext_missing_page():
    assert wc.extract_wikitext(_missing_payload("X")) == ""


def test_extract_wikitext_empty_query():
    assert wc.extract_wikitext({"query": {"pages": []}}) == ""
    assert wc.extract_wikitext({}) == ""


def test_extract_wikitext_legacy_format_v1_fallback():
    # formatversion=1 used "*" key for the revision content.
    legacy = {
        "query": {"pages": [{"pageid": 1, "revisions": [{"*": "legacy body"}]}]}
    }
    assert wc.extract_wikitext(legacy) == "legacy body"


# ── AE section picker ─────────────────────────────────────────────────────


def test_pick_ae_section_no_ae_returns_full_text():
    wt = "== Description ==\nSome text.\n"
    section, used = wc.pick_ae_section(wt)
    assert used == "base"
    assert section == wt


def test_pick_ae_section_returns_ae_block_only():
    wt = (
        "== Description ==\n"
        "Base text.\n"
        "=== Advanced Edition ===\n"
        "AE text body.\n"
        "== Trivia ==\n"
        "Not AE-related.\n"
    )
    section, used = wc.pick_ae_section(wt)
    assert used == "ae"
    # AE section stops at the == Trivia == header (level 2, which is
    # higher than our === AE === level 3).
    assert "AE text body." in section
    assert "Not AE-related." not in section


def test_pick_ae_section_ae_at_end_of_page():
    wt = "== Description ==\nBase.\n=== Advanced Edition ===\nAE tail.\n"
    section, used = wc.pick_ae_section(wt)
    assert used == "ae"
    assert "AE tail" in section


def test_pick_ae_section_ae_is_case_insensitive():
    wt = "=== advanced EDITION ===\nAE body.\n"
    section, used = wc.pick_ae_section(wt)
    assert used == "ae"
    assert "AE body." in section


# ── infobox parsing ───────────────────────────────────────────────────────


def test_parse_infobox_simple_weapon():
    wt = (
        "{{Weapon Infobox\n"
        "| name = Vice Fist\n"
        "| damage = 1\n"
        "| push = Throw\n"
        "| class = Prime\n"
        "}}\n"
        "== Description ==\n"
        "Grabs and tosses.\n"
    )
    box = wc.parse_infobox(wt)
    assert box["name"] == "Vice Fist"
    assert box["damage"] == "1"
    assert box["push"] == "Throw"
    assert box["class"] == "Prime"


def test_parse_infobox_handles_nested_templates():
    # Nested {{icon|...}} inside a field value mustn't break on its |.
    wt = (
        "{{Weapon Infobox\n"
        "| name = X\n"
        "| damage = 2 {{icon|damage|red}}\n"
        "| push = none\n"
        "}}\n"
    )
    box = wc.parse_infobox(wt)
    assert box["name"] == "X"
    assert "icon" in box["damage"]
    assert box["push"] == "none"


def test_parse_infobox_handles_wiki_links_with_pipes():
    wt = (
        "{{Weapon Infobox\n"
        "| name = Y\n"
        "| description = See [[Grid|Power Grid]] for damage.\n"
        "}}\n"
    )
    box = wc.parse_infobox(wt)
    assert box["description"].startswith("See [[Grid|Power Grid]]")


def test_parse_infobox_returns_empty_when_no_matching_template():
    wt = "{{Unit Infobox|name=X}}\nno weapon here."
    box = wc.parse_infobox(wt, template_name_contains="weapon")
    assert box == {}


def test_parse_infobox_custom_template_needle():
    wt = "{{Unit Infobox|name=Firefly Leader|hp=6}}\n"
    box = wc.parse_infobox(wt, template_name_contains="unit")
    assert box["name"] == "Firefly Leader"
    assert box["hp"] == "6"


# ── high-level entry points ───────────────────────────────────────────────


def test_fetch_page_end_to_end(tmp_path: Path):
    def fake(title, _timeout):
        return _payload(title, (
            "== Description ==\n"
            "Base behavior.\n"
            "=== Advanced Edition ===\n"
            "{{Weapon Infobox|name=Vice Fist|damage=1|push=Throw}}\n"
            "AE blurb.\n"
        ))

    page = wc.fetch_page("Vice Fist", cache_dir=tmp_path, fetcher=fake)
    assert page is not None
    assert page.title == "Vice Fist"
    assert page.used_section == "ae"
    assert "Weapon Infobox" in page.wikitext


def test_fetch_page_missing_returns_none(tmp_path: Path):
    def fake(title, _timeout):
        return _missing_payload(title)

    assert wc.fetch_page("Imaginary", cache_dir=tmp_path, fetcher=fake) is None


def test_fetch_weapon_returns_infobox(tmp_path: Path):
    def fake(title, _timeout):
        return _payload(title, (
            "{{Weapon Infobox\n"
            "| name = Vice Fist\n"
            "| damage = 1\n"
            "| push = Throw\n"
            "}}\n"
        ))

    out = wc.fetch_weapon("Vice Fist", cache_dir=tmp_path, fetcher=fake)
    assert out["title"] == "Vice Fist"
    assert out["infobox"]["damage"] == "1"
    assert out["infobox"]["push"] == "Throw"


def test_fetch_weapon_missing_page_returns_empty_dict(tmp_path: Path):
    def fake(title, _timeout):
        return _missing_payload(title)

    assert wc.fetch_weapon("Imaginary", cache_dir=tmp_path, fetcher=fake) == {}
