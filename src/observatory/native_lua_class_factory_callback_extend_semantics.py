"""Bounded second-source extension of an actual factory receiver's tree.

Each source has at most seven canonical nodes; the retained destination union
has at most fourteen. The second call reuses explicit Lua and successful heap
response premises. Logical IDs preserve existing nodes across rotations; they
do not describe native addresses, memory, a Lua VM, allocation or ownership.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_repeat_semantics as repeat_model,
)

tree_model = repeat_model.tree_model
callback = tree_model.callback
MAX_SOURCE_NODES = 7
MAX_DESTINATION_NODES = 14


class FactoryCallbackExtendError(repeat_model.FactoryCallbackRepeatError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackExtendError(message)


def apply(
    *,
    first_arguments,
    second_source_state,
    new_vector_pointer,
    second_entry,
    second_registers,
):
    """Return detached first/second packets for a retained-tree union.

    Source word, references, iterator recipes, cookie and receiver identities
    retain the first-call premises. The second incoming GPRs are the actual
    first normal return except ESP. Existing destination IDs and unvisited
    payloads survive, new keys receive successive IDs in second-source key
    order, and all selected payloads overwrite their matching destination ID.
    Successful allocation/free requests remain conditional logical requests.
    """
    _require(
        type(first_arguments) is dict
        and set(first_arguments) == repeat_model.FIRST_ARGUMENT_FIELDS,
        "first argument schema differs",
    )
    try:
        first = tree_model.apply(**first_arguments)
        checked = callback.operation.tree.validate_state(second_source_state)
        _require(
            checked["nodes"] <= MAX_SOURCE_NODES,
            "second source exceeds seven-node model bound",
        )
        source_ids = {
            node["key"]: index
            for index, node in enumerate(second_source_state["tree"]["nodes"])
        }
        initial = first["callback_operation"]["destination"]
        destination_ids = {
            node["key"]: index for index, node in enumerate(initial["tree"]["nodes"])
        }
        _require(
            len(set(source_ids) | set(destination_ids)) <= MAX_DESTINATION_NODES,
            "destination union exceeds fourteen-node model bound",
        )
        baseline = repeat_model.apply(
            first_arguments=copy.deepcopy(first_arguments),
            second_source_state=copy.deepcopy(first_arguments["source_state"]),
            new_vector_pointer=new_vector_pointer,
            second_entry=second_entry,
            second_registers=copy.deepcopy(second_registers),
        )
        _require(baseline["first"] == first, "repeat baseline first packet disagrees")
        second = copy.deepcopy(baseline["second"])
        _require(
            second["tree_count"] == first["tree_count"]
            and second["normal_field_updates"][56] == first["tree_count"]
            and second["field_updates"][56] == first["tree_count"]
            and second["sentinel_link_ids"] == first["sentinel_link_ids"]
            and second["sentinel_preserved_offsets"] == list(range(24))
            and second["tree_heap_requests"] == [],
            "repeat baseline tree metadata disagrees",
        )
        source_pointer = first_arguments["source_pointer"]
        vector = dict(
            records=[[0, source_pointer], [0, source_pointer]],
            capacity=2,
            begin=new_vector_pointer,
            end=new_vector_pointer + 16,
            capacity_pointer=new_vector_pointer + 16,
        )
        _require(
            second["vector"] == vector
            and second["callback_operation"]["vector"]
            == dict(records=[[0, source_pointer], [0, source_pointer]], capacity=2)
            and second["old_vector_pointer"] == first_arguments["vector_pointer"]
            and second["vector_heap_request"]
            == dict(continuation=0x00789463, handle=0x12345678, flags=0, bytes=16)
            and second["vector_free_request"]
            == dict(
                continuation=0x00789172,
                handle=0x12345678,
                flags=0,
                pointer=first_arguments["vector_pointer"],
            ),
            "repeat baseline vector requests disagree",
        )
        full_return = copy.deepcopy(first["full_return"])
        full_return["registers"]["esp"] = second_entry + 4
        class_return = copy.deepcopy(first["class_return"])
        class_return["registers"].update(
            edx=0xB0000001, ebp=second_entry - 4, esp=second_entry - 40
        )
        _require(
            second["full_return"] == full_return
            and second["class_return"] == class_return,
            "repeat baseline normal return packets disagree",
        )
        suffix = callback.apply(
            copy.deepcopy(second_source_state),
            copy.deepcopy(initial),
            dict(records=[[0, source_pointer]], capacity=1),
            source_pointer=source_pointer,
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_growth=True,
        )
    except (
        tree_model.FactoryCallbackTreeError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackExtendError(str(exc)) from exc

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
        raise FactoryCallbackExtendError(str(exc)) from exc
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
            "extension baseline and callback suffix packets disagree",
        )
    _require(
        second["normal_requests"] == second["prefix_calls"] + suffix["calls"],
        "extension baseline and callback request packets disagree",
    )
    destination = copy.deepcopy(initial)
    copies = []
    for key in checked["inorder"]:
        inserted = key not in destination_ids
        if inserted:
            destination_ids[key] = len(destination["tree"]["nodes"])
            destination["tree"] = callback.operation.tree.balancing.insert(
                destination["tree"], key
            )["tree"]
            destination["payloads"].append(0)
        source_id = source_ids[key]
        destination_id = destination_ids[key]
        payload = second_source_state["payloads"][source_id]
        destination["payloads"][destination_id] = payload
        copies.append(
            dict(
                source=source_id,
                destination=destination_id,
                key=key,
                inserted=inserted,
                payload=payload,
            )
        )
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
        "extension class operation packet disagrees",
    )
    nodes = destination["tree"]["nodes"]
    root = destination["tree"]["root"]
    count = len(nodes)
    leftmost = (
        min(range(count), key=lambda index: nodes[index]["key"]) if count else None
    )
    rightmost = (
        max(range(count), key=lambda index: nodes[index]["key"]) if count else None
    )
    second.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(second_source_state),
        tree_count=count,
        tree_heap_requests=[
            dict(continuation=0x00789463, handle=0x12345678, flags=0, bytes=24)
            for entry in copies
            if entry["inserted"]
        ],
        sentinel_link_ids=dict(root=root, leftmost=leftmost, rightmost=rightmost),
        sentinel_preserved_offsets=list(range(12, 24)),
    )
    second["field_updates"][56] = count
    second["normal_field_updates"][56] = count
    return dict(first=first, second=second)
