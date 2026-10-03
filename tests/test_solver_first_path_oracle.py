"""Admission failure tests; original execution requires explicit local inputs."""
import os
from pathlib import Path
import sys

import pytest

from src.observatory.solver_first_path_oracle import BOARD, BASE, Machine, OracleError, OriginalSource, recipes


def test_rejects_wrong_original_build(tmp_path):
    pytest.importorskip("capstone")
    executable = tmp_path / "wrong.bin"
    executable.write_bytes(b"not the admitted original build")
    with pytest.raises(OracleError, match="executable identity differs"):
        OriginalSource(executable)


def test_failed_body_does_not_admit_partial_instruction_cache():
    cs = pytest.importorskip("capstone")
    source = object.__new__(OriginalSource)
    source.decoder = cs.Cs(cs.CS_ARCH_X86, cs.CS_MODE_32)
    source.points, source.verified = {}, {}
    source.owners = {0x1000: dict(entry_rva="0x00001000", body_size=4, body_sha256="0" * 64,
                                ranges=[dict(start_rva="0x00001000", size=4)])}
    source.bytes_at = lambda at, size: b"\x55\x8b\xec\xc3"
    with pytest.raises(OracleError, match="body bytes differ"):
        source.verify(0x1000)
    assert source.points == {} and source.verified == {}


@pytest.fixture(scope="module")
def source():
    executable = os.environ.get("ITB_ORIGINAL_QUERY_EXE")
    runtime = os.environ.get("ITB_ORIGINAL_QUERY_RUNTIME")
    if not executable or not runtime:
        pytest.skip("original executable and pinned local runtime not supplied")
    sys.path.insert(0, str(Path(runtime).resolve()))
    return OriginalSource(executable)


def machine(source):
    m = Machine(source)
    m.fixture(recipes()[2])
    m.call(0x3030, [])
    return m


def test_instruction_budget_rejection_and_fresh_call(source):
    m = machine(source)
    args = [BOARD + 0x1000, 0, 0, 2, 18]
    with pytest.raises(OracleError, match="budget exhausted"):
        m.call(0x174180, args, limit=1)
    assert len(m.trace) == 1
    receipt = m.call(0x174180, args)
    assert receipt["returned"]
    assert m.output(BOARD + 0x1000) == [[0, 1], [0, 2]]


def test_rejects_original_instruction_mutation(source):
    m = machine(source)
    m.uc.mem_write(BASE + 0x174180, b"\x90")
    with pytest.raises(OracleError, match="original instruction differs"):
        m.call(0x174180, [BOARD + 0x1000, 0, 0, 2, 18])


def test_rejects_non_instruction_entry(source):
    m = machine(source)
    entry = next(at + 1 for at, code in source.points.items() if 0x174180 <= at < 0x174190 and len(code) > 1)
    with pytest.raises(OracleError, match="non-instruction boundary"):
        m.call(entry, [BOARD + 0x1000, 0, 0, 2, 18])


def test_rejects_unknown_import(source):
    m = machine(source)
    stub = next(at for at, row in m.stubs.items() if row["name"] not in ("HeapAlloc", "HeapFree"))
    with pytest.raises(OracleError, match="unresolved import"):
        m.call(stub - BASE, [])


def test_rejects_wrong_heap_import_caller(source):
    m = machine(source)
    stub = next(at for at, row in m.stubs.items() if row["name"] == "HeapAlloc")
    with pytest.raises(OracleError, match="unadmitted import caller"):
        m.call(stub - BASE, [0x12345678, 0, 32])


@pytest.mark.parametrize("fault", ["freed", "overcapacity"])
def test_rejects_invalid_returned_vector(source, fault):
    m = machine(source)
    out = BOARD + 0x1000
    m.call(0x174180, [out, 0, 0, 2, 18])
    if fault == "freed":
        m.live.remove(m.get(out))
    else:
        m.put(out + 8, m.get(out) + m.allocations[m.get(out)] + 8)
    with pytest.raises(OracleError, match="vector ownership|vector geometry"):
        m.output(out)
