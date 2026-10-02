"""Actual produced class receiver through continuous native callback return."""

from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from src.observatory import (
    native_lua_class_factory_callback_empty_class_conformance as first,
)

full, factory, callback, empty, layout = (
    first.full,
    first.factory,
    first.callback,
    first.empty,
    first.layout,
)
BASE, ConformanceError, _require = first.BASE, first.ConformanceError, first._require
_canonical_sha256, _canonical_bytes = first._canonical_sha256, first._canonical_bytes
ANALYSIS_KIND = "pe_native_lua_class_factory_callback_return_conformance"
SEALED_SHA256 = "6b0f0ced057240a366ccd5c9545d482feb2d7fbcd3af70aaa5186779c3ad885e"
SOURCE_PINS = {
    **first.SOURCE_PINS,
    "factory_empty_class": (first.ANALYSIS_KIND, first.SEALED_SHA256),
    "table": callback.SOURCE_PINS["table"],
}
PARENT_EXCLUDED = ((0x2EC140, 0x2EC154), (0x2EC164, 0x2EC178), (0x2EC188, 0x2EC19E))


def vectors():
    return [
        dict(v, transfer_profile=i)
        for v in first.vectors()
        for i in range(len(callback.TRANSFER_PAIRS))
    ]


def _first_vector(vector):
    return {k: v for k, v in vector.items() if k != "transfer_profile"}


def _resume(produced, vector):
    _require(
        type(vector["transfer_profile"]) is int and 0 <= vector["transfer_profile"] < 6,
        "unreviewed factory callback transfer profile",
    )
    fixture = first._resume(produced, _first_vector(vector))
    pages = {p: bytearray(b) for p, b in fixture["pages"].items()}
    patches = list(fixture["patches"])
    source = fixture["source_pointer"]
    word = (0, 0xFFFFFFFF)[vector["profile"]]
    source_refs = [23 + 100 * vector["profile"], 29 + 100 * vector["profile"]]
    for a, w in (
        (source, word),
        (source + 32, source_refs[0]),
        (source + 40, source_refs[1]),
    ):
        for i, b in enumerate(w.to_bytes(4, "little")):
            at = a + i
            p, off = at & ~4095, at & 4095
            patches.append(dict(address=at, before=pages[p][off], after=b))
            pages[p][off] = b
    frozen = {p: bytes(b) for p, b in pages.items()}
    cv = dict(
        first._class_vector(vector, frozen),
        marker_words=[(0, 0x12345678)[vector["profile"]], 0xFFFFFFFF],
        transfers=copy.deepcopy(
            list(callback.TRANSFER_PAIRS[vector["transfer_profile"]])
        ),
        source_word=word,
        source_refs=source_refs,
        destination_word=factory._raw(produced["pages"], first.alignment.USERDATA),
        destination_refs=[
            factory._raw(produced["pages"], first.alignment.USERDATA + o)
            for o in (32, 40)
        ],
    )
    prototype = empty._fixture(cv)
    logical = callback.model.apply(
        prototype["source_state"],
        prototype["destination_state"],
        dict(records=[], capacity=0),
        source_pointer=source,
        source_word=word,
        destination_word=cv["destination_word"],
        source_refs=source_refs,
        destination_refs=cv["destination_refs"],
        transfers=cv["transfers"],
        allow_growth=True,
    )
    return dict(
        fixture,
        pages=frozen,
        patches=patches,
        prototype=prototype,
        logical=logical,
        callback_vector=cv,
        endpoint=callback.RETURN,
    )


def _logical(fixture, produced):
    from src.observatory import (
        native_lua_class_factory_callback_return_semantics as model,
    )

    cv = fixture["callback_vector"]
    return model.apply(
        state=fixture["state"],
        userdata=fixture["receiver"],
        record_pointer=produced["fixture"]["record"],
        source_pointer=fixture["source_pointer"],
        callback_entry=fixture["entry"],
        registers=fixture["registers"],
        closure_target=produced["closure"][1],
        closure_upvalues=[produced["closure"][2][1]],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
        vector_pointer=fixture["vector_begin"],
        cookie=cv["cookie"],
        source_word=cv["source_word"],
        destination_word=cv["destination_word"],
        destination_refs=cv["destination_refs"],
        source_refs=cv["source_refs"],
        transfers=cv["transfers"],
    )


class _IdentityPrefix:
    """Actual physical requests interpreted with U/A-bound Lua value identities."""

    def __init__(self, fixture):
        self.fixture = fixture
        self.stack = [("argument", fixture["source_pointer"])]
        self.trace = []

    def apply(self, call, arguments):
        api, group = call["api"], call["group"]
        args = [v - 2**32 if v >= 2**31 else v for v in arguments]
        _require(
            arguments[0] == self.fixture["state"], "factory return Lua state differs"
        )
        before = list(self.stack)
        result = 0
        if api == "lua_touserdata":
            identity = (
                self.fixture["receiver"]
                if args[1] == -10003
                else self.fixture["source_pointer"]
            )
            result = call["response"]["eax"]
            _require(
                result == identity, "factory return supplied userdata identity differs"
            )
        else:
            i = int(group[-1])
            identity = (self.fixture["receiver"], self.fixture["source_pointer"])[i]
            if api == "lua_getmetatable":
                self.stack.append(("metatable", identity))
                result = call["response"]["eax"]
                _require(result == 1, "factory return metatable differs")
            elif api == "lua_pushstring":
                self.stack.append(("marker_key", identity))
            elif api == "lua_gettable":
                _require(
                    self.stack[-2:]
                    == [("metatable", identity), ("marker_key", identity)],
                    "factory return marker identity differs",
                )
                self.stack[-1] = ("marker_value", identity, ("zero", "table")[i])
            elif api == "lua_toboolean":
                _require(
                    self.stack[-1] == ("marker_value", identity, ("zero", "table")[i]),
                    "factory return marker identity differs",
                )
                result = call["response"]["eax"]
                _require(result == 1, "factory return marker truth differs")
            elif api == "lua_settop":
                _require(
                    self.stack[-2:]
                    == [
                        ("metatable", identity),
                        ("marker_value", identity, ("zero", "table")[i]),
                    ],
                    "factory return marker identity differs",
                )
                del self.stack[-2:]
            else:
                raise ConformanceError("factory return unexpected prefix API")
        self.trace.append(
            dict(
                api=api,
                arguments=args,
                result=result,
                before=before,
                after=list(self.stack),
                group=group,
            )
        )


def _run_case(
    codes,
    points,
    fixture,
    produced,
    vector,
    negative=None,
    *,
    logical=None,
    class_module=None,
    capture=None,
    entry_capture=None,
):
    from unicorn import x86_const as x

    logical = _logical(fixture, produced) if logical is None else logical
    class_module = empty if class_module is None else class_module
    observer = _IdentityPrefix(fixture)
    call_cursor = 0
    class_entries = []
    class_returns = []
    heap_entries = []
    free_entries = []
    old_count = fixture["prototype"].get("old_size", 0)
    _require(
        type(old_count) is int
        and (
            old_count in range(4)
            or (old_count == 4 and getattr(class_module, "SIMD_FACTORY", False) is True)
        ),
        "unreviewed factory return vector size",
    )
    normalized = lambda value: json.loads(json.dumps(value))

    def before(m, address, ids, expected, negative):
        nonlocal call_cursor
        if address == BASE + callback.START and entry_capture is not None:
            entry_capture(m, ids, expected)
        regs = lambda: {r: m.reg_read(i) for r, i in ids.items()}
        words = lambda a, n: [
            int.from_bytes(m.mem_read(a + 4 * i, 4), "little") for i in range(n)
        ]
        child = next(c for c in expected["children"] if c["kind"] == "class")
        if address in layout.TARGETS.values():
            _require(
                call_cursor < len(expected["calls"]), "factory return extra Lua API"
            )
            call = expected["calls"][call_cursor]
            if call_cursor < 12:
                observer.apply(
                    call, words(m.reg_read(ids["esp"]) + 4, len(call["arguments"]))
                )
            call_cursor += 1
        if address in (BASE + 0x2EC134, BASE + 0x2EC1A3):
            identity = (
                fixture["receiver"]
                if address == BASE + 0x2EC134
                else fixture["source_pointer"]
            )
            if negative == (
                "upvalue_identity"
                if address == BASE + 0x2EC134
                else "argument_identity"
            ):
                m.reg_write(ids["eax"], identity ^ 1)
            _require(
                m.reg_read(ids["eax"]) == identity,
                "factory return native userdata identity differs",
            )
        if negative == "marker_guard" and address == BASE + 0x2EC160:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) & 0xFFFFFF00)
        if negative == "argument_guard" and address == BASE + 0x2EC184:
            m.reg_write(ids["eax"], m.reg_read(ids["eax"]) & 0xFFFFFF00)
        _require(
            not any(a <= address - BASE < b for a, b in PARENT_EXCLUDED),
            "factory return entered excluded parent arm",
        )
        if address == BASE + empty.START:
            caller = logical["class_caller"]
            prefix = callback._expected(
                dict(
                    frame_alignment=15 * vector["profile"],
                    marker_words=fixture["callback_vector"]["marker_words"],
                ),
                fixture,
                class_module=class_module,
                class_entry_only=True,
            )
            if negative == "class_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x10)
            _require(
                not class_entries
                and regs() == caller["registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == prefix["flags"]
                and words(regs()["esp"], 2)
                == [caller["return_address"], caller["argaddress"]]
                and words(caller["argaddress"], 2) == caller["argument_record"]
                and all(
                    bytes(m.mem_read(p, 4096)) == b
                    for p, b in child["fixture"]["pages"].items()
                ),
                "factory return class entry differs",
            )
            class_entries.append(address)
        if address == layout.HEAP_TARGET:
            sp = m.reg_read(ids["esp"])
            if words(sp, 1) == [0x789172]:
                if negative == "free_register":
                    m.reg_write(ids["edx"], 0)
                if negative == "free_flags":
                    m.reg_write(
                        x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x10
                    )
                request = logical.get("vector_free_request")
                _require(
                    request is not None
                    and not free_entries
                    and words(sp, 4)
                    == [0x789172, request["handle"], 0, request["pointer"]]
                    and regs()
                    == dict(
                        eax=0x1FFFFFFF,
                        ebx=old_count,
                        ecx=request["pointer"],
                        edx=7,
                        esi=fixture["receiver"] + 4,
                        edi=fixture["vector_begin"],
                        ebp=fixture["entry"] - 164,
                        esp=fixture["entry"] - 180,
                    )
                    and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5
                    == int((request["pointer"] & 255).bit_count() % 2 == 0) << 2,
                    "factory return free ABI differs",
                )
                free_entries.append(address)
                return
            tree_count = child["result"].get("tree_heap_count", 0)
            if len(heap_entries) < tree_count:
                if negative == "tree_request":
                    m.mem_write(sp + 12, (25).to_bytes(4, "little"))
                if negative == "tree_register":
                    m.reg_write(ids["esi"], 25)
                if negative == "tree_flags":
                    m.reg_write(
                        x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1
                    )
                _require(
                    words(sp, 4) == [0x789463, 0x12345678, 0, 24]
                    and sp == fixture["entry"] - 192
                    and m.reg_read(ids["eax"]) == fixture["entry"] - 104
                    and m.reg_read(ids["esi"]) == 24
                    and m.reg_read(ids["ebp"]) == fixture["entry"] - 172
                    and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCC5 == 4,
                    "factory return tree heap ABI differs",
                )
                heap_entries.append(address)
                return
            if negative == "heap_register":
                m.reg_write(ids["edx"], 0)
            if negative == "heap_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 1)
            _require(
                len(heap_entries) == tree_count
                and logical["vector"]["capacity"]
                == max(old_count + 1, old_count + old_count // 2)
                and words(sp, 4)
                == [0x789463, 0x12345678, 0, 8 * logical["vector"]["capacity"]]
                and regs()
                == dict(
                    eax=8 * logical["vector"]["capacity"],
                    ebx=0x1FFFFFFF - old_count // 2,
                    ecx=fixture["receiver"] + 4,
                    edx=logical["vector"]["capacity"],
                    esi=8 * logical["vector"]["capacity"],
                    edi=old_count,
                    ebp=fixture["entry"] - 168,
                    esp=fixture["entry"] - 188,
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCC5
                == int((8 * logical["vector"]["capacity"] & 255).bit_count() % 2 == 0)
                << 2,
                "factory return heap ABI differs",
            )
            heap_entries.append(address)
        if address == 0x789172:
            if negative == "free_identity":
                m.reg_write(ids["eax"], 0)
            _require(
                len(free_entries) == 1
                and regs()
                == dict(
                    eax=1,
                    ebx=old_count,
                    ecx=0xA0000001,
                    edx=0xB0000001,
                    esi=fixture["receiver"] + 4,
                    edi=fixture["vector_begin"],
                    ebp=fixture["entry"] - 164,
                    esp=fixture["entry"] - 164,
                )
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == 0xD5,
                "factory return free response identity differs",
            )
        if address == 0x789463:
            if negative == "heap_identity":
                m.reg_write(ids["eax"], fixture["vector_begin"] + 1)
            _require(
                m.reg_read(ids["eax"])
                == child["result"]["heap_nodes"][len(heap_entries) - 1]
                and m.reg_read(ids["ecx"]) == 0xA0000001
                and m.reg_read(ids["edx"]) == 0xB0000001,
                "factory return heap response identity differs",
            )
        if address == first.ENDPOINT:
            _require(
                not class_returns
                and regs() == logical["class_return"]["registers"]
                and m.reg_read(x.UC_X86_REG_EFLAGS) & 0xCD5 == 0x44
                and all(
                    bytes(m.mem_read(p, 4096)) == b
                    for p, b in child["result"]["pages"].items()
                ),
                "factory return class return differs",
            )
            class_returns.append(address)
        if address == fixture["endpoint"]:
            corrupt = {
                "sentinel_padding": produced["fixture"]["record"] + 23,
                "factory_reference": fixture["receiver"] + 32,
                "source_padding": empty.SOURCE_HEAD + 14,
                "cookie_page": factory.COOKIE,
            }
            if negative in corrupt:
                a = corrupt[negative]
                m.mem_write(a, bytes([m.mem_read(a, 1)[0] ^ 1]))
            if negative == "return_cookie":
                m.reg_write(ids["ecx"], m.reg_read(ids["ecx"]) ^ 1)
            if negative == "return_flags":
                m.reg_write(x.UC_X86_REG_EFLAGS, m.reg_read(x.UC_X86_REG_EFLAGS) ^ 0x10)

    def verify_return(m, ids, expected, lua):
        _require(
            len(class_entries) == len(class_returns) == 1
            and len(free_entries) == int("vector_free_request" in logical)
            and len(heap_entries)
            == len(
                next(c for c in expected["children"] if c["kind"] == "class")["result"][
                    "heap_nodes"
                ]
            ),
            "factory return native boundary count differs",
        )
        _require(
            {r: m.reg_read(i) for r, i in ids.items()}
            == logical["full_return"]["registers"]
            and expected["flags"] == logical["full_return"]["flags"]
            and m.reg_read(x.UC_X86_REG_EFLAGS) & logical["full_return"]["flag_mask"]
            == logical["full_return"]["flags"],
            "factory return independent normal ABI differs",
        )
        actual_trace = copy.deepcopy(lua.trace)
        for call in actual_trace:
            for key in ("before", "after"):
                call[key] = [
                    (
                        ("argument", fixture["source_pointer"])
                        if tuple(t) == ("argument", 0)
                        else t
                    )
                    for t in call[key]
                ]
        final_stack = [
            (
                ("argument", fixture["source_pointer"])
                if tuple(t) == ("argument", 0)
                else t
            )
            for t in lua.stack
        ]
        _require(
            normalized(observer.trace) == normalized(logical["prefix_calls"])
            and normalized(actual_trace) == normalized(logical["registry_table_calls"])
            and normalized(final_stack)
            == normalized(logical["normal_final_lua_stack"]),
            "factory return independent identity request trace differs",
        )
        _require(
            all(
                int.from_bytes(m.mem_read(fixture["receiver"] + o, 4), "little") == v
                for o, v in logical["normal_field_updates"].items()
            ),
            "factory return independent field updates differ",
        )
        if capture is not None:
            capture(m, ids, expected, lua)

    try:
        result = callback._run_case(
            codes,
            points,
            fixture["callback_vector"],
            negative,
            class_module=class_module,
            fixture=fixture,
            continuation=dict(before_instruction=before, verify_return=verify_return),
        )
    except callback.ConformanceError as exc:
        raise ConformanceError(str(exc)) from exc
    if negative == "cookie":
        return result
    return dict(
        result,
        vector=vector,
        factory_pages_sha256=_canonical_sha256(
            {
                str(p): hashlib.sha256(b).hexdigest()
                for p, b in produced["pages"].items()
            }
        ),
        host_patches_sha256=_canonical_sha256(fixture["patches"]),
        identity_prefix_sha256=_canonical_sha256(normalized(observer.trace)),
    )


def _load_code(data, image, sources):
    payload, fp, continuation, _, _ = first._load_code(data, image, sources)
    codes, points = callback._load_code(
        data, image, dict(sources, class_spare=sources["class_empty"])
    )
    return payload, fp, continuation, codes, points


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS),
        "factory callback return source partition differs",
    )
    return {
        k: factory._source_identity(sources[k], *pin, k)
        for k, pin in SOURCE_PINS.items()
    }


CONTROLS = {
    **{k: "callback ancestor memory differs" for k in ("ancestor", "record")},
    **{
        k: "callback protected memory differs"
        for k in (
            "word",
            "reference",
            "literal",
            "iat",
            "vector",
            "capacity",
            "sentinel_padding",
            "factory_reference",
            "source_padding",
            "cookie_page",
        )
    },
    **{
        k: "callback registers or flags differ"
        for k in ("result", "return_cookie", "return_flags")
    },
    "lua_prefix": "callback Lua request trace differs",
    "heap_request": "callback heap handoff differs",
    "upvalue_identity": "factory return native userdata identity differs",
    "argument_identity": "factory return native userdata identity differs",
    "marker_guard": "factory return entered excluded parent arm",
    "argument_guard": "factory return entered excluded parent arm",
    "class_flags": "factory return class entry differs",
    "heap_register": "factory return heap ABI differs",
    "heap_flags": "factory return heap ABI differs",
    "heap_identity": "factory return heap response identity differs",
}


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = full._load_executable(Path(executable))
    _require(
        digest == full.EXE_SHA256 and image.image_base == BASE,
        "exact factory callback return executable differs",
    )
    payload, fp, continuation, codes, points = _load_code(data, image, sources)
    observations, producer = [], []
    sample = None
    for vector in vectors():
        produced, observation = first._produce(
            payload, fp, continuation, _first_vector(vector)
        )
        fixture = _resume(produced, vector)
        observations.append(_run_case(codes, points, fixture, produced, vector))
        producer.append(observation)
        if vector["profile"] == 1 and vector["transfer_profile"] == 4:
            sample = (produced, fixture, vector)
    controls = []
    for kind, reason in CONTROLS.items():
        try:
            _run_case(codes, points, sample[1], sample[0], sample[2], kind)
        except ConformanceError as exc:
            _require(
                str(exc) == reason,
                "factory callback return incidental control: " + kind + ": " + str(exc),
            )
            controls.append(dict(kind=kind, rejected=True, reason=reason))
        else:
            raise ConformanceError("factory callback return control survived: " + kind)
    failure = _run_case(codes, points, sample[1], sample[0], sample[2], "cookie")
    _require(
        failure == dict(kind="cookie", rejected=True, endpoint="0x003574d5"),
        "factory callback cookie failure differs",
    )
    controls.append(dict(failure, kind="native_callback_cookie"))
    union = sorted({r for o in observations for r in o["trace_rvas"]})
    parent_sites = {
        p["rva"]
        for p in points
        if callback.START <= int(p["rva"], 16) < callback.END
        and not any(a <= int(p["rva"], 16) < b for a, b in PARENT_EXCLUDED)
    }
    class_sites = set(
        sources["factory_empty_class"]["normal_site_partition"]["empty_class"]
    )
    marker_sites = set(
        sources["factory_empty_class"]["normal_site_partition"]["callback_and_markers"]
    ) - {p["rva"] for p in points if callback.START <= int(p["rva"], 16) < callback.END}
    table_sites = set(sources["table"]["executed_rvas"])
    _require(
        set(union) == parent_sites | class_sites | marker_sites | table_sites,
        "factory callback return normal site partition differs",
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
                    end_rva=f"0x{a+len(b):08x}",
                    sha256=hashlib.sha256(b).hexdigest(),
                )
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        executed_rvas=union,
        normal_site_partition=dict(
            callback=sorted(parent_sites),
            empty_class=sorted(class_sites),
            markers=sorted(marker_sites),
            tables=sorted(table_sites),
            excluded=sorted({p["rva"] for p in points} - set(union)),
        ),
        negative_controls=controls,
        observations_sha256=_canonical_sha256(observations),
        producer_observations_sha256=_canonical_sha256(producer),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        summary=dict(
            cases=len(observations),
            static_sites=len(points),
            executed_sites=len(union),
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            factory_instructions=sum(len(o["trace_rvas"]) for o in producer),
            callback_instructions=sum(len(o["trace_rvas"]) for o in observations),
            factory_api_calls=34 * len(observations),
            callback_api_calls=sum(o["api_calls"] for o in observations),
            factory_heap_calls=len(observations),
            class_heap_calls=sum(len(o["allocations"]) for o in observations),
            marker_calls=2 * len(observations),
            table_calls=2 * len(observations),
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in observations
            ),
            retained_lua_values=5,
            result_count=0,
            tree_insertions=0,
            free_calls=0,
            controls=len(controls),
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_factory=True,
            continuous_callback_and_all_helpers=True,
            continuous_across_host=False,
            checked=[
                "Actual produced receiver sentinel references and cookie retained",
                "Native marker class first-null growth and two table helpers through normal callback return",
                "All data pages ordered events API frames GPRs defined flags and identity bound requests",
                "Original pair appended filtered assignment requests and source word copied",
            ],
            premises=[
                "Explicit supplied host closure invocation and empty source object",
                "Source class word and two references supplied by named byte patches",
                "Compatible successful heap registry and Lua responses",
            ],
            excluded=[
                "Real Lua VM registry table and metamethod effects",
                "Nonempty tree transfer key strings insertion and successor traversal",
                "Heap ownership assertion delivery and global accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "factory callback return executable changed",
    )
    first.entry._assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    first.entry._validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed factory callback return differs",
    )
    first.entry._assert_publication_safe(evidence)
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
        "exact factory callback return differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = first.encode_conformance
