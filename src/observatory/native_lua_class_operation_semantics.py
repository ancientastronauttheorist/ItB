"""Independent logical normal-return model for the native class mutation owner.

The supplied source state must resolve the selected record's second word.
This model does not execute memory accesses, heap APIs, assertions or exceptions.
"""

from __future__ import annotations
import copy
from src.observatory import native_lua_class_tree_semantics as tree

MAX_CAPACITY = 0x0FFFFFFF


class OperationError(RuntimeError):
    pass


def _record(value):
    if (
        type(value) is not list
        or len(value) != 2
        or any(type(word) is not int or not 0 <= word <= 0xFFFFFFFF for word in value)
    ):
        raise OperationError("record must contain two uint32 words")
    return list(value)


def next_capacity(size, capacity, *, allow_fifth_growth=False):
    """Old finite domain, plus explicitly selected exact full4-to-capacity6.

    The new flag cannot select spare capacity or another full-vector size.
    """
    if type(allow_fifth_growth) is not bool:
        raise OperationError("allow_fifth_growth must be bool")
    if (
        type(size) is not int
        or type(capacity) is not int
        or not 0 <= size <= capacity <= MAX_CAPACITY
    ):
        raise OperationError("invalid vector size or capacity")
    if allow_fifth_growth:
        if size != 4 or capacity != 4:
            raise OperationError("fifth growth requires exactly four full records")
        return 6
    if size < capacity:
        return capacity
    if size > 3:
        raise OperationError("growth beyond modeled small-vector domain")
    return max(size + 1, capacity + capacity // 2)


def apply(
    source,
    destination,
    vector,
    *,
    argument=None,
    argument_index=None,
    allow_fifth_growth=False,
):
    """Return detached destination/vector states; all input objects remain unchanged.

    Supply exactly one external argument record or internal record index. Both
    normal paths append the same selected record after ordered tree transfer.
    """
    tree.validate_state(source)
    tree.validate_state(destination)
    if type(vector) is not dict or set(vector) != {"records", "capacity"}:
        raise OperationError("vector state schema differs")
    if type(vector["records"]) is not list:
        raise OperationError("vector records must be a list")
    records = [_record(record) for record in vector["records"]]
    capacity = next_capacity(
        len(records), vector["capacity"], allow_fifth_growth=allow_fifth_growth
    )
    internal = argument_index is not None
    if internal:
        if (
            argument is not None
            or type(argument_index) is not int
            or not 0 <= argument_index < len(records)
        ):
            raise OperationError("invalid internal argument selection")
        selected = list(records[argument_index])
    else:
        selected = _record(argument)
    if selected[1] == 0:
        raise OperationError("normal class operation requires a nonzero source word")
    transferred = tree.transfer(source, destination)
    return dict(
        destination=transferred["destination"],
        copies=transferred["copies"],
        vector=dict(records=records + [copy.deepcopy(selected)], capacity=capacity),
        return_word=selected[1],
        argument_kind="internal" if internal else "external",
        grew=len(records) == vector["capacity"],
    )
