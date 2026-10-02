"""Independent actual-page full6-to9 growth adapter laws."""

import copy
from pathlib import Path
import sys
import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import native_simd_vector_growth6_to9_semantics as m
from src.observatory import native_simd_vector_growth6_to9_conformance as c
from tests import test_itb_native_simd_vector_resize6_to9_semantics as handwritten

GPR = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMM = tuple("xmm" + str(i) for i in range(8))
STACK = 0x30000000
canonical_hash, page_hashes = handwritten.canonical_hash, handwritten.page_hashes
blob, install = handwritten.blob, handwritten.install

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


def independent(
    *,
    pages,
    registers,
    xmm,
    source,
    destination,
    object_address,
    return_address,
    entry_flags,
):
    """Growth scalar equations around the independently handwritten resize law."""
    fixture = dict(
        pages=pages,
        registers=registers,
        xmm=xmm,
        return_address=return_address,
        entry_flags=entry_flags,
    )
    g = fixture["registers"]["esp"]
    o, d = source, destination
    H = object_address
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
        entry_flags=entry_flags & 0x202,
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
        (g, return_address),
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
        endpoint=return_address,
        boundaries=boundaries,
        child_input=child_input,
        child=child,
        allocation_request=copy.deepcopy(child["allocation_request"]),
        free_request=copy.deepcopy(child["free_request"]),
        source_snapshot=child["source_snapshot"],
        stack_extent=[g - 96, g + 8],
        imported=imported,
    )


def check_result(packet, result, wanted):
    fixture = packet
    o, d, H = packet["source"], packet["destination"], packet["object_address"]
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
    assert blob(result["pages"], o, 48) == wanted["source_snapshot"]
    assert blob(result["pages"], d + 48, 24) == blob(fixture["pages"], d + 48, 24)
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
        dict(access="write", address=H + 8, width=4, value=d + 72),
        dict(access="write", address=H + 4, width=4, value=d + 48),
        dict(access="write", address=H, width=4, value=d),
    ]


def growth_input(
    alignment=7,
    profile=2,
    *,
    header=0x10000104,
    entry=None,
    source=None,
    destination=None,
    return_address=0x006EB205,
    entry_flags=0x246,
    unused_word=1,
):
    packet = handwritten.actual_input(
        alignment,
        profile,
        header=header,
        entry=entry,
        source=source,
        destination=destination,
        return_address=return_address,
        entry_flags=entry_flags,
    )
    install(
        packet["pages"],
        packet["registers"]["esp"] + 4,
        unused_word.to_bytes(4, "little"),
    )
    return packet


@pytest.mark.parametrize("alignment", range(16))
def test_all_profiles_actual_class_return_full_independent_law(alignment):
    for profile in range(3):
        packet = growth_input(alignment, profile)
        before = copy.deepcopy(packet)
        result = m.apply(**packet)
        check_result(packet, result, independent(**packet))
        assert result["endpoint"] == 0x006EB205
        assert (
            result["resize_entry"]["flags"] == 0
            and result["resize_entry"]["flag_mask"] == 0x8D5
        )
        assert result["resize_packet"]["allocation_entry"]["flags"] == 0x202
        assert not any(
            row["access"] == "read" and row["address"] == packet["registers"]["esp"] + 4
            for row in result["events"]
        )
        assert packet == before
        result["registers"]["eax"] ^= 1
        result["resize_packet"]["xmm"]["xmm7"] ^= 1
        result["events"][0]["value"] ^= 1
        assert packet == before


ORDINARY_FLAGS = tuple(
    2
    | sum(
        (1 << bit)
        for i, bit in enumerate((0, 2, 4, 6, 7, 9, 11))
        if selector & (1 << i)
    )
    for selector in range(128)
)


@pytest.mark.parametrize("flags", ORDINARY_FLAGS)
def test_all128_ordinary_flags_cmp_status_reset_and_IF_fixedbit_preservation(flags):
    packet = growth_input(entry_flags=flags)
    result = m.apply(**packet)
    check_result(packet, result, independent(**packet))
    assert result["resize_entry"]["flags"] == 0
    assert result["allocation_entry"]["flags"] == flags & 0x202
    assert result["allocation_entry"]["flag_mask"] == 0xFFFFFFFF


@pytest.mark.parametrize(
    "geometry",
    (
        dict(
            header=0x10000FFA,
            source=0x06002FF0,
            destination=0x06004FE7,
            entry=0x30001003,
        ),
        dict(header=0x10000104, entry=0x30000000 + 96),
        dict(header=0x10000104, entry=0x30002000 - 8),
        dict(header=0xFFFFFFF3, destination=0x06005031),
        dict(header=0x10000104, destination=0xFFFFFFB7),
        dict(header=0x10000104, source=0x7FFFFFF0, destination=0x80002000),
        dict(
            header=0x10000004,
            source=0x10001009,
            destination=0x10002017,
            entry=0x300000AD,
            return_address=0x04000000,
        ),
        dict(
            header=0x10000FF4,
            source=0x06003FED,
            destination=0x06007011,
            entry=0x30000FCA,
            return_address=0x006EB206,
        ),
        dict(header=0x10000104, return_address=0xFFFFFFFF),
    ),
)
@pytest.mark.parametrize("unused", (0, 0xFFFFFFFF))
def test_independent_addresses_pages_signed_source_stack_ends_and_unused_caller_word(
    geometry, unused
):
    packet = growth_input(**geometry, unused_word=unused)
    before = copy.deepcopy(packet)
    result = m.apply(**packet)
    check_result(packet, result, independent(**packet))
    g = packet["registers"]["esp"]
    assert int.from_bytes(blob(result["pages"], g + 4, 4), "little") == unused
    assert not any(
        row["access"] == "read" and row["address"] == g + 4 for row in result["events"]
    )
    if packet["source"] == 0x7FFFFFF0:
        assert result["copy_entry"]["flags"] == 0x804
    assert packet == before


def test_production_adapter_consumes_actual_inputs_without_fixture_construction(
    monkeypatch,
):
    packet = growth_input(unused_word=0xDEADBEEF)

    def forbidden(*args, **kwargs):
        raise AssertionError("fixture creation attempted")

    monkeypatch.setattr(c, "_fixture", forbidden)
    monkeypatch.setattr(m.child.primitive, "_fixture", forbidden)
    monkeypatch.setattr(m.child.primitive.installed_copy, "_fixture", forbidden)
    check_result(packet, m.apply(**packet), independent(**packet))


@pytest.mark.parametrize("word", (0, 0xFFFFFFFF))
def test_arbitrary_incoming_nonvolatile_GPR_XMM_words_and_extra_ancestor_page(word):
    packet = growth_input(entry_flags=0xAD7, unused_word=0xFFFFFFFF)
    g, h = packet["registers"]["esp"], packet["object_address"]
    packet["registers"] = {name: word for name in GPR}
    packet["registers"].update(ecx=h, esp=g)
    packet["xmm"] = {name: (0 if word == 0 else 2**128 - 1) for name in XMM}
    packet["pages"][0x11000000] = bytes((i * 29 + (i >> 3)) & 255 for i in range(4096))
    before = copy.deepcopy(packet)
    result = m.apply(**packet)
    check_result(packet, result, independent(**packet))
    for name in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][name] == word
    for name in XMM[2:]:
        assert result["xmm"][name] == packet["xmm"][name]
    assert result["pages"][0x11000000] == packet["pages"][0x11000000]
    assert packet == before


def test_child_receives_exact_actual_prefix_pages_state_and_projected_flags(
    monkeypatch,
):
    packet = growth_input(
        header=0x10000FFA,
        entry=0x30000FF5,
        source=0x06002FF0,
        destination=0x06004FE7,
        entry_flags=0x8D7,
        unused_word=0xFFFFFFFF,
    )
    packet["pages"][0x11000000] = bytes((i * 31 + (i >> 4)) & 255 for i in range(4096))
    wanted = independent(**packet)
    original = m.child.apply
    supplied = []

    def checked(**kwargs):
        supplied.append(copy.deepcopy(kwargs))
        assert kwargs == wanted["child_input"]
        return original(**kwargs)

    monkeypatch.setattr(m.child, "apply", checked)
    result = m.apply(**packet)
    assert len(supplied) == 1
    assert supplied[0]["entry_flags"] == 2
    check_result(packet, result, wanted)


@pytest.mark.parametrize(
    "bit", tuple(bit for bit in range(32) if not (0xAD7 & (1 << bit)))
)
def test_each_forbidden_flag_bit_rejects_without_mutation(bit):
    packet = growth_input(entry_flags=2 | (1 << bit))
    before = copy.deepcopy(packet)
    with pytest.raises(m.Growth6To9Error):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize("flags", (0, 4, 0x200, 0x8D5, 0xFFFFFBFF, False, -1, 2**32))
def test_missing_fixedbit_arbitrary_control_words_and_typed_flags_reject(flags):
    packet = growth_input(entry_flags=flags)
    before = copy.deepcopy(packet)
    with pytest.raises(m.Growth6To9Error):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize(
    "kind",
    (
        "gpr_bool",
        "gpr_missing",
        "gpr_extra",
        "xmm_bool",
        "xmm_overflow",
        "xmm_missing",
        "pages_list",
        "page_bool",
        "page_mutable",
        "page_short",
        "missing_stack",
        "missing_error",
        "missing_feature",
        "source_bool",
        "source_zero",
        "source_wrap",
        "destination_wrap",
        "header_wrap",
        "destination_overlap",
        "destination_adjacent",
        "header_source",
        "header_destination",
        "source_stack",
        "header_global",
        "destination_error",
        "source_feature",
        "header_iat",
        "stack_low",
        "stack_high",
        "ecx_header",
        "return_zero",
        "return_bool",
        "return_data",
        "return_import",
        "return_selected_code",
        "flags_bool",
        "df",
        "caller_return",
        "header_end",
        "header_capacity",
        "feature",
        "heap",
        "iat",
        "code_page",
        "import_page",
    ),
)
def test_typed_bounds_aliases_frames_globals_and_installed_premises_reject(kind):
    packet = growth_input()
    if kind == "gpr_bool":
        packet["registers"]["eax"] = False
    elif kind == "gpr_missing":
        packet["registers"].pop("eax")
    elif kind == "gpr_extra":
        packet["registers"]["unused"] = 0
    elif kind == "xmm_bool":
        packet["xmm"]["xmm0"] = False
    elif kind == "xmm_overflow":
        packet["xmm"]["xmm7"] = 2**128
    elif kind == "xmm_missing":
        packet["xmm"].pop("xmm0")
    elif kind == "pages_list":
        packet["pages"] = list(packet["pages"].items())
    elif kind == "page_bool":
        packet["pages"][False] = bytes(4096)
    elif kind == "page_mutable":
        packet["pages"][0x06004000] = bytearray(packet["pages"][0x06004000])
    elif kind == "page_short":
        packet["pages"][0x06004000] = packet["pages"][0x06004000][:-1]
    elif kind.startswith("missing_"):
        packet["pages"].pop(
            dict(
                missing_stack=0x30000000,
                missing_error=0x06000000,
                missing_feature=0x00893000,
            )[kind]
        )
    elif kind == "source_bool":
        packet["source"] = True
    elif kind == "source_zero":
        packet["source"] = 0
    elif kind == "source_wrap":
        packet["source"] = 0xFFFFFFF0
    elif kind == "destination_wrap":
        packet["destination"] = 0xFFFFFFB8
    elif kind == "header_wrap":
        packet["object_address"] = 0xFFFFFFF8
        packet["registers"]["ecx"] = 0xFFFFFFF8
    elif kind in ("destination_overlap", "destination_adjacent"):
        packet["destination"] = packet["source"] + (
            32 if kind == "destination_overlap" else 48
        )
    elif kind in ("header_source", "header_destination", "header_global", "header_iat"):
        h = dict(
            header_source=packet["source"],
            header_destination=packet["destination"],
            header_global=0x008B7634,
            header_iat=0x007D6220,
        )[kind]
        packet["object_address"] = h
        packet["registers"]["ecx"] = h
    elif kind == "source_stack":
        packet["source"] = 0x30000100
        packet["destination"] = 0x30000200
    elif kind == "destination_error":
        packet["source"] = 0x05002800
        packet["destination"] = 0x06000080
    elif kind == "source_feature":
        packet["source"] = 0x00893080
    elif kind == "stack_low":
        packet["registers"]["esp"] = 0x30000000 + 95
    elif kind == "stack_high":
        packet["registers"]["esp"] = 0x30002000 - 7
    elif kind == "ecx_header":
        packet["registers"]["ecx"] ^= 1
    elif kind == "return_zero":
        packet["return_address"] = 0
    elif kind == "return_bool":
        packet["return_address"] = True
    elif kind == "return_data":
        packet["return_address"] = packet["source"]
    elif kind == "return_import":
        packet["return_address"] = 0x05000000
    elif kind == "return_selected_code":
        packet["return_address"] = 0x006EB680
    elif kind == "flags_bool":
        packet["entry_flags"] = False
    elif kind == "df":
        packet["entry_flags"] |= 0x400
    elif kind in ("code_page", "import_page"):
        packet["pages"][0x006EB000 if kind == "code_page" else 0x05000000] = bytes(4096)
    else:
        at = dict(
            caller_return=packet["registers"]["esp"],
            caller_request=packet["registers"]["esp"] + 4,
            header_end=packet["object_address"] + 4,
            header_capacity=packet["object_address"] + 8,
            feature=0x00893F30,
            heap=0x008B7634,
            iat=0x007D6220,
        )[kind]
        install(packet["pages"], at, bytes([blob(packet["pages"], at, 1)[0] ^ 1]))
    before = copy.deepcopy(packet)
    with pytest.raises(m.Growth6To9Error):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize(
    "kind",
    (
        "allocation_bool",
        "allocation_extra",
        "allocation_spare",
        "copy_edx32",
        "copy_df_bool",
        "copy_spare",
        "copy_ancestor",
        "free_returned_int",
        "free_result_bool",
        "free_error",
    ),
)
def test_full_child_packets_reject_bool_aliases_and_coordinated_page_corruption(
    monkeypatch, kind
):
    packet = growth_input(header=0x10000104)
    before = copy.deepcopy(packet)
    role = kind.split("_", 1)[0]
    name = "_" + role + "_packet_law"
    original = getattr(m.primitive, name)

    def corrupted(*args, **kwargs):
        result = original(*args, **kwargs)
        if kind == "allocation_bool":
            result["relation"]["metadata"] = False
        elif kind == "allocation_extra":
            result["unused"] = 0
        elif kind == "allocation_spare":
            result["payload"] = (
                bytes([result["payload"][0] ^ 1]) + result["payload"][1:]
            )
            result["events"].append(
                dict(
                    access="write", address=packet["destination"] + 48, width=4, value=0
                )
            )
        elif kind == "copy_edx32":
            result["registers"]["edx"] = 0
        elif kind == "copy_df_bool":
            result["df"] = False
        elif kind in ("copy_spare", "copy_ancestor"):
            at = (
                packet["destination"] + 48
                if kind == "copy_spare"
                else packet["registers"]["esp"] + 8
            )
            value = int.from_bytes(blob(result["pages"], at, 4), "little") ^ 1
            install(result["pages"], at, value.to_bytes(4, "little"))
            result["events"].append(
                dict(access="write", address=at, width=4, value=value)
            )
        elif kind == "free_returned_int":
            result["protocol"]["returned"] = 1
        elif kind == "free_result_bool":
            result["protocol"]["result"] = True
        else:
            result["error"] = bytes([result["error"][0] ^ 1]) + result["error"][1:]
        return result

    monkeypatch.setattr(m.primitive, name, corrupted)
    with pytest.raises(m.Growth6To9Error, match=role + " primitive"):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize("kind", ("extra", "missing"))
def test_apply_keyword_schema_is_closed(kind):
    packet = growth_input()
    if kind == "extra":
        packet["unused"] = 0
    else:
        packet.pop("entry_flags")
    with pytest.raises(TypeError):
        m.apply(**packet)


def test_output_packets_detach_from_actual_installed_inputs():
    packet = growth_input(header=0x10000104, entry_flags=0x256)
    result = m.apply(**packet)
    before = copy.deepcopy(result)
    packet["registers"]["ebx"] ^= 1
    packet["xmm"]["xmm7"] ^= 1
    packet["pages"].clear()
    assert result == before


@pytest.mark.parametrize(
    "kind",
    (
        "gpr_bool",
        "df_bool",
        "xmm_bool",
        "flags_bool",
        "extra",
        "missing",
        "geometry_bool",
        "allocation_extra",
        "copy_tail",
        "free_returned_int",
        "raw_flags_projection",
        "boundary_disagreement",
        "spare_and_event",
        "ancestor_and_event",
        "old_and_copy_snapshot",
        "header_and_event",
        "event_order",
        "trace_extra",
    ),
)
def test_complete18_child_join_rejects_typed_and_coordinated_corruption(
    monkeypatch, kind
):
    original = m.child.apply

    def corrupted(**kwargs):
        child = original(**kwargs)
        if kind == "gpr_bool":
            child["registers"]["ecx"] = True
        elif kind == "xmm_bool":
            child["xmm"]["xmm7"] = False
        elif kind == "df_bool":
            child["df"] = False
        elif kind == "flags_bool":
            child["flags"] = False
        elif kind == "extra":
            child["unused"] = 0
        elif kind == "missing":
            child.pop("allocation_request")
        elif kind == "geometry_bool":
            child["geometry"]["old_size"] = True
        elif kind == "allocation_extra":
            child["allocation_packet"]["unused"] = 0
        elif kind == "copy_tail":
            child["copy_packet"]["registers"]["edx"] = 0
        elif kind == "free_returned_int":
            child["free_packet"]["protocol"]["returned"] = 1
        elif kind == "raw_flags_projection":
            child["allocation_entry"]["flags"] = 0
        elif kind == "boundary_disagreement":
            child["copy_entry"]["registers"]["esi"] ^= 1
        elif kind in (
            "spare_and_event",
            "ancestor_and_event",
            "old_and_copy_snapshot",
            "header_and_event",
        ):
            at = dict(
                spare_and_event=kwargs["destination"] + 48,
                ancestor_and_event=kwargs["registers"]["esp"] + 28,
                old_and_copy_snapshot=kwargs["source"],
                header_and_event=kwargs["object_address"],
            )[kind]
            value = int.from_bytes(blob(child["pages"], at, 4), "little") ^ 1
            install(child["pages"], at, value.to_bytes(4, "little"))
            child["events"].append(
                dict(access="write", address=at, width=4, value=value)
            )
            if kind == "old_and_copy_snapshot":
                child["copy_packet"]["source_snapshot"] = (
                    value.to_bytes(4, "little")
                    + child["copy_packet"]["source_snapshot"][4:]
                )
        elif kind == "event_order":
            child["events"][-8], child["events"][-7] = (
                child["events"][-7],
                child["events"][-8],
            )
        else:
            child["trace_rvas"].append("0x002eb674")
        return child

    monkeypatch.setattr(m.child, "apply", corrupted)
    packet = growth_input(unused_word=0xFFFFFFFF)
    before = copy.deepcopy(packet)
    with pytest.raises(m.Growth6To9Error, match="resize primitive"):
        m.apply(**packet)
    assert packet == before


@pytest.mark.parametrize(
    "kind",
    (
        "growth_return",
        "growth_failure_return",
        "import_return_padding",
        "header_stack",
        "source_global",
        "destination_iat",
        "missing_heap",
        "missing_iat",
        "missing_header_page",
        "missing_source_page",
        "missing_spare_page",
        "header_bool",
        "destination_bool",
        "return_negative",
        "return_overflow",
        "gpr_negative",
        "gpr_overflow",
        "xmm_negative",
        "page_unaligned",
        "page_wrap",
    ),
)
def test_growth_specific_return_ranges_full_extent_pages_and_typed_addresses_reject(
    kind,
):
    packet = growth_input(header=0x10000104)
    if kind == "growth_return":
        packet["return_address"] = 0x006EB66E
    elif kind == "growth_failure_return":
        packet["return_address"] = 0x006EB674
    elif kind == "import_return_padding":
        packet["return_address"] = 0x05000100
    elif kind == "header_stack":
        packet["object_address"] = 0x30000100
        packet["registers"]["ecx"] = 0x30000100
    elif kind == "source_global":
        packet["source"] = 0x008B7600
    elif kind == "destination_iat":
        packet["source"] = 0x00402000
        packet["destination"] = 0x007D6200
    elif kind in ("header_bool", "destination_bool"):
        packet["object_address" if kind == "header_bool" else "destination"] = True
    elif kind in ("return_negative", "return_overflow"):
        packet["return_address"] = -1 if kind == "return_negative" else 2**32
    elif kind in ("gpr_negative", "gpr_overflow"):
        packet["registers"]["ebp"] = -1 if kind == "gpr_negative" else 2**32
    elif kind == "xmm_negative":
        packet["xmm"]["xmm7"] = -1
    elif kind in ("page_unaligned", "page_wrap"):
        packet["pages"][0x11000001 if kind == "page_unaligned" else 2**32] = bytes(4096)
    elif kind == "missing_spare_page":
        packet = growth_input(destination=0x06004FD0)
        packet["pages"].pop(0x06005000)
    else:
        page = dict(
            missing_heap=0x008B7000,
            missing_iat=0x007D6000,
            missing_header_page=0x10000000,
            missing_source_page=0x06002000,
        )[kind]
        packet["pages"].pop(page)
    before = copy.deepcopy(packet)
    with pytest.raises(m.Growth6To9Error):
        m.apply(**packet)
    assert packet == before


def test_prior_source_pins_and_new_analysis_kind_remain_exact():
    assert m.SOURCE_PINS == c.SOURCE_PINS
    assert len(m.SOURCE_PINS) == 11
    assert m.SOURCE_PINS["growth"] == (
        "pe_native_lua_vector_growth_semantics",
        "6e442065281f9d7f1853dbb2d2dd91b3d5645cae16a5497db772b7a66f28ec69",
    )
    assert m.SOURCE_PINS["resize6_to9"] == (
        "pe_native_simd_vector_resize6_to9_conformance",
        "009f36e1b254058ec21f7af157f6e86ebfa18039abe24fce1690f9df97bc2949",
    )
    assert m.ANALYSIS_KIND == "pe_native_simd_vector_growth6_to9_semantics"
    assert len(GROWTH_PREFIX) == 34 and len(TRACE) == 235 and len(set(TRACE)) == 217
