"""Independent native mode-three getter and opaque child-entry conformance."""

import copy
import faulthandler
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
from src.observatory import native_assertion_helper_parent_dispatch_conformance as c

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE_PATH = PROGRAMS / (
    PREFIX + "native_assertion_helper_parent_dispatch_conformance.json"
)
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
GETTERS = (0, 1, 2, 0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF)
FIRST_ADDRESS, SECOND_ADDRESS = 0x008B7534, 0x008B7318


def canonical_hash(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def blob(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def word(pages, address):
    return int.from_bytes(blob(pages, address, 4), "little")


def patch(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def alternate(vector):
    return (
        vector["first_global"] == 1
        or vector["first_global"] == 0
        and vector["second_global"] == 1
    )


def independent_trace(vector):
    rows = [
        0x379CC2,
        0x379CC4,
        0x379CC5,
        0x379CC7,
        0x379CC8,
        0x379CCB,
        0x379CCD,
        0x38E392,
        0x38E394,
        0x38E395,
        0x38E397,
        0x38E39A,
        0x38E39C,
        0x38E39E,
        0x38E3A1,
        0x38E3A3,
        0x38E3A6,
        0x38E3A8,
        0x38E3AD,
        0x38E3AE,
        0x379CD2,
        0x379CD3,
        0x379CD6,
    ]
    if vector["first_global"] != 1:
        rows += [0x379CD8, 0x379CDA]
    if vector["first_global"] == 0:
        rows += [0x379CDC, 0x38C89F, 0x38C8A4, 0x379CE1, 0x379CE4]
    return rows + (
        [0x379CFB, 0x379CFE, 0x379D01, 0x379D04]
        if alternate(vector)
        else [0x379CE6, 0x379CE7, 0x379CEA, 0x379CED, 0x379CF0]
    )


FLAG_LITERALS = {
    0: (0x95, 0xCD5),
    1: (0x44, 0xCD5),
    2: (0, 0xCD5),
    0x7FFFFFFF: (0, 0xCD5),
    0x80000000: (0x814, 0xCD5),
    0x80000001: (0x84, 0xCD5),
    0xFFFFFFFF: (0x80, 0xCD5),
}
TEST_FLAG_LITERALS = {
    2: (0, 0xCC5),
    0x7FFFFFFF: (4, 0xCC5),
    0x80000000: (0x84, 0xCC5),
    0x80000001: (0x80, 0xCC5),
    0xFFFFFFFF: (0x84, 0xCC5),
}


def independent_flags(vector):
    first = vector["first_global"]
    if first == 0:
        return FLAG_LITERALS[vector["second_global"]]
    if first == 1:
        return 0x44, 0xCD5
    return TEST_FLAG_LITERALS[first]


def _source_paths():
    return {
        key: PROGRAMS
        / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }


def _sources():
    return {key: json.loads(path.read_bytes()) for key, path in _source_paths().items()}


def scalar_arguments(fixture, vector):
    s = fixture["registers"]["esp"]
    return dict(
        entry=s,
        registers=fixture["registers"],
        caller_return=word(fixture["pages"], s),
        condition=word(fixture["pages"], s + 4),
        file=word(fixture["pages"], s + 8),
        line=word(fixture["pages"], s + 12),
        first_global=vector["first_global"],
        second_global=vector["second_global"],
    )


def test_exact_matrix_opaque_profiles_body_geometry_and_four_source_dependencies():
    expected = [
        dict(first_global=first, second_global=second, alignment=a, profile=p)
        for first in GETTERS
        for second in GETTERS
        for a in range(16)
        for p in range(3)
    ]
    assert c.vectors() == expected and len(expected) == 2352
    assert set(c.SOURCE_PINS) == {"parent", "first", "second", "program_facts"}
    assert (
        c.SOURCE_PINS["parent"][1]
        == "beeebb2dadd0ef2a77742f9296760fd09afe5c566c7b46bf36d2dd3cf8e441b4"
    )
    assert (
        c.SOURCE_PINS["first"][1]
        == "e99d2b76879c1456c6ec44bf3fcbc38f2f50a456aae6416687f0cf1f09898da0"
    )
    assert (
        c.SOURCE_PINS["second"][1]
        == "ad26b7dddb2996fd69b53937de0ae8bdb6d694982df62c280c4a03430895e0d7"
    )
    assert {key: value[:2] for key, value in c.BODIES.items()} == {
        0x379CC2: (72, 29),
        0x38E392: (63, 23),
        0x38C89F: (6, 2),
    }
    assert sum(body[0] for body in c.BODIES.values()) == 141
    assert sum(body[1] for body in c.BODIES.values()) == 54
    assert {key: value[2] for key, value in c.BODIES.items()} == {
        0x379CC2: "1f55c49efcf686fecf491fc4ac23411e373af8d7c38c0f076b070a417e7ddf13",
        0x38E392: "9ccce0d1b341bdf834edec2dc6c9626c73f97a7e4df7917e4c7d202ae906039d",
        0x38C89F: "f664d3656a8c5a2735ac645e41a9bf134e95d47511b55d5466a3384f9d529fec",
    }


@pytest.mark.parametrize(
    "profile,words,flags",
    (
        (0, [0x0400A000, 0, 0, 0], 0x246),
        (1, [0x006EC151, 0x0083CA00, 0x0083C9C8, 69], 0x202),
        (2, [0xFFFFFFFF, 0xFFFFFFFF, 0xFEFEFEFE, 0xFFFFFFFF], 0x2D7),
    ),
)
@pytest.mark.parametrize("alignment", (0, 1, 7, 15))
def test_fixture_profiles_preserve_arbitrary_opaque_caller_words(
    profile, words, flags, alignment
):
    fixture = c._fixture(
        dict(first_global=0, second_global=1, alignment=alignment, profile=profile)
    )
    assert set(fixture) == {"pages", "registers", "entry_flags"}
    s = fixture["registers"]["esp"]
    assert s == 0x30001000 + alignment
    assert [word(fixture["pages"], s + 4 * i) for i in range(4)] == words
    assert fixture["entry_flags"] == flags
    assert set(fixture["registers"]) == set(GPR)
    packet = c._expected(fixture)
    assert packet["call"]["arguments"] == words[1:]
    assert packet["registers"]["esi"] == words[0]
    assert packet["call"]["entry_esp"] == s - 24


@pytest.mark.parametrize(
    "field", ("first_global", "second_global", "alignment", "profile")
)
@pytest.mark.parametrize("bad", (False, True, -1, 2**32, 1.0, None))
def test_vector_words_and_recipe_indices_are_strict(field, bad):
    vector = dict(first_global=0, second_global=0, alignment=0, profile=0)
    vector[field] = bad
    with pytest.raises(c.ConformanceError, match="vector differs"):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind", ("missing", "extra", "tuple", "getter", "alignment", "profile")
)
def test_vector_schema_and_finite_membership_are_closed(kind):
    vector = dict(first_global=0, second_global=0, alignment=0, profile=0)
    if kind == "missing":
        vector.pop("profile")
    elif kind == "extra":
        vector["mode"] = 3
    elif kind == "tuple":
        vector = tuple(vector.items())
    elif kind == "getter":
        vector["first_global"] = 3
    elif kind == "alignment":
        vector["alignment"] = 16
    else:
        vector["profile"] = 3
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "tuple",
        "register_missing",
        "register_extra",
        "register_bool",
        "register_wide",
        "esp_wrap",
        "pages_tuple",
        "page_missing",
        "page_short",
        "page_bytearray",
        "page_unaligned",
        "page_wide",
        "flags_bool",
        "flags_negative",
        "flags_wide",
        "flags_df",
        "stack_overlap",
    ),
)
def test_expected_fixture_schema_types_memory_geometry_and_flags_are_strict(kind):
    fixture = c._fixture(dict(first_global=0, second_global=1, alignment=0, profile=0))
    if kind == "extra":
        fixture["extra"] = 0
    elif kind == "missing":
        fixture.pop("entry_flags")
    elif kind == "tuple":
        fixture = tuple(fixture.items())
    elif kind == "register_missing":
        fixture["registers"].pop("edx")
    elif kind == "register_extra":
        fixture["registers"]["eip"] = 0
    elif kind == "register_bool":
        fixture["registers"]["eax"] = False
    elif kind == "register_wide":
        fixture["registers"]["eax"] = 2**32
    elif kind == "esp_wrap":
        fixture["registers"]["esp"] = 0xFFFFFFF1
    elif kind == "pages_tuple":
        fixture["pages"] = tuple(fixture["pages"].items())
    elif kind == "page_missing":
        fixture["pages"].pop(0x008B7000)
    elif kind == "page_short":
        fixture["pages"][0x008B7000] = bytes(4095)
    elif kind == "page_bytearray":
        fixture["pages"][0x008B7000] = bytearray(4096)
    elif kind == "page_unaligned":
        fixture["pages"][0x05000001] = bytes(4096)
    elif kind == "page_wide":
        fixture["pages"][2**32] = bytes(4096)
    elif kind.startswith("flags_"):
        fixture["entry_flags"] = {
            "flags_bool": False,
            "flags_negative": -1,
            "flags_wide": 2**32,
            "flags_df": 0x646,
        }[kind]
    else:
        fixture["registers"]["esp"] = FIRST_ADDRESS
    with pytest.raises(c.ConformanceError):
        c._expected(fixture)


def test_actual_page_contract_accepts_changed_caller_return_condition_file_line_and_AF():
    fixture = c._fixture(dict(first_global=0, second_global=0, alignment=15, profile=0))
    s = fixture["registers"]["esp"]
    values = [0x00779551, 0xFFFFFFFF, 0, 0xDEADFEED]
    for i, value in enumerate(values):
        patch(fixture["pages"], s + 4 * i, value)
    fixture["entry_flags"] = 0x54
    packet = c._expected(fixture)
    assert packet["call"]["arguments"] == [*values[1:], values[0]]
    assert packet["registers"]["esi"] == values[0]
    assert packet["flags"] == 0x95 and packet["flag_mask"] == 0xCD5


def test_preflight_closes_source_schema_without_executable():
    original = _sources()
    assert set(c._preflight(original)) == set(c.SOURCE_PINS)
    for kind in ("missing", "extra", "tuple", "value_type"):
        sources = copy.deepcopy(original)
        if kind == "missing":
            sources.pop("first")
        elif kind == "extra":
            sources["fifth"] = {}
        elif kind == "tuple":
            sources = tuple(sources.items())
        else:
            sources["parent"] = []
        with pytest.raises(c.ConformanceError):
            c._preflight(sources)
    for key in c.SOURCE_PINS:
        sources = copy.deepcopy(original)
        sources[key]["schema_version"] = 99
        with pytest.raises(c.ConformanceError):
            c._preflight(sources)


def test_evidence_encoder_is_deterministic_utf8_lf():
    data = dict(schema_version=1, label="é", values=[0, 1, 0xFFFFFFFF])
    encoded = c.encode_conformance(data).encode("utf-8")
    assert encoded.endswith(b"\n") and b"\r" not in encoded
    assert b"\xc3\xa9" in encoded and b"\\u00e9" not in encoded
    assert json.loads(encoded) == data
    assert encoded == c.encode_conformance(dict(reversed(list(data.items())))).encode(
        "utf-8"
    )


SELECTED_SPECS = (
    (0, 0, 0, 0),
    (0, 1, 1, 1),
    (0, 2, 2, 2),
    (0, 0x7FFFFFFF, 3, 0),
    (0, 0x80000000, 4, 1),
    (0, 0x80000001, 5, 2),
    (0, 0xFFFFFFFF, 6, 0),
    (1, 0xFFFFFFFF, 7, 1),
    (2, 1, 8, 2),
    (0x7FFFFFFF, 1, 9, 0),
    (0x80000000, 1, 10, 1),
    (0x80000001, 1, 11, 2),
    (0xFFFFFFFF, 1, 12, 0),
    (1, 0, 13, 2),
    (2, 0xFFFFFFFF, 14, 1),
    (0, 1, 15, 0),
)
SELECTED = [
    c.vectors().index(dict(first_global=f, second_global=s, alignment=a, profile=p))
    for f, s, a, p in SELECTED_SPECS
]


def _native_inputs(index):
    vector = c.vectors()[index]
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.EXE_SHA256
    codes, points = c._load_code(data, image, _sources())
    return codes, points, vector


def independent_events(arguments):
    s = arguments["entry"]
    initial = arguments["registers"]
    first, second = arguments["first_global"], arguments["second_global"]
    alt = first == 1 or (first == 0 and second == 1)
    rows = [
        ("write", s - 4, initial["ebp"], 0x379CC4),
        ("write", s - 8, initial["esi"], 0x379CC7),
        ("read", s, arguments["caller_return"], 0x379CC8),
        ("write", s - 12, 3, 0x379CCB),
        ("write", s - 16, 0x00779CD2, 0x379CCD),
        ("write", s - 20, s - 4, 0x38E394),
        ("read", s - 12, 3, 0x38E397),
        ("read", FIRST_ADDRESS, first, 0x38E3A8),
        ("read", s - 20, s - 4, 0x38E3AD),
        ("read", s - 16, 0x00779CD2, 0x38E3AE),
        ("read", s - 12, 3, 0x379CD2),
    ]
    if first == 0:
        rows += [
            ("write", s - 12, 0x00779CE1, 0x379CDC),
            ("read", SECOND_ADDRESS, second, 0x38C89F),
            ("read", s - 12, 0x00779CE1, 0x38C8A4),
        ]
    if alt:
        rows += [
            ("read", s + 12, arguments["line"], 0x379CFB),
            ("write", s - 12, arguments["line"], 0x379CFB),
            ("read", s + 8, arguments["file"], 0x379CFE),
            ("write", s - 16, arguments["file"], 0x379CFE),
            ("read", s + 4, arguments["condition"], 0x379D01),
            ("write", s - 20, arguments["condition"], 0x379D01),
            ("write", s - 24, 0x00779D09, 0x379D04),
        ]
    else:
        rows += [
            ("write", s - 12, arguments["caller_return"], 0x379CE6),
            ("read", s + 12, arguments["line"], 0x379CE7),
            ("write", s - 16, arguments["line"], 0x379CE7),
            ("read", s + 8, arguments["file"], 0x379CEA),
            ("write", s - 20, arguments["file"], 0x379CEA),
            ("read", s + 4, arguments["condition"], 0x379CED),
            ("write", s - 24, arguments["condition"], 0x379CED),
            ("write", s - 28, 0x00779CF5, 0x379CF0),
        ]
    return rows


def _packet(index):
    from unicorn import x86_const as x

    codes, points, vector = _native_inputs(index)
    assert sum(map(len, codes.values())) == 141 and len(points) == 54
    assert {a - c.BASE: len(body) for a, body in codes.items()} == {
        0x379CC2: 72,
        0x38E392: 63,
        0x38C89F: 6,
    }
    fixture = c._fixture(vector)
    before = copy.deepcopy(fixture)
    arguments = scalar_arguments(fixture, vector)
    events = independent_events(arguments)
    expected_pages = copy.deepcopy(fixture["pages"])
    for access, address, value, _ in events:
        if access == "write":
            patch(expected_pages, address, value)
    flags, mask = independent_flags(vector)
    s = fixture["registers"]["esp"]
    is_alt = alternate(vector)
    sp = s - (24 if is_alt else 28)
    expected_registers = dict(
        fixture["registers"],
        eax=(
            vector["second_global"]
            if vector["first_global"] == 0
            else vector["first_global"]
        ),
        ecx=3,
        esi=arguments["caller_return"],
        ebp=s - 4,
        esp=sp,
    )
    captured = {}

    def capture(machine, ids, expected):
        captured.update(
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
        )

    observation = c._run_case(codes, points, vector, capture=capture)
    assert set(observation) == {
        "vector",
        "branch",
        "registers",
        "flags",
        "flag_mask",
        "endpoint",
        "trace_rvas",
        "events_sha256",
        "memory_sha256",
        "second_getter",
        "arguments",
        "opaque_child_executed",
    }
    assert captured["registers"] == expected_registers
    assert all(
        type(value) is int and 0 <= value <= 0xFFFFFFFF
        for value in captured["registers"].values()
    )
    assert captured["pages"] == expected_pages
    assert captured["endpoint"] == (0x00779B31 if is_alt else 0x00779550)
    assert captured["flags"] & mask == flags and captured["flags"] & 0x400 == 0
    event_dicts = [
        dict(access=a, address=p, width=4, value=v, rva=rva) for a, p, v, rva in events
    ]
    assert observation["events_sha256"] == canonical_hash(event_dicts)
    assert observation["memory_sha256"] == canonical_hash(
        {str(p): hashlib.sha256(body).hexdigest() for p, body in expected_pages.items()}
    )
    assert observation["registers"] == expected_registers
    assert (observation["flags"], observation["flag_mask"]) == (flags, mask)
    assert observation["vector"] == vector
    assert observation["arguments"] == [
        arguments["condition"],
        arguments["file"],
        arguments["line"],
    ] + ([] if is_alt else [arguments["caller_return"]])
    assert observation["endpoint"] == ("0x00379b31" if is_alt else "0x00379550")
    assert observation["second_getter"] is (vector["first_global"] == 0)
    assert observation["opaque_child_executed"] is False
    assert observation["trace_rvas"] == [
        f"0x{pc:08x}" for pc in independent_trace(vector)
    ]
    assert not any(
        pc in observation["trace_rvas"]
        for pc in (
            "0x00379550",
            "0x00379b31",
            "0x00379cf5",
            "0x00379cfa",
            "0x00379d09",
            "0x0038e3af",
            "0x0038e3bc",
            "0x0038e3c7",
        )
    )
    assert blob(captured["pages"], FIRST_ADDRESS, 4) == blob(
        before["pages"], FIRST_ADDRESS, 4
    )
    assert blob(captured["pages"], SECOND_ADDRESS, 4) == blob(
        before["pages"], SECOND_ADDRESS, 4
    )
    assert blob(captured["pages"], s, 16) == blob(before["pages"], s, 16)
    assert fixture == before


def _controls():
    codes, points, _ = _native_inputs(0)
    vector = dict(first_global=0, second_global=2, alignment=15, profile=2)
    assert (
        c.CONTROLS["restored_global_write"]
        == "assertion dispatch ordered events differ"
    )
    assert (
        c.CONTROLS["missing_read"]
        == c.CONTROLS["extra_read"]
        == "assertion dispatch ordered events differ"
    )
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, vector, kind)
        assert str(caught.value) == reason, kind


def _isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed private native runtime")
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        capture_output=True,
        env=environment,
        timeout=2400,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b"" and result.stdout == b""


@pytest.mark.parametrize("index", SELECTED)
def test_selected_actual_native_packets_all_alignments_profiles_getters_and_flags(
    index,
):
    _isolated("packet", index)


def test_all_native_and_injected_event_record_controls_reject_at_intended_frontier():
    # missing/extra/restored-write controls alter the recorded event list.
    # They prove strict event comparison, not execution of a native global store.
    _isolated("controls")


@pytest.fixture
def receipts():
    if not EVIDENCE_PATH.exists():
        pytest.skip("primary has not published the sealed dispatch receipt")
    return json.loads(EVIDENCE_PATH.read_bytes()), _sources()


def test_sealed_receipt_summary_is_derived_from_independent_branch_and_trace_equations(
    receipts,
):
    evidence, sources = receipts
    assert c.SEALED_SHA256 != "PENDING"
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert canonical_hash(evidence) == c.SEALED_SHA256
    assert c.encode_conformance(evidence).encode("utf-8") == EVIDENCE_PATH.read_bytes()
    vectors = c.vectors()
    summary = evidence["summary"]
    paths = [independent_trace(v) for v in vectors]
    union = sorted({f"0x{pc:08x}" for path in paths for pc in path})
    assert evidence["executed_rvas"] == union
    assert evidence["vectors"] == vectors and len(evidence["source_receipts"]) == 4
    assert len(evidence["body"]["points"]) == summary["static_sites"] == 54
    assert (
        sum(
            int(row["end_rva"], 16) - int(row["start_rva"], 16)
            for row in evidence["body"]["ranges"]
        )
        == summary["instruction_bytes"]
        == 141
    )
    assert summary["cases"] == summary["first_getters"] == 2352
    assert summary["second_getters"] == sum(v["first_global"] == 0 for v in vectors)
    assert summary["alternate"] == sum(alternate(v) for v in vectors)
    assert summary["normal"] == sum(not alternate(v) for v in vectors)
    assert summary["native_instructions"] == sum(map(len, paths))
    assert summary["executed_sites"] == len(union)
    assert (
        summary["controls"]
        == len(evidence["negative_controls"])
        == len(c.CONTROLS)
        == 19
    )
    assert {
        row["kind"]: row["reason"] for row in evidence["negative_controls"]
    } == c.CONTROLS
    assert all(row["rejected"] is True for row in evidence["negative_controls"])
    assert all(
        summary[key] == 0
        for key in (
            "global_writes",
            "opaque_native_instructions",
            "accounting_promotions",
        )
    )
    assert evidence["engine"] == dict(
        name="Unicorn", version="2.1.4", architecture="x86_32"
    )
    assert len(evidence["observations_sha256"]) == 64


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "vector",
        "observation",
        "control",
        "coverage",
        "point",
        "range",
        "pins",
        "scope",
    ),
)
def test_refreshed_or_mutated_receipt_cannot_reseal_without_the_exact_frozen_digest(
    receipts, kind
):
    original, sources = receipts
    evidence = copy.deepcopy(original)
    if kind == "summary":
        evidence["summary"]["normal"] += 1
    elif kind == "vector":
        evidence["vectors"][0]["first_global"] = 1
    elif kind == "observation":
        evidence["observations_sha256"] = "0" * 64
    elif kind == "control":
        evidence["negative_controls"][0]["rejected"] = False
    elif kind == "coverage":
        evidence["executed_rvas"].pop()
    elif kind == "point":
        evidence["body"]["points"][0]["size"] += 1
    elif kind == "range":
        evidence["body"]["ranges"][0]["end_rva"] = "0xffffffff"
    elif kind == "pins":
        evidence["source_receipts"] = {}
    else:
        evidence["scope"]["checked"][0] += " source identity"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize("key", ("parent", "first", "second", "program_facts"))
def test_static_source_tampering_rejects_even_with_unchanged_sealed_receipt(
    receipts, key
):
    evidence, original = receipts
    sources = copy.deepcopy(original)
    sources[key]["schema_version"] = 99
    with pytest.raises(c.ConformanceError):
        c.validate_structure(evidence, sources)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_and_structure_match_deterministic_sealed_receipt(
    receipts, command
):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and reviewed private native runtime")
    arguments = [
        sys.executable,
        str(
            ROOT / "scripts/itb_native_assertion_helper_parent_dispatch_conformance.py"
        ),
        command,
    ]
    for key, path in _source_paths().items():
        arguments += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        arguments += ["--executable", str(Path(executable))]
    if command != "build":
        arguments += ["--evidence", str(EVIDENCE_PATH)]
    environment = dict(os.environ)
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, timeout=2400, env=environment
    )
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
    faulthandler.disable()
    action, index = sys.argv[1], int(sys.argv[2])
    if action == "packet":
        _packet(index)
    elif action == "controls":
        _controls()
    else:
        raise ValueError("unknown isolated dispatch action")
