"""Joined deallocation frame, raw-null result and ancestor alias tests."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from src.observatory import native_vector_deallocation_composition as helper
from src.observatory import native_vector_deallocation_conformance_joined as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
P = 0x7000100


def records(cell=0x6000101, last=5, mapped=12):
    return [
        dict(kind=k, eax=v)
        for k, v in (
            ("heap_free", 0),
            ("error", cell),
            ("get_last_error", last),
            ("map_error", mapped),
        )
    ]


@pytest.mark.parametrize("s", [32, 0x30001000, 0x3000100F, 2**32 - 16])
def test_fresh_ancestor_frames_and_tail_cleanup(s):
    frame = helper.frame_join(s)
    assert frame["free_entry"] == s - 12 and frame["heap_entry"] == s - 32
    assert frame["protected_start"] == s - 32 and frame["protected_end"] == s + 16
    assert frame["guard_return"] == s + 4
    assert helper.tail_case(s)["exit_esp"] == s + 4


@pytest.mark.parametrize("s", [True, 31, 2**32 - 15, None])
def test_wrapping_or_invalid_ancestor_frames_rejected(s):
    with pytest.raises(helper.CompositionError):
        helper.frame_join(s)


@pytest.mark.parametrize(
    "pointer,count,stride,metadata,result",
    [
        (0, 0, 8, None, 0x1FFFFFFF),
        (0, 0, 7, None, 0xFFFFFFFF // 7),
        (32, 512, 8, 0, 32),
    ],
)
def test_numeric_raw_null_preserves_guard_eax(pointer, count, stride, metadata, result):
    value = helper.joined_spec(pointer, count, stride, metadata, [])
    assert value["outcome"] == "normal_return"
    assert value["free"]["outcome"] == "null_return"
    assert value["result"] == result


@pytest.mark.parametrize("mapped", [0, 12, 0xFFFFFFFF])
def test_mapped_error_result_reaches_guard_return(mapped):
    value = helper.joined_spec(P, 512, 8, P - 32, records(mapped=mapped))
    assert value["outcome"] == "normal_return" and value["result"] == mapped


@pytest.mark.parametrize(
    "cell",
    [
        0x30000FE0,
        0x3000100C,
        0x3000100F,
        P - 5,
        P - 4,
        P - 1,
        helper.free.HEAP_WORD,
        helper.free.FREE_IAT,
        helper.BASE + 0x7856,
        0xFFFFFFFF,
    ],
)
def test_error_write_cannot_alias_ancestor_arguments_or_metadata(cell):
    with pytest.raises(helper.CompositionError, match="aliases"):
        helper.joined_spec(P, 512, 8, P - 32, records(cell=cell))


@pytest.mark.parametrize(
    "pointer", [0x30001000, helper.free.FREE_IAT + 4, helper.BASE + 0x7820]
)
def test_metadata_must_avoid_protected_frame_iat_and_code(pointer):
    # Some protected words are not payload-aligned; only aligned metadata reads apply.
    pointer = (pointer + 31) & ~31
    if pointer == helper.free.FREE_IAT + 4:
        expected = True
    else:
        expected = pointer in (0x30001000, helper.BASE + 0x7820)
    assert expected
    with pytest.raises(helper.CompositionError, match="metadata"):
        helper.joined_spec(pointer, 512, 8, pointer - 32, [])


def test_guard_frontier_never_consumes_free_responses():
    value = helper.joined_spec(1, 0, 0, None, [])
    assert value["outcome"] == "division_frontier" and value["free"] is None
    with pytest.raises(helper.CompositionError):
        helper.joined_spec(1, 0, 0, None, [dict(kind="heap_free", eax=1)])


def test_cleanup_mutation_is_detected():
    with pytest.raises(helper.CompositionError):
        helper.tail_case(increment=8)


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "guard_semantics": "native_vector_deallocation_semantics",
        "free_protocol": "native_heap_free_protocol",
        "composition": "native_vector_deallocation_composition",
        "conformance": "native_vector_deallocation_conformance_joined",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffix.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_published_join_covers_native_tail_and_component_bodies(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["composition"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        replay.validate_structure(data["conformance"], data["composition"])["status"]
        == "structurally_verified"
    )
    assert (
        helper.encode_composition(data["composition"]).encode()
        == paths["composition"].read_bytes()
    )
    assert (
        replay.encode_conformance(data["conformance"]).encode()
        == paths["conformance"].read_bytes()
    )
    assert data["conformance"]["summary"]["executed_instruction_sites"] == 53
    assert data["conformance"]["summary"]["opaque_instructions"] == 0


@pytest.mark.parametrize("kind", ["composition", "conformance"])
def test_changed_receipt_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 99
    with pytest.raises((helper.CompositionError, replay.ConformanceError)):
        (
            helper.validate_structure(changed, sources)
            if kind == "composition"
            else replay.validate_structure(changed, data["composition"])
        )


@pytest.mark.parametrize("kind", ["composition", "conformance"])
def test_exact_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    script = (
        "itb_native_vector_deallocation_"
        + ("composition" if kind == "composition" else "conformance_joined")
        + ".py"
    )
    args = [
        sys.executable,
        str(ROOT / "scripts" / script),
        "build",
        "--executable",
        executable,
    ]
    for key in (sources if kind == "composition" else ["composition"]):
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
