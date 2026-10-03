"""Link bounded movement evidence to the atlas without promoting review levels."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PREFIX = "windows_build_13725832_31fe35265598_"
BASELINE_INVENTORY = "data/observatory/inventories/" + PREFIX + "full_decompile_baseline_20260830.json"


def canonical_sha256(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":"), sort_keys=True) + "\n"
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_ledger(root: Path, executable: Path) -> dict:
    """Use the existing verifier, including original executable atlas rereads."""
    from src.observatory.native_function_accounting import validate_native_function_accounting
    directory = root / "data/observatory/programs"
    def load(suffix: str) -> dict:
        return json.loads((directory / (PREFIX + suffix + ".json")).read_text(encoding="utf-8"))
    inventory = json.loads((root / BASELINE_INVENTORY).read_text(encoding="utf-8"))
    result = validate_native_function_accounting(
        executable, load("native_function_accounting"), load("program_facts"),
        load("native_function_review_registry"), inventory=inventory, repo_root=root,
    )
    return {"status": result["status"], "evidence_sha256": result["evidence_sha256"],
            "inventory_path": BASELINE_INVENTORY, "inventory_canonical_sha256": canonical_sha256(inventory)}


def build_movement_index(root: Path) -> dict:
    directory = root / "data/observatory/programs"

    def load(suffix: str) -> dict:
        return json.loads((directory / (PREFIX + suffix + ".json")).read_text(encoding="utf-8"))

    atlas = load("program_facts")
    registry = load("native_function_review_registry")
    ledger = load("native_function_accounting")
    atlas_hash = canonical_sha256(atlas)
    if registry["atlas_canonical_sha256"] != atlas_hash:
        raise ValueError("registry atlas pin differs")
    functions = {entry["entry_rva"]: entry for entry in atlas["functions"]}
    if registry["claims"] or ledger["summary"]["reviewed_functions"] != 0:
        raise ValueError("S0 zero-promotion baseline changed; reconcile explicitly")
    if ledger["summary"]["level_L0"] != len(functions):
        raise ValueError("ledger L0 denominator differs")

    receipts = []
    for path in sorted(directory.glob(PREFIX + "native_movement*conformance.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        summary = value["summary"]
        if summary.get("accounting_delta", summary.get("accounting_promotions")) != 0:
            raise ValueError(f"unexpected promotion in {path.name}")
        receipts.append({"path": path.relative_to(root).as_posix(),
                         "canonical_sha256": canonical_sha256(value),
                         "evidence_class": "retained_bounded_original_body_execution_receipt",
                         "cases": summary["cases"],
                         "negative_controls": summary.get("negative_controls", summary.get("controls")),
                         "scope": value["scope"]})

    joins = []
    for suffix in ("native_movement_effect_binding", "native_movement_addmove_normal_conformance",
                   "native_movement_addcharge_normal_conformance"):
        value = load(suffix)
        bodies = value["bodies"]
        rows = bodies.values() if isinstance(bodies, dict) else bodies
        joined = []
        for body in rows:
            rva = body["entry_rva"]
            entry = functions[rva]
            body_hash = body.get("sha256", body.get("body_sha256"))
            if body_hash != entry["body_sha256"]:
                raise ValueError(f"body hash differs at {rva}")
            # Binding bodies store length as size; conformance bodies do too.
            size = body["size"]
            if size != entry["body_size"]:
                raise ValueError(f"body size differs at {rva}")
            joined.append({"entry_rva": rva, "body_size": size, "body_sha256": body_hash})
        joins.append({"path": (directory / (PREFIX + suffix + ".json")).relative_to(root).as_posix(),
                      "canonical_sha256": canonical_sha256(value),
                      "evidence_class": "static_binding" if suffix.endswith("binding") else "bounded_original_body_execution",
                      "matched_atlas_bodies": joined})

    return {
        "schema_version": 1, "kind": "solver_first_movement_evidence_reconciliation",
        "atlas_canonical_sha256": atlas_hash,
        "registry_canonical_sha256": canonical_sha256(registry),
        "ledger_canonical_sha256": canonical_sha256(ledger),
        "ledger": {key: ledger["summary"][key] for key in
                   ("atlas_functions", "level_L0", "level_L1", "level_L2", "reviewed_functions", "reviewed_exclusions")},
        "receipts": receipts, "atlas_joins": joins,
        "retained_case_sum": sum(r["cases"] for r in receipts),
        "retained_negative_control_sum": sum(r["negative_controls"] for r in receipts),
        "count_policy": "Overlapping bounded experiments, not distinct gameplay scenarios or whole functions recovered.",
        "october_2_seven_laws": {"handoff": "docs/decompile_handoff_2026_10_02.md",
                                "evidence_class": "model_and_independent_tests_with_prose_reported_native_probes",
                                "published_corpus_receipts": 0,
                                "hash_convention": "Seven model hashes match Git LF blobs; three test hashes in handoff use checkout CRLF, four use Git LF."},
        "ledger_promotions": 0,
        "not_established": ["reviewed exact whole-function boundaries", "ownership classification",
                            "complete immediate reference sets", "Lua consumer execution", "pawn movement",
                            "full-turn fidelity", "gameplay coverage percentage"],
    }
