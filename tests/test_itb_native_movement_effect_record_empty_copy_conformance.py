"""Independent finite empty-path record-copy machine and receipt checks.

The handwritten pure test oracle supplies expectations. Production fixtures,
models and expected functions are only actual values under test.
"""

from __future__ import annotations
import copy
import faulthandler
import hashlib
import inspect
import json
import os
import subprocess
import sys
from collections import UserDict
from pathlib import Path

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
import pytest
from src.observatory import native_movement_effect_record_empty_copy_conformance as c
from tests.test_itb_native_movement_effect_record_empty_copy_semantics import (
    independent,
    check,
    strict_equal,
    store,
    read_bytes,
    TRACE,
    FIELDS,
    STRINGS,
    KEYS,
)

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (
    PREFIX + "native_movement_effect_record_empty_copy_conformance.json"
)
CLI = ROOT / "scripts/itb_native_movement_effect_record_empty_copy_conformance.py"
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
PAGES = (
    0,
    0x30000000,
    0x30001000,
    0x10000000,
    0x10001000,
    0x10002000,
    0x10003000,
    0x00893000,
)
BODY_PINS = {
    0x15B9B0: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    0x80D0: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
}
POINT_SHA = "45e4d085df78b3abdcc5b54404ebc16a36a8fb8ca41ec1c7c0eab9083c3d76df"
SELECTED = (0, 1, 2, 3, 4, 5, 21, 22, 23, 45, 46, 47)
OBS_KEYS = {
    "vector",
    "registers",
    "xmm",
    "eflags",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "trace_rvas",
    "events_sha256",
    "pages_sha256",
    "memory_event_count",
    "boundaries",
}
OBS_BOUNDARY_KEYS = {
    "kind",
    "name",
    "index",
    "registers",
    "xmm",
    "eflags",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "pages_sha256",
    "events_sha256",
}
ROLES = (
    "outer_entry",
    "string_entry",
    "string_return",
    "path_entry",
    "path_return",
    "reserve_entry",
    "reserve_return",
)
CONTROLS = {
    **{
        role + "_" + kind: "empty record copy " + role.replace("_", " ") + " differs"
        for role in ROLES
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    **{
        name: "empty record copy ordered memory differs"
        for name in ("caller_source", "source_size", "destination_capacity")
    },
    **{
        name: "empty record copy final pages differ"
        for name in (
            "field",
            "padding",
            "source",
            "source_padding",
            "source_capacity",
            "source_terminator",
            "stack_ancestor",
            "stack_padding",
            "seh",
            "cookie",
            "random_padding",
        )
    },
    **{
        name: "empty record copy final ABI differs"
        for name in (
            "final_gpr",
            "final_edx",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "empty record copy final events differ",
    "restored_write_record": "empty record copy final events differ",
    "trace_record": "empty record copy final native path differs",
}

SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
    "default_record": (
        "pe_native_movement_effect_record_default_conformance",
        "942fc246105c941a46ac73e7be432acdacad1428322888b76c0164aca49e673f",
    ),
    "empty_string_copy": (
        "pe_native_movement_empty_string_copy_conformance",
        "c3d9d8598d7aa922157397a27a58aeabf86732e9bb620625d602481dd90c18b1",
    ),
}


def canonical_hash(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
    ).hexdigest()


def page_hashes(pages):
    return {
        f"0x{p:08x}": hashlib.sha256(b).hexdigest() for p, b in sorted(pages.items())
    }


def all_vectors():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def independent_fixture(vector):
    a, p = vector["alignment"], vector["profile"]
    g, s, d = 0x30001000 + a, 0x10000FF0 + a, 0x10002FF0 + a
    pages = {
        page: bytes((i * 31 + j * 23 + p * 67) & 255 for j in range(4096))
        for i, page in enumerate(PAGES)
    }
    for at, value in (
        (g, 0x04000000),
        (g + 4, s),
        (0, (0x1234ABCD + p * 0x12345) & 0xFFFFFFFF),
        (0x00893F28, (0x6D3FA172 ^ p * 0x11111111) & 0xFFFFFFFF),
        (s, (0xBF800000, 0x7FC01234, 0xFF800000)[p]),
    ):
        store(pages, at, value)
    for off in STRINGS:
        store(pages, s + off, 0, 1)
        store(pages, s + off + 16, 0)
        store(pages, s + off + 20, 15)
    for off in (0xCC, 0xD0, 0xD4):
        store(pages, s + off, 0)
    registers = {
        r: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, r in enumerate(GPR)
    }
    registers.update(ecx=d, esp=g)
    xmm = {
        r: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=registers,
        xmm=xmm,
        return_address=0x04000000,
        entry_flags=0x246,
    )


@pytest.fixture(scope="module")
def cases():
    return [
        (v, independent_fixture(v), independent(independent_fixture(v)))
        for v in all_vectors()
    ]


def test_all48_exact_fixture_full14_packet_and_detached_expected_contract(cases):
    assert c.vectors() == all_vectors() and len(all_vectors()) == 48
    assert c.CONTROLS == CONTROLS and len(CONTROLS) == 58
    for vector, fixture, wanted in cases:
        strict_equal(c._fixture(vector), fixture)
        before = copy.deepcopy(fixture)
        actual = c._expected(vector, fixture)
        check(actual, fixture)
        strict_equal(actual, wanted)
        strict_equal(fixture, before)
        actual["pages"].clear()
        actual["events"].clear()
        actual["boundaries"][0]["events"].clear()
        strict_equal(c._expected(vector, fixture), wanted)


@pytest.mark.parametrize(
    "field,value",
    [
        ("alignment", True),
        ("alignment", -1),
        ("alignment", 16),
        ("alignment", 1.0),
        ("profile", False),
        ("profile", -1),
        ("profile", 3),
        ("profile", 1.0),
    ],
)
def test_typed_closed_vector_values(field, value):
    vector = all_vectors()[0]
    vector[field] = value
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize("kind", ("extra", "missing", "mapping", "key_subclass"))
def test_typed_closed_vector_schema(kind):
    v = all_vectors()[0]
    if kind == "extra":
        v["extra"] = 0
    elif kind == "missing":
        v.pop("profile")
    elif kind == "mapping":
        v = UserDict(v)
    else:

        class Key(str):
            pass

        v = {Key(k): x for k, x in v.items()}
    with pytest.raises(c.ConformanceError):
        c._fixture(v)


@pytest.mark.parametrize(
    "kind",
    ("extra", "gpr_bool", "xmm", "source", "ancestor", "flags", "label", "pages_type"),
)
def test_fixture_identity_cannot_be_relabelled(kind):
    vector = all_vectors()[2]
    fixture = independent_fixture(vector)
    if kind == "extra":
        fixture["opaque"] = 0
    elif kind == "gpr_bool":
        fixture["registers"]["eax"] = True
    elif kind == "xmm":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind == "source":
        old = read_bytes(fixture["pages"], 0x10000FF1, 1)[0]
        store(fixture["pages"], 0x10000FF1, old ^ 1, 1)
    elif kind == "ancestor":
        store(fixture["pages"], 0x30001040, 1)
    elif kind == "flags":
        fixture["entry_flags"] = 0x202
    elif kind == "label":
        vector["profile"] = 0
    else:
        fixture["pages"][0] = bytearray(fixture["pages"][0])
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "source",
        "gpr_bool",
        "xmm",
        "flags",
        "df_bool",
        "endpoint",
        "record",
        "padding",
        "pages",
        "event_bool",
        "event_read",
        "event_width",
        "trace",
        "boundary_count",
        "boundary_index",
        "boundary_gpr",
        "boundary_xmm",
        "boundary_flags",
        "boundary_type",
        "boundary_events",
    ),
)
def test_declared_expected_model_contract_guards(monkeypatch, kind):
    vector = all_vectors()[-1]
    fixture = independent_fixture(vector)
    forged = independent(fixture)
    if kind == "extra":
        forged["opaque"] = 0
    elif kind == "missing":
        forged.pop("df")
    elif kind == "source":
        forged["source_address"] += 1
    elif kind == "gpr_bool":
        forged["registers"]["ebx"] = True
    elif kind == "xmm":
        forged["xmm"]["xmm7"] ^= 1
    elif kind == "flags":
        forged["flags"] ^= 1
    elif kind == "df_bool":
        forged["df"] = False
    elif kind == "endpoint":
        forged["endpoint"] += 1
    elif kind in ("record", "padding"):
        at = 0 if kind == "record" else 0x15
        b = bytearray(forged["record_bytes"])
        b[at] ^= 1
        forged["record_bytes"] = bytes(b)
    elif kind == "pages":
        store(forged["pages"], 0x30001050, 1)
    elif kind == "event_bool":
        forged["events"][0]["width"] = True
    elif kind == "event_read":
        forged["events"][3]["value"] ^= 1
    elif kind == "event_width":
        forged["events"][0]["width"] = 8
    elif kind == "trace":
        forged["trace_rvas"][0] = "0x0015b9b1"
    elif kind == "boundary_count":
        forged["boundaries"].pop()
    elif kind == "boundary_index":
        forged["boundaries"][0]["index"] = False
    elif kind == "boundary_gpr":
        forged["boundaries"][18]["registers"]["edx"] ^= 1
    elif kind == "boundary_xmm":
        forged["boundaries"][0]["xmm"]["xmm7"] ^= 1
    elif kind == "boundary_flags":
        forged["boundaries"][0]["flags"] ^= 1
    elif kind == "boundary_type":
        forged["boundaries"][0]["pages"][0] = bytearray(
            forged["boundaries"][0]["pages"][0]
        )
    else:
        forged["boundaries"][0]["events"][0]["value"] ^= 1
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(forged))
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def source_paths():
    return {
        key: PROGRAMS
        / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        for key, (kind, digest) in SOURCE_PINS.items()
    }


def sources():
    return {key: json.loads(path.read_bytes()) for key, path in source_paths().items()}


def test_source_and_direct_interface_identity():
    assert c.SOURCE_PINS == SOURCE_PINS and c.BODY_PINS == BODY_PINS
    assert c.POINTS_SHA256 == POINT_SHA and c.CPU_MODEL == 19
    supplied = sources()
    for key, (kind, digest) in SOURCE_PINS.items():
        assert (
            supplied[key]["analysis_kind"] == kind
            and canonical_hash(supplied[key]) == digest
        )
    atlas = {
        int(row["entry_rva"], 16): row for row in supplied["program_facts"]["functions"]
    }
    for start, (size, digest) in BODY_PINS.items():
        assert (
            atlas[start]["body_size"] == size and atlas[start]["body_sha256"] == digest
        )
        assert atlas[start]["ranges"] == [dict(start_rva=f"0x{start:08x}", size=size)]
    params = inspect.signature(c._run_case).parameters
    assert list(params) == ["codes", "points", "vector", "negative", "capture"]
    assert params["capture"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(c.ConformanceError):
        c._preflight(UserDict(sources()))
    with pytest.raises(c.ConformanceError):
        c._checked_code_packet({k: bytes(n) for k, (n, h) in BODY_PINS.items()}, [])


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_source_pin_and_refreshed_build_facade_rejection(key, monkeypatch):
    supplied = sources()
    supplied[key]["analysis_kind"] = "forged"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)
    supplied = sources()
    identity = "identity" if key == "program_facts" else "build_identity"
    supplied[key][identity]["executable_sha256"] = "0" * 64
    monkeypatch.setattr(
        c.common,
        "_source_identity",
        lambda value, kind, digest, label: dict(
            analysis_kind=kind, canonical_sha256=digest
        ),
    )
    with pytest.raises(c.ConformanceError, match="source build"):
        c._preflight(supplied)


def quiet_environment():
    env = dict(os.environ)
    env.pop("PYTHONFAULTHANDLER", None)
    return env


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE for isolated native workers")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=2400,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b"" and result.stderr == b""


def native_code():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    return c._load_code(data, image, sources())


def outer(fixture):
    return dict(
        kind="outer",
        name="entry",
        index=0,
        registers=copy.deepcopy(fixture["registers"]),
        xmm=copy.deepcopy(fixture["xmm"]),
        pages=copy.deepcopy(fixture["pages"]),
        events=[],
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=0x0055B9B0,
    )


def publication_boundary(state, raw):
    return {
        **{
            k: copy.deepcopy(state[k])
            for k in (
                "kind",
                "name",
                "index",
                "registers",
                "xmm",
                "flags",
                "flag_mask",
                "df",
                "endpoint",
            )
        },
        "eflags": raw,
        "pages_sha256": page_hashes(state["pages"]),
        "events_sha256": canonical_hash(state["events"]),
    }


def worker_packet(index, codes=None, points=None):
    import unicorn as uc
    from unicorn import x86_const as x

    if codes is None:
        codes, points = native_code()
    assert len(points) == 386 and sum(map(len, codes.values())) == 1226
    vector = all_vectors()[index]
    fixture = independent_fixture(vector)
    wanted = independent(fixture)
    states = [outer(fixture)] + wanted["boundaries"]
    (
        instances,
        selected,
        starts,
        observed_trace,
        observed_events,
        observed_states,
        captured,
    ) = ([], [], [], [], [], [], [])
    original_uc = uc.Uc

    def tracked_uc(*args, **kwargs):
        machine = original_uc(*args, **kwargs)
        instances.append(machine)

        def code_hook(m, address, size, user):
            if address == fixture["return_address"]:
                return
            cursor = len(observed_states)
            if cursor < len(states) and address == states[cursor]["endpoint"]:
                expected = states[cursor]
                raw = m.reg_read(x.UC_X86_REG_EFLAGS)
                actual = {
                    **{k: expected[k] for k in ("kind", "name", "index", "flag_mask")},
                    "registers": {
                        r: m.reg_read(getattr(x, "UC_X86_REG_" + r.upper()))
                        for r in GPR
                    },
                    "xmm": {
                        r: m.reg_read(getattr(x, "UC_X86_REG_" + r.upper()))
                        for r in XMM
                    },
                    "pages": {p: bytes(m.mem_read(p, 4096)) for p in PAGES},
                    "events": copy.deepcopy(observed_events),
                    "flags": raw & expected["flag_mask"],
                    "df": (raw >> 10) & 1,
                    "endpoint": m.reg_read(x.UC_X86_REG_EIP),
                }
                strict_equal(actual, expected)
                if cursor == 0:
                    assert raw == 0x246
                observed_states.append(publication_boundary(actual, raw))
            observed_trace.append(f"0x{address-0x400000:08x}")

        def memory_hook(m, access, address, width, value, user):
            writing = access == uc.UC_MEM_WRITE
            observed_events.append(
                dict(
                    access="write" if writing else "read",
                    address=address,
                    width=width,
                    value=(
                        value & ((1 << (8 * width)) - 1)
                        if writing
                        else int.from_bytes(m.mem_read(address, width), "little")
                    ),
                )
            )

        set_cpu = machine.ctl_set_cpu_model

        def selected_cpu(cpu):
            assert cpu == 19
            selected.append(cpu)
            set_cpu(cpu)
            machine.hook_add(uc.UC_HOOK_CODE, code_hook)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory_hook)

        machine.ctl_set_cpu_model = selected_cpu
        emu_start = machine.emu_start

        def continuous(*args, **kwargs):
            starts.append((args, kwargs))
            return emu_start(*args, **kwargs)

        machine.emu_start = continuous
        return machine

    uc.Uc = tracked_uc

    def capture(machine, ids, expected, supplied):
        strict_equal(expected, wanted)
        strict_equal(supplied, fixture)
        assert machine is instances[0] and machine.ctl_get_cpu_model() == 19
        strict_equal({r: machine.reg_read(ids[r]) for r in GPR}, wanted["registers"])
        strict_equal(
            {r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper())) for r in XMM},
            wanted["xmm"],
        )
        assert machine.reg_read(x.UC_X86_REG_EFLAGS) == 0x287
        assert machine.reg_read(x.UC_X86_REG_EIP) == 0x04000000
        strict_equal(
            {p: bytes(machine.mem_read(p, 4096)) for p in PAGES}, wanted["pages"]
        )
        strict_equal(observed_trace, wanted["trace_rvas"])
        strict_equal(observed_events, wanted["events"])
        assert (
            len(observed_states) == 21
            and len(observed_trace) == 492
            and len(observed_events) == 315
        )
        expected["events"].clear()
        supplied["pages"].clear()
        captured.append(True)

    try:
        actual = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = original_uc
    assert (
        len(instances) == 1
        and selected == [19]
        and len(starts) == 1
        and captured == [True]
    )
    assert set(actual) == OBS_KEYS and len(OBS_KEYS) == 13
    strict_equal(
        actual,
        {
            "vector": vector,
            **{
                k: copy.deepcopy(wanted[k])
                for k in (
                    "registers",
                    "xmm",
                    "flags",
                    "flag_mask",
                    "df",
                    "endpoint",
                    "trace_rvas",
                )
            },
            "eflags": 0x287,
            "events_sha256": canonical_hash(wanted["events"]),
            "pages_sha256": page_hashes(wanted["pages"]),
            "memory_event_count": 315,
            "boundaries": observed_states,
        },
    )
    assert all(set(row) == OBS_BOUNDARY_KEYS for row in actual["boundaries"])
    return actual


@pytest.mark.parametrize("index", SELECTED)
def test_actual_one_uc_one_start_cpu19_full315_events_and21_boundaries(index):
    isolated("packet", index)


def worker_controls():
    codes, points = native_code()
    assert c.CONTROLS == CONTROLS
    for name, reason in CONTROLS.items():
        try:
            c._run_case(codes, points, all_vectors()[-1], name)
        except c.ConformanceError as exc:
            assert str(exc) == reason, (name, str(exc), reason)
        else:
            raise AssertionError("control survived: " + name)


def test_all58_actual_and_record_controls_have_intended_frontiers():
    isolated("controls")


def worker_code():
    import unicorn as uc

    codes, points = native_code()
    instances = []
    original = uc.Uc

    def counted(*args, **kwargs):
        instances.append(True)
        return original(*args, **kwargs)

    uc.Uc = counted
    for kind in (
        "bytes",
        "refreshed_point",
        "short",
        "key",
        "extra",
        "point_order",
        "point_missing",
        "point_duplicate",
        "negative",
        "model_flags",
        "model_pages",
    ):
        changed, rows = dict(codes), copy.deepcopy(points)
        negative = None
        apply = c.model.apply
        if kind in ("bytes", "refreshed_point"):
            b = bytearray(changed[0x80D0])
            b[0] ^= 1
            changed[0x80D0] = bytes(b)
            if kind == "refreshed_point":
                rows[0]["sha256"] = hashlib.sha256(
                    bytes(b[: rows[0]["size"]])
                ).hexdigest()
        elif kind == "short":
            changed[0x15B9B0] = changed[0x15B9B0][:-1]
        elif kind == "key":

            class Address(int):
                pass

            changed = {Address(k): v for k, v in changed.items()}
        elif kind == "extra":
            changed[0x8ABA0] = b"\x90"
        elif kind == "point_order":
            rows.reverse()
        elif kind == "point_missing":
            rows.pop()
        elif kind == "point_duplicate":
            rows.append(copy.deepcopy(rows[0]))
        elif kind == "negative":
            negative = False
        else:
            forged = independent(independent_fixture(all_vectors()[0]))
            if kind == "model_flags":
                forged["flags"] ^= 1
            else:
                store(forged["pages"], 0x30001040, 1)
            c.model.apply = lambda **kwargs: copy.deepcopy(forged)
        try:
            with pytest.raises(c.ConformanceError):
                c._run_case(changed, rows, all_vectors()[0], negative)
        finally:
            c.model.apply = apply
    assert instances == []


def test_direct_code_model_and_control_forgeries_fail_before_any_uc():
    isolated("code")


def worker_observations():
    codes, points = native_code()
    observations = [worker_packet(i, codes, points) for i in range(48)]
    receipt = json.loads(EVIDENCE.read_bytes())
    assert canonical_hash(observations) == receipt["observations_sha256"]


def test_all48_full_independent_native_observations_match_receipt_digest():
    isolated("observations")


@pytest.fixture
def receipt():
    return json.loads(EVIDENCE.read_bytes())


def test_sealed_receipt_complete_scope_counts_points_sources_and_encoding(receipt):
    assert c.SEALED_SHA256 != "PENDING" and canonical_hash(receipt) == c.SEALED_SHA256
    assert (
        c.SEALED_SHA256
        == "e7a534fde897fc1e7520c1de8e8d7f9bb2a7fad6a33520c3fc70f396fe8c024d"
    )
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert (
        len(raw) == 79638
        and hashlib.sha256(raw).hexdigest()
        == "f4ac5009002ffcbf107b50fc4b92958b92d6b4918852bff2ebb068dd504706dc"
    )
    checked = c.validate_structure(receipt, sources())
    assert checked["status"] == "structurally_verified"
    assert (
        receipt["analysis_kind"]
        == "pe_native_movement_effect_record_empty_copy_conformance"
    )
    assert receipt["schema_version"] == 1 and receipt["vectors"] == all_vectors()
    strict_equal(
        receipt["body"]["ranges"],
        [
            dict(
                start_rva=f"0x{start:08x}",
                exclusive_end_rva=f"0x{start+size:08x}",
                sha256=digest,
            )
            for start, (size, digest) in sorted(BODY_PINS.items())
        ],
    )
    assert (
        canonical_hash(receipt["body"]["points"]) == POINT_SHA
        and len(receipt["body"]["points"]) == 386
    )
    assert (
        receipt["executed_rvas"] == sorted({f"0x{pc:08x}" for pc in TRACE})
        and len(receipt["executed_rvas"]) == 261
    )
    assert receipt["engine"] == dict(
        name="Unicorn",
        version="2.1.4",
        architecture="x86_32",
        cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
    )
    strict_equal(
        receipt["source_receipts"],
        {
            key: dict(analysis_kind=kind, canonical_sha256=digest)
            for key, (kind, digest) in SOURCE_PINS.items()
        },
    )
    assert len(receipt["source_receipts"]) == 4
    assert {r["name"]: r["reason"] for r in receipt["negative_controls"]} == CONTROLS
    assert all(r["rejected"] is True for r in receipt["negative_controls"])
    summary = dict(
        cases=48,
        loaded_sites=386,
        loaded_bytes=1226,
        executed_sites=261,
        native_instructions=48 * 492,
        memory_events=48 * 315,
        native_boundary_snapshots=48 * 21,
        empty_string_calls=48 * 8,
        empty_path_calls=48,
        zero_reserve_calls=48,
        source_bytes_preserved=48 * 308,
        record_bytes=48 * 308,
        record_written_bytes=48 * 183,
        record_padding_bytes_preserved=48 * 125,
        copied_scalar_bytes=48 * 99,
        empty_string_field_bytes=48 * 72,
        initialized_empty_path_bytes=48 * 12,
        xmm_preserved_cases=48,
        allocation_requests=0,
        free_requests=0,
        scalar_clone_calls=0,
        wide_reads=0,
        wide_writes=0,
        api_responses=0,
        cookie_checker_calls=0,
        opaque_instructions=0,
        controls=58,
        accounting_promotions=0,
    )
    strict_equal(receipt["summary"], summary)
    excluded = " ".join(receipt["scope"]["not_claimed"]).lower()
    for term in (
        "ownership",
        "unwind",
        "failure handler",
        "nonempty",
        "assignment",
        "append",
        "addmove",
        "gameplay",
        "lua",
        "coordinated",
        "represented writes",
    ):
        assert term in excluded
    before = copy.deepcopy(receipt)
    checked["summary"].clear()
    strict_equal(receipt, before)


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool",
        "vector",
        "point",
        "range",
        "control",
        "observations",
        "pins",
        "scope",
    ),
)
def test_refreshed_encoding_does_not_reseal_mutated_evidence(receipt, kind):
    changed = copy.deepcopy(receipt)
    if kind == "summary":
        changed["summary"]["allocation_requests"] = 1
    elif kind == "bool":
        changed["summary"]["free_requests"] = False
    elif kind == "vector":
        changed["vectors"][0]["profile"] = 1
    elif kind == "point":
        changed["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        changed["body"]["ranges"][0]["exclusive_end_rva"] = "0x000081ef"
    elif kind == "control":
        changed["negative_controls"][0]["rejected"] = False
    elif kind == "observations":
        changed["observations_sha256"] = "0" * 64
    elif kind == "pins":
        changed["source_receipts"].clear()
    else:
        changed["scope"]["claim"] = "general movement publication proved"
    # Normal deterministic re-encoding does not authorize a fresh canonical seal.
    refreshed = json.loads(c.encode_conformance(changed))
    with pytest.raises(c.ConformanceError):
        c.validate_structure(refreshed, sources())


def cli_arguments(command, paths=None, evidence=None):
    args = [sys.executable, str(CLI), command]
    for key, path in (source_paths() if paths is None else paths).items():
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "build":
        args += ["--evidence", str(EVIDENCE if evidence is None else evidence)]
    if command != "verify-structure":
        args += ["--executable", os.environ["ITB_EXACT_EXE"]]
    return args


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_and_structure(receipt, command):
    if command != "verify-structure" and not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE for native CLI")
    result = subprocess.run(
        cli_arguments(command),
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=2400,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    if command == "build":
        assert result.stdout == EVIDENCE.read_bytes()
    else:
        value = json.loads(result.stdout)
        assert value["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert value["evidence_sha256"] == c.SEALED_SHA256
        strict_equal(value["summary"], receipt["summary"])
        assert result.stdout == c.encode_conformance(value).encode("utf-8")


@pytest.mark.parametrize("kind", ("crlf", "duplicate_key", "source", "nonfinite"))
def test_structure_cli_rejects_malformed_encoding_and_source(receipt, tmp_path, kind):
    raw = c.encode_conformance(receipt).encode("utf-8")
    paths = source_paths()
    if kind == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif kind == "duplicate_key":
        raw = raw.replace(b"{\n", b'{\n  "schema_version": 1,\n', 1)
    elif kind == "nonfinite":
        raw = raw.replace(b'"schema_version": 1', b'"schema_version": NaN', 1)
    else:
        source = sources()["movement_binding"]
        source["scope"]["runtime_registration"] = True
        path = tmp_path / "source.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        paths["movement_binding"] = path
    evidence = tmp_path / "receipt.json"
    evidence.write_bytes(raw)
    result = subprocess.run(
        cli_arguments("verify-structure", paths, evidence),
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=2400,
    )
    assert (
        result.returncode == 1
        and result.stdout == b""
        and result.stderr.startswith(b"error:")
    )


def test_encoder_rejects_nonfinite_and_emits_utf8_lf():
    with pytest.raises(ValueError):
        c.encode_conformance({"value": float("nan")})
    value = {"snow": "☃"}
    raw = c.encode_conformance(value).encode("utf-8")
    assert b"\r" not in raw and raw.endswith(b"\n") and b"\\u2603" not in raw
    assert json.loads(raw) == value


if __name__ == "__main__":
    faulthandler.disable()
    action, index = sys.argv[1], int(sys.argv[2])
    if action == "packet":
        worker_packet(index)
    elif action == "controls":
        worker_controls()
    elif action == "code":
        worker_code()
    elif action == "observations":
        worker_observations()
    else:
        raise SystemExit("unknown worker")
