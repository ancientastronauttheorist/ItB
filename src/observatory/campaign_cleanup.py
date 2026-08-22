"""Fail-closed cleanup for an ITB Observatory capture campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Sequence


class CampaignCleanupError(ValueError):
    """Raised when cleanup inputs or filesystem boundaries are unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise CampaignCleanupError(f"{label} must be a regular non-symlink file")
    return path.resolve(strict=True)


def _root(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise CampaignCleanupError(f"{label} must be a non-symlink directory")
    return path.resolve(strict=True)


def _is_experimental_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith("itb_observatory_") or lowered.startswith(
        "observatory_"
    )


def _experimental_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        dirnames[:] = [
            name for name in dirnames if not (directory_path / name).is_symlink()
        ]
        for name in filenames:
            if not _is_experimental_name(name):
                continue
            candidate = directory_path / name
            if candidate.is_symlink() or not candidate.is_file():
                raise CampaignCleanupError(
                    f"experimental target is not a regular file: {candidate}"
                )
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise CampaignCleanupError(
                    f"experimental target escapes cleanup root: {candidate}"
                ) from exc
            files.append(resolved)
    return sorted(files, key=lambda value: value.as_posix().casefold())


def _replace_file_atomically(source: Path, destination: Path) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix="itb_observatory_restore_",
            suffix=".tmp",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def cleanup_campaign(
    *,
    install_dir: Path,
    bridge_dir: Path,
    baseline_modloader: Path,
    expected_baseline_sha256: str,
    allow_cleanup: bool = False,
) -> dict[str, object]:
    install_root = _root(install_dir, "install directory")
    bridge_root = _root(bridge_dir, "bridge directory")
    scripts_root = _root(install_root / "scripts", "install scripts directory")
    if install_root == bridge_root:
        raise CampaignCleanupError("install and bridge directories must be disjoint")
    try:
        bridge_root.relative_to(install_root)
    except ValueError:
        pass
    else:
        raise CampaignCleanupError("bridge directory must not be inside the install")
    try:
        install_root.relative_to(bridge_root)
    except ValueError:
        pass
    else:
        raise CampaignCleanupError("install directory must not be inside the bridge")
    _regular_file(install_root / "Breach.exe", "Breach executable")
    installed_modloader = _regular_file(
        scripts_root / "modloader.lua", "installed modloader"
    )
    baseline = _regular_file(baseline_modloader, "baseline modloader")
    for active_root in (scripts_root, bridge_root):
        try:
            baseline.relative_to(active_root)
        except ValueError:
            continue
        raise CampaignCleanupError("baseline modloader must be outside active roots")

    expected_hash = expected_baseline_sha256.lower()
    if len(expected_hash) != 64 or any(
        c not in "0123456789abcdef" for c in expected_hash
    ):
        raise CampaignCleanupError("expected baseline SHA-256 is malformed")
    baseline_hash = _sha256(baseline)
    if baseline_hash != expected_hash:
        raise CampaignCleanupError(
            f"baseline modloader hash mismatch: {baseline_hash} != {expected_hash}"
        )

    install_targets = _experimental_files(scripts_root)
    bridge_targets = _experimental_files(bridge_root)
    report: dict[str, object] = {
        "schema_version": 1,
        "kind": "observatory_campaign_cleanup_result",
        "applied": False,
        "install_removed_file_count": len(install_targets),
        "install_removed_byte_count": sum(
            path.stat().st_size for path in install_targets
        ),
        "bridge_removed_file_count": len(bridge_targets),
        "bridge_removed_byte_count": sum(
            path.stat().st_size for path in bridge_targets
        ),
        "baseline_modloader_sha256": baseline_hash,
    }
    if not allow_cleanup:
        return report

    _replace_file_atomically(baseline, installed_modloader)
    if _sha256(installed_modloader) != baseline_hash:
        raise CampaignCleanupError("installed modloader failed post-copy verification")
    for target in install_targets:
        target.unlink()
    for target in bridge_targets:
        target.unlink()

    remaining_install = _experimental_files(scripts_root)
    remaining_bridge = _experimental_files(bridge_root)
    report.update(
        {
            "applied": True,
            "installed_modloader_sha256": _sha256(installed_modloader),
            "remaining_install_experimental_file_count": len(remaining_install),
            "remaining_bridge_experimental_file_count": len(remaining_bridge),
        }
    )
    if remaining_install or remaining_bridge:
        raise CampaignCleanupError("experimental files remain after cleanup")
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--bridge-dir", type=Path, required=True)
    parser.add_argument("--baseline-modloader", type=Path, required=True)
    parser.add_argument("--expected-baseline-sha256", required=True)
    parser.add_argument(
        "--allow-cleanup",
        action="store_true",
        help="restore the loader and remove the reported experimental files",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = cleanup_campaign(
        install_dir=args.install_dir,
        bridge_dir=args.bridge_dir,
        baseline_modloader=args.baseline_modloader,
        expected_baseline_sha256=args.expected_baseline_sha256,
        allow_cleanup=args.allow_cleanup,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
