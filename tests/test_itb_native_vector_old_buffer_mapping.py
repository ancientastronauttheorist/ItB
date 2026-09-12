"""Actual old-buffer pointers preserve source pages during small native growth modeling."""

import copy
import pytest
from src.observatory import native_small_vector_resize_conformance as resize
from src.observatory import native_small_vector_growth_conformance as growth

STACK, OBJECT, CONTEXT = 0x30000000, 0x0FFFF000, 0x0FFFFFD0


def fixture(size, old_base=0x14000000):
    vector = dict(
        has_old=True,
        old_size=size,
        old_capacity=size,
        requested=size + 1,
        new_alignment=7,
        old_alignment=0,
        stack_alignment=0,
        new_pointer=resize.NEW + 0x2007,
        old_pointer=old_base + 0x1F8,
    )
    regs = dict(
        eax=0x12345678,
        ebx=0xABCDEF01,
        ecx=CONTEXT,
        edx=0x98765432,
        esi=0x12349876,
        edi=0xFFEEDDCC,
        ebp=STACK + 0x1000,
        esp=STACK + 0x1000 - 40,
    )
    buffers = [
        resize.STACK_TEMPLATE[:0x2000],
        resize.NEW_TEMPLATE,
        bytes((i * 29 + (i >> 2) + 37) % 256 for i in range(4096)),
        resize.OBJECT_TEMPLATE,
    ]
    return vector, regs, buffers


def run(module, vector, regs, buffers, old_base=0x14000000):
    return module._expected(
        vector, regs, *buffers, stack_base=STACK, object_base=OBJECT, old_base=old_base
    )


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize("size", range(4))
@pytest.mark.parametrize("old_base", [0x14000000, 0x16000000, 0x18000000])
def test_actual_old_pointer_copy_and_whole_page_preservation(module, size, old_base):
    vector, regs, buffers = fixture(size, old_base)
    snapshot = copy.deepcopy((vector, regs, buffers))
    result = run(module, vector, regs, buffers, old_base)
    assert (vector, regs, buffers) == snapshot
    assert result["old"] == buffers[2]
    wanted = bytearray(buffers[1])
    wanted[0x2007 : 0x2007 + size * 8] = buffers[2][0x1F8 : 0x1F8 + size * 8]
    assert result["new"] == bytes(wanted)
    reads = [
        e
        for e in result["events"]
        if e["access"] == "read" and old_base <= e["address"] < old_base + 4096
    ]
    assert reads == [
        dict(
            access="read",
            address=vector["old_pointer"] + i,
            width=4,
            value=int.from_bytes(buffers[2][0x1F8 + i : 0x1FC + i], "little"),
        )
        for i in range(0, size * 8, 4)
    ]
    writes = [e for e in result["events"] if e["access"] == "write"]
    assert not any(old_base <= e["address"] < old_base + 4096 for e in writes)
    assert (
        sum(
            e["access"] == "read" and e["address"] == module.FREE_IAT
            for e in result["events"]
        )
        == 1
    )
    assert result["registers"]["edx"] == 0xB0000001
    assert result["registers"]["esp"] == regs["esp"] + 8
    for r in ("ebx", "esi", "edi", "ebp"):
        assert result["registers"][r] == regs[r]


@pytest.mark.parametrize("module", [resize, growth])
@pytest.mark.parametrize(
    "kind",
    [
        "base_bool",
        "base_wrap",
        "pointer_bool",
        "pointer_null",
        "pointer_negative",
        "pointer_wrap",
        "pointer_low",
        "pointer_high",
        "short_old",
        "stack_alias",
        "object_alias",
        "new_alias",
        "large_geometry",
    ],
)
def test_invalid_old_pointer_or_buffer_is_rejected(module, kind):
    vector, regs, buffers = fixture(3)
    base = 0x14000000
    if kind == "base_bool":
        base = True
    elif kind == "base_wrap":
        base = 2**32 - 1
    elif kind == "pointer_bool":
        vector["old_pointer"] = True
    elif kind == "pointer_null":
        vector["old_pointer"] = 0
    elif kind == "pointer_negative":
        vector["old_pointer"] = -1
    elif kind == "pointer_wrap":
        vector["old_pointer"] = 2**32 - 24
    elif kind == "pointer_low":
        vector["old_pointer"] = base - 1
    elif kind == "pointer_high":
        vector["old_pointer"] = base + 4096 - 23
    elif kind == "short_old":
        buffers[2] = buffers[2][:0x200]
    elif kind in ("stack_alias", "object_alias", "new_alias"):
        base = {"stack_alias": STACK, "object_alias": OBJECT, "new_alias": resize.NEW}[
            kind
        ]
        vector["old_pointer"] = base + 0x1F8
    elif kind == "large_geometry":
        vector.update(old_capacity=512, requested=513)
    with pytest.raises(RuntimeError):
        run(module, vector, regs, buffers, base)


def test_null_old_cannot_supply_explicit_nonnull_pointer():
    vector, _, _ = fixture(0)
    vector["has_old"] = False
    with pytest.raises(RuntimeError):
        resize.geometry(vector)


@pytest.mark.parametrize("module", [resize, growth])
def test_explicit_original_old_buffer_mapping_is_identical(module):
    vector, regs, buffers = fixture(3, resize.OLD)
    vector.pop("old_pointer")
    implicit = module._expected(
        vector, regs, *buffers, stack_base=STACK, object_base=OBJECT
    )
    explicit = run(module, vector, regs, buffers, resize.OLD)
    assert implicit == explicit
