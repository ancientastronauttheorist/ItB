"""Independent actual-page 08ABA0 four-DWORD clone law.

Expectations follow decoded operands. Production apply supplies only actuals.
"""

from __future__ import annotations

import ast
import copy
import inspect

import pytest

from src.observatory import native_movement_path_scalar_clone2_semantics as c

GPRS = ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
XMMS = tuple(f"xmm{i}" for i in range(8))
TRACE = tuple(int(w, 16) for w in """
8aba0 8aba1 8aba3 8aba6 8aba7 8aba9 8abab 8abad
8abb0 8abb2 8abb4 8abb6 8abb8 8abbb 8abbe 8abc1 8abc4 8abc6
8abb0 8abb2 8abb4 8abb6 8abb8 8abbb 8abbe 8abc1 8abc4 8abc6
8abc8 8abc9 8abca
""".split())
KEYS = {
    "pages",
    "registers",
    "xmm",
    "flags",
    "flag_mask",
    "df",
    "endpoint",
    "source_snapshot",
    "events",
    "trace_rvas",
}
RANGES = (
    (0x48ABA0, 0x48ABCB),
    (0x49A8E0, 0x49A92F),
    (0x49AC40, 0x49AC97),
    (0x48A920, 0x48A97B),
    (0x7574DB, 0x75750E),
    (0x779F52, 0x779F5D),
    (0x78942B, 0x789479),
)


def read_bytes(pages, address, width):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(width)
    )


def store(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        page = (address + i) & ~4095
        data = bytearray(pages[page])
        data[(address + i) & 4095] = byte
        pages[page] = bytes(data)


def assert_strict_packet(actual, wanted):
    assert type(actual) is type(wanted)
    if type(wanted) is dict:
        assert set(actual) == set(wanted)
        assert all(any(type(k) is type(j) and k == j for j in wanted) for k in actual)
        for key in wanted:
            assert_strict_packet(actual[key], wanted[key])
    elif type(wanted) in (list, tuple):
        assert len(actual) == len(wanted)
        for a, b in zip(actual, wanted):
            assert_strict_packet(a, b)
    else:
        assert actual == wanted


def inputs(
    *,
    frame=0x30001000,
    source=0x10000100,
    destination=0x10000300,
    profile=0,
    flags=0x246,
    return_address=0x49A921,
):
    spans = (
        (frame - 8, frame + 20),
        (source, source + 16),
        (destination, destination + 16),
    )
    bases = {
        page
        for start, end in spans
        for page in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096)
    }
    bases.add(0x12340000)
    pages = {
        page: bytes((i * 37 + j * 23 + profile * 79) & 255 for j in range(4096))
        for i, page in enumerate(sorted(bases))
    }
    regs = {
        name: (0x13579BDF + i * 0x1234567 + profile * 0x76543) & 0xFFFFFFFF
        for i, name in enumerate(GPRS)
    }
    regs.update(ecx=source, edx=source + 16, esp=frame)
    xmm = {
        name: int.from_bytes(
            bytes((i * 29 + j * 41 + profile * 67) & 255 for j in range(16)), "little"
        )
        for i, name in enumerate(XMMS)
    }
    words = (0xD15C0016, 0xFFFFFFFF, 0, 0x8765DD16)
    for i, word in enumerate(words):
        store(pages, source + i * 4, word ^ ((profile * 0x3456789) & 0xFFFFFFFF))
    for i, word in enumerate(
        (return_address, destination, 0xFFFFFFFF, 0x12345678, 0x76543210)
    ):
        store(pages, frame + i * 4, word)
    return dict(
        pages=pages,
        registers=regs,
        xmm=xmm,
        source=source,
        destination=destination,
        return_address=return_address,
        entry_flags=flags,
    )


def independent(arg):
    """Two literal loop iterations; memory replay is separate from the event list."""
    p = arg["pages"]
    r = arg["registers"]
    frame, source, dest = r["esp"], arg["source"], arg["destination"]
    snapshot = read_bytes(p, source, 16)
    words = [int.from_bytes(snapshot[i : i + 4], "little") for i in (0, 4, 8, 12)]
    rows = [
        ("write", frame - 4, r["ebp"]),
        ("read", frame + 4, dest),
        ("write", frame - 8, r["esi"]),
    ]
    for offset, word in zip((0, 4, 8, 12), words):
        rows.extend((("read", source + offset, word), ("write", dest + offset, word)))
    rows.extend(
        (
            ("read", frame - 8, r["esi"]),
            ("read", frame - 4, r["ebp"]),
            ("read", frame, arg["return_address"]),
        )
    )
    pages = dict(p)
    store(pages, frame - 4, r["ebp"])
    store(pages, frame - 8, r["esi"])
    for offset, word in zip((0, 4, 8, 12), words):
        store(pages, dest + offset, word)
    return dict(
        pages=pages,
        registers=dict(r, eax=dest + 16, ecx=words[3], esp=frame + 4),
        xmm=dict(arg["xmm"]),
        flags=0x44,
        flag_mask=0x8D5,
        df=0,
        endpoint=arg["return_address"],
        source_snapshot=snapshot,
        events=[
            dict(access=op, address=at, width=4, value=value) for op, at, value in rows
        ],
        trace_rvas=[f"0x{pc:08x}" for pc in TRACE],
    )


def check_packet(actual, arg):
    assert set(actual) == KEYS
    assert_strict_packet(actual, independent(arg))
    assert len(actual["events"]) == 14
    assert len(actual["trace_rvas"]) == 31
    assert read_bytes(actual["pages"], arg["source"], 16) == actual["source_snapshot"]
    assert (
        read_bytes(actual["pages"], arg["destination"], 16) == actual["source_snapshot"]
    )
    frame = arg["registers"]["esp"]
    assert read_bytes(actual["pages"], frame, 20) == read_bytes(arg["pages"], frame, 20)
    writes = [e for e in actual["events"] if e["access"] == "write"]
    assert [e["address"] for e in writes] == [frame - 4, frame - 8] + [
        arg["destination"] + i for i in (0, 4, 8, 12)
    ]
    assert [
        e["address"]
        for e in actual["events"]
        if e["access"] == "read" and arg["source"] <= e["address"] < arg["source"] + 16
    ] == [arg["source"] + offset for offset in (0, 4, 8, 12)]


@pytest.mark.parametrize("alignment", range(16))
@pytest.mark.parametrize("profile", range(3))
@pytest.mark.parametrize("reverse", (False, True))
def test_all_alignments_profiles_and_source_order(alignment, profile, reverse):
    s, d = (0x10000100, 0x10000300) if not reverse else (0x10000300, 0x10000100)
    arg = inputs(
        frame=0x30001000 + alignment,
        source=s + alignment,
        destination=d + alignment,
        profile=profile,
    )
    check_packet(c.apply(**arg), arg)


@pytest.mark.parametrize("bits", range(128))
def test_every_ordinary_flags_word(bits):
    allowed = (1, 4, 0x10, 0x40, 0x80, 0x200, 0x800)
    flags = 2 | sum(bit for i, bit in enumerate(allowed) if bits >> i & 1)
    arg = inputs(flags=flags)
    check_packet(c.apply(**arg), arg)


@pytest.mark.parametrize(
    "frame,source,dest",
    [
        (0x30001003, 0x10000FFB, 0x10002FF9),
        (0x30000FFB, 0x10000100, 0x10000300),
        (0x30001000, 0x7FFFFFF8, 0x90000FF8),
        (0x30001000, 1, 0x10000300),
        (0x30001000, 0xFFFFFFEF, 0x10000300),
        (0x30001000, 0x10000100, 0xFFFFFFEF),
        (8, 0x10000100, 0x10000300),
        (0xFFFFFFEB, 0x10000100, 0x10000300),
        (0x30001000, 0x10000100, 0x10000110),
        (0x30001000, 0x10000110, 0x10000100),
        (0x10000108, 0x100000F0, 0x1000011C),
    ],
)
def test_crossings_conservative_limits_and_adjacent_spans(frame, source, dest):
    arg = inputs(frame=frame, source=source, destination=dest)
    check_packet(c.apply(**arg), arg)


@pytest.mark.parametrize("word", (0, 0xFFFFFFFF))
def test_arbitrary_nonvolatile_and_xmm_values(word):
    arg = inputs()
    for name in ("eax", "ebx", "esi", "edi", "ebp"):
        arg["registers"][name] = word
    arg["xmm"] = {name: (0 if word == 0 else 2**128 - 1) for name in XMMS}
    check_packet(c.apply(**arg), arg)


def test_caller_unused_words_do_not_become_reads():
    arg = inputs()
    frame = arg["registers"]["esp"]
    for offset in (8, 12, 16):
        store(arg["pages"], frame + offset, 0xFFFFFFFF - offset)
    actual = c.apply(**arg)
    check_packet(actual, arg)
    assert not any(frame + 8 <= e["address"] < frame + 20 for e in actual["events"])


def test_inputs_unchanged_and_results_detached():
    arg = inputs()
    before = copy.deepcopy(arg)
    actual = c.apply(**arg)
    check_packet(actual, arg)
    assert_strict_packet(arg, before)
    actual["registers"]["ebx"] ^= 1
    actual["xmm"]["xmm0"] ^= 1
    actual["pages"].clear()
    actual["events"][0]["value"] ^= 1
    actual["trace_rvas"].clear()
    assert_strict_packet(arg, before)
    check_packet(c.apply(**arg), arg)


class IntAlias(int):
    pass


class StrAlias(str):
    pass


@pytest.mark.parametrize(
    "field", ("source", "destination", "return_address", "entry_flags")
)
@pytest.mark.parametrize("value", (True, 1.0, IntAlias(2), -1, 2**32, None))
def test_scalar_argument_strict_types(field, value):
    arg = inputs()
    arg[field] = value
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize("field", ("registers", "xmm"))
@pytest.mark.parametrize(
    "kind",
    (
        "missing",
        "extra",
        "bool",
        "float",
        "intalias",
        "stralias",
        "negative",
        "overflow",
        "list",
    ),
)
def test_register_schema(field, kind):
    arg = inputs()
    packet = arg[field]
    name = next(iter(packet))
    if kind == "missing":
        packet.pop(name)
    elif kind == "extra":
        packet["extra"] = 0
    elif kind == "bool":
        packet[name] = False
    elif kind == "float":
        packet[name] = 0.0
    elif kind == "intalias":
        packet[name] = IntAlias(packet[name])
    elif kind == "stralias":
        packet[StrAlias(name)] = packet.pop(name)
    elif kind == "negative":
        packet[name] = -1
    elif kind == "overflow":
        packet[name] = 2 ** (128 if field == "xmm" else 32)
    else:
        arg[field] = list(packet.items())
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize(
    "kind",
    (
        "empty",
        "list",
        "badkey",
        "floatkey",
        "aliaskey",
        "badlen",
        "bytearray",
        "missing",
        "codepage",
    ),
)
def test_full_page_schema(kind):
    arg = inputs()
    pages = arg["pages"]
    page = next(iter(pages))
    if kind == "empty":
        arg["pages"] = {}
    elif kind == "list":
        arg["pages"] = list(pages.items())
    elif kind == "badkey":
        pages[page + 1] = pages.pop(page)
    elif kind == "floatkey":
        pages[float(page)] = pages.pop(page)
    elif kind == "aliaskey":
        pages[IntAlias(page)] = pages.pop(page)
    elif kind == "badlen":
        pages[page] = pages[page][:-1]
    elif kind == "bytearray":
        pages[page] = bytearray(pages[page])
    elif kind == "missing":
        pages.pop(arg["source"] & ~4095)
    else:
        pages[0x48A000] = bytes(4096)
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize("bit", [i for i in range(32) if (1 << i) & ~0xAD7])
def test_each_forbidden_flag(bit):
    arg = inputs(flags=2 | (1 << bit))
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize("flags", (0, 4, 0xAD5))
def test_required_fixed_flag_bit(flags):
    arg = inputs(flags=flags)
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize(
    "kind",
    (
        "ecx",
        "edx",
        "returnword",
        "destinationword",
        "sourcezero",
        "destzero",
        "sourcewrap",
        "destwrap",
        "frameunder",
        "framewrap",
        "buffersoverlap",
        "sourcestack",
        "deststack",
    ),
)
def test_installed_entry_and_geometry_rejections(kind):
    arg = inputs()
    frame = arg["registers"]["esp"]
    if kind in ("ecx", "edx"):
        arg["registers"][kind] ^= 1
    elif kind == "returnword":
        store(arg["pages"], frame, arg["return_address"] ^ 1)
    elif kind == "destinationword":
        store(arg["pages"], frame + 4, arg["destination"] ^ 1)
    elif kind == "sourcezero":
        arg["source"] = 0
    elif kind == "destzero":
        arg["destination"] = 0
    elif kind == "sourcewrap":
        arg["source"] = 0xFFFFFFF0
    elif kind == "destwrap":
        arg["destination"] = 0xFFFFFFF0
    elif kind == "frameunder":
        arg["registers"]["esp"] = 7
    elif kind == "framewrap":
        arg["registers"]["esp"] = 0xFFFFFFEC
    elif kind == "buffersoverlap":
        arg["destination"] = arg["source"] + 15
    elif kind == "sourcestack":
        arg["source"] = frame - 8
    else:
        arg["destination"] = frame + 19
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize(
    "endpoint",
    (
        0,
        0x48ABA0,
        0x48ABCA,
        0x30000FF8,
        0x30001013,
        0x10000100,
        0x1000010F,
        0x10000300,
        0x1000030F,
    ),
)
def test_return_rejects_zero_own_body_and_touched_spans(endpoint):
    arg = inputs(return_address=endpoint)
    with pytest.raises(c.ScalarCloneError):
        c.apply(**arg)


@pytest.mark.parametrize(
    "endpoint", (0x49A921, 0x48ABCB, 0x5000000, 0x10000110, 0x30001014, 0xFFFFFFFF)
)
def test_logical_return_endpoints_and_parent_continuation(endpoint):
    arg = inputs(return_address=endpoint)
    check_packet(c.apply(**arg), arg)


@pytest.mark.parametrize("start,end", RANGES)
def test_every_selected_body_page_excluded_even_if_untouched(start, end):
    for page in range(start & ~4095, ((end - 1) & ~4095) + 1, 4096):
        arg = inputs()
        arg["pages"][page] = bytes(4096)
        with pytest.raises(c.ScalarCloneError):
            c.apply(**arg)


def test_actual_page_interface_has_no_fixture_or_delegated_native():
    signature = inspect.signature(c.apply)
    assert tuple(signature.parameters) == (
        "pages",
        "registers",
        "xmm",
        "source",
        "destination",
        "return_address",
        "entry_flags",
    )
    assert all(
        p.kind is inspect.Parameter.KEYWORD_ONLY
        and p.default is inspect.Parameter.empty
        for p in signature.parameters.values()
    )
    tree = ast.parse(inspect.getsource(c))
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert all(
        isinstance(node, ast.ImportFrom) and node.module == "__future__"
        for node in imports
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in ("_fixture", "Uc", "eval", "exec", "__import__")
        for node in ast.walk(tree)
    )
