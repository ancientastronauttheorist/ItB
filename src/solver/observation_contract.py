"""Explicit information boundary for offline solver-first evaluations.

This is an experimental evaluation adapter, not the live bridge adapter.
Classification is provisional: an allowed key still needs evidence that its
value came from the visible board, action history, or public game definitions.
Unreviewed fields fail closed instead of being silently lost.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).resolve().parents[2] / "data/solver_first/s0_information_contract.json"


class ObservationBoundaryError(ValueError):
    pass


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def player_observation(raw: dict[str, Any], *, contract: dict | None = None) -> dict:
    """Project a declared observation to canonical planner keys.

    Known oracle-only fields are discarded at every supported object level.
    Pending fields, configuration supplied inside raw game state, and unknown
    fields are rejected. Configuration must be selected independently; this
    adapter intentionally does not accept weights or runtime weapon patches.
    The caller must establish acquisition provenance; filtering alone cannot.
    """
    policy = load_contract() if contract is None else contract

    def project(value: dict, scope: str, path: str) -> dict:
        if type(value) is not dict:
            raise ObservationBoundaryError(f"{path} must be an object")
        rules = policy["fields"][scope]
        result = {}
        for key, item in value.items():
            category = rules.get(key)
            if category == "oracle_only":
                continue
            if category not in {"visible", "public_rule", "observation_identity"}:
                raise ObservationBoundaryError(f"{path}.{key}: {category or 'unclassified'}")
            if scope == "JsonInput" and key in {"tiles", "units"}:
                if type(item) is not list:
                    raise ObservationBoundaryError(f"{path}.{key} must be a list")
                child_scope = "JsonTile" if key == "tiles" else "JsonUnit"
                result[key] = [project(child, child_scope, f"{path}.{key}[{i}]")
                               for i, child in enumerate(item)]
            else:
                # No admitted structured leaf may carry unclassified nested
                # oracle fields. The current contract admits scalar arrays only.
                def check_leaf(leaf: Any) -> None:
                    if isinstance(leaf, dict):
                        raise ObservationBoundaryError(f"{path}.{key}: structured leaf requires audit")
                    if isinstance(leaf, list):
                        for part in leaf:
                            check_leaf(part)
                check_leaf(item)
                result[key] = deepcopy(item)
        return result

    result = project(raw, "JsonInput", "state")
    if "tiles" in result:
        result["tiles"] = sorted(result["tiles"], key=lambda tile: (tile["x"], tile["y"]))
        positions = [(tile["x"], tile["y"]) for tile in result["tiles"]]
        if len(set(positions)) != len(positions):
            raise ObservationBoundaryError("duplicate visible tile positions")
    # Engine-assigned UIDs are not observable information. Use labels derived
    # from visible identity and remap references instead of passing them through.
    units = sorted(result.get("units", []), key=lambda u: (u["x"], u["y"], u["type"]))
    identities = [(u["x"], u["y"], u["type"]) for u in units]
    if len(set(identities)) != len(identities):
        raise ObservationBoundaryError("ambiguous visible unit identities")
    remap = {}
    for label, unit in enumerate(units):
        if "is_grappled" in unit:
            if "grappled" in unit:
                raise ObservationBoundaryError("duplicate grappled representations")
            unit["grappled"] = unit.pop("is_grappled")
        uid = unit.get("uid")
        if uid is not None:
            if type(uid) is not int or uid in remap:
                raise ObservationBoundaryError("invalid or duplicate engine unit identifier")
            remap[uid] = label
        unit["uid"] = label
    if "units" in result:
        result["units"] = units
    if "attack_order" in result:
        try:
            if any(type(uid) is not int for uid in result["attack_order"]):
                raise ObservationBoundaryError("invalid attack order identifier")
            result["attack_order"] = [remap[uid] for uid in result["attack_order"]]
        except (KeyError, TypeError) as exc:
            raise ObservationBoundaryError("attack order lacks a visible unit identity") from exc
    return result


def encode_observation(raw: dict[str, Any]) -> str:
    """Stable serialization; equal observations produce equal planner inputs."""
    return json.dumps(player_observation(raw), sort_keys=True, separators=(",", ":"), allow_nan=False)
