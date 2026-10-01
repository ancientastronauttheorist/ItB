"""Caller-installed forward SIMD copy boundaries; native tests are explicit gates.

It makes no factory growth or ownership claim. Native checks run in isolated
subprocesses so Unicorn's handled Windows faults do not flood pytest's reporter.
"""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_short_simd_copy_conformance as c
from src.observatory import native_short_simd_copy_semantics as semantic

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "src/observatory").is_dir()
)
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
REGISTERS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple(f"xmm{i}" for i in range(8))
DATA, STACK, RETURN, FEATURE = 0x06000000, 0x30000000, 0x006EB6A6, 0x00893F30


def _installed(
    alignment=0, profile=0, pattern=0, *, length=32, source=0x3800, destination=0x2800
):
    source += alignment
    destination += alignment
    vector = dict(
        length=length,
        source_offset=source,
        destination_offset=destination,
        alignment=15 * profile,
        df=0,
        feature_word=0x93939393,
    )
    payload = bytearray(bytes((i * 37 + (i >> 7) + 0xB9) & 255 for i in range(0x4000)))
    if pattern == 0:
        snapshot = (bytes(4) + (0x18000001 + profile).to_bytes(4, "little")) * (
            (length + 7) // 8
        )
    elif pattern == 1:
        snapshot = bytes((i * 29 + alignment + profile) & 255 for i in range(length))
    else:
        snapshot = bytes((255 - i * 17 + alignment) & 255 for i in range(length))
    payload[source : source + length] = snapshot[:length]
    entry = STACK + 0x1000 + 15 * profile
    registers = {
        r: (0xFFEEDDCC - i * 0x1010307 + pattern) & 0xFFFFFFFF
        for i, r in enumerate(REGISTERS)
    }
    registers["esp"] = entry
    xmm = {
        name: int.from_bytes(
            bytes((i * 31 + j * 43 + pattern + 5) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    stack = bytearray(bytes((i * 53 + (i >> 5) + 0x6B) & 255 for i in range(0x2000)))
    for offset, value in (
        (0, RETURN),
        (4, DATA + destination),
        (8, DATA + source),
        (12, length),
    ):
        at = entry - STACK + offset
        stack[at : at + 4] = value.to_bytes(4, "little")
    feature = bytearray(b"\x93" * 4096)
    feature[0xF28:0xF2C] = (0xFFFFFFFF if profile else 0x12345678).to_bytes(4, "little")
    feature[0x123:0x127] = b"keep"
    return vector, dict(
        stack_base=STACK,
        payload_base=DATA,
        stack=bytes(stack),
        payload=bytes(payload),
        registers=registers,
        xmm=xmm,
        feature_page=bytes(feature),
        return_address=RETURN,
    )


def _expected(vector, fixture):
    return c._expected(
        vector,
        fixture["registers"],
        fixture["xmm"],
        fixture["stack"],
        fixture["payload"],
        stack_base=fixture["stack_base"],
        payload_base=fixture["payload_base"],
        return_address=fixture["return_address"],
        feature_page=fixture["feature_page"],
    )


def _snapshot(vector, fixture):
    start = vector["source_offset"]
    snapshot = fixture["payload"][start : start + vector["length"]]
    payload = bytearray(fixture["payload"])
    begin = vector["destination_offset"]
    payload[begin : begin + len(snapshot)] = snapshot
    return snapshot, bytes(payload)


def _independent_events32(vector, fixture):
    entry = fixture["registers"]["esp"]
    source = fixture["payload_base"] + vector["source_offset"]
    destination = fixture["payload_base"] + vector["destination_offset"]
    snapshot, _ = _snapshot(vector, fixture)
    events = [
        ("write", entry - 4, 4, fixture["registers"]["edi"]),
        ("write", entry - 8, 4, fixture["registers"]["esi"]),
        ("read", entry + 8, 4, source),
        ("read", entry + 12, 4, 32),
        ("read", entry + 4, 4, destination),
        ("read", FEATURE, 4, 0x93939393),
    ]
    events += [
        (
            access,
            base + offset,
            8,
            int.from_bytes(snapshot[offset : offset + 8], "little"),
        )
        for access, base in (("read", source), ("write", destination))
        for offset in (0, 8, 16, 24)
    ]
    events += [
        ("read", entry + 4, 4, destination),
        ("read", entry - 8, 4, fixture["registers"]["esi"]),
        ("read", entry - 4, 4, fixture["registers"]["edi"]),
        ("read", entry, 4, fixture["return_address"]),
    ]
    return [
        dict(access=access, address=address, width=width, value=value)
        for access, address, width, value in events
    ]


@pytest.mark.parametrize("alignment", [0, 1, 7, 31])
@pytest.mark.parametrize("profile", [0, 1])
@pytest.mark.parametrize("pattern", [0, 1, 2])
def test_relocated_32_snapshot_full_registers_pages_and_order(
    alignment, profile, pattern
):
    vector, fixture = _installed(alignment, profile, pattern)
    before = copy.deepcopy((vector, fixture))
    result = _expected(vector, fixture)
    snapshot, payload = _snapshot(vector, fixture)
    assert result["payload"] == payload
    assert result["source_snapshot"] == snapshot
    assert result["feature_page"] == fixture["feature_page"]
    assert result["feature_page"][0xF28:0xF2C] == fixture["feature_page"][0xF28:0xF2C]
    assert result["registers"] == dict(
        fixture["registers"],
        eax=DATA + vector["destination_offset"],
        ecx=0,
        edx=0,
        esp=fixture["registers"]["esp"] + 4,
    )
    assert result["xmm"] == dict(
        fixture["xmm"],
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:], "little"),
    )
    stack = bytearray(fixture["stack"])
    at = fixture["registers"]["esp"] - STACK
    stack[at - 8 : at - 4] = fixture["registers"]["esi"].to_bytes(4, "little")
    stack[at - 4 : at] = fixture["registers"]["edi"].to_bytes(4, "little")
    assert result["stack"] == bytes(stack)
    assert result["events"] == _independent_events32(vector, fixture)
    assert (result["flags"], result["flag_mask"], result["df"], result["endpoint"]) == (
        0x44,
        0x8C5,
        0,
        RETURN,
    )
    assert (vector, fixture) == before
    result["registers"]["ebx"] ^= 1
    result["xmm"]["xmm7"] ^= 1
    result["events"][0]["value"] ^= 1
    assert (vector, fixture) == before


@pytest.mark.parametrize("length", [33, 35, 36, 47, 63, 64, 65, 95, 96, 127])
@pytest.mark.parametrize("delta", [-17, -1, 0, 128])
def test_safe_overlap_and_tail_last_word_law(length, delta):
    vector, fixture = _installed(
        7, 1, 1, length=length, source=0x1000, destination=0x1000 + delta
    )
    result = _expected(vector, fixture)
    snapshot, payload = _snapshot(vector, fixture)
    assert result["payload"] == payload
    last = 32 * (length // 32 - 1)
    assert result["xmm"]["xmm0"] == int.from_bytes(snapshot[last : last + 16], "little")
    assert result["xmm"]["xmm1"] == int.from_bytes(
        snapshot[last + 16 : last + 32], "little"
    )
    tail = length % 32
    expected_edx = (
        int.from_bytes(
            snapshot[
                length - tail + 4 * (tail // 4 - 1) : length - tail + 4 * (tail // 4)
            ],
            "little",
        )
        if tail >= 4
        else 0
    )
    assert result["registers"]["edx"] == expected_edx
    assert result["flag_mask"] == (0x8C5 if length % 4 == 0 else 0x8D5)
    assert all(result["xmm"][name] == fixture["xmm"][name] for name in XMM[2:])
    assert result["feature_page"] == fixture["feature_page"]


def test_default_fixture_packet_preserves_existing_math_and_observation_inputs():
    assert len(c.vectors()) == 4992
    vector = c.vectors()[0]
    fixture = c._fixture(vector)
    packet = _expected(vector, fixture)
    snapshot = fixture["payload"][
        vector["source_offset"] : vector["source_offset"] + vector["length"]
    ]
    assert packet["registers"]["eax"] == c.PAYLOAD + vector["destination_offset"]
    assert fixture["registers"]["esp"] == c.STACK + 0x2000 + vector["alignment"]
    assert fixture["stack_base"] == c.STACK and fixture["payload_base"] == c.PAYLOAD
    assert fixture["return_address"] == c.RETURN
    assert packet["xmm"]["xmm0"] == int.from_bytes(snapshot[:16], "little")
    assert packet["xmm"]["xmm1"] == int.from_bytes(snapshot[16:32], "little")
    assert set(fixture) == {
        "stack_base",
        "payload_base",
        "stack",
        "payload",
        "registers",
        "xmm",
        "feature_page",
        "return_address",
    }


def test_actual_frame_is_independent_of_default_alignment_metadata():
    vector, fixture = _installed(0, 1)
    vector["alignment"] = 0
    assert _expected(vector, fixture)["registers"]["esp"] == STACK + 0x100F + 4


def test_zero_endpoint_rejected_by_oracle_and_before_native_import():
    vector, fixture = _installed()
    fixture["return_address"] = 0
    stack = bytearray(fixture["stack"])
    at = fixture["registers"]["esp"] - fixture["stack_base"]
    stack[at : at + 4] = bytes(4)
    fixture["stack"] = bytes(stack)
    with pytest.raises(c.ConformanceError, match="^invalid zero return address$"):
        _expected(vector, fixture)
    with pytest.raises(c.ConformanceError, match="^invalid zero return address$"):
        c._run_case({}, [], vector, fixture=fixture)


def test_generated_feature_page_only_installs_named_feature_word():
    vector, fixture = _installed()
    result = c._expected(
        vector,
        fixture["registers"],
        fixture["xmm"],
        fixture["stack"],
        fixture["payload"],
        stack_base=STACK,
        payload_base=DATA,
        return_address=RETURN,
    )
    expected = bytearray(4096)
    expected[0xF30:0xF34] = (0x93939393).to_bytes(4, "little")
    assert result["feature_page"] == bytes(expected)


@pytest.mark.parametrize(
    "field,value",
    [
        ("length", 31),
        ("length", 128),
        ("length", True),
        ("source_offset", -1),
        ("source_offset", 0x4000 - 31),
        ("source_offset", True),
        ("destination_offset", 0x3801),
        ("destination_offset", 0x4000 - 31),
        ("alignment", -1),
        ("alignment", 16),
        ("alignment", True),
        ("df", 1),
        ("df", False),
        ("feature_word", 0x93939391),
        ("feature_word", True),
        ("feature_word", 2**32),
    ],
)
def test_strict_vector_values(field, value):
    vector, fixture = _installed()
    vector[field] = value
    with pytest.raises(c.ConformanceError):
        _expected(vector, fixture)


@pytest.mark.parametrize("kind", ["extra", "missing", "mapping", "registers"])
def test_strict_vector_and_register_schemas(kind):
    vector, fixture = _installed()
    if kind == "extra":
        vector["unclaimed"] = 1
    elif kind == "missing":
        del vector["df"]
    elif kind == "mapping":
        vector = list(vector.items())
    else:
        fixture["registers"]["eflags"] = 0x246
    with pytest.raises(c.ConformanceError):
        _expected(vector, fixture)


@pytest.mark.parametrize("register", REGISTERS)
@pytest.mark.parametrize("value", [True, -1, 2**32])
def test_strict_gpr_words(register, value):
    vector, fixture = _installed()
    fixture["registers"][register] = value
    with pytest.raises(c.ConformanceError):
        _expected(vector, fixture)


@pytest.mark.parametrize("name", XMM)
@pytest.mark.parametrize("value", [False, -1, 2**128])
def test_strict_xmm_words(name, value):
    vector, fixture = _installed()
    fixture["xmm"][name] = value
    with pytest.raises(c.ConformanceError):
        _expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    [
        "xmm_missing",
        "xmm_extra",
        "xmm_list",
        "gpr_missing",
        "gpr_list",
        "stack_mutable",
        "payload_mutable",
        "stack_short",
        "payload_short",
        "empty_stack",
        "empty_payload",
        "feature_short",
        "feature_mutable",
        "feature_binding",
        "stack_base_alignment",
        "payload_base_alignment",
        "base_bool",
        "base_negative",
        "mapping_wrap",
        "copy_wrap",
        "frame_low",
        "frame_high",
        "frame_wrap",
        "stack_payload_alias",
        "feature_payload_alias",
        "feature_stack_alias",
        "code_payload_alias",
        "code_stack_alias",
        "return_payload_alias",
        "return_stack_alias",
        "return_feature_alias",
        "return_code_alias",
        "return_bool",
        "return_negative",
        "return_wrap",
    ],
)
def test_installed_mapping_boundaries(kind):
    vector, fixture = _installed()
    if kind == "xmm_missing":
        del fixture["xmm"]["xmm7"]
    elif kind == "xmm_extra":
        fixture["xmm"]["xmm8"] = 0
    elif kind == "xmm_list":
        fixture["xmm"] = list(fixture["xmm"].values())
    elif kind == "gpr_missing":
        del fixture["registers"]["eax"]
    elif kind == "gpr_list":
        fixture["registers"] = list(fixture["registers"].values())
    elif kind in ("stack_mutable", "payload_mutable", "feature_mutable"):
        field = {"feature_mutable": "feature_page"}.get(kind, kind.split("_")[0])
        fixture[field] = bytearray(fixture[field])
    elif kind in ("stack_short", "payload_short", "feature_short"):
        field = {"feature_short": "feature_page"}.get(kind, kind.split("_")[0])
        fixture[field] = fixture[field][:-1]
    elif kind.startswith("empty_"):
        fixture[kind[6:]] = b""
    elif kind == "feature_binding":
        page = bytearray(fixture["feature_page"])
        page[0xF30] ^= 4
        fixture["feature_page"] = bytes(page)
    elif kind in ("stack_base_alignment", "payload_base_alignment"):
        fixture[kind.removesuffix("_alignment")] += 1
    elif kind in ("base_bool", "base_negative"):
        fixture["payload_base"] = True if kind == "base_bool" else -4096
    elif kind == "mapping_wrap":
        fixture["payload_base"] = 0xFFFFF000
    elif kind == "copy_wrap":
        fixture["payload_base"] = 0xFFFFC000
        vector["source_offset"] = 0x3FE0
    elif kind.startswith("frame_"):
        fixture["registers"]["esp"] = {
            "frame_low": STACK + 7,
            "frame_high": STACK + 0x2000 - 15,
            "frame_wrap": 0xFFFFFFF0,
        }[kind]
    elif kind == "stack_payload_alias":
        fixture["stack_base"] = DATA
        fixture["registers"]["esp"] = DATA + 0x1000
    elif kind.startswith("feature_"):
        fixture["payload_base" if kind == "feature_payload_alias" else "stack_base"] = (
            0x00893000
        )
        if kind == "feature_stack_alias":
            fixture["registers"]["esp"] = 0x00894000
    elif kind.startswith("code_"):
        fixture["payload_base" if kind == "code_payload_alias" else "stack_base"] = (
            c.BASE + (c.START & ~4095)
        )
        if kind == "code_stack_alias":
            fixture["registers"]["esp"] = fixture["stack_base"] + 0x1000
    else:
        fixture["return_address"] = {
            "return_payload_alias": DATA + 0x100,
            "return_stack_alias": STACK + 0x100,
            "return_feature_alias": FEATURE,
            "return_code_alias": c.BASE + c.START,
            "return_bool": False,
            "return_negative": -1,
            "return_wrap": 2**32,
        }[kind]
    with pytest.raises(c.ConformanceError):
        _expected(vector, fixture)


@pytest.mark.parametrize("offset", [0, 4, 8, 12])
def test_each_installed_cdecl_argument_is_bound_before_execution(offset):
    vector, fixture = _installed()
    stack = bytearray(fixture["stack"])
    stack[fixture["registers"]["esp"] - STACK + offset] ^= 1
    fixture["stack"] = bytes(stack)
    with pytest.raises(c.ConformanceError, match="installed copy arguments"):
        _expected(vector, fixture)


@pytest.mark.parametrize("kind", ["extra", "missing", "list", "feature_none"])
def test_runner_fixture_schema_rejected_before_native_import(kind):
    vector, fixture = _installed()
    if kind == "extra":
        fixture["ownership"] = False
    elif kind == "missing":
        del fixture["feature_page"]
    elif kind == "list":
        fixture = list(fixture.items())
    else:
        fixture["feature_page"] = None
    with pytest.raises(
        c.ConformanceError,
        match="feature page" if kind == "feature_none" else "fixture schema",
    ):
        c._run_case({}, [], vector, fixture=fixture)


def test_coordinated_addresses_still_reject_protected_mapping_overlap_before_import():
    vector, fixture = _installed()
    # Change both payload base and its stack arguments. The buffer still aliases
    # the feature page, so argument consistency cannot admit this packet.
    fixture["payload_base"] = 0x00893000
    stack = bytearray(fixture["stack"])
    entry = fixture["registers"]["esp"] - STACK
    for at, offset in (
        (entry + 4, vector["destination_offset"]),
        (entry + 8, vector["source_offset"]),
    ):
        stack[at : at + 4] = (fixture["payload_base"] + offset).to_bytes(4, "little")
    fixture["stack"] = bytes(stack)
    with pytest.raises(c.ConformanceError, match="mappings overlap"):
        c._run_case({}, [], vector, fixture=fixture)


@pytest.fixture(scope="module")
def native_copy_code():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    executable = Path(executable)
    evidence = json.loads(
        (PROGRAMS / (PREFIX + "native_short_simd_copy_semantics.json")).read_text(
            encoding="utf-8"
        )
    )
    data, image, digest = c._load_executable(executable)
    assert digest == c.EXE_SHA256
    assert (
        semantic.validate_structure(
            evidence,
            {
                key: json.loads(
                    (PROGRAMS / (PREFIX + suffix + ".json")).read_text(encoding="utf-8")
                )
                for key, suffix in {
                    "program_facts": "program_facts",
                    "scalar_copy_semantics": "native_scalar_copy_semantics",
                }.items()
            },
        )["status"]
        == "structurally_verified"
    )
    codes, points = {}, []
    for start, end in c.RANGES:
        at = image.rva_to_file_offset(start)
        codes[start] = data[at : at + end - start]
        witness = next(
            part
            for part in evidence["scalar_ranges"]
            if int(part["start_rva"], 16) == start
        )
        decoded = [
            c._point(row)
            for row in c.capstone.Cs(
                c.capstone.CS_ARCH_X86, c.capstone.CS_MODE_32
            ).disasm(codes[start], c.BASE + start)
        ]
        assert decoded == witness["points"]
        points.extend(decoded)
    return codes, points


def _check_native_relocated_32_corpus(native_copy_code, alignment, profile, pattern):
    vector, fixture = _installed(alignment, profile, pattern)
    before = copy.deepcopy((vector, fixture))
    result = c._run_case(*native_copy_code, vector, fixture=fixture)
    expected = _expected(vector, fixture)
    assert (
        result["registers"] == expected["registers"]
        and result["xmm"] == expected["xmm"]
    )
    assert result["events_sha256"] == c._canonical_sha256(
        _independent_events32(vector, fixture)
    )
    assert (
        result["payload_sha256"]
        == hashlib.sha256(_snapshot(vector, fixture)[1]).hexdigest()
    )
    assert result["stack_sha256"] == hashlib.sha256(expected["stack"]).hexdigest()
    assert result["df"] == 0 and result["flags"] == 0x44
    assert (vector, fixture) == before
    result["vector"]["feature_word"] ^= 4
    result["registers"]["ebx"] ^= 1
    result["xmm"]["xmm7"] ^= 1
    assert (vector, fixture) == before


def _check_native_relocated_corruption_controls(native_copy_code, negative):
    vector, fixture = _installed(31, 1, 2, length=64)
    with pytest.raises(c.ConformanceError):
        c._run_case(*native_copy_code, vector, fixture=fixture, negative=negative)


def _check_native_coordinated_expected_packet_corruption(native_copy_code, monkeypatch):
    vector, fixture = _installed(7, 1, 1)
    original = c._expected

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        result["registers"]["edx"] = 1
        result["xmm"]["xmm0"] ^= 1
        payload = bytearray(result["payload"])
        payload[vector["destination_offset"]] ^= 1
        result["payload"] = bytes(payload)
        return result

    monkeypatch.setattr(c, "_expected", changed)
    with pytest.raises(c.ConformanceError, match="register oracle"):
        c._run_case(*native_copy_code, vector, fixture=fixture)


def _check_native_default_receipt_rebuild_and_verify_remain_exact():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    executable = Path(executable)
    semantics = json.loads(
        (PROGRAMS / (PREFIX + "native_short_simd_copy_semantics.json")).read_text(
            encoding="utf-8"
        )
    )
    raw = (PROGRAMS / (PREFIX + "native_short_simd_copy_conformance.json")).read_bytes()
    evidence = json.loads(raw)
    assert (
        c.encode_conformance(c.build_conformance(executable, semantics)).encode("utf-8")
        == raw
    )
    assert (
        c.validate_conformance(executable, evidence, semantics)["status"] == "verified"
    )


def _isolated_native(action, *arguments):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, *map(str, arguments)],
        cwd=ROOT,
        capture_output=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b"" and result.stderr == b""


@pytest.mark.parametrize("alignment", [0, 1, 7, 31])
@pytest.mark.parametrize("profile", [0, 1])
@pytest.mark.parametrize("pattern", [0, 1, 2])
def test_native_relocated_32_corpus(alignment, profile, pattern):
    _isolated_native("corpus", alignment, profile, pattern)


@pytest.mark.parametrize("negative", ["byte", "xmm"])
def test_native_relocated_corruption_controls(negative):
    _isolated_native("negative", negative)


def test_native_coordinated_expected_packet_corruption():
    _isolated_native("coordinated")


def test_native_default_receipt_rebuild_and_verify_remain_exact():
    _isolated_native("default")


if __name__ == "__main__":
    action, *arguments = sys.argv[1:]
    if action == "default":
        _check_native_default_receipt_rebuild_and_verify_remain_exact()
    else:
        code = native_copy_code.__wrapped__()
        if action == "corpus":
            _check_native_relocated_32_corpus(code, *map(int, arguments))
        elif action == "negative":
            _check_native_relocated_corruption_controls(code, arguments[0])
        elif action == "coordinated":
            with pytest.MonkeyPatch.context() as patch:
                _check_native_coordinated_expected_packet_corruption(code, patch)
        else:
            raise ValueError("unknown isolated native action")
