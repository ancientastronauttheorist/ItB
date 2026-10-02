"""Independent class append law; sealed tree prefix is a checked lower witness."""

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
from src.observatory import native_lua_class_simd_vector6_to7_return_conformance as c
from tests import test_itb_native_simd_vector_growth6_to9_semantics as handwritten

blob, install = handwritten.blob, handwritten.install
canonical_hash, page_hashes = handwritten.canonical_hash, handwritten.page_hashes
GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
U, COOKIE = 0x0FFFFFCC, 0x00893F28
TAIL_BEFORE = (
    0x2EB1BB,
    0x2EB1BE,
    0x2EB1C1,
    0x2EB1C3,
    0x2EB1F7,
    0x2EB1FA,
    0x2EB1FC,
    0x2EB1FD,
    0x2EB200,
)
TAIL_AFTER = (
    0x2EB205,
    0x2EB208,
    0x2EB20A,
    0x2EB20C,
    0x2EB20E,
    0x2EB210,
    0x2EB213,
    0x2EB216,
    0x2EB21A,
    0x2EB21D,
    0x2EB21E,
    0x2EB21F,
    0x2EB221,
    0x2EB222,
    0x3574CA,
    0x3574D0,
    0x3574D3,
    0x2EB227,
    0x2EB229,
    0x2EB22A,
)
TAIL = TAIL_BEFORE + handwritten.TRACE + TAIL_AFTER
EXPECTED_KEYS = {
    "registers",
    "pages",
    "events",
    "flags",
    "endpoint",
    "insertions",
    "heap_nodes",
    "destination_addresses",
    "destination_key_pointers",
    "tree_heap_count",
    "xmm",
    "df",
    "growth_entry",
    "growth_return",
    "growth_packet",
    "prefix_packet",
}


def read(pages, address, width=4):
    return int.from_bytes(blob(pages, address, width), "little")


def strict_equal(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual) == set(expected)
        for key in expected:
            strict_equal(actual[key], expected[key])
    elif type(expected) in (list, tuple):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            strict_equal(a, b)
    else:
        assert actual == expected


def checked_prefix(vector, fixture):
    """Reuse the unchanged sealed insertion/successor trace, check its physical law."""
    lower = c.prefix._expected(vector, fixture)
    assert set(lower) == EXPECTED_KEYS - {
        "tree_heap_count",
        "xmm",
        "df",
        "growth_entry",
        "growth_return",
        "growth_packet",
        "prefix_packet",
    }
    f = fixture["stack"] - 4
    source = {
        n["key"]: (i, fixture["source_state"]["payloads"][i])
        for i, n in enumerate(fixture["source_state"]["tree"]["nodes"])
    }
    destinations = {
        n["key"]: a
        for n, a in zip(
            fixture["destination_state"]["tree"]["nodes"],
            fixture["destination_addresses"],
        )
    }
    assert set(source) == set(destinations) == set(vector["source_keys"])
    rows = [
        dict(
            source=source[key][0],
            key=key,
            destination_address=destinations[key],
            inserted=False,
            mode="existing",
            payload=source[key][1],
            heap_node=None,
        )
        for key in sorted(source)
    ]
    strict_equal(lower["insertions"], rows)
    assert lower["heap_nodes"] == []
    assert lower["destination_addresses"] == fixture["destination_addresses"]
    assert lower["destination_key_pointers"] == [
        read(fixture["pages"], a + 16) for a in fixture["destination_addresses"]
    ]
    # Full nonstack pages have only destination payload updates. All topology,
    # nil/color/padding/key bytes, source storage, sentinel, and globals survive.
    memory = copy.deepcopy(fixture["pages"])
    for key, a in destinations.items():
        install(memory, a + 20, source[key][1].to_bytes(4, "little"))
    for page in memory:
        if page not in (0x30000000, 0x30001000):
            assert lower["pages"][page] == memory[page]
    # Replay sealed lower events, independently checking each recorded read.
    replay = copy.deepcopy(fixture["pages"])
    for row in lower["events"]:
        assert set(row) == {"access", "address", "width", "value"}
        assert type(row["value"]) is int and row["width"] in (1, 2, 4)
        if row["access"] == "write":
            install(
                replay, row["address"], row["value"].to_bytes(row["width"], "little")
            )
        else:
            assert row["access"] == "read"
            assert read(replay, row["address"], row["width"]) == row["value"]
    assert lower["pages"] == replay
    argument = read(fixture["pages"], fixture["stack"] + 4)
    root = fixture["source_state"]["tree"]["root"]
    root_right = (
        None
        if root is None
        else fixture["source_state"]["tree"]["nodes"][root]["right"]
    )
    last_successor_ecx = (
        c.prefix.SOURCE_HEAD
        if root_right is None
        else fixture["source_addresses"][root_right]
    )
    regs = dict(
        fixture["registers"],
        eax=(f - 8 if rows else c.prefix.SOURCE_HEAD),
        ebx=c.prefix.SOURCE_OBJECT,
        ecx=(last_successor_ecx if rows else U),
        esi=c.prefix.SOURCE_HEAD,
        edi=argument,
        ebp=f,
        esp=f - 32,
    )
    if rows:
        regs["edx"] = f - 8
    strict_equal(lower["registers"], regs)
    assert lower["flags"] == 0x44 and lower["endpoint"] == 0x006EB1BB
    assert read(replay, f) == fixture["registers"]["ebp"]
    assert read(replay, f - 4) == vector["cookie"] ^ f
    for offset, register in ((-24, "ebx"), (-28, "esi"), (-32, "edi")):
        assert read(replay, f + offset) == fixture["registers"][register]
    assert read(replay, f - 12) == U
    assert read(replay, f - 8) == c.prefix.SOURCE_HEAD
    if rows:
        assert read(replay, f - 20) == rows[-1]["destination_address"]
        assert read(replay, f - 16, 1) == 0
    assert blob(replay, fixture["stack"], 0x30002000 - fixture["stack"]) == blob(
        fixture["pages"], fixture["stack"], 0x30002000 - fixture["stack"]
    )
    return copy.deepcopy(lower)


def independent(vector, fixture):
    lower = checked_prefix(vector, fixture)
    pages, events = copy.deepcopy(lower["pages"]), copy.deepcopy(lower["events"])
    registers = copy.deepcopy(lower["registers"])
    f, o, d = fixture["stack"] - 4, fixture["old_begin"], fixture["vector_begin"]
    argument = read(fixture["pages"], fixture["stack"] + 4)

    def event(access, address, value):
        if access == "write":
            install(pages, address, value.to_bytes(4, "little"))
        else:
            assert read(pages, address) == value
        events.append(dict(access=access, address=address, width=4, value=value))

    def boundary(registers, xmm, endpoint, flags, mask):
        return dict(
            registers=copy.deepcopy(registers),
            xmm=copy.deepcopy(xmm),
            pages=copy.deepcopy(pages),
            events=copy.deepcopy(events),
            endpoint=endpoint,
            flags=flags,
            flag_mask=mask,
            df=0,
        )

    boundaries = {
        "class_prefix": boundary(registers, fixture["xmm"], 0x006EB1BB, 0x44, 0xCC5)
    }
    assert argument > o + 48
    for access, address, value in (
        ("read", f - 12, U),
        ("read", U + 8, o + 48),
        ("read", U + 12, o + 48),
        ("write", f - 36, registers["ecx"]),
        ("write", f - 40, 0x006EB205),
    ):
        event(access, address, value)
    registers.update(eax=o + 48, esi=U, ecx=U + 4, esp=f - 40)
    inputs = dict(
        pages=copy.deepcopy(pages),
        registers=copy.deepcopy(registers),
        xmm=copy.deepcopy(fixture["xmm"]),
        source=o,
        destination=d,
        object_address=U + 4,
        return_address=0x006EB205,
        entry_flags=0x246,
    )
    boundaries["growth_entry"] = boundary(
        registers, fixture["xmm"], 0x006EB620, 0x246, 0xFFFFFFFF
    )
    prefix = copy.deepcopy(events)
    growth = handwritten.independent(**inputs)
    for name, child_boundary in growth["boundaries"].items():
        boundaries[name] = copy.deepcopy(child_boundary)
        boundaries[name]["events"] = prefix + boundaries[name]["events"]
    imported = copy.deepcopy(growth["imported"])
    # Imported packets expose hash-only events; rebuild each exact combined prefix.
    for row, count in zip(imported, (36, 99)):
        row["events_sha256"] = canonical_hash(prefix + growth["events"][:count])
    events.extend(copy.deepcopy(growth["events"]))
    pages, registers = copy.deepcopy(growth["pages"]), copy.deepcopy(
        growth["registers"]
    )
    boundaries["growth_return"] = boundary(
        registers, growth["xmm"], 0x006EB205, growth["flags"], 0x8D5
    )
    assert registers["esp"] == f - 32 and registers["edi"] == argument
    for access, address, value in (
        ("read", U + 8, d + 48),
        ("read", argument, read(fixture["pages"], argument)),
        ("write", d + 48, read(fixture["pages"], argument)),
        ("read", argument + 4, read(fixture["pages"], argument + 4)),
        ("write", d + 52, read(fixture["pages"], argument + 4)),
        ("read", U + 8, d + 48),
        ("write", U + 8, d + 56),
    ):
        event(access, address, value)
    # Handwritten cookie epilogue, including the checker's exact CALL/RET words.
    for access, address, value in (
        ("read", f - 4, vector["cookie"] ^ f),
        ("read", f - 32, fixture["registers"]["edi"]),
        ("read", f - 28, fixture["registers"]["esi"]),
        ("read", f - 24, fixture["registers"]["ebx"]),
        ("write", f - 24, 0x006EB227),
        ("read", COOKIE, vector["cookie"]),
        ("read", f - 24, 0x006EB227),
        ("read", f, fixture["registers"]["ebp"]),
        ("read", f + 4, fixture["return_address"]),
    ):
        event(access, address, value)
    result = dict(
        lower,
        pages=pages,
        events=events,
        registers=dict(
            fixture["registers"],
            eax=read(fixture["pages"], argument + 4),
            ecx=vector["cookie"],
            edx=0xB0000001,
            esp=fixture["stack"] + 8,
        ),
        flags=0x44,
        endpoint=fixture["return_address"],
        heap_nodes=[d],
        tree_heap_count=0,
        xmm=copy.deepcopy(growth["xmm"]),
        df=0,
        growth_entry=boundaries["growth_entry"],
        growth_return=boundaries["growth_return"],
        prefix_packet=lower,
    )
    return dict(
        packet=result,
        growth=growth,
        inputs=inputs,
        boundaries=boundaries,
        imported=imported,
        argument=argument,
        prefix_count=len(lower["events"]),
    )


def check_result(vector, fixture, result, wanted):
    assert set(result) == EXPECTED_KEYS
    for key, value in wanted["packet"].items():
        strict_equal(result[key], value)
    handwritten.check_result(
        wanted["inputs"], result["growth_packet"], wanted["growth"]
    )
    o, d, L = fixture["old_begin"], fixture["vector_begin"], fixture["stack"]
    assert len(result["events"]) == wanted["prefix_count"] + 137
    assert blob(result["pages"], d, 56) == blob(fixture["pages"], o, 48) + blob(
        fixture["pages"], wanted["argument"], 8
    )
    assert blob(result["pages"], o, 48) == blob(fixture["pages"], o, 48)
    assert blob(result["pages"], d + 56, 16) == blob(fixture["pages"], d + 56, 16)
    assert blob(result["pages"], L, 0x30002000 - L) == blob(
        fixture["pages"], L, 0x30002000 - L
    )
    assert [
        (r["address"] - U, r["value"])
        for r in result["events"]
        if r["access"] == "write" and r["address"] in (U + 4, U + 8, U + 12)
    ] == [(12, d + 72), (8, d + 48), (4, d), (8, d + 56)]
    wide = [row for row in result["events"] if row["width"] == 8]
    assert wide == [
        dict(
            access=access,
            address=base + off,
            width=8,
            value=read(fixture["pages"], o + off, 8),
        )
        for access, base in (("read", o), ("write", d))
        for off in (0, 8, 16, 24)
    ]
    copied = result["growth_packet"]["copy_packet"]
    assert copied["registers"]["edx"] == read(fixture["pages"], o + 44)
    assert copied["registers"]["edx"] not in (0, read(fixture["pages"], o + 32))


@pytest.fixture(scope="module")
def cases():
    return [(v, f, independent(v, f)) for v in c.vectors() for f in [c._fixture(v)]]


def test_exact_matrix_and_recipe_extent(cases):
    vectors = [
        dict(v, vector_alignment=a, old_size=6, old_alignment=a, xmm_profile=x)
        for v in c.prefix.vectors()
        if v["profile"] == "all_existing"
        for a in (0, 7, 31)
        for x in (0, 1)
    ]
    assert c.vectors() == vectors and len(vectors) == 288
    assert {len(v["source_keys"]) for v in vectors} == set(range(8))
    assert {v["frame_alignment"] for v in vectors} == {0, 15}
    assert {v["node_alignment"] for v in vectors} == {0, 7, 31}
    assert len(TAIL) == 264
    for v, f, wanted in cases:
        assert set(f) == c.legacy.FIXTURE_KEYS and len(f) == 29
        assert f["old_begin"] == 0x06002800 + v["vector_alignment"]
        assert f["vector_begin"] == 0x06004800 + v["vector_alignment"]
        assert f["pages"][0x06004000] == bytes([0xA5]) * 4096
        assert [read(f["pages"], f["old_begin"] + 4 * i) for i in range(12)] == [
            (0x91827364 ^ i * 0x1234567 ^ v["xmm_profile"] * 0x7654321) & 0xFFFFFFFF
            for i in range(12)
        ]
        assert wanted["inputs"]["registers"]["esp"] == f["stack"] - 44
        assert wanted["inputs"]["object_address"] == 0x0FFFFFD0


def test_full_independent_class_child_pages_events_abi_and_cookie(cases):
    for vector, fixture, wanted in cases:
        before = copy.deepcopy((vector, fixture))
        check_result(vector, fixture, c._expected(vector, fixture), wanted)
        assert (vector, fixture) == before


def test_outputs_detached_from_input_and_nested_snapshots(cases):
    v, f, wanted = cases[-1]
    before = copy.deepcopy((v, f))
    result = c._expected(v, f)
    result["growth_entry"]["registers"]["eax"] ^= 1
    result["growth_packet"]["resize_packet"]["copy_packet"]["registers"]["edx"] ^= 1
    result["prefix_packet"]["destination_addresses"].clear()
    assert (v, f) == before
    check_result(v, f, c._expected(v, f), wanted)


@pytest.mark.parametrize(
    "kind",
    (
        "old_size_bool",
        "profile_bool",
        "extra",
        "missing",
        "size4",
        "alignment1",
        "source_bool",
        "frame1",
    ),
)
def test_finite_vector_strict_schema(kind):
    vector = copy.deepcopy(c.vectors()[0])
    if kind == "old_size_bool":
        vector["old_size"] = True
    elif kind == "profile_bool":
        vector["xmm_profile"] = False
    elif kind == "extra":
        vector["unused"] = 0
    elif kind == "missing":
        vector.pop("cookie")
    elif kind == "size4":
        vector["old_size"] = 4
    elif kind == "alignment1":
        vector["vector_alignment"] = 1
    elif kind == "source_bool":
        vector["source_keys"] = [False]
    else:
        vector["frame_alignment"] = 1
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "register_bool",
        "xmm_bool",
        "page_bytearray",
        "page_missing",
        "extra",
        "missing",
        "header",
        "tail44",
        "spare16",
        "ancestor",
        "dummy",
        "feature_padding",
        "old_size",
    ),
)
def test_exact_fixture_no_alias_or_refreshed_recipe(kind):
    vector = c.vectors()[-1]
    fixture = c._fixture(vector)
    if kind == "register_bool":
        fixture["registers"]["eax"] = False
    elif kind == "xmm_bool":
        fixture["xmm"]["xmm7"] = False
    elif kind == "page_bytearray":
        fixture["pages"][0x06004000] = bytearray(4096)
    elif kind == "page_missing":
        fixture["pages"].pop(0x06004000)
    elif kind == "extra":
        fixture["unused"] = 0
    elif kind == "missing":
        fixture.pop("source_state")
    elif kind == "old_size":
        fixture["old_size"] = 4
    else:
        at = {
            "header": U + 8,
            "tail44": fixture["old_begin"] + 44,
            "spare16": fixture["vector_begin"] + 56,
            "ancestor": fixture["stack"] + 8,
            "dummy": fixture["stack"] - 40,
            "feature_padding": 0x00893001,
        }[kind]
        install(fixture["pages"], at, bytes([read(fixture["pages"], at, 1) ^ 1]))
    before = copy.deepcopy(fixture)
    with pytest.raises(c.ConformanceError, match="fixture recipe"):
        c._expected(vector, fixture)
    assert fixture == before


@pytest.mark.parametrize(
    "kind",
    (
        "old44",
        "copy44",
        "append",
        "spare16",
        "header",
        "ancestor",
        "source",
        "node_padding",
        "payload",
        "iterator",
    ),
)
def test_independent_memory_equation_exposes_refreshed_hash_forgery(cases, kind):
    vector, fixture, wanted = cases[-1]
    result = c._expected(vector, fixture)
    node = result["insertions"][-1]["destination_address"]
    at = {
        "old44": fixture["old_begin"] + 44,
        "copy44": fixture["vector_begin"] + 44,
        "append": fixture["vector_begin"] + 48,
        "spare16": fixture["vector_begin"] + 56,
        "header": U + 12,
        "ancestor": fixture["stack"] + 8,
        "source": c.prefix.SOURCE_HEAD + 14,
        "node_padding": node + 14,
        "payload": node + 20,
        "iterator": fixture["stack"] - 12,
    }[kind]
    install(result["pages"], at, bytes([read(result["pages"], at, 1) ^ 1]))
    # A freshly calculated full-page hash cannot change the byte equation.
    assert page_hashes(result["pages"]) != page_hashes(wanted["packet"]["pages"])
    with pytest.raises(AssertionError):
        check_result(vector, fixture, result, wanted)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "gpr_bool",
        "xmm_bool",
        "df_bool",
        "metadata_bool",
        "request48",
        "copy32",
        "copy_edx_zero",
        "copy_edx32",
        "free_bool",
        "entry_flags",
        "unused_dummy",
        "resize_gpr",
        "trace_extra",
        "spare_coordinated",
        "spare_all_views",
        "ancestor_coordinated",
        "source_snapshot",
        "header_order",
        "boundary_divergence",
    ),
)
def test_independent_full_growth_join_rejects_child_forgery(monkeypatch, kind):
    original = c.model.apply

    def changed(**kwargs):
        child = original(**kwargs)
        if kind == "extra":
            child["unused"] = 0
        elif kind == "missing":
            child.pop("free_packet")
        elif kind == "gpr_bool":
            child["registers"]["ecx"] = True
        elif kind == "xmm_bool":
            child["xmm"]["xmm7"] = False
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "metadata_bool":
            child["allocation_packet"]["relation"]["metadata"] = False
        elif kind == "request48":
            child["allocation_request"]["bytes"] = 48
        elif kind == "copy32":
            child["geometry"]["copy_bytes"] = 32
        elif kind in ("copy_edx_zero", "copy_edx32"):
            child["copy_packet"]["registers"]["edx"] = (
                0
                if kind == "copy_edx_zero"
                else read(kwargs["pages"], kwargs["source"] + 32)
            )
        elif kind == "free_bool":
            child["free_packet"]["protocol"]["result"] = True
        elif kind == "entry_flags":
            child["allocation_entry"]["flags"] = 0x246
        elif kind == "unused_dummy":
            child["resize_packet"]["registers"]["ebx"] ^= 1
        elif kind == "resize_gpr":
            child["resize_entry"]["registers"]["edi"] = 4
        elif kind == "trace_extra":
            child["trace_rvas"].append("0x002eb674")
        elif kind in (
            "spare_coordinated",
            "spare_all_views",
            "ancestor_coordinated",
            "source_snapshot",
        ):
            at = (
                kwargs["destination"] + 56
                if kind in ("spare_coordinated", "spare_all_views")
                else (
                    kwargs["registers"]["esp"] + 52
                    if kind == "ancestor_coordinated"
                    else kwargs["source"] + 44
                )
            )
            value = read(child["pages"], at) ^ 1
            install(child["pages"], at, value.to_bytes(4, "little"))
            child["events"].append(
                dict(access="write", address=at, width=4, value=value)
            )
            if kind == "source_snapshot":
                child["copy_packet"]["source_snapshot"] = child["copy_packet"][
                    "source_snapshot"
                ][:44] + value.to_bytes(4, "little")
            if kind == "spare_all_views":
                # Forge every page/event view consistently; the fixed input
                # byte equation must still reject the invented spare write.
                child["events"].pop()

                def coordinate(value_packet):
                    if type(value_packet) is dict:
                        if "pages" in value_packet:
                            install(
                                value_packet["pages"], at, value.to_bytes(4, "little")
                            )
                        if "events" in value_packet:
                            value_packet["events"].append(
                                dict(access="write", address=at, width=4, value=value)
                            )
                        for key, nested in value_packet.items():
                            if key not in ("pages", "events"):
                                coordinate(nested)
                    elif type(value_packet) is list:
                        for nested in value_packet:
                            coordinate(nested)

                coordinate(child)
        elif kind == "header_order":
            indices = [
                i
                for i, row in enumerate(child["events"])
                if row["access"] == "write" and row["address"] in (U + 4, U + 8, U + 12)
            ]
            i, j = indices[:2]
            child["events"][i], child["events"][j] = (
                child["events"][j],
                child["events"][i],
            )
        else:
            child["copy_entry"]["registers"]["esp"] += 4
        return child

    monkeypatch.setattr(c.model, "apply", changed)
    vector = c.vectors()[-1]
    fixture = c._fixture(vector)
    before = copy.deepcopy(fixture)
    with pytest.raises(c.ConformanceError, match="growth join"):
        c._expected(vector, fixture)
    assert fixture == before


PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (
    PREFIX + "native_lua_class_simd_vector6_to7_return_conformance.json"
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
            ).read_text()
        )
        for key, (kind, digest) in c.SOURCE_PINS.items()
    }


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.common.EXE_SHA256
    codes, points, selected = c._load_code(data, image, sources())
    return codes, points


def check_actual_boundary(actual, expected, name=None):
    keys = {
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
    if name is not None:
        keys.add("name")
    assert set(actual) == keys
    if name is not None:
        assert actual["name"] == name
    for key in ("registers", "xmm", "endpoint", "flags", "flag_mask", "df"):
        strict_equal(actual[key], expected[key])
    assert type(actual["eflags"]) is int and 0 <= actual["eflags"] <= 0xFFFFFFFF
    assert actual["eflags"] & expected["flag_mask"] == expected["flags"]
    assert actual["eflags"] & 0x400 == 0
    assert actual["pages_sha256"] == page_hashes(expected["pages"])
    assert actual["events_sha256"] == canonical_hash(expected["events"])


def packet(index):
    import unicorn as uc
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = c.vectors()[index]
    fixture = c._fixture(vector)
    wanted = independent(vector, fixture)
    captured = {}

    def capture(machine, ids, expected, installed):
        strict_equal(installed, fixture)
        check_result(vector, fixture, expected, wanted)
        captured.update(
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            xmm={
                r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper())) for r in XMM
            },
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    independent_trace, machines = [], []
    allowed = {0x00400000 + int(point["rva"], 16) for point in points}
    original_uc = uc.Uc

    def instrumented_uc(*args, **kwargs):
        machine = original_uc(*args, **kwargs)
        machines.append(machine)

        def independent_code_hook(machine, address, size, user):
            if address in allowed:
                independent_trace.append(f"0x{address-0x00400000:08x}")

        machine.hook_add(uc.UC_HOOK_CODE, independent_code_hook)
        return machine

    uc.Uc = instrumented_uc
    try:
        observed = c._run_case(codes, points, vector, capture=capture)
    finally:
        uc.Uc = original_uc
    assert len(machines) == 1
    assert observed["trace_rvas"] == independent_trace
    final = wanted["packet"]
    for key in ("registers", "xmm", "pages", "endpoint"):
        strict_equal(captured[key], final[key])
    assert captured["flags"] & 0x8D5 == 0x44 and captured["flags"] & 0x400 == 0
    assert set(observed) == {
        "vector",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "trace_rvas",
        "events_sha256",
        "summaries",
        "boundaries",
        "pages_sha256",
        "memory_event_count",
        "insertions",
        "allocations",
        "frees",
    }
    for key in ("vector", "registers", "xmm", "flags", "df", "insertions"):
        strict_equal(observed[key], vector if key == "vector" else final[key])
    assert observed["flag_mask"] == 0x8D5
    assert observed["memory_event_count"] == len(final["events"])
    assert observed["events_sha256"] == canonical_hash(final["events"])
    assert observed["pages_sha256"] == page_hashes(final["pages"])
    tail_index = observed["trace_rvas"].index("0x002eb1bb")
    assert observed["trace_rvas"][tail_index:] == [f"0x{pc:08x}" for pc in TAIL]
    # Prefix routing is inherited and checked by its complete actual join; tail
    # routing is handwritten here, including all69 installed-copy occurrences.
    assert tail_index > 0
    names = (
        "class_prefix",
        "growth_entry",
        "resize_entry",
        "allocation_entry",
        "allocation_return",
        "copy_entry",
        "copy_return",
        "free_entry",
        "resize_return",
        "growth_return",
    )
    assert [b["name"] for b in observed["boundaries"]] == list(names)
    for actual, name in zip(observed["boundaries"], names):
        check_actual_boundary(actual, wanted["boundaries"][name], name)
    assert observed["boundaries"][1]["eflags"] == 0x246
    assert observed["boundaries"][2]["eflags"] == 0x202
    assert observed["boundaries"][3]["eflags"] == 0x202
    assert observed["boundaries"][6]["registers"]["edx"] == read(
        fixture["pages"], fixture["old_begin"] + 44
    )
    assert len(observed["summaries"]) == 2
    for actual, expected in zip(observed["summaries"], wanted["imported"]):
        assert set(actual) == set(expected) | {"eflags"}
        strict_equal({k: v for k, v in actual.items() if k != "eflags"}, expected)
        assert type(actual["eflags"]) is int
        assert actual["eflags"] & expected["flag_mask"] == expected["flags"]
        assert actual["eflags"] & 0x400 == 0
    alloc, free = wanted["imported"]
    assert observed["allocations"] == [
        dict(
            node=fixture["vector_begin"],
            entry_esp=alloc["entry_esp"],
            request=72,
            continuation=0x00789463,
        )
    ]
    assert observed["frees"] == [
        dict(
            pointer=fixture["old_begin"],
            entry_esp=free["entry_esp"],
            result=1,
            continuation=0x00789172,
        )
    ]


def controls():
    codes, points = native_inputs()
    for kind, reason in c.CONTROLS.items():
        if kind == "cookie":
            strict_equal(
                c._run_case(codes, points, c.vectors()[-1], kind),
                dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
            )
        else:
            with pytest.raises(c.ConformanceError) as caught:
                c._run_case(codes, points, c.vectors()[-1], kind)
            assert str(caught.value) == reason, kind


def code_tamper():
    codes, points = native_inputs()
    for kind in (
        "missing_body",
        "extra_body",
        "short_body",
        "point_bool",
        "point_extra",
        "point_missing",
        "point_order",
        "coordinated_bytes",
    ):
        cc, pp = copy.deepcopy(codes), copy.deepcopy(points)
        start = next(iter(cc))
        point = pp[0]
        if kind == "missing_body":
            cc.pop(start)
        elif kind == "extra_body":
            cc[0x7FFFFFFF] = b"x"
        elif kind == "short_body":
            cc[start] = cc[start][:-1]
        elif kind == "point_bool":
            point["size"] = True
        elif kind == "point_extra":
            point["unused"] = 0
        elif kind == "point_missing":
            pp.pop()
        elif kind == "point_order":
            pp[0], pp[1] = pp[1], pp[0]
        else:
            body = bytearray(cc[start])
            body[0] ^= 1
            cc[start] = bytes(body)
            point["sha256"] = hashlib.sha256(cc[start][: point["size"]]).hexdigest()
        with pytest.raises(c.ConformanceError):
            c._checked_code_packet(cc, pp)


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed class runtime")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    run = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=2400,
    )
    assert run.returncode == 0, (run.stdout + run.stderr).decode(
        "utf-8", errors="replace"
    )[-4000:]


# Every population; both frames/profiles; all three node and vector alignments.
SELECTED = (0, 35, 36, 53, 72, 103, 108, 125, 144, 179, 180, 197, 216, 247, 252, 287)


@pytest.mark.parametrize("index", SELECTED)
def test_actual_class_boundaries_imported_abi_and_final_full_machine(index):
    isolated("packet", index)


def test_all_intended_native_controls():
    isolated("controls")


def test_direct_code_packet_types_extents_and_refreshed_identity():
    isolated("code_tamper")


@pytest.mark.parametrize(
    "shape", ("missing", "extra", "list", "bool_document", "non_json")
)
def test_preflight_malformed_source_partition(shape):
    supplied = sources()
    key = next(k for k in supplied if k != "program_facts")
    if shape == "missing":
        supplied.pop(key)
    elif shape == "extra":
        supplied["unused"] = {}
    elif shape == "list":
        supplied = list(supplied.items())
    elif shape == "bool_document":
        supplied[key] = False
    else:
        supplied[key]["unused"] = b"not JSON"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_all_twenty_pinned_source_identities():
    identities = c._preflight(sources())
    assert len(identities) == 20 and set(identities) == set(c.SOURCE_PINS)
    for key, (kind, digest) in c.SOURCE_PINS.items():
        assert identities[key] == dict(analysis_kind=kind, canonical_sha256=digest)
        supplied = sources()
        supplied[key]["analysis_kind"] = "forged"
        with pytest.raises(c.ConformanceError):
            c._preflight(supplied)


@pytest.mark.parametrize("key", ("program_facts", "class_simd_return", "growth6_to9"))
def test_build_identity_join_survives_faulty_source_identity_facade(monkeypatch, key):
    supplied = sources()
    supplied[key]["identity" if key == "program_facts" else "build_identity"][
        "executable_sha256"
    ] = ("0" * 64)
    monkeypatch.setattr(
        c.common,
        "_source_identity",
        lambda value, kind, digest, label: dict(
            analysis_kind=kind, canonical_sha256=digest
        ),
    )
    with pytest.raises(c.ConformanceError, match="source build"):
        c._preflight(supplied)


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("primary has not published class6-to7 receipt")
    return json.loads(EVIDENCE.read_text())


def test_receipt_exact_encoding_points_pins_and_independent_byte_counts(receipt, cases):
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert canonical_hash(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == c.vectors()
    assert (
        canonical_hash(receipt["body"]["points"])
        == "bc43b3482b4a7c8a47f3cd213b2ef76ace1a0599aa06b86cdee4ca99d246e690"
    )
    assert (
        len(receipt["body"]["points"]) == 939 and len(receipt["body"]["ranges"]) == 27
    )
    lower = sources()["class_simd_return"]
    assert receipt["body"]["points"] == lower["body"]["points"]
    assert [
        (row["start_rva"], row["exclusive_end_rva"])
        for row in receipt["body"]["ranges"]
    ] == [(row["start_rva"], row["end_rva"]) for row in lower["body"]["ranges"]]
    assert all(
        len(row["sha256"]) == 64
        and all(ch in "0123456789abcdef" for ch in row["sha256"])
        for row in receipt["body"]["ranges"]
    )
    assert set(receipt["source_receipts"]) == set(c.SOURCE_PINS)
    assert {f"0x{pc:08x}" for pc in TAIL} <= set(receipt["executed_rvas"])
    assert all(
        not (0x2EB15F <= int(pc, 16) < 0x2EB179 or 0x2EB1C5 <= int(pc, 16) < 0x2EB1F7)
        for pc in receipt["executed_rvas"]
    )
    ordinary_controls = [row for row in receipt["negative_controls"] if "name" in row]
    assert {r["name"]: r["reason"] for r in ordinary_controls} == {
        k: v for k, v in c.CONTROLS.items() if k != "cookie"
    }
    strict_equal(
        [r for r in receipt["negative_controls"] if "kind" in r],
        [dict(kind="cookie", rejected=True, endpoint="0x003574d5")],
    )
    assert all(r["rejected"] is True for r in receipt["negative_controls"])
    assert len(receipt["negative_controls"]) == len(c.CONTROLS) == 60
    counts = dict(
        cases=288,
        loaded_sites=939,
        loaded_bytes=2440,
        tree_allocations=0,
        allocation_requests=288,
        free_requests=288,
        existing_insertions=288 * 7 // 2,
        copied_bytes=48 * 288,
        preserved_old_bytes=48 * 288,
        allocated_bytes=72 * 288,
        appended_bytes=8 * 288,
        live_vector_bytes=56 * 288,
        spare_bytes=16 * 288,
        wide_reads=4 * 288,
        wide_writes=4 * 288,
        scalar_tail_reads=4 * 288,
        scalar_tail_writes=4 * 288,
        memory_events=sum(len(w["packet"]["events"]) for v, f, w in cases),
        controls=60,
        opaque_instructions=0,
        accounting_promotions=0,
    )
    for key, value in counts.items():
        assert (
            type(receipt["summary"][key]) is int and receipt["summary"][key] == value
        ), key
    assert receipt["summary"]["executed_sites"] == len(receipt["executed_rvas"])
    assert type(receipt["summary"]["native_instructions"]) is int
    assert receipt["summary"]["native_instructions"] >= 288 * len(TAIL)
    assert set(receipt["executed_rvas"]) <= {
        p["rva"] for p in receipt["body"]["points"]
    }


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool_summary",
        "vector",
        "control",
        "point",
        "range",
        "observation",
        "pin",
        "scope",
        "bytes_json",
    ),
)
def test_sealed_receipt_tampering_and_typed_json(kind, receipt):
    value = copy.deepcopy(receipt)
    if kind == "summary":
        value["summary"]["copied_bytes"] += 1
    elif kind == "bool_summary":
        value["summary"]["opaque_instructions"] = False
    elif kind == "vector":
        value["vectors"][0]["xmm_profile"] = False
    elif kind == "control":
        value["negative_controls"][0]["rejected"] = 1
    elif kind == "point":
        value["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        value["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observation":
        value["observations_sha256"] = "0" * 64
    elif kind == "pin":
        value["source_receipts"]["growth6_to9"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        value["scope"]["not_claimed"].clear()
    else:
        value["unused"] = b"not JSON"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(value, sources())


def builder():
    actual = c.build_conformance(Path(os.environ["ITB_EXACT_EXE"]), sources())
    assert c.encode_conformance(actual).encode("utf-8") == EVIDENCE.read_bytes()


def cli(command):
    args = [
        sys.executable,
        str(
            ROOT / "scripts/itb_native_lua_class_simd_vector6_to7_return_conformance.py"
        ),
        command,
    ]
    for key, (kind, digest) in c.SOURCE_PINS.items():
        path = PROGRAMS / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        args += ["--executable", os.environ["ITB_EXACT_EXE"]]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    run = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=2400)
    assert run.returncode == 0, run.stderr.decode("utf-8", errors="replace")[-4000:]
    assert run.stderr == b""
    if command == "build":
        assert run.stdout == EVIDENCE.read_bytes()
    else:
        value = json.loads(run.stdout)
        assert value["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert value["evidence_sha256"] == c.SEALED_SHA256
        assert run.stdout == c.encode_conformance(value).encode("utf-8")


def test_exact_native_builder_reproduces_receipt(receipt):
    isolated("builder")


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_serial_exact_cli_commands(command, receipt):
    if command == "verify-structure":
        cli(command)
    else:
        isolated("cli", command)


if __name__ == "__main__":
    faulthandler.disable()
    if sys.argv[1] == "packet":
        packet(int(sys.argv[2]))
    elif sys.argv[1] == "code_tamper":
        code_tamper()
    elif sys.argv[1] == "builder":
        builder()
    elif sys.argv[1] == "cli":
        cli(sys.argv[2])
    else:
        controls()
