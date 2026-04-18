"""Phase 4 P4-1a — weapon-override pattern miner.

Reads two jsonl corpora and groups observations into
``MinedCandidate`` records that cross a configured threshold:

- ``data/weapon_def_mismatches.jsonl`` — Vision-vs-Rust comparator
  output (one entry per comparator run; weapon_id + field already
  present).
- ``recordings/failure_db.jsonl`` — solver-vs-bridge desyncs (per
  action; needs ``weapon_id`` resolved from the same run's
  ``m<NN>_turn_<NN>_solve.json``).

Candidates that appear in the deny list
(``data/weapon_overrides_rejected.jsonl``) are skipped — P4-1b adds
the write side to ``review_overrides reject``.

The miner is pure: it takes paths and returns structured Python,
never writes to disk, never calls git, never runs the solver.
Callers (P4-1c auto-extraction, P4-1d CLI + PR drafter) handle all
side effects.

Why a separate module, not tucked into ``weapon_overrides.py``:

- Keeps the staging-side deserializer (``weapon_overrides.py``) free
  of corpus-reading code — that module is imported by the Rust call
  path and shouldn't be sensitive to jsonl drift.
- Makes the miner unit-testable with only stdlib: take bytes in,
  return records out.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VISION_PATH = REPO_ROOT / "data" / "weapon_def_mismatches.jsonl"
DEFAULT_FAILURE_PATH = REPO_ROOT / "recordings" / "failure_db.jsonl"
DEFAULT_DENY_PATH = REPO_ROOT / "data" / "weapon_overrides_rejected.jsonl"
DEFAULT_RECORDINGS_ROOT = REPO_ROOT / "recordings"


# ── signatures ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DiffSignature:
    """Canonical identity for a "same shape of disagreement".

    Two observations share a signature iff they point at the same
    (weapon, field, before, after) pattern — the miner collapses
    multiple boards reporting the same signature into one candidate.

    ``source`` keeps Vision and failure_db hits separate because
    their thresholds differ and mixing them in one count would let
    2 solver desyncs masquerade as 2 Vision reads.
    """

    source: str            # "vision" | "failure_db"
    weapon_id: str
    field: str             # "damage" | "push_arrows" | "damage_amount" | ...
    rust_bucket: str       # canonical pre-patch value
    vision_bucket: str     # canonical observed value

    def hash8(self) -> str:
        raw = f"{self.source}|{self.weapon_id}|{self.field}|{self.rust_bucket}|{self.vision_bucket}"
        return hashlib.sha1(raw.encode()).hexdigest()[:8]


@dataclass
class MinedCandidate:
    """A signature that cleared its threshold, with provenance.

    ``board_refs`` is deterministic (sorted) so the caller's PR-draft
    title and branch hash are stable across runs.
    """

    signature: DiffSignature
    count: int
    board_refs: list[tuple[str, int, int]]      # (run_id, mission, turn)
    sample_entries: list[dict] = field(default_factory=list)

    @property
    def hash8(self) -> str:
        return self.signature.hash8()


# ── thresholds ──────────────────────────────────────────────────────────────


# Defaults come from the Phase 4 design discussion:
# - Vision's damage read is essentially ground truth on high-confidence
#   parses (it's literally the number printed on the preview card), so
#   one observation is enough to stage.
# - Vision footprint/push counting is noisier (pixel-counted glyphs),
#   so require two independent reads.
# - failure_db desyncs individually include real solver noise — bump
#   threshold to 3 distinct boards before we believe the pattern.
DEFAULT_THRESHOLDS: dict[tuple[str, str], int] = {
    ("vision", "damage"): 1,
    ("vision", "footprint_size"): 2,
    ("vision", "push_arrows"): 2,
    ("vision", "unknown_weapon"): 1,
    ("vision", "passive_has_damage"): 1,
    ("vision", "passive_has_footprint"): 1,
}
FAILURE_DEFAULT_THRESHOLD = 3


def _threshold_for(
    signature: DiffSignature,
    thresholds: dict[tuple[str, str], int] | None,
) -> int:
    t = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)
    key = (signature.source, signature.field)
    if key in t:
        return t[key]
    if signature.source == "failure_db":
        return FAILURE_DEFAULT_THRESHOLD
    # Unknown vision fields fall back to failure-level caution: the
    # miner would rather under-stage than flood review.
    return FAILURE_DEFAULT_THRESHOLD


# ── signature extractors ────────────────────────────────────────────────────


def signature_from_vision(mm: dict) -> DiffSignature | None:
    """Build a signature from a ``weapon_def_mismatches.jsonl`` entry.

    Returns ``None`` when the entry isn't stageable — e.g.,
    unknown_weapon without a resolvable display_name, or a row that
    predates the current jsonl schema.
    """
    weapon_id = mm.get("weapon_id") or ""
    field_name = mm.get("field") or ""
    if not field_name:
        return None
    # unknown_weapon rows don't have a real weapon_id; key by display_name
    # so the same mystery weapon collapses across runs.
    if field_name == "unknown_weapon":
        display = mm.get("display_name") or mm.get("vision_value") or ""
        weapon_id = f"?:{str(display).strip().lower()}"
    elif not weapon_id:
        return None
    rust_bucket = _bucket(mm.get("rust_value"))
    vision_bucket = _bucket(mm.get("vision_value"))
    return DiffSignature(
        source="vision",
        weapon_id=weapon_id,
        field=field_name,
        rust_bucket=rust_bucket,
        vision_bucket=vision_bucket,
    )


# Only failure_db triggers that carry a specific weapon are in scope.
# Movement-only desyncs (per_sub_action_desync_move) can't be patched by
# a weapon-def override — they're a mech/pathing concern.
_WEAPON_ATTRIBUTABLE_TRIGGERS = frozenset({
    "per_action_desync",
    "per_sub_action_desync_attack",
})


def signature_from_failure(
    f: dict,
    *,
    solve_loader: "SolveLoader",
) -> DiffSignature | None:
    """Build a signature from a ``failure_db.jsonl`` entry.

    Returns ``None`` unless the entry is an attack-attributable
    desync with a resolvable ``weapon_id``. ``solve_loader`` is
    injected so tests can stub the disk read.
    """
    trigger = f.get("trigger") or ""
    if trigger not in _WEAPON_ATTRIBUTABLE_TRIGGERS:
        return None
    action_index = f.get("action_index")
    if action_index is None:
        return None
    run_id = f.get("run_id") or ""
    mission = f.get("mission")
    turn = f.get("turn")
    if not run_id or mission is None or turn is None:
        return None
    weapon_id = solve_loader.weapon_id_for(run_id, int(mission), int(turn), int(action_index))
    if not weapon_id:
        return None
    category = f.get("category") or ""
    if not category:
        return None
    diff = f.get("diff") or {}
    vision_bucket = _diff_shape_bucket(diff)
    # Rust side: for failure_db we don't have a clean "rust value" — the
    # bucket just encodes "sim predicted differently" with the affected
    # fields as the identity. That keeps the same (weapon, category,
    # diff_shape) counted together across boards.
    rust_bucket = "predicted"
    return DiffSignature(
        source="failure_db",
        weapon_id=weapon_id,
        field=category,
        rust_bucket=rust_bucket,
        vision_bucket=vision_bucket,
    )


def _diff_shape_bucket(diff: dict) -> str:
    """Compact string describing *which fields* drifted on a desync.

    Not the numeric values — those vary per board and would blow up
    the count. The shape ("tile:fire,terrain | unit: | scalar:") is
    what we want to group by.
    """
    def fields_of(entries: list | None) -> str:
        if not entries:
            return ""
        s = set()
        for e in entries:
            if isinstance(e, dict):
                s.add(str(e.get("field", "?")))
        return ",".join(sorted(s))

    return (
        f"tile:{fields_of(diff.get('tile_diffs'))}|"
        f"unit:{fields_of(diff.get('unit_diffs'))}|"
        f"scalar:{fields_of(diff.get('scalar_diffs'))}"
    )


def _bucket(v: Any) -> str:
    """Stable stringification for the rust/vision sides of a signature.

    Dicts are key-sorted so ``{"push_dir":"inward","expected":[1,4]}``
    and ``{"expected":[1,4],"push_dir":"inward"}`` collide. Lists keep
    order — they're usually ``[min, max]`` tuples where order matters.
    """
    if v is None:
        return ""
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    if isinstance(v, (list, tuple)):
        return json.dumps(list(v), separators=(",", ":"))
    return str(v)


# ── solve-file loader (failure_db → weapon_id resolution) ───────────────────


class SolveLoader:
    """Resolves ``(run_id, mission, turn, action_index) -> weapon_id``.

    Caches per-file solve JSON to avoid rereading the same turn for
    multiple desync records on the same action. Tests pass in a
    recordings_root; production defaults to repo root.
    """

    def __init__(self, recordings_root: Path | str = DEFAULT_RECORDINGS_ROOT) -> None:
        self._root = Path(recordings_root)
        self._cache: dict[tuple[str, int, int], list[dict]] = {}

    def _actions_for(self, run_id: str, mission: int, turn: int) -> list[dict]:
        key = (run_id, mission, turn)
        if key in self._cache:
            return self._cache[key]
        fname = f"m{mission:02d}_turn_{turn:02d}_solve.json"
        path = self._root / run_id / fname
        if not path.exists():
            self._cache[key] = []
            return []
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            self._cache[key] = []
            return []
        data = raw.get("data") if isinstance(raw, dict) else {}
        actions = data.get("actions") if isinstance(data, dict) else []
        self._cache[key] = actions if isinstance(actions, list) else []
        return self._cache[key]

    def weapon_id_for(
        self, run_id: str, mission: int, turn: int, action_index: int,
    ) -> str | None:
        actions = self._actions_for(run_id, mission, turn)
        if 0 <= action_index < len(actions):
            wid = actions[action_index].get("weapon_id") if isinstance(actions[action_index], dict) else None
            return str(wid) if wid else None
        return None


# ── deny-list ───────────────────────────────────────────────────────────────


def load_deny_list(path: Path | str | None = None) -> set[str]:
    """Return the set of ``signature.hash8()`` strings already rejected.

    Missing file = empty set (first run). Malformed lines are skipped
    silently — the deny list is advisory, not authoritative; worst
    case a rejected candidate re-surfaces in the next draft PR.
    """
    p = Path(path) if path is not None else DEFAULT_DENY_PATH
    if not p.exists():
        return set()
    out: set[str] = set()
    for raw in p.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        h = rec.get("signature_hash") or rec.get("hash8")
        if isinstance(h, str) and h:
            out.add(h)
    return out


# ── main mining loop ────────────────────────────────────────────────────────


def _iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw)
        except json.JSONDecodeError:
            continue


def mine(
    *,
    vision_path: Path | str | None = None,
    failure_path: Path | str | None = None,
    deny_list: set[str] | None = None,
    thresholds: dict[tuple[str, str], int] | None = None,
    recordings_root: Path | str | None = None,
    sample_cap: int = 3,
) -> list[MinedCandidate]:
    """Group jsonl corpora by signature and return crossing candidates.

    ``sample_cap`` trims how many raw entries ride along per candidate
    — PR drafts want a few for context, not the entire cohort.
    """
    vp = Path(vision_path) if vision_path is not None else DEFAULT_VISION_PATH
    fp = Path(failure_path) if failure_path is not None else DEFAULT_FAILURE_PATH
    rr = Path(recordings_root) if recordings_root is not None else DEFAULT_RECORDINGS_ROOT
    deny = deny_list if deny_list is not None else load_deny_list()

    groups: dict[DiffSignature, dict[str, Any]] = defaultdict(
        lambda: {"refs": set(), "samples": []}
    )

    # Vision pass.
    for mm in _iter_jsonl(vp):
        sig = signature_from_vision(mm)
        if sig is None:
            continue
        if sig.hash8() in deny:
            continue
        g = groups[sig]
        ref = (
            mm.get("run_id") or "",
            -1,  # vision mismatches aren't tied to a mission/turn
            -1,
        )
        g["refs"].add(ref)
        if len(g["samples"]) < sample_cap:
            g["samples"].append(dict(mm))

    # failure_db pass (needs solve.json resolution).
    loader = SolveLoader(rr)
    for f in _iter_jsonl(fp):
        sig = signature_from_failure(f, solve_loader=loader)
        if sig is None:
            continue
        if sig.hash8() in deny:
            continue
        g = groups[sig]
        ref = (
            f.get("run_id") or "",
            int(f.get("mission") or 0),
            int(f.get("turn") or 0),
        )
        g["refs"].add(ref)
        if len(g["samples"]) < sample_cap:
            g["samples"].append(dict(f))

    out: list[MinedCandidate] = []
    for sig, g in groups.items():
        refs = sorted(g["refs"])
        count = len(refs)
        if count < _threshold_for(sig, thresholds):
            continue
        out.append(MinedCandidate(
            signature=sig,
            count=count,
            board_refs=refs,
            sample_entries=list(g["samples"]),
        ))

    # Deterministic output order so PR-draft branches are stable.
    out.sort(key=lambda c: (c.signature.weapon_id, c.signature.field, c.signature.hash8()))
    return out
