"""Independent lower-bound, unsigned byte and native frame boundary checks."""

import copy, hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from src.observatory import native_tree_lower_bound_semantics as helper
from src.observatory import native_tree_lower_bound_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


def node(key, left=None, right=None):
    return dict(key=key, left=left, right=right)


@pytest.mark.parametrize(
    "query", [b"", b"a", b"ab", b"m", b"n", b"z", b"\x80", b"\xff", b"\xff\xff"]
)
def test_ordered_result_matches_independent_inorder_minimum(query):
    nodes = [
        node(b"m", 1, 2),
        node(b"a", 3, 4),
        node(b"\x80", 5, 6),
        node(b""),
        node(b"ab"),
        node(b"z"),
        node(b"\xff"),
    ]
    order = [3, 1, 4, 0, 5, 2, 6]
    expected = next((i for i in order if nodes[i]["key"] >= query), None)
    relation = helper.traversal_spec(nodes, 0, query)
    result = helper.model_case(nodes, 0, query)
    assert relation["ordered"] and relation["candidate"] == expected
    assert relation["minimum_lower_bound"] == expected
    assert result["registers"]["eax"] == (
        helper.HEAD if expected is None else helper.NODES + 64 * expected
    )


def test_duplicates_choose_first_inorder_match():
    nodes = [node(b"a", 1, 2), node(b"a"), node(b"a")]
    relation = helper.traversal_spec(nodes, 0, b"a")
    assert relation["candidate"] == relation["minimum_lower_bound"] == 1
    assert relation["path"] == [0, 1]


def test_unordered_tree_has_only_structural_path_claim():
    nodes = [node(b"a", 1, 2), node(b"z"), node(b"")]
    relation = helper.traversal_spec(nodes, 0, b"a")
    assert relation["candidate"] == 1 and not relation["ordered"]
    assert relation["minimum_lower_bound"] is None
    assert min(n["key"] for n in nodes if n["key"] >= b"a") == b"a"


@pytest.mark.parametrize(
    "query,expected", [(b"\x7f", 0), (b"\x80", 0), (b"\xff", None)]
)
def test_unsigned_high_bytes(query, expected):
    assert helper.traversal_spec([node(b"\x80")], 0, query)["candidate"] == expected


@pytest.mark.parametrize("nil", [1, 127, 128, 255])
def test_empty_tree_never_reads_query_or_saves_ebx(nil):
    fixture = helper.case_fixture([], None, None, nil_flag=nil)
    result = helper.model_case([], None, None, nil_flag=nil)
    assert result["registers"]["eax"] == helper.HEAD
    assert result["registers"]["ecx"] == fixture["registers"]["ecx"]
    assert result["registers"]["edx"] == fixture["registers"]["edx"]
    assert result["registers"]["esp"] == fixture["stack"] + 8
    assert "0x002e82a3" not in result["trace_rvas"]
    forbidden = {fixture["stack"] + 4, fixture["stack"] - 16, helper.ARG, helper.QUERY}
    assert not any(e["address"] in forbidden for e in result["events"])
    assert result["arithmetic_flags"] == dict(
        cf=0, pf=int(nil.bit_count() % 2 == 0), af=0, zf=0, sf=nil >> 7, of=0
    )


@pytest.mark.parametrize(
    "key,query,cursor,dl",
    [
        (b"", b"", 0, 0),
        (b"a", b"a", 2, 0),
        (b"ab", b"ab", 2, 0),
        (b"abc", b"abc", 4, 0),
        (b"ab", b"ac", 0, ord("b")),
        (b"ab", b"a", 0, ord("b")),
        (b"a", b"b", 0, ord("a")),
    ],
)
def test_paired_byte_cursor_and_preserved_edx_bits(key, query, cursor, dl):
    fixture = helper.case_fixture([node(key)], 0, query, seed=255)
    result = helper.model_case([node(key)], 0, query, seed=255)
    assert result["registers"]["ecx"] == helper.KEYS + cursor
    assert result["registers"]["edx"] == (fixture["registers"]["edx"] & 0xFFFFFF00) | dl
    assert not any(e["address"] == helper.QUERY * 2 for e in result["events"])


def test_deep_maximum_length_prefix_chain():
    nodes = [
        node(b"p" * 63 + bytes([i + 1]), right=i + 1 if i < 30 else None)
        for i in range(31)
    ]
    result = helper.model_case(
        nodes, 0, b"p" * 63 + b"\xff", frame_alignment=15, nil_flag=255
    )
    assert result["relation"]["path"] == list(range(31))
    assert result["relation"]["candidate"] is None
    assert len(result["trace_rvas"]) < 20000


@pytest.mark.parametrize(
    "nodes,root,query",
    [
        ([node(b"a", 0)], 0, b"a"),
        ([node(b"a", 1, 1), node(b"b")], 0, b"a"),
        ([node(b"a"), node(b"b")], 0, b"a"),
        ([node(b"a", True)], 0, b"a"),
        ([node(b"a")], True, b"a"),
        ([node(b"a\0")], 0, b"a"),
        ([node(b"a")], 0, b"a\0"),
        ([node(b"a" * 65)], 0, b"a"),
        ([node(b"a")], 0, "a"),
        ([node(b"a")] * 32, 0, b"a"),
    ],
)
def test_invalid_structural_or_string_premises(nodes, root, query):
    with pytest.raises(helper.LowerBoundError):
        helper.traversal_spec(nodes, root, query)


@pytest.mark.parametrize("nil", [0, 256, True, -1])
def test_invalid_sentinel_flag(nil):
    with pytest.raises(helper.LowerBoundError):
        helper.model_case([], None, None, nil_flag=nil)


def test_independent_replay_oracle():
    vector = dict(
        shape="independent",
        nodes=[dict(key=[128], left=None, right=None)],
        root=0,
        query=[255],
        frame_alignment=7,
        nil_flag=128,
        seed=0,
    )
    fixture = helper.case_fixture(**helper.unpack(vector))
    result = replay.oracle(vector, fixture)
    assert result["candidate"] is None and result["path"] == [0]
    assert result["registers"]["eax"] == helper.HEAD
    assert result["flags"] == 0x80


@pytest.fixture(scope="module")
def receipts():
    paths = {
        k: PROGRAMS / (PREFIX + v + ".json")
        for k, v in {
            "program_facts": "program_facts",
            "chain": "native_lua_class_return_helper_chain",
            "semantics": "native_tree_lower_bound_semantics",
            "conformance": "native_tree_lower_bound_conformance",
        }.items()
    }
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in helper.SOURCE_PINS}


def test_receipt_pins_and_lf_encoding(receipts):
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
            "06e62158b0beec225c2256eaf70eac4a4a8ce37425149af5d2ce250cf4079915",
        ),
        (
            "conformance",
            replay.encode_conformance,
            "8a9fb9eb800671ca1935dcf848f6631f01fc8d64beecc9dcbe9124fdec0fa691",
        ),
    ]:
        raw = paths[kind].read_bytes()
        assert raw == encode(data[kind]).encode() and b"\r\n" not in raw
        assert hashlib.sha256(raw).hexdigest() == sha
    assert (
        data["conformance"]["executed_rvas"]
        == data["semantics"]["model_evidence"]["instruction_union_rvas"]
    )


@pytest.mark.parametrize("kind", ["semantics", "conformance", "source"])
def test_modified_receipts_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data["chain" if kind == "source" else kind])
    changed["schema_version"] = 999
    with pytest.raises((helper.LowerBoundError, replay.ConformanceError)):
        if kind == "semantics":
            helper.validate_structure(changed, sources)
        elif kind == "source":
            helper.validate_structure(data["semantics"], dict(sources, chain=changed))
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
        str(ROOT / "scripts" / f"itb_native_tree_lower_bound_{kind}.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources if kind == "semantics" else ["semantics"]:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
