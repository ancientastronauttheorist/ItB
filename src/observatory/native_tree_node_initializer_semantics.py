"""Conditional node-head stores after one explicitly opaque normal return."""

from __future__ import annotations
import hashlib, json
from pathlib import Path
from collections.abc import Mapping
import capstone.x86_const as x86
from src.observatory import native_allocation_retry_semantics as retry
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _canonical_bytes,
    _canonical_sha256,
    _source_identity,
    _validate_json_tree,
    _assert_publication_safe,
    _load_executable,
    _decode_body,
    _point,
)

ANALYSIS_KIND = "pe_native_tree_node_initializer_semantics"
SEALED_SHA256 = "445d6993772da858de7bfb28b0852ceb5201922cfe024c847cfd6c1f36d45a85"
SOURCE_PINS = {
    "program_facts": retry.SOURCE_PINS["program_facts"],
    "retry_semantics": (retry.ANALYSIS_KIND, retry.SEALED_SHA256),
}
START, END, CALL, TARGET = 0x7D060, 0x7D093, 0x7D066, 0x3574DB
U32 = 0xFFFFFFFF
SOURCE = 0x10001000
OPS = {
    512096: ("push", ("reg", "esi")),
    512097: ("push", ("reg", "edi")),
    512098: ("push", ("imm", 24)),
    512100: ("mov", ("reg", "edi"), ("reg", "ecx")),
    512102: ("call", ("imm", 7697627)),
    512107: ("mov", ("reg", "esi"), ("reg", "eax")),
    512109: ("add", ("reg", "esp"), ("imm", 4)),
    512112: ("test", ("reg", "esi"), ("reg", "esi")),
    512114: ("je", ("imm", 4706424)),
    512116: ("mov", ("reg", "edx"), ("mem", "edi", 0, 4)),
    512118: ("mov", ("mem", "esi", 0, 4), ("reg", "edx")),
    512120: ("lea", ("reg", "ecx"), ("mem", "esi", 4, 4)),
    512123: ("test", ("reg", "ecx"), ("reg", "ecx")),
    512125: ("je", ("imm", 4706435)),
    512127: ("mov", ("reg", "eax"), ("mem", "edi", 0, 4)),
    512129: ("mov", ("mem", "ecx", 0, 4), ("reg", "eax")),
    512131: ("lea", ("reg", "ecx"), ("mem", "esi", 8, 4)),
    512134: ("test", ("reg", "ecx"), ("reg", "ecx")),
    512136: ("je", ("imm", 4706446)),
    512138: ("mov", ("reg", "eax"), ("mem", "edi", 0, 4)),
    512140: ("mov", ("mem", "ecx", 0, 4), ("reg", "eax")),
    512142: ("pop", ("reg", "edi")),
    512143: ("mov", ("reg", "eax"), ("reg", "esi")),
    512145: ("pop", ("reg", "esi")),
    512146: ("ret",),
}
SIZES = {
    512096: 1,
    512097: 1,
    512098: 2,
    512100: 2,
    512102: 5,
    512107: 2,
    512109: 3,
    512112: 2,
    512114: 2,
    512116: 2,
    512118: 2,
    512120: 3,
    512123: 2,
    512125: 2,
    512127: 2,
    512129: 2,
    512131: 3,
    512134: 2,
    512136: 2,
    512138: 2,
    512140: 2,
    512142: 1,
    512143: 2,
    512145: 1,
    512146: 1,
}
WIDTHS = {
    512096: [4],
    512097: [4],
    512098: [4],
    512100: [4, 4],
    512102: [4],
    512107: [4, 4],
    512109: [4, 4],
    512112: [4, 4],
    512114: [4],
    512116: [4, 4],
    512118: [4, 4],
    512120: [4, 4],
    512123: [4, 4],
    512125: [4],
    512127: [4, 4],
    512129: [4, 4],
    512131: [4, 4],
    512134: [4, 4],
    512136: [4],
    512138: [4, 4],
    512140: [4, 4],
    512142: [4],
    512143: [4, 4],
    512145: [4],
    512146: [],
}


class InitializerError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise InitializerError(message)


def _u32(value):
    _require(type(value) is int and 0 <= value <= U32, "invalid unsigned word")


def _normalize(fn):
    try:
        return fn()
    except InitializerError:
        raise
    except Exception as exc:
        raise InitializerError(str(exc)) from exc


def _logic(value):
    return dict(
        cf=0,
        pf=int((value & 255).bit_count() % 2 == 0),
        af=None,
        zf=int(value == 0),
        sf=value >> 31,
        of=0,
    )


def storage_spec(pointer, source_address, initial_memory):
    _u32(pointer)
    _u32(source_address)
    _require(source_address + 4 <= 1 << 32, "source word crosses address boundary")
    _require(
        isinstance(initial_memory, Mapping)
        and all(
            type(a) is int and 0 <= a <= U32 and type(b) is int and 0 <= b <= 255
            for a, b in initial_memory.items()
        ),
        "invalid byte storage",
    )
    memory = dict(initial_memory)
    events = []
    values = []
    for offset in (0, 4, 8):
        destination = (pointer + offset) & U32
        if not destination:
            continue
        _require(
            destination + 4 <= 1 << 32, "destination word crosses address boundary"
        )
        _require(
            all(
                source_address + i in memory and destination + i in memory
                for i in range(4)
            ),
            "unmapped conditional field",
        )
        value = int.from_bytes(
            bytes(memory[source_address + i] for i in range(4)), "little"
        )
        events.append(
            dict(
                kind="read",
                address=source_address,
                width=4,
                value=value,
                origin="native",
            )
        )
        events.append(
            dict(
                kind="write", address=destination, width=4, value=value, origin="native"
            )
        )
        memory.update(
            {destination + i: b for i, b in enumerate(value.to_bytes(4, "little"))}
        )
        values.append(dict(offset=offset, address=destination, value=value))
    return dict(
        memory=memory,
        events=events,
        stores=values,
        ecx=(pointer + 8) & U32,
        flags=_logic((pointer + 8) & U32),
    )


def fresh_block_spec(pointer, head, source_address=SOURCE):
    _u32(pointer)
    _u32(head)
    _u32(source_address)
    _require(
        pointer != 0 and pointer + 24 <= 1 << 32 and source_address + 4 <= 1 << 32,
        "invalid nonwrapping fresh block",
    )
    _require(
        pointer + 24 <= source_address or source_address + 4 <= pointer,
        "fresh block aliases source",
    )
    return dict(
        pointer=pointer,
        initialized_offsets=[0, 4, 8],
        initialized_bytes=list(head.to_bytes(4, "little") * 3),
        untouched_offsets=list(range(12, 24)),
    )


def _sample(seed, volatile=None):
    _u32(seed)
    if volatile is None:
        return dict(
            ecx=(0xAABB0000 + seed) & U32,
            edx=(0xCCDD0000 + seed) & U32,
            flags=(seed * 0x2D5) & 0x8D5,
        )
    _require(
        type(volatile) is dict and set(volatile) == {"ecx", "edx", "flags"},
        "invalid opaque volatile fields",
    )
    for value in volatile.values():
        _u32(value)
    _require(volatile["flags"] & ~0x8D5 == 0, "opaque flags outside arithmetic mask")
    return dict(volatile)


def case_fixture(
    pointer,
    head=0x11223344,
    frame_alignment=0,
    seed=1,
    source_address=SOURCE,
    df=0,
    volatile=None,
):
    for value in (pointer, head, source_address, seed):
        _u32(value)
    _require(
        type(frame_alignment) is int and 0 <= frame_alignment < 16,
        "invalid frame alignment",
    )
    _require(type(df) is int and df in (0, 1), "invalid direction flag")
    _require(source_address + 4 <= 1 << 32, "source crosses address boundary")
    s = 0x30001000 + frame_alignment
    protected = [
        (s - 20, s + 8),
        (BASE + (START & ~0xFFF), BASE + (START & ~0xFFF) + 0x1000),
        (BASE + (TARGET & ~0xFFF), BASE + (TARGET & ~0xFFF) + 0x1000),
        (0x04000000, 0x04001000),
    ]
    destinations = [(pointer + i) & U32 for i in (0, 4, 8) if (pointer + i) & U32]
    for at in [source_address] + destinations:
        _require(
            at + 4 <= 1 << 32 and all(at + 4 <= a or b <= at for a, b in protected),
            "data aliases protected storage or crosses word boundary",
        )
    regs = {
        r: (0xA1000000 + i * 0x10101 + seed) & U32
        for i, r in enumerate(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"))
    }
    regs.update(ecx=source_address, esp=s)
    memory = {s + i: ((i * 23) ^ seed) & 255 for i in range(-20, 8)}
    for at in [source_address] + destinations:
        for address in range(max(0, at - 4), min(1 << 32, at + 28)):
            _require(
                all(not (a <= address < b) for a, b in protected),
                "fixture data guard overlaps protected storage",
            )
            memory[address] = ((address * 37) ^ (address >> 3) ^ seed) & 255
    memory.update(
        {source_address + i: b for i, b in enumerate(head.to_bytes(4, "little"))}
    )
    memory.update({s + i: b for i, b in enumerate((0x04000000).to_bytes(4, "little"))})
    sample = _sample(seed, volatile)
    return dict(
        registers=regs,
        memory=memory,
        stack=s,
        return_address=0x04000000,
        sample=sample,
        df=df,
    )


def model_case(
    pointer,
    head=0x11223344,
    frame_alignment=0,
    seed=1,
    source_address=SOURCE,
    df=0,
    volatile=None,
    ops=None,
):
    fixture = case_fixture(
        pointer, head, frame_alignment, seed, source_address, df, volatile
    )
    initial = fixture["registers"]
    s = fixture["stack"]
    sample = fixture["sample"]
    storage = storage_spec(pointer, source_address, fixture["memory"])
    expected_memory = dict(storage["memory"])
    expected_events = []

    def expected(kind, at, value, origin="native"):
        expected_events.append(
            dict(kind=kind, address=at, width=4, value=value, origin=origin)
        )
        if kind == "write":
            expected_memory.update(
                {at + i: b for i, b in enumerate(value.to_bytes(4, "little"))}
            )

    expected("write", s - 4, initial["esi"])
    expected("write", s - 8, initial["edi"])
    expected("write", s - 12, 24)
    expected("write", s - 16, BASE + 0x7D06B)
    expected("read", s - 16, BASE + 0x7D06B, "opaque_return")
    expected_events.extend(storage["events"])
    expected("read", s - 8, initial["edi"])
    expected("read", s - 4, initial["esi"])
    expected("read", s, fixture["return_address"])
    wanted = dict(
        initial,
        eax=pointer,
        ecx=(pointer + 8) & U32,
        edx=storage["stores"][0]["value"] if pointer else sample["edx"],
        esp=s + 4,
    )
    regs = dict(initial)
    memory = dict(fixture["memory"])
    flags = None
    pc = START
    trace = []
    events = []
    operations = OPS if ops is None else ops

    def access(at, origin="native"):
        _require(all(at + i in memory for i in range(4)), "unmapped initializer read")
        value = int.from_bytes(bytes(memory[at + i] for i in range(4)), "little")
        events.append(
            dict(kind="read", address=at, width=4, value=value, origin=origin)
        )
        return value

    def read(arg):
        if arg[0] == "imm":
            return arg[1] & U32
        if arg[0] == "reg":
            return regs[arg[1]]
        return access((regs[arg[1]] + arg[2]) & U32)

    def write(arg, value):
        if arg[0] == "reg":
            regs[arg[1]] = value & U32
            return
        at = (regs[arg[1]] + arg[2]) & U32
        _require(all(at + i in memory for i in range(4)), "unmapped initializer write")
        memory.update({at + i: b for i, b in enumerate(value.to_bytes(4, "little"))})
        events.append(
            dict(kind="write", address=at, width=4, value=value, origin="native")
        )

    while True:
        _require(pc in operations and len(trace) < 50, "initializer escaped graph")
        trace.append(f"0x{pc:08x}")
        op, *args = operations[pc]
        nxt = pc + SIZES[pc]
        if op == "push":
            value = read(args[0])
            regs["esp"] -= 4
            write(("mem", "esp", 0, 4), value)
        elif op == "pop":
            write(args[0], access(regs["esp"]))
            regs["esp"] += 4
        elif op == "mov":
            write(args[0], read(args[1]))
        elif op == "lea":
            write(args[0], (regs[args[1][1]] + args[1][2]) & U32)
        elif op == "add":
            left, right = read(args[0]), read(args[1])
            value = (left + right) & U32
            flags = dict(
                cf=int(left + right > U32),
                pf=int((value & 255).bit_count() % 2 == 0),
                af=((left ^ right ^ value) >> 4) & 1,
                zf=int(value == 0),
                sf=value >> 31,
                of=(~(left ^ right) & (left ^ value) & U32) >> 31,
            )
            write(args[0], value)
        elif op == "test":
            flags = _logic(read(args[0]) & read(args[1]))
        elif op in ("je", "jne"):
            if bool(flags["zf"]) == (op == "je"):
                nxt = read(args[0]) - BASE
        elif op == "call":
            _require(read(args[0]) == BASE + TARGET, "opaque target differs")
            regs["esp"] -= 4
            write(("mem", "esp", 0, 4), BASE + nxt)
            continuation = access(regs["esp"], "opaque_return")
            _require(continuation == BASE + nxt, "opaque continuation differs")
            regs.update(
                eax=pointer, ecx=sample["ecx"], edx=sample["edx"], esp=regs["esp"] + 4
            )
            flags = {
                name: int(bool(sample["flags"] & bit))
                for name, bit in (
                    ("cf", 1),
                    ("pf", 4),
                    ("af", 16),
                    ("zf", 64),
                    ("sf", 128),
                    ("of", 2048),
                )
            }
        elif op == "ret":
            returned = access(regs["esp"])
            regs["esp"] += 4
            break
        else:
            raise InitializerError("unsupported initializer operation")
        pc = nxt
    _require(
        regs == wanted and flags == storage["flags"],
        "initializer register or flag oracle differs",
    )
    _require(
        memory == expected_memory and events == expected_events,
        "initializer alias or ordered memory oracle differs",
    )
    _require(returned == fixture["return_address"], "initializer return differs")
    return dict(
        registers=regs,
        arithmetic_flags=flags,
        df=df,
        events=events,
        stores=storage["stores"],
        trace_rvas=trace,
        memory_sha256=_canonical_sha256([list(i) for i in sorted(memory.items())]),
    )


def vectors():
    pointers = (
        [0, 4, 8, 0xFFFFFFF8, 0xFFFFFFFC]
        + [0x20002000 + i for i in range(16)]
        + [SOURCE + i for i in range(-11, 5)]
    )
    return [
        dict(
            pointer=p,
            head=h,
            frame_alignment=f,
            seed=seed,
            source_address=SOURCE,
            df=df,
        )
        for p in pointers
        for h in (0, 0x11223344, 0xFFFFFFFF)
        for f in (0, 1, 7, 15)
        for seed in (0, 255)
        for df in (0, 1)
    ]


def _preflight(sources):
    _require(
        isinstance(sources, Mapping) and set(sources) == set(SOURCE_PINS),
        "source partition differs",
    )
    return {
        k: _source_identity(sources[k], kind, digest, k)
        for k, (kind, digest) in SOURCE_PINS.items()
    }


def _grammar(rows):
    _require([r.address - BASE for r in rows] == list(OPS), "initializer points differ")
    for row in rows:
        args = []
        for arg in row.operands:
            if arg.type == x86.X86_OP_REG:
                args.append(("reg", row.reg_name(arg.reg)))
            elif arg.type == x86.X86_OP_IMM:
                args.append(("imm", arg.imm))
            else:
                _require(
                    arg.type == x86.X86_OP_MEM
                    and not arg.mem.segment
                    and not arg.mem.index
                    and arg.mem.scale == 1,
                    "unexpected memory operand",
                )
                args.append(("mem", row.reg_name(arg.mem.base), arg.mem.disp, arg.size))
        pc = row.address - BASE
        _require(
            (row.mnemonic, *args) == OPS[pc]
            and row.size == SIZES[pc]
            and [a.size for a in row.operands] == WIDTHS[pc],
            "initializer exact grammar differs",
        )


def _build_unsealed(executable, sources):
    ids = _preflight(sources)
    data, image, digest = _load_executable(executable)
    _require(
        digest == EXE_SHA256 and image.image_base == BASE, "exact executable differs"
    )
    rows = _decode_body(data, image, sources["program_facts"], START)
    _grammar(rows)
    retry_rows = _decode_body(data, image, sources["program_facts"], TARGET)
    _require(
        [_point(r) for r in retry_rows] == sources["retry_semantics"]["body"]["points"],
        "retry provenance differs",
    )
    owner = _decode_body(data, image, sources["program_facts"], 0x7CD90)
    edge = next(r for r in owner if r.address - BASE == 0x7CD93)
    _require(
        edge.id == x86.X86_INS_CALL and edge.operands[0].imm == BASE + START,
        "factory incoming edge differs",
    )
    cases = []
    for vector in vectors():
        case = model_case(**vector)
        cases.append(dict(sha256=_canonical_sha256(case), trace=case["trace_rvas"]))
    union = sorted({p for c in cases for p in c["trace"]})
    _require(union == [f"0x{p:08x}" for p in OPS], "initializer coverage differs")
    controls = []
    for name, pc, operation, pointer in [
        (
            "cached_head_breaks_alias_feedback",
            0x7D07F,
            ("mov", ("reg", "eax"), ("reg", "edx")),
            SOURCE - 1,
        ),
        ("wrong_null_guard", 0x7D072, ("jne", ("imm", BASE + 0x7D078)), 0),
        (
            "wrong_return_pointer",
            0x7D08F,
            ("mov", ("reg", "eax"), ("imm", 0)),
            0x20002000,
        ),
    ]:
        changed = dict(OPS)
        changed[pc] = operation
        try:
            model_case(pointer, ops=changed)
        except InitializerError:
            controls.append(dict(name=name, rejected=True))
        else:
            raise InitializerError("initializer mutation accepted")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=sources["program_facts"]["identity"],
        source_receipts=ids,
        body=dict(
            entry_rva=f"0x{START:08x}",
            bytes=51,
            nodes=25,
            points=[_point(r) for r in rows],
        ),
        static_lineage=dict(
            factory_entry_rva="0x0007cd90",
            factory_points=[_point(r) for r in owner],
            incoming_call=_point(edge),
            opaque_call=_point(next(r for r in rows if r.address - BASE == CALL)),
            opaque_target_rva=f"0x{TARGET:08x}",
        ),
        vectors=vectors(),
        model_evidence=dict(
            cases_sha256=_canonical_sha256(cases),
            instruction_union_rvas=union,
            negative_controls=controls,
        ),
        summary=dict(
            cases=len(cases),
            modeled_nodes=25,
            modeled_bytes=51,
            opaque_normal_returns=len(cases),
            actual_callee_executions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            premises=[
                "One supplied normal cdecl return from retry target with EAX pointer and sampled ECX EDX arithmetic flags",
                "Opaque summary preserves every modeled byte and nonvolatile register plus DF, including all ancestor frame, source and prospective destination storage except native CALL continuation write",
                "All actual source and destination DWORDs are mapped and do not cross the 32 bit address boundary, disjoint from protected frame and code; source-destination partial aliases are explicitly allowed",
                "Finite frame base is 0x30001000 and declared alignments",
            ],
            machine_relation="For each modular address P P+4 P+8, skip only a zero address; otherwise reread the source head DWORD then store it, preserving ordered byte alias feedback",
            ordinary_corollary="For a nonnull nonwrapping fresh 24 byte block disjoint from source and frame, offsets zero four eight equal the original head word and offsets twelve through twenty-three stay unchanged",
            registers="EAX returns P and ECX is modular P+8; EDX is the first head read when P is nonzero, otherwise the supplied opaque EDX; saved registers restore and ESP advances four",
            flags="Final TEST of modular P+8 defines CF and OF zero, sign, zero and parity from its result, and leaves AF undefined; DF preserves",
            synthetic_cases="P zero still stores at four and eight; P fffffff8 and fffffffc skip individual modular zero fields under explicit low and high mapped storage premises; these are not inferred reachable allocator outputs",
            event_policy="Native instruction accesses and CALL continuation write are distinct from the opaque normal-return continuation read",
            not_claimed=[
                "Actual allocation, harmless null behavior, opaque callee implementation, or factory composition",
                "Invalid word-crossing accesses, unmapped storage, code or frame aliases, or accounting promotion",
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
    def run():
        _validate_json_tree(evidence, "evidence")
        ids = _preflight(sources)
        _require(
            _canonical_sha256(evidence) == SEALED_SHA256
            and evidence["source_receipts"] == ids,
            "sealed initializer differs",
        )
        _assert_publication_safe(evidence)
        return dict(
            status="structurally_verified",
            evidence_sha256=SEALED_SHA256,
            summary=evidence["summary"],
        )

    return _normalize(run)


def build_semantics(executable, sources):
    def run():
        result = _build_unsealed(executable, sources)
        validate_structure(result, sources)
        return result

    return _normalize(run)


def validate_semantics(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_semantics(executable, sources))
        == _canonical_bytes(evidence),
        "exact initializer differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_semantics(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
