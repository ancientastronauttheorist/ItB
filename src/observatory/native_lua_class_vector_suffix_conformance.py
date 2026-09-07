"""Joined native append and cookie return with caller-specific ancestor preservation."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory import native_scalar_vector_append_conformance as scalar_append
from src.observatory import native_small_vector_append_conformance as small_append
from src.observatory import native_lua_class_vector_return_conformance as returned
from src.observatory import native_scalar_vector_growth_conformance as linked_growth
from src.observatory import native_lua_class_vector_append_semantics as append
from src.observatory.native_lua_vector_allocation_return_conformance import _add_flags
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_vector_suffix_conformance"
SEALED_SHA256 = "3857ad551d3f6577537d379ff7be32d3995f73ca33737745c916cc78883b9b24"
SOURCE_PINS = {
    **scalar_append.SOURCE_PINS,
    "small_append_conformance": (
        small_append.ANALYSIS_KIND,
        small_append.SEALED_SHA256,
    ),
    "scalar_append_conformance": (
        scalar_append.ANALYSIS_KIND,
        scalar_append.SEALED_SHA256,
    ),
    "return_conformance": (returned.ANALYSIS_KIND, returned.SEALED_SHA256),
}

STACK, NEW, OLD, OBJECT, RETURN, IMPORT = (
    linked_growth.STACK,
    linked_growth.NEW,
    linked_growth.OLD,
    linked_growth.OBJECT,
    linked_growth.RETURN,
    linked_growth.IMPORT,
)
HEAP_GLOBAL, ALLOC_IAT, FREE_IAT, HEAP = (
    linked_growth.HEAP_GLOBAL,
    linked_growth.ALLOC_IAT,
    linked_growth.FREE_IAT,
    linked_growth.HEAP,
)
STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE = (
    linked_growth.STACK_TEMPLATE,
    linked_growth.NEW_TEMPLATE,
    linked_growth.OLD_TEMPLATE,
    linked_growth.OBJECT_TEMPLATE,
)
ARG_LOW, ARG_HIGH = 0x01000000, 0x0A000000
LOW_TEMPLATE = bytes(((i * 47) ^ 0x35) & 255 for i in range(0x1000))
HIGH_TEMPLATE = bytes(((i * 53) ^ 0xD1) & 255 for i in range(0x1000))
STOP = BASE + 0x2EB21A
BODIES = {**scalar_append.BODIES, **returned.BODIES}


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    selected = [
        v
        for v in small_append.vectors() + scalar_append.vectors()
        if v["new_alignment"] in (0, 1, 7, 15, 31) and v["stack_alignment"] in (0, 15)
    ]
    return [
        {**v, "cookie": cookie, "global_delta": delta}
        for v in selected
        for cookie in (0, 0x6B8B4567)
        for delta in (0, 1)
    ]


def geometry(vector):
    for k in ("cookie", "global_delta"):
        _require(
            type(vector[k]) is int and 0 <= vector[k] < 2**32, "invalid cookie state"
        )
    child = (
        small_append
        if type(vector["old_size"]) is int and vector["old_size"] < 4
        else scalar_append
    )
    try:
        g = child.geometry(vector)
    except Exception as exc:
        raise ConformanceError(str(exc)) from exc
    g.update(
        current_cookie=(vector["cookie"] + vector["global_delta"]) & 0xFFFFFFFF,
        equal=vector["global_delta"] == 0,
    )
    return g


def frame_join(s):
    frame = scalar_append.frame_join(s)
    frame.update(
        checker_entry=s + 8,
        caller_return=s + 44,
        mismatch_esp=s + 8,
        saved_ebp=s + 32,
        return_word=s + 36,
    )
    return frame


def _expected(
    vector, initial, original_stack, original_new, original_old, original_object
):
    g = geometry(vector)
    child = small_append if vector["old_size"] < 4 else scalar_append
    result = child._expected(
        vector, initial, original_stack, original_new, original_old, original_object
    )
    f = initial["ebp"]
    saved = {
        r: int.from_bytes(
            original_stack[f + off - STACK : f + off - STACK + 4], "little"
        )
        for r, off in (("edi", -32), ("esi", -28), ("ebx", -24), ("ebp", 0))
    }
    relation = returned.return_spec(f, vector["cookie"], g["current_cookie"])
    tail = returned._expected(
        dict(
            frame=f,
            cookie=vector["cookie"],
            current=g["current_cookie"],
            relation=relation,
            saved=saved,
            registers=result["registers"],
            stack=result["stack"],
        )
    )
    result.update(
        geometry=g,
        registers=tail["registers"],
        stack=tail["stack"],
        events=result["events"] + tail["events"],
        flags=tail["flags"],
        flag_mask=0x8D5,
        endpoint=relation["endpoint"],
    )
    return result


def _preflight(sources):
    _require(set(sources) == set(SOURCE_PINS), "source partition differs")
    return {k: _source_identity(sources[k], *pin, k) for k, pin in SOURCE_PINS.items()}


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(digest == EXE_SHA256, "executable differs")
    all_points = {}
    bodies = [
        *sources["return_conformance"]["bodies"].values(),
        sources["append"]["slice"],
        sources["growth"]["body"],
        sources["owner"]["body"],
        *sources["allocation_conformance"]["bodies"].values(),
        sources["deallocation_composition"]["guard_body"],
        *sources["deallocation_composition"]["free_bodies"],
        *sources["scalar_copy"]["body"]["ranges"],
    ]
    for body in bodies:
        for point in body["points"]:
            _require(point["rva"] not in all_points, "source point overlap")
            all_points[point["rva"]] = point
    decoder = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    decoder.detail = True
    codes, points = {}, {}
    for name, (a, b) in BODIES.items():
        offset = image.rva_to_file_offset(a)
        codes[name] = data[offset : offset + b - a]
        points[name] = [_point(r) for r in decoder.disasm(codes[name], BASE + a)]
        _require(
            sum(p["size"] for p in points[name]) == b - a
            and all(all_points.get(p["rva"]) == p for p in points[name]),
            "integrated witness differs",
        )
    for table, targets in linked_growth.resize.copy_replay.TABLES.items():
        offset = image.rva_to_file_offset(table)
        _require(
            data[offset : offset + 16]
            == b"".join((BASE + v).to_bytes(4, "little") for v in targets),
            "exact copy table differs",
        )
    observations = [_run_case(codes, points, v) for v in vectors()]
    union = sorted({p for c in observations for p in c["trace_rvas"]})
    _require(
        all(
            p["rva"] in union
            for name in ("append", "epilogue", "checker_normal", "checker_escape")
            for p in points[name]
        ),
        "append coverage differs",
    )
    controls = []
    sample = next(
        v
        for v in vectors()
        if v["old_size"] == 4
        and v["requested"] == 6
        and v["argument_kind"] == "external_high"
    )
    for kind, message in (
        ("ancestor", "integrated ancestor memory differs"),
        ("payload", "integrated payload or metadata differs"),
    ):
        try:
            _run_case(codes, points, sample, kind)
        except ConformanceError as exc:
            _require(str(exc) == message, "negative control failed incidentally")
            controls.append(dict(kind=kind, rejected=True))
        else:
            raise ConformanceError("integrated mutation survived")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=ids,
        build_identity=sources["owner"]["build_identity"],
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=union,
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            loaded_bytes=sum(len(c) for c in codes.values()),
            table_data_bytes=32,
            loaded_sites=sum(len(p) for p in points.values()),
            executed_sites=len(union),
            equal_returns=sum(geometry(v)["equal"] for v in vectors()),
            mismatch_frontiers=sum(not geometry(v)["equal"] for v in vectors()),
            resized_cases=sum(geometry(v)["grows"] for v in vectors()),
            allocation_api_summaries=sum(
                c["role"] == "allocate" for o in observations for c in o["summaries"]
            ),
            free_api_summaries=sum(
                c["role"] == "free" for o in observations for c in o["summaries"]
            ),
            opaque_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Append, native relocation descendants and owner cookie epilogue execute in one state to caller return or external mismatch boundary; only successful heap API responses are supplied",
            domain="Small zero-through-three and sampled four-through-256 live sizes from sealed append domains; five paired block alignments and two stack alignments; two protected cookies and equal or adjacent current globals",
            frame_relation="Append S reaches allocation API S-104 and free API S-96; owner F=S+32; checker CALL overwrites already-restored saved EBX at S+8; equality finishes S+44, mismatch stops with S+8",
            oracle_join="Sealed small or scalar append oracle joins the independently sealed return oracle using the actual saved words, current child registers and complete child stack",
            premises=[
                "Disjoint object, payload, argument and ancestor storage; valid prior saved registers and protected cookie word",
                "Stable zero copy feature words, exact dispatch tables, heap, imports and current cookie global; DF clear",
                "Successful stdcall API responses preserve all storage and nonvolatile registers",
            ],
            not_claimed=[
                "Tree prefix execution, actual heap effects, failed allocation, mismatch failure implementation, SIMD modes or arbitrary geometry",
                "Full game equivalence or accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    ids = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == ids
        and evidence["vectors"] == vectors(),
        "sealed integrated append differs",
    )
    _assert_publication_safe(evidence)
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
        "exact integrated append differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )


def _run_case(codes, points, vector, negative=None):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    g = geometry(vector)
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    pages = {BASE + (a & ~0xFFF) for a, b in BODIES.values()}
    pages.update(
        (
            RETURN,
            returned.ESCAPE & ~0xFFF,
            IMPORT,
            HEAP_GLOBAL & ~0xFFF,
            ALLOC_IAT & ~0xFFF,
            OBJECT,
            ARG_LOW,
            ARG_HIGH,
            0x893000,
            0x8B6000,
        )
    )
    for page in sorted(pages):
        machine.mem_map(page, 0x1000)
    for page in (STACK, NEW, OLD):
        machine.mem_map(page, 0x4000)
    for name, (a, b) in BODIES.items():
        machine.mem_write(BASE + a, codes[name])
    table_payloads = {
        BASE + t: b"".join((BASE + v).to_bytes(4, "little") for v in targets)
        for t, targets in linked_growth.resize.copy_replay.TABLES.items()
    }
    for address, payload in table_payloads.items():
        machine.mem_write(address, payload)
    machine.mem_write(IMPORT, b"\xcc")
    s = STACK + 0x2000 + vector["stack_alignment"]
    obj = OBJECT + 0x104
    stack, new, old, objects = map(
        bytearray, (STACK_TEMPLATE, NEW_TEMPLATE, OLD_TEMPLATE, OBJECT_TEMPLATE)
    )
    for address, value in (
        (s, RETURN),
        (s + 4, vector["requested"]),
        (s + 20, OBJECT + 0x100),
    ):
        stack[address - STACK : address - STACK + 4] = value.to_bytes(4, "little")
    for i, key in enumerate(("old_begin", "old_end", "old_capacity")):
        objects[obj - OBJECT + 4 * i : obj - OBJECT + 4 * i + 4] = g[key].to_bytes(
            4, "little"
        )
    if g["old_metadata"] is not None:
        at = g["old_metadata"] - OLD
        old[at : at + 4] = g["old_raw"].to_bytes(4, "little")
    globals = bytearray(0x1000)
    offset = HEAP_GLOBAL & 0xFFF
    globals[offset : offset + 4] = HEAP.to_bytes(4, "little")
    iat = bytearray(0x1000)
    for address in (ALLOC_IAT, FREE_IAT):
        iat[address & 0xFFF : (address & 0xFFF) + 4] = IMPORT.to_bytes(4, "little")
    for page, payload in (
        (STACK, stack),
        (NEW, new),
        (OLD, old),
        (OBJECT, objects),
        (ARG_LOW, LOW_TEMPLATE),
        (ARG_HIGH, HIGH_TEMPLATE),
        (HEAP_GLOBAL & ~0xFFF, globals),
        (ALLOC_IAT & ~0xFFF, iat),
    ):
        machine.mem_write(page, bytes(payload))
    ids = {
        "eax": x.UC_X86_REG_EAX,
        "ebx": x.UC_X86_REG_EBX,
        "ecx": x.UC_X86_REG_ECX,
        "edx": x.UC_X86_REG_EDX,
        "esi": x.UC_X86_REG_ESI,
        "edi": x.UC_X86_REG_EDI,
        "ebp": x.UC_X86_REG_EBP,
        "esp": x.UC_X86_REG_ESP,
    }
    initial = {r: 0x16273849 + i * 0x1010101 for i, r in enumerate(ids)}
    initial.update(esp=s, ebp=s + 32, ecx=0x1A2B3C4D, edi=g["argument"])
    f = initial["ebp"]
    for offset, value in (
        (0, 0xA1B2C3D4),
        (4, 0xB2C3D4E5),
        (8, 0xC3D4E5F6),
        (28, vector["cookie"] ^ f),
        (32, 0xD4E5F607),
        (36, RETURN),
    ):
        stack[s + offset - STACK : s + offset - STACK + 4] = value.to_bytes(4, "little")
    machine.mem_write(STACK, bytes(stack))
    cookie_page = bytearray(0x1000)
    at = returned.COOKIE & 0xFFF
    cookie_page[at : at + 4] = g["current_cookie"].to_bytes(4, "little")
    machine.mem_write(returned.COOKIE & ~0xFFF, bytes(cookie_page))
    expected = _expected(vector, initial, stack, new, old, objects)
    for reg, value in initial.items():
        machine.reg_write(ids[reg], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
    allowed = {int(p["rva"], 16) for rows in points.values() for p in rows}
    visited, events, summaries = [], [], []
    resume = None

    def on_code(m, address, size, user):
        nonlocal resume
        if address in (RETURN, returned.ESCAPE):
            m.emu_stop()
            return
        if address == IMPORT:
            sp = m.reg_read(x.UC_X86_REG_ESP)
            words = [
                int.from_bytes(m.mem_read(sp + 4 * i, 4), "little") for i in range(4)
            ]
            continuation = words[0]
            if continuation == BASE + 0x389463:
                role = "allocate"
                _require(
                    g["request"] is not None
                    and sp == s - 104
                    and words[1:] == [HEAP, 0, g["request"]],
                    "nested allocation handoff differs",
                )
                result = g["new_raw"]
            elif continuation == BASE + 0x389172:
                role = "free"
                _require(
                    vector["has_old"]
                    and sp == s - 96
                    and words[1:] == [HEAP, 0, g["old_raw"]],
                    "nested free handoff differs",
                )
                result = 1
            else:
                raise ConformanceError("unexpected imported continuation")
            _require(role not in [c["role"] for c in summaries], "repeated API call")
            m.reg_write(x.UC_X86_REG_EAX, result)
            m.reg_write(x.UC_X86_REG_ECX, 0xA0000001)
            m.reg_write(x.UC_X86_REG_EDX, 0xB0000001)
            m.reg_write(x.UC_X86_REG_EFLAGS, 0x246)
            m.reg_write(x.UC_X86_REG_ESP, sp + 16)
            if negative == "ancestor" and role == "allocate":
                m.mem_write(
                    s + 40,
                    (int.from_bytes(m.mem_read(s + 40, 4), "little") ^ 1).to_bytes(
                        4, "little"
                    ),
                )
            if negative == "payload" and role == "free" and g["copy_bytes"]:
                first = int.from_bytes(m.mem_read(g["new_begin"], 1), "little")
                m.mem_write(g["new_begin"], bytes([first ^ 1]))
            summaries.append(dict(role=role, entry_esp=sp, continuation=continuation))
            resume = continuation
            m.emu_stop()
            return
        pc = address - BASE
        _require(pc in allowed, "execution escaped integrated successful resize")
        visited.append(f"0x{pc:08x}")

    def on_memory(m, access, address, size, value, user):
        _require(size in (1, 4), "unexpected integrated access width")
        write = access == uc.UC_MEM_WRITE
        _require(
            write
            or not (
                OLD <= address < OLD + 0x4000
                and any(c["role"] == "free" for c in summaries)
            ),
            "read from released old storage",
        )
        events.append(
            dict(
                access="write" if write else "read",
                address=address,
                width=size,
                value=(
                    value
                    if write
                    else int.from_bytes(m.mem_read(address, size), "little")
                ),
            )
        )

    machine.hook_add(uc.UC_HOOK_CODE, on_code)
    machine.hook_add(uc.UC_HOOK_MEM_READ | uc.UC_HOOK_MEM_WRITE, on_memory)
    start = BASE + 0x2EB1BB
    for _ in range(3):
        resume = None
        machine.emu_start(start, 0, count=4000)
        if resume is None:
            break
        start = resume
    _require(
        machine.reg_read(x.UC_X86_REG_EIP) == expected["endpoint"],
        "integrated resize did not return",
    )
    _require(
        [c["role"] for c in summaries]
        == (["allocate"] if g["request"] is not None else [])
        + (["free"] if g["grows"] and vector["has_old"] else []),
        "API sequence differs",
    )
    actual = {r: machine.reg_read(i) for r, i in ids.items()}
    flags = machine.reg_read(x.UC_X86_REG_EFLAGS)
    _require(
        actual == expected["registers"]
        and flags & expected["flag_mask"] == expected["flags"] & expected["flag_mask"]
        and not (flags & 0x400),
        "integrated register or flag oracle differs",
    )
    _require(events == expected["events"], "integrated ordered event oracle differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == expected["stack"],
        "integrated ancestor memory differs",
    )
    _require(
        bytes(machine.mem_read(NEW, 0x4000)) == expected["new"]
        and bytes(machine.mem_read(OLD, 0x4000)) == expected["old"]
        and bytes(machine.mem_read(OBJECT, 0x1000)) == expected["object"]
        and bytes(machine.mem_read(ARG_LOW, 0x1000)) == LOW_TEMPLATE
        and bytes(machine.mem_read(ARG_HIGH, 0x1000)) == HIGH_TEMPLATE,
        "integrated payload or metadata differs",
    )
    _require(
        bytes(machine.mem_read(HEAP_GLOBAL & ~0xFFF, 0x1000)) == bytes(globals)
        and bytes(machine.mem_read(ALLOC_IAT & ~0xFFF, 0x1000)) == bytes(iat),
        "integrated global or IAT memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(page, 0x1000))
            == (
                bytes(cookie_page)
                if page == returned.COOKIE & ~0xFFF
                else bytes(0x1000)
            )
            for page in (0x893000, 0x8B6000)
        ),
        "feature memory differs",
    )
    _require(
        all(
            bytes(machine.mem_read(address, len(payload))) == payload
            for address, payload in table_payloads.items()
        ),
        "copy table memory differs",
    )
    return dict(
        inputs=vector,
        registers=actual,
        flags=flags & expected["flag_mask"],
        flag_mask=expected["flag_mask"],
        trace_rvas=visited,
        events_sha256=_canonical_sha256(events),
        stack_sha256=hashlib.sha256(expected["stack"]).hexdigest(),
        new_sha256=hashlib.sha256(expected["new"]).hexdigest(),
        old_sha256=hashlib.sha256(expected["old"]).hexdigest(),
        object_sha256=hashlib.sha256(expected["object"]).hexdigest(),
        summaries=summaries,
    )
