#!/bin/bash
# Run the full regression suite: Rust corpus + Python failure_db replay.
# Sets DYLD_FRAMEWORK_PATH so pyo3 tests can find libpython at runtime.

set -e

cd "$(dirname "$0")/.."
REPO=$(pwd)

# Find Python framework path dynamically
PYTHON_PREFIX=$(python3 -c 'import sys; print(sys.prefix)')
FRAMEWORK_DIR=$(dirname $(dirname $(dirname "$PYTHON_PREFIX")))

echo "=== Rust regression (cargo test --no-default-features) ==="
cd "$REPO/rust_solver"
DYLD_FRAMEWORK_PATH="$FRAMEWORK_DIR" \
    CARGO_INCREMENTAL=0 \
    cargo test --release --test regression --no-default-features -- --nocapture

echo ""
echo "=== Python regression (pytest -m regression) ==="
cd "$REPO"
python3 -m pytest tests/test_regression_corpus.py -v -m regression

echo ""
echo "=== All regression tests passed ==="
