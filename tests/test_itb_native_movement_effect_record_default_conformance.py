"""Independent continuous default-constructor native checkpoint tests.

Expected pages/events/state come only from the handwritten pure-test oracle.
Native workers install additional hooks on the real single Unicorn instance.
"""

from __future__ import annotations

import copy
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
from src.observatory import native_movement_effect_record_default_conformance as c
from tests import test_itb_native_movement_effect_record_default_semantics as p

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (
    PREFIX + "native_movement_effect_record_default_conformance.json"
)
CLI = ROOT / "scripts/itb_native_movement_effect_record_default_conformance.py"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
    "movement_binding": (
        "pe_native_movement_effect_binding",
        "54c060913d61f6bb5e4c1f2586f0d5186ea73ad6c058dd48b1cc056e64a410b9",
    ),
}
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
BOUNDARY_KEYS = {
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
CONTROL_REASONS = {
    **{
        name: "default record string boundary differs"
        for name in (
            "entry_gpr",
            "entry_xmm",
            "entry_flags",
            "entry_df",
            "entry_page",
            "return_gpr",
            "return_xmm",
            "return_flags",
            "return_df",
            "return_page",
        )
    },
    **{
        name: "default record ordered memory differs"
        for name in ("source_word", "length_word", "capacity_word")
    },
    **{
        name: "default record final pages differ"
        for name in (
            "field",
            "padding",
            "stack_ancestor",
            "stack_padding",
            "seh",
            "cookie",
            "literal",
            "heap_padding",
        )
    },
    **{
        name: "default record final ABI differs"
        for name in (
            "final_gpr",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "default record final events differ",
    "restored_write_record": "default record final events differ",
    "trace_record": "default record final native path differs",
}


def canonical(value):
    return hashlib.sha256(
        (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode()
    ).hexdigest()


def page_hashes(pages):
    return {
        f"0x{page:08x}": hashlib.sha256(data).hexdigest()
        for page, data in sorted(pages.items())
    }


def recipes():
    return [
        dict(alignment=a, profile=i, storage=storage)
        for a in range(16)
        for i in range(3)
        for storage in ("heap", "parent_local")
    ]


def finite_fixture(vector):
    """Handwritten declared recipe, independent from the production fixture."""
    a, i = vector["alignment"], vector["profile"]
    pages = {
        page: bytes((j * 29 + k * 17 + i * 53) & 255 for k in range(4096))
        for j, page in enumerate(
            (0, 0x30000000, 0x30001000, 0x10000000, 0x893000, 0x80D000)
        )
    }
    g = 0x30001000 + a
    r = 0x10000800 + a if vector["storage"] == "heap" else g + 0x148
    stop = 0x4000000 if vector["storage"] == "heap" else 0x657397
    for address, value in (
        (0, (0x11112222 ^ i * 0x1020304) & 0xFFFFFFFF),
        (0x893F28, (0x19A51C73 ^ i * 0x2468ACE) & 0xFFFFFFFF),
        (g, stop),
        (g + 4, 0),
    ):
        p.store(pages, address, value)
    p.store(pages, 0x80DFDC, 0, 1)
    regs = {
        name: (0x12345678 + n * 0x11111111 + i * 0x1234) & 0xFFFFFFFF
        for n, name in enumerate(p.GPRS)
    }
    regs.update(ecx=r, esp=g)
    xmms = {
        name: int.from_bytes(
            bytes((n * 19 + j * 41 + i * 73) & 255 for j in range(16)), "little"
        )
        for n, name in enumerate(p.XMMS)
    }
    return dict(
        pages=pages, registers=regs, xmm=xmms, return_address=stop, entry_flags=0x246
    )


def expected_observation(vector, wanted):
    boundaries = []
    for boundary in wanted["string_boundaries"]:
        boundaries.append(
            dict(
                name=boundary["name"],
                index=boundary["index"],
                registers=boundary["registers"],
                xmm=boundary["xmm"],
                eflags=0x287,
                flags=0x85,
                flag_mask=0x8D5,
                df=0,
                endpoint=boundary["endpoint"],
                pages_sha256=page_hashes(boundary["pages"]),
                events_sha256=canonical(boundary["events"]),
            )
        )
    return dict(
        vector=vector,
        registers=wanted["registers"],
        xmm=wanted["xmm"],
        eflags=0x287,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=wanted["endpoint"],
        trace_rvas=wanted["trace_rvas"],
        events_sha256=canonical(wanted["events"]),
        pages_sha256=page_hashes(wanted["pages"]),
        memory_event_count=217,
        boundaries=boundaries,
    )


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("storage", ("heap", "parent_local"))
def test_declared_fixture_and_complete_expected_are_independent(
    alignment, profile, storage
):
    vector = dict(alignment=alignment, profile=profile, storage=storage)
    fixture = finite_fixture(vector)
    original = copy.deepcopy(fixture)
    p.assert_strict_packet(c._fixture(vector), fixture)
    p.check_packet(c._expected(vector, fixture), fixture)
    p.assert_strict_packet(fixture, original)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "bool_alignment",
        "float_alignment",
        "bool_profile",
        "storage",
        "alignment_range",
        "profile_range",
    ),
)
def test_exact_vector_domain(kind):
    vector = dict(alignment=0, profile=0, storage="heap")
    if kind == "extra":
        vector["extra"] = 0
    elif kind == "missing":
        vector.pop("storage")
    elif kind == "bool_alignment":
        vector["alignment"] = False
    elif kind == "float_alignment":
        vector["alignment"] = 0.0
    elif kind == "bool_profile":
        vector["profile"] = False
    elif kind == "storage":
        vector["storage"] = "caller"
    elif kind == "alignment_range":
        vector["alignment"] = 16
    else:
        vector["profile"] = 3
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "page_bool",
        "mutable",
        "gpr_bool",
        "xmm_bool",
        "xmm_changed",
        "cookie",
        "padding",
        "argument",
        "return",
        "flags",
    ),
)
def test_finite_fixture_identity_and_types(kind):
    vector = dict(alignment=15, profile=2, storage="parent_local")
    fixture = finite_fixture(vector)
    if kind == "extra":
        fixture["extra"] = 0
    elif kind == "missing":
        fixture.pop("pages")
    elif kind == "page_bool":
        data = fixture["pages"].pop(0)
        fixture["pages"][False] = data
    elif kind == "mutable":
        fixture["pages"][0] = bytearray(fixture["pages"][0])
    elif kind == "gpr_bool":
        fixture["registers"]["eax"] = False
    elif kind == "xmm_bool":
        fixture["xmm"]["xmm0"] = False
    elif kind == "xmm_changed":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind in ("cookie", "padding", "argument"):
        address = {
            "cookie": 0x893F28,
            "padding": 0x10000001,
            "argument": fixture["registers"]["esp"] + 4,
        }[kind]
        p.store(
            fixture["pages"],
            address,
            p.read_bytes(fixture["pages"], address, 1)[0] ^ 1,
            1,
        )
    elif kind == "return":
        fixture["return_address"] += 1
    else:
        fixture["entry_flags"] |= 0x10
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "gpr_bool",
        "df_bool",
        "xmm_bool",
        "field",
        "padding",
        "pages",
        "event_bool",
        "event_value",
        "boundary_missing",
        "boundary_extra",
        "boundary_bool_index",
    ),
)
def test_model_packet_independent_guard(monkeypatch, kind):
    vector = dict(alignment=7, profile=1, storage="heap")
    fixture = finite_fixture(vector)
    forged = p.independent_packet(fixture)
    if kind == "extra":
        forged["extra"] = 0
    elif kind == "missing":
        forged.pop("df")
    elif kind == "gpr_bool":
        forged["registers"]["eax"] = True
    elif kind == "df_bool":
        forged["df"] = False
    elif kind == "xmm_bool":
        forged["xmm"]["xmm0"] = False
    elif kind in ("field", "padding"):
        record = bytearray(forged["record_bytes"])
        record[12 if kind == "field" else 21] ^= 1
        forged["record_bytes"] = bytes(record)
    elif kind == "pages":
        forged["pages"][0] = bytes(4096)
    elif kind == "event_bool":
        forged["events"][17]["width"] = True  # BYTE14 width1 is a numeric bool alias.
    elif kind == "event_value":
        forged["events"][3]["value"] ^= 1
    elif kind == "boundary_missing":
        forged["string_boundaries"].pop()
    elif kind == "boundary_extra":
        forged["string_boundaries"][0]["extra"] = 0
    else:
        forged["string_boundaries"][0]["index"] = False
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(forged))
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def test_expected_results_are_detached(monkeypatch):
    vector = dict(alignment=0, profile=0, storage="heap")
    fixture = finite_fixture(vector)
    supplied = p.independent_packet(fixture)
    saved = copy.deepcopy(supplied)
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: supplied)
    result = c._expected(vector, fixture)
    result["events"][0]["value"] ^= 1
    result["string_boundaries"][0]["events"][0]["value"] ^= 1
    result["pages"][0] = bytes(4096)
    p.assert_strict_packet(supplied, saved)


def sources():
    return {
        key: json.loads(
            (
                PROGRAMS
                / (
                    PREFIX
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ).read_text(encoding="utf-8")
        )
        for key, (kind, _) in SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.EXE_SHA256
    codes, points = c._load_code(data, image, sources())
    assert len(points) == 259 and sum(map(len, codes.values())) == 914
    assert (
        canonical(points)
        == "14102b9cd0505d7c23fd0b31cab4d1d2865c0920cac89a37e976c2b571f95469"
    )
    return codes, points


def worker_packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_inputs()
    alignment = (0, 7, 15)[index // 4]
    profile = index % 3
    storage = "heap" if index % 2 == 0 else "parent_local"
    vector = dict(alignment=alignment, profile=profile, storage=storage)
    fixture = finite_fixture(vector)
    wanted = p.independent_packet(fixture)
    machines = []
    trace = []
    events = []
    boundaries = []
    captured = {}
    real_uc = uc.Uc

    def state(machine):
        flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
        return dict(
            registers={
                name: machine.reg_read(getattr(x, "UC_X86_REG_" + name.upper()))
                for name in p.GPRS
            },
            xmm={
                name: machine.reg_read(getattr(x, "UC_X86_REG_" + name.upper()))
                for name in p.XMMS
            },
            pages={
                page: bytes(machine.mem_read(page, 4096)) for page in fixture["pages"]
            },
            eflags=flags,
            flags=flags & 0x8D5,
            flag_mask=0x8D5,
            df=(flags >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    def own_code(machine, address, size, user):
        if address == fixture["return_address"]:
            return
        pc = address - 0x400000
        assert 0x7FD0 <= pc < 0x80C5 or 0x1999A0 <= pc < 0x199C3D
        if len(boundaries) < 14:
            expected = wanted["string_boundaries"][len(boundaries)]
            if address == expected["endpoint"]:
                actual = state(machine)
                boundaries.append(
                    dict(
                        name=expected["name"],
                        index=expected["index"],
                        **actual,
                        events=copy.deepcopy(events),
                    )
                )
        trace.append(f"0x{pc:08x}")

    def own_memory(machine, access, address, width, value, user):
        assert width in (1, 2, 4)
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value & ((1 << (width * 8)) - 1)
                    if writing
                    else int.from_bytes(machine.mem_read(address, width), "little")
                ),
            )
        )

    def observed_uc(*args, **kwargs):
        machine = real_uc(*args, **kwargs)
        machines.append(machine)
        original_set_cpu = machine.ctl_set_cpu_model
        attached = False

        def select_cpu_then_observe(cpu_model):
            nonlocal attached
            original_set_cpu(cpu_model)
            assert cpu_model == 19 and not attached
            machine.hook_add(uc.UC_HOOK_CODE, own_code)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, own_memory)
            attached = True

        machine.ctl_set_cpu_model = select_cpu_then_observe
        return machine

    def capture(machine, ids, expected, installed):
        assert machine is machines[0] and set(ids) == set(p.GPRS)
        p.assert_strict_packet(expected, wanted)
        p.assert_strict_packet(installed, fixture)
        captured.update(state(machine))

    uc.Uc = observed_uc
    try:
        observation = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = real_uc
    assert len(machines) == 1 and machines[0].ctl_get_cpu_model() == 19
    p.assert_strict_packet(trace, wanted["trace_rvas"])
    p.assert_strict_packet(events, wanted["events"])
    assert len(boundaries) == 14
    for actual, expected in zip(boundaries, wanted["string_boundaries"]):
        raw = actual.pop("eflags")
        assert raw == 0x287
        p.assert_strict_packet(actual, expected)
    expected_final = {
        k: wanted[k]
        for k in ("registers", "xmm", "pages", "flags", "flag_mask", "df", "endpoint")
    }
    assert captured.pop("eflags") == 0x287
    p.assert_strict_packet(captured, expected_final)
    assert set(observation) == OBS_KEYS
    assert all(set(boundary) == BOUNDARY_KEYS for boundary in observation["boundaries"])
    p.assert_strict_packet(observation, expected_observation(vector, wanted))


def worker_controls():
    codes, points = native_inputs()
    p.assert_strict_packet(c.CONTROLS, CONTROL_REASONS)
    vector = dict(alignment=15, profile=2, storage="parent_local")
    for name, reason in CONTROL_REASONS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, vector, name)
        assert str(caught.value) == reason, name


def worker_direct_codes():
    import unicorn as uc

    codes, points = native_inputs()
    real = uc.Uc

    def forbidden(*args, **kwargs):
        raise AssertionError("tampered code reached Unicorn construction")

    uc.Uc = forbidden
    try:
        for kind in (
            "float_key",
            "extra_body",
            "missing_body",
            "mutable",
            "short",
            "byte",
            "missing_point",
            "extra_point",
            "reordered",
            "bool_size",
            "point_hash",
        ):
            badcodes = copy.deepcopy(codes)
            badpoints = copy.deepcopy(points)
            start = min(codes)
            if kind == "float_key":
                payload = badcodes.pop(start)
                badcodes[float(start)] = payload
            elif kind == "extra_body":
                badcodes[0x1234] = bytes(1)
            elif kind == "missing_body":
                badcodes.pop(start)
            elif kind == "mutable":
                badcodes[start] = bytearray(badcodes[start])
            elif kind == "short":
                badcodes[start] = badcodes[start][:-1]
            elif kind == "byte":
                badcodes[start] = bytes([badcodes[start][0] ^ 1]) + badcodes[start][1:]
            elif kind == "missing_point":
                badpoints.pop()
            elif kind == "extra_point":
                badpoints.append(copy.deepcopy(badpoints[0]))
            elif kind == "reordered":
                badpoints.reverse()
            elif kind == "bool_size":
                badpoints[0]["size"] = True
            else:
                badpoints[0]["sha256"] = "0" * 64
            with pytest.raises(c.ConformanceError):
                c._run_case(
                    badcodes, badpoints, dict(alignment=0, profile=0, storage="heap")
                )
    finally:
        uc.Uc = real


def worker_forged_joins():
    codes, points = native_inputs()
    vector = dict(alignment=0, profile=0, storage="heap")
    fixture = finite_fixture(vector)
    original = c.model.apply
    try:
        for kind in ("boundary_gpr", "boundary_pages", "boundary_events", "trace"):
            forged = p.independent_packet(fixture)
            if kind == "boundary_gpr":
                forged["string_boundaries"][0]["registers"]["edx"] ^= 1
            elif kind == "boundary_pages":
                forged["string_boundaries"][0]["pages"][0] = bytes(4096)
            elif kind == "boundary_events":
                forged["string_boundaries"][0]["events"][0]["value"] ^= 1
            else:
                forged["trace_rvas"][1] = "0x001999a3"
            c.model.apply = lambda **kwargs: copy.deepcopy(forged)
            with pytest.raises(c.ConformanceError) as caught:
                c._run_case(codes, points, vector)
            assert str(caught.value) == (
                "default record native path differs"
                if kind == "trace"
                else "default record string boundary differs"
            )
    finally:
        c.model.apply = original


def cli_arguments(command):
    args = [sys.executable, str(CLI), command]
    for key, (kind, _) in SOURCE_PINS.items():
        args += [
            "--" + key.replace("_", "-"),
            str(
                PROGRAMS
                / (
                    PREFIX
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ),
        ]
    if command != "verify-structure":
        args += ["--executable", os.environ["ITB_EXACT_EXE"]]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    return args


def worker_rebuild():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    p.assert_strict_packet(
        c.build_conformance(os.environ["ITB_EXACT_EXE"], sources()), evidence
    )


def worker_cli():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    for command in ("build", "verify", "verify-structure"):
        result = subprocess.run(
            cli_arguments(command), cwd=ROOT, capture_output=True, timeout=2400
        )
        assert result.returncode == 0, (result.stdout + result.stderr).decode(
            "utf-8", errors="replace"
        )[-4000:]
        value = json.loads(result.stdout)
        assert (
            result.stdout == c.encode_conformance(value).encode("utf-8")
            and b"\r" not in result.stdout
        )
        if command == "build":
            p.assert_strict_packet(value, evidence)
        else:
            p.assert_strict_packet(
                value,
                dict(
                    status=(
                        "verified" if command == "verify" else "structurally_verified"
                    ),
                    evidence_sha256=c.SEALED_SHA256,
                    summary=evidence["summary"],
                ),
            )


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("primary must provide reviewed exact executable/runtime")
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
    )[-5000:]


@pytest.mark.parametrize("index", range(12))
def test_actual_single_machine_independent_trace_events_and_all_boundaries(index):
    isolated("packet", index)


def test_all_machine_and_record_controls():
    isolated("controls")


def test_direct_code_packets_fail_before_machine_construction():
    isolated("direct")


def test_forged_model_joins_fail_at_actual_native_boundary():
    isolated("joins")


def test_exact_native_rebuild():
    isolated("rebuild")


def test_exact_three_cli_commands():
    isolated("cli")


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("primary must publish the sealed receipt")
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_published_receipt_identity_points_recipes_and_independent_totals(receipt):
    raw = EVIDENCE.read_bytes()
    assert b"\r" not in raw and raw == c.encode_conformance(receipt).encode("utf-8")
    assert canonical(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    p.assert_strict_packet(receipt["vectors"], recipes())
    assert c.SOURCE_PINS == SOURCE_PINS and len(receipt["source_receipts"]) == 2
    for key, pin in SOURCE_PINS.items():
        assert canonical(sources()[key]) == pin[1]
        assert receipt["source_receipts"][key]["canonical_sha256"] == pin[1]
    assert (
        canonical(receipt["body"]["points"])
        == "14102b9cd0505d7c23fd0b31cab4d1d2865c0920cac89a37e976c2b571f95469"
    )
    assert len(receipt["body"]["points"]) == 259
    assert receipt["body"]["ranges"] == [
        dict(
            start_rva="0x00007fd0",
            exclusive_end_rva="0x000080c5",
            sha256="c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906",
        ),
        dict(
            start_rva="0x001999a0",
            exclusive_end_rva="0x00199c3d",
            sha256="2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d",
        ),
    ]
    assert receipt["executed_rvas"] == [
        f"0x{pc:08x}" for pc in sorted(set(p.OWNER_TRACE + p.HELPER_TRACE))
    ]
    assert receipt["engine"] == dict(
        name="Unicorn",
        version="2.1.4",
        architecture="x86_32",
        cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
    )
    p.assert_strict_packet(
        {row["name"]: row["reason"] for row in receipt["negative_controls"]},
        CONTROL_REASONS,
    )
    assert len(receipt["negative_controls"]) == 29 and all(
        row["rejected"] is True for row in receipt["negative_controls"]
    )
    assert (
        receipt["scope"]["claim"]
        == "Finite continuous default308-byte record constructor and seven source-below-inline length-zero string assignments"
    )
    totals = dict(
        cases=96,
        heap_cases=48,
        parent_local_cases=48,
        loaded_sites=259,
        loaded_bytes=914,
        executed_sites=164,
        native_instructions=356 * 96,
        memory_events=217 * 96,
        string_calls=7 * 96,
        string_boundaries=14 * 96,
        record_bytes=308 * 96,
        record_written_bytes=183 * 96,
        record_padding_bytes=125 * 96,
        allocation_requests=0,
        copy_requests=0,
        free_requests=0,
        opaque_instructions=0,
        accounting_promotions=0,
        controls=29,
    )
    p.assert_strict_packet(receipt["summary"], totals)
    observations = [
        expected_observation(vector, p.independent_packet(finite_fixture(vector)))
        for vector in recipes()
    ]
    assert receipt["observations_sha256"] == canonical(observations)


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool_summary",
        "vector",
        "control",
        "point",
        "range",
        "observations",
        "pin",
        "scope",
        "extra",
    ),
)
def test_sealed_receipt_forgeries(kind, receipt):
    bad = copy.deepcopy(receipt)
    if kind == "summary":
        bad["summary"]["record_padding_bytes"] += 1
    elif kind == "bool_summary":
        bad["summary"]["free_requests"] = False
    elif kind == "vector":
        bad["vectors"][0]["alignment"] = True
    elif kind == "control":
        bad["negative_controls"][0]["rejected"] = False
    elif kind == "point":
        bad["body"]["points"][0]["size"] += 1
    elif kind == "range":
        bad["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observations":
        bad["observations_sha256"] = "0" * 64
    elif kind == "pin":
        bad["source_receipts"]["movement_binding"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        bad["scope"]["claim"] = "whole game constructor ownership"
    else:
        bad["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "nonmapping",
        "source_kind",
        "source_body",
        "source_build",
        "nonfinite",
    ),
)
def test_source_partition_identity_and_json(kind, monkeypatch):
    supplied = sources()
    if kind == "missing":
        supplied.pop("movement_binding")
    elif kind == "extra":
        supplied["extra"] = {}
    elif kind == "nonmapping":
        supplied = list(supplied.values())
    elif kind == "source_kind":
        supplied["movement_binding"]["analysis_kind"] = "forged"
    elif kind == "source_body":
        supplied["movement_binding"]["bodies"]["move_parent"]["size"] += 1
    elif kind == "nonfinite":
        supplied["movement_binding"]["unexpected"] = float("nan")
    else:
        supplied["movement_binding"]["build_identity"]["executable_sha256"] = "0" * 64
        changed = dict(c.SOURCE_PINS)
        changed["movement_binding"] = (
            changed["movement_binding"][0],
            canonical(supplied["movement_binding"]),
        )
        monkeypatch.setattr(c, "SOURCE_PINS", changed)
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_every_source_pin_rejects_changed_document(key):
    supplied = sources()
    supplied[key]["extra_unpinned_field"] = 0
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_structure_summary_detachment(receipt):
    result = c.validate_structure(receipt, sources())
    result["summary"]["cases"] = 0
    assert receipt["summary"]["cases"] == 96


def test_strict_encoder_and_json_schema(receipt):
    assert c.encode_conformance({"text": "café"}) == '{\n  "text": "café"\n}\n'
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            c.encode_conformance({"bad": value})
    bad = copy.deepcopy(receipt)
    bad["summary"]["cases"] = float("nan")
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind", ("noncanonical", "duplicate", "nonfinite", "invalid_utf8")
)
def test_cli_rejects_malformed_or_nondeterministic_evidence(tmp_path, receipt, kind):
    raw = c.encode_conformance(receipt).encode("utf-8")
    if kind == "noncanonical":
        raw = b" " + raw
    elif kind == "duplicate":
        raw = b'{"analysis_kind":"a","analysis_kind":"b"}\n'
    elif kind == "nonfinite":
        raw = b'{"value":NaN}\n'
    else:
        raw = b"\xff"
    path = tmp_path / "malformed.json"
    path.write_bytes(raw)
    args = cli_arguments("verify-structure")
    args[-1] = str(path)
    result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
    assert (
        result.returncode == 1 and result.stdout == b"" and b"error:" in result.stderr
    )


if __name__ == "__main__":
    action = sys.argv[1]
    index = int(sys.argv[2])
    {
        "packet": lambda: worker_packet(index),
        "controls": worker_controls,
        "direct": worker_direct_codes,
        "joins": worker_forged_joins,
        "rebuild": worker_rebuild,
        "cli": worker_cli,
    }[action]()
