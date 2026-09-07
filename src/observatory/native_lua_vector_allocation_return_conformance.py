"""Exact post-call allocation tails under mapped, disjoint storage premises."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
import capstone
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _point,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_vector_allocation_return_conformance"
SEALED_SHA256 = "681ff7aec2526a193fb0f9c1498dd002e5848d47e9b248186e1a938897327ff6"
TAILS = {"large": (0x8A950, 0x8A962), "small": (0x8A968, 0x8A971)}
STACK, RETURN = 0x2000000, 0x4000000
MASK = 0xFFFFFFFF


class ConformanceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise ConformanceError(message)


def vectors():
    pointers = sorted(
        {b + i for b in [0, 0x50001000, 0xFFFFFFC0] for i in range(32)}
        | {0xFFFFFFE0, 0xFFFFFFFC, 0xFFFFFFFF}
    )
    return [
        dict(path=path, pointer=p, alignment=a)
        for path in TAILS
        for p in pointers
        for a in [0, 1, 7, 15]
    ]


def pointer_oracle(pointer):
    _require(type(pointer) is int and 0 <= pointer <= MASK, "invalid pointer")
    # Integer ceiling formulation, independently reduced modulo the address space.
    aligned = (((pointer + 4 + 31) // 32) * 32) & MASK
    return dict(aligned=aligned, metadata=(aligned - 4) & MASK)


def _add_flags(left, right):
    total = left + right
    result = total & MASK
    return (
        int(total > MASK)
        | (int((result & 255).bit_count() % 2 == 0) << 2)
        | ((left ^ right ^ result) & 16)
        | (int(result == 0) << 6)
        | ((result >> 31) << 7)
        | (((~(left ^ right) & (left ^ result)) >> 31) & 1) << 11
    )


def _run_case(code, points, vector, *, negative=False):
    import unicorn as uc
    from unicorn import x86_const as x

    _require(uc.__version__ == "2.1.4", "reviewed Unicorn required")
    path, pointer = vector["path"], vector["pointer"]
    start, end = TAILS[path]
    expected = pointer_oracle(pointer)
    frame = STACK + 0x2000 + vector["alignment"]
    machine = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
    machine.mem_map(BASE + 0x8A000, 0x1000)
    machine.mem_write(BASE + start, code)
    machine.mem_map(STACK, 0x4000)
    machine.mem_map(RETURN, 0x1000)
    original = bytearray(((i * 19) ^ (i >> 5) ^ 0xA9) & 255 for i in range(0x4000))
    saved = 0xACDC1234
    original[frame - STACK : frame - STACK + 4] = saved.to_bytes(4, "little")
    original[frame - STACK + 4 : frame - STACK + 8] = RETURN.to_bytes(4, "little")
    machine.mem_write(STACK, bytes(original))
    page = expected["metadata"] & ~0xFFF
    payload = bytearray(((i * 31) ^ (i >> 2) ^ 0x79) & 255 for i in range(0x1000))
    if path == "large":
        _require(
            page not in range(STACK, STACK + 0x4000, 0x1000) and page != RETURN,
            "metadata aliases protected frame",
        )
        machine.mem_map(page, 0x1000)
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
    initial = {name: (0x16325478 + i * 0x1010101) & MASK for i, name in enumerate(ids)}
    initial.update(eax=pointer, ebp=frame, esp=frame - 4)
    for name, value in initial.items():
        machine.reg_write(ids[name], value)
    machine.reg_write(x.UC_X86_REG_EFLAGS, 2)
    if negative:
        machine.reg_write(x.UC_X86_REG_EAX, (pointer + 1) & MASK)
    visited, events = [], []
    allowed = {int(p["rva"], 16) for p in points}

    def on_code(m, address, size, user):
        _require(address - BASE in allowed, "execution escaped tail")
        visited.append(f"0x{address-BASE:08x}")

    def on_memory(m, access, address, size, value, user):
        write = access == uc.UC_MEM_WRITE
        if write:
            _require(
                path == "large" and address == expected["metadata"] and size == 4,
                "metadata oracle address differs",
            )
        else:
            _require(
                address in [frame, frame + 4] and size == 4, "unexpected return read"
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
    machine.emu_start(BASE + start, RETURN, count=30)
    result_pointer = expected["aligned"] if path == "large" else pointer
    wanted = dict(
        initial, eax=result_pointer, ecx=result_pointer, ebp=saved, esp=frame + 12
    )
    actual = {name: machine.reg_read(reg) for name, reg in ids.items()}
    _require(actual == wanted, "return pointer oracle registers differ")
    _require(machine.reg_read(x.UC_X86_REG_EIP) == RETURN, "return address differs")
    if path == "large":
        flags = (
            int(result_pointer == 0) * 64
            | int((result_pointer & 255).bit_count() % 2 == 0) * 4
            | (result_pointer >> 31) * 128
        )
        flagmask = 0x8C5
    else:
        flags = _add_flags(frame - 4, 4)
        flagmask = 0x8D5
    _require(
        machine.reg_read(x.UC_X86_REG_EFLAGS) & flagmask == flags,
        "defined tail flags differ",
    )
    expected_events = []
    if path == "large":
        offset = expected["metadata"] - page
        payload[offset : offset + 4] = pointer.to_bytes(4, "little")
        _require(
            bytes(machine.mem_read(page, 0x1000)) == bytes(payload),
            "metadata pointer oracle differs",
        )
        expected_events.append(
            dict(access="write", address=expected["metadata"], width=4, value=pointer)
        )
    expected_events += [
        dict(access="read", address=frame, width=4, value=saved),
        dict(access="read", address=frame + 4, width=4, value=RETURN),
    ]
    _require(events == expected_events, "ordered tail memory differs")
    _require(
        bytes(machine.mem_read(STACK, 0x4000)) == bytes(original),
        "protected frame changed",
    )
    return dict(
        vector=vector,
        visited=visited,
        registers=actual,
        flags=flags,
        flag_mask=flagmask,
        events_sha256=_canonical_sha256(events),
    )


def _build_unsealed(executable, semantics):
    from src.observatory import native_lua_vector_allocation_return_semantics as sem

    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(semantics) == sem.SEALED_SHA256, "return semantics differs"
    )
    data, image, digest = _load_executable(executable)
    _require(
        capstone.__version__ == "5.0.7"
        and digest == EXE_SHA256
        and image.image_base == BASE,
        "exact build differs",
    )
    codes, points = {}, {}
    for path, (start, end) in TAILS.items():
        offset = image.rva_to_file_offset(start)
        codes[path] = data[offset : offset + end - start]
        points[path] = [
            _point(r)
            for r in capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
                codes[path], BASE + start
            )
        ]
    _require(sum(len(p) for p in points.values()) == 11, "tail node count differs")
    # Exact byte hashes bind the same immutable body; the source receipt validates tail membership.
    whole_offset = image.rva_to_file_offset(0x8A920)
    whole = data[whole_offset : whole_offset + 91]
    _require(
        hashlib.sha256(whole).hexdigest() == semantics["body"]["sha256"],
        "source allocation body differs",
    )
    observations = [
        _run_case(codes[v["path"]], points[v["path"]], v) for v in vectors()
    ]
    caught = False
    try:
        _run_case(
            codes["large"],
            points["large"],
            dict(path="large", pointer=0x50001000, alignment=0),
            negative=True,
        )
    except ConformanceError as exc:
        caught = "metadata pointer oracle" in str(exc)
    _require(caught, "changed pointer control accepted")
    visited = sorted({pc for row in observations for pc in row["visited"]})
    _require(len(visited) == 11, "tail coverage differs")
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        build_identity=semantics["build_identity"],
        source_semantics_sha256=sem.SEALED_SHA256,
        tails={
            path: dict(
                entry_rva=f"0x{start:08x}",
                exclusive_end_rva=f"0x{end:08x}",
                bytes=end - start,
                points=points[path],
                sha256=hashlib.sha256(codes[path]).hexdigest(),
            )
            for path, (start, end) in TAILS.items()
        },
        emulator=dict(
            name="Unicorn", version="2.1.4", architecture="x86", mode_bits=32
        ),
        decoder=dict(name="Capstone", version="5.0.7"),
        vectors=vectors(),
        observations_sha256=_canonical_sha256(observations),
        executed_rvas=visited,
        summary=dict(
            cases=len(observations),
            executed_instruction_sites=11,
            bytes=27,
            executed_calls=0,
            negative_controls=1,
            accounting_promotions=0,
        ),
        scope=dict(
            claim="Exact post-call tails agree with independent pointer-ceiling and memory oracle",
            premises=[
                "Synthetic post-call state has mapped saved EBP and return words",
                "Large-tail metadata page is writable and disjoint from protected stack and return target",
            ],
            preservation="Other registers are preserved relative to post-call state, without inferring allocator preservation",
            flags="Large AND flags exclude undefined AF; small ADD ESP flags include all six arithmetic flags",
            not_claimed=[
                "Actual allocator execution or success",
                "Null or wrapping pointers as valid allocated objects",
                "Complete allocation helper or resize replay",
                "Whole-game accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, semantics):
    from src.observatory import native_lua_vector_allocation_return_semantics as sem

    _validate_json_tree(evidence, "evidence")
    _validate_json_tree(semantics, "semantics")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and _canonical_sha256(semantics) == sem.SEALED_SHA256,
        "sealed return replay differs",
    )
    _require(
        evidence["source_semantics_sha256"] == sem.SEALED_SHA256
        and evidence["vectors"] == vectors(),
        "source relation differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, semantics):
    result = _build_unsealed(executable, semantics)
    validate_structure(result, semantics)
    return result


def validate_conformance(executable, evidence, semantics):
    validate_structure(evidence, semantics)
    _require(
        _canonical_bytes(build_conformance(executable, semantics))
        == _canonical_bytes(evidence),
        "exact replay differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


def encode_conformance(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
