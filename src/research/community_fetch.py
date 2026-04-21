"""Community-notes fetcher — Steam forum + Reddit.

Third source in the research pipeline after in-game tooltip
(``vision``) and Fandom wiki (``wiki_client``). Community threads
surface edge-case interactions the wiki sanitizes or omits.

Python can't drive ``WebFetch`` directly — it's a harness-side tool.
So this module mirrors the capture / orchestrator pattern: Python
builds the query URLs and exposes them to the harness through
``orchestrator.submit_research``'s result payload; the harness
runs ``WebFetch`` on each URL, summarizes, and calls
``cmd_research_attach_community`` with the normalized excerpts.

Confidence banding is defined in ``docs/self_healing_loop_design.md``
§External research: confirmed = tooltip + wiki + community agree,
likely = tooltip + wiki, speculative = community-only, none = nothing.
"""

from __future__ import annotations

import urllib.parse
from typing import Any


STEAM_APP_ID = "590380"  # Into the Breach on Steam


def build_queries(name: str) -> dict[str, str]:
    """Return WebFetch-ready search URLs for the named target.

    Two queries per unknown: Steam discussions and r/IntoTheBreach.
    Both are direct search pages that the harness can scrape for
    thread titles + snippets. Returns an empty dict when ``name`` is
    blank — skip the community step rather than search empty.
    """
    name = (name or "").strip()
    if not name:
        return {}
    q = urllib.parse.quote_plus(name)
    return {
        "steam_forum": (
            f"https://steamcommunity.com/app/{STEAM_APP_ID}/discussions/search/?q={q}"
        ),
        "reddit": (
            f"https://www.reddit.com/r/IntoTheBreach/search/?q={q}&restrict_sr=1"
        ),
    }


def normalize_notes(raw: Any) -> list[dict]:
    """Flatten harness-supplied WebFetch results into note records.

    Expected input shape (from ``cmd_research_attach_community``):

    ::

        {
          "steam_forum": {
            "url": "https://...",
            "excerpt": "summary text Claude extracted from the page",
            "confidence": 0.7
          },
          "reddit": {...}
        }

    Output: sorted list of ``{source, url, excerpt, confidence}``
    records. Entries with empty excerpts or sub-threshold confidence
    are dropped by ``drop_low_confidence`` before persistence — this
    function returns everything structurally valid so the caller can
    decide whether to keep or drop.
    """
    if not isinstance(raw, dict):
        return []
    out: list[dict] = []
    for source, data in raw.items():
        if not isinstance(data, dict):
            continue
        excerpt = str(data.get("excerpt", "")).strip()
        if not excerpt:
            continue
        try:
            conf = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(conf, 1.0))
        out.append({
            "source": str(source),
            "url": str(data.get("url", "")),
            "excerpt": excerpt,
            "confidence": round(conf, 2),
        })
    out.sort(key=lambda n: n["source"])  # deterministic order
    return out


# Sub-threshold notes are dropped before they land in the wiki_raw
# record. Sparse / joke / contradicted threads give low confidence at
# the harness summarization step; we treat them as noise.
COMMUNITY_NOTE_THRESHOLD = 0.3


def drop_low_confidence(notes: list[dict]) -> list[dict]:
    """Return only notes whose confidence clears the threshold."""
    return [n for n in notes if float(n.get("confidence", 0.0)) >= COMMUNITY_NOTE_THRESHOLD]


def classify_confidence(
    tooltip_ok: bool,
    wiki_ok: bool,
    community_count: int,
) -> str:
    """Pick a confidence band per the design doc.

    - ``confirmed`` — tooltip + wiki + community all corroborate.
    - ``likely`` — tooltip + wiki agree; no community data yet.
    - ``speculative`` — only community notes (no Vision, no wiki).
    - ``none`` — nothing usable from any source.
    """
    if tooltip_ok and wiki_ok and community_count > 0:
        return "confirmed"
    if tooltip_ok and wiki_ok:
        return "likely"
    if community_count > 0 and not (tooltip_ok or wiki_ok):
        return "speculative"
    if tooltip_ok or wiki_ok:
        # Partial agreement — treat as likely, even without community data.
        return "likely"
    return "none"
