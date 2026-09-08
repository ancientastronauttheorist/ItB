"""Predecessor sentinel, ancestor writes and independent inorder boundaries."""

import copy, hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from src.observatory import native_tree_predecessor_semantics as helper
from src.observatory import native_tree_predecessor_conformance as replay

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
NIL = 0x10000000


def inorder(nodes):
    result = []

    def walk(a):
        if a == NIL:
            return
        walk(nodes[a]["left"])
        result.append(a)
        walk(nodes[a]["right"])

    normal = [a for a in nodes if a != NIL]
    if normal:
        walk(next(a for a in normal if nodes[a]["parent"] == NIL))
    return result


@pytest.mark.parametrize("shape", helper.SHAPES)
def test_every_start_matches_independent_inorder(shape):
    nodes = helper.tree_fixture(shape)
    ordered = inorder(nodes)
    for start in nodes:
        expected = (
            (ordered[-1] if ordered else NIL)
            if start == NIL
            else (ordered[ordered.index(start) - 1] if ordered.index(start) else NIL)
        )
        result = helper.predecessor_spec(nodes, start)
        assert result["predecessor"] == expected and result["inorder_corollary"]


@pytest.mark.parametrize("alignment", range(16))
def test_climb_writes_each_ancestor_then_head(alignment):
    result = helper.model_case("left_chain", NIL + 64, alignment, 128, df=1)
    assert result["outcome"]["slot_write_nodes"] == [
        NIL + 128,
        NIL + 192,
        NIL + 256,
        NIL,
    ]
    assert [e["value"] for e in result["events"] if e["access"] == "write"] == [
        NIL + 128,
        NIL + 192,
        NIL + 256,
        NIL,
    ]
    assert (
        result["registers"]["ecx"] == NIL and result["registers"]["eax"] == 0x03001000
    )
    assert (
        result["registers"]["esp"] == 0x02002000 + alignment + 4 and result["df"] == 1
    )
    assert result["flags"] == dict(CF=0, PF=1, AF=0, ZF=1, SF=0, OF=0)


@pytest.mark.parametrize("flag,sign,parity", [(1, 0, 0), (128, 1, 0), (255, 1, 1)])
def test_head_flags_and_empty_self_store(flag, sign, parity):
    result = helper.model_case("empty", NIL, sentinel_byte=flag)
    assert result["outcome"]["slot_write_nodes"] == [NIL]
    assert result["registers"]["ecx"] == 0x03001000
    assert result["flags"] == dict(CF=0, PF=parity, AF=0, ZF=0, SF=sign, OF=0)
    assert [e["address"] for e in result["events"] if e["access"] == "read"] == [
        0x03001000,
        NIL + 13,
        NIL + 8,
        0x02002000,
    ]


def test_noncanonical_head_is_structural_not_global_maximum():
    nodes = helper.tree_fixture("balanced", canonical_head=False)
    result = helper.predecessor_spec(nodes, NIL)
    assert result["predecessor"] == NIL + 64 and not result["inorder_corollary"]
    assert inorder(nodes)[-1] == NIL + 448


def test_left_subtree_rightmost_cursor_and_slot():
    result = helper.model_case("balanced", NIL + 256, sentinel_byte=255)
    assert result["outcome"]["predecessor"] == NIL + 192
    assert result["registers"]["ecx"] == NIL + 192
    assert result["outcome"]["slot_write_nodes"] == [NIL + 192]


@pytest.mark.parametrize(
    "mutation", ["cycle", "bad_parent", "two_sentinels", "unmapped", "overlap"]
)
def test_invalid_topologies_rejected(mutation):
    nodes = helper.tree_fixture("balanced")
    start = NIL + 64
    if mutation == "cycle":
        nodes[start]["parent"] = start
    elif mutation == "bad_parent":
        nodes[start]["parent"] = NIL
    elif mutation == "two_sentinels":
        nodes[start]["sentinel"] = 1
    elif mutation == "unmapped":
        nodes[start]["left"] = 0xDEADBEEF
    else:
        nodes[NIL + 1] = nodes.pop(start)
        start = NIL + 1
    with pytest.raises(helper.PredecessorError):
        helper.predecessor_spec(nodes, start)


@pytest.mark.parametrize(
    "args",
    [
        dict(alignment=True),
        dict(alignment=16),
        dict(df=True),
        dict(df=2),
        dict(sentinel_byte=0),
        dict(canonical_head=1),
    ],
)
def test_invalid_fixture_parameters_rejected(args):
    with pytest.raises((helper.PredecessorError, helper.successor.SuccessorError)):
        helper.model_case("single", NIL + 64, **args)


def test_independent_event_oracle_and_nop_no_access():
    vector = dict(
        shape="left_chain",
        start=NIL + 64,
        alignment=7,
        sentinel_byte=255,
        canonical_head=True,
        df=1,
    )
    fixture = helper.case_fixture(**vector)
    expected = replay.oracle(vector, fixture)
    model = helper.model_case(**vector)
    assert model["events"] == expected["events"]
    assert "0x0007188c" in model["trace_rvas"]
    assert len([e for e in model["events"] if e["access"] == "write"]) == 4


@pytest.fixture(scope="module")
def receipts():
    paths = {
        k: PROGRAMS / (PREFIX + v + ".json")
        for k, v in dict(
            program_facts="program_facts",
            successor_semantics="native_lua_tree_successor_semantics",
            semantics="native_tree_predecessor_semantics",
            conformance="native_tree_predecessor_conformance",
        ).items()
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
            "641f99378def5e6f885d99e6a96b362134ae1a818651c11b57b89df046d7558d",
        ),
        (
            "conformance",
            replay.encode_conformance,
            "ea89dc8bfc2f5c89a2efe4b58ae18b3309e2f5387b4159ac1ea11b25722a661a",
        ),
    ]:
        raw = paths[kind].read_bytes()
        assert raw == encode(data[kind]).encode() and b"\r\n" not in raw
        assert hashlib.sha256(raw).hexdigest() == sha
    assert (
        data["conformance"]["executed_rvas"]
        == data["semantics"]["model_evidence"]["instruction_union_rvas"]
    )
    assert (
        data["semantics"]["summary"]["cases"] == 14400
        and data["conformance"]["summary"]["cases"] == 4416
    )


@pytest.mark.parametrize("kind", ["semantics", "conformance", "source"])
def test_receipt_mutation_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data["successor_semantics" if kind == "source" else kind])
    changed["schema_version"] = 999
    with pytest.raises((helper.PredecessorError, replay.ConformanceError)):
        if kind == "semantics":
            helper.validate_structure(changed, sources)
        elif kind == "source":
            helper.validate_structure(
                data["semantics"], dict(sources, successor_semantics=changed)
            )
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
        str(ROOT / "scripts" / f"itb_native_tree_predecessor_{kind}.py"),
        "build",
        "--executable",
        executable,
    ]
    for key in sources if kind == "semantics" else ["semantics"]:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths[kind].read_bytes()
