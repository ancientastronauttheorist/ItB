"""Bounded source-tree continuation of the actual factory-returned callback.

The factory destination tree and vector start empty, and the first eight-byte
vector allocation succeeds. A supplied canonical source has zero through seven
nodes. This composes logical models without executing native code, a Lua VM,
memory accesses, allocation or ownership operations. Sentinel links are logical
node IDs, never native addresses; its final twelve bytes are preserved.
"""

from __future__ import annotations

import copy

from src.observatory import native_lua_class_callback_semantics as callback
from src.observatory import (
    native_lua_class_factory_callback_return_semantics as full_return_model,
)

MAX_SOURCE_NODES = 7


class FactoryCallbackTreeError(full_return_model.FactoryCallbackReturnError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackTreeError(message)


def _suffix_contract(
    suffix, *, source_pointer, source_word, destination_refs, source_refs, transfers
):
    """Check source-independent Lua requests against the table helper contract."""
    stack = [("argument", source_pointer)]
    calls, registry, tables = [], [], []
    for pair, offset in enumerate((32, 40)):
        prefix = list(stack)
        values = []
        for role, reference in (
            ("destination", destination_refs[pair]),
            ("source", source_refs[pair]),
        ):
            arguments = [-10000, reference]
            registry.append(
                dict(
                    role=role,
                    field_offset=offset,
                    reference=reference,
                    arguments=list(arguments),
                )
            )
            before = list(stack)
            values.append(("registry", reference))
            stack.append(values[-1])
            calls.append(
                dict(
                    api="lua_rawgeti",
                    arguments=arguments,
                    before=before,
                    after=list(stack),
                    truth=None,
                )
            )
        table = callback.table.transfer_requests(transfers[pair], len(prefix))

        def bound(snapshot):
            result = []
            for token in snapshot:
                if token[0] == "prefix":
                    token = prefix[token[1]]
                elif token == ("destination",):
                    token = values[0]
                elif token == ("source",):
                    token = values[1]
                result.append(token)
            return result

        table["initial"] = bound(table["initial"])
        table["final"] = bound(table["final"])
        for call in table["calls"]:
            call["before"] = bound(call["before"])
            call["after"] = bound(call["after"])
        tables.append(table)
        calls.extend(copy.deepcopy(table["calls"]))
        stack = list(table["final"])
    expected = dict(
        destination_word=source_word,
        return_count=0,
        initial_lua_stack=[("argument", source_pointer)],
        final_lua_stack=stack,
        lua_stack_delta=4,
        registry_requests=registry,
        table_transfers=tables,
        requested_assignments=[list(table["assignments"]) for table in tables],
        calls=calls,
    )
    _require(
        set(suffix) == set(expected) | {"class_operation"},
        "callback suffix schema disagrees",
    )
    _require(
        all(suffix[key] == value for key, value in expected.items()),
        "callback suffix requests disagree with table contract",
    )


def apply(
    *,
    source_state,
    state,
    userdata,
    record_pointer,
    source_pointer,
    callback_entry,
    registers,
    closure_target,
    closure_upvalues,
    upvalue_has_metatable,
    argument_has_metatable,
    upvalue_marker_kind,
    argument_marker_kind,
    vector_pointer,
    cookie,
    source_word,
    destination_word,
    destination_refs,
    source_refs,
    transfers,
):
    """Return detached bounded tree, suffix requests and complete return packet.

    The full-return model supplies strict words, closure identity, disjoint
    modeled extents, identity-bound prefix and normal ABI. Tree insertion is
    ordered by unsigned key and overwrites each newly inserted payload. The
    original [0, source_pointer] record and class EAX/EDX return law survive.
    No native node-address mapping or deeper helper frame extent is claimed.
    """
    try:
        checked = callback.operation.tree.validate_state(source_state)
        _require(
            checked["nodes"] <= MAX_SOURCE_NODES,
            "source tree exceeds seven-node model bound",
        )
        result = full_return_model.apply(
            state=state,
            userdata=userdata,
            record_pointer=record_pointer,
            source_pointer=source_pointer,
            callback_entry=callback_entry,
            registers=registers,
            closure_target=closure_target,
            closure_upvalues=closure_upvalues,
            upvalue_has_metatable=upvalue_has_metatable,
            argument_has_metatable=argument_has_metatable,
            upvalue_marker_kind=upvalue_marker_kind,
            argument_marker_kind=argument_marker_kind,
            vector_pointer=vector_pointer,
            cookie=cookie,
            source_word=source_word,
            destination_word=destination_word,
            destination_refs=destination_refs,
            source_refs=source_refs,
            transfers=transfers,
        )
        suffix = callback.apply(
            source_state,
            {"tree": {"root": None, "nodes": []}, "payloads": []},
            {"records": [], "capacity": 0},
            source_pointer=source_pointer,
            source_word=source_word,
            destination_word=destination_word,
            destination_refs=destination_refs,
            source_refs=source_refs,
            transfers=transfers,
            allow_growth=True,
        )
    except (
        full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackTreeError(str(exc)) from exc

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
        transfer["initial"] = bound(transfer["initial"])
        transfer["final"] = bound(transfer["final"])
        for call in transfer["calls"]:
            call["before"], call["after"] = bound(call["before"]), bound(call["after"])
    _suffix_contract(
        suffix,
        source_pointer=source_pointer,
        source_word=source_word,
        destination_refs=destination_refs,
        source_refs=source_refs,
        transfers=transfers,
    )
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
            result[baseline_key] == suffix[suffix_key],
            "full-return and tree callback suffix packets disagree",
        )
    _require(
        result["normal_requests"] == result["prefix_calls"] + suffix["calls"],
        "full-return and tree callback request packets disagree",
    )

    keys = checked["inorder"]
    source_ids = {
        node["key"]: index for index, node in enumerate(source_state["tree"]["nodes"])
    }
    destination = dict(
        tree=callback.operation.tree.balancing.from_keys(keys),
        payloads=[source_state["payloads"][source_ids[key]] for key in keys],
    )
    copies = [
        dict(
            source=source_ids[key],
            destination=index,
            key=key,
            inserted=True,
            payload=destination["payloads"][index],
        )
        for index, key in enumerate(keys)
    ]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=[[0, source_pointer]], capacity=1),
        return_word=source_pointer,
        argument_kind="external",
        grew=True,
    )
    _require(
        suffix["class_operation"] == expected_operation,
        "tree class operation packet disagrees",
    )
    _require(
        result["vector"]
        == dict(
            records=[[0, source_pointer]],
            capacity=1,
            begin=vector_pointer,
            end=vector_pointer + 8,
            capacity_pointer=vector_pointer + 8,
        )
        and result["class_return"]["registers"]["eax"] == source_pointer
        and result["class_return"]["registers"]["edx"] == 0,
        "tree vector and class return packets disagree",
    )
    tree = destination["tree"]
    nodes = tree["nodes"]
    root = tree["root"]
    leftmost = rightmost = root
    if root is not None:
        while nodes[leftmost]["left"] is not None:
            leftmost = nodes[leftmost]["left"]
        while nodes[rightmost]["right"] is not None:
            rightmost = nodes[rightmost]["right"]
    result.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(source_state),
        tree_count=checked["nodes"],
        normal_field_updates={
            0: source_word,
            4: vector_pointer,
            8: vector_pointer + 8,
            12: vector_pointer + 8,
            56: checked["nodes"],
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ],
        sentinel_preserved_offsets=list(range(12, 24)),
        sentinel_link_ids=dict(root=root, leftmost=leftmost, rightmost=rightmost),
    )
    # The earlier empty-tree helper's whole-record preservation does not hold
    # across this tree continuation: only the sentinel's last twelve bytes do.
    result.pop("record_preserved_size")
    result["vector_heap_request"] = result.pop("heap_request")
    result["tree_heap_requests"] = [
        dict(continuation=0x00789463, handle=0x12345678, flags=0, bytes=24)
        for _ in keys
    ]
    result["field_updates"][56] = checked["nodes"]
    result["preserved_userdata_offsets"].remove(56)
    return result
