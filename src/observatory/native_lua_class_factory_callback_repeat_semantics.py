"""Two bounded normal calls on the same actual factory class receiver.

The second call reuses the supplied Lua word/reference/iterator premises and
source topology, with explicit source payloads. Its full one-record vector grows
to two records under successful allocation and free responses. These are logical
requests, not native memory, allocator, Lua VM or ownership operations.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_tree_semantics as tree_model,
)

callback = tree_model.callback
FIRST_ARGUMENT_FIELDS = frozenset(
    {
        "source_state",
        "state",
        "userdata",
        "record_pointer",
        "source_pointer",
        "callback_entry",
        "registers",
        "closure_target",
        "closure_upvalues",
        "upvalue_has_metatable",
        "argument_has_metatable",
        "upvalue_marker_kind",
        "argument_marker_kind",
        "vector_pointer",
        "cookie",
        "source_word",
        "destination_word",
        "destination_refs",
        "source_refs",
        "transfers",
    }
)


class FactoryCallbackRepeatError(tree_model.FactoryCallbackTreeError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackRepeatError(message)


def _word(value, label, *, nonzero=False):
    _require(
        type(value) is int and int(nonzero) <= value <= 0xFFFFFFFF,
        label + " must be " + ("nonzero " if nonzero else "") + "uint32",
    )


def apply(
    *,
    first_arguments,
    second_source_state,
    new_vector_pointer,
    second_entry,
    second_registers,
):
    """Return detached first/second callback packets under finite-repeat premises.

    Second source tree IDs, keys, links and colors equal the first source tree;
    payload DWORDs can change or stay equal. All incoming second GPRs are the
    actual first full-return GPRs, except ESP names the new invocation entry.
    Word, registry references, iterator recipes, cookie and identities are
    explicitly reused. The freed old eight-byte vector is a conditional request;
    no lifetime, ownership or successful real-VM state transition is asserted.
    """
    _require(
        type(first_arguments) is dict and set(first_arguments) == FIRST_ARGUMENT_FIELDS,
        "first argument schema differs",
    )
    try:
        first = tree_model.apply(**first_arguments)
        checked = callback.operation.tree.validate_state(second_source_state)
        _require(
            checked["nodes"] <= tree_model.MAX_SOURCE_NODES,
            "second source exceeds seven-node model bound",
        )
        _require(
            second_source_state["tree"] == first_arguments["source_state"]["tree"],
            "second source topology differs from first",
        )
        _word(second_entry, "second entry")
        _word(new_vector_pointer, "new vector pointer", nonzero=True)
        _require(
            new_vector_pointer + 16 <= 0xFFFFFFFF,
            "new sixteen-byte vector extent wraps uint32",
        )
        _require(
            type(second_registers) is dict
            and set(second_registers) == set(first["full_return"]["registers"]),
            "second register schema differs",
        )
        for register, value in second_registers.items():
            _word(value, "second " + register)
        expected_registers = dict(first["full_return"]["registers"], esp=second_entry)
        _require(
            second_registers == expected_registers,
            "second incoming registers differ from actual first return",
        )
        second_arguments = copy.deepcopy(first_arguments)
        second_arguments.pop("source_state")
        second_arguments.update(
            callback_entry=second_entry,
            registers=copy.deepcopy(second_registers),
            vector_pointer=new_vector_pointer,
            destination_word=first_arguments["source_word"],
        )
        second = tree_model.full_return_model.apply(**second_arguments)
        old = first_arguments["vector_pointer"]
        spans = (
            (old, 8, "old vector"),
            (new_vector_pointer, 16, "new vector"),
            (first_arguments["userdata"], 72, "userdata"),
            (first_arguments["record_pointer"], 24, "sentinel"),
            (first_arguments["source_pointer"], 72, "source"),
            (second_entry - 48, 56, "second callback frame"),
        )
        for index, (start, size, label) in enumerate(spans):
            for other, other_size, other_label in spans[index + 1 :]:
                _require(
                    start + size <= other or other + other_size <= start,
                    label + " overlaps " + other_label,
                )
        suffix = callback.apply(
            copy.deepcopy(second_source_state),
            copy.deepcopy(first["callback_operation"]["destination"]),
            dict(records=[[0, first_arguments["source_pointer"]]], capacity=1),
            source_pointer=first_arguments["source_pointer"],
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_growth=True,
        )
    except (
        tree_model.FactoryCallbackTreeError,
        tree_model.full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackRepeatError(str(exc)) from exc

    source_pointer = first_arguments["source_pointer"]

    def bound(snapshot):
        return [
            ("argument", source_pointer) if token == ("argument", 0) else token
            for token in snapshot
        ]

    suffix["initial_lua_stack"] = bound(suffix["initial_lua_stack"])
    suffix["final_lua_stack"] = bound(suffix["final_lua_stack"])
    for call in suffix["calls"]:
        call["before"], call["after"] = bound(call["before"]), bound(call["after"])
    for transfer in suffix["table_transfers"]:
        transfer["initial"], transfer["final"] = bound(transfer["initial"]), bound(
            transfer["final"]
        )
        for call in transfer["calls"]:
            call["before"], call["after"] = bound(call["before"]), bound(call["after"])
    try:
        tree_model._suffix_contract(
            suffix,
            source_pointer=source_pointer,
            source_word=first_arguments["source_word"],
            destination_refs=first_arguments["destination_refs"],
            source_refs=first_arguments["source_refs"],
            transfers=first_arguments["transfers"],
        )
    except tree_model.FactoryCallbackTreeError as exc:
        raise FactoryCallbackRepeatError(str(exc)) from exc
    for baseline_key, suffix_key in (
        ("destination_word", "destination_word"),
        ("return_count", "return_count"),
        ("normal_initial_lua_stack", "initial_lua_stack"),
        ("normal_final_lua_stack", "final_lua_stack"),
        ("normal_lua_stack_delta", "lua_stack_delta"),
        ("registry_requests", "registry_requests"),
        ("table_transfers", "table_transfers"),
        ("requested_assignments", "requested_assignments"),
        ("registry_table_calls", "calls"),
    ):
        _require(
            second[baseline_key] == suffix[suffix_key],
            "second full-return and callback suffix packets disagree",
        )
    _require(
        second["normal_requests"] == second["prefix_calls"] + suffix["calls"],
        "second full-return and callback request packets disagree",
    )
    keys = checked["inorder"]
    source_ids = {
        node["key"]: index
        for index, node in enumerate(second_source_state["tree"]["nodes"])
    }
    destination_tree = copy.deepcopy(first["callback_operation"]["destination"]["tree"])
    destination_ids = {
        node["key"]: index for index, node in enumerate(destination_tree["nodes"])
    }
    payloads = [
        second_source_state["payloads"][source_ids[node["key"]]]
        for node in destination_tree["nodes"]
    ]
    destination = dict(tree=destination_tree, payloads=payloads)
    copies = [
        dict(
            source=source_ids[key],
            destination=destination_ids[key],
            key=key,
            inserted=False,
            payload=second_source_state["payloads"][source_ids[key]],
        )
        for key in keys
    ]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=[[0, source_pointer], [0, source_pointer]], capacity=2),
        return_word=source_pointer,
        argument_kind="external",
        grew=True,
    )
    _require(
        suffix["class_operation"] == expected_operation,
        "second existing-key class operation packet disagrees",
    )
    second["class_return"]["registers"]["edx"] = 0xB0000001
    second.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(second_source_state),
        tree_count=checked["nodes"],
        old_vector_pointer=old,
        vector=dict(
            records=[[0, source_pointer], [0, source_pointer]],
            capacity=2,
            begin=new_vector_pointer,
            end=new_vector_pointer + 16,
            capacity_pointer=new_vector_pointer + 16,
        ),
        vector_heap_request=dict(
            continuation=0x00789463, handle=0x12345678, flags=0, bytes=16
        ),
        vector_free_request=dict(
            continuation=0x00789172, handle=0x12345678, flags=0, pointer=old
        ),
        tree_heap_requests=[],
        field_updates={
            4: new_vector_pointer,
            8: new_vector_pointer + 16,
            12: new_vector_pointer + 16,
            56: checked["nodes"],
        },
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12, 56)
        ],
        normal_field_updates={
            0: first_arguments["source_word"],
            4: new_vector_pointer,
            8: new_vector_pointer + 16,
            12: new_vector_pointer + 16,
            56: checked["nodes"],
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ],
        sentinel_link_ids=copy.deepcopy(first["sentinel_link_ids"]),
        sentinel_preserved_offsets=list(range(24)),
    )
    second.pop("record_preserved_size")
    second.pop("heap_request")
    return dict(first=first, second=second)
