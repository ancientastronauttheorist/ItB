"""Independent finite80D0 machine proof and exact publication checks.

The pure oracle is handwritten in the predecessor test file. Production fixture,
model and expected functions are used only as actual values under test.
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
from src.observatory import native_movement_empty_string_copy_conformance as c
from tests.test_itb_native_movement_empty_string_copy_semantics import (
    independent,
    assert_strict_packet as strict_equal,
    store,
    read_bytes,
    TRACE,
    KEYS,
)

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_movement_empty_string_copy_conformance.json")
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
PAGES = (0x30000000, 0x30001000, 0x06002000, 0x06003000, 0x06004000, 0x06005000)
BODY_SHA = "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"
POINT_SHA = "bd0122e721665f06a92d7a1d28a7b218e471ed26ed688f3f6d5bfee8b9662dcb"
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
}
CONTROLS = {
    **{
        n: "empty string native entry differs"
        for n in ("entry_gpr", "entry_xmm", "entry_flags", "entry_df", "entry_page")
    },
    **{
        n: "empty string ordered memory differs"
        for n in ("source_size", "offset", "maximum", "destination_capacity")
    },
    **{
        n: "empty string final pages differ"
        for n in (
            "source_capacity",
            "source_terminator",
            "source_padding",
            "destination_size",
            "destination_byte",
            "destination_padding",
            "stack_ancestor",
            "stack_padding",
            "caller_word",
        )
    },
    **{
        n: "empty string final ABI differs"
        for n in ("final_gpr", "final_xmm", "final_flags", "final_df", "final_endpoint")
    },
    "missing_read_record": "empty string final events differ",
    "restored_write_record": "empty string final events differ",
    "trace_record": "empty string final native path differs",
}
SELECTED = (0, 1, 2, 3, 4, 5, 42, 43, 50, 51, 94, 95)
OBSERVATION_KEYS = {
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
    return [
        dict(alignment=a, profile=p, return_form=r)
        for a in range(16)
        for p in range(3)
        for r in ("external", "record_copy")
    ]


def independent_fixture(vector):
    a, p = vector["alignment"], vector["profile"]
    g, s, d = 0x30001000 + a, 0x06002FF0 + a, 0x06004FF0 + a
    stop = 0x04000000 if vector["return_form"] == "external" else 0x0055BA65
    pages = {
        page: bytes((i * 31 + j * 17 + p * 53) & 255 for j in range(4096))
        for i, page in enumerate(PAGES)
    }
    for at, v in (
        (g, stop),
        (g + 4, s),
        (g + 8, 0),
        (g + 12, 0xFFFFFFFF),
        (s + 16, 0),
        (s + 20, 15),
        (d + 16, (0, 7, 15)[p]),
        (d + 20, 15),
    ):
        store(pages, at, v)
    store(pages, s, 0, 1)
    store(pages, d + (0, 7, 15)[p], 0, 1)
    regs = {
        r: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, r in enumerate(GPR)
    }
    regs.update(ecx=d, esp=g)
    xmm = {
        r: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, r in enumerate(XMM)
    }
    return dict(
        pages=pages, registers=regs, xmm=xmm, return_address=stop, entry_flags=0x246
    )


@pytest.fixture(scope="module")
def cases():
    return [
        (v, independent_fixture(v), independent(independent_fixture(v)))
        for v in all_vectors()
    ]


def test_exact96_fixture_recipe_and_full_independent_11_field_law(cases):
    assert len(all_vectors()) == 96 and c.vectors() == all_vectors()
    assert c.CONTROLS == CONTROLS and len(CONTROLS) == 26
    for vector, fixture, wanted in cases:
        strict_equal(c._fixture(vector), fixture)
        before = copy.deepcopy(fixture)
        actual = c._expected(vector, fixture)
        strict_equal(actual, wanted)
        strict_equal(fixture, before)
        assert set(actual) == KEYS and len(KEYS) == 11
        assert len(actual["events"]) == 17 and len(actual["trace_rvas"]) == 33
        assert [r["width"] for r in actual["events"]].count(1) == 1
        assert len(set(actual["trace_rvas"])) == 33
        s, d = actual["source_address"], actual["destination_address"]
        assert read_bytes(actual["pages"], s, 24) == read_bytes(fixture["pages"], s, 24)
        old = read_bytes(fixture["pages"], d, 24)
        assert (
            read_bytes(actual["pages"], d, 24)
            == b"\0" + old[1:16] + bytes(4) + old[20:24]
        )
        actual["events"].clear()
        actual["xmm"].clear()
        actual["pages"].clear()
        strict_equal(c._expected(vector, fixture), wanted)


@pytest.mark.parametrize(
    "field,value",
    [
        ("alignment", True),
        ("alignment", -1),
        ("alignment", 16),
        ("alignment", 0.0),
        ("profile", False),
        ("profile", 3),
        ("return_form", "record"),
        ("return_form", 1),
    ],
)
def test_typed_finite_vector_guard(field, value):
    vector = all_vectors()[0]
    vector[field] = value
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize("kind", ("extra", "missing", "mapping", "key_subclass"))
def test_closed_vector_schema(kind):
    v = all_vectors()[0]
    if kind == "extra":
        v["unused"] = 0
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
    ("schema", "register", "xmm", "ancestor", "source", "label", "flag", "page_type"),
)
def test_fixture_identity_cannot_be_relabelled(kind):
    v = all_vectors()[2]
    packet = independent_fixture(v)
    if kind == "schema":
        packet["unused"] = 0
    elif kind == "register":
        packet["registers"]["ecx"] = False
    elif kind == "xmm":
        packet["xmm"]["xmm7"] ^= 1
    elif kind == "ancestor":
        store(packet["pages"], 0x30001020, 1)
    elif kind == "source":
        store(packet["pages"], 0x06002FF1, 0, 1)
    elif kind == "label":
        v["profile"] = 0
    elif kind == "flag":
        packet["entry_flags"] = 0x202
    else:
        packet["pages"][PAGES[0]] = bytearray(packet["pages"][PAGES[0]])
    before = copy.deepcopy(packet)
    with pytest.raises(c.ConformanceError):
        c._expected(v, packet)
    strict_equal(packet, before)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "bool",
        "address",
        "gpr",
        "xmm",
        "flags",
        "df",
        "endpoint",
        "source_page",
        "padding",
        "event_value",
        "event_order",
        "restore_record",
        "trace",
        "trace_order",
    ),
)
def test_full_model_packet_guard_rejects_same_size_and_coordinated_forgery(
    monkeypatch, kind
):
    vector = all_vectors()[95]
    fixture = independent_fixture(vector)
    forged = independent(fixture)
    if kind == "extra":
        forged["opaque"] = 0
    elif kind == "missing":
        forged.pop("df")
    elif kind == "bool":
        forged["registers"]["ecx"] = False
    elif kind == "address":
        forged["source_address"] += 1
    elif kind == "gpr":
        forged["registers"]["edx"] ^= 1
    elif kind == "xmm":
        forged["xmm"]["xmm7"] ^= 1
    elif kind == "flags":
        forged["flags"] ^= 1
    elif kind == "df":
        forged["df"] = False
    elif kind == "endpoint":
        forged["endpoint"] += 1
    elif kind in ("source_page", "padding"):
        store(
            forged["pages"],
            0x06002FF0 + 15 if kind == "source_page" else 0x30001020,
            1,
            1,
        )
    elif kind == "event_value":
        forged["events"][8]["value"] ^= 1
    elif kind == "event_order":
        forged["events"][8], forged["events"][9] = (
            forged["events"][9],
            forged["events"][8],
        )
        forged["events"][8]["address"] += 1
    elif kind == "restore_record":
        forged["events"][8:10] = [
            dict(
                access="write",
                address=forged["destination_address"] + 1,
                width=1,
                value=1,
            ),
            dict(
                access="write",
                address=forged["destination_address"] + 1,
                width=1,
                value=read_bytes(forged["pages"], forged["destination_address"] + 1, 1)[
                    0
                ],
            ),
        ]
    elif kind == "trace":
        forged["trace_rvas"][17] = "0x00008152"
    else:
        forged["trace_rvas"][0], forged["trace_rvas"][1] = (
            forged["trace_rvas"][1],
            forged["trace_rvas"][0],
        )
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(forged))
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def source_paths():
    names = {
        "program_facts": "program_facts",
        "movement_binding": "native_movement_effect_binding",
        "default_record": "native_movement_effect_record_default_conformance",
    }
    return {k: PROGRAMS / (PREFIX + n + ".json") for k, n in names.items()}


def sources():
    return {k: json.loads(p.read_bytes()) for k, p in source_paths().items()}


def test_exact_sources_signature_and_code_schema():
    assert c.SOURCE_PINS == SOURCE_PINS
    supplied = sources()
    for key, (kind, digest) in SOURCE_PINS.items():
        assert supplied[key]["analysis_kind"] == kind
        assert canonical_hash(supplied[key]) == digest
    atlas = {int(f["entry_rva"], 16): f for f in supplied["program_facts"]["functions"]}
    assert atlas[0x80D0]["body_size"] == 288
    assert atlas[0x80D0]["body_sha256"] == BODY_SHA
    assert atlas[0x80D0]["ranges"] == [dict(start_rva="0x000080d0", size=288)]
    args = inspect.signature(c._run_case).parameters
    assert list(args) == ["codes", "points", "vector", "negative", "capture"]
    assert args["capture"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(c.ConformanceError):
        c._preflight(UserDict(sources()))
    with pytest.raises(c.ConformanceError):
        c._checked_code_packet({0x80D0: bytes(288)}, [])


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_declared_source_error_normalization_and_fresh_pin_facade(monkeypatch, key):
    supplied = sources()
    supplied[key]["analysis_kind"] = "forged"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)
    supplied = sources()
    id_key = "identity" if key == "program_facts" else "build_identity"
    supplied[key][id_key]["executable_sha256"] = "0" * 64
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
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        capture_output=True,
        env=quiet_environment(),
        timeout=1800,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stdout == b"" and completed.stderr == b""


def native_code():
    data, image, sha = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert sha == "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    return c._load_code(data, image, sources())


@pytest.mark.parametrize("index", SELECTED)
def test_actual_one_uc_cpu19_full_state_trace_events_and_caller_stop(index):
    isolated("packet", index)


def test_all26_controls_have_intended_frontiers():
    isolated("controls")


def test_direct_code_and_model_forgeries_fail_before_any_uc():
    isolated("code")


def worker_packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_code()
    vector = all_vectors()[index]
    fixture = independent_fixture(vector)
    wanted = independent(fixture)
    observed_trace, observed_events, instances, captured = [], [], [], []
    original_uc = uc.Uc

    def tracked_uc(*args, **kwargs):
        machine = original_uc(*args, **kwargs)
        instances.append(machine)

        def code_hook(m, address, size, user):
            if address != fixture["return_address"]:
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
            set_cpu(cpu)
            machine.hook_add(uc.UC_HOOK_CODE, code_hook)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, memory_hook)

        # Hooks initialize/lock the CPU: select CPU19 before observer installation.
        machine.ctl_set_cpu_model = selected_cpu
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
        assert machine.reg_read(x.UC_X86_REG_EIP) == fixture["return_address"]
        strict_equal(
            {p: bytes(machine.mem_read(p, 4096)) for p in PAGES}, wanted["pages"]
        )
        strict_equal(observed_trace, wanted["trace_rvas"])
        strict_equal(observed_events, wanted["events"])
        assert len(observed_trace) == 33 and len(observed_events) == 17
        expected["events"].clear()
        supplied["pages"].clear()
        captured.append(True)

    actual = c._run_case(codes, points, vector, capture=capture)
    assert len(instances) == 1 and captured == [True]
    assert set(actual) == OBSERVATION_KEYS and len(actual) == 13
    for key in (
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "endpoint",
        "trace_rvas",
    ):
        strict_equal(actual[key], wanted[key])
    assert actual["vector"] == vector and actual["eflags"] == 0x287
    assert actual["events_sha256"] == canonical_hash(wanted["events"])
    assert (
        actual["pages_sha256"] == page_hashes(wanted["pages"])
        and actual["memory_event_count"] == 17
    )
    assert len(actual["boundaries"]) == 1
    row = actual["boundaries"][0]
    assert set(row) == {
        "name",
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
    assert (
        row["name"] == "entry"
        and row["endpoint"] == 0x004080D0
        and row["eflags"] == 0x246
    )
    strict_equal(row["registers"], fixture["registers"])
    strict_equal(row["xmm"], fixture["xmm"])
    assert row["flags"] == 0x44 and row["flag_mask"] == 0x8D5 and row["df"] == 0
    assert row["pages_sha256"] == page_hashes(fixture["pages"]) and row[
        "events_sha256"
    ] == canonical_hash([])


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
        "size",
        "key",
        "extra",
        "point_order",
        "negative",
        "model_events",
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
        elif kind == "size":
            changed[0x80D0] = changed[0x80D0][:-1]
        elif kind == "key":

            class Address(int):
                pass

            changed = {Address(k): v for k, v in changed.items()}
        elif kind == "extra":
            changed[0x81F0] = b"\x90"
        elif kind == "point_order":
            rows.reverse()
        elif kind == "negative":
            negative = False
        else:
            forged = independent(independent_fixture(all_vectors()[0]))
            if kind == "model_events":
                forged["events"][8]["value"] ^= 1
            else:
                store(forged["pages"], 0x30001020, 1)
            c.model.apply = lambda **kwargs: copy.deepcopy(forged)
        try:
            try:
                c._run_case(changed, rows, all_vectors()[0], negative)
            except c.ConformanceError:
                pass
            else:
                raise AssertionError("forgery survived: " + kind)
        finally:
            c.model.apply = apply
    assert instances == []


def worker_observations():
    codes, points = native_code()
    actual = [c._run_case(codes, points, v) for v in all_vectors()]
    receipt = json.loads(EVIDENCE.read_bytes())
    assert canonical_hash(actual) == receipt["observations_sha256"]
    assert all(
        o["memory_event_count"] == 17 and len(o["trace_rvas"]) == 33 for o in actual
    )


def test_full96_native_observation_digest_matches_sealed_receipt():
    isolated("observations")


@pytest.fixture
def receipt():
    return json.loads(EVIDENCE.read_bytes())


def test_sealed_receipt_exact_sources_counts_flags_encoding_and_scope(receipt, cases):
    assert c.SEALED_SHA256 != "PENDING" and canonical_hash(receipt) == c.SEALED_SHA256
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    checked = c.validate_structure(receipt, sources())
    assert checked["status"] == "structurally_verified"
    assert (
        receipt["analysis_kind"] == "pe_native_movement_empty_string_copy_conformance"
    )
    assert receipt["vectors"] == all_vectors()
    assert receipt["body"]["ranges"] == [
        dict(start_rva="0x000080d0", exclusive_end_rva="0x000081f0", sha256=BODY_SHA)
    ]
    assert (
        canonical_hash(receipt["body"]["points"]) == POINT_SHA
        and len(receipt["body"]["points"]) == 119
    )
    assert receipt["executed_rvas"] == sorted(f"0x{p:08x}" for p in TRACE)
    assert {r["name"]: r["reason"] for r in receipt["negative_controls"]} == CONTROLS
    assert all(r["rejected"] is True for r in receipt["negative_controls"])
    expected = dict(
        cases=96,
        external_cases=48,
        record_copy_cases=48,
        loaded_sites=119,
        loaded_bytes=288,
        executed_sites=33,
        native_instructions=96 * 33,
        memory_events=96 * 17,
        source_preserved_bytes=96 * 24,
        destination_written_bytes=96 * 5,
        destination_preserved_bytes=96 * 19,
        xmm_preserved_cases=96,
        child_calls=0,
        allocation_requests=0,
        copy_requests=0,
        free_requests=0,
        opaque_instructions=0,
        accounting_promotions=0,
        controls=26,
    )
    strict_equal(receipt["summary"], expected)
    strict_equal(
        receipt["source_receipts"],
        {
            key: dict(analysis_kind=kind, canonical_sha256=digest)
            for key, (kind, digest) in SOURCE_PINS.items()
        },
    )
    assert receipt["engine"] == dict(
        name="Unicorn",
        version="2.1.4",
        architecture="x86_32",
        cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
    )
    assert len(receipt["source_receipts"]) == 3
    text = " ".join(receipt["scope"]["not_claimed"]).lower()
    for excluded in (
        "record-copy caller",
        "addmove",
        "ownership",
        "unwind",
        "gameplay",
    ):
        assert excluded in text
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
        "observation",
        "pins",
        "scope",
    ),
)
def test_refreshed_encoding_cannot_reseal_forged_receipt(receipt, kind):
    changed = copy.deepcopy(receipt)
    if kind == "summary":
        changed["summary"]["child_calls"] = 1
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
    elif kind == "observation":
        changed["observations_sha256"] = "0" * 64
    elif kind == "pins":
        changed["source_receipts"].clear()
    else:
        changed["scope"]["claim"] = "general strings proved"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(changed, sources())


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_and_structure(receipt, command):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE for native CLI")
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_movement_empty_string_copy_conformance.py"),
        command,
    ]
    for key, path in source_paths().items():
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    if command != "verify-structure":
        args += ["--executable", executable]
    result = subprocess.run(
        args, cwd=ROOT, capture_output=True, env=quiet_environment(), timeout=1800
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stderr == b""
    if command == "build":
        assert result.stdout == EVIDENCE.read_bytes()
    else:
        parsed = json.loads(result.stdout)
        assert parsed["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert parsed["evidence_sha256"] == c.SEALED_SHA256
        strict_equal(parsed["summary"], receipt["summary"])
        assert result.stdout == c.encode_conformance(parsed).encode("utf-8")


@pytest.mark.parametrize("kind", ("crlf", "duplicate_key", "source"))
def test_structure_cli_rejects_encoding_and_source_tampering(receipt, tmp_path, kind):
    raw = c.encode_conformance(receipt).encode("utf-8")
    paths = source_paths()
    if kind == "crlf":
        raw = raw.replace(b"\n", b"\r\n")
    elif kind == "duplicate_key":
        raw = raw.replace(b"{\n", b'{\n  "schema_version": 1,\n', 1)
    else:
        changed = sources()["movement_binding"]
        changed["scope"]["runtime_registration"] = True
        path = tmp_path / "source.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        paths["movement_binding"] = path
    evidence = tmp_path / "receipt.json"
    evidence.write_bytes(raw)
    args = [
        sys.executable,
        str(ROOT / "scripts/itb_native_movement_empty_string_copy_conformance.py"),
        "verify-structure",
        "--evidence",
        str(evidence),
    ]
    for key, path in paths.items():
        args += ["--" + key.replace("_", "-"), str(path)]
    result = subprocess.run(
        args, cwd=ROOT, capture_output=True, env=quiet_environment(), timeout=1800
    )
    assert (
        result.returncode == 1
        and result.stdout == b""
        and result.stderr.startswith(b"error:")
    )


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
