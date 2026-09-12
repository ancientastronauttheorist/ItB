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


def next_capacity(size, capacity):
    """Spare capacity or the proven zero-to-three-record growth domain."""
    if (
        type(size) is not int
        or type(capacity) is not int
        or not 0 <= size <= capacity <= MAX_CAPACITY
    ):
        raise OperationError("invalid vector size or capacity")
    if size < capacity:
        return capacity
    if size > 3:
        raise OperationError("growth beyond modeled small-vector domain")
    return max(size + 1, capacity + capacity // 2)


def apply(source, destination, vector, *, argument=None, argument_index=None):
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
    capacity = next_capacity(len(records), vector["capacity"])
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
