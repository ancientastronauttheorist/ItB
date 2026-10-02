"""Independent normal AddMove machine observers and finite handwritten witnesses.

Reviewed handwritten child test laws supply expected data; production outputs
are actual values under test. One machine crosses six external responses.
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
from src.observatory import native_movement_addmove_normal_conformance as c
from tests import test_itb_native_movement_addmove_normal_semantics as pure

equal, store, read_bytes = pure.equal, pure.store, pure.read_bytes
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_movement_addmove_normal_conformance.json")
CLI = ROOT / "scripts/itb_native_movement_addmove_normal_conformance.py"
SEAL = "1f7f77d9ef362f2b9157cc444b43b1981fd5a1173c35e3788f275c2f73d89f88"
POINTS_SHA = "1a4b2521a802a2dd8c42414f5481c92c820d42708b40f217dd3bbb3a124f54b6"
COMMON = {"registers", "xmm", "pages", "events", "flags", "flag_mask", "df", "endpoint"}
BOUNDARY_KEYS = COMMON | {"name", "phase"}
IMPORT_KEYS = COMMON | {"name", "entry_esp", "words"}
OBS_KEYS = {
    "vector",
    "instructions",
    "memory_events",
    "boundary_states",
    "api_calls",
    "trace_sha256",
    "events_sha256",
    "states_sha256",
    "final_registers",
    "final_xmm",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "pages_sha256",
    "loaded_sites",
    "executed_sites",
}
NAMES = (
    "default",
    "assignment",
    "record_copy",
    "append",
    "destroy_temp",
    "destroy_original",
    "free_caller",
    "cookie",
)
ROLES = (
    ("outer_entry",)
    + tuple("boundary_" + f"{i:02}" for i in range(16))
    + tuple("import_" + f"{i:02}" for i in range(6))
    + ("outer_return",)
)
CONTROL_REASONS = {
    role
    + "_"
    + kind: dict(
        role=role, kind=kind, reason=f"native state differs at {role} in {kind}"
    )
    for role in ROLES
    for kind in ("gpr", "xmm", "pages", "flags", "df")
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
    "free_conformance": (
        "pe_native_vector_deallocation_conformance_joined",
        "8aba04f2be47f06284fbb3d00ebb7faa643613f99db3475fca54bd7f4cbc401a",
    ),
    "addmove_early": (
        "pe_native_movement_addmove_early_return_conformance",
        "c2448f75dc5c50f3e4de7f6bc0f412016cdb07bbe7becc491d5bd1b31f840079",
    ),
}
BODY_PINS = {
    30720: (91, "2d09033991193eea352dab418355232650d3aeb45906f909b384e0b662cd1ef6"),
    32720: (245, "c49f0e24bd27ed5495ceddc13536ca6fbe85d8c97f207db817ce0642b8b01906"),
    32976: (288, "062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333"),
    567584: (91, "e13e3be9b5e53d78d61aaaacc91b9c7c3183b77ef1f005bd2010bc1aa9b9830e"),
    568224: (43, "92494ea2dfd86d06ce373c9837f55d42e6c62746bd9c2c3c26d2a8af6abe938b"),
    633056: (79, "4359ecaf051506bce97afe182b66c453ca8d13ac4091d72a810f9df43d14d2e0"),
    633920: (87, "29a0428ed018a85e4e0a76f283f10040cf9e084f49bee5706b58766b570cb9d1"),
    809904: (226, "62157759ee3564515e63f20e297c171de6444d84732bccf7414eb208d953eefe"),
    1106592: (497, "641631ac31c522163cb141e846f21fa5e163ed176f042c3123762564c6d7d8ee"),
    1423792: (772, "3846fdb1ca2ebc1b4b6e83a64994f82d4907938345ff0d856c9bbea690957fc6"),
    1677728: (669, "2f17cc9bd3616c14305fb7fc1871bf0e37d09262825a99213f5b0568d6c6045d"),
    2454336: (231, "910d5418dbd9db30c75adcd8b74077c5c4e99119b2298c6c252045f8c9803d67"),
    2465536: (183, "39a9908012609c47f77556aea5af0865f3eb36943b5a1860c4c338bb6ea6fbb7"),
    3503306: (17, "5eafe60e37cdb82b85f6df218e4b490940c6fb2545895c2cef644fb38ab97375"),
    3503323: (51, "452b4c981b0a2567c6f4fc35b20076deca45a6b3509707358212028d21db5bfa"),
    3504221: (5, "f45c1f23615da61aa6c903e18306f5628c975cfaf6027b37e45d2264c7ed477d"),
    3603223: (5, "fafd106d4b0ce80368b3e080fb3be3b06582d8145fce2063305541cab5f65ea3"),
    3645266: (11, "831e215b24984219b6d6d7ce812127a420a48782704f0fef1630b1b8050cabbd"),
    3707222: (58, "223079ea989dad987b5fdf47fc9c63d348f353dc2ab70257ae6dc53c62a9003c"),
    3707947: (78, "d97ee587f29bfdaf154ca653059e883b67b56713a5d96643356a4edf6e3edde8"),
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
        f"0x{at:08x}": hashlib.sha256(data).hexdigest()
        for at, data in sorted(pages.items())
    }


def recipes():
    return [dict(alignment=a, profile=p) for a in range(16) for p in range(3)]


def finite_fixture(vector):
    a, p = vector["alignment"], vector["profile"]
    g, h, d, o = 0x30001000 + a, 0x10000100 + a, 0x10002000 + a, 0x06002FF9 + a
    bases = (
        0,
        0x30000000,
        0x30001000,
        0x10000000,
        0x10002000,
        0x06000000,
        0x06001000,
        0x06002000,
        0x06003000,
        0x00893000,
        0x0080D000,
        0x008B7000,
        0x007D6000,
    )
    pages = {
        base: bytes((i * 31 + j * 23 + a * 67 + p * 97) & 255 for j in range(4096))
        for i, base in enumerate(bases)
    }
    for at, value in (
        (g, 0x04000000),
        (g + 4, o),
        (g + 8, o + 16),
        (g + 12, o + 16),
        (g + 16, (0xBF800000, 0x7FC01234, 0x80000000)[p]),
        (h, d),
        (h + 4, d),
        (h + 8, d + 616),
        (0, (0x1234ABCD, 0, 0xFFFFFFFF)[p]),
        (0x00893F28, (0x19A51C73, 0, 0xFFFFFFFF)[p]),
        (0x008B7634, 0x12345678),
        (0x007D6220, 0x05000000),
        (0x007D621C, 0x05000000),
    ):
        store(pages, at, value)
    store(pages, 0x0080DFDC, 0, 1)
    regs = {
        name: (0x12345678 + i * 0x11111111 + p * 0x31415927) & 0xFFFFFFFF
        for i, name in enumerate(GPR)
    }
    regs.update(ecx=h, esp=g)
    xmm = {
        name: int.from_bytes(
            bytes((i * 19 + j * 41 + p * 71) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMM)
    }
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        return_address=0x04000000,
        entry_flags=(0x246, 0x287, 0x202)[p],
        allocation_results=[0x06001103 + a, 0x06002003 + a, 0x06003033 + a],
    )


def all_states(fixture, wanted):
    first = dict(
        registers=fixture["registers"],
        xmm=fixture["xmm"],
        pages=fixture["pages"],
        events=[],
        flags=fixture["entry_flags"] & 0x8D5,
        flag_mask=0x8D5,
        df=0,
        endpoint=0x00657340,
    )
    rows = [dict(role="outer_entry", state=first)]
    rows += [
        dict(role=f"boundary_{i:02}", state={k: v[k] for k in COMMON})
        for i, v in enumerate(wanted["boundaries"])
    ]
    rows += [
        dict(role=f"import_{i:02}", state={k: v[k] for k in COMMON})
        for i, v in enumerate(wanted["imports"])
    ]
    rows.append(dict(role="outer_return", state={k: wanted[k] for k in COMMON}))
    return sorted(rows, key=lambda row: len(row["state"]["events"]))


def metadata(role, state):
    return dict(
        role=role,
        event_prefix=len(state["events"]),
        registers=state["registers"],
        xmm={key: f"0x{value:032x}" for key, value in state["xmm"].items()},
        flags=state["flags"],
        flag_mask=state["flag_mask"],
        endpoint=f"0x{state['endpoint']:08x}",
        pages_sha256=page_hashes(state["pages"]),
    )


def expected_observation(vector, fixture, wanted):
    api = []
    for i, state in enumerate(wanted["imports"]):
        api.append(
            dict(
                kind="allocate" if i < 3 else "free",
                entry_esp=state["entry_esp"],
                words=state["words"],
                result=fixture["allocation_results"][i] if i < 3 else 1,
                event_prefix=len(state["events"]),
            )
        )
    return dict(
        vector=vector,
        instructions=2089,
        memory_events=1293,
        boundary_states=24,
        api_calls=api,
        trace_sha256=canonical(wanted["trace_rvas"]),
        events_sha256=canonical(wanted["events"]),
        states_sha256=canonical(
            [metadata(row["role"], row["state"]) for row in all_states(fixture, wanted)]
        ),
        final_registers=wanted["registers"],
        final_xmm={k: f"0x{v:032x}" for k, v in wanted["xmm"].items()},
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint="0x04000000",
        pages_sha256=page_hashes(wanted["pages"]),
        loaded_sites=1206,
        executed_sites=sorted(set(wanted["trace_rvas"])),
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
    assert digest == "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
    codes, points = c._load_code(data, image, sources())
    assert (
        len(points) == 1206
        and sum(map(len, codes.values())) == 3727
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
    machines = []
    trace = []
    events = []
    states = []
    imports = []
    starts = []
    captured = {}
    cursor = 0
    outer = False
    real = uc.Uc

    def state(machine, mask):
        raw = machine.reg_read(x.UC_X86_REG_EFLAGS)
        return dict(
            registers={
                n: machine.reg_read(getattr(x, "UC_X86_REG_" + n.upper())) for n in GPR
            },
            xmm={
                n: machine.reg_read(getattr(x, "UC_X86_REG_" + n.upper())) for n in XMM
            },
            pages={
                base: bytes(machine.mem_read(base, 4096)) for base in fixture["pages"]
            },
            events=copy.deepcopy(events),
            eflags=raw,
            flags=raw & mask,
            flag_mask=mask,
            df=(raw >> 10) & 1,
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    def take(machine, role, expected):
        row = state(machine, expected["flag_mask"])
        raw = row.pop("eflags")
        assert raw & ~0xAD7 == 0 and raw & 2 and raw & 0x400 == 0
        equal(row, {key: expected[key] for key in COMMON})
        states.append(dict(role=role, state=row))
        return raw

    def own_code(machine, address, size, user):
        nonlocal cursor, outer
        if not outer:
            assert address == 0x00657340
            raw = take(machine, "outer_entry", all_states(fixture, wanted)[0]["state"])
            assert raw == fixture["entry_flags"]
            outer = True
        if address == 0x04000000:
            assert take(machine, "outer_return", wanted) == 0x246
            return
        if address == 0x05000000:
            i = len(imports)
            expected = wanted["imports"][i]
            raw = take(machine, f"import_{i:02}", expected)
            row = copy.deepcopy(states[-1]["state"])
            sp = row["registers"]["esp"]
            row.update(
                name=expected["name"],
                entry_esp=sp,
                words=[
                    int.from_bytes(machine.mem_read(sp + 4 * j, 4), "little")
                    for j in range(4)
                ],
            )
            equal(row, expected)
            imports.append(row)
            return
        assert f"0x{address-0x400000:08x}" in set(wanted["trace_rvas"])
        if cursor < 16 and address == wanted["boundaries"][cursor]["endpoint"]:
            take(machine, f"boundary_{cursor:02}", wanted["boundaries"][cursor])
            cursor += 1
        trace.append(f"0x{address-0x400000:08x}")

    def own_memory(machine, access, address, width, value, user):
        assert width in (1, 2, 4)
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
            if len(starts) <= 6:
                i = len(starts) - 1
                expected = imports[i]
                row = state(machine, 0xFFFFFFFF)
                raw = row.pop("eflags")
                assert raw == 0x246
                equal(
                    row,
                    dict(
                        registers=dict(
                            expected["registers"],
                            eax=fixture["allocation_results"][i] if i < 3 else 1,
                            ecx=0xA0000001,
                            edx=0xB0000001,
                            esp=expected["entry_esp"] + 16,
                        ),
                        xmm=expected["xmm"],
                        pages=expected["pages"],
                        events=expected["events"],
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
        equal(expected, wanted)
        equal(installed, fixture)
        captured.update(state(machine, 0x8D5))
        ids.clear()
        expected["pages"].clear()
        expected["registers"].clear()
        installed["pages"].clear()

    uc.Uc = observed
    try:
        observation = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = real
    assert len(machines) == 1 and machines[0].ctl_get_cpu_model() == 19 and cursor == 16
    equal(
        starts,
        [
            ((at, 0), dict(count=20000))
            for at in (
                0x00657340,
                0x00789463,
                0x00789463,
                0x00789463,
                0x00789172,
                0x00789172,
                0x00789172,
            )
        ],
    )
    equal(trace, wanted["trace_rvas"])
    equal(events, wanted["events"])
    assert (
        len(trace) == 2089
        and len(events) == 1293
        and len(states) == 24
        and len(imports) == 6
    )
    equal(states, all_states(fixture, wanted))
    equal(imports, wanted["imports"])
    assert captured.pop("eflags") == 0x246
    equal(captured, {k: wanted[k] for k in COMMON})
    assert set(observation) == OBS_KEYS
    equal(observation, expected_observation(vector, fixture, wanted))
    return observation


def worker_corpus():
    actual = [worker_packet(i) for i in range(48)]
    equal(actual, json.loads(EVIDENCE.read_text(encoding="utf-8"))["cases"])


def worker_controls():
    codes, points = native_inputs()
    equal(c.CONTROLS, CONTROL_REASONS)
    assert len(CONTROL_REASONS) == 120
    for name, control in CONTROL_REASONS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, dict(alignment=15, profile=2), name)
        assert str(caught.value) == control["reason"], name


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
    equal(
        c.build_conformance(os.environ["ITB_EXACT_EXE"], sources()),
        json.loads(EVIDENCE.read_text(encoding="utf-8")),
    )


def worker_cli():
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    for command in ("build", "verify", "verify-structure"):
        result = subprocess.run(
            cli_arguments(command), cwd=ROOT, capture_output=True, timeout=3600
        )
        assert result.returncode == 0, (result.stdout + result.stderr).decode(
            "utf-8", errors="replace"
        )[-5000:]
        value = json.loads(result.stdout)
        assert (
            result.stdout == c.encode_conformance(value).encode("utf-8")
            and b"\r" not in result.stdout
        )
        equal(value, evidence)


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
        timeout=3600,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        "utf-8", errors="replace"
    )[-5000:]


@pytest.mark.parametrize("index", (0, 1, 2, 21, 22, 23, 45, 46, 47))
def test_actual_independent_complete_machine_states(index):
    isolated("packet", index)


def test_full48_independent_observer_corpus():
    isolated("corpus")


def test_all120_exact_reason_controls():
    isolated("controls")


def test_direct_code_forgeries_pre_uc():
    isolated("direct")


def test_exact_rebuild():
    isolated("rebuild")


def test_exact_three_cli_commands():
    isolated("cli")


@pytest.mark.parametrize("vector", recipes())
def test_full48_handwritten_fixture_and_normal_packet(vector):
    fixture = finite_fixture(vector)
    equal(c._fixture(vector), fixture)
    actual = c._expected(vector, fixture)
    assert type(actual) is dict and set(actual) == pure.KEYS
    assert len(actual["trace_rvas"]) == 2089 and len(actual["events"]) == 1293
    assert len(actual["boundaries"]) == 16 and len(actual["imports"]) == 6
    assert all(set(row) == BOUNDARY_KEYS for row in actual["boundaries"])
    assert all(set(row) == IMPORT_KEYS for row in actual["imports"])
    equal(actual, pure.independent(fixture))


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
        "flags",
        "gpr",
        "xmm",
        "return",
        "allocation",
        "allocationtuple",
        "source",
        "ancestor",
        "cookie",
        "heap",
        "iat",
        "literal",
        "padding",
        "mutable",
        "mapping",
        "pagealias",
    ),
)
def test_exact_fixture_recipe_types(kind):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    if kind == "extra":
        fixture["extra"] = 0
    elif kind == "missing":
        fixture.pop("xmm")
    elif kind == "flags":
        fixture["entry_flags"] ^= 1
    elif kind == "gpr":
        fixture["registers"]["eax"] ^= 1
    elif kind == "xmm":
        fixture["xmm"]["xmm7"] ^= 1
    elif kind == "return":
        fixture["return_address"] ^= 1
    elif kind == "allocation":
        fixture["allocation_results"][0] += 4
    elif kind == "allocationtuple":
        fixture["allocation_results"] = tuple(fixture["allocation_results"])
    elif kind == "mutable":
        fixture["pages"][0] = bytearray(fixture["pages"][0])
    elif kind == "mapping":
        fixture = UserDict(fixture)
    elif kind == "pagealias":
        fixture["pages"][0.0] = fixture["pages"].pop(0)
    else:
        at = {
            "source": 0x06002FF9,
            "ancestor": 0x30001014,
            "cookie": 0x893F28,
            "heap": 0x8B7634,
            "iat": 0x7D6220,
            "literal": 0x80DFDC,
            "padding": 0x10000800,
        }[kind]
        store(fixture["pages"], at, read_bytes(fixture["pages"], at, 1)[0] ^ 1, 1)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def forged_model(kind, fixture):
    packet = pure.independent(fixture)
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
    elif kind == "geometry":
        packet["geometry"]["new_record"] += 4
    elif kind == "path":
        packet["path"]["parameter_bits"] ^= 1
    elif kind == "count":
        packet["events"].pop()
    elif kind == "eventtuple":
        packet["events"] = tuple(packet["events"])
    elif kind == "eventwidth":
        packet["events"][0]["width"] = 4.0
    elif kind == "tracecount":
        packet["trace_rvas"].pop()
    elif kind == "pages":
        store(packet["pages"], 0x10000800, 0, 1)
    elif kind == "boundaryextra":
        packet["boundaries"][0]["extra"] = 0
    elif kind == "boundaryname":
        packet["boundaries"][0]["name"] = "cookie"
    elif kind == "boundaryphase":
        packet["boundaries"][0]["phase"] = "return"
    elif kind == "boundarytuple":
        packet["boundaries"] = tuple(packet["boundaries"])
    elif kind == "boundarypage":
        store(packet["boundaries"][0]["pages"], 0x893001, 0, 1)
    elif kind == "boundarygpr":
        packet["boundaries"][0]["registers"]["eax"] = False
    elif kind == "boundaryalias":

        class Text(str):
            pass

        regs = packet["boundaries"][0]["registers"]
        regs[Text("eax")] = regs.pop("eax")
    elif kind == "boundarynegative":
        packet["boundaries"][0]["endpoint"] = -1
    elif kind == "importextra":
        packet["imports"][0]["extra"] = 0
    elif kind == "importname":
        packet["imports"][0]["name"] = "append"
    elif kind == "importwordbool":
        packet["imports"][0]["words"][2] = False
    elif kind == "importwordtuple":
        packet["imports"][0]["words"] = tuple(packet["imports"][0]["words"])
    elif kind == "importesp":
        packet["imports"][0]["entry_esp"] = float(packet["imports"][0]["entry_esp"])
    elif kind == "importendpoint":
        packet["imports"][0]["endpoint"] = float(packet["imports"][0]["endpoint"])
    elif kind == "childnone":
        packet["child_packets"]["default"] = None
    elif kind == "childextra":
        packet["child_packets"]["assignment"]["extra"] = 0
    elif kind == "childdf":
        packet["child_packets"]["record_copy"]["df"] = False
    elif kind == "childendpoint":
        packet["child_packets"]["append"]["endpoint"] += 4
    elif kind == "freeprotocol":
        packet["child_packets"]["free_caller"]["protocol"]["result"] = True
    elif kind == "freestack":
        packet["child_packets"]["free_caller"]["stack"] = bytes(8192)
    elif kind == "freeerror":
        packet["child_packets"]["free_caller"]["error"] = bytes(4096)
    elif kind == "freeevents":
        packet["child_packets"]["free_caller"]["events"][0]["width"] = 4.0
    elif kind == "freegpr":
        packet["child_packets"]["free_caller"]["registers"]["edx"] ^= 1
    else:
        raise AssertionError(kind)
    return packet


MODEL_FORGERIES = (
    "extra",
    "missing",
    "df",
    "endpoint",
    "gpr",
    "xmm",
    "geometry",
    "path",
    "count",
    "eventtuple",
    "eventwidth",
    "tracecount",
    "pages",
    "boundaryextra",
    "boundaryname",
    "boundaryphase",
    "boundarytuple",
    "boundarypage",
    "boundarygpr",
    "boundaryalias",
    "boundarynegative",
    "importextra",
    "importname",
    "importwordbool",
    "importwordtuple",
    "importesp",
    "importendpoint",
    "childnone",
    "childextra",
    "childdf",
    "childendpoint",
    "freeprotocol",
    "freestack",
    "freeerror",
    "freeevents",
    "freegpr",
)


@pytest.mark.parametrize("kind", MODEL_FORGERIES)
def test_complete_model_state_envelopes_and_free_join(kind, monkeypatch):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    bad = forged_model(kind, fixture)
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(bad))
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


def test_valid_nested_extra_semantics_remain_trusted(monkeypatch):
    vector = dict(alignment=0, profile=0)
    fixture = finite_fixture(vector)
    bad = pure.independent(fixture)
    # Closed envelope is valid; deeper snapshot semantics are the trusted child.
    bad["child_packets"]["assignment"]["source_snapshot"] = bytes(16)
    monkeypatch.setattr(c.model, "apply", lambda **kwargs: copy.deepcopy(bad))
    equal(c._expected(vector, fixture), bad)


def test_packet_and_fixture_detachment():
    vector = dict(alignment=7, profile=2)
    fixture = finite_fixture(vector)
    before = copy.deepcopy(fixture)
    actual = c._expected(vector, fixture)
    equal(actual, pure.independent(fixture))
    actual["pages"].clear()
    actual["boundaries"][0]["pages"].clear()
    actual["child_packets"]["default"]["events"].clear()
    equal(fixture, before)
    equal(c._expected(vector, fixture), pure.independent(fixture))


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
            "df",
            "gpr",
            "geometry",
            "eventwidth",
            "boundaryextra",
            "boundaryalias",
            "importwordbool",
            "childnone",
            "freeprotocol",
        ):
            fixture = finite_fixture(dict(alignment=0, profile=0))
            bad = forged_model(kind, fixture)
            c.model.apply = lambda **kwargs: copy.deepcopy(bad)
            with pytest.raises(c.ConformanceError):
                c._run_case(codes, points, dict(alignment=0, profile=0))
    finally:
        c.model.apply = real_model
        uc.Uc = real_uc


def test_model_forgeries_fail_pre_uc():
    isolated("pre_uc")


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("root must publish sealed receipt")
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_receipt_complete_source_points_independent_cases_and_scope(receipt):
    assert (
        c.SEALED_SHA256 != "PENDING" and canonical(receipt) == SEAL == c.SEALED_SHA256
    )
    raw = EVIDENCE.read_bytes()
    assert (
        len(raw) == 1235636
        and hashlib.sha256(raw).hexdigest()
        == "afaf03d30cd132040f9afedb92338002fc45d16e508e3a42de8432b50faa4c0f"
    )
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert receipt["analysis_kind"] == "pe_native_movement_addmove_normal_conformance"
    equal(c.SOURCE_PINS, SOURCE_PINS)
    equal(c.BODY_PINS, BODY_PINS)
    equal(c.vectors(), recipes())
    supplied = sources()
    equal(receipt["build_identity"], supplied["program_facts"]["identity"])
    assert set(receipt["sources"]) == set(SOURCE_PINS)
    for key, (kind, digest) in SOURCE_PINS.items():
        assert canonical(supplied[key]) == digest
        equal(
            receipt["sources"][key], dict(analysis_kind=kind, canonical_sha256=digest)
        )
    equal(
        receipt["bodies"],
        [
            dict(entry_rva=f"0x{start:08x}", size=size, sha256=digest)
            for start, (size, digest) in sorted(BODY_PINS.items())
        ],
    )
    points = receipt["instruction_points"]
    assert (
        len(points) == 1206
        and len({p["rva"] for p in points}) == 1206
        and sum(p["size"] for p in points) == 3727
    )
    assert canonical(points) == POINTS_SHA and points == sorted(
        points, key=lambda p: int(p["rva"], 16)
    )
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
    observations = [
        expected_observation(v, finite_fixture(v), pure.independent(finite_fixture(v)))
        for v in recipes()
    ]
    equal(receipt["cases"], observations)
    executed = {pc for row in observations for pc in row["executed_sites"]}
    assert executed <= set(row["rva"] for row in points)
    equal(
        receipt["summary"],
        dict(
            cases=48,
            negative_controls=120,
            loaded_bodies=20,
            loaded_bytes=3727,
            loaded_instruction_sites=1206,
            executed_instruction_sites=len(executed),
            executed_instructions=100272,
            memory_events=62064,
            boundary_states=1152,
            allocation_requests=144,
            allocation_requested_bytes=2304,
            allocation_responses=144,
            free_requests=144,
            free_responses=144,
            path_copied_bytes=2304,
            appended_records=48,
            receiver_advanced_bytes=14784,
            cookie_checks=48,
            opaque_callees=0,
            wide_copies=0,
            accounting_delta=0,
        ),
    )
    equal(
        receipt["negative_controls"],
        [
            dict(name=name, reason=value["reason"], rejected=True)
            for name, value in CONTROL_REASONS.items()
        ],
    )
    assert len(CONTROL_REASONS) == 120
    equal(
        receipt["method"],
        dict(
            machine="x86-32",
            cpu_model=19,
            continuous=True,
            machines_per_case=1,
            starts_per_case=7,
            external_responses_per_case=6,
            expected_model="reviewed selected count-two AddMove",
            typed_replay=True,
            universal_coordinated_forgery_rejection=False,
        ),
    )
    for unresolved in (
        "ownership",
        "receiver growth",
        "exception unwinding",
        "whole game",
        "Lua execution",
        "pawn movement",
    ):
        assert unresolved in receipt["scope"]["unresolved"]


@pytest.mark.parametrize(
    "kind",
    ("summary", "boolsummary", "case", "api", "point", "body", "pin", "scope", "extra"),
)
def test_receipt_forgeries(kind, receipt):
    bad = copy.deepcopy(receipt)
    if kind == "summary":
        bad["summary"]["allocation_requests"] += 1
    elif kind == "boolsummary":
        bad["summary"]["opaque_callees"] = False
    elif kind == "case":
        bad["cases"][0]["vector"]["alignment"] = False
    elif kind == "api":
        bad["cases"][0]["api_calls"][0]["words"][2] = False
    elif kind == "point":
        bad["instruction_points"][0]["size"] += 1
    elif kind == "body":
        bad["bodies"][0]["size"] += 1
    elif kind == "pin":
        bad["sources"]["movement_binding"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        bad["scope"]["unresolved"] = []
    else:
        bad["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "mapping",
        "kind",
        "body",
        "nonfinite",
        "build",
        "atlas",
        "duplicate",
        "boolsize",
    ),
)
def test_preflight_sources_and_refreshed_joins(kind, monkeypatch):
    supplied = sources()
    if kind == "missing":
        supplied.pop("movement_binding")
    elif kind == "extra":
        supplied["extra"] = {}
    elif kind == "mapping":
        supplied = UserDict(supplied)
    elif kind == "kind":
        supplied["movement_binding"]["analysis_kind"] = "forged"
    elif kind == "body":
        supplied["movement_binding"]["bodies"]["move_parent"]["size"] += 1
    elif kind == "nonfinite":
        supplied["movement_binding"]["bad"] = float("nan")
    else:
        key = "movement_binding" if kind == "build" else "program_facts"
        if kind == "build":
            supplied[key]["build_identity"]["executable_sha256"] = "0" * 64
        elif kind == "duplicate":
            supplied[key]["functions"].append(
                copy.deepcopy(supplied[key]["functions"][0])
            )
        else:
            row = next(
                r for r in supplied[key]["functions"] if r["entry_rva"] == "0x00257340"
            )
            row["body_size"] = True if kind == "boolsize" else row["body_size"] + 1
        changed = dict(c.SOURCE_PINS)
        changed[key] = (changed[key][0], canonical(supplied[key]))
        monkeypatch.setattr(c, "SOURCE_PINS", changed)
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("key", tuple(SOURCE_PINS))
def test_every_source_pin_closed(key):
    supplied = sources()
    supplied[key]["extra"] = 0
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_structure_result_detached(receipt):
    result = c.validate_structure(receipt, sources())
    result["cases"][0]["final_registers"].clear()
    result["summary"]["cases"] = 0
    assert (
        receipt["summary"]["cases"] == 48
        and len(receipt["cases"][0]["final_registers"]) == 8
    )


def test_encoder_utf8_and_json_types(receipt):
    assert (
        c.encode_conformance({"text": "caf\u00e9"}) == '{\n  "text": "caf\u00e9"\n}\n'
    )
    for value in (float("nan"), float("inf"), float("-inf"), 0.0):
        with pytest.raises(Exception):
            c.encode_conformance({"bad": value})
    bad = copy.deepcopy(receipt)
    bad["summary"]["cases"] = float("nan")
    with pytest.raises(c.ConformanceError):
        c.validate_structure(bad, sources())


@pytest.mark.parametrize(
    "kind", ("noncanonical", "duplicate", "nonfinite", "invalid_utf8")
)
def test_cli_malformed_evidence_rejects(tmp_path, receipt, kind):
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
        "corpus": worker_corpus,
        "controls": worker_controls,
        "direct": worker_direct_codes,
        "pre_uc": worker_pre_uc,
        "rebuild": worker_rebuild,
        "cli": worker_cli,
    }[action]()
