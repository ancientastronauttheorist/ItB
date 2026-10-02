"""Independent bounded normal-return requests for a returned class callback.

Both class markers are true, source/destination representations are valid and
disjoint, and registry values and Lua responses are compatible normal values.
The vector has external storage, with small full-vector growth opt-in. This
composes logical helper models; it does not execute a VM, memory accesses,
heap APIs, assertions or exceptions.
The retained Lua values describe the stack immediately before returning zero
results, before the host handles the callback frame.
"""

from __future__ import annotations

import copy
from src.observatory import native_lua_class_operation_semantics as operation
from src.observatory import native_lua_table_transfer_semantics as table


class CallbackError(RuntimeError):
    pass


def _word(value, label, *, nonzero=False):
    if type(value) is not int or not int(nonzero) <= value <= 0xFFFFFFFF:
        raise CallbackError(f"{label} must be {'nonzero ' if nonzero else ''}uint32")
    return value


def _refs(values, label):
    if type(values) is not list or len(values) != 2:
        raise CallbackError(f"{label} must contain two registry references")
    return [_word(value, label) for value in values]


def _containers(value):
    """Mutable representation identities, excluding shared immutable words."""
    result = set()

    def visit(current):
        if type(current) not in (dict, list) or id(current) in result:
            return
        result.add(id(current))
        for child in current.values() if type(current) is dict else current:
            visit(child)

    visit(value)
    return result


def apply(
    source,
    destination,
    vector,
    *,
    source_pointer,
    source_word,
    destination_word,
    destination_refs,
    source_refs,
    transfers,
    allow_growth=False,
    allow_fifth_growth=False,
    allow_sixth_spare=False,
):
    """Return detached class outputs and ordered conditional Lua requests.

    The bounded callback has one initial Lua argument. Each transfer keeps
    its destination/source registry values, so the helper prefixes are one
    and three. Entries categorized as init/finalize are filtered by the table
    model; assignments are requests rather than asserted VM table mutations.
    Growth is accepted only with explicit boolean opt-in and uses the existing
    class-operation capacity law for zero through three live external records.
    The separate fifth opt-in accepts only full4/cap4 and produces capacity6;
    it does not admit the subsequent spare-capacity callback. The separate
    sixth spare opt-in accepts only size5/capacity6 without vector growth.
    """
    if type(allow_sixth_spare) is not bool:
        raise CallbackError("allow_sixth_spare must be bool")
    if allow_sixth_spare and allow_fifth_growth:
        raise CallbackError("sixth spare and fifth growth cannot coexist")
    if type(allow_fifth_growth) is not bool:
        raise CallbackError("allow_fifth_growth must be bool")
    if allow_fifth_growth and not allow_growth:
        raise CallbackError("fifth growth requires allow_growth")
    if type(allow_growth) is not bool:
        raise CallbackError("allow_growth must be bool")
    _word(source_pointer, "source pointer", nonzero=True)
    _word(source_word, "source word")
    _word(destination_word, "destination word")
    destination_refs = _refs(destination_refs, "destination references")
    source_refs = _refs(source_refs, "source references")
    if (
        type(transfers) is not list
        or len(transfers) != 2
        or any(
            type(kinds) is not list
            or len(kinds) > 3
            or any(type(kind) is not str or kind not in table.KINDS for kind in kinds)
            for kinds in transfers
        )
    ):
        raise CallbackError(
            "two finite transfer category lists of at most three required"
        )
    if allow_sixth_spare:
        if (
            type(vector) is not dict
            or set(vector) != {"records", "capacity"}
            or type(vector["records"]) is not list
            or len(vector["records"]) != 5
            or type(vector["capacity"]) is not int
            or vector["capacity"] != 6
        ):
            raise CallbackError(
                "sixth spare requires exactly five records and capacity six"
            )
    elif allow_fifth_growth:
        if (
            type(vector) is not dict
            or set(vector) != {"records", "capacity"}
            or type(vector["records"]) is not list
            or len(vector["records"]) != 4
            or type(vector["capacity"]) is not int
            or vector["capacity"] != 4
        ):
            raise CallbackError(
                "fifth growth requires exactly four full external records"
            )
    else:
        if (
            type(vector) is not dict
            or set(vector) != {"records", "capacity"}
            or type(vector["records"]) is not list
            or not 0 <= len(vector["records"]) <= 3
            or type(vector["capacity"]) is not int
            or not (
                len(vector["records"]) <= vector["capacity"] <= 5
                if allow_growth
                else len(vector["records"]) < vector["capacity"] <= 5
            )
        ):
            if allow_growth:
                raise CallbackError(
                    "external vector must have at most three live records and full or spare capacity <=5"
                )
            raise CallbackError(
                "external vector must have at most three live records and spare capacity <=5"
            )
    domains = [_containers(state) for state in (source, destination, vector)]
    if any(domains[i] & domains[j] for i in range(3) for j in range(i + 1, 3)):
        raise CallbackError("class and vector representations must be disjoint")
    try:
        class_operation = operation.apply(
            source,
            destination,
            vector,
            argument=[0, source_pointer],
            allow_fifth_growth=allow_fifth_growth,
        )
    except (
        operation.OperationError,
        operation.tree.TransferError,
        operation.tree.balancing.BalancingError,
    ) as exc:
        raise CallbackError(str(exc)) from exc

    initial = [("argument", 0)]
    stack = list(initial)
    registry_requests, table_transfers, calls = [], [], []
    for pair, offset in enumerate((32, 40)):
        prefix = list(stack)
        values = []
        for role, reference in (
            ("destination", destination_refs[pair]),
            ("source", source_refs[pair]),
        ):
            value = ("registry", reference)
            values.append(value)
            request = dict(
                role=role,
                field_offset=offset,
                reference=reference,
                arguments=[-10000, reference],
            )
            registry_requests.append(request)
            before = list(stack)
            stack.append(value)
            calls.append(
                dict(
                    api="lua_rawgeti",
                    arguments=list(request["arguments"]),
                    before=before,
                    after=list(stack),
                    truth=None,
                )
            )
        result = table.transfer_requests(transfers[pair], len(prefix))

        def mapped(snapshot):
            def token(value):
                if value[0] == "prefix":
                    return prefix[value[1]]
                if value == ("destination",):
                    return values[0]
                if value == ("source",):
                    return values[1]
                return value

            return [token(value) for value in snapshot]

        result["initial"] = mapped(result["initial"])
        result["final"] = mapped(result["final"])
        for call in result["calls"]:
            call["before"] = mapped(call["before"])
            call["after"] = mapped(call["after"])
        table_transfers.append(result)
        calls.extend(copy.deepcopy(result["calls"]))
        stack = list(result["final"])

    return dict(
        class_operation=class_operation,
        destination_word=source_word,
        return_count=0,
        initial_lua_stack=initial,
        final_lua_stack=stack,
        lua_stack_delta=len(stack) - len(initial),
        registry_requests=registry_requests,
        table_transfers=table_transfers,
        requested_assignments=[
            list(result["assignments"]) for result in table_transfers
        ],
        calls=calls,
    )
