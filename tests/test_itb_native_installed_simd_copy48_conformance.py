"""Independent installed copy48 scalar-tail and full retained-state equations."""

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
from src.observatory import native_installed_simd_copy48_semantics as m
from src.observatory import native_installed_simd_copy48_conformance as c
from tests import test_itb_native_assertion_helper_parent_dispatch_conformance as d

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
TRACE = (
    (
        0x36E580,
        0x36E581,
        0x36E582,
        0x36E586,
        0x36E58A,
        0x36E58E,
        0x36E590,
        0x36E592,
        0x36E594,
        0x36E596,
        0x36E598,
        0x36E59A,
        0x36E5A0,
        0x36E5A3,
        0x36E5A9,
        0x36E5AF,
        0x36E5B1,
        0x36E5B9,
        0x36EA4D,
        0x36EA4F,
        0x36EA51,
        0x36EA53,
        0x36EA56,
        0x36EA58,
        0x36EA5A,
        0x36EA60,
        0x36EA64,
        0x36EA69,
        0x36EA6D,
        0x36EA72,
        0x36EA75,
        0x36EA78,
        0x36EA79,
        0x36EA7B,
        0x36EA7E,
        0x36EA80,
        0x36EA82,
        0x36EA85,
    )
    + (0x36EA87, 0x36EA89, 0x36EA8B, 0x36EA8E, 0x36EA91, 0x36EA94) * 4
    + (
        0x36EA96,
        0x36EA98,
        0x36EA9B,
        0x36EAB0,
        0x36EAB4,
        0x36EAB5,
        0x36EAB6,
    )
)
EVENT_SITES = (
    (
        0x36E580,
        0x36E581,
        0x36E582,
        0x36E586,
        0x36E58A,
        0x36E5B1,
        0x36EA60,
        0x36EA60,
        0x36EA64,
        0x36EA64,
        0x36EA69,
        0x36EA69,
        0x36EA6D,
        0x36EA6D,
    )
    + (0x36EA87, 0x36EA89) * 4
    + (0x36EAB0, 0x36EAB4, 0x36EAB5, 0x36EAB6)
)


def independent(fixture):
    pages = fixture["pages"]
    original = fixture["registers"]
    s, o, n = original["esp"], fixture["source"], fixture["destination"]
    snapshot = d.blob(pages, o, 48)
    events = [
        dict(access="write", address=s - 4, width=4, value=original["edi"]),
        dict(access="write", address=s - 8, width=4, value=original["esi"]),
        dict(access="read", address=s + 8, width=4, value=o),
        dict(access="read", address=s + 12, width=4, value=48),
        dict(access="read", address=s + 4, width=4, value=n),
        dict(access="read", address=0x00893F30, width=4, value=0x93939393),
    ]
    for access, at in (("read", o), ("write", n)):
        for offset in (0, 8, 16, 24):
            events.append(
                dict(
                    access=access,
                    address=at + offset,
                    width=8,
                    value=int.from_bytes(snapshot[offset : offset + 8], "little"),
                )
            )
    for offset in (32, 36, 40, 44):
        value = int.from_bytes(snapshot[offset : offset + 4], "little")
        events += [
            dict(access="read", address=o + offset, width=4, value=value),
            dict(access="write", address=n + offset, width=4, value=value),
        ]
    events += [
        dict(access="read", address=s + 4, width=4, value=n),
        dict(access="read", address=s - 8, width=4, value=original["esi"]),
        dict(access="read", address=s - 4, width=4, value=original["edi"]),
        dict(access="read", address=s, width=4, value=fixture["return_address"]),
    ]
    output = copy.deepcopy(pages)
    for row in events:
        if row["access"] == "write":
            at, width, value = (row[k] for k in ("address", "width", "value"))
            for i, byte in enumerate(value.to_bytes(width, "little")):
                page = (at + i) & ~4095
                b = bytearray(output[page])
                b[(at + i) & 4095] = byte
                output[page] = bytes(b)
    return dict(
        pages=output,
        source_snapshot=snapshot,
        registers=dict(
            original,
            eax=n,
            ecx=0,
            edx=int.from_bytes(snapshot[44:48], "little"),
            esp=s + 4,
        ),
        xmm=dict(
            fixture["xmm"],
            xmm0=int.from_bytes(snapshot[:16], "little"),
            xmm1=int.from_bytes(snapshot[16:32], "little"),
        ),
        flags=0x44,
        flag_mask=0x8C5,
        df=0,
        endpoint=fixture["return_address"],
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
        events=events,
    )


def test_exact_matrix_geometry_and_new_scalar_tail():
    assert c.vectors() == [
        dict(alignment=a, profile=p) for a in range(16) for p in range(3)
    ]
    assert len(c.SOURCE_PINS) == 3
    assert len(TRACE) == 69 and len(set(TRACE)) == 51
    assert len(EVENT_SITES) == 26
    for vector in c.vectors():
        fixture = c._fixture(vector)
        a = vector["alignment"]
        assert (
            fixture["registers"]["esp"],
            fixture["source"],
            fixture["destination"],
            fixture["return_address"],
            fixture["entry_flags"],
        ) == (0x30001000 + a, 0x06002800 + a, 0x06004800 + a, 0x04000000, 0x246)
        assert set(fixture["pages"]) == {
            0x06002000,
            0x06003000,
            0x06004000,
            0x30000000,
            0x30001000,
            0x00893000,
        }
        if vector["profile"] == 2:
            snapshot = d.blob(fixture["pages"], fixture["source"], 48)
            assert snapshot == (0x00000000).to_bytes(4, "little") + (
                0x06000100
            ).to_bytes(4, "little") + b"".join(
                [(0).to_bytes(4, "little") + (0x06000100).to_bytes(4, "little")] * 4
            ) + (
                0
            ).to_bytes(
                4, "little"
            ) + (
                0xD15C0048
            ).to_bytes(
                4, "little"
            )
        assert all(type(v) is int and v != 0 for v in fixture["xmm"].values())


@pytest.mark.parametrize("alignment", range(16))
def test_all_profiles_independent_snapshot_pages_gprs_xmms_events_and_trace(alignment):
    for profile in range(3):
        vector = dict(alignment=alignment, profile=profile)
        fixture = c._fixture(vector)
        before = copy.deepcopy(fixture)
        wanted = independent(fixture)
        result = m.apply(**fixture)
        assert set(result) == set(wanted) and result == wanted
        assert c._expected(vector, fixture) == wanted
        assert fixture == before
        assert wanted["pages"][0x00893000] == before["pages"][0x00893000]
        assert d.blob(wanted["pages"], fixture["destination"] + 48, 24) == d.blob(
            before["pages"], fixture["destination"] + 48, 24
        )
        fixture["registers"]["eax"] ^= 1
        fixture["xmm"]["xmm7"] ^= 1
        fixture["pages"].clear()
        assert result == wanted


def test_arbitrary_installed_frame_cross_page_source_and_incoming_AF():
    fixture = c._fixture(dict(alignment=0, profile=1))
    fixture["source"] = 0x06002FF0
    fixture["destination"] = 0x060047E3
    fixture["registers"]["esp"] = 0x30001003
    for i, value in enumerate(
        (fixture["return_address"], fixture["destination"], fixture["source"], 48)
    ):
        d.patch(fixture["pages"], fixture["registers"]["esp"] + 4 * i, value)
    fixture["entry_flags"] |= 0x10
    assert m.apply(**fixture) == independent(fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "gpr_bool",
        "gpr_missing",
        "xmm_bool",
        "xmm_overflow",
        "xmm_missing",
        "pages_list",
        "page_mutable",
        "page_short",
        "page_missing",
        "source_bool",
        "source_wrap",
        "destination_overlap",
        "destination_adjacent",
        "stack_underflow",
        "frame_wrap",
        "frame_overlap",
        "return_zero",
        "return_data",
        "feature",
        "caller",
        "flags_bool",
        "df",
    ),
)
def test_actual_adapter_rejects_invalid_typed_geometry_or_installed_premises(kind):
    fixture = c._fixture(dict(alignment=7, profile=2))
    if kind == "gpr_bool":
        fixture["registers"]["eax"] = False
    elif kind == "gpr_missing":
        fixture["registers"].pop("eax")
    elif kind == "xmm_bool":
        fixture["xmm"]["xmm0"] = False
    elif kind == "xmm_overflow":
        fixture["xmm"]["xmm7"] = 2**128
    elif kind == "xmm_missing":
        fixture["xmm"].pop("xmm7")
    elif kind == "pages_list":
        fixture["pages"] = list(fixture["pages"].items())
    elif kind == "page_mutable":
        fixture["pages"][0x06002000] = bytearray(fixture["pages"][0x06002000])
    elif kind == "page_short":
        fixture["pages"][0x06002000] = fixture["pages"][0x06002000][:-1]
    elif kind == "page_missing":
        fixture["pages"].pop(0x06004000)
    elif kind == "source_bool":
        fixture["source"] = True
    elif kind == "source_wrap":
        fixture["source"] = 0xFFFFFFF0
    elif kind == "destination_overlap":
        fixture["destination"] = fixture["source"] + 32
    elif kind == "destination_adjacent":
        fixture["destination"] = fixture["source"] + 48
    elif kind == "stack_underflow":
        fixture["registers"]["esp"] = 7
    elif kind == "frame_wrap":
        fixture["registers"]["esp"] = 0xFFFFFFF0
    elif kind == "frame_overlap":
        fixture["registers"]["esp"] = fixture["source"] + 8
    elif kind == "return_zero":
        fixture["return_address"] = 0
    elif kind == "return_data":
        fixture["return_address"] = 0x06004000
    elif kind == "feature":
        d.patch(fixture["pages"], 0x00893F30, 0x93939391)
    elif kind == "caller":
        d.patch(fixture["pages"], fixture["registers"]["esp"] + 12, 32)
    elif kind == "flags_bool":
        fixture["entry_flags"] = False
    else:
        fixture["entry_flags"] |= 0x400
    with pytest.raises(m.Copy48Error):
        m.apply(**fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "bool_gpr",
        "xmm_changed",
        "page_changed",
        "source_changed",
        "flags_AF",
        "return_changed",
    ),
)
def test_finite_native_fixture_rejects_relabeling_and_typed_aliases(kind):
    vector = dict(alignment=15, profile=2)
    fixture = c._fixture(vector)
    if kind == "extra":
        fixture["unused"] = 0
    elif kind == "missing":
        fixture.pop("pages")
    elif kind == "bool_gpr":
        fixture["registers"]["eax"] = False
    elif kind == "xmm_changed":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind == "page_changed":
        d.patch(
            fixture["pages"],
            fixture["source"],
            d.word(fixture["pages"], fixture["source"]) ^ 1,
        )
    elif kind == "source_changed":
        fixture["source"] += 1
    elif kind == "flags_AF":
        fixture["entry_flags"] |= 0x10
    else:
        fixture["return_address"] += 1
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def sources():
    programs = ROOT / "data/observatory/programs"
    return {
        key: json.loads(
            (
                programs
                / (
                    "windows_build_13725832_31fe35265598_"
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ).read_text()
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.common.EXE_SHA256
    codes, points = c._load_code(data, image, sources())
    assert sum(map(len, codes.values())) == 169 and len(points) == 59
    return codes, points


def packet(alignment):
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = dict(alignment=alignment, profile=alignment % 3)
    fixture = c._fixture(vector)
    wanted = independent(fixture)
    observed = {}

    def capture(machine, ids, expected, installed):
        observed.update(
            registers={name: machine.reg_read(i) for name, i in ids.items()},
            xmm={
                name: machine.reg_read(getattr(x, "UC_X86_REG_" + name.upper()))
                for name in XMM
            },
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    observation = c._run_case(codes, points, vector, capture=capture)
    assert observed["registers"] == wanted["registers"]
    assert observed["xmm"] == wanted["xmm"]
    assert observed["pages"] == wanted["pages"]
    assert observed["flags"] & 0x8C5 == 0x44 and observed["flags"] & 0x400 == 0
    assert observed["endpoint"] == 0x04000000
    assert set(observation) == {
        "vector",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "endpoint",
        "trace_rvas",
        "events_sha256",
        "pages_sha256",
        "source_snapshot_sha256",
    }
    assert observation["vector"] == vector
    assert observation["registers"] == wanted["registers"]
    assert observation["xmm"] == wanted["xmm"]
    assert (
        observation["flags"],
        observation["flag_mask"],
        observation["df"],
        observation["endpoint"],
    ) == (0x44, 0x8C5, 0, 0x04000000)
    assert observation["trace_rvas"] == wanted["trace_rvas"]
    assert observation["events_sha256"] == d.canonical_hash(wanted["events"])
    assert observation["pages_sha256"] == {
        f"0x{at:08x}": hashlib.sha256(b).hexdigest()
        for at, b in sorted(wanted["pages"].items())
    }
    assert (
        observation["source_snapshot_sha256"]
        == hashlib.sha256(wanted["source_snapshot"]).hexdigest()
    )
    return observation


def controls():
    codes, points = native_inputs()
    vector = dict(alignment=15, profile=2)
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, vector, kind)
        assert str(caught.value) == reason, kind


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed private native runtime")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=2400,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        "utf-8", errors="replace"
    )[-4000:]


@pytest.mark.parametrize("alignment", range(16))
def test_actual_native_snapshot_tail_and_all_captured_state(alignment):
    isolated("packet", alignment)


def test_all_native_and_record_controls():
    isolated("controls")


PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_installed_simd_copy48_conformance.json")


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("primary has not published the native receipt")
    return json.loads(EVIDENCE.read_text())


def test_sealed_receipt_encoding_source_extents_and_independent_finite_totals(receipt):
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert d.canonical_hash(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == c.vectors()
    assert len(receipt["body"]["ranges"]) == 2 and len(receipt["body"]["points"]) == 59
    assert receipt["executed_rvas"] == [f"0x{rva:08x}" for rva in sorted(set(TRACE))]
    assert len(receipt["source_receipts"]) == 3
    assert {
        row["name"]: row["reason"] for row in receipt["negative_controls"]
    } == c.CONTROLS
    assert all(row["rejected"] is True for row in receipt["negative_controls"])
    for key, value in dict(
        cases=48,
        static_sites=59,
        executed_sites=51,
        instruction_bytes=169,
        native_instructions=3312,
        copied_bytes=2304,
        memory_events=1248,
        wide_reads=192,
        wide_writes=192,
        scalar_tail_reads=192,
        scalar_tail_writes=192,
        controls=len(c.CONTROLS),
        supplied_api_calls=0,
        allocations=0,
        frees=0,
        accounting_promotions=0,
    ).items():
        assert (
            type(receipt["summary"][key]) is int and receipt["summary"][key] == value
        ), key
    assert all(
        rva not in receipt["executed_rvas"]
        for rva in (
            "0x0036ea9d",
            "0x0036ea9f",
            "0x0036eaa1",
            "0x0036eaa2",
            "0x0036eaa3",
            "0x0036eaa4",
            "0x0036eaa6",
            "0x0036eaad",
        )
    )


@pytest.mark.parametrize(
    "kind",
    ("summary", "vector", "controls", "points", "range", "observation", "pin", "scope"),
)
def test_refreshed_receipt_mutations_reject(kind, receipt):
    value = copy.deepcopy(receipt)
    if kind == "summary":
        value["summary"]["copied_bytes"] += 1
    elif kind == "vector":
        value["vectors"][0]["profile"] = 2
    elif kind == "controls":
        value["negative_controls"][0]["rejected"] = False
    elif kind == "points":
        value["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        value["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observation":
        value["observations_sha256"] = "0" * 64
    elif kind == "pin":
        value["source_receipts"]["short_simd_semantics"]["canonical_sha256"] = "0" * 64
    else:
        value["scope"]["checked"].append("forged claim")
    with pytest.raises(c.ConformanceError):
        c.validate_structure(value, sources())


@pytest.mark.parametrize(
    "key", ("program_facts", "short_simd_semantics", "short_simd_conformance")
)
def test_all_source_dependencies_reject_tampering(key, receipt):
    supplied = sources()
    supplied[key]["analysis_kind"] = "forged"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(receipt, supplied)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_structure(command, receipt):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and reviewed runtime")
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_installed_simd_copy48_conformance.py"),
        command,
    ]
    for key, (kind, _) in c.SOURCE_PINS.items():
        path = PROGRAMS / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        args += ["--executable", executable]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=2400)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[
        -4000:
    ]
    if command == "build":
        assert result.stdout == EVIDENCE.read_bytes()
    else:
        output = json.loads(result.stdout)
        assert output["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert output["evidence_sha256"] == c.SEALED_SHA256


if __name__ == "__main__":
    faulthandler.disable()
    if sys.argv[1] == "packet":
        packet(int(sys.argv[2]))
    else:
        controls()
