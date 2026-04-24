"""PR3 — Layer 2 agent fallback validator + rejection store.

Covers the contract that mediates the harness's Explore-agent dispatch:

  - validate_agent_response enforces the strict JSON schema (path
    resolves, lines exist, target_language=rust, confidence enum,
    fix_snippet completeness).
  - apply_agent_response writes status=agent_proposed markdown that
    Layer 4 (PR5) will eventually consume.
  - record_rejection / is_rejected dedupe by
    (combined_diff_signature × sim_version × proposed_fix_sig).
  - diagnose() consults rejections before rules.yaml; --force overrides.

Marked @pytest.mark.regression so they run with the rest of the corpus
suite (pytest -m regression).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.solver.diagnosis import (
    REPO_ROOT,
    apply_agent_response,
    build_agent_prompt,
    combined_diff_signature,
    diagnose,
    fix_signature,
    is_rejected,
    record_rejection,
    reject,
    validate_agent_response,
)


@pytest.fixture(autouse=True)
def _isolated_rejections_path(monkeypatch, tmp_path):
    """Every test gets a fresh, empty rejections.jsonl.

    Without this, tests that touch record_rejection / reject pollute the
    real diagnoses/rejections.jsonl AND leak rejections into later tests
    in the same session — diagnose() would short-circuit unexpectedly.
    """
    monkeypatch.setattr(
        "src.solver.diagnosis.REJECTIONS_PATH",
        tmp_path / "isolated_rejections.jsonl",
    )


# ---------------------------------------------------------------------------
# Shared synthetic fixture: a sim_v10 hp diff that no seed rule matches.
# ---------------------------------------------------------------------------


def _frozen_status_failure() -> tuple[dict, dict]:
    """A status.frozen unit_diff that none of the four seed rules cover."""
    failure = {
        "id": "fixture_pr3_frozen",
        "run_id": "test_pr3",
        "mission": 0,
        "turn": 1,
        "action_index": 0,
        "simulator_version": 10,
        "category": "status",
        "diff": {
            "unit_diffs": [
                {
                    "uid": 99,
                    "type": "Hornet1",
                    "field": "status.frozen",
                    "predicted": True,
                    "actual": False,
                }
            ],
            "tile_diffs": [],
            "scalar_diffs": [],
            "total_count": 1,
        },
    }
    action = {
        "mech_uid": 0,
        "mech_type": "PunchMech",
        "weapon": "Titan Fist",
        "weapon_id": "Prime_Punchmech",
        "target": [3, 3],
        "description": "PunchMech, fire Titan Fist at E5",
    }
    return failure, action


# ---------------------------------------------------------------------------
# Validator: structural + semantic checks.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_validate_rejects_python_target_language():
    """Python sim was deleted — proposals targeting any Python file
    are auto-rejected via the target_language check."""
    bad = {
        "target_language": "python",
        "root_cause": "Some hypothetical Python fix",
        "suspect_files": [
            {"path": "src/solver/solver.py", "lines": [10]}
        ],
        "fix_snippet": {"before": "x", "after": "y"},
        "confidence": "high",
        "verification_plan": [],
        "open_questions": [],
    }
    response, errors = validate_agent_response(bad)
    assert response is None
    assert any("target_language" in e for e in errors)
    # Validator no longer mentions simulate.py by name (deleted in PR-D);
    # the message now points at the Rust-only policy.
    assert any("Python sim was deleted" in e or "rust_solver" in e for e in errors)


@pytest.mark.regression
def test_validate_rejects_nonexistent_path():
    bad = {
        "target_language": "rust",
        "root_cause": "?",
        "suspect_files": [
            {"path": "rust_solver/src/does_not_exist.rs", "lines": [1]}
        ],
        "fix_snippet": {"before": "x", "after": "y"},
        "confidence": "high",
        "verification_plan": [],
        "open_questions": [],
    }
    response, errors = validate_agent_response(bad)
    assert response is None
    assert any("does not exist" in e for e in errors)


@pytest.mark.regression
def test_validate_rejects_out_of_range_line():
    """rust_solver/src/lib.rs is short — line 999999 must fail."""
    bad = {
        "target_language": "rust",
        "root_cause": "?",
        "suspect_files": [
            {"path": "rust_solver/src/lib.rs", "lines": [999_999]}
        ],
        "fix_snippet": {"before": "x", "after": "y"},
        "confidence": "high",
        "verification_plan": [],
        "open_questions": [],
    }
    response, errors = validate_agent_response(bad)
    assert response is None
    assert any("out of range" in e for e in errors)


@pytest.mark.regression
def test_validate_rejects_missing_fix_halves():
    bad = {
        "target_language": "rust",
        "root_cause": "?",
        "suspect_files": [
            {"path": "rust_solver/src/lib.rs", "lines": [1]}
        ],
        "fix_snippet": {"before": "x", "after": ""},
        "confidence": "high",
        "verification_plan": [],
        "open_questions": [],
    }
    response, errors = validate_agent_response(bad)
    assert response is None
    assert any("before" in e and "after" in e for e in errors)


@pytest.mark.regression
def test_validate_rejects_bad_confidence_enum():
    bad = {
        "target_language": "rust",
        "root_cause": "?",
        "suspect_files": [
            {"path": "rust_solver/src/lib.rs", "lines": [1]}
        ],
        "fix_snippet": {"before": "x", "after": "y"},
        "confidence": "very-high",
        "verification_plan": [],
        "open_questions": [],
    }
    response, errors = validate_agent_response(bad)
    assert response is None
    assert any("confidence" in e for e in errors)


@pytest.mark.regression
def test_validate_accepts_well_formed_response():
    good = {
        "target_language": "rust",
        "root_cause": "Hornet's frozen flag persists across the unit-load pass.",
        "suspect_files": [
            {"path": "rust_solver/src/lib.rs", "lines": [1, 5]}
        ],
        "fix_snippet": {
            "before": "// stale frozen flag survives load",
            "after": "// clear frozen on first damage",
        },
        "confidence": "medium",
        "verification_plan": ["Run regression", "Replay turn"],
        "open_questions": ["Does this affect Massive units?"],
    }
    response, errors = validate_agent_response(good)
    assert errors == []
    assert response is not None
    assert response.target_language == "rust"
    assert response.confidence == "medium"
    assert response.suspect_files[0]["path"] == "rust_solver/src/lib.rs"
    assert response.open_questions == ["Does this affect Massive units?"]


@pytest.mark.regression
def test_validate_strips_markdown_fences():
    """Agents tend to wrap JSON in ```json fences; the validator tolerates it."""
    payload = (
        "```json\n"
        + json.dumps(
            {
                "target_language": "rust",
                "root_cause": "?",
                "suspect_files": [
                    {"path": "rust_solver/src/lib.rs", "lines": [1]}
                ],
                "fix_snippet": {"before": "a", "after": "b"},
                "confidence": "low",
                "verification_plan": [],
                "open_questions": [],
            }
        )
        + "\n```"
    )
    response, errors = validate_agent_response(payload)
    assert errors == []
    assert response is not None


@pytest.mark.regression
def test_validate_extracts_last_json_from_prose_wrapped_response():
    """Surfaced on the live integration test (PR6): agents reason aloud,
    return a tentative JSON, then a "wait, let me reconsider" paragraph
    followed by the FINAL JSON. The validator must pick the last block.
    """
    early = json.dumps({
        "target_language": "rust", "root_cause": "first guess",
        "suspect_files": [{"path": "rust_solver/src/lib.rs", "lines": [1]}],
        "fix_snippet": {"before": "a", "after": "b"},
        "confidence": "low", "verification_plan": [], "open_questions": [],
    })
    final = json.dumps({
        "target_language": "rust", "root_cause": "FINAL answer",
        "suspect_files": [{"path": "rust_solver/src/lib.rs", "lines": [1]}],
        "fix_snippet": {"before": "x", "after": "y"},
        "confidence": "high", "verification_plan": ["regression"],
        "open_questions": [],
    })
    payload = (
        "Now I'll think out loud.\n\n"
        f"```json\n{early}\n```\n\n"
        "Wait, that's wrong. Let me reconsider...\n\n"
        f"```json\n{final}\n```\n"
    )
    response, errors = validate_agent_response(payload)
    assert errors == [], errors
    assert response is not None
    assert response.root_cause == "FINAL answer"
    assert response.confidence == "high"


@pytest.mark.regression
def test_validate_skips_braces_inside_strings():
    """Brace-balancer must ignore '{' and '}' inside JSON string literals
    (e.g. Rust code in fix_snippet.before contains them constantly)."""
    payload = json.dumps({
        "target_language": "rust", "root_cause": "?",
        "suspect_files": [{"path": "rust_solver/src/lib.rs", "lines": [1]}],
        "fix_snippet": {
            "before": "fn x() { let y = 1; }",
            "after": "fn x() { let y = 2; }",
        },
        "confidence": "high", "verification_plan": [], "open_questions": [],
    })
    response, errors = validate_agent_response(f"prose\n{payload}\nmore prose")
    assert errors == [], errors
    assert response is not None
    assert "let y = 2" in response.fix_snippet["after"]


@pytest.mark.regression
def test_validate_rejects_malformed_json():
    response, errors = validate_agent_response("not actually json {")
    assert response is None
    assert any("JSON" in e for e in errors)


# ---------------------------------------------------------------------------
# apply_agent_response writes status=agent_proposed markdown.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_apply_agent_response_writes_agent_proposed_markdown(tmp_path):
    failure, action = _frozen_status_failure()
    payload = json.dumps(
        {
            "target_language": "rust",
            "root_cause": (
                "frozen status not cleared on first damage in apply_damage_core"
            ),
            "suspect_files": [
                {"path": "rust_solver/src/lib.rs", "lines": [1, 50]}
            ],
            "fix_snippet": {
                "before": "// pre-fix",
                "after": "// post-fix: clear frozen here",
            },
            "confidence": "medium",
            "verification_plan": ["Run regression"],
            "open_questions": [],
        }
    )
    out_dir = tmp_path / "diag"
    result = apply_agent_response(
        failure["id"], payload, out_dir=out_dir,
        failure=failure, action=action,
    )
    assert result["status"] == "agent_proposed"
    assert result["confidence"] == "medium"

    md_path = out_dir / f"{failure['id']}.md"
    assert md_path.exists()
    text = md_path.read_text()
    assert "status: agent_proposed" in text
    assert "agent_invoked: true" in text
    assert "rust_solver/src/lib.rs" in text
    assert "// post-fix: clear frozen here" in text
    assert "reject_diagnosis" in text  # cleanup hint


@pytest.mark.regression
def test_apply_agent_response_returns_errors_on_invalid_payload(tmp_path):
    failure, action = _frozen_status_failure()
    bad_payload = json.dumps(
        {
            "target_language": "python",
            "root_cause": "?",
            "suspect_files": [{"path": "src/solver/solver.py", "lines": [10]}],
            "fix_snippet": {"before": "x", "after": "y"},
            "confidence": "high",
            "verification_plan": [],
            "open_questions": [],
        }
    )
    result = apply_agent_response(
        failure["id"], bad_payload, out_dir=tmp_path / "diag",
        failure=failure, action=action,
    )
    assert result["status"] == "ERROR"
    assert "errors" in result
    assert any("target_language" in e for e in result["errors"])
    # No markdown written on failed validation.
    assert not (tmp_path / "diag" / f"{failure['id']}.md").exists()


# ---------------------------------------------------------------------------
# Rejection store: round-trip + dedup.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_record_and_is_rejected_round_trip():
    """is_rejected fires for the same diff_signature × sim_version pair."""
    failure, _ = _frozen_status_failure()
    diff = failure["diff"]
    sim_v = failure["simulator_version"]

    assert is_rejected(diff, sim_v) is None

    record_rejection(
        failure_id=failure["id"],
        reason="wrong direction; frozen actually cleared by fire damage",
        diff=diff,
        sim_version=sim_v,
        proposed_fix={"before": "a", "after": "b"},
    )

    rec = is_rejected(diff, sim_v)
    assert rec is not None
    assert rec["reason"].startswith("wrong direction")

    # Same diff, different sim version → different cache bucket.
    assert is_rejected(diff, sim_version=11) is None


@pytest.mark.regression
def test_record_rejection_dedupes_on_same_fix_signature(tmp_path):
    failure, _ = _frozen_status_failure()
    diff = failure["diff"]
    sim_v = failure["simulator_version"]
    fix = {"before": "x", "after": "y"}

    record_rejection(failure["id"], "first take", diff, sim_v, proposed_fix=fix)
    record_rejection(failure["id"], "second take", diff, sim_v, proposed_fix=fix)

    text = (tmp_path / "isolated_rejections.jsonl").read_text()
    assert text.count("\n") == 1, "duplicate rejection of same fix should dedupe"
    assert "first take" in text
    assert "second take" not in text


@pytest.mark.regression
def test_combined_diff_signature_is_order_insensitive():
    a = {
        "unit_diffs": [
            {"uid": 1, "type": "WallMech", "field": "active",
             "predicted": False, "actual": True},
            {"uid": 2, "type": "Hornet", "field": "hp",
             "predicted": 1, "actual": 2},
        ],
        "tile_diffs": [],
        "scalar_diffs": [],
    }
    b = {
        "unit_diffs": [a["unit_diffs"][1], a["unit_diffs"][0]],
        "tile_diffs": [],
        "scalar_diffs": [],
    }
    assert combined_diff_signature(a) == combined_diff_signature(b)


@pytest.mark.regression
def test_fix_signature_collapses_whitespace_only_changes():
    assert fix_signature(None) == "none"
    assert fix_signature({}) == "none"
    a = fix_signature({"before": "x", "after": "y"})
    b = fix_signature({"before": "  x  ", "after": "  y  \n"})
    assert a == b


# ---------------------------------------------------------------------------
# diagnose() consults rejections; --force bypasses.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_diagnose_short_circuits_on_prior_rejection(tmp_path):
    failure, action = _frozen_status_failure()
    record_rejection(
        failure_id=failure["id"],
        reason="false positive — frozen unit took damage on enemy turn",
        diff=failure["diff"],
        sim_version=failure["simulator_version"],
    )

    out_dir = tmp_path / "diag"
    result = diagnose(
        failure["id"], out_dir=out_dir,
        failure=failure, action=action, emit_prompt=False,
    )
    assert result["status"] == "rejected"
    assert result.get("rejection") is not None
    assert "agent_prompt" not in result

    text = (out_dir / f"{failure['id']}.md").read_text()
    assert "status: rejected" in text
    assert "false positive" in text


@pytest.mark.regression
def test_diagnose_force_bypasses_rejection(tmp_path):
    failure, action = _frozen_status_failure()
    record_rejection(
        failure["id"], "earlier rejection",
        failure["diff"], failure["simulator_version"],
    )

    result = diagnose(
        failure["id"], force=True, out_dir=tmp_path / "diag",
        failure=failure, action=action, emit_prompt=False,
    )
    # No seed rule matches the frozen-status diff so we fall through to
    # needs_agent — but the key assertion is that the rejection guard was
    # bypassed (status != "rejected").
    assert result["status"] != "rejected"


@pytest.mark.regression
def test_diagnose_emits_agent_prompt_on_needs_agent(tmp_path):
    """needs_agent markdown should embed the agent prompt for harness dispatch."""
    failure, action = _frozen_status_failure()
    out_dir = tmp_path / "diag"
    result = diagnose(
        failure["id"], out_dir=out_dir,
        failure=failure, action=action, emit_prompt=True,
    )
    assert result["status"] == "needs_agent"
    assert "agent_prompt" in result
    assert "diagnose_apply_agent" in result["next_step"]

    text = (out_dir / f"{failure['id']}.md").read_text()
    assert "## Agent prompt" in text
    assert "target_language" in text  # the prompt embeds the JSON schema
    assert "rust_solver" in text


# ---------------------------------------------------------------------------
# build_agent_prompt: shape + content.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_build_agent_prompt_pins_rust_only():
    """The agent prompt must pin Rust as the only simulator and reject
    target_language=python. Python sim was deleted in PR-D."""
    failure, action = _frozen_status_failure()
    prompt = build_agent_prompt(failure, action)
    assert "rust_solver/src/" in prompt
    assert "ONLY simulator" in prompt
    assert "target_language: python" in prompt  # auto-rejection notice
    assert '"target_language": "rust"' in prompt
    # Section 9 category map is included so the agent has somewhere to start.
    assert "DIFF-CATEGORY" in prompt


# ---------------------------------------------------------------------------
# reject() public entry point: round-trip + side effects.
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_reject_writes_rejected_markdown(tmp_path):
    failure, _ = _frozen_status_failure()
    out_dir = tmp_path / "diag"
    result = reject(
        failure["id"],
        reason="false positive; frozen flag is correctly modeled now",
        failure=failure,
        out_dir=out_dir,
    )
    assert result["status"] == "rejected"
    md = out_dir / f"{failure['id']}.md"
    assert md.exists()
    text = md.read_text()
    assert "status: rejected" in text
    assert "false positive" in text
    # Rejection persisted.
    assert (tmp_path / "isolated_rejections.jsonl").exists()


@pytest.mark.regression
def test_reject_requires_non_empty_reason():
    failure, _ = _frozen_status_failure()
    result = reject(failure["id"], reason="   ", failure=failure)
    assert result["status"] == "ERROR"
    assert "reason" in result["error"].lower()
