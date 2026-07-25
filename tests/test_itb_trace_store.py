"""Tests for immutable, identity-gated Observatory trace storage."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from scripts.itb_trace import main as trace_cli
from src.observatory import trace_store
from src.observatory.trace_codec import (
    EVENT_KINDS,
    HARD_MAX_BUNDLE_BYTES,
    TraceBuffer,
    TraceConfig,
    encode_trace,
    hook_coverage_sha256,
    trace_config_sha256,
)
from src.observatory.trace_store import (
    TraceStoreError,
    build_identity_from_inventory,
    list_final_traces,
    load_json_object,
    load_final_trace,
    read_final_trace,
    require_authoritative_build_identity,
    summarize_trace,
    write_final_trace,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


def _inventory() -> dict:
    return {
        "app_id": "590380",
        "platform": "windows",
        "executable": {
            "architecture": "x86",
            "sha256": HASH_A,
        },
        "steam": {
            "app_id": "590380",
            "build_id": "13725832",
            "evidence": {
                "path": "appmanifest_590380.acf",
                "sha256": HASH_B,
            },
            "installed_depots": [
                {
                    "depot_id": "590381",
                    "manifest": "8335438558621014449",
                }
            ],
        },
        "content": {
            "scripts": {"revision_sha256": HASH_B},
            "maps": {"revision_sha256": HASH_C},
        },
    }


def _capture_identity() -> dict:
    config = TraceConfig(enabled=True)
    return {
        "capture_id": "experiment-001",
        "arm_nonce": "0123456789abcdef0123456789abcdef",
        "controller_version": "observatory-test/1",
        "controller_sha256": HASH_D,
        "installed_modloader_sha256": HASH_E,
        "expected_mission_id": "Mission_Test",
        "expected_turn": 2,
        "timeline_fingerprint": HASH_A,
        "master_seed": 12345,
        "region_id": "archive_a",
        "ai_seed_fingerprint": HASH_B,
        "expected_phase": "combat_enemy",
        "config_sha256": trace_config_sha256(config),
        "hook_coverage_sha256": hook_coverage_sha256(_coverage()),
        "activated_at_utc": "2026-07-24T12:00:00Z",
        "expires_at_utc": "2026-07-24T12:05:00Z",
    }


def _checkpoint() -> dict:
    return {
        "seq": 3,
        "reason": "turn_boundary",
        "mission_id": "Mission_Test",
        "turn": 2,
        "phase": "combat_enemy",
        "attempted_calls": {
            kind: 0 for kind in EVENT_KINDS
        },
        "started_at_utc": "2026-07-24T12:00:01Z",
        "completed_at_utc": "2026-07-24T12:00:02Z",
    }


def _coverage() -> list[dict]:
    return [
        {
            "event_kind": kind,
            "target": f"observatory.{kind}",
            "target_kind": "lua_global",
            "status": (
                "installed" if kind == "random_int" else "unavailable"
            ),
            "source_sha256": (
                HASH_C if kind == "random_int" else None
            ),
        }
        for kind in sorted(EVENT_KINDS)
    ]


def _trace() -> dict:
    buffer = TraceBuffer(
        build_identity_from_inventory(_inventory()),
        TraceConfig(enabled=True),
        capture_identity=_capture_identity(),
        checkpoint=_checkpoint(),
        hook_coverage=_coverage(),
    )
    assert buffer.record(
        "random_int",
        phase="combat_enemy",
        mission_id="Mission_Test",
        turn=2,
        context={"call_site": "observatory.random_int"},
        payload={"call_order": 0, "upper_bound": 5, "result": 2},
    )
    return buffer.to_dict()


def _digest(trace: dict) -> str:
    return hashlib.sha256(encode_trace(trace).encode("utf-8")).hexdigest()


def test_inventory_adapter_builds_authoritative_identity():
    identity = build_identity_from_inventory(_inventory())
    assert identity == {
        "platform": "windows",
        "architecture": "x86",
        "architectures": None,
        "executable_sha256": HASH_A,
        "build_id": "13725832",
        "depot_manifest": "8335438558621014449",
        "build_evidence": "local_appmanifest",
        "scripts_revision_sha256": HASH_B,
        "maps_revision_sha256": HASH_C,
    }
    assert require_authoritative_build_identity(identity) == identity


def test_inventory_without_manifest_evidence_is_not_authoritative():
    inventory = _inventory()
    inventory["steam"]["evidence"] = None
    identity = build_identity_from_inventory(inventory)
    assert identity["build_evidence"] == "unavailable"
    with pytest.raises(TraceStoreError, match="requires build/manifest"):
        require_authoritative_build_identity(identity)


def test_inventory_rejects_ambiguous_multi_depot_identity():
    inventory = _inventory()
    inventory["steam"]["installed_depots"].append(
        {
            "depot_id": "590399",
            "manifest": "123456789",
        }
    )
    with pytest.raises(TraceStoreError, match="exactly one"):
        build_identity_from_inventory(inventory)


def test_publish_list_and_exact_load_round_trip(tmp_path: Path):
    trace = _trace()
    final_path = write_final_trace(trace, root=tmp_path)
    (tmp_path / "itb_observatory_trace.json.tmp").write_text(
        "{}",
        encoding="utf-8",
    )
    (tmp_path / "itb_observatory_trace_raw.json").write_text(
        "{}",
        encoding="utf-8",
    )

    assert list_final_traces(tmp_path) == [final_path]
    loaded = load_final_trace(
        "experiment-001",
        3,
        expected_build_identity=trace["build_identity"],
        expected_capture_identity=trace["capture_identity"],
        expected_trace_sha256=_digest(trace),
        root=tmp_path,
    )
    assert loaded == trace
    assert not (final_path.stat().st_mode & stat.S_IWUSR)
    with pytest.raises(TraceStoreError, match="already exists"):
        write_final_trace(trace, root=tmp_path)


@pytest.mark.parametrize("identity_kind", ["build", "capture"])
def test_exact_identity_mismatch_is_rejected(
    tmp_path: Path,
    identity_kind: str,
):
    trace = _trace()
    path = write_final_trace(trace, root=tmp_path)
    expected_build = dict(trace["build_identity"])
    expected_capture = dict(trace["capture_identity"])
    if identity_kind == "build":
        expected_build["executable_sha256"] = HASH_E
    else:
        expected_capture["arm_nonce"] = "f" * 32
    with pytest.raises(TraceStoreError, match=f"{identity_kind} identity"):
        read_final_trace(
            path,
            expected_build_identity=expected_build,
            expected_capture_identity=expected_capture,
            expected_trace_sha256=_digest(trace),
            root=tmp_path,
        )


def test_filename_identity_mismatch_is_rejected(tmp_path: Path):
    trace = _trace()
    original = write_final_trace(trace, root=tmp_path)
    renamed = (
        tmp_path
        / f"itb_observatory_trace_other_3_{_digest(trace)}.json"
    )
    original.rename(renamed)
    with pytest.raises(TraceStoreError, match="filename capture"):
        read_final_trace(
            renamed,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=_digest(trace),
            root=tmp_path,
        )


def test_non_final_or_nested_paths_are_rejected(tmp_path: Path):
    trace = _trace()
    path = write_final_trace(trace, root=tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    moved = nested / path.name
    path.rename(moved)
    with pytest.raises(TraceStoreError, match="direct child"):
        read_final_trace(
            moved,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=_digest(trace),
            root=tmp_path,
        )


def test_changed_during_read_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    trace = _trace()
    path = write_final_trace(trace, root=tmp_path)
    real_fingerprint = trace_store._fingerprint
    calls = 0

    def changing_fingerprint(stat_result):
        nonlocal calls
        calls += 1
        value = real_fingerprint(stat_result)
        if calls == 2:
            return (*value[:-1], value[-1] + 1)
        return value

    monkeypatch.setattr(trace_store, "_fingerprint", changing_fingerprint)
    with pytest.raises(TraceStoreError, match="changed during read"):
        read_final_trace(
            path,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=_digest(trace),
            root=tmp_path,
        )


def test_content_address_rejects_post_publication_mutation(tmp_path: Path):
    trace = _trace()
    path = write_final_trace(trace, root=tmp_path)
    expected_sha256 = _digest(trace)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    raw = bytearray(path.read_bytes())
    raw[-2] = ord(" ")
    path.write_bytes(raw)
    with pytest.raises(TraceStoreError, match="content digest"):
        read_final_trace(
            path,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=expected_sha256,
            root=tmp_path,
        )


def test_publication_failure_never_leaves_a_final_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    trace = _trace()

    def fail_chmod(*_args, **_kwargs):
        raise PermissionError("injected chmod failure")

    monkeypatch.setattr(trace_store.os, "chmod", fail_chmod)
    with pytest.raises(TraceStoreError, match="cannot publish"):
        write_final_trace(trace, root=tmp_path)
    assert list_final_traces(tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_post_publish_fsync_failure_is_cleaned_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    trace = _trace()

    def fail_fsync(_path):
        raise TraceStoreError("injected directory fsync failure")

    monkeypatch.setattr(trace_store, "_fsync_directory", fail_fsync)
    with pytest.raises(TraceStoreError, match="injected directory"):
        write_final_trace(trace, root=tmp_path)
    assert list_final_traces(tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_trace_root_creation_errors_are_normalized(tmp_path: Path):
    root = tmp_path / "not-a-directory"
    root.write_text("occupied", encoding="utf-8")
    with pytest.raises(TraceStoreError, match="cannot create trace root"):
        write_final_trace(_trace(), root=root)


def test_symlink_final_trace_is_rejected(tmp_path: Path):
    trace = _trace()
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / (
        "itb_observatory_trace_experiment-001_3_"
        f"{_digest(trace)}.json"
    )
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(TraceStoreError, match="symlinks"):
        read_final_trace(
            link,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=_digest(trace),
            root=tmp_path,
        )


def test_strict_utf8_and_malformed_bundle_are_rejected(tmp_path: Path):
    trace = _trace()
    invalid_utf8 = b"\xff"
    invalid_utf8_sha = hashlib.sha256(invalid_utf8).hexdigest()
    filename = tmp_path / (
        "itb_observatory_trace_experiment-001_3_"
        f"{invalid_utf8_sha}.json"
    )
    filename.write_bytes(invalid_utf8)
    with pytest.raises(TraceStoreError, match="strict UTF-8"):
        read_final_trace(
            filename,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=invalid_utf8_sha,
            root=tmp_path,
        )

    malformed = b"{}"
    malformed_sha = hashlib.sha256(malformed).hexdigest()
    filename = tmp_path / (
        "itb_observatory_trace_experiment-001_3_"
        f"{malformed_sha}.json"
    )
    filename.write_bytes(malformed)
    with pytest.raises(TraceStoreError, match="invalid final trace"):
        read_final_trace(
            filename,
            expected_build_identity=trace["build_identity"],
            expected_capture_identity=trace["capture_identity"],
            expected_trace_sha256=malformed_sha,
            root=tmp_path,
        )


def test_summary_is_deterministic():
    trace = _trace()
    first = summarize_trace(trace)
    second = summarize_trace(json.loads(json.dumps(trace)))
    assert first == second
    assert first["event_counts"] == {"random_int": 1}
    assert first["hook_status_counts"] == {
        "installed": 1,
        "unavailable": 7,
    }


def test_default_root_is_resolved_at_call_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    artifact_root = tmp_path / "isolated-artifacts"
    monkeypatch.setenv("ITB_ARTIFACT_ROOT", str(artifact_root))
    trace = _trace()
    assert write_final_trace(trace).parent == (
        artifact_root / "observatory" / "traces"
    ).resolve()


def test_cli_requires_trusted_inputs_and_emits_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
):
    trace = _trace()
    path = write_final_trace(trace, root=tmp_path)
    inventory_path = tmp_path / "inventory.json"
    capture_path = tmp_path / "capture.json"
    inventory_path.write_text(
        json.dumps(_inventory()),
        encoding="utf-8",
    )
    capture_path.write_text(
        json.dumps(trace["capture_identity"]),
        encoding="utf-8",
    )
    assert trace_cli(
        [
            "summary",
            str(path),
            "--inventory",
            str(inventory_path),
            "--capture-identity",
            str(capture_path),
            "--trace-sha256",
            _digest(trace),
        ]
    ) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["capture_id"] == "experiment-001"
    assert output["event_counts"] == {"random_int": 1}


@pytest.mark.parametrize(
    "text",
    [
        '{"key":1,"key":2}',
        '{"value":NaN}',
    ],
)
def test_trust_inputs_reject_ambiguous_json(
    tmp_path: Path,
    text: str,
):
    path = tmp_path / "ambiguous.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(TraceStoreError, match="invalid trust input JSON"):
        load_json_object(path, "trust input")


def test_trust_input_size_is_bounded_before_parsing(tmp_path: Path):
    path = tmp_path / "oversized.json"
    with path.open("wb") as handle:
        handle.seek(HARD_MAX_BUNDLE_BYTES)
        handle.write(b"x")
    with pytest.raises(TraceStoreError, match="hard size limit"):
        load_json_object(path, "trust input")
