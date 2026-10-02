"""Exact retained factory source7/destination8, size5/cap6 spare class adapter.

This consumes actual retained pages and preserves all eight supplied XMM words.
It constructs no fixture and makes no native, VM or heap ownership claim.
"""

from __future__ import annotations

import copy

from src.observatory import native_lua_class_factory_simd_adapter as fifth
from src.observatory import native_lua_class_spare_return_conformance as spare

XMM_SPARE_FACTORY = True
ConformanceError, _require = spare.ConformanceError, spare._require
prefix = spare.prefix
VECTOR_KEYS = fifth.VECTOR_KEYS | {"buffer_address", "spare_records"}
FIXTURE_KEYS = fifth.child.FIXTURE_KEYS - {
    "old_begin",
    "old_base",
    "new_base",
    "new_page_count",
}
SOURCE_KEYS = set(fifth.SOURCE_KEYS)
REGISTERS = {"eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"}
XMM = {"xmm" + str(index) for index in range(8)}
SPARE_RESULT_KEYS = {
    "registers",
    "pages",
    "events",
    "flags",
    "endpoint",
    "insertions",
    "heap_nodes",
    "destination_addresses",
    "destination_key_pointers",
}
_model_pages = spare._model_pages


def _fixture(*args, **kwargs):
    raise ConformanceError("spare factory requires an actual retained capture")


def _word(value):
    return type(value) is int and 0 <= value <= 0xFFFFFFFF


def _same_packet(actual, expected):
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _same_packet(actual[key], value) for key, value in expected.items()
        )
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same_packet(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def _blob(pages, address, size):
    _require(
        _word(address)
        and type(size) is int
        and size >= 0
        and address + size <= 2**32
        and all((address + offset) & ~4095 in pages for offset in range(size)),
        "factory spare extent unmapped or wraps",
    )
    return bytes(
        pages[(address + offset) & ~4095][(address + offset) & 4095]
        for offset in range(size)
    )


def _raw(pages, address, width=4):
    return int.from_bytes(_blob(pages, address, width), "little")


def _event_law(vector, fixture, copies, events, *, inherited_events):
    """Independent writes and append/return tail; tree-prefix reads are inherited."""
    entry, begin = fixture["stack"], fixture["vector_begin"]
    addresses = fixture["destination_addresses"]
    frame, argument, end = entry - 4, entry + 28, begin + 40

    def event(access, address, value):
        return dict(access=access, address=address, width=4, value=value)

    payload_writes = [
        event("write", addresses[row["destination"]] + 20, row["payload"])
        for row in copies
    ]
    append_writes = [
        event("write", end, 0),
        event("write", end + 4, prefix.SOURCE_OBJECT),
        event("write", prefix.RECEIVER + 8, begin + 48),
    ]
    nonstack_writes = [
        row
        for row in events
        if row["access"] == "write" and not entry - 92 <= row["address"] < entry
    ]
    _require(
        _same_packet(nonstack_writes, payload_writes + append_writes),
        "factory spare ordered nonstack writes differ",
    )
    tail = [
        event("read", frame - 12, prefix.RECEIVER),
        event("read", prefix.RECEIVER + 8, end),
    ]
    # The actual factory argument C+28 is above DATA+0x2800+a+40, so this
    # conditional read is absent in the exact admitted factory domain.
    if argument < end:
        tail.append(event("read", prefix.RECEIVER + 4, begin))
    tail.extend(
        [
            event("read", prefix.RECEIVER + 12, begin + 48),
            event("read", prefix.RECEIVER + 8, end),
            event("read", argument, 0),
            append_writes[0],
            event("read", argument + 4, prefix.SOURCE_OBJECT),
            append_writes[1],
            event("read", prefix.RECEIVER + 8, end),
            append_writes[2],
            event("read", frame - 4, vector["cookie"] ^ frame),
            event("read", frame - 32, fixture["registers"]["edi"]),
            event("read", frame - 28, fixture["registers"]["esi"]),
            event("read", frame - 24, fixture["registers"]["ebx"]),
            event("write", frame - 24, spare.returned.CONTINUATION),
            event("read", spare.returned.COOKIE, vector["cookie"]),
            event("read", frame - 24, spare.returned.CONTINUATION),
            event("read", frame, fixture["registers"]["ebp"]),
            event("read", frame + 4, fixture["return_address"]),
        ]
    )
    _require(
        _same_packet(events, inherited_events + tail),
        "factory spare append and return event tail differs",
    )


def _physical_tree(pages, state, addresses, head, strings):
    nodes = state["tree"]["nodes"]
    at = lambda identity: head if identity is None else addresses[identity]
    order = sorted(range(len(nodes)), key=lambda identity: nodes[identity]["key"])
    _require(
        [_raw(pages, head + offset) for offset in (0, 4, 8)]
        == [at(order[0]), at(state["tree"]["root"]), at(order[-1])]
        and _raw(pages, head + 13, 1) == 1,
        "factory spare sentinel links differ",
    )
    for identity, (address, node) in enumerate(zip(addresses, nodes)):
        pointer = _raw(pages, address + 16)
        value = f"{node['key']:08x}".encode() + b"\0"
        _require(
            [_raw(pages, address + offset) for offset in (0, 4, 8)]
            == [at(node[key]) for key in ("left", "parent", "right")]
            and _raw(pages, address + 12, 1) == node["color"]
            and _raw(pages, address + 13, 1) == 0
            and _raw(pages, address + 20) == state["payloads"][identity]
            and pointer in strings
            and strings[pointer] == value
            and _blob(pages, pointer, len(value)) == value,
            "factory spare node or key bytes differ",
        )


def _checked(vector, fixture):
    _require(
        type(vector) is dict and set(vector) == VECTOR_KEYS,
        "factory spare vector schema differs",
    )
    _require(
        type(fixture) is dict and set(fixture) == FIXTURE_KEYS,
        "factory spare class fixture schema differs",
    )
    scalar = VECTOR_KEYS - {
        "profile",
        "source_keys",
        "destination_keys",
        "marker_words",
        "source_refs",
        "destination_refs",
        "transfers",
    }
    _require(
        all(_word(vector[key]) for key in scalar)
        and type(vector["profile"]) is str
        and vector["profile"] == "all_existing"
        and vector["old_size"] == 5
        and vector["spare_records"] == 1
        and vector["vector_alignment"] in (0, 7, 31)
        and vector["old_alignment"] == vector["vector_alignment"]
        and vector["node_alignment"] in (0, 7, 31)
        and vector["frame_alignment"] in (0, 15)
        and vector["nil_flag"] == 1
        and vector["source_word"] == vector["destination_word"],
        "factory spare vector geometry differs",
    )
    for key in ("marker_words", "source_refs", "destination_refs"):
        _require(
            type(vector[key]) is list
            and len(vector[key]) == 2
            and all(_word(value) for value in vector[key]),
            "factory spare Lua word schema differs",
        )
    _require(
        type(vector["transfers"]) is list
        and len(vector["transfers"]) == 2
        and all(
            type(recipe) is list
            and len(recipe) <= 3
            and all(
                type(kind) is str and kind in ("init", "finalize", "other")
                for kind in recipe
            )
            for recipe in vector["transfers"]
        ),
        "factory spare Lua recipe differs",
    )
    try:
        source_checked = prefix.model.validate_state(fixture["source_state"])
        destination_checked = prefix.model.validate_state(fixture["destination_state"])
    except (prefix.model.TransferError, prefix.model.balancing.BalancingError) as exc:
        raise ConformanceError(str(exc)) from exc
    source = fixture["source_state"]
    destination = fixture["destination_state"]
    source_keys = [node["key"] for node in source["tree"]["nodes"]]
    destination_keys = [node["key"] for node in destination["tree"]["nodes"]]
    _require(
        source_checked["nodes"] == 7
        and destination_checked["nodes"] == 8
        and set(source_keys) == SOURCE_KEYS
        and set(destination_keys) == SOURCE_KEYS | {16}
        and type(vector["source_keys"]) is list
        and type(vector["destination_keys"]) is list
        and all(
            _word(key) for key in vector["source_keys"] + vector["destination_keys"]
        )
        and vector["source_keys"] == source_keys
        and vector["destination_keys"] == destination_keys,
        "factory spare existing-key domain differs",
    )
    for key in (
        "stack",
        "return_address",
        "vector_begin",
        "vector_end",
        "vector_capacity",
        "old_size",
        "node",
        "query_argument",
        "parent",
        "selector",
    ):
        _require(_word(fixture[key]), "factory spare fixture word differs")
    _require(
        type(fixture["registers"]) is dict
        and set(fixture["registers"]) == REGISTERS
        and all(_word(value) for value in fixture["registers"].values())
        and type(fixture["xmm"]) is dict
        and set(fixture["xmm"]) == XMM
        and all(
            type(value) is int and 0 <= value < 2**128
            for value in fixture["xmm"].values()
        ),
        "factory spare register schema differs",
    )
    pages = fixture["pages"]
    _require(
        type(pages) is dict
        and pages
        and all(
            _word(page)
            and page % 4096 == 0
            and page <= 2**32 - 4096
            and type(payload) is bytes
            and len(payload) == 4096
            for page, payload in pages.items()
        ),
        "factory spare page schema differs",
    )
    for key, count in (("source_addresses", 7), ("destination_addresses", 8)):
        _require(
            type(fixture[key]) is list
            and len(fixture[key]) == count
            and all(_word(address) and address != 0 for address in fixture[key])
            and len(set(fixture[key])) == count,
            "factory spare physical identity mapping differs",
        )
    _require(
        type(fixture["strings"]) is dict
        and all(
            _word(pointer)
            and pointer != 0
            and type(value) is bytes
            and len(value) == 9
            and value[-1:] == b"\0"
            and _blob(pages, pointer, len(value)) == value
            for pointer, value in fixture["strings"].items()
        ),
        "factory spare retained string schema differs",
    )
    a, entry = vector["vector_alignment"], fixture["stack"]
    begin = prefix.construction.DATA + 0x2800 + a
    _require(
        vector["buffer_address"] == fixture["vector_begin"] == begin
        and fixture["old_size"] == 5
        and fixture["vector_end"] == begin + 40
        and fixture["vector_capacity"] == begin + 48
        and entry == prefix.construction.STACK + 0x1000 + vector["frame_alignment"]
        and fixture["return_address"] == spare.BASE + 0x2EC1BD
        and fixture["registers"]["esp"] == entry
        and fixture["registers"]["ecx"] == prefix.RECEIVER
        and fixture["registers"]["eax"] == entry + 28
        and fixture["registers"]["esi"] == prefix.RECEIVER
        and fixture["registers"]["edi"] == prefix.SOURCE_OBJECT
        and fixture["registers"]["ebp"] == entry + 44
        and fixture["registers"]["ebx"] != 0,
        "factory spare class pointer geometry differs",
    )
    argument = prefix._checked_argument(fixture)
    _require(
        argument == entry + 28
        and _blob(pages, argument, 8)
        == bytes(4) + prefix.SOURCE_OBJECT.to_bytes(4, "little")
        and _blob(pages, begin, 40) == _blob(pages, argument, 8) * 5
        and [_raw(pages, prefix.RECEIVER + offset) for offset in (4, 8, 12)]
        == [begin, begin + 40, begin + 48]
        and _raw(pages, prefix.RECEIVER + 52) == prefix.leaf.HEAD
        and _raw(pages, prefix.RECEIVER + 56) == 8
        and _raw(pages, prefix.SOURCE_OBJECT + 52) == prefix.SOURCE_HEAD
        and _raw(pages, 0) == vector["previous_seh"]
        and _raw(pages, spare.returned.COOKIE) == vector["cookie"]
        and _raw(pages, prefix.SOURCE_OBJECT) == vector["source_word"]
        and _raw(pages, prefix.RECEIVER) == vector["destination_word"]
        and [_raw(pages, prefix.SOURCE_OBJECT + offset) for offset in (32, 40)]
        == vector["source_refs"]
        and [_raw(pages, prefix.RECEIVER + offset) for offset in (32, 40)]
        == vector["destination_refs"],
        "factory spare physical words differ",
    )
    source_addresses, destination_addresses = (
        fixture["source_addresses"],
        fixture["destination_addresses"],
    )
    spans = [
        (prefix.RECEIVER, 72),
        (prefix.SOURCE_OBJECT, 72),
        (prefix.leaf.HEAD, 24),
        (prefix.SOURCE_HEAD, 24),
        (begin, 48),
        (entry - 92, 148),  # Sixth T=entry+48: complete [T-140,T+8) callback.
    ] + [(address, 24) for address in source_addresses + destination_addresses]
    for offset, size in ((0x2000, 8), (0x1000, 16), (0x800, 24), (0x3800, 32)):
        pointer = prefix.construction.DATA + offset + a
        _require(
            _blob(pages, pointer, size) == _blob(pages, argument, 8) * (size // 8),
            "factory spare retained prior vector records differ",
        )
        spans.append((pointer, size))
    spans += [(pointer, len(value)) for pointer, value in fixture["strings"].items()]
    for index, (start, size) in enumerate(spans):
        _blob(pages, start, size)
        for other, other_size in spans[index + 1 :]:
            _require(
                start + size <= other or other + other_size <= start,
                "factory spare protected extents overlap",
            )
    _physical_tree(
        pages, source, source_addresses, prefix.SOURCE_HEAD, fixture["strings"]
    )
    _physical_tree(
        pages, destination, destination_addresses, prefix.leaf.HEAD, fixture["strings"]
    )
    final = copy.deepcopy(destination)
    copies = []
    destination_ids = {
        node["key"]: index for index, node in enumerate(destination["tree"]["nodes"])
    }
    source_ids = {
        node["key"]: index for index, node in enumerate(source["tree"]["nodes"])
    }
    for key in sorted(SOURCE_KEYS):
        source_id, destination_id = source_ids[key], destination_ids[key]
        payload = source["payloads"][source_id]
        final["payloads"][destination_id] = payload
        copies.append(
            dict(
                source=source_id,
                destination=destination_id,
                key=key,
                inserted=False,
                payload=payload,
            )
        )
    _require(
        _same_packet(fixture["transfer"], dict(destination=final, copies=copies)),
        "factory spare independent transfer differs",
    )
    return argument, final, copies


def _expected(vector, fixture):
    argument, final_state, copies = _checked(vector, fixture)
    result = spare._expected(vector, fixture)
    _require(
        type(result) is dict and set(result) == SPARE_RESULT_KEYS,
        "factory spare class result schema differs",
    )
    entry, begin = fixture["stack"], fixture["vector_begin"]
    pages = fixture["pages"]
    final_pages = result["pages"]
    addresses = fixture["destination_addresses"]
    wanted_insertions = [
        dict(
            source=row["source"],
            key=row["key"],
            destination_address=addresses[row["destination"]],
            inserted=False,
            mode="existing",
            payload=row["payload"],
            heap_node=None,
        )
        for row in copies
    ]
    wanted_registers = dict(
        fixture["registers"],
        eax=prefix.SOURCE_OBJECT,
        ecx=vector["cookie"],
        edx=entry - 12,
        esp=entry + 8,
    )
    _require(
        _same_packet(result["heap_nodes"], [])
        and _same_packet(result["insertions"], wanted_insertions)
        and _same_packet(result["destination_addresses"], addresses)
        and _same_packet(
            result["destination_key_pointers"],
            [_raw(pages, address + 16) for address in addresses],
        )
        and _same_packet(result["registers"], wanted_registers)
        and type(result["flags"]) is int
        and result["flags"] == 0x44
        and type(result["endpoint"]) is int
        and result["endpoint"] == fixture["return_address"],
        "factory spare class return or allocation differs",
    )
    writes = {(addresses[row["destination"]] + 20, 4) for row in copies}
    writes |= {(begin + 40, 4), (begin + 44, 4), (prefix.RECEIVER + 8, 4)}
    _require(
        type(result["events"]) is list
        and all(
            type(event) is dict
            and set(event) == {"access", "address", "width", "value"}
            and type(event["access"]) is str
            and event["access"] in ("read", "write")
            and _word(event["address"])
            and type(event["width"]) is int
            and event["width"] in (1, 4)
            and type(event["value"]) is int
            and 0 <= event["value"] < 2 ** (8 * event["width"])
            and (
                event["access"] == "read"
                or (event["address"], event["width"]) in writes
                or entry - 92
                <= event["address"]
                < event["address"] + event["width"]
                <= entry
            )
            for event in result["events"]
        ),
        "factory spare memory event schema or write footprint differs",
    )
    inherited = prefix._expected(vector, fixture)
    _event_law(
        vector, fixture, copies, result["events"], inherited_events=inherited["events"]
    )
    _require(
        type(final_pages) is dict
        and set(final_pages) == set(pages)
        and all(
            type(payload) is bytes and len(payload) == 4096
            for payload in final_pages.values()
        )
        and final_pages == spare._model_pages(fixture, result),
        "factory spare final page schema differs",
    )
    wanted = {page: bytearray(payload) for page, payload in pages.items()}

    def put(address, value, width=4):
        for offset, byte in enumerate(value.to_bytes(width, "little")):
            at = address + offset
            wanted[at & ~4095][at & 4095] = byte

    for row in copies:
        put(addresses[row["destination"]] + 20, row["payload"])
    pair = _blob(pages, argument, 8)
    for offset, byte in enumerate(pair):
        put(begin + 40 + offset, byte, 1)
    put(prefix.RECEIVER + 8, begin + 48)
    stack_pages = {prefix.construction.STACK, prefix.construction.STACK + 4096}
    _require(
        all(
            final_pages[page] == bytes(payload)
            for page, payload in wanted.items()
            if page not in stack_pages
        )
        and _blob(final_pages, begin, 40) == _blob(pages, begin, 40)
        and _blob(final_pages, begin + 40, 8) == pair
        and _blob(final_pages, prefix.leaf.HEAD, 24)
        == _blob(pages, prefix.leaf.HEAD, 24)
        and _blob(final_pages, prefix.SOURCE_OBJECT, 72)
        == _blob(pages, prefix.SOURCE_OBJECT, 72)
        and all(
            _blob(final_pages, address, 20) == _blob(pages, address, 20)
            and _raw(final_pages, address + 20) == final_state["payloads"][identity]
            for identity, address in enumerate(addresses)
        )
        and all(
            _blob(final_pages, prefix.RECEIVER + offset, 4)
            == _blob(pages, prefix.RECEIVER + offset, 4)
            for offset in range(0, 72, 4)
            if offset != 8
        ),
        "factory spare independent byte preservation differs",
    )
    for offset, size in ((0x2000, 8), (0x1000, 16), (0x800, 24), (0x3800, 32)):
        pointer = prefix.construction.DATA + offset + vector["vector_alignment"]
        _require(
            _blob(final_pages, pointer, size) == _blob(pages, pointer, size),
            "factory spare retained prior vector differs",
        )
    for page in stack_pages:
        start = max(0, entry + 8 - page)
        _require(
            final_pages[page][start:] == pages[page][start:],
            "factory spare caller stack differs",
        )
    _require(
        set(result).isdisjoint(
            {
                "growth_entry",
                "resize_entry",
                "copy_entry",
                "copy_return",
                "allocations",
                "frees",
                "vector_heap_request",
                "vector_free_request",
            }
        ),
        "factory spare unexpected growth packet",
    )
    return dict(result, tree_heap_count=0, xmm=copy.deepcopy(fixture["xmm"]), df=0)
