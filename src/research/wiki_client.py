"""Fandom MediaWiki client for Phase 2 research fallback.

Called when the in-game tooltip extraction (``src.research.vision``)
comes back below the confidence threshold, or for non-combat
entities (status effects, island-level features) that don't have an
in-game panel at all.

Endpoint: ``https://intothebreach.fandom.com/api.php`` with
``action=query&titles=<Name>&prop=revisions&rvprop=content&format=json``.
We ask for the raw wikitext rather than the rendered HTML — the
infobox templates are easier to parse than scraped HTML, and the
payload is ~10× smaller.

Caching: every fetched page lands in ``data/wiki_raw/<Name>.json``.
The cache is content-addressed by title, never invalidated
automatically — the wiki moves slowly and we'd rather re-use a
slightly stale snapshot than hammer the API. Manual ``rm`` is the
way to refresh.

AE filter: Into the Breach Advanced Edition ships alongside the
base game; the wiki flags AE content with ``{{AE}}`` templates or
a ``=== Advanced Edition ===`` header. Since we run AE, the AE
section wins when both are present; the base section is the
fallback when no AE section exists.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


WIKI_API_URL = "https://intothebreach.fandom.com/api.php"
WIKI_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "wiki_raw"

DEFAULT_USER_AGENT = (
    "ItB-achievement-bot/0.1 (self-healing research client; "
    "https://github.com/ancientastronauttheorist/ItB)"
)


# ── raw fetch + cache ────────────────────────────────────────────────────────


@dataclass
class WikiPage:
    """Parsed shape of a fandom wiki page."""
    title: str
    wikitext: str
    # Section preference: "ae" if an AE-specific section exists, else "base".
    used_section: str


def _cache_path(title: str, cache_dir: Path | None = None) -> Path:
    """Map a page title to its cache file.

    Titles get URL-encoded so slashes, spaces, and non-ASCII don't
    escape the cache dir — the encoded name is safe on every platform.
    """
    d = cache_dir or WIKI_CACHE_DIR
    safe = urllib.parse.quote(title, safe="")
    return d / f"{safe}.json"


def _default_fetcher(title: str, timeout_s: float) -> dict:
    """Hit the Fandom API and return the parsed JSON response."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json",
        "formatversion": "2",
    }
    url = f"{WIKI_API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_raw(
    title: str,
    *,
    cache_dir: Path | None = None,
    fetcher: Callable[[str, float], dict] | None = None,
    timeout_s: float = 10.0,
    refresh: bool = False,
) -> dict:
    """Fetch the raw MediaWiki JSON response for ``title``, with caching.

    Args:
        title: Page title (e.g. "Vice Fist", "Firefly Leader").
        cache_dir: Override the default cache location (tests).
        fetcher: Override the default HTTP fetcher (tests).
        timeout_s: HTTP timeout.
        refresh: If True, bypass the cache and hit the API.
    """
    d = cache_dir or WIKI_CACHE_DIR
    p = _cache_path(title, cache_dir=d)
    if p.exists() and not refresh:
        return json.loads(p.read_text())

    actual_fetcher = fetcher or _default_fetcher
    payload = actual_fetcher(title, timeout_s)
    d.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))
    return payload


def extract_wikitext(payload: dict) -> str:
    """Pull the wikitext body out of a MediaWiki query response.

    Returns "" when the response signals page-missing or has no
    revisions — callers should treat that as "no article for this
    title; try a different spelling or skip".
    """
    # formatversion=2 response shape:
    # {"query": {"pages": [{"pageid": ..., "title": ..., "revisions": [{"content": "..."}]}]}}
    query = payload.get("query") or {}
    pages = query.get("pages") or []
    if not pages:
        return ""
    page = pages[0]
    if page.get("missing"):
        return ""
    revs = page.get("revisions") or []
    if not revs:
        return ""
    return revs[0].get("content", "") or revs[0].get("*", "") or ""


# ── AE section filter ───────────────────────────────────────────────────────


AE_HEADER_RE = re.compile(
    r"^(==+)\s*Advanced Edition\s*\1\s*$",
    re.MULTILINE | re.IGNORECASE,
)
HEADER_RE = re.compile(r"^(==+)\s*([^=].*?)\s*\1\s*$", re.MULTILINE)


def pick_ae_section(wikitext: str) -> tuple[str, str]:
    """Return ``(section_text, used)`` — AE section if present, else full text.

    When the AE section is found, ``used == "ae"`` and the returned
    text spans from the AE header to the next heading of the same or
    higher level (or end of page). Otherwise ``used == "base"`` and
    we return the full wikitext.
    """
    m = AE_HEADER_RE.search(wikitext)
    if not m:
        return (wikitext, "base")

    level = len(m.group(1))  # number of '=' signs
    start = m.end()

    # Find the next header whose level is <= this one.
    rest = wikitext[start:]
    for hm in HEADER_RE.finditer(rest):
        next_level = len(hm.group(1))
        if next_level <= level:
            return (rest[: hm.start()].strip(), "ae")
    return (rest.strip(), "ae")


def fetch_page(
    title: str,
    *,
    cache_dir: Path | None = None,
    fetcher: Callable[[str, float], dict] | None = None,
    timeout_s: float = 10.0,
    refresh: bool = False,
) -> WikiPage | None:
    """High-level fetch: raw payload → wikitext → AE-filtered section.

    Returns None when the page doesn't exist on the wiki.
    """
    payload = fetch_raw(
        title,
        cache_dir=cache_dir, fetcher=fetcher,
        timeout_s=timeout_s, refresh=refresh,
    )
    wikitext = extract_wikitext(payload)
    if not wikitext:
        return None
    section, used = pick_ae_section(wikitext)
    return WikiPage(title=title, wikitext=section, used_section=used)


# ── infobox parser ──────────────────────────────────────────────────────────

def _scan_templates(wikitext: str) -> list[tuple[str, str]]:
    """Yield ``(name, body)`` for each top-level template in ``wikitext``.

    Regex can't match balanced ``{{...}}`` pairs when templates nest
    (e.g. a field value containing ``{{icon|x}}``), so we scan with
    a depth counter. Only TOP-level templates are emitted — nested
    ones live inside a parent's body.
    """
    out: list[tuple[str, str]] = []
    i = 0
    n = len(wikitext)
    while i < n - 1:
        if wikitext[i] == "{" and wikitext[i + 1] == "{":
            # Find the matching closing ``}}``.
            depth = 1
            j = i + 2
            while j < n - 1 and depth > 0:
                if wikitext[j] == "{" and wikitext[j + 1] == "{":
                    depth += 1
                    j += 2
                    continue
                if wikitext[j] == "}" and wikitext[j + 1] == "}":
                    depth -= 1
                    j += 2
                    continue
                j += 1
            if depth != 0:
                # Unbalanced — bail on this template.
                i = j
                continue
            inner = wikitext[i + 2 : j - 2]
            # Split name / body on the first top-level ``|``.
            name, _, body = _split_first_pipe(inner)
            out.append((name.strip(), body))
            i = j
            continue
        i += 1
    return out


def _split_first_pipe(body: str) -> tuple[str, str, str]:
    """Split ``body`` at the first depth-zero ``|``."""
    depth = 0
    for k, c in enumerate(body):
        if c == "{" and k + 1 < len(body) and body[k + 1] == "{":
            depth += 1
        elif c == "}" and k + 1 < len(body) and body[k + 1] == "}":
            depth = max(0, depth - 1)
        elif c == "[" and k + 1 < len(body) and body[k + 1] == "[":
            depth += 1
        elif c == "]" and k + 1 < len(body) and body[k + 1] == "]":
            depth = max(0, depth - 1)
        elif c == "|" and depth == 0:
            return body[:k], "|", body[k + 1 :]
    return body, "", ""


def parse_infobox(
    wikitext: str,
    *,
    template_name_contains: str = "weapon",
) -> dict[str, str]:
    """Extract key=value pairs from the first matching infobox template.

    Most ITB wiki weapon pages open with ``{{Weapon Infobox |name=... |damage=...}}``.
    We find the first template whose name contains ``template_name_contains``
    (case-insensitive) and split its body on ``|``.

    Returns an empty dict when no matching template is found — caller
    should treat that as "wiki page exists but doesn't have the
    expected infobox".
    """
    needle = template_name_contains.lower()
    for name, body in _scan_templates(wikitext):
        if needle in name.lower():
            return _split_infobox_body(body)
    return {}


def _split_infobox_body(body: str) -> dict[str, str]:
    """Split an infobox body on ``|``, respecting nested templates/links.

    Naive ``.split("|")`` breaks on nested ``{{...|...}}`` or
    ``[[file|alt]]``. We scan with a depth counter instead.
    """
    fields: list[str] = []
    depth = 0
    buf: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == "{" and i + 1 < len(body) and body[i + 1] == "{":
            depth += 1
            buf.append("{{")
            i += 2
            continue
        if c == "}" and i + 1 < len(body) and body[i + 1] == "}":
            depth = max(0, depth - 1)
            buf.append("}}")
            i += 2
            continue
        if c == "[" and i + 1 < len(body) and body[i + 1] == "[":
            depth += 1
            buf.append("[[")
            i += 2
            continue
        if c == "]" and i + 1 < len(body) and body[i + 1] == "]":
            depth = max(0, depth - 1)
            buf.append("]]")
            i += 2
            continue
        if c == "|" and depth == 0:
            fields.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if buf:
        fields.append("".join(buf))

    out: dict[str, str] = {}
    for field in fields:
        if "=" not in field:
            continue
        k, _, v = field.partition("=")
        key = k.strip().lower()
        val = v.strip()
        if key:
            out[key] = val
    return out


# ── public entry points used by the research processor ─────────────────────


def fetch_weapon(
    title: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Shortcut: fetch ``title`` and return ``{page, infobox}`` or ``{}``.

    ``page`` is the ``WikiPage`` dataclass as a dict so the caller can
    pickle/serialize the whole thing; ``infobox`` is the extracted
    key/value dict.
    """
    page = fetch_page(title, **kwargs)
    if page is None:
        return {}
    return {
        "title": page.title,
        "used_section": page.used_section,
        "wikitext": page.wikitext,
        "infobox": parse_infobox(page.wikitext, template_name_contains="weapon"),
    }
