"""Rust-vs-Python EvalWeights parity test.

Guards against the silent-default hazard: a new field added to
rust_solver/src/evaluate.rs that isn't mirrored in src/solver/evaluate.py
means Python callers (strategist, tests, replay) can't set it, so it
always takes the Rust default — even when the operator wanted it tuned.

The test enforces: every field in the Rust EvalWeights struct must exist
in the Python dataclass. The Python side may have extra fields (e.g.
mech_centrality is Python-only, used by the test primitive).

When this test fails, the remediation is always the same: add the
missing field to src/solver/evaluate.py with the matching Rust default,
and mirror any downstream uses (strategist settings, serialization).
"""
import dataclasses
import pathlib
import re

from src.solver.evaluate import EvalWeights

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RUST_EVAL = REPO_ROOT / "rust_solver" / "src" / "evaluate.rs"


def _rust_eval_weights_fields() -> set[str]:
    text = RUST_EVAL.read_text()
    m = re.search(
        r"pub struct EvalWeights\s*\{(.*?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert m, "couldn't locate `pub struct EvalWeights` in evaluate.rs"
    body = m.group(1)
    return set(re.findall(r"pub\s+(\w+):\s*\w+", body))


def test_python_mirrors_all_rust_eval_weights_fields():
    rust_fields = _rust_eval_weights_fields()
    py_fields = {f.name for f in dataclasses.fields(EvalWeights)}
    missing = rust_fields - py_fields
    assert not missing, (
        f"Rust EvalWeights has fields not mirrored in Python: {sorted(missing)}. "
        f"Add them to src/solver/evaluate.py with matching defaults — else "
        f"Python callers can't set these weights and they silently take Rust defaults."
    )


def test_python_extras_are_known_test_primitives():
    rust_fields = _rust_eval_weights_fields()
    py_fields = {f.name for f in dataclasses.fields(EvalWeights)}
    py_only = py_fields - rust_fields

    # Known Python-only fields (used by the Python test-primitive evaluator,
    # not the live Rust solver). Add to this list only when a field is
    # intentionally Python-local; otherwise it probably belongs in Rust too.
    KNOWN_PY_ONLY = {"mech_centrality"}

    unexpected = py_only - KNOWN_PY_ONLY
    assert not unexpected, (
        f"Python EvalWeights has fields not in Rust and not in the allowlist: "
        f"{sorted(unexpected)}. Either add them to Rust or list them in "
        f"KNOWN_PY_ONLY with a justifying comment."
    )
