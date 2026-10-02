"""Independent finite fixtures, continuous observers and record-copy2 receipt.

Expected owner and lower packets come from the handwritten pure test law.
Observation hooks run after CPU selection and independently collect machine state.
"""

from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from collections import UserDict
import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_movement_effect_record_copy2_conformance as c
from tests import test_itb_native_movement_effect_record_copy2_semantics as pure

strict_equal, store, read_bytes = pure.strict_equal, pure.store, pure.read_bytes
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_movement_effect_record_copy2_conformance.json")
CLI = ROOT / "scripts/itb_native_movement_effect_record_copy2_conformance.py"
SEAL = "594b01e901b028f23bc8a75857d9ddf775b481b22285bdaca74fe301753f5489"
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
    "allocation_composition": (
        "pe_native_vector_allocation_composition",
        "a63d7ef54e07f8aa63449136988a237592704708ab35cbefb203ec843e8e5507",
    ),
    "allocation_conformance": (
        "pe_native_vector_allocation_conformance",
        "8a2af8e009d4f67b672e92e9fd12bce6a5c32feb609af95f2ee1dc61fb1e9d29",
    ),
    "clone2_conformance": (
        "pe_native_movement_path_clone2_conformance",
        "1cddf384c45fb50a60752656acd2560a7e243dd20f0d68b8a963a4a7bb3a739b",
    ),
}
BODY_PINS = {
    0x15B9B0: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    0x80D0: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    0x9A8E0: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    0x9AC40: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    0x8ABA0: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    0x8A920: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    0x3574DB: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    0x379F52: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    0x38942B: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
}
POINTS_SHA = "4153ee13abbc8b63b43b1d04d1f5bc64b57ec7e28ba8d7e262f2b420c0714a5d"
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
    "summaries",
}
BOUNDARY_KEYS = {
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
SUMMARY_KEYS = {
    "role",
    "registers",
    "xmm",
    "eflags",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "pages_sha256",
    "events_sha256",
    "entry_esp",
    "words",
}
PATH_NAMES = (
    "parent_entry",
    "reserve_entry",
    "allocation_entry",
    "allocation_return",
    "reserve_return",
    "scalar_entry",
    "scalar_return",
)
ROLES = ("outer_entry", "string_entry", "string_return") + tuple(
    "path_" + name for name in PATH_NAMES
)
CONTROL_REASONS = {
    **{
        role + "_" + kind: "record copy2 " + role.replace("_", " ") + " differs"
        for role in ROLES
        for kind in ("gpr", "xmm", "flags", "df", "page")
    },
    **{
        name: "record copy2 ordered memory differs"
        for name in ("caller_source", "source_size", "destination_capacity")
    },
    **{
        name: "record copy2 final pages differ"
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
            "path_source",
            "path_buffer",
            "path_capacity",
            "heap_padding",
            "iat_padding",
        )
    },
    **{
        name: "record copy2 final ABI differs"
        for name in (
            "final_gpr",
            "final_edx",
            "final_xmm",
            "final_flags",
            "final_df",
            "final_endpoint",
        )
    },
    "missing_read_record": "record copy2 final events differ",
    "restored_write_record": "record copy2 final events differ",
    "trace_record": "record copy2 final native path differs",
    "heap_request": "record copy2 allocation handoff differs",
    **{
        name: "record copy2 allocation imported ABI differs"
        for name in ("heap_gpr", "heap_xmm", "heap_flags", "heap_df", "heap_page")
    },
    **{
        name: "record copy2 supplied response preservation differs"
        for name in (
            "response_result",
            "response_gpr",
            "response_xmm",
            "response_page",
            "response_flags",
        )
    },
    "reserve_full_eax": "record copy2 path reserve return differs",
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
        f"0x{base:08x}": hashlib.sha256(payload).hexdigest()
        for base, payload in sorted(pages.items())
    }


def recipes():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def finite_fixture(vector):
    a, p = vector["alignment"], vector["profile"]
    g, s, d = 0x30001000 + a, 0x10000FF0 + a, 0x10002FF0 + a
    bases = (
        0,
        0x30000000,
        0x30001000,
        0x10000000,
        0x10001000,
        0x10002000,
        0x10003000,
        0x00893000,
        0x06000000,
        0x06001000,
        0x06002000,
        0x06003000,
        0x008B7000,
        0x007D6000,
    )
    pages = {
        base: bytes((i * 31 + j * 23 + p * 67) & 255 for j in range(4096))
        for i, base in enumerate(bases)
    }
    for at, value in (
        (g, 0x04000000),
        (g + 4, s),
        (0, (0x1234ABCD + p * 0x12345) & 0xFFFFFFFF),
        (0x00893F28, (0x6D3FA172 ^ (p * 0x11111111)) & 0xFFFFFFFF),
        (s, (0xBF800000, 0x7FC01234, 0xFF800000)[p]),
        (0x008B7634, 0x12345678),
        (0x007D6220, 0x05000000),
        (s + 0xCC, 0x06002FF9 + a),
        (s + 0xD0, 0x06003009 + a),
        (s + 0xD4, (0, 0xFFFFFFFF, 0xDEADBEEF)[p]),
    ):
        store(pages, at, value)
    for off in (0x38, 0x50, 0x68, 0x80, 0xA4, 0xE0, 0xF8, 0x118):
        store(pages, s + off, 0, 1)
        store(pages, s + off + 16, 0)
        store(pages, s + off + 20, 15)
    for i, word in enumerate((0xD15C0016, 0xFFFFFFFF, 0x80000000, 0x8765DD16)):
        store(pages, 0x06002FF9 + a + 4 * i, word ^ (p * 0x07654321))
    regs = {
        name: (0x12345678 + i * 0x11111111 + p * 0x1234) & 0xFFFFFFFF
        for i, name in enumerate(GPR)
    }
    regs.update(esp=g, ecx=d)
    xmm = {
        name: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 73) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=0x04000000,
        entry_flags=0x246,
        allocation_result=0x06001103 + a,
    )


def expected_states(fixture, wanted):
    return [
        dict(
            kind="outer",
            name="entry",
            index=0,
            registers=dict(fixture["registers"]),
            xmm=dict(fixture["xmm"]),
            pages=dict(fixture["pages"]),
            events=[],
            flags=0x44,
            flag_mask=0x8D5,
            df=0,
            endpoint=0x0055B9B0,
        )
    ] + copy.deepcopy(wanted["boundaries"])


def imported_state(wanted):
    state = copy.deepcopy(wanted["path_packet"]["imported"])
    state["events"] = copy.deepcopy(wanted["events"][:195]) + state["events"]
    return state


def expected_observation(vector, fixture, wanted):
    def metadata(state):
        # CPU19 finite raw words, separately from architectural defined masks.
        raw = (
            state["flags"]
            if state["flag_mask"] == 0xFFFFFFFF
            else state["flags"] | 0x202
        )
        return dict(
            registers=dict(state["registers"]),
            xmm=dict(state["xmm"]),
            eflags=raw,
            flags=state["flags"],
            flag_mask=state["flag_mask"],
            df=0,
            endpoint=state["endpoint"],
            pages_sha256=page_hashes(state["pages"]),
            events_sha256=canonical(state["events"]),
        )

    boundaries = []
    for state in expected_states(fixture, wanted):
        row = metadata(state)
        row.update(kind=state["kind"], name=state["name"], index=state["index"])
        boundaries.append(row)
    imported = imported_state(wanted)
    summary = metadata(imported)
    summary.update(
        role="allocation", entry_esp=imported["entry_esp"], words=imported["words"]
    )
    return dict(
        vector=dict(vector),
        registers=wanted["registers"],
        xmm=wanted["xmm"],
        eflags=0x287,
        flags=0x85,
        flag_mask=0x8D5,
        df=0,
        endpoint=0x04000000,
        trace_rvas=wanted["trace_rvas"],
        events_sha256=canonical(wanted["events"]),
        pages_sha256=page_hashes(wanted["pages"]),
        memory_event_count=372,
        boundaries=boundaries,
        summaries=[summary],
    )


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
        for key, (kind, digest) in SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.EXE_SHA256
    codes, points = c._load_code(data, image, sources())
    assert (
        len(points) == 498
        and sum(map(len, codes.values())) == 1500
        and canonical(points) == POINTS_SHA
    )
    return codes, points


def worker_packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = recipes()[index]
    fixture = finite_fixture(vector)
    wanted = pure.independent(fixture)
    states = expected_states(fixture, wanted)
    imported = imported_state(wanted)
    machines = []
    observed_trace = []
    events = []
    boundaries = []
    imports = []
    starts = []
    captured = {}
    cursor = 0
    real = uc.Uc

    def state(machine, mask):
        raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
        return dict(
            registers={
                name: machine.reg_read(getattr(x, "UC_X86_REG_" + name.upper()))
                for name in GPR
            },
            xmm={
                name: machine.reg_read(getattr(x, "UC_X86_REG_" + name.upper()))
                for name in XMM
            },
            pages={
                base: bytes(machine.mem_read(base, 4096)) for base in fixture["pages"]
            },
            eflags=raw,
            flags=raw & mask,
            flag_mask=mask,
            df=(raw >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    def own_code(machine, address, size, user):
        nonlocal cursor
        if address == 0x04000000:
            return
        if address == 0x05000000:
            row = state(machine, 0x8C5)
            sp = machine.reg_read(x.UC_X86_REG_ESP)
            row.update(
                events=copy.deepcopy(events),
                entry_esp=sp,
                words=[
                    int.from_bytes(machine.mem_read(sp + 4 * i, 4), "little")
                    for i in range(4)
                ],
            )
            imports.append(row)
            return
        assert address - 0x400000 in set(pure.TRACE)
        if cursor < len(states) and address == states[cursor]["endpoint"]:
            expected = states[cursor]
            row = state(machine, expected["flag_mask"])
            row.update(
                kind=expected["kind"],
                name=expected["name"],
                index=expected["index"],
                events=copy.deepcopy(events),
            )
            boundaries.append(row)
            cursor += 1
        observed_trace.append(f"0x{address-0x400000:08x}")

    def own_memory(machine, access, address, width, value, user):
        assert width in (1, 4)
        writing = access == uc.UC_MEM_WRITE
        events.append(
            dict(
                access="write" if writing else "read",
                address=address,
                width=width,
                value=(
                    value & ((1 << (8 * width)) - 1)
                    if writing
                    else int.from_bytes(machine.mem_read(address, width), "little")
                ),
            )
        )

    def observed(*args, **kwargs):
        machine = real(*args, **kwargs)
        machines.append(machine)
        original_cpu = machine.ctl_set_cpu_model
        attached = False

        def select_then_observe(cpu_model):
            nonlocal attached
            original_cpu(cpu_model)
            assert cpu_model == 19 and not attached
            machine.hook_add(uc.UC_HOOK_CODE, own_code)
            machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, own_memory)
            attached = True

        machine.ctl_set_cpu_model = select_then_observe
        original_start = machine.emu_start

        def start(*args, **kwargs):
            starts.append((args, dict(kwargs)))
            result = original_start(*args, **kwargs)
            if len(starts) == 1:
                response = state(machine, 0xFFFFFFFF)
                assert response.pop("eflags") == 0x246
                strict_equal(
                    response,
                    dict(
                        registers=dict(
                            imported["registers"],
                            eax=fixture["allocation_result"],
                            ecx=0xA0000001,
                            edx=0xB0000001,
                            esp=imported["entry_esp"] + 16,
                        ),
                        xmm=imported["xmm"],
                        pages=imported["pages"],
                        flags=0x246,
                        flag_mask=0xFFFFFFFF,
                        df=0,
                        endpoint=0x05000000,
                    ),
                )
            return result

        machine.emu_start = start
        return machine

    def capture(machine, ids, expected, installed):
        assert machine is machines[0] and set(ids) == set(GPR)
        strict_equal(expected, wanted)
        strict_equal(installed, fixture)
        captured.update(state(machine, 0x8D5))
        expected["boundaries"].clear()
        installed["pages"].clear()

    uc.Uc = observed
    try:
        observation = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = real
    assert len(machines) == 1 and machines[0].ctl_get_cpu_model() == 19
    assert starts == [
        ((0x0055B9B0, 0), {"count": 10000}),
        ((0x00789463, 0), {"count": 10000}),
    ]
    strict_equal(observed_trace, wanted["trace_rvas"])
    strict_equal(events, wanted["events"])
    assert len(boundaries) == 24 and cursor == 24 and len(imports) == 1
    for actual, expected in zip(boundaries, states):
        raw = actual.pop("eflags")
        assert raw == (
            expected["flags"]
            if expected["flag_mask"] == 0xFFFFFFFF
            else expected["flags"] | 0x202
        )
        strict_equal(actual, expected)
    assert imports[0].pop("eflags") == 0x202
    strict_equal(imports[0], imported)
    assert captured.pop("eflags") == 0x287
    strict_equal(
        captured,
        {
            key: wanted[key]
            for key in (
                "registers",
                "xmm",
                "pages",
                "flags",
                "flag_mask",
                "df",
                "endpoint",
            )
        },
    )
    assert set(observation) == OBS_KEYS and all(
        set(row) == BOUNDARY_KEYS for row in observation["boundaries"]
    )
    assert all(set(row) == SUMMARY_KEYS for row in observation["summaries"])
    strict_equal(observation, expected_observation(vector, fixture, wanted))
    return observation


def worker_corpus():
    observations = [worker_packet(i) for i in range(48)]
    evidence = json.loads(EVIDENCE.read_text())
    assert canonical(observations) == evidence["observations_sha256"]
    assert sum(len(row["boundaries"]) for row in observations) == 1152


def worker_controls():
    codes, points = native_inputs()
    strict_equal(c.CONTROLS, CONTROL_REASONS)
    assert len(CONTROL_REASONS) == 90
    for name, reason in CONTROL_REASONS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, dict(alignment=15, profile=2), name)
        assert str(caught.value) == reason, name


def worker_direct_codes():
    import unicorn as uc

    codes, points = native_inputs()
    real = uc.Uc

    def forbidden(*args, **kwargs):
        raise AssertionError("forged code reached Uc")

    uc.Uc = forbidden
    try:
        for kind in (
            "floatkey",
            "extra",
            "missing",
            "mutable",
            "short",
            "byte",
            "missingpoint",
            "extrapoint",
            "reverse",
            "boolsize",
            "hash",
            "extra_point_field",
        ):
            code = copy.deepcopy(codes)
            rows = copy.deepcopy(points)
            start = min(code)
            if kind == "floatkey":
                code[float(start)] = code.pop(start)
            elif kind == "extra":
                code[1] = bytes(1)
            elif kind == "missing":
                code.pop(start)
            elif kind == "mutable":
                code[start] = bytearray(code[start])
            elif kind == "short":
                code[start] = code[start][:-1]
            elif kind == "byte":
                code[start] = bytes([code[start][0] ^ 1]) + code[start][1:]
            elif kind == "missingpoint":
                rows.pop()
            elif kind == "extrapoint":
                rows.append(copy.deepcopy(rows[0]))
            elif kind == "reverse":
                rows.reverse()
            elif kind == "boolsize":
                rows[0]["size"] = True
            elif kind == "hash":
                rows[0]["sha256"] = "0" * 64
            else:
                rows[0]["extra"] = 0
            with pytest.raises(c.ConformanceError):
                c._run_case(code, rows, dict(alignment=0, profile=0))
    finally:
        uc.Uc = real


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
    strict_equal(
        c.build_conformance(os.environ["ITB_EXACT_EXE"], sources()),
        json.loads(EVIDENCE.read_text(encoding="utf-8")),
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
            strict_equal(value, evidence)
        else:
            strict_equal(
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
        pytest.skip("root must provide reviewed exact executable/runtime")
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


@pytest.mark.parametrize("index", (0, 1, 2, 21, 22, 23, 45, 46, 47))
def test_actual_one_machine_two_starts_full_ordered_state(index):
    isolated("packet", index)


def test_all_48_independent_machine_observations_and_digest():
    isolated("corpus")


def test_all_90_intended_controls():
    isolated("controls")


def test_direct_code_forgeries_before_machine_creation():
    isolated("direct")


def test_exact_native_rebuild():
    isolated("rebuild")


def test_exact_three_cli_commands():
    isolated("cli")


@pytest.mark.parametrize("vector", recipes())
def test_complete_independent_finite_fixture_and_15_field_packet(vector):
    fixture = finite_fixture(vector)
    strict_equal(c._fixture(vector), fixture)
    wanted = pure.independent(fixture)
    actual = c._expected(vector, fixture)
    pure.check(actual, fixture)
    strict_equal(actual, wanted)
    assert len(wanted["events"]) == 372 and len(wanted["trace_rvas"]) == 591
    assert len(wanted["boundaries"]) == 23 and len(set(pure.TRACE)) == 350


@pytest.mark.parametrize(
    "kind",
    ("bool", "float", "extra", "missing", "profile", "alignment", "list", "mapping"),
)
def test_closed_vector_recipe(kind):
    vector = dict(alignment=0, profile=0)
    if kind == "bool":
        vector["alignment"] = False
    elif kind == "float":
        vector["profile"] = 0.0
    elif kind == "extra":
        vector["extra"] = 0
    elif kind == "missing":
        vector.pop("profile")
    elif kind == "profile":
        vector["profile"] = 3
    elif kind == "alignment":
        vector["alignment"] = 16
    elif kind == "mapping":
        vector = UserDict(vector)
    else:
        vector = list(vector.items())
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "boolflags",
        "gpr",
        "xmm",
        "return",
        "allocation",
        "source",
        "ancestor",
        "cookie",
        "heap",
        "iat",
        "padding",
        "mutable",
        "mapping",
    ),
)
def test_fixture_exact_closed_recipe(kind):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    if kind == "extra":
        fixture["extra"] = 0
    elif kind == "missing":
        fixture.pop("xmm")
    elif kind == "boolflags":
        fixture["entry_flags"] = True
    elif kind == "gpr":
        fixture["registers"]["eax"] ^= 1
    elif kind == "xmm":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind == "return":
        fixture["return_address"] ^= 1
    elif kind == "allocation":
        fixture["allocation_result"] += 4
    elif kind == "mutable":
        fixture["pages"][0] = bytearray(fixture["pages"][0])
    elif kind == "mapping":
        fixture = UserDict(fixture)
    else:
        at = {
            "source": 0x10000FF0,
            "ancestor": 0x30001008,
            "cookie": 0x893F28,
            "heap": 0x8B7634,
            "iat": 0x7D6220,
            "padding": 0x10002001,
        }[kind]
        store(fixture["pages"], at, read_bytes(fixture["pages"], at, 1)[0] ^ 1, 1)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "df",
        "endpoint",
        "gpr",
        "xmm",
        "field",
        "padding",
        "source",
        "pages",
        "eventmissing",
        "eventwidth",
        "trace",
        "boundarytuple",
        "boundarygpr",
        "boundarypage",
        "pathsnapshot",
        "pathcoordinated",
    ),
)
def test_model_packet_guard_rejects_independent_forgeries(kind, monkeypatch):
    vector = dict(alignment=15, profile=2)
    fixture = finite_fixture(vector)
    packet = pure.independent(fixture)
    g = fixture["registers"]["esp"]
    d = fixture["registers"]["ecx"]
    if kind == "extra":
        packet["extra"] = 0
    elif kind == "missing":
        packet.pop("xmm")
    elif kind == "df":
        packet["df"] = False
    elif kind == "endpoint":
        packet["endpoint"] = float(packet["endpoint"])
    elif kind == "gpr":
        packet["registers"]["edx"] ^= 1
    elif kind == "xmm":
        packet["xmm"]["xmm7"] ^= 1
    elif kind in ("field", "padding"):
        off = 0 if kind == "field" else 0x32
        b = bytearray(packet["record_bytes"])
        b[off] ^= 1
        packet["record_bytes"] = bytes(b)
        store(packet["pages"], d + off, b[off], 1)
    elif kind == "source":
        packet["source_snapshot"] = bytes(308)
    elif kind == "pages":
        store(packet["pages"], g + 8, 0, 1)
    elif kind == "eventmissing":
        packet["events"].pop(0)
    elif kind == "eventwidth":
        packet["events"][0]["width"] = 4.0
    elif kind == "trace":
        packet["trace_rvas"][-1] = "0x0015b9b0"
    elif kind == "boundarytuple":
        packet["boundaries"] = tuple(packet["boundaries"])
    elif kind == "boundarygpr":
        packet["boundaries"][-1]["registers"]["edx"] ^= 1
    elif kind == "boundarypage":
        store(packet["boundaries"][14]["pages"], 0x893001, 0, 1)
    elif kind == "pathsnapshot":
        packet["path_packet"]["source_snapshot"] = bytes(16)
    else:
        child = packet["path_packet"]
        child["scalar_packet"]["source_snapshot"] = bytes(16)
        child["scalar_packet"]["registers"]["ecx"] = 0
        child["registers"]["ecx"] = 0
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(packet))
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


@pytest.mark.parametrize("child", ("allocation", "scalar"))
@pytest.mark.parametrize(
    "kind", ("extra", "missing", "bool", "gpr", "pages", "events", "coordinated")
)
def test_complete_7_and_10_field_child_join(child, kind, monkeypatch):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    wanted = pure.independent(fixture)
    packet = copy.deepcopy(
        wanted["path_packet"][
            "allocation_packet" if child == "allocation" else "scalar_packet"
        ]
    )
    if child == "allocation":
        packet["events"][-1]["value"] = 0x04000000
    if kind == "extra":
        packet["extra"] = 0
    elif kind == "missing":
        packet.pop("flag_mask")
    elif kind == "bool":
        if child == "scalar":
            packet["df"] = False
        else:
            packet["flag_mask"] = float(packet["flag_mask"])
    elif kind == "gpr":
        packet["registers"]["edx"] ^= 1
    elif kind == "pages":
        if child == "scalar":
            store(packet["pages"], 0x893001, 0, 1)
        else:
            packet["payload"] = (
                bytes([packet["payload"][0] ^ 1]) + packet["payload"][1:]
            )
    elif kind == "events":
        packet["events"].pop()
    else:
        packet["registers"]["eax"] ^= 1
        packet["events"][0]["value"] ^= 1
        if child == "allocation":
            packet["relation"]["result"] ^= 1
        else:
            packet["source_snapshot"] = bytes(16)
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(wanted))
    target = c.allocator if child == "allocation" else c.scalar
    monkeypatch.setattr(
        target,
        "_expected" if child == "allocation" else "apply",
        lambda *args, **kwargs: copy.deepcopy(packet),
    )
    with pytest.raises(
        c.ConformanceError, match="record copy2 path " + child + " primitive differs"
    ):
        c._expected(vector, fixture)


def test_only_canonical_allocation_ret_is_rebound():
    fixture = finite_fixture(dict(alignment=0, profile=0))
    wanted = pure.independent(fixture)
    state = wanted["path_packet"]["boundaries"]["allocation_entry"]
    pages = dict(state["pages"])
    store(pages, state["registers"]["esp"], 0x04000000)
    with pytest.raises(c.ConformanceError, match="installed continuation differs"):
        c._allocation_packet_law(
            state["registers"],
            pages,
            fixture["allocation_result"],
            0x49AC78,
            0x30000000,
        )


def test_expected_and_fixture_are_detached():
    vector = dict(alignment=7, profile=1)
    fixture = finite_fixture(vector)
    before = copy.deepcopy(fixture)
    actual = c._expected(vector, fixture)
    strict_equal(actual, pure.independent(fixture))
    actual["path_packet"]["scalar_packet"]["pages"].clear()
    actual["boundaries"][0]["events"].clear()
    actual["xmm"].clear()
    actual["pages"].clear()
    strict_equal(fixture, before)
    strict_equal(c._expected(vector, fixture), pure.independent(fixture))


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("root must publish sealed receipt")
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_published_receipt_scope_points_pins_and_independent_corpus(receipt):
    assert canonical(receipt) == SEAL == c.SEALED_SHA256
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert (
        len(raw) == 104314
        and hashlib.sha256(raw).hexdigest()
        == "4c24d3861e840ff247d441adf16d86f5454985f1bbe76212d30008762dd869d3"
    )
    assert (
        receipt["analysis_kind"] == "pe_native_movement_effect_record_copy2_conformance"
    )
    strict_equal(c.SOURCE_PINS, SOURCE_PINS)
    strict_equal(c.BODY_PINS, BODY_PINS)
    strict_equal(receipt["vectors"], recipes())
    strict_equal(c.vectors(), recipes())
    supplied = sources()
    strict_equal(receipt["build_identity"], supplied["program_facts"]["identity"])
    assert set(receipt["source_receipts"]) == set(SOURCE_PINS)
    for key, (kind, digest) in SOURCE_PINS.items():
        assert canonical(supplied[key]) == digest
        strict_equal(
            receipt["source_receipts"][key],
            dict(analysis_kind=kind, canonical_sha256=digest),
        )
    ranges = receipt["body"]["ranges"]
    strict_equal(
        ranges,
        [
            dict(
                start_rva=f"0x{start:08x}",
                exclusive_end_rva=f"0x{start+size:08x}",
                sha256=digest,
            )
            for start, (size, digest) in sorted(BODY_PINS.items())
        ],
    )
    points = receipt["body"]["points"]
    assert (
        len(points) == 498
        and sum(row["size"] for row in points) == 1500
        and canonical(points) == POINTS_SHA
    )
    assert len({row["rva"] for row in points}) == 498
    assert points == sorted(points, key=lambda row: int(row["rva"], 16))
    for start, (size, digest) in BODY_PINS.items():
        cursor = start
        for point in points:
            at = int(point["rva"], 16)
            if start <= at < start + size:
                assert (
                    set(point) == {"rva", "size", "sha256"}
                    and type(point["size"]) is int
                )
                assert at == cursor
                cursor += point["size"]
        assert cursor == start + size
    strict_equal(receipt["executed_rvas"], sorted({f"0x{pc:08x}" for pc in pure.TRACE}))
    observations = [
        expected_observation(v, finite_fixture(v), pure.independent(finite_fixture(v)))
        for v in recipes()
    ]
    assert receipt["observations_sha256"] == canonical(observations)
    strict_equal(
        receipt["engine"],
        dict(
            name="Unicorn",
            version="2.1.4",
            architecture="x86_32",
            cpu_model=dict(id=19, name="UC_CPU_X86_HASWELL"),
        ),
    )
    strict_equal(
        receipt["summary"],
        dict(
            accounting_promotions=0,
            allocation_requests=48,
            allocation_snapshots=48,
            api_responses=48,
            cases=48,
            controls=90,
            cookie_checker_calls=0,
            copied_path_bytes=768,
            copied_scalar_bytes=4752,
            empty_string_calls=384,
            empty_string_field_bytes=3456,
            executed_sites=350,
            free_requests=0,
            loaded_bytes=1500,
            loaded_sites=498,
            memory_events=17856,
            native_boundary_snapshots=1152,
            native_instructions=28368,
            opaque_instructions=0,
            path_clone_calls=48,
            path_header_bytes=576,
            path_source_bytes_preserved=768,
            record_bytes=14784,
            record_padding_bytes_preserved=6000,
            record_written_bytes=8784,
            requested_allocation_bytes=768,
            reserve_calls=48,
            scalar_clone_calls=48,
            source_bytes_preserved=14784,
            wide_reads=0,
            wide_writes=0,
            xmm_preserved_cases=48,
        ),
    )
    strict_equal(
        receipt["negative_controls"],
        [
            dict(name=name, rejected=True, reason=reason)
            for name, reason in CONTROL_REASONS.items()
        ],
    )
    assert (
        len(CONTROL_REASONS) == 90
        and sum(name.endswith("_record") for name in CONTROL_REASONS) == 3
    )
    text = " ".join(receipt["scope"]["premises"] + receipt["scope"]["not_claimed"])
    for term in (
        "twenty-three",
        "supplied",
        "372",
        "183",
        "125",
        "same-count",
        "record mutations",
        "cookie checker",
    ):
        assert term in text


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
        bad["summary"]["copied_path_bytes"] += 1
    elif kind == "bool_summary":
        bad["summary"]["free_requests"] = False
    elif kind == "vector":
        bad["vectors"][0]["alignment"] = False
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
        bad["scope"]["claim"] = "whole game ownership"
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
        "kind",
        "body",
        "build",
        "nonfinite",
        "atlas",
        "duplicate",
        "boolsize",
        "floatbuild",
    ),
)
def test_source_preflight_identity_and_refreshed_pins(kind, monkeypatch):
    supplied = sources()
    if kind == "missing":
        supplied.pop("movement_binding")
    elif kind == "extra":
        supplied["extra"] = {}
    elif kind == "nonmapping":
        supplied = list(supplied.values())
    elif kind == "kind":
        supplied["movement_binding"]["analysis_kind"] = "forged"
    elif kind == "body":
        supplied["movement_binding"]["bodies"]["move_parent"]["size"] += 1
    elif kind == "nonfinite":
        supplied["movement_binding"]["bad"] = float("nan")
    else:
        key = "movement_binding" if kind in ("build", "floatbuild") else "program_facts"
        if kind == "build":
            supplied[key]["build_identity"]["executable_sha256"] = "0" * 64
        elif kind == "floatbuild":
            supplied[key]["build_identity"]["executable_size"] = float(
                supplied[key]["build_identity"]["executable_size"]
            )
        elif kind == "duplicate":
            supplied[key]["functions"].append(
                copy.deepcopy(supplied[key]["functions"][0])
            )
        else:
            row = next(
                r for r in supplied[key]["functions"] if r["entry_rva"] == "0x0008aba0"
            )
            row["body_size"] = True if kind == "boolsize" else row["body_size"] + 1
        changed = dict(c.SOURCE_PINS)
        changed[key] = (changed[key][0], canonical(supplied[key]))
        monkeypatch.setattr(c, "SOURCE_PINS", changed)
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_every_pin_is_closed(key):
    supplied = sources()
    supplied[key]["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_structure_summary_detached(receipt):
    result = c.validate_structure(receipt, sources())
    result["summary"]["cases"] = 0
    assert receipt["summary"]["cases"] == 48


def test_encoder_utf8_and_nonfinite(receipt):
    assert (
        c.encode_conformance({"text": "caf\u00e9"}) == '{\n  "text": "caf\u00e9"\n}\n'
    )
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
def test_cli_malformed_evidence_rejects(tmp_path, receipt, kind):
    raw = c.encode_conformance(receipt).encode()
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


def worker_pre_uc():
    import unicorn as uc

    codes, points = native_inputs()
    real_uc = uc.Uc
    real_model = c.model.apply

    def forbidden(*args, **kwargs):
        raise AssertionError("forged model reached Uc")

    uc.Uc = forbidden
    try:
        for kind in (
            "missing",
            "extra",
            "df",
            "gpr",
            "xmm",
            "snapshot",
            "path",
            "events",
            "trace",
            "boundary",
        ):
            vector = dict(alignment=0, profile=0)
            fixture = finite_fixture(vector)
            bad = pure.independent(fixture)
            if kind == "missing":
                bad.pop("pages")
            elif kind == "extra":
                bad["extra"] = 0
            elif kind == "df":
                bad["df"] = False
            elif kind == "gpr":
                bad["registers"]["edx"] ^= 1
            elif kind == "xmm":
                bad["xmm"]["xmm7"] ^= 1
            elif kind == "snapshot":
                bad["source_snapshot"] = bytes(308)
            elif kind == "path":
                bad["path_packet"]["source_snapshot"] = bytes(16)
            elif kind == "events":
                bad["events"].pop(0)
            elif kind == "trace":
                bad["trace_rvas"][-1] = "0x0015b9b0"
            else:
                bad["boundaries"][-1]["registers"]["edx"] ^= 1
            c.model.apply = lambda **kwargs: copy.deepcopy(bad)
            with pytest.raises(c.ConformanceError):
                c._run_case(codes, points, vector)
    finally:
        c.model.apply = real_model
        uc.Uc = real_uc


def test_model_forgeries_fail_before_uc():
    isolated("pre_uc")


if __name__ == "__main__":
    action = sys.argv[1]
    index = int(sys.argv[2])
    {
        "packet": lambda: worker_packet(index),
        "corpus": worker_corpus,
        "controls": worker_controls,
        "direct": worker_direct_codes,
        "pre_uc": worker_pre_uc,
        "rebuild": worker_rebuild,
        "cli": worker_cli,
    }[action]()
