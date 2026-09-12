"""Class return oracle supports an actual caller stack and continuation."""

import copy
import pytest
from src.observatory import native_lua_class_vector_return_conformance as c


@pytest.mark.parametrize("edge", [0, -1])
def test_default_frame_mapping_is_unchanged(edge):
    f = c._fixture(c.vectors()[edge])
    explicit = dict(f, stack_base=c.STACK)
    assert c._expected(f) == c._expected(explicit)
    assert c.return_spec(f["frame"], f["cookie"], f["current"]) == c.return_spec(
        f["frame"], f["cookie"], f["current"], return_address=c.RETURN
    )


@pytest.mark.parametrize("delta", [0, 1])
def test_relocated_stack_and_real_caller_return(delta):
    f = c._fixture(c.vectors()[0])
    f["current"] = (f["cookie"] + delta) & 0xFFFFFFFF
    oldbase = c.STACK
    newbase = 0x30000000
    frame = f["frame"] - oldbase + newbase
    stack = bytearray(f["stack"])
    offset = frame - newbase
    stack[offset - 4 : offset] = (f["cookie"] ^ frame).to_bytes(4, "little")
    caller = 0x44556677
    stack[offset + 4 : offset + 8] = caller.to_bytes(4, "little")
    f.update(
        frame=frame,
        stack_base=newbase,
        stack=bytes(stack),
        relation=c.return_spec(frame, f["cookie"], f["current"], return_address=caller),
    )
    f["registers"] = dict(f["registers"], ebp=frame, esp=frame - 32)
    before = copy.deepcopy(f)
    e = c._expected(f)
    assert f == before
    assert (
        e["registers"]["esp"] == frame + 12
        if not delta
        else e["registers"]["esp"] == frame - 24
    )
    assert e["registers"]["ecx"] == f["cookie"]
    for reg in ("edi", "esi", "ebx"):
        assert e["registers"][reg] == f["saved"][reg]
    expected = bytearray(stack)
    expected[offset - 24 : offset - 20] = c.CONTINUATION.to_bytes(4, "little")
    assert e["stack"] == bytes(expected)
    assert e["events"][0] == dict(
        access="read", address=frame - 4, width=4, value=f["cookie"] ^ frame
    )
    if not delta:
        assert e["events"][-1] == dict(
            access="read", address=frame + 4, width=4, value=caller
        )
        assert (
            f["relation"]["endpoint"] == caller
            and e["registers"]["ebp"] == f["saved"]["ebp"]
        )
    else:
        assert f["relation"]["endpoint"] == c.ESCAPE


@pytest.mark.parametrize("value", [True, -1, 2**32])
def test_invalid_return_pointer(value):
    with pytest.raises(c.ConformanceError):
        c.return_spec(0x30001000, 0, 0, return_address=value)


@pytest.mark.parametrize("value", [True, -1, 2**32, 0x1000])
def test_invalid_stack_mapping(value):
    f = c._fixture(c.vectors()[0])
    f["stack_base"] = value
    with pytest.raises(c.ConformanceError):
        c._expected(f)
