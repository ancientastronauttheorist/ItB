"""Black-parent attachment returns and immutable exact replay evidence."""

import copy, hashlib, json, os, subprocess, sys
from pathlib import Path
import pytest
from src.observatory import native_tree_attachment_return_conformance as c

ROOT = Path(__file__).resolve().parents[1]
PREFIX = ROOT / "data/observatory/programs/windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize("profile", ["empty", "root_left", "root_right"])
@pytest.mark.parametrize("color", [1, 255])
def test_root_color_result_and_restored_registers(profile, color):
    v = dict(
        profile=profile,
        count=0 if profile == "empty" else 1,
        selector=int(profile == "root_left"),
        node_alignment=7,
        frame_alignment=15,
        df=1,
        parent_color=color,
    )
    f = c._fixture(v)
    e = c._expected(v, f)
    n = f["node"]
    root = n if profile == "empty" else c.attachment.ROOT
    assert e["root"] == root and e["pages"][root & ~0xFFF][(root & 0xFFF) + 12] == 1
    assert (
        int.from_bytes(
            e["pages"][c.OUTPUT & ~0xFFF][c.OUTPUT & 0xFFF : (c.OUTPUT & 0xFFF) + 4],
            "little",
        )
        == n
    )
    assert (
        e["registers"]["eax"] == c.OUTPUT
        and e["registers"]["ecx"] == f["parent"]
        and e["registers"]["esp"] == f["s"] + 24
    )
    assert all(
        e["registers"][r] == f["registers"][r]
        for r in ("ebx", "ebp", "esi", "edi", "edx")
    )
    assert e["flags"] == (0 if color == 1 else 0x84)
    assert [a["address"] for a in e["events"][-11:]] == [
        n + 4,
        f["parent"] + 12,
        c.attachment.TREE,
        f["s"] - 12,
        c.attachment.HEAD + 4,
        root + 12,
        f["s"] + 4,
        c.OUTPUT,
        f["s"] - 8,
        f["s"] - 4,
        f["s"],
    ]


@pytest.mark.parametrize("color", [0, 128, True, -1, 256])
def test_outside_selected_black_parent_fixture_rejected(color):
    v = dict(c.vectors()[0], parent_color=color)
    with pytest.raises(c.ConformanceError):
        c._fixture(v)


@pytest.fixture(scope="module")
def receipts():
    paths = {
        k: Path(
            str(PREFIX)
            + ("native_tree_attachment_conformance" if k == "attachment" else k)
            + ".json"
        )
        for k in c.SOURCE_PINS
    }
    paths["evidence"] = Path(
        str(PREFIX) + "native_tree_attachment_return_conformance.json"
    )
    data = {k: json.loads(p.read_bytes()) for k, p in paths.items()}
    return paths, data, {k: data[k] for k in c.SOURCE_PINS}


def test_receipt_seal_and_raw_encoding(receipts):
    paths, data, sources = receipts
    raw = paths["evidence"].read_bytes()
    assert (
        c.validate_structure(data["evidence"], sources)["status"]
        == "structurally_verified"
    )
    assert raw == c.encode_conformance(data["evidence"]).encode() and b"\r\n" not in raw
    assert (
        hashlib.sha256(raw).hexdigest()
        == "87c2507184204304c6a9cd9e01c0edf0670b3c9089f78dfb38a6c3ad031abc36"
    )
    assert data["evidence"]["summary"]["executed_sites"] == 48


@pytest.mark.parametrize("kind", ["evidence", "attachment"])
def test_mutated_receipts_rejected(receipts, kind):
    _, data, sources = receipts
    changed = copy.deepcopy(data[kind])
    changed["schema_version"] = 999
    with pytest.raises((c.ConformanceError, RuntimeError)):
        (
            c.validate_structure(changed, sources)
            if kind == "evidence"
            else c.validate_structure(
                data["evidence"], dict(sources, attachment=changed)
            )
        )


def test_exact_cli_rebuild(receipts):
    exe = os.environ.get("ITB_EXACT_EXE")
    if not exe:
        pytest.skip("requires private exact executable and Unicorn runtime")
    paths, _, sources = receipts
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_tree_attachment_return_conformance.py"),
        "build",
        "--executable",
        exe,
    ]
    for k in sources:
        args += ["--" + k.replace("_", "-"), str(paths[k])]
    r = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180)
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
