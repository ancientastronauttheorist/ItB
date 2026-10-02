"""Sixth scalar spare callback over an actual retained fifth factory return."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from src.observatory import native_lua_class_factory_callback_fifth_conformance as fifth
from src.observatory import native_lua_class_factory_callback_sixth_semantics as model
from src.observatory import native_lua_class_factory_spare_adapter as adapter

fourth, third, tree, extend, repeat, old = (
    fifth.fourth,
    fifth.third,
    fifth.tree,
    fifth.extend,
    fifth.repeat,
    fifth.old,
)
normal, full, factory, callback = (
    fifth.normal,
    fifth.full,
    fifth.factory,
    fifth.callback,
)
simd_class = fifth.simd_class
BASE, ConformanceError, _require = fifth.BASE, fifth.ConformanceError, fifth._require
_canonical_sha256, _canonical_bytes = fifth._canonical_sha256, fifth._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_sixth_conformance"
SEALED_SHA256 = "cdd92b83335043ca08b33f04dc4ca9a3643e97f594f8ba8349f40de81f547c18"
CONTROLS = {
    **{
        key: reason
        for key, reason in normal.CONTROLS.items()
        if key not in {"heap_request", "heap_register", "heap_flags", "heap_identity"}
    },
    "spare_entry_xmm": "callback SIMD XMM differs",
    "spare_entry_df": "callback SIMD DF differs",
    "simd_xmm": "callback SIMD XMM differs",
    "simd_df": "callback SIMD DF differs",
    "spare_record": "callback protected memory differs",
}
SOURCE_PINS = {
    **fifth.SOURCE_PINS,
    "factory_callback_fifth": (fifth.ANALYSIS_KIND, fifth.SEALED_SHA256),
}
GROWTH_RANGES = tuple(sorted(set(simd_class.growth.BODIES.values())))


def vectors():
    return fifth.vectors()


def _machine_boundary(machine, ids):
    from unicorn import x86_const as x

    return dict(
        registers={r: machine.reg_read(i) for r, i in ids.items()},
        xmm={
            r: machine.reg_read(getattr(x, "UC_X86_REG_" + r.upper()))
            for r in callback.XMM
        },
        flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
        endpoint=machine.reg_read(x.UC_X86_REG_EIP),
    )


def _produce_fifth(payload, fp, continuation, codes, points, vector):
    produced, producer, f1, cap1, f2, cap2, f3, cap3, f4, cap4 = fifth._produce_fourth(
        payload, fp, continuation, codes, points, vector
    )
    f5 = fifth._resume(produced, f4, cap4, vector)
    cap5 = dict(entry=[], returned=[])

    def entry_capture(machine, ids, expected):
        cap5["entry"].append(_machine_boundary(machine, ids))

    def capture(machine, ids, expected, lua):
        cap5["returned"].append(_machine_boundary(machine, ids))
        cap5.update(
            pages={p: bytes(machine.mem_read(p, 4096)) for p in f5["pages"]},
            registers={r: machine.reg_read(i) for r, i in ids.items()},
        )

    cap5["observation"] = fifth._run_case(
        codes,
        points,
        f5,
        produced,
        vector,
        capture=capture,
        entry_capture=entry_capture,
    )
    return produced, producer, f1, cap1, f2, cap2, f3, cap3, f4, cap4, f5, cap5


def _checked_boundary(rows, registers, xmm, endpoint, label):
    reason = "fifth producer " + label + " boundary differs"
    _require(type(rows) is list and len(rows) == 1, reason)
    boundary = rows[0]
    _require(
        type(boundary) is dict
        and set(boundary) == {"registers", "xmm", "flags", "endpoint"}
        and type(boundary["registers"]) is dict
        and set(boundary["registers"]) == set(callback.REGISTERS)
        and all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in boundary["registers"].values()
        )
        and boundary["registers"] == registers
        and type(boundary["xmm"]) is dict
        and set(boundary["xmm"]) == set(callback.XMM)
        and all(type(v) is int and 0 <= v < 2**128 for v in boundary["xmm"].values())
        and adapter._same_packet(boundary["xmm"], xmm)
        and type(boundary["flags"]) is int
        and boundary["flags"] == 0x246
        and type(boundary["endpoint"]) is int
        and boundary["endpoint"] == endpoint,
        reason,
    )
    return copy.deepcopy(boundary)


def _check_fifth(produced, fixture, captured):
    _require(
        type(captured) is dict
        and set(captured) == {"entry", "returned", "pages", "registers", "observation"},
        "verified fifth callback capture differs",
    )
    observation = captured["observation"]
    pages = captured["pages"]
    _require(
        type(pages) is dict
        and set(pages) == set(fixture["pages"])
        and all(
            type(p) is int and type(v) is bytes and len(v) == 4096
            for p, v in pages.items()
        )
        and type(captured["registers"]) is dict
        and set(captured["registers"]) == set(callback.REGISTERS)
        and all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in captured["registers"].values()
        )
        and type(observation) is dict
        and type(observation.get("registers")) is dict
        and set(observation["registers"]) == set(callback.REGISTERS)
        and all(
            type(v) is int and 0 <= v <= 0xFFFFFFFF
            for v in observation["registers"].values()
        )
        and captured["registers"] == observation["registers"]
        and repeat._page_sha(pages) == observation.get("memory_sha256"),
        "verified fifth callback capture differs",
    )
    prior = fifth._logical(fixture)
    snapshot = bytes(
        factory._raw(fixture["pages"], fixture["fourth_vector_pointer"] + i, 1)
        for i in range(32)
    )
    incoming = {r: 0 for r in callback.XMM}
    outgoing = dict(
        incoming,
        xmm0=int.from_bytes(snapshot[:16], "little"),
        xmm1=int.from_bytes(snapshot[16:], "little"),
    )
    _require(
        type(observation.get("xmm")) is dict
        and adapter._same_packet(observation["xmm"], outgoing)
        and type(observation.get("df")) is int
        and observation["df"] == 0,
        "verified fifth callback capture differs",
    )
    _checked_boundary(
        captured["entry"],
        fixture["registers"],
        incoming,
        BASE + callback.START,
        "entry",
    )
    returned = _checked_boundary(
        captured["returned"],
        prior["full_return"]["registers"],
        outgoing,
        fixture["endpoint"],
        "return",
    )
    expected = callback._expected(
        fixture["callback_vector"], fixture, class_module=fifth.adapter
    )
    _require(
        pages == expected["pages"]
        and captured["registers"] == prior["full_return"]["registers"]
        and returned["registers"] == captured["registers"]
        and returned["flags"] & prior["full_return"]["flag_mask"]
        == prior["full_return"]["flags"],
        "retained fifth callback differs",
    )
    receiver, sentinel = fixture["receiver"], produced["fixture"]["record"]
    prototype = fixture["prototype"]
    nodes = list(prototype["destination_addresses"])
    state = prior["class_transfer"]["destination"]
    at = lambda i: sentinel if i is None else nodes[i]
    _require(len(nodes) == prior["tree_count"] == 8, "retained fifth callback differs")
    links = prior["sentinel_link_ids"]
    _require(
        [factory._raw(pages, sentinel + i) for i in (0, 4, 8)]
        == [at(links[k]) for k in ("leftmost", "root", "rightmost")]
        and all(
            factory._raw(pages, sentinel + i, 1)
            == factory._raw(fixture["pages"], sentinel + i, 1)
            for i in range(24)
        )
        and all(
            factory._raw(pages, receiver + i)
            == prior["normal_field_updates"].get(
                i, factory._raw(fixture["pages"], receiver + i)
            )
            for i in range(0, 72, 4)
        ),
        "retained fifth callback differs",
    )
    _require(
        all(
            [factory._raw(pages, address + i) for i in (0, 4, 8, 16, 20)]
            == [
                at(n["left"]),
                at(n["parent"]),
                at(n["right"]),
                factory._raw(fixture["pages"], address + 16),
                state["payloads"][identity],
            ]
            and factory._raw(pages, address + 12, 1) == n["color"]
            and factory._raw(pages, address + 13, 1) == 0
            and all(
                factory._raw(pages, address + i, 1)
                == factory._raw(fixture["pages"], address + i, 1)
                for i in (14, 15)
            )
            for identity, (address, n) in enumerate(zip(nodes, state["tree"]["nodes"]))
        )
        and all(
            factory._raw(pages, p + i, 1) == b
            for p, value in prototype["strings"].items()
            for i, b in enumerate(value)
        )
        and all(
            factory._raw(pages, p + i, 1) == factory._raw(fixture["pages"], p + i, 1)
            for p, width in [
                (fixture["source_pointer"], 72),
                (old.prefix.SOURCE_HEAD, 24),
            ]
            + [(a, 24) for a in prototype["source_addresses"]]
            for i in range(width)
        ),
        "retained fifth callback differs",
    )
    _require(
        all(
            [factory._raw(pages, p + 4 * i) for i in range(2 * n)]
            == [0, fixture["source_pointer"]] * n
            for p, n in (
                (fixture["vector_begin"], 5),
                (fixture["fourth_vector_pointer"], 4),
                (fixture["third_vector_pointer"], 3),
                (fixture["second_vector_pointer"], 2),
                (fixture["first_arguments"]["vector_pointer"], 1),
            )
        )
        and pages[0x06003000] == fixture["pages"][0x06003000]
        and all(
            pages[0x06002000][i] == fixture["pages"][0x06002000][i]
            for i in range(4096)
            if not fixture["vector_begin"] - 0x06002000
            <= i
            < fixture["vector_begin"] - 0x06002000 + 40
        )
        and pages[0x00893000] == fixture["pages"][0x00893000]
        and factory._raw(pages, 0x00893F30) == 0x93939393
        and factory._raw(pages, 0) == factory._raw(fixture["pages"], 0)
        and adapter._same_packet(
            observation.get("allocations"),
            [
                dict(
                    node=fixture["vector_begin"],
                    entry_esp=fixture["entry"] - 188,
                    request=48,
                    continuation=0x00789463,
                )
            ],
        )
        and adapter._same_packet(
            observation.get("frees"),
            [
                dict(
                    pointer=fixture["fourth_vector_pointer"],
                    entry_esp=fixture["entry"] - 180,
                    result=1,
                    continuation=0x00789172,
                )
            ],
        ),
        "retained fifth callback differs",
    )
    return prior, nodes


def _check_host_patches(captured, fixture):
    patches = fixture["patches"]
    allowed = {fixture["entry"] + i for i in range(8)} | {
        address + 20 + i
        for address in fixture["prototype"]["source_addresses"]
        for i in range(4)
    }
    _require(
        type(patches) is list and len(patches) == len(allowed),
        "sixth host patch partition differs",
    )
    pages = {p: bytearray(v) for p, v in captured["pages"].items()}
    seen = set()
    expected_bytes = {}
    for address, value in [
        (fixture["entry"], fixture["endpoint"]),
        (fixture["entry"] + 4, fixture["state"]),
    ] + [
        (address + 20, value)
        for address, value in zip(
            fixture["prototype"]["source_addresses"],
            fixture["prototype"]["source_state"]["payloads"],
        )
    ]:
        for i, byte in enumerate(value.to_bytes(4, "little")):
            expected_bytes[address + i] = byte
    for patch in patches:
        _require(
            type(patch) is dict
            and set(patch) == {"address", "before", "after"}
            and all(type(v) is int for v in patch.values())
            and patch["address"] in allowed - seen
            and 0 <= patch["before"] <= 255
            and 0 <= patch["after"] <= 255,
            "sixth host patch partition differs",
        )
        _require(
            patch["after"] == expected_bytes[patch["address"]],
            "sixth host patch partition differs",
        )
        address = patch["address"]
        page, at = address & ~4095, address & 4095
        _require(
            pages[page][at] == patch["before"], "sixth host patch partition differs"
        )
        pages[page][at] = patch["after"]
        seen.add(address)
    _require(
        seen == allowed and {p: bytes(v) for p, v in pages.items()} == fixture["pages"],
        "sixth host patch partition differs",
    )


def _resume(produced, previous, captured, vector):
    prior, nodes = _check_fifth(produced, previous, captured)
    fixture = copy.deepcopy(previous)
    pages = {p: bytearray(v) for p, v in captured["pages"].items()}
    patches = []

    def put(address, value):
        for i, byte in enumerate(value.to_bytes(4, "little")):
            page, at = (address + i) & ~4095, (address + i) & 4095
            patches.append(
                dict(address=address + i, before=pages[page][at], after=byte)
            )
            pages[page][at] = byte

    put(fixture["entry"], fixture["endpoint"])
    put(fixture["entry"] + 4, fixture["state"])
    source = copy.deepcopy(previous["prototype"]["source_state"])
    for identity, address in enumerate(previous["prototype"]["source_addresses"]):
        source["payloads"][identity] ^= (0xFFFFFFFF, 0)[vector["profile"]]
        put(address + 20, source["payloads"][identity])
    a = vector["vector_alignment"]
    fresh = 0x06002800 + a
    xmm = dict(captured["returned"][0]["xmm"])
    prototype = dict(
        copy.deepcopy(previous["prototype"]),
        source_state=source,
        destination_state=copy.deepcopy(prior["class_transfer"]["destination"]),
        destination_addresses=nodes,
        old_size=5,
        vector_begin=fresh,
        vector_end=fresh + 40,
        vector_capacity=fresh + 48,
        xmm=xmm,
    )
    for key in ("old_begin", "old_base", "new_base", "new_page_count"):
        prototype.pop(key, None)
    prototype["transfer"] = old.prefix.model.transfer(
        source, prototype["destination_state"]
    )
    cv = copy.deepcopy(previous["callback_vector"])
    cv.update(
        profile="all_existing",
        source_keys=[n["key"] for n in source["tree"]["nodes"]],
        destination_keys=[
            n["key"] for n in prototype["destination_state"]["tree"]["nodes"]
        ],
        old_size=5,
        old_alignment=a,
        destination_word=cv["source_word"],
        buffer_address=fresh,
        spare_records=1,
    )
    logical = callback.model.apply(
        source,
        prototype["destination_state"],
        dict(records=[[0, previous["source_pointer"]] for _ in range(5)], capacity=6),
        source_pointer=previous["source_pointer"],
        source_word=cv["source_word"],
        destination_word=cv["source_word"],
        source_refs=cv["source_refs"],
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_sixth_spare=True,
    )
    fixture.update(
        pages={p: bytes(v) for p, v in pages.items()},
        patches=patches,
        registers=dict(captured["registers"], esp=previous["entry"]),
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        vector_begin=fresh,
        fifth_source_state=copy.deepcopy(previous["prototype"]["source_state"]),
        fifth_vector_pointer=previous["vector_begin"],
        fifth_entry=previous["entry"],
        fifth_registers=copy.deepcopy(previous["registers"]),
        simd_state=dict(xmm=xmm, df=0),
        captured_pages_sha256=repeat._page_sha(captured["pages"]),
        captured_simd_sha256=_canonical_sha256(
            dict(entry=captured["entry"], returned=captured["returned"])
        ),
    )
    _check_host_patches(captured, fixture)
    return fixture


def _logical(fixture):
    return model.apply(
        first_arguments=fixture["first_arguments"],
        second_source_state=fixture["second_source_state"],
        second_vector_pointer=fixture["second_vector_pointer"],
        second_entry=fixture["second_entry"],
        second_registers=fixture["second_registers"],
        third_source_state=fixture["third_source_state"],
        third_vector_pointer=fixture["third_vector_pointer"],
        third_entry=fixture["third_entry"],
        third_registers=fixture["third_registers"],
        fourth_source_state=fixture["fourth_source_state"],
        fourth_vector_pointer=fixture["fourth_vector_pointer"],
        fourth_entry=fixture["fourth_entry"],
        fourth_registers=fixture["fourth_registers"],
        fifth_source_state=fixture["fifth_source_state"],
        fifth_vector_pointer=fixture["fifth_vector_pointer"],
        fifth_entry=fixture["fifth_entry"],
        fifth_registers=fixture["fifth_registers"],
        sixth_source_state=fixture["prototype"]["source_state"],
        sixth_entry=fixture["entry"],
        sixth_registers=fixture["registers"],
    )["sixth"]


def _run_case(
    codes,
    points,
    fixture,
    produced,
    vector,
    negative=None,
    *,
    capture=None,
    entry_capture=None,
):
    logical = _logical(fixture)
    result = normal._run_case(
        codes,
        points,
        fixture,
        produced,
        extend._base_vector(vector),
        negative,
        logical=logical,
        class_module=adapter,
        capture=capture,
        entry_capture=entry_capture,
    )
    if negative == "cookie":
        return result
    expected = callback._expected(
        fixture["callback_vector"], fixture, class_module=adapter
    )
    child = next(row for row in expected["children"] if row["kind"] == "class")[
        "result"
    ]
    nodes = fixture["prototype"]["destination_addresses"]
    _require(
        child["tree_heap_count"] == 0
        and child["heap_nodes"] == []
        and adapter._same_packet(result["allocations"], [])
        and adapter._same_packet(result["frees"], [])
        and not any(row["width"] == 8 for row in expected["events"])
        and not any(
            a <= int(pc, 16) < b
            for pc in result["trace_rvas"]
            for a, b in GROWTH_RANGES
        ),
        "sixth allocation partition differs",
    )
    _require(
        adapter._same_packet(child["registers"], logical["class_return"]["registers"])
        and child["registers"]["edx"] == fixture["entry"] - 60
        and child["registers"]["esp"] == fixture["entry"] - 40
        and adapter._same_packet(
            result["registers"], logical["full_return"]["registers"]
        ),
        "sixth independent class and full return differ",
    )
    _require(
        child["destination_addresses"] == nodes
        and child["insertions"]
        == [
            dict(
                source=c["source"],
                key=c["key"],
                destination_address=nodes[c["destination"]],
                inserted=False,
                mode="existing",
                payload=c["payload"],
                heap_node=None,
            )
            for c in logical["class_transfer"]["copies"]
        ],
        "sixth independent existing routing differs",
    )
    final, initial = expected["pages"], fixture["pages"]
    receiver, sentinel = fixture["receiver"], produced["fixture"]["record"]
    _require(
        all(
            factory._raw(final, sentinel + i, 1)
            == factory._raw(initial, sentinel + i, 1)
            for i in range(24)
        )
        and factory._raw(final, receiver + 56) == logical["tree_count"] == 8
        and all(
            factory._raw(final, receiver + i) == factory._raw(initial, receiver + i)
            for i in logical["normal_preserved_userdata_offsets"]
        ),
        "sixth independent preserved fields differ",
    )
    selected = {c["destination"] for c in logical["class_transfer"]["copies"]}
    _require(
        all(
            all(
                factory._raw(final, address + i, 1)
                == factory._raw(initial, address + i, 1)
                for i in range(20)
            )
            and (
                identity in selected
                or factory._raw(final, address + 20)
                == factory._raw(initial, address + 20)
            )
            for identity, address in enumerate(nodes)
        ),
        "sixth retained key or omitted payload differs",
    )
    _require(
        [factory._raw(final, fixture["vector_begin"] + 4 * i) for i in range(12)]
        == [0, fixture["source_pointer"]] * 6
        and all(
            factory._raw(final, p + i, 1) == factory._raw(initial, p + i, 1)
            for p, width in (
                (fixture["fourth_vector_pointer"], 32),
                (fixture["third_vector_pointer"], 24),
                (fixture["second_vector_pointer"], 16),
                (fixture["first_arguments"]["vector_pointer"], 8),
            )
            for i in range(width)
        )
        and all(
            factory._raw(final, fixture["vector_begin"] + i, 1)
            == factory._raw(initial, fixture["vector_begin"] + i, 1)
            for i in range(40)
        ),
        "sixth independent retained vector copies differ",
    )
    at = fixture["vector_begin"] - 0x06002000
    _require(
        all(
            final[0x06002000][i] == initial[0x06002000][i]
            for i in range(4096)
            if not at + 40 <= i < at + 48
        ),
        "sixth allocation page outside vector differs",
    )
    _require(
        adapter._same_packet(result["xmm"], fixture["simd_state"]["xmm"])
        and type(result["df"]) is int
        and result["df"] == 0
        and adapter._same_packet(child["xmm"], fixture["simd_state"]["xmm"])
        and type(child["df"]) is int
        and child["df"] == 0,
        "sixth independent SIMD return differs",
    )
    return dict(
        result,
        payload_updates=len(logical["class_transfer"]["copies"]),
        captured_pages_sha256=fixture["captured_pages_sha256"],
        captured_simd_sha256=fixture["captured_simd_sha256"],
    )


def _preflight(sources):
    _require(
        type(sources) is dict and set(sources) == set(SOURCE_PINS),
        "factory sixth source partition differs",
    )
    _require(
        all(type(v) is dict for v in sources.values()),
        "factory sixth source partition differs",
    )
    try:
        return {
            key: factory._source_identity(sources[key], *pin, key)
            for key, pin in SOURCE_PINS.items()
        }
    except simd_class.NativeLuaClassReturnHelperChainError as exc:
        raise ConformanceError(str(exc)) from exc


def _load_code(data, image, sources):
    # The selected fifth union already contains the existing spare branch.
    return fifth._load_code(data, image, sources)


def _capture_controls(sample):
    produced, previous, original, fixture, vector = sample
    controls = []

    def rejected(kind, captured, reason):
        try:
            _resume(produced, previous, captured, vector)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "sixth incidental capture control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("sixth capture control survived: " + kind)

    for key in ("registers", "pages"):
        captured = copy.deepcopy(original)
        if key == "registers":
            captured[key]["eax"] ^= 1
        else:
            address = previous["vector_begin"]
            page = address & ~4095
            data = bytearray(captured[key][page])
            data[address & 4095] ^= 1
            captured[key][page] = bytes(data)
        rejected("capture_" + key, captured, "verified fifth callback capture differs")
    for group, label in (("entry", "entry"), ("returned", "return")):
        for kind in (
            "missing",
            "duplicate",
            "endpoint",
            "flags",
            "df",
            "registers",
        ) + callback.XMM:
            captured = copy.deepcopy(original)
            rows = captured[group]
            if kind == "missing":
                rows.clear()
            elif kind == "duplicate":
                rows.append(copy.deepcopy(rows[0]))
            elif kind in callback.XMM:
                rows[0]["xmm"][kind] ^= 1
            elif kind == "registers":
                rows[0]["registers"]["eax"] ^= 1
            elif kind == "df":
                rows[0]["flags"] |= 0x400
            else:
                rows[0][kind] ^= 1
            rejected(
                "fifth_" + label + "_" + kind,
                captured,
                "fifth producer " + label + " boundary differs",
            )
        for register in callback.REGISTERS:
            captured = copy.deepcopy(original)
            captured[group][0]["registers"][register] ^= 1
            rejected(
                "fifth_" + label + "_gpr_" + register,
                captured,
                "fifth producer " + label + " boundary differs",
            )
        for kind in (
            "tuple",
            "extra",
            "missing",
            "gpr_bool",
            "xmm_bool",
            "xmm_missing",
            "xmm_extra",
            "flags_bool",
            "endpoint_bool",
        ):
            captured = copy.deepcopy(original)
            row = captured[group][0]
            if kind == "tuple":
                captured[group] = tuple(captured[group])
            elif kind == "extra":
                row["extra"] = 0
            elif kind == "missing":
                row.pop("flags")
            elif kind == "gpr_bool":
                row["registers"]["eax"] = True
            elif kind == "xmm_bool":
                row["xmm"]["xmm7"] = False
            elif kind == "xmm_missing":
                row["xmm"].pop("xmm7")
            elif kind == "xmm_extra":
                row["xmm"]["xmm8"] = 0
            elif kind == "flags_bool":
                row["flags"] = True
            else:
                row["endpoint"] = True
            rejected(
                "fifth_" + label + "_schema_" + kind,
                captured,
                "fifth producer " + label + " boundary differs",
            )
    for register in callback.REGISTERS:
        captured = copy.deepcopy(original)
        captured["registers"][register] ^= 1
        captured["observation"]["registers"][register] ^= 1
        captured["returned"][0]["registers"][register] ^= 1
        rejected(
            "coordinated_gpr_" + register,
            captured,
            "fifth producer return boundary differs",
        )
    for kind in (
        "xmm_value",
        "xmm_bool",
        "xmm_missing",
        "xmm_extra",
        "df_value",
        "df_bool",
    ):
        captured = copy.deepcopy(original)
        observation = captured["observation"]
        if kind == "xmm_value":
            observation["xmm"]["xmm0"] ^= 1
        elif kind == "xmm_bool":
            observation["xmm"]["xmm7"] = False
        elif kind == "xmm_missing":
            observation["xmm"].pop("xmm7")
        elif kind == "xmm_extra":
            observation["xmm"]["xmm8"] = 0
        elif kind == "df_value":
            observation["df"] = 1
        else:
            observation["df"] = False
        rejected(
            "observation_" + kind, captured, "verified fifth callback capture differs"
        )
    for key in (
        "capture_extra",
        "page_bytearray",
        "captured_gpr_bool",
        "observation_gpr_bool",
    ):
        captured = copy.deepcopy(original)
        if key == "capture_extra":
            captured["extra"] = 0
        elif key == "page_bytearray":
            page = next(iter(captured["pages"]))
            captured["pages"][page] = bytearray(captured["pages"][page])
        elif key == "captured_gpr_bool":
            captured["registers"]["eax"] = True
        else:
            captured["observation"]["registers"]["eax"] = True
        rejected(key, captured, "verified fifth callback capture differs")
    addresses = {
        **{"userdata_" + str(i): previous["receiver"] + i for i in range(0, 72, 4)},
        **{"sentinel_" + str(i): produced["fixture"]["record"] + i for i in range(24)},
        **{
            "node_" + str(i): previous["prototype"]["destination_addresses"][0] + i
            for i in (0, 4, 8, 12, 13, 14, 15, 16, 20, 23)
        },
        **{
            "source_object_" + str(i): previous["source_pointer"] + i
            for i in (0, 32, 40, 71)
        },
        **{
            "source_head_" + str(i): old.prefix.SOURCE_HEAD + i
            for i in (0, 12, 13, 14, 23)
        },
        **{
            "source_node_" + str(i): previous["prototype"]["source_addresses"][0] + i
            for i in (0, 4, 8, 12, 13, 14, 15, 16, 20, 23)
        },
        "first_vector": previous["first_arguments"]["vector_pointer"] + 7,
        "second_vector": previous["second_vector_pointer"] + 15,
        "third_vector": previous["third_vector_pointer"] + 23,
        "fourth_vector": previous["fourth_vector_pointer"] + 31,
        "fifth_vector": previous["vector_begin"] + 39,
        "page_two": 0x06003333,
        "fs": 0,
        "cookie": 0x00893F28,
        "feature_word": 0x00893F30,
        "feature_page": 0x00893222,
        "allocation_page_filler": 0x06002222,
        "new_spare": fixture["vector_begin"] + 47,
        "stack_scratch": previous["entry"] - 100,
    }
    strings = sorted(previous["prototype"]["strings"])
    addresses.update(
        first_key_bytes=next(p for p in strings if 0x1C000000 <= p < 0x1D000000),
        second_key_bytes=next(p for p in strings if 0x1D000000 <= p < 0x1E000000),
    )
    for kind, address in addresses.items():
        captured = copy.deepcopy(original)
        page = address & ~4095
        data = bytearray(captured["pages"][page])
        data[address & 4095] ^= 1
        captured["pages"][page] = bytes(data)
        captured["observation"]["memory_sha256"] = repeat._page_sha(captured["pages"])
        rejected("retained_" + kind, captured, "retained fifth callback differs")
    for kind in ("allocation_bool", "free_bool"):
        captured = copy.deepcopy(original)
        if kind == "allocation_bool":
            captured["observation"]["allocations"][0]["entry_esp"] = True
        else:
            captured["observation"]["frees"][0]["result"] = True
        rejected(kind, captured, "retained fifth callback differs")
    for kind in (
        "missing",
        "extra",
        "duplicate",
        "before",
        "after",
        "coordinated_after",
        "page",
        "extra_page",
        "address_bool",
        "byte_bool",
        "byte_wide",
        "schema_extra",
        "tuple",
        "missing_page",
    ):
        forged = copy.deepcopy(fixture)
        if kind == "missing":
            forged["patches"].pop()
        elif kind == "extra":
            forged["patches"].append(dict(address=0, before=0, after=0))
        elif kind == "duplicate":
            forged["patches"][-1] = copy.deepcopy(forged["patches"][0])
        elif kind in ("before", "after", "coordinated_after"):
            key = "before" if kind == "before" else "after"
            forged["patches"][0][key] ^= 1
            if kind == "coordinated_after":
                address = forged["patches"][0]["address"]
                page = address & ~4095
                data = bytearray(forged["pages"][page])
                data[address & 4095] ^= 1
                forged["pages"][page] = bytes(data)
        elif kind == "page":
            data = bytearray(forged["pages"][0x06002000])
            data[0x222] ^= 1
            forged["pages"][0x06002000] = bytes(data)
        elif kind == "extra_page":
            forged["pages"][0x17000000] = bytes(4096)
        elif kind == "address_bool":
            forged["patches"][0]["address"] = True
        elif kind == "byte_bool":
            forged["patches"][0]["before"] = False
        elif kind == "byte_wide":
            forged["patches"][0]["after"] = 256
        elif kind == "schema_extra":
            forged["patches"][0]["width"] = 1
        elif kind == "tuple":
            forged["patches"] = tuple(forged["patches"])
        else:
            forged["pages"].pop(0x06002000)
        try:
            _check_host_patches(original, forged)
        except ConformanceError as exc:
            _require(
                str(exc) == "sixth host patch partition differs",
                "sixth incidental host control",
            )
            controls.append(dict(kind="host_" + kind, rejected=True, reason=str(exc)))
        else:
            raise ConformanceError("sixth host control survived")
    return controls


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory sixth executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    groups = [[] for _ in range(6)]
    producers, boundaries, fourth_boundaries = [], [], []
    sample = None
    for vector in vectors():
        produced, producer, f1, cap1, f2, cap2, f3, cap3, f4, cap4, f5, cap5 = (
            _produce_fifth(payload, fp, continuation, codes, points, vector)
        )
        fixture = _resume(produced, f5, cap5, vector)
        for group, captured in zip(groups, (cap1, cap2, cap3, cap4, cap5)):
            group.append(captured["observation"])
        groups[5].append(_run_case(codes, points, fixture, produced, vector))
        producers.append(producer)
        boundaries.append(dict(entry=cap5["entry"], returned=cap5["returned"]))
        fourth_boundaries.append(dict(entry=cap4["entry"], returned=cap4["returned"]))
        if (
            vector["profile"] == vector["first_key_profile"] == 1
            and vector["transfer_profile"] == 4
        ):
            sample = (produced, f5, cap5, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[3], sample[0], sample[4], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "sixth incidental native control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("sixth native control survived: " + kind)
    failure = _run_case(codes, points, sample[3], sample[0], sample[4], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "sixth cookie failure differs",
    )
    controls.append(dict(failure, kind="native_callback_cookie"))
    controls.extend(_capture_controls(sample))
    predecessor = sources["factory_callback_fifth"]
    names = ("first", "second", "third", "fourth", "fifth", "sixth")
    site_groups = [
        sorted({pc for observation in group for pc in observation["trace_rvas"]})
        for group in groups
    ]
    observation_hashes = {
        _name + "_observations_sha256": _canonical_sha256(group)
        for _name, group in zip(names, groups)
    }
    for index, name in enumerate(names[:5]):
        _require(
            site_groups[index] == predecessor[name + "_executed_rvas"]
            and observation_hashes[name + "_observations_sha256"]
            == predecessor[name + "_observations_sha256"],
            "sixth predecessor " + name + " differs",
        )
    producer_hash = _canonical_sha256(producers)
    _require(
        producer_hash == predecessor["producer_observations_sha256"],
        "sixth predecessor factory differs",
    )
    union = sorted(set().union(*map(set, site_groups)))
    selected = {p["rva"] for p in points}
    _require(
        set(union) <= selected
        and not any(
            a <= int(pc, 16) < b for pc in union for a, b in normal.PARENT_EXCLUDED
        ),
        "sixth normal site partition differs",
    )
    _require(
        {"0x002eb205", "0x002eb140"} <= set(site_groups[5])
        and not any(
            a <= int(pc, 16) < b for pc in site_groups[5] for a, b in GROWTH_RANGES
        ),
        "sixth spare class coverage differs",
    )
    fourth_boundary_hash = _canonical_sha256(fourth_boundaries)
    _require(
        fourth_boundary_hash == predecessor["fourth_simd_boundary_observations_sha256"],
        "sixth predecessor fourth SIMD boundary differs",
    )
    base = sources["factory_callback_tree"]["normal_site_partition"]
    parent, markers, tables = (set(base[k]) for k in ("callback", "markers", "tables"))
    count = len(groups[5])
    sixths = groups[5]
    summary = dict(predecessor["summary"])
    summary.update(
        cases=count,
        callback_invocations=6 * count,
        static_sites=len(points),
        executed_sites=len(union),
        instruction_bytes=len(
            {a + i for a, body in codes.items() for i in range(len(body))}
        ),
        sixth_callback_instructions=sum(len(o["trace_rvas"]) for o in sixths),
        callback_api_calls=summary["callback_api_calls"]
        + sum(o["api_calls"] for o in sixths),
        sixth_class_heap_calls=0,
        sixth_payload_updates=sum(o["payload_updates"] for o in sixths),
        sixth_tree_allocations=0,
        sixth_copied_old_vector_bytes=0,
        sixth_vector_bytes=48 * count,
        sixth_capacity_bytes=48 * count,
        sixth_preserved_old_vector_bytes=40 * count,
        sixth_free_calls=0,
        fifth_xmm_entry_captures=count,
        fifth_xmm_return_captures=count,
        sixth_wide_reads=0,
        sixth_wide_writes=0,
        sixth_xmm_preservations=count,
        marker_calls=12 * count,
        table_calls=12 * count,
        requested_assignments=summary["requested_assignments"]
        + sum(sum(map(len, o["assignments"])) for o in sixths),
        controls=len(controls),
        accounting_promotions=0,
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            ranges=[
                dict(
                    start_rva=f"0x{a:08x}",
                    end_rva=f"0x{a + len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        **{name + "_executed_rvas": sites for name, sites in zip(names, site_groups)},
        normal_site_partition=dict(
            callback=sorted(parent),
            class_operation=sorted(set(union) - parent - markers - tables),
            markers=sorted(markers),
            tables=sorted(tables),
            excluded=sorted(selected - set(union)),
        ),
        negative_controls=controls,
        **observation_hashes,
        producer_observations_sha256=producer_hash,
        fourth_simd_boundary_observations_sha256=fourth_boundary_hash,
        fifth_xmm_boundary_observations_sha256=_canonical_sha256(boundaries),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=summary,
        scope=dict(
            continuous_each_callback=True,
            continuous_across_host=False,
            checked=[
                "Actual factory receiver and verified first through fifth return pages retained across explicit host invocations",
                "Every fifth producer captures actual eight XMM registers full EFLAGS GPRs and PCs at entry and return; incoming zeros and outgoing old-four-record words are independently checked",
                "Complete fifth pages and typed allocation and free metadata agree with the independent fifth oracle and direct retained tree source userdata vectors strings feature and page-two equations",
                "Exactly thirty-six caller and source payload bytes are replayed against captured pages",
                "Sixth native seven existing payload updates preserve eight destination identities and omitted key sixteen",
                "Sixth scalar append preserves forty bytes and fills the last eight bytes of the retained forty-eight-byte capacity with no heap request copy or free request",
                "All eight incoming XMM registers and clear DF survive class Lua cookie and full return with no eight-byte memory access",
                "Every ordered native access final page and independent logical field and ABI equation agrees",
            ],
            premises=[
                "Six fixed explicit host invocations with seven fixed source keys retained eight destination identities and successful predecessor allocation and free responses",
                "Sixth source payload DWORDs are complemented for factory profile zero and unchanged for profile one; keys and topology stay fixed",
                "Supplied normal Lua responses preserve all eight XMM registers; VM requests do not prove actual table effects",
                "Pinned Unicorn predecessor machine state and actual captured boundaries; no hardware execution claim",
            ],
            excluded=[
                "New sixth keys other source recipes more than six callbacks and native unions larger than eight",
                "Real Lua VM heap ownership invalidation allocator reuse assertion exception failure-handler behavior and whole-program accounting",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory sixth executable changed",
    )
    normal.first.entry._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    normal.first.entry._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory sixth receipt differs",
    )
    normal.first.entry._assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_conformance(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_conformance(executable, sources))
        == _canonical_bytes(evidence),
        "exact factory sixth receipt differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = fifth.encode_conformance
