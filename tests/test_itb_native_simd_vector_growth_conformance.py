"""Independent fixed old4 growth-to-six conformance tests."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_simd_vector_growth_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE_PATH = PROGRAMS / (PREFIX + "native_simd_vector_growth_conformance.json")


def word(buffer, offset):
    return int.from_bytes(buffer[offset : offset + 4], "little")


@pytest.mark.parametrize("vector", c.vectors())
def test_growth_snapshot_capacity_six_parent_abi_xmm_and_retained_bytes(vector):
    fixture = c._fixture(vector)
    before = copy.deepcopy((vector, fixture))
    result = c._packet(vector, fixture)
    a = vector["vector_alignment"]
    s = fixture["registers"]["esp"]
    begin = 0x06002800 + a
    snapshot = fixture["old"][0x800 + a : 0x820 + a]
    new = bytearray(fixture["new"])
    new[0x800 + a : 0x820 + a] = snapshot
    assert result["new"] == bytes(new)
    for name in ("old", "error", "feature_page"):
        assert result[name] == fixture[name]
    obj = bytearray(fixture["object"])
    for offset, value in ((0, begin), (4, begin + 32), (8, begin + 48)):
        obj[0xFD0 + offset : 0xFD4 + offset] = value.to_bytes(4, "little")
    assert result["object"] == bytes(obj)
    assert result["registers"] == dict(
        fixture["registers"], eax=begin + 32, ecx=0xA0000001, edx=0xB0000001, esp=s + 8
    )
    assert result["resize_entry"] == dict(
        fixture["registers"],
        eax=6,
        ebx=0x1FFFFFFD,
        ecx=0x0FFFFFD0,
        edx=6,
        esi=0x0FFFFFD0,
        edi=4,
        esp=s - 20,
    )
    assert result["xmm"] == dict(
        fixture["xmm"],
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:], "little"),
    )
    # Last arithmetic is the descendant ADD ESP,12 at G-52; caller POPs preserve it.
    lhs = s - 52
    value = (lhs + 12) & 0xFFFFFFFF
    expected_flags = 4 if (value & 255).bit_count() % 2 == 0 else 0
    expected_flags |= 0x10 if ((lhs & 15) + 12) > 15 else 0
    assert result["flags"] == expected_flags and result["flag_mask"] == 0x8D5
    assert result["df"] == 0 and result["endpoint"] == 0x04000000
    prefix = [
        ("write", s - 4, fixture["registers"]["esi"]),
        ("write", s - 8, fixture["registers"]["edi"]),
        ("read", 0x0FFFFFD8, 0x06003800 + a + 32),
        ("read", 0x0FFFFFD4, 0x06003800 + a + 32),
        ("read", 0x0FFFFFD0, 0x06003800 + a),
        ("write", s - 12, fixture["registers"]["ebx"]),
        ("write", s - 16, 6),
        ("write", s - 20, 0x006EB66E),
    ]
    assert result["events"][:8] == [
        dict(access=k, address=address, width=4, value=value)
        for k, address, value in prefix
    ]
    assert result["events"][-4:] == [
        dict(access="read", address=address, width=4, value=value)
        for address, value in (
            (s - 12, fixture["registers"]["ebx"]),
            (s - 8, fixture["registers"]["edi"]),
            (s - 4, fixture["registers"]["esi"]),
            (s, 0x04000000),
        )
    ]
    assert any(
        e == dict(access="read", address=s - 20, width=4, value=0x006EB66E)
        for e in result["events"]
    )
    wide = [e for e in result["events"] if e["width"] == 8]
    assert [(e["access"], e["address"], e["value"]) for e in wide] == [
        (access, base + offset, int.from_bytes(snapshot[offset : offset + 8], "little"))
        for access, base in (("read", 0x06003800 + a), ("write", begin))
        for offset in (0, 8, 16, 24)
    ]
    at = s - c.STACK
    assert result["stack"][: at - 96] == fixture["stack"][: at - 96]
    assert result["stack"][at:] == fixture["stack"][at:]
    assert word(result["stack"], at - 4) == fixture["registers"]["esi"]
    assert word(result["stack"], at - 8) == fixture["registers"]["edi"]
    assert word(result["stack"], at - 12) == fixture["registers"]["ebx"]
    assert result["allocation_request"] == dict(
        continuation=0x789463, handle=0x12345678, flags=0, bytes=48
    )
    assert result["free_request"] == dict(
        continuation=0x789172, handle=0x12345678, flags=0, pointer=0x06003800 + a
    )
    result["registers"]["ebx"] ^= 1
    result["xmm"]["xmm7"] ^= 1
    result["resize_entry"]["edx"] ^= 1
    result["events"][0]["value"] ^= 1
    assert (vector, fixture) == before


def test_fixed_matrix_and_frame():
    assert c.vectors() == [
        dict(profile=p, vector_alignment=a, stack_alignment=s)
        for p in (0, 1)
        for a in (0, 7, 31)
        for s in (0, 1, 7, 15)
    ]
    assert len(c.SOURCE_PINS) == 11
    frame = c.frame_join(0x3000100F)
    assert frame["resize_entry"] == 0x30000FFB
    assert frame["heap_allocation_entry"] == 0x30000FAF
    assert frame["heap_free_entry"] == 0x30000FB7
    assert frame["copy_entry"] == 0x30000FD7


@pytest.mark.parametrize(
    "kind",
    [
        "registers",
        "xmm",
        "new",
        "old",
        "object",
        "error",
        "feature_page",
        "stack",
        "events",
        "endpoint",
        "flags",
        "df",
        "geometry",
        "copy_entry",
        "allocation_request",
        "free_request",
        "extra_metadata",
        "coordinated_stack_events",
        "flag_mask",
    ],
)
def test_independent_resize_join_rejects_component_corruption(monkeypatch, kind):
    original = c.resize._expected
    calls = 0

    def changed(*args, **kwargs):
        nonlocal calls
        calls += 1
        packet = original(*args, **kwargs)
        if calls == 1:
            if kind == "registers":
                packet[kind]["ebx"] ^= 1
            elif kind == "xmm":
                packet[kind]["xmm7"] ^= 1
            elif kind == "events":
                packet[kind][0]["value"] ^= 1
            elif kind == "geometry":
                packet[kind]["new_begin"] ^= 1
            elif kind == "copy_entry":
                packet[kind]["esp"] ^= 4
            elif kind == "allocation_request":
                packet[kind]["bytes"] ^= 1
            elif kind == "free_request":
                packet[kind]["pointer"] ^= 1
            elif kind == "extra_metadata":
                packet["ownership_claim"] = True
            elif kind == "coordinated_stack_events":
                packet["events"][0]["value"] ^= 1
                at = packet["events"][0]["address"] - c.STACK
                data = bytearray(packet["stack"])
                data[at] ^= 1
                packet["stack"] = bytes(data)
            elif kind in ("new", "old", "object", "error", "feature_page", "stack"):
                data = bytearray(packet[kind])
                data[0] ^= 1
                packet[kind] = bytes(data)
            else:
                packet[kind] ^= 1
        return packet

    monkeypatch.setattr(c.resize, "_expected", changed)
    with pytest.raises(c.ConformanceError, match="SIMD growth resize join differs"):
        c._packet(c.vectors()[0], c._fixture(c.vectors()[0]))


@pytest.mark.parametrize(
    "kind",
    [
        "vector_extra",
        "vector_bool",
        "alignment",
        "profile",
        "stack_alignment",
        "fixture_extra",
        "fixture_missing",
        "gpr_extra",
        "gpr_bool",
        "xmm_missing",
        "xmm_bool",
        "xmm_overflow",
        "stack_mutable",
        "new_short",
        "old_short",
        "object_short",
        "error_short",
        "feature_short",
        "feature_bit",
        "object_identity",
        "frame_low",
        "frame_high",
        "return_argument",
        "old_begin",
        "old_end",
        "old_cap",
    ],
)
def test_strict_installed_fixed_domain(kind):
    vector = c.vectors()[0]
    fixture = c._fixture(vector)
    if kind == "vector_extra":
        vector["requested"] = 7
    elif kind == "vector_bool":
        vector["profile"] = False
    elif kind in ("alignment", "profile", "stack_alignment"):
        vector[{"alignment": "vector_alignment"}.get(kind, kind)] = 2
    elif kind == "fixture_extra":
        fixture["ownership"] = 1
    elif kind == "fixture_missing":
        del fixture["error"]
    elif kind == "gpr_extra":
        fixture["registers"]["eflags"] = 0x246
    elif kind == "gpr_bool":
        fixture["registers"]["eax"] = True
    elif kind == "xmm_missing":
        del fixture["xmm"]["xmm7"]
    elif kind == "xmm_bool":
        fixture["xmm"]["xmm7"] = False
    elif kind == "xmm_overflow":
        fixture["xmm"]["xmm7"] = 2**128
    elif kind == "stack_mutable":
        fixture["stack"] = bytearray(fixture["stack"])
    elif kind.endswith("_short"):
        name = (
            "feature_page" if kind == "feature_short" else kind.removesuffix("_short")
        )
        fixture[name] = fixture[name][:-1]
    elif kind == "feature_bit":
        buffer = bytearray(fixture["feature_page"])
        buffer[0xF30] ^= 2
        fixture["feature_page"] = bytes(buffer)
    elif kind == "object_identity":
        fixture["registers"]["ecx"] += 4
    elif kind.startswith("frame_"):
        fixture["registers"]["esp"] = 0x30000040 if kind == "frame_low" else 0x30001FF9
    elif kind.endswith("_argument"):
        buffer = bytearray(fixture["stack"])
        buffer[0x1000 + (4 if kind == "request_argument" else 0)] ^= 1
        fixture["stack"] = bytes(buffer)
    else:
        buffer = bytearray(fixture["object"])
        buffer[0xFD0 + {"old_begin": 0, "old_end": 4, "old_cap": 8}[kind]] ^= 1
        fixture["object"] = bytes(buffer)
    with pytest.raises(c.ConformanceError):
        c._packet(vector, fixture)


@pytest.mark.parametrize("discarded", [0, 1, 6, 0x93939393, 0xFFFFFFFF])
def test_ignored_caller_argument_is_preserved(discarded):
    vector = c.vectors()[0]
    fixture = c._fixture(vector)
    stack = bytearray(fixture["stack"])
    at = fixture["registers"]["esp"] - c.STACK + 4
    stack[at : at + 4] = discarded.to_bytes(4, "little")
    fixture["stack"] = bytes(stack)
    result = c._packet(vector, fixture)
    assert result["stack"][at : at + 4] == fixture["stack"][at : at + 4]
    assert not any(
        event["address"] == fixture["registers"]["esp"] + 4
        for event in result["events"]
    )


def _source_paths():
    names = {
        "owner": "native_vector_resize_semantics",
        "small_copy": "native_small_copy_semantics",
        "deallocation_conformance": "native_vector_deallocation_conformance_joined",
        "small_resize": "native_small_vector_resize_conformance",
        "short_simd_semantics": "native_short_simd_copy_semantics",
        "short_simd_conformance": "native_short_simd_copy_conformance",
        "simd_resize": "native_simd_vector_resize_conformance",
        "growth": "native_lua_vector_growth_semantics",
    }
    return {
        key: PROGRAMS / (PREFIX + names.get(key, "native_vector_" + key) + ".json")
        for key in c.SOURCE_PINS
    }


def _sources():
    return {key: json.loads(path.read_bytes()) for key, path in _source_paths().items()}


def test_pinned_sources_are_exact_and_opaque_partition_bounded():
    sources = _sources()
    identities = c._preflight(sources)
    assert set(identities) == set(c.SOURCE_PINS)
    assert (
        c.SOURCE_PINS["short_simd_conformance"][1]
        == "67e3ceefdb4b00bfab28653b34634f51a1ab5310fd27b2f2e4bdd75324de5865"
    )
    sources["small_resize"]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c._preflight(sources)


@pytest.fixture(scope="module")
def native_code():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private reviewed runtime")
    data, image, digest = c._load_executable(Path(executable))
    assert digest == c.EXE_SHA256
    sources = _sources()
    c._preflight(sources)
    return c._load_code(data, image, sources)


def _check_native_exact24_corpus(native_code, vector):
    fixture = c._fixture(vector)
    before = copy.deepcopy(fixture)
    expected = c._packet(vector, fixture)
    result = c._run_case(*native_code, vector, fixture=fixture)
    assert (
        result["registers"] == expected["registers"]
        and result["xmm"] == expected["xmm"]
    )
    assert result["events_sha256"] == c._canonical_sha256(expected["events"])
    assert result["new_sha256"] == hashlib.sha256(expected["new"]).hexdigest()
    assert [item["role"] for item in result["summaries"]] == ["allocate", "free"]
    assert fixture == before


def _check_native_intended_controls(native_code, kind):
    with pytest.raises(c.ConformanceError, match="^" + c.CONTROLS[kind] + "$"):
        c._run_case(*native_code, c.vectors()[-1], kind)


def _isolated_native(action, *arguments):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and private reviewed runtime")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b"" and result.stderr == b""


@pytest.mark.parametrize(
    "vector",
    [
        dict(profile=p, vector_alignment=a, stack_alignment=s)
        for p in (0, 1)
        for a in (0, 7, 31)
        for s in (0, 1, 7, 15)
    ],
)
def test_native_exact24_corpus(vector):
    _isolated_native(
        "corpus",
        vector["profile"],
        vector["vector_alignment"],
        vector["stack_alignment"],
    )


@pytest.mark.parametrize("kind", ["ancestor", "payload", "xmm", "request", "free"])
def test_native_intended_controls(kind):
    _isolated_native("negative", kind)


def test_receipt_encoding_structure_and_bounded_summary():
    raw = EVIDENCE_PATH.read_bytes()
    evidence = json.loads(raw)
    assert c.SEALED_SHA256 != "PENDING"
    assert raw == c.encode_conformance(evidence).encode("utf-8") and b"\r\n" not in raw
    assert c._canonical_sha256(evidence) == c.SEALED_SHA256
    assert (
        c.validate_structure(evidence, _sources())["status"] == "structurally_verified"
    )
    assert evidence["vectors"] == c.vectors() and len(evidence["vectors"]) == 24
    assert evidence["source_receipts"] == c._preflight(_sources())
    summary = evidence["summary"]
    assert {
        key: summary[key]
        for key in (
            "cases",
            "allocation_api_summaries",
            "free_api_summaries",
            "copied_bytes",
            "allocated_bytes",
            "accounting_promotions",
        )
    } == {
        "cases": 24,
        "allocation_api_summaries": 24,
        "free_api_summaries": 24,
        "copied_bytes": 768,
        "allocated_bytes": 1152,
        "accounting_promotions": 0,
    }
    assert evidence["negative_controls"] == [
        dict(kind=kind, rejected=True) for kind in c.CONTROLS
    ]
    points = {point["rva"] for point in evidence["body"]["points"]}
    assert set(evidence["executed_rvas"]) <= points
    assert {
        "0x0036e5b1",
        "0x0036ea60",
        "0x0036ea64",
        "0x0036ea69",
        "0x0036ea6d",
    } <= set(evidence["executed_rvas"])


@pytest.mark.parametrize(
    "kind",
    [
        "summary",
        "vector",
        "observation",
        "control",
        "coverage",
        "point",
        "range",
        "pin",
        "scope",
    ],
)
def test_receipt_tampering_rejected(kind):
    evidence = json.loads(EVIDENCE_PATH.read_bytes())
    if kind == "summary":
        evidence["summary"]["copied_bytes"] += 1
    elif kind == "vector":
        evidence["vectors"][0]["vector_alignment"] = 1
    elif kind == "observation":
        evidence["observations_sha256"] = "0" * 64
    elif kind == "control":
        evidence["negative_controls"][0]["rejected"] = False
    elif kind == "coverage":
        evidence["executed_rvas"].pop()
    elif kind == "point":
        evidence["body"]["points"][0]["size"] += 1
    elif kind == "range":
        evidence["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "pin":
        evidence["source_receipts"] = {}
    else:
        evidence["scope"]["claim"] += " actual heap ownership"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, _sources())


@pytest.mark.parametrize(
    "key", ["short_simd_semantics", "short_simd_conformance", "small_resize"]
)
def test_ancestor_source_tampering_rejected(key):
    evidence = json.loads(EVIDENCE_PATH.read_bytes())
    sources = _sources()
    sources[key]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize("command", ["build", "verify", "verify-structure"])
def test_exact_cli_commands(command):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and private reviewed runtime")
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_simd_vector_growth_conformance.py"),
        command,
    ]
    paths = _source_paths()
    assert set(paths) == set(c.SOURCE_PINS) and len(paths) == 11
    for key, path in paths.items():
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        args += ["--executable", str(Path(executable))]
    if command != "build":
        args += ["--evidence", str(EVIDENCE_PATH)]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    if command == "build":
        assert result.stdout == EVIDENCE_PATH.read_bytes()
    else:
        verified = json.loads(result.stdout)
        assert verified["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert verified["evidence_sha256"] == c.SEALED_SHA256
        assert result.stdout == c.encode_conformance(verified).encode("utf-8")


if __name__ == "__main__":
    action, *arguments = sys.argv[1:]
    code = native_code.__wrapped__()
    if action == "corpus":
        profile, alignment, stack_alignment = map(int, arguments)
        _check_native_exact24_corpus(
            code,
            dict(
                profile=profile,
                vector_alignment=alignment,
                stack_alignment=stack_alignment,
            ),
        )
    elif action == "negative":
        _check_native_intended_controls(code, arguments[0])
    else:
        raise ValueError("unknown isolated native action")
