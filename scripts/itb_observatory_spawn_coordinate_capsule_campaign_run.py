#!/usr/bin/env python3
"""Run, restore, import, validate, and seal the nine-condition capsule campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import itb_observatory_pair_state as pair_state  # noqa: E402
from scripts import itb_observatory_spawn_coordinate_capsule_condition as condition_runner  # noqa: E402
from src.observatory.spawn_coordinate_capsule_campaign import (  # noqa: E402
    CAMPAIGN_LIFECYCLE_KIND,
    PAIR_SPECS,
    SpawnCoordinateCapsuleCampaignError,
    build_spawn_coordinate_capsule_campaign_receipt,
    publish_spawn_coordinate_capsule_campaign_receipt,
)


class CapsuleCampaignRunError(RuntimeError):
    """Raised when a live campaign cannot be completed and sealed exactly."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--repository-campaign-root", type=Path, required=True)
    parser.add_argument("--receipt-output", type=Path, required=True)
    parser.add_argument("--save-root", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, required=True)
    parser.add_argument("--source-session", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--module", type=Path, required=True)
    parser.add_argument("--profile", default="Alpha")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--max-wait", type=float, default=45.0)
    parser.add_argument("--process-wait", type=float, default=30.0)
    parser.add_argument("--bridge-wait", type=float, default=60.0)
    parser.add_argument("--close-wait", type=float, default=30.0)
    parser.add_argument("--wait-poll-interval", type=float, default=0.20)
    parser.add_argument("--candidate-rank", type=int, default=None)
    parser.add_argument("--allow-dirty-plan", action="store_true")
    parser.add_argument("--dirty-consent-id", default=None)
    parser.add_argument("--allow-protected-objective-loss", action="store_true")
    parser.add_argument("--allow-objective-loss", action="store_true")
    parser.add_argument("--allow-timeline-collapse", action="store_true")
    parser.add_argument("--allow-mech-loss", action="store_true")
    parser.add_argument(
        "--no-frontier-diagnostics",
        dest="frontier_diagnostics",
        action="store_false",
        default=True,
    )
    return parser


def _external_empty_root(path: Path) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.is_symlink() or not candidate.is_dir():
        raise CapsuleCampaignRunError(f"artifact root is unavailable: {candidate}")
    root = candidate.resolve()
    repo = ROOT.resolve()
    if root == repo or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise CapsuleCampaignRunError("artifact root must not overlap the repository")
    if any(root.iterdir()):
        raise CapsuleCampaignRunError("artifact root must be empty")
    return root


def _fresh_repository_path(path: Path, label: str, *, directory: bool) -> Path:
    candidate = Path(os.path.abspath(path.expanduser()))
    if candidate.exists() or candidate.is_symlink():
        raise CapsuleCampaignRunError(f"{label} already exists: {candidate}")
    captures_root = (ROOT / "data" / "observatory" / "captures").resolve()
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(captures_root) or resolved == captures_root:
        raise CapsuleCampaignRunError(
            f"{label} must be a fresh path below {captures_root}"
        )
    if directory and resolved.suffix:
        raise CapsuleCampaignRunError(f"{label} must be a directory path")
    if not directory and resolved.suffix.lower() != ".json":
        raise CapsuleCampaignRunError(f"{label} must be a JSON file")
    return resolved


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root: Path) -> list[dict[str, Any]]:
    if root.is_symlink() or not root.is_dir():
        raise CapsuleCampaignRunError(f"campaign tree is unavailable: {root}")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise CapsuleCampaignRunError(f"campaign tree contains a symlink: {path}")
        if path.is_file():
            entries.append(
                {
                    "relative_path": path.relative_to(root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    if not entries:
        raise CapsuleCampaignRunError("campaign tree has no files")
    return entries


def _write_create_only(path: Path, value: object) -> None:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _condition_args(args: argparse.Namespace, pair_name: str, condition: str) -> argparse.Namespace:
    return argparse.Namespace(
        artifact_root=args.artifact_root,
        pair_id=f"spawn-capsule-pair{pair_name[-3:]}",
        condition=condition,
        save_root=args.save_root,
        snapshot_root=args.snapshot_root,
        source_session=args.source_session,
        executable=args.executable,
        build_receipt=args.build_receipt,
        module=args.module,
        profile=args.profile,
        time_limit=args.time_limit,
        max_wait=args.max_wait,
        process_wait=args.process_wait,
        bridge_wait=args.bridge_wait,
        close_wait=args.close_wait,
        wait_poll_interval=args.wait_poll_interval,
        candidate_rank=args.candidate_rank,
        allow_dirty_plan=args.allow_dirty_plan,
        dirty_consent_id=args.dirty_consent_id,
        allow_protected_objective_loss=args.allow_protected_objective_loss,
        allow_objective_loss=args.allow_objective_loss,
        allow_timeline_collapse=args.allow_timeline_collapse,
        allow_mech_loss=args.allow_mech_loss,
        frontier_diagnostics=args.frontier_diagnostics,
    )


def _final_restore(args: argparse.Namespace) -> dict[str, Any]:
    result = pair_state.restore_state(
        argparse.Namespace(
            save_root=args.save_root,
            snapshot_root=args.snapshot_root,
            allow_restore=True,
        )
    )
    if result != 0:
        raise CapsuleCampaignRunError("final save restore returned nonzero")
    return pair_state.build_start_state_verification_proof(
        args.save_root,
        args.snapshot_root,
    )


def _campaign_lifecycle(
    artifact_root: Path,
    condition_receipts: list[dict[str, Any]],
    final_restore: dict[str, Any] | None,
    errors: dict[str, str],
) -> dict[str, Any]:
    valid = bool(
        len(condition_receipts) == 9
        and final_restore is not None
        and not any(errors.values())
    )
    return {
        "schema_version": 1,
        "kind": CAMPAIGN_LIFECYCLE_KIND,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "capture_track": "owner_local_modified",
        "status": "complete" if valid else "rejected",
        "valid_campaign": valid,
        "artifact_root": str(artifact_root),
        "condition_order": [
            f"{item['pair']}/{item['condition']}" for item in condition_receipts
        ],
        "conditions": condition_receipts,
        "final_restore": final_restore,
        "errors": errors,
    }


def _import_create_only(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise CapsuleCampaignRunError(
            f"repository campaign destination already exists: {destination}"
        )
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    if _tree(source) != _tree(destination):
        raise CapsuleCampaignRunError("repository campaign import differs")


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    artifact_root = _external_empty_root(args.artifact_root)
    args.artifact_root = artifact_root
    repository_campaign_root = _fresh_repository_path(
        args.repository_campaign_root,
        "repository campaign root",
        directory=True,
    )
    receipt_output = _fresh_repository_path(
        args.receipt_output,
        "campaign receipt output",
        directory=False,
    )
    if receipt_output.is_relative_to(repository_campaign_root):
        raise CapsuleCampaignRunError(
            "campaign receipt output must be outside the campaign directory"
        )

    errors = {"conditions": "", "final_restore": ""}
    condition_receipts: list[dict[str, Any]] = []
    final_restore: dict[str, Any] | None = None
    condition_failed = False
    try:
        for pair_name, order in PAIR_SPECS.items():
            for condition in order:
                try:
                    code, receipt = condition_runner.run(
                        _condition_args(args, pair_name, condition)
                    )
                    lifecycle = receipt.get("lifecycle_output")
                    if (
                        code != 0
                        or receipt.get("valid_lifecycle") is not True
                        or not isinstance(lifecycle, dict)
                        or not Path(str(lifecycle.get("path"))).is_file()
                    ):
                        raise CapsuleCampaignRunError(
                            f"{pair_name}/{condition} was rejected"
                        )
                    condition_receipts.append(
                        {
                            "pair": pair_name,
                            "condition": condition,
                            "lifecycle_sha256": str(lifecycle["sha256"]),
                        }
                    )
                except Exception as exc:
                    errors["conditions"] = str(exc)
                    condition_failed = True
                    break
            if condition_failed:
                break
    finally:
        try:
            final_restore = _final_restore(args)
        except Exception as exc:
            errors["final_restore"] = str(exc)

    campaign_lifecycle = _campaign_lifecycle(
        artifact_root,
        condition_receipts,
        final_restore,
        errors,
    )
    lifecycle_path = artifact_root / "campaign_lifecycle.json"
    _write_create_only(lifecycle_path, campaign_lifecycle)
    if campaign_lifecycle["valid_campaign"] is not True:
        return 2, {
            "status": "rejected",
            "valid_campaign": False,
            "artifact_root": str(artifact_root),
            "campaign_lifecycle": str(lifecycle_path),
            "errors": errors,
        }

    _import_create_only(artifact_root, repository_campaign_root)
    receipt = build_spawn_coordinate_capsule_campaign_receipt(
        repository_campaign_root,
        repository_root=ROOT,
    )
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    published_path, published_sha256 = publish_spawn_coordinate_capsule_campaign_receipt(
        receipt,
        receipt_output,
    )
    return 0, {
        "status": "complete",
        "valid_campaign": True,
        "artifact_root": str(artifact_root),
        "artifact_tree": _tree(artifact_root),
        "repository_campaign_root": str(repository_campaign_root),
        "repository_tree": _tree(repository_campaign_root),
        "campaign_lifecycle": {
            "path": str(lifecycle_path),
            "sha256": _sha256(lifecycle_path),
        },
        "receipt": {
            "path": str(published_path),
            "sha256": published_sha256,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        code, result = run(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return code
    except (
        CapsuleCampaignRunError,
        OSError,
        pair_state.PairStateError,
        shutil.Error,
        SpawnCoordinateCapsuleCampaignError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
