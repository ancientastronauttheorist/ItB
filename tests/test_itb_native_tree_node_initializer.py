"""Conditional fields, partial alias feedback and explicit opaque-return checks."""

import copy, hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from src.observatory import native_tree_node_initializer_semantics as helper
from src.observatory import native_tree_node_initializer_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("alignment", range(16))
def test_fresh_block_first_three_words_and_untouched_tail(alignment):
    p = 0x20002000 + alignment
    head = 0x89ABCDEF
    fixture = helper.case_fixture(p, head)
    result = helper.model_case(p, head)
    wanted = dict(fixture["memory"])
    for i, b in enumerate(head.to_bytes(4, "little") * 3):
        wanted[p + i] = b
    s = fixture["stack"]
    for at, value in (
        (s - 4, fixture["registers"]["esi"]),
        (s - 8, fixture["registers"]["edi"]),
        (s - 12, 24),
        (s - 16, helper.BASE + 0x7D06B),
    ):
        wanted.update({at + i: b for i, b in enumerate(value.to_bytes(4, "little"))})
    assert result["memory_sha256"] == helper._canonical_sha256(
        [list(i) for i in sorted(wanted.items())]
    )
    assert result["registers"]["eax"] == p and result["registers"]["edx"] == head
    assert result["registers"]["ecx"] == p + 8 and result["registers"]["esp"] == s + 4
    assert helper.fresh_block_spec(p, head)["untouched_offsets"] == list(range(12, 24))


@pytest.mark.parametrize(
    "offset,values",
    [
        (-1, [0x11223344, 0x11112233, 0x33112233]),
        (1, [0x11223344, 0x22334444, 0x22334444]),
        (-5, [0x11223344, 0x11223344, 0x11112233]),
        (-9, [0x11223344] * 3),
        (0, [0x11223344] * 3),
    ],
)
def test_partial_alias_requires_fresh_head_read(offset, values):
    result = helper.model_case(helper.SOURCE + offset, 0x11223344)
    assert [store["value"] for store in result["stores"]] == values
    assert result["registers"]["edx"] == 0x11223344
    reads = [
        e
        for e in result["events"]
        if e["kind"] == "read" and e["address"] == helper.SOURCE
    ]
    assert [e["value"] for e in reads] == values


@pytest.mark.parametrize(
    "pointer,addresses",
    [
        (0, [4, 8]),
        (0xFFFFFFF8, [0xFFFFFFF8, 0xFFFFFFFC]),
        (0xFFFFFFFC, [0xFFFFFFFC, 4]),
    ],
)
def test_numeric_null_and_wrap_skip_only_zero_field(pointer, addresses):
    volatile = dict(ecx=3, edx=0x55667788, flags=0x8D5)
    result = helper.model_case(pointer, volatile=volatile)
    assert [store["address"] for store in result["stores"]] == addresses
    assert result["registers"]["eax"] == pointer
    assert result["registers"]["edx"] == (0x55667788 if pointer == 0 else 0x11223344)
    final = (pointer + 8) & 0xFFFFFFFF
    assert result["arithmetic_flags"] == dict(
        cf=0,
        pf=int((final & 255).bit_count() % 2 == 0),
        af=None,
        zf=int(final == 0),
        sf=final >> 31,
        of=0,
    )


def test_actual_call_and_opaque_return_events_are_distinct():
    fixture = helper.case_fixture(0x20002000)
    result = helper.model_case(0x20002000)
    s = fixture["stack"]
    events = result["events"]
    assert events[2] == dict(
        kind="write", address=s - 12, width=4, value=24, origin="native"
    )
    assert events[3] == dict(
        kind="write",
        address=s - 16,
        width=4,
        value=helper.BASE + 0x7D06B,
        origin="native",
    )
    assert events[4] == dict(
        kind="read",
        address=s - 16,
        width=4,
        value=helper.BASE + 0x7D06B,
        origin="opaque_return",
    )


@pytest.mark.parametrize(
    "pointer",
    [
        True,
        -1,
        0x100000000,
        0xFFFFFFF9,
        0xFFFFFFFA,
        0xFFFFFFFB,
        0xFFFFFFFD,
        0xFFFFFFFE,
        0xFFFFFFFF,
    ],
)
def test_invalid_or_crossing_word_pointers_rejected(pointer):
    with pytest.raises(helper.InitializerError):
        helper.model_case(pointer)


def test_protected_alias_and_invalid_summary_rejected():
    for pointer in (
        0x30001000,
        helper.BASE + helper.START,
        helper.BASE + helper.TARGET,
    ):
        with pytest.raises(helper.InitializerError):
            helper.model_case(pointer)
    with pytest.raises(helper.InitializerError):
        helper.model_case(0x20002000, volatile=dict(ecx=0, edx=0, flags=0x400))
    with pytest.raises(helper.InitializerError):
        helper.model_case(0x20002000, df=True)
    with pytest.raises(helper.InitializerError):
        helper.model_case(0x20002000, frame_alignment=True)


def test_fresh_corollary_excludes_alias_null_and_wrapped_block():
    for pointer in (0, helper.SOURCE, 0xFFFFFFF8):
        with pytest.raises(helper.InitializerError):
            helper.fresh_block_spec(pointer, 1)


def test_independent_replay_alias_oracle():
    vector = dict(
        pointer=helper.SOURCE - 1,
        head=0x11223344,
        frame_alignment=15,
        seed=7,
        source_address=helper.SOURCE,
        df=1,
    )
    result = replay.oracle(vector, helper.case_fixture(**vector))
    assert [s["value"] for s in result["stores"]] == [
        0x11223344,
        0x11112233,
        0x33112233,
    ]
    assert not result["ordinary"]


@pytest.fixture(scope="module")
def receipts():
    paths = {
        key: PROGRAMS / (PREFIX + suffix + ".json")
        for key, suffix in {
            "program_facts": "program_facts",
            "retry_semantics": "native_allocation_retry_semantics",
            "semantics": "native_tree_node_initializer_semantics",
            "conformance": "native_tree_node_initializer_conformance",
        }.items()
    }
    data = {key: json.loads(path.read_bytes()) for key, path in paths.items()}
    return paths, data, {key: data[key] for key in helper.SOURCE_PINS}


def test_receipt_integrity_and_encoding(receipts):
    paths, data, sources = receipts
    assert (
        helper.validate_structure(data["semantics"], sources)["status"]
        == "structurally_verified"
    )
    assert (
        replay.validate_structure(data["conformance"], data["semantics"])["status"]
        == "structurally_verified"
    )
    for kind, encode, sha in [
        (
            "semantics",
            helper.encode_semantics,
            "b70068e94024626aa1255edc1980be27cc484ee8680772dc9ed7ac8a63bfb03b",
        ),
        (
            "conformance",
            replay.encode_conformance,
            "0d948405547c6ce9e62c53a7047f3f691d6d171c1e3746ab32952754cb92f8a9",
        ),
    ]:
        raw = paths[kind].read_bytes()
        assert raw == encode(data[kind]).encode() and b"\r\n" not in raw
        assert hashlib.sha256(raw).hexdigest() == sha


@pytest.mark.parametrize("kind", ["semantics", "conformance", "source"])
def test_receipt_mutations_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data["retry_semantics" if kind == "source" else kind])
    changed["schema_version"] = 999
    with pytest.raises((helper.InitializerError, replay.ConformanceError)):
        if kind == "source":
            helper.validate_structure(
                data["semantics"], dict(sources, retry_semantics=changed)
            )
        elif kind == "semantics":
            helper.validate_structure(changed, sources)
        else:
            replay.validate_structure(changed, data["semantics"])


@pytest.mark.parametrize("kind", ["semantics", "conformance"])
def test_exact_cli_rebuild(receipts, kind):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private Unicorn PYTHONPATH")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts" / f"itb_native_tree_node_initializer_{kind}.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources if kind == "semantics" else ["semantics"]:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
