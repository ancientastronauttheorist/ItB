"""Independent continuous ordinary full6-to9 growth conformance laws."""

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
from src.observatory import native_simd_vector_growth6_to9_conformance as c
from tests import test_itb_native_simd_vector_resize6_to9_semantics as handwritten

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
H, O, D, STACK, RETURN = 0x0FFFFFD0, 0x06002800, 0x06004800, 0x30000000, 0x04000000
GROWTH_PREFIX = (
    0x2EB620,
    0x2EB621,
    0x2EB623,
    0x2EB624,
    0x2EB627,
    0x2EB629,
    0x2EB62C,
    0x2EB62E,
    0x2EB631,
    0x2EB634,
    0x2EB636,
    0x2EB638,
    0x2EB63A,
    0x2EB63B,
    0x2EB640,
    0x2EB643,
    0x2EB645,
    0x2EB647,
    0x2EB64A,
    0x2EB64C,
    0x2EB64E,
    0x2EB64F,
    0x2EB652,
    0x2EB654,
    0x2EB656,
    0x2EB658,
    0x2EB65A,
    0x2EB65C,
    0x2EB65E,
    0x2EB661,
    0x2EB663,
    0x2EB666,
    0x2EB668,
    0x2EB669,
)
GROWTH_SUFFIX = (0x2EB66E, 0x2EB66F, 0x2EB670, 0x2EB671)
TRACE = GROWTH_PREFIX + handwritten.TRACE + GROWTH_SUFFIX
canonical_hash, page_hashes = handwritten.canonical_hash, handwritten.page_hashes
blob, install = handwritten.blob, handwritten.install


def independent(vector, fixture):
    """Growth scalar equations around the independently handwritten resize law."""
    g = fixture["registers"]["esp"]
    o, d = O + vector["alignment"], D + vector["alignment"]
    pages = copy.deepcopy(fixture["pages"])
    incoming = copy.deepcopy(fixture["registers"])
    events = []

    def event(access, address, value):
        if access == "write":
            install(pages, address, value.to_bytes(4, "little"))
        else:
            assert int.from_bytes(blob(pages, address, 4), "little") == value
        events.append(dict(access=access, address=address, width=4, value=value))

    for access, address, value in (
        ("write", g - 4, incoming["esi"]),
        ("write", g - 8, incoming["edi"]),
        ("read", H + 8, o + 48),
        ("read", H + 4, o + 48),
        ("read", H, o),
        ("write", g - 12, incoming["ebx"]),
        ("write", g - 16, 9),
        ("write", g - 20, 0x006EB66E),
    ):
        event(access, address, value)
    entry = dict(
        incoming, eax=9, ebx=0x1FFFFFFC, ecx=H, edx=9, esi=H, edi=6, esp=g - 20
    )
    child_input = dict(
        pages=copy.deepcopy(pages),
        registers=entry,
        xmm=copy.deepcopy(fixture["xmm"]),
        source=o,
        destination=d,
        object_address=H,
        return_address=0x006EB66E,
        entry_flags=0x202,
    )
    # CMP(proposal9, minimum7) gives result2: CF/PF/AF/ZF/SF/OF all zero.
    child = handwritten.independent(**child_input)
    resize_entry = dict(
        registers=entry,
        xmm=copy.deepcopy(fixture["xmm"]),
        pages=copy.deepcopy(pages),
        events=copy.deepcopy(events),
        endpoint=0x006EB680,
        flags=0,
        flag_mask=0x8D5,
        df=0,
    )
    prefix = copy.deepcopy(events)
    pages = copy.deepcopy(child["pages"])
    events.extend(copy.deepcopy(child["events"]))
    resize_return = {
        key: copy.deepcopy(child[key])
        for key in ("registers", "xmm", "pages", "endpoint", "flags", "flag_mask", "df")
    }
    resize_return["events"] = copy.deepcopy(events)
    boundaries = {"resize_entry": resize_entry}
    for name in (
        "allocation_entry",
        "allocation_return",
        "copy_entry",
        "copy_return",
        "free_entry",
    ):
        boundary = copy.deepcopy(child["boundaries"][name])
        boundary["events"] = prefix + boundary["events"]
        boundaries[name] = boundary
    boundaries["resize_return"] = resize_return
    imported = []
    for role, count, registers, xmms, flags, mask in (
        (
            "allocation",
            36,
            dict(entry, eax=72, esi=72, ebp=g - 76, esp=g - 96),
            fixture["xmm"],
            4,
            0x8C5,
        ),
        (
            "free",
            99,
            dict(
                child["boundaries"]["free_entry"]["registers"],
                eax=0x1FFFFFFF,
                edx=7,
                ebp=g - 72,
                esp=g - 88,
            ),
            child["xmm"],
            int(((o & 255).bit_count() % 2) == 0) << 2,
            0x8D5,
        ),
    ):
        import_pages = copy.deepcopy(fixture["pages"])
        for row in events[:count]:
            if row["access"] == "write":
                install(
                    import_pages,
                    row["address"],
                    row["value"].to_bytes(row["width"], "little"),
                )
        request = child[
            "allocation_request" if role == "allocation" else "free_request"
        ]
        imported.append(
            dict(
                role=role,
                entry_esp=request["entry_esp"],
                words=request["words"],
                registers=registers,
                xmm=copy.deepcopy(xmms),
                flags=flags,
                flag_mask=mask,
                df=0,
                endpoint=0x05000000,
                pages_sha256=page_hashes(import_pages),
                events_sha256=canonical_hash(events[:count]),
            )
        )
    for address, value in (
        (g - 12, incoming["ebx"]),
        (g - 8, incoming["edi"]),
        (g - 4, incoming["esi"]),
        (g, RETURN),
    ):
        event("read", address, value)
    return dict(
        registers=dict(incoming, eax=d + 48, ecx=0xA0000001, edx=0xB0000001, esp=g + 8),
        xmm=copy.deepcopy(child["xmm"]),
        pages=pages,
        events=events,
        flags=handwritten.add_flags(g - 52, 12),
        flag_mask=0x8D5,
        df=0,
        endpoint=RETURN,
        boundaries=boundaries,
        child_input=child_input,
        child=child,
        allocation_request=copy.deepcopy(child["allocation_request"]),
        free_request=copy.deepcopy(child["free_request"]),
        source_snapshot=child["source_snapshot"],
        stack_extent=[g - 96, g + 8],
        imported=imported,
    )


def check_final(vector, fixture, result, wanted):
    assert set(result) == {
        "geometry",
        "registers",
        "xmm",
        "flags",
        "flag_mask",
        "df",
        "events",
        "pages",
        "endpoint",
        "allocation_entry",
        "allocation_packet",
        "copy_entry",
        "copy_packet",
        "free_entry",
        "free_packet",
        "allocation_request",
        "free_request",
        "trace_rvas",
        "resize_entry",
        "resize_return",
        "resize_packet",
    }
    for key in (
        "registers",
        "xmm",
        "pages",
        "events",
        "flags",
        "flag_mask",
        "df",
        "endpoint",
    ):
        assert result[key] == wanted[key], key
    assert result["trace_rvas"] == [f"0x{pc:08x}" for pc in TRACE]
    assert len(result["events"]) == 116
    handwritten.check_result(
        wanted["child_input"], result["resize_packet"], wanted["child"]
    )
    for name in (
        "resize_entry",
        "resize_return",
        "allocation_entry",
        "copy_entry",
        "free_entry",
    ):
        assert result[name] == wanted["boundaries"][name], name
    for name in (
        "geometry",
        "allocation_packet",
        "copy_packet",
        "free_packet",
        "allocation_request",
        "free_request",
    ):
        assert result[name] == result["resize_packet"][name], name
    a = vector["alignment"]
    assert blob(result["pages"], O + a, 48) == wanted["source_snapshot"]
    assert blob(result["pages"], D + a + 48, 24) == blob(
        fixture["pages"], D + a + 48, 24
    )
    g = fixture["registers"]["esp"]
    assert blob(result["pages"], STACK, g - 96 - STACK) == blob(
        fixture["pages"], STACK, g - 96 - STACK
    )
    assert blob(result["pages"], g, STACK + 8192 - g) == blob(
        fixture["pages"], g, STACK + 8192 - g
    )
    assert [
        row
        for row in result["events"]
        if row["access"] == "write" and H <= row["address"] < H + 12
    ] == [
        dict(access="write", address=H + 8, width=4, value=D + a + 72),
        dict(access="write", address=H + 4, width=4, value=D + a + 48),
        dict(access="write", address=H, width=4, value=D + a),
    ]


@pytest.mark.parametrize("alignment", range(16))
def test_all_profiles_independent_growth_resize_join_and_complete_pages(alignment):
    for profile in range(3):
        vector = dict(alignment=alignment, profile=profile)
        fixture = c._fixture(vector)
        before = copy.deepcopy((vector, fixture))
        wanted = independent(vector, fixture)
        result = c._expected(vector, fixture)
        check_final(vector, fixture, result, wanted)
        assert (vector, fixture) == before
        result["resize_packet"]["registers"]["eax"] ^= 1
        result["resize_entry"]["xmm"]["xmm7"] ^= 1
        result["events"][0]["value"] ^= 1
        assert (vector, fixture) == before


def test_exact_matrix_source_backed_request_and_outer_child_frames():
    assert c.vectors() == [
        dict(alignment=a, profile=p) for a in range(16) for p in range(3)
    ]
    assert len(GROWTH_PREFIX) == 34 and len(GROWTH_SUFFIX) == 4 and len(TRACE) == 235
    assert len(set(TRACE)) == 217
    assert 6 + 6 // 2 == 9 and max(6 + 1, 9) == 9
    assert 0x1FFFFFFF - 6 // 2 == 0x1FFFFFFC
    assert len(c.SOURCE_PINS) == 11
    assert c.SOURCE_PINS["growth"] == (
        "pe_native_lua_vector_growth_semantics",
        "6e442065281f9d7f1853dbb2d2dd91b3d5645cae16a5497db772b7a66f28ec69",
    )
    assert c.SOURCE_PINS["resize6_to9"] == (
        "pe_native_simd_vector_resize6_to9_conformance",
        "009f36e1b254058ec21f7af157f6e86ebfa18039abe24fce1690f9df97bc2949",
    )
    assert len(c.CONTROLS) == 43
    assert c.CONTROLS["resize_request"] == "growth6 to9 resize entry differs"
    assert c.CONTROLS["child_tail"] == "growth6 to9 copy return differs"
    assert c.CONTROLS["caller_argument"] == "growth6 to9 final pages differ"
    for a in range(16):
        g = STACK + 0x1000 + a
        assert c.frame_join(g) == dict(
            protected_start=g - 96,
            protected_end=g + 8,
            resize=g - 20,
            allocation=g - 48,
            heap_allocate=g - 96,
            copy=g - 56,
            deallocation=g - 56,
            heap_free=g - 88,
            returned=g + 8,
        )
        assert c.geometry(dict(alignment=a, profile=0)) == dict(
            old_begin=O + a,
            old_end=O + a + 48,
            old_capacity=O + a + 48,
            new_begin=D + a,
            new_end=D + a + 48,
            new_capacity=D + a + 72,
            copy_bytes=48,
            request=72,
            old_size=6,
            requested=9,
        )


@pytest.mark.parametrize(
    "kind",
    (
        "list",
        "extra",
        "missing",
        "alignment_bool",
        "profile_bool",
        "alignment_high",
        "profile_high",
    ),
)
def test_finite_vector_schema_and_strict_words(kind):
    vector = dict(alignment=7, profile=2)
    if kind == "list":
        vector = list(vector.items())
    elif kind == "extra":
        vector["unused"] = 0
    elif kind == "missing":
        vector.pop("profile")
    elif kind.endswith("bool"):
        vector[kind.split("_")[0]] = True
    else:
        vector[kind.split("_")[0]] = 16 if kind == "alignment_high" else 3
    with pytest.raises(c.ConformanceError):
        c.geometry(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "gpr_bool",
        "gpr_extra",
        "xmm_bool",
        "xmm_missing",
        "flags_bool",
        "flags_other",
        "return_bool",
        "return_other",
        "page_mutable",
        "page_short",
        "page_missing",
        "page_extra",
        "header",
        "spare",
        "old",
        "ancestor",
        "feature_padding",
        "caller_unused",
    ),
)
def test_exact_fixture_rejects_typed_relabeling_and_preserved_page_changes(kind):
    vector = dict(alignment=7, profile=2)
    fixture = c._fixture(vector)
    if kind == "extra":
        fixture["unused"] = 0
    elif kind == "missing":
        fixture.pop("entry_flags")
    elif kind == "gpr_bool":
        fixture["registers"]["eax"] = False
    elif kind == "gpr_extra":
        fixture["registers"]["unused"] = 0
    elif kind == "xmm_bool":
        fixture["xmm"]["xmm0"] = False
    elif kind == "xmm_missing":
        fixture["xmm"].pop("xmm0")
    elif kind.startswith("flags_"):
        fixture["entry_flags"] = False if kind == "flags_bool" else 0x202
    elif kind.startswith("return_"):
        fixture["return_address"] = True if kind == "return_bool" else RETURN + 4
    elif kind == "page_mutable":
        fixture["pages"][0x06004000] = bytearray(fixture["pages"][0x06004000])
    elif kind == "page_short":
        fixture["pages"][0x06004000] = fixture["pages"][0x06004000][:-1]
    elif kind == "page_missing":
        fixture["pages"].pop(0x06004000)
    elif kind == "page_extra":
        fixture["pages"][0x10000000] = bytes(4096)
    else:
        g = fixture["registers"]["esp"]
        address = dict(
            header=H,
            spare=D + 7 + 48,
            old=O + 7 + 44,
            ancestor=g + 8,
            feature_padding=0x00893001,
            caller_unused=g + 4,
        )[kind]
        install(
            fixture["pages"],
            address,
            bytes([blob(fixture["pages"], address, 1)[0] ^ 1]),
        )
    before = copy.deepcopy(fixture)
    with pytest.raises(c.ConformanceError, match="fixture recipe"):
        c._expected(vector, fixture)
    assert fixture == before


@pytest.mark.parametrize(
    "kind",
    (
        "register_bool",
        "xmm_bool",
        "flags_bool",
        "df_bool",
        "geometry_bool",
        "extra",
        "missing",
        "allocation_metadata_bool",
        "copy_edx32",
        "free_result_bool",
        "allocation_entry_flags",
        "spare_and_event",
        "ancestor_and_event",
        "source_and_copy_snapshot",
        "trace_extra",
        "header_order",
        "boundary_divergence",
    ),
)
def test_complete_resize_join_rejects_typed_and_coordinated_child_corruption(
    monkeypatch, kind
):
    original = c.model.apply

    def corrupted(**kwargs):
        child = original(**kwargs)
        if kind == "register_bool":
            child["registers"]["ecx"] = True
        elif kind == "xmm_bool":
            child["xmm"]["xmm2"] = False
        elif kind == "flags_bool":
            child["flags"] = False
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "geometry_bool":
            child["geometry"]["requested"] = True
        elif kind == "extra":
            child["unused"] = 0
        elif kind == "missing":
            child.pop("free_request")
        elif kind == "allocation_metadata_bool":
            child["allocation_packet"]["relation"]["metadata"] = False
        elif kind == "copy_edx32":
            child["copy_packet"]["registers"]["edx"] = 0
        elif kind == "free_result_bool":
            child["free_packet"]["protocol"]["result"] = True
        elif kind == "allocation_entry_flags":
            child["allocation_entry"]["flags"] = 0
        elif kind in (
            "spare_and_event",
            "ancestor_and_event",
            "source_and_copy_snapshot",
        ):
            at = (
                kwargs["destination"] + 48
                if kind == "spare_and_event"
                else (
                    kwargs["registers"]["esp"] + 28
                    if kind == "ancestor_and_event"
                    else kwargs["source"]
                )
            )
            value = int.from_bytes(blob(child["pages"], at, 4), "little") ^ 1
            install(child["pages"], at, value.to_bytes(4, "little"))
            child["events"].append(
                dict(access="write", address=at, width=4, value=value)
            )
            if kind == "source_and_copy_snapshot":
                child["copy_packet"]["source_snapshot"] = (
                    value.to_bytes(4, "little")
                    + child["copy_packet"]["source_snapshot"][4:]
                )
        elif kind == "trace_extra":
            child["trace_rvas"].append("0x002eb674")
        elif kind == "header_order":
            child["events"][-8], child["events"][-7] = (
                child["events"][-7],
                child["events"][-8],
            )
        else:
            child["copy_entry"]["registers"]["esi"] ^= 1
        return child

    monkeypatch.setattr(c.model, "apply", corrupted)
    vector = dict(alignment=15, profile=2)
    fixture = c._fixture(vector)
    before = copy.deepcopy(fixture)
    with pytest.raises(c.ConformanceError, match="resize primitive"):
        c._expected(vector, fixture)
    assert fixture == before


PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (PREFIX + "native_simd_vector_growth6_to9_conformance.json")


def sources():
    base = ROOT / "data/observatory/programs"
    return {
        key: json.loads(
            (
                base
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
    return c._load_code(data, image, sources())


def packet(alignment):
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = dict(alignment=alignment, profile=alignment % 3)
    fixture = c._fixture(vector)
    wanted = independent(vector, fixture)
    captured = {}

    def capture(machine, ids, expected, installed):
        captured.update(
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            xmm={
                r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper())) for r in XMM
            },
            pages={p: bytes(machine.mem_read(p, 4096)) for p in fixture["pages"]},
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
        )

    observed = c._run_case(codes, points, vector, capture=capture)
    for key in ("registers", "xmm", "pages", "endpoint"):
        assert captured[key] == wanted[key], key
    assert (
        captured["flags"] & 0x8D5 == wanted["flags"] and captured["flags"] & 0x400 == 0
    )
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
    }
    for key in ("registers", "xmm", "flags", "flag_mask", "df"):
        assert observed[key] == wanted[key], key
    assert observed["vector"] == vector and observed["memory_event_count"] == 116
    assert observed["trace_rvas"] == [f"0x{pc:08x}" for pc in TRACE]
    assert observed["events_sha256"] == canonical_hash(wanted["events"])
    assert observed["pages_sha256"] == page_hashes(wanted["pages"])
    assert len(observed["summaries"]) == 2
    for actual, expected_import in zip(observed["summaries"], wanted["imported"]):
        assert set(actual) == set(expected_import) | {"eflags"}
        assert {
            key: value for key, value in actual.items() if key != "eflags"
        } == expected_import
        assert type(actual["eflags"]) is int and 0 <= actual["eflags"] <= 0xFFFFFFFF
        assert (
            actual["eflags"] & expected_import["flag_mask"] == expected_import["flags"]
        )
        assert actual["eflags"] & 0x400 == 0
    names = (
        "resize_entry",
        "allocation_entry",
        "allocation_return",
        "copy_entry",
        "copy_return",
        "free_entry",
        "resize_return",
    )
    assert [b["name"] for b in observed["boundaries"]] == list(names)
    for actual, name in zip(observed["boundaries"], names):
        expected = wanted["boundaries"][name]
        assert set(actual) == {
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
        for key in ("registers", "xmm", "endpoint", "flags", "flag_mask", "df"):
            assert actual[key] == expected[key], (name, key)
        assert (
            type(actual["eflags"]) is int
            and actual["eflags"] & expected["flag_mask"] == expected["flags"]
            and actual["eflags"] & 0x400 == 0
        )
        assert actual["pages_sha256"] == page_hashes(expected["pages"])
        assert actual["events_sha256"] == canonical_hash(expected["events"])
    assert observed["boundaries"][4]["registers"]["edx"] == int.from_bytes(
        wanted["source_snapshot"][44:48], "little"
    )


def controls():
    codes, points = native_inputs()
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, dict(alignment=15, profile=2), kind)
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
        "coordinated_bytes",
    ):
        cc, pp = copy.deepcopy(codes), copy.deepcopy(points)
        name = next(iter(cc))
        point = pp[name][0]
        start = c.BODIES[name][0]
        if kind == "missing_body":
            cc.pop(name)
        elif kind == "extra_body":
            cc["unused"] = b"x"
        elif kind == "short_body":
            cc[name] = cc[name][:-1]
        elif kind == "point_bool":
            point["size"] = True
        elif kind == "point_extra":
            point["unused"] = 0
        elif kind == "point_missing":
            pp[name].pop()
        else:
            offset = int(point["rva"], 16) - start
            body = bytearray(cc[name])
            body[offset] ^= 1
            cc[name] = bytes(body)
            point["sha256"] = hashlib.sha256(
                cc[name][offset : offset + point["size"]]
            ).hexdigest()
        with pytest.raises(c.ConformanceError):
            c._checked_code_packet(cc, pp)


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed growth runtime")
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


@pytest.mark.parametrize("alignment", range(16))
def test_actual_boundaries_and_final_full_machine(alignment):
    isolated("packet", alignment)


def test_all_intended_native_controls():
    isolated("controls")


def test_direct_code_packet_schema_and_refreshed_byte_identity():
    isolated("code_tamper")


@pytest.mark.parametrize(
    "shape", ("missing", "extra", "list", "bool_document", "non_json")
)
def test_preflight_rejects_malformed_source_partition(shape):
    supplied = sources()
    if shape == "missing":
        supplied.pop("owner")
    elif shape == "extra":
        supplied["unused"] = {}
    elif shape == "list":
        supplied = list(supplied.items())
    elif shape == "bool_document":
        supplied["owner"] = False
    else:
        supplied["owner"]["unused"] = b"not JSON"
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


def test_preflight_checks_exact_all_source_identities():
    identities = c._preflight(sources())
    assert set(identities) == set(c.SOURCE_PINS)
    for key, (kind, digest) in c.SOURCE_PINS.items():
        assert identities[key] == dict(analysis_kind=kind, canonical_sha256=digest)
        supplied = sources()
        supplied[key]["analysis_kind"] = "forged"
        with pytest.raises(c.ConformanceError):
            c._preflight(supplied)


@pytest.mark.parametrize(
    "key",
    (
        "program_facts",
        "owner",
        "allocation_conformance",
        "deallocation_conformance",
        "installed_copy48",
        "growth",
        "resize6_to9",
    ),
)
def test_independent_build_check_rejects_disagreement_after_identity_facade(
    monkeypatch, key
):
    supplied = sources()
    identity = supplied[key]["identity" if key == "program_facts" else "build_identity"]
    identity["executable_sha256"] = "0" * 64
    # Exercise the independent build join even if a source-identity facade is faulty.
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
        pytest.skip("primary has not published the growth6-to9 receipt")
    return json.loads(EVIDENCE.read_text())


def test_receipt_exact_encoding_source_anchor_and_independent_equations(receipt):
    raw = EVIDENCE.read_bytes()
    assert raw == c.encode_conformance(receipt).encode("utf-8") and b"\r" not in raw
    assert canonical_hash(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == [
        dict(alignment=a, profile=p) for a in range(16) for p in range(3)
    ]
    assert receipt["executed_rvas"] == [f"0x{pc:08x}" for pc in sorted(set(TRACE))]
    assert (
        canonical_hash(receipt["body"]["points"])
        == "a2288f29ad9c57968d54196062f106d9111f45f28c75c80cf31db1964aa42b44"
    )
    assert len(receipt["body"]["points"]) == 289
    assert {
        row["name"]: row["reason"] for row in receipt["negative_controls"]
    } == c.CONTROLS
    assert len(receipt["negative_controls"]) == len(c.CONTROLS)
    assert all(row["rejected"] is True for row in receipt["negative_controls"])
    assert set(receipt["source_receipts"]) == set(c.SOURCE_PINS)
    for key, value in dict(
        cases=48,
        loaded_sites=289,
        loaded_bytes=754,
        executed_sites=len(set(TRACE)),
        native_instructions=48 * len(TRACE),
        allocation_api_summaries=48,
        free_api_summaries=48,
        copied_bytes=48 * 48,
        allocated_bytes=72 * 48,
        spare_bytes=24 * 48,
        wide_reads=4 * 48,
        wide_writes=4 * 48,
        scalar_tail_reads=4 * 48,
        scalar_tail_writes=4 * 48,
        preserved_old_bytes=48 * 48,
        memory_events=116 * 48,
        controls=len(c.CONTROLS),
        accounting_promotions=0,
    ).items():
        assert (
            type(receipt["summary"][key]) is int and receipt["summary"][key] == value
        ), key
    assert all(
        pc not in receipt["executed_rvas"]
        for pc in (
            "0x0036ea9d",
            "0x0036ea9f",
            "0x0036eaa1",
            "0x0036eaa2",
            "0x0036eaa3",
            "0x0036eaa4",
        )
    )


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "bool_summary",
        "vector",
        "controls",
        "point",
        "range",
        "observation",
        "pin",
        "scope",
        "bytes_json",
    ),
)
def test_sealed_receipt_tampering_and_typed_json_reject(kind, receipt):
    value = copy.deepcopy(receipt)
    if kind == "summary":
        value["summary"]["copied_bytes"] += 1
    elif kind == "bool_summary":
        value["summary"]["accounting_promotions"] = False
    elif kind == "vector":
        value["vectors"][0]["alignment"] = True
    elif kind == "controls":
        value["negative_controls"][0]["rejected"] = 1
    elif kind == "point":
        value["body"]["points"][0]["sha256"] = "0" * 64
    elif kind == "range":
        value["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "observation":
        value["observations_sha256"] = "0" * 64
    elif kind == "pin":
        value["source_receipts"]["owner"]["canonical_sha256"] = "0" * 64
    elif kind == "scope":
        value["scope"]["checked"].append("forged ownership claim")
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
        str(ROOT / "scripts/itb_native_simd_vector_growth6_to9_conformance.py"),
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
def test_exact_serial_cli_commands(command, receipt):
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
