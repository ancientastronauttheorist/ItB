"""Explicit caller mappings for NULL-old vector allocation, resize and growth."""

import copy
import pytest
from src.observatory import native_vector_allocation_conformance as allocation
from src.observatory import native_small_vector_resize_conformance as resize
from src.observatory import native_small_vector_growth_conformance as growth

STACK = 0x30000000
OBJECT = 0x0FFFF000
CONTEXT = 0x0FFFFFD0


def fixture(module, alignment=0):
    vector = dict(
        has_old=False,
        old_size=0,
        old_capacity=0,
        requested=1,
        new_alignment=alignment,
        old_alignment=0,
        stack_alignment=0,
        new_pointer=allocation.DATA + 0x2000 + alignment,
    )
    registers = dict(
        eax=0x11223344,
        ecx=CONTEXT,
        edx=0x55667788,
        ebx=0xAABBCCDD,
        esi=0x88776655,
        edi=0x12345678,
        ebp=STACK + 0x1000,
        esp=STACK + 0x1000 - 40,
    )
    buffers = [
        bytes(resize.STACK_TEMPLATE),
        bytes(resize.NEW_TEMPLATE),
        bytes(resize.OLD_TEMPLATE),
        bytes(resize.OBJECT_TEMPLATE),
    ]
    return vector, registers, buffers


def run(module, vector, registers, buffers, **kwargs):
    options = dict(stack_base=STACK, object_base=OBJECT)
    options.update(kwargs)
    return module._expected(vector, registers, *buffers, **options)


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize("alignment", [0, 1, 7, 31])
def test_relocated_null_old_exact_writes_and_preserved_storage(module, alignment):
    vector, regs, buffers = fixture(module, alignment)
    before = copy.deepcopy((vector, regs, buffers))
    result = run(module, vector, regs, buffers)
    assert (vector, regs, buffers) == before
    assert result["new"] == buffers[1] and result["old"] == buffers[2]
    objects = bytearray(buffers[3])
    pointer = vector["new_pointer"]
    objects[CONTEXT - OBJECT : CONTEXT - OBJECT + 12] = b"".join(
        v.to_bytes(4, "little") for v in (pointer, pointer, pointer + 8)
    )
    assert result["object"] == bytes(objects)
    stack = bytearray(buffers[0])
    for event in result["events"]:
        if event["access"] == "write" and STACK <= event["address"] < STACK + len(
            stack
        ):
            offset = event["address"] - STACK
            stack[offset : offset + event["width"]] = event["value"].to_bytes(
                event["width"], "little"
            )
    assert result["stack"] == bytes(stack)
    assert len(stack) == len(buffers[0])
    assert result["registers"]["esp"] == regs["esp"] + 8
    for register in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][register] == regs[register]
    assert result["geometry"]["request"] == 8
    writes = [e for e in result["events"] if e["access"] == "write"]
    assert not any(
        allocation.DATA <= e["address"] < allocation.DATA + 0x2000 for e in writes
    )
    deepest = regs["esp"] - (96 if module is growth else 76)
    assert min(e["address"] for e in writes if e["address"] >= STACK) == deepest


@pytest.mark.parametrize("module", [resize, growth])
def test_explicit_default_mappings_are_identical(module):
    vector = next(
        v for v in module.vectors() if not v["has_old"] and v["requested"] == 1
    )
    _, regs, buffers = fixture(module)
    regs.update(
        esp=module.STACK + 0x1000, ebp=module.STACK + 0x1800, ecx=module.OBJECT + 0x100
    )
    implicit = module._expected(vector, regs, *buffers)
    explicit = module._expected(
        vector, regs, *buffers, stack_base=module.STACK, object_base=module.OBJECT
    )
    assert implicit == explicit


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize(
    "kind",
    [
        "stack_bool",
        "stack_wrap",
        "object_bool",
        "object_wrap",
        "frame_low",
        "frame_high",
        "object_high",
        "overlap",
        "old",
        "pointer_low",
        "pointer_high",
        "pointer_bool",
        "short_data",
    ],
)
def test_invalid_mapping_rejected(module, kind):
    vector, regs, buffers = fixture(module)
    options = {}
    if kind == "stack_bool":
        options["stack_base"] = True
    elif kind == "stack_wrap":
        options["stack_base"] = 2**32 - 1
    elif kind == "object_bool":
        options["object_base"] = True
    elif kind == "object_wrap":
        options["object_base"] = 2**32 - 1
    elif kind == "frame_low":
        regs["esp"] = STACK + 10
    elif kind == "frame_high":
        regs["esp"] = STACK + len(buffers[0]) - 4
    elif kind == "object_high":
        regs["ecx"] = OBJECT + len(buffers[3]) - 8
    elif kind == "overlap":
        options["object_base"] = STACK
        regs["ecx"] = STACK + 0x100
    elif kind == "old":
        vector.update(has_old=True, old_capacity=512, requested=513)
    elif kind == "pointer_low":
        vector["new_pointer"] = allocation.DATA - 1
    elif kind == "pointer_high":
        vector["new_pointer"] = allocation.DATA + 0x4000 - 7
    elif kind == "pointer_bool":
        vector["new_pointer"] = True
    elif kind == "short_data":
        buffers[1] = buffers[1][:0x1000]
    with pytest.raises(RuntimeError):
        run(module, vector, regs, buffers, **options)


@pytest.mark.parametrize("count", [0, 1, 512])
def test_allocation_actual_stack_and_metadata(count):
    _, regs, buffers = fixture(resize)
    vector = dict(count=count, pointer=allocation.DATA + 0x2000)
    result = allocation._expected(
        vector, regs, buffers[0], buffers[1], stack_base=STACK
    )
    assert result["registers"]["esp"] == regs["esp"] + 8
    payload = bytearray(buffers[1])
    if count >= 512:
        address = result["relation"]["metadata"] - allocation.DATA
        payload[address : address + 4] = vector["pointer"].to_bytes(4, "little")
    assert result["payload"] == bytes(payload)


@pytest.mark.parametrize("kind", ["overlap", "frame", "wrap", "short_data"])
def test_allocation_mapping_rejected(kind):
    _, regs, buffers = fixture(resize)
    stack_base = STACK
    if kind == "overlap":
        stack_base = allocation.DATA
        regs["esp"] = stack_base + 0x1000
    elif kind == "frame":
        regs["esp"] = STACK + 47
    elif kind == "wrap":
        stack_base = 2**32 - 1
    elif kind == "short_data":
        buffers[1] = buffers[1][:0x1000]
    with pytest.raises(RuntimeError):
        allocation._expected(
            dict(count=1, pointer=allocation.DATA + 0x2000),
            regs,
            buffers[0],
            buffers[1],
            stack_base=stack_base,
        )


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize("size", [0, 1, 2, 3])
def test_relocated_old_live_records_copy_and_successful_free(module, size):
    vector, regs, buffers = fixture(module, 7)
    vector.update(
        has_old=True,
        old_size=size,
        old_capacity=size,
        requested=max(size + 1, size + size // 2),
    )
    result = run(module, vector, regs, buffers)
    g = result["geometry"]
    wanted = bytearray(buffers[1])
    a, b = g["new_begin"] - module.NEW, g["old_begin"] - module.OLD
    wanted[a : a + size * 8] = buffers[2][b : b + size * 8]
    assert result["new"] == bytes(wanted)
    assert result["old"] == buffers[2]
    assert result["registers"]["esp"] == regs["esp"] + 8
    assert result["registers"]["edx"] == 0xB0000001
    for register in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][register] == regs[register]
    free_calls = [
        e
        for e in result["events"]
        if e["access"] == "read" and e["address"] == module.FREE_IAT
    ]
    assert len(free_calls) == 1
    for i, value in enumerate(
        (g["new_begin"], g["new_begin"] + 8 * size, g["new_capacity"])
    ):
        assert (
            int.from_bytes(
                result["object"][
                    CONTEXT - OBJECT + 4 * i : CONTEXT - OBJECT + 4 * i + 4
                ],
                "little",
            )
            == value
        )


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize("kind", ["short_old", "old_stack_alias", "old_object_alias"])
def test_relocated_old_mapping_guards(module, kind):
    vector, regs, buffers = fixture(module)
    vector.update(has_old=True, old_size=3, old_capacity=3, requested=4)
    options = {}
    if kind == "short_old":
        buffers[2] = buffers[2][:0x110]
    elif kind == "old_stack_alias":
        options["stack_base"] = module.OLD
        regs["esp"] = module.OLD + 0x1000
    else:
        options["object_base"] = module.OLD
        regs["ecx"] = module.OLD + 0x100
    with pytest.raises(RuntimeError):
        run(module, vector, regs, buffers, **options)


def free_fixture(joined=False):
    from src.observatory import native_heap_free_protocol_conformance as free
    from src.observatory import (
        native_vector_deallocation_conformance_joined as joined_module,
    )

    module = joined_module if joined else free
    _, regs, buffers = fixture(resize)
    vector = dict(
        pointer=resize.OLD + 0x100,
        heap=0x12345678,
        responses=[dict(kind="heap_free", eax=1)],
    )
    if joined:
        vector.update(count=3, stride=8, metadata=None)
    return module, vector, regs, buffers[0], bytes(4096)


@pytest.mark.parametrize("joined", [False, True])
@pytest.mark.parametrize("null", [False, True])
def test_successful_free_actual_stack(joined, null):
    module, vector, regs, stack, error = free_fixture(joined)
    if null:
        vector.update(pointer=0, responses=[])
        if joined:
            vector["count"] = 0
    result = module._expected(vector, regs, stack, error, stack_base=STACK)
    assert result["protocol"]["returned"]
    assert result["error"] == error
    assert result["registers"]["esp"] == regs["esp"] + 4
    wanted = bytearray(stack)
    for e in result["events"]:
        if e["access"] == "write":
            assert STACK <= e["address"] <= STACK + len(stack) - 4
            at = e["address"] - STACK
            wanted[at : at + 4] = e["value"].to_bytes(4, "little")
    assert result["stack"] == bytes(wanted)
    assert len(result["stack"]) == len(stack)


@pytest.mark.parametrize("joined", [False, True])
@pytest.mark.parametrize(
    "kind",
    ["bool", "wrap", "frame_low", "frame_high", "unfinished", "failure", "overlap"],
)
def test_free_mapping_guards(joined, kind):
    module, vector, regs, stack, error = free_fixture(joined)
    base = STACK
    if kind == "bool":
        base = True
    elif kind == "wrap":
        base = 2**32 - 1
    elif kind == "frame_low":
        regs["esp"] = STACK + 10
    elif kind == "frame_high":
        regs["esp"] = STACK + len(stack) - 4
    elif kind == "unfinished":
        vector["responses"] = []
    elif kind == "failure":
        vector["responses"] = [dict(kind="heap_free", eax=0)]
    elif kind == "overlap":
        base = module.ERROR_PAGE
        regs["esp"] = base + 0x1000
    with pytest.raises(RuntimeError):
        module._expected(vector, regs, stack, error, stack_base=base)


@pytest.mark.parametrize("address", [STACK + 0x100, allocation.DATA + 0x100])
def test_relocated_deallocation_metadata_cannot_alias_writable_buffers(address):
    module, vector, regs, stack, error = free_fixture(True)
    vector.update(pointer=address, count=512, metadata=address - 32)
    with pytest.raises(RuntimeError, match="metadata overlaps"):
        module._expected(vector, regs, stack, error, stack_base=STACK)
