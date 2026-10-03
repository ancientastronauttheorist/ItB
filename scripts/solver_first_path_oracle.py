#!/usr/bin/env python3
"""Acquire bounded original path-query outputs and compare Rust destinations."""
import argparse
import faulthandler
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, help="Optional directory containing the pinned Unicorn package")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path)
    args = parser.parse_args()
    if args.output.exists() or (args.private_output_dir and args.private_output_dir.exists()):
        parser.error("Outputs are create-only; choose new paths")
    if args.runtime_path:
        sys.path.insert(0, str(args.runtime_path.resolve()))
    faulthandler.disable()
    from src.observatory.solver_first_path_oracle import run
    if args.private_output_dir:
        args.private_output_dir.mkdir(parents=True)
    result = run(args.executable, private_dir=args.private_output_dir)
    with args.output.open("x", encoding="utf-8", newline="\n") as out:
        json.dump(result, out, indent=2, sort_keys=True, allow_nan=False)
        out.write("\n")
    print(json.dumps({k: result[k] for k in ("attempted", "admitted", "failed", "excluded", "rust_projection_attempted")} | {"mismatches": len(result["mismatches"])}))
    return 1 if result["failures"] or result["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
