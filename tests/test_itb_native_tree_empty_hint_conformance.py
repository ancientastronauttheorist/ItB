"""Empty hint composition, protected ancestor, normal SEH and cookie return."""

import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.observatory import native_tree_empty_hint_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"
CANONICAL = "eda3e3b090fe4b36b40b2158c3c65767f3604b40574f3a89244c4995a4fde0bf"
RAW = "4629b131e3829992605be0e789fad203bc033126c9654dcf2c117dbbb21a618c"


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def event(access, address, value, width=4):
    return dict(access=access, address=address, width=width, value=value)


def case(**changes):
    v = dict(c.vectors()[0], **changes)
    f = c._fixture(v)
    return v, f, c._expected(v, f)


@pytest.mark.parametrize("previous", [0, 0xFFFFFFFF, 0x18001000, 0x87654321])
@pytest.mark.parametrize("cookie", [0, 1, 0x80000000, 0xFFFFFFFF, 0xA12598FD])
def test_normal_registration_cookie_and_return_abi(previous, cookie):
    v, f, e = case(previous_seh=previous, cookie=cookie, frame_alignment=15, df=1)
    h = f["s"]
    encoded = cookie ^ (h - 4)
    assert [a for a in e["events"] if a["address"] == 0] == [
        event("read", 0, previous),
        event("write", 0, h - 16),
        event("write", 0, previous),
    ]
    assert read(e["pages"], 0) == previous
    assert read(e["pages"], h - 16) == previous
    if previous:
        assert previous & ~0xFFF not in f["pages"]
        assert not any(a["address"] == previous for a in e["events"])
    assert read(e["pages"], h - 12) == 0x007D0EA0
    assert not any(a["address"] == 0x007D0EA0 for a in e["events"])
    assert [a for a in e["events"] if a["address"] == c.COOKIE] == [
        event("read", c.COOKIE, cookie),
        event("read", c.COOKIE, cookie),
    ]
    for slot in (h - 24, h - 68):
        assert read(e["pages"], slot) == encoded
        assert event("write", slot, encoded) in e["events"]
        assert event("read", slot, encoded) in e["events"]
    assert [a for a in e["events"] if a["address"] == h - 56] == [
        event("write", h - 56, f["registers"]["ebx"]),
        event("read", h - 56, f["registers"]["ebx"]),
        event("write", h - 56, c.BASE + 0x2E84D8),
        event("read", h - 56, c.BASE + 0x2E84D8),
    ]
    assert e["registers"] == dict(f["registers"], eax=c.OUTPUT, ecx=cookie, esp=h + 20)
    assert all(
        e["registers"][r] == f["registers"][r]
        for r in ("ebx", "ebp", "esi", "edi", "edx")
    )
    assert e["flags"] == 0x44 and e["endpoint"] == read(f["pages"], h)
    # Restore the previous chain before recovering nonvolatile registers and
    # issuing the normal cookie check; retain the two distinct cookie copies.
    assert e["events"][-12:] == [
        event("read", h - 16, previous),
        event("write", 0, previous),
        event("read", h - 68, encoded),
        event("read", h - 64, f["registers"]["edi"]),
        event("read", h - 60, f["registers"]["esi"]),
        event("read", h - 56, f["registers"]["ebx"]),
        event("read", h - 24, encoded),
        event("write", h - 56, c.BASE + 0x2E84D8),
        event("read", c.COOKIE, cookie),
        event("read", h - 56, c.BASE + 0x2E84D8),
        event("read", h - 4, f["registers"]["ebp"]),
        event("read", h, e["endpoint"]),
    ]


def test_child_entry_frame_and_unread_opaque_arguments():
    _, f, e = case(node_alignment=31, frame_alignment=7)
    h, n = f["s"], f["node"]
    expected_call = [
        event("write", h - 72, n),
        event("write", h - 76, n),
        event("read", c.attachment.TREE, c.attachment.HEAD),
        event("write", h - 80, c.attachment.HEAD),
        event("write", h - 84, 1),
        event("write", h - 88, c.OUTPUT),
        event("write", h - 92, c.BASE + 0x2E835D),
        event("write", h - 96, h - 4),
        event("write", h - 100, c.OUTPUT),
        event("write", h - 104, f["registers"]["edi"]),
    ]
    start = e["events"].index(expected_call[0])
    assert e["events"][start : start + len(expected_call)] == expected_call
    assert h - 92 + 24 == h - 68
    child_return = e["events"].index(event("read", h - 92, c.BASE + 0x2E835D))
    edi_restore = e["events"].index(event("read", h - 104, f["registers"]["edi"]))
    assert edi_restore < child_return - 3
    assert e["events"][child_return - 3 : child_return + 1] == [
        event("write", c.OUTPUT, n),
        event("read", h - 100, c.OUTPUT),
        event("read", h - 96, h - 4),
        event("read", h - 92, c.BASE + 0x2E835D),
    ]
    for offset, opaque in ((8, 0xDEADA000), (12, 0xDEADB000)):
        assert read(f["pages"], h + offset) == opaque
        assert read(e["pages"], h + offset) == opaque
        assert opaque & ~0xFFF not in f["pages"]
        assert not any(a["address"] in (h + offset, opaque) for a in e["events"])


def test_entire_corpus_protected_pages_and_104_byte_ancestor():
    for v in c.vectors():
        f = c._fixture(v)
        e = c._expected(v, f)
        h, n, regs = f["s"], f["node"], f["registers"]
        expected = {page: bytearray(value) for page, value in f["pages"].items()}

        def put(address, value, width=4):
            for i, byte in enumerate(value.to_bytes(width, "little")):
                expected[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

        encoded = v["cookie"] ^ (h - 4)
        stack = {
            -4: regs["ebp"],
            -8: 0,
            -12: 0x007D0EA0,
            -16: v["previous_seh"],
            -20: h - 68,
            -24: encoded,
            -32: n,
            -36: c.attachment.TREE,
            -40: c.OUTPUT,
            -48: n,
            -56: c.BASE + 0x2E84D8,
            -60: regs["esi"],
            -64: regs["edi"],
            -68: encoded,
            -72: n,
            -76: n,
            -80: c.attachment.HEAD,
            -84: 1,
            -88: c.OUTPUT,
            -92: c.BASE + 0x2E835D,
            -96: h - 4,
            -100: c.OUTPUT,
            -104: regs["edi"],
        }
        for offset, value in stack.items():
            put(h + offset, value)
        for offset in (0, 4, 8):
            put(c.attachment.HEAD + offset, n)
        put(c.attachment.TREE + 4, 1)
        put(n + 12, 1, 1)
        put(c.OUTPUT, n)
        assert {page: bytes(value) for page, value in expected.items()} == e["pages"]
        stack_writes = [
            a["address"]
            for a in e["events"]
            if a["access"] == "write"
            and c.attachment.STACK <= a["address"] < c.attachment.STACK + 0x2000
        ]
        assert min(stack_writes) == h - 104 and max(stack_writes) == h - 4
        assert read(e["pages"], n + 4) == c.attachment.HEAD
        assert read(e["pages"], n + 12, 1) == 1
        assert read(e["pages"], n + 14, 2) == 0xA5A5


@pytest.mark.parametrize(
    "field,value",
    [
        ("previous_seh", -1),
        ("previous_seh", 2**32),
        ("previous_seh", True),
        ("cookie", -1),
        ("cookie", 2**32),
        ("cookie", False),
        ("node_alignment", 32),
        ("node_alignment", True),
        ("frame_alignment", 16),
        ("frame_alignment", -1),
        ("df", 2),
        ("nil_marker", 0),
        ("nil_marker", 256),
    ],
)
def test_malformed_scalar_alignment_and_marker_rejected(field, value):
    with pytest.raises(RuntimeError):
        c._fixture(dict(c.vectors()[0], **{field: value}))


@pytest.fixture(scope="module")
def receipts():
    suffix = {
        "program_facts": "program_facts",
        "balancing": "native_tree_balancing_conformance",
        "cookie_return": "native_lua_class_vector_return_conformance",
        "evidence": "native_tree_empty_hint_conformance",
    }
    paths = {k: Path(str(PREFIX) + name + ".json") for k, name in suffix.items()}
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in c.SOURCE_PINS}


def test_seal_raw_identity_and_bounded_coverage(receipts):
    paths, data, sources = receipts
    evidence = data["evidence"]
    assert c.validate_structure(evidence, sources)["status"] == "structurally_verified"
    assert c.SEALED_SHA256 == c._canonical_sha256(evidence) == CANONICAL
    raw = paths["evidence"].read_bytes()
    assert hashlib.sha256(raw).hexdigest() == RAW
    assert raw == c.encode_conformance(evidence).encode() and b"\r\n" not in raw
    assert evidence["summary"] == dict(
        cases=1600,
        instruction_bytes=641,
        static_sites=232,
        executed_sites=86,
        normal_returns=1600,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    outer_sites = {
        p["rva"]
        for p in evidence["body"]["points"]
        if not 0x7D0A0 <= int(p["rva"], 16) < 0x7D294
    }
    assert outer_sites <= set(evidence["executed_rvas"])
    assert evidence["negative_controls"] == [
        dict(kind=k, rejected=True) for k in ("ancestor", "padding", "seh", "cookie")
    ]


@pytest.mark.parametrize(
    "kind", ["evidence", "program_facts", "balancing", "cookie_return"]
)
def test_modified_evidence_or_source_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises(RuntimeError):
        c.validate_structure(
            changed if kind == "evidence" else data["evidence"],
            sources if kind == "evidence" else dict(sources, **{kind: changed}),
        )


def test_exact_cli_rebuild(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_empty_hint_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for key in sources:
        args += ["--" + key.replace("_", "-"), str(paths[key])]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stderr == b"" and result.stdout == paths["evidence"].read_bytes()
