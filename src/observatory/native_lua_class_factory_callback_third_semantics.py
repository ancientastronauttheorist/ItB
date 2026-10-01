"""Bounded third normal callback on a retained factory receiver.

The first two calls construct a union of at most fourteen logical nodes. A third
source preserves the second source's canonical topology and updates existing
payloads. The full two-record vector grows to three records under supplied
successful heap responses. Requests do not establish native memory, Lua VM,
allocation, deallocation, lifetime or ownership behavior.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_extend_semantics as extend_model,
)

tree_model = extend_model.tree_model
callback = tree_model.callback
MAX_SOURCE_NODES = 7
MAX_DESTINATION_NODES = 14


class FactoryCallbackThirdError(extend_model.FactoryCallbackExtendError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackThirdError(message)


def _word(value, label, *, nonzero=False):
    _require(
        type(value) is int and int(nonzero) <= value <= 0xFFFFFFFF,
        label + " must be " + ("nonzero " if nonzero else "") + "uint32",
    )


def _prefix_contract(first, entry):
    """Reconstruct the identity-bound twelve requests and original pair."""
    state, userdata, source = (
        first[key] for key in ("state", "userdata", "source_pointer")
    )
    stack = [("argument", source)]
    calls = []

    def request(api, arguments, *, result=0, group="direct", remove=0, additions=()):
        before = list(stack)
        if remove:
            del stack[-remove:]
        stack.extend(additions)
        calls.append(
            dict(
                api=api,
                arguments=[
                    word - 2**32 if word > 0x7FFFFFFF else word for word in arguments
                ],
                result=result,
                before=before,
                after=list(stack),
                group=group,
            )
        )

    request("lua_touserdata", [state, -10003], result=userdata)
    for identity, index, kind, group in (
        (userdata, -10003, first["upvalue_marker_kind"], "marker0"),
        (source, 1, first["argument_marker_kind"], "marker1"),
    ):
        request(
            "lua_getmetatable",
            [state, index],
            result=1,
            group=group,
            additions=[("metatable", identity)],
        )
        request(
            "lua_pushstring",
            [state, 0x0083C738],
            group=group,
            additions=[("marker_key", identity)],
        )
        request(
            "lua_gettable",
            [state, -2],
            group=group,
            remove=1,
            additions=[("marker_value", identity, kind)],
        )
        request("lua_toboolean", [state, -1], result=1, group=group)
        request("lua_settop", [state, -3], group=group, remove=2)
    request("lua_touserdata", [state, 1], result=source)
    caller = dict(
        return_address=0x006EC1BD,
        argaddress=entry - 20,
        argument_record=[0, source],
        registers=dict(
            eax=entry - 20,
            ebx=state,
            ecx=userdata,
            edx=0xB1000002,
            esi=userdata,
            edi=source,
            ebp=entry - 4,
            esp=entry - 48,
        ),
    )
    return calls, caller


def apply(
    *,
    first_arguments,
    second_source_state,
    second_vector_pointer,
    second_entry,
    second_registers,
    third_source_state,
    new_vector_pointer,
    third_entry,
    third_registers,
):
    """Return detached first/second/third packets under finite call premises.

    Incoming third GPRs equal the actual second normal return except ESP. The
    third tree equals the second source tree, including IDs, links and colors;
    strict DWORD payloads may change or remain equal. Existing destination IDs,
    omitted payloads, count and all sentinel bytes survive. Growth requests
    twenty-four bytes, copies the two old records and appends the same [0,A]
    pair, then conditionally requests freeing the old sixteen-byte vector.
    """
    try:
        prior = extend_model.apply(
            first_arguments=first_arguments,
            second_source_state=second_source_state,
            new_vector_pointer=second_vector_pointer,
            second_entry=second_entry,
            second_registers=second_registers,
        )
        second = prior["second"]
        checked = callback.operation.tree.validate_state(third_source_state)
        _require(
            checked["nodes"] <= MAX_SOURCE_NODES,
            "third source exceeds seven-node model bound",
        )
        _require(
            third_source_state["tree"] == second_source_state["tree"],
            "third source topology differs from second",
        )
        _word(third_entry, "third entry")
        _word(new_vector_pointer, "new vector pointer", nonzero=True)
        _require(
            new_vector_pointer + 24 <= 0xFFFFFFFF,
            "new twenty-four-byte vector extent wraps uint32",
        )
        _require(
            type(third_registers) is dict
            and set(third_registers) == set(second["full_return"]["registers"]),
            "third register schema differs",
        )
        for register, value in third_registers.items():
            _word(value, "third " + register)
        _require(
            third_registers
            == dict(second["full_return"]["registers"], esp=third_entry),
            "third incoming registers differ from actual second return",
        )
        arguments = copy.deepcopy(first_arguments)
        arguments.pop("source_state")
        arguments.update(
            callback_entry=third_entry,
            registers=copy.deepcopy(third_registers),
            vector_pointer=new_vector_pointer,
            destination_word=first_arguments["source_word"],
        )
        third = tree_model.full_return_model.apply(**arguments)
        spans = (
            (second_vector_pointer, 16, "old vector"),
            (new_vector_pointer, 24, "new vector"),
            (first_arguments["userdata"], 72, "userdata"),
            (first_arguments["record_pointer"], 24, "sentinel"),
            (first_arguments["source_pointer"], 72, "source"),
            (third_entry - 48, 56, "third callback frame"),
        )
        for index, (start, size, label) in enumerate(spans):
            for other, other_size, other_label in spans[index + 1 :]:
                _require(
                    start + size <= other or other + other_size <= start,
                    label + " overlaps " + other_label,
                )
        initial = copy.deepcopy(second["callback_operation"]["destination"])
        initial_checked = callback.operation.tree.validate_state(initial)
        _require(
            initial_checked["nodes"] <= MAX_DESTINATION_NODES,
            "retained destination exceeds fourteen-node model bound",
        )
        suffix = callback.apply(
            copy.deepcopy(third_source_state),
            copy.deepcopy(initial),
            dict(
                records=[
                    [0, first_arguments["source_pointer"]],
                    [0, first_arguments["source_pointer"]],
                ],
                capacity=2,
            ),
            source_pointer=first_arguments["source_pointer"],
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_growth=True,
        )
    except (
        extend_model.FactoryCallbackExtendError,
        tree_model.full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackThirdError(str(exc)) from exc

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
        raise FactoryCallbackThirdError(str(exc)) from exc
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
            third[baseline_key] == suffix[suffix_key],
            "third full-return and callback suffix packets disagree",
        )
    prefix, caller = _prefix_contract(first_arguments, third_entry)
    _require(
        third["calls"] == prefix
        and third["prefix_calls"] == prefix
        and third["class_caller"] == caller
        and third["initial_lua_stack"] == suffix["initial_lua_stack"]
        and third["boundary_lua_stack"] == suffix["initial_lua_stack"],
        "third identity prefix packet disagrees",
    )
    _require(
        third["normal_requests"] == prefix + suffix["calls"],
        "third full-return and callback request packets disagree",
    )
    class_return = dict(
        registers=dict(
            eax=source_pointer,
            ebx=first_arguments["state"],
            ecx=first_arguments["cookie"],
            edx=0,
            esi=first_arguments["userdata"],
            edi=source_pointer,
            ebp=third_entry - 4,
            esp=third_entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    full_return = dict(
        registers=dict(
            eax=0,
            ebx=third_registers["ebx"],
            ecx=first_arguments["cookie"],
            edx=0xB0000300 + len(suffix["table_transfers"][1]["calls"]),
            esi=third_registers["esi"],
            edi=third_registers["edi"],
            ebp=third_registers["ebp"],
            esp=third_entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    cookie = dict(
        frame=third_entry - 52,
        protected_address=third_entry - 56,
        stored_word=first_arguments["cookie"] ^ (third_entry - 52),
    )
    _require(
        third["class_return"] == class_return
        and third["full_return"] == full_return
        and third["native_cookie"] == cookie,
        "third independent normal return packet disagrees",
    )
    source_ids = {
        node["key"]: index
        for index, node in enumerate(third_source_state["tree"]["nodes"])
    }
    destination_ids = {
        node["key"]: index for index, node in enumerate(initial["tree"]["nodes"])
    }
    _require(
        set(source_ids) <= set(destination_ids),
        "third source key missing from retained destination",
    )
    destination = copy.deepcopy(initial)
    copies = []
    for key in checked["inorder"]:
        source_id, destination_id = source_ids[key], destination_ids[key]
        payload = third_source_state["payloads"][source_id]
        destination["payloads"][destination_id] = payload
        copies.append(
            dict(
                source=source_id,
                destination=destination_id,
                key=key,
                inserted=False,
                payload=payload,
            )
        )
    records = [[0, source_pointer], [0, source_pointer], [0, source_pointer]]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=records, capacity=3),
        return_word=source_pointer,
        argument_kind="external",
        grew=True,
    )
    _require(
        suffix["class_operation"] == expected_operation,
        "third existing-key class operation packet disagrees",
    )
    nodes = destination["tree"]["nodes"]
    count = len(nodes)
    links = dict(
        root=destination["tree"]["root"],
        leftmost=min(range(count), key=lambda i: nodes[i]["key"]) if count else None,
        rightmost=max(range(count), key=lambda i: nodes[i]["key"]) if count else None,
    )
    _require(
        second["tree_count"] == count
        and second["sentinel_link_ids"] == links
        and second["vector"]
        == dict(
            records=records[:2],
            capacity=2,
            begin=second_vector_pointer,
            end=second_vector_pointer + 16,
            capacity_pointer=second_vector_pointer + 16,
        ),
        "third retained second packet disagrees",
    )
    third["class_return"]["registers"]["edx"] = 0xB0000001
    third.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(third_source_state),
        tree_count=count,
        old_vector_pointer=second_vector_pointer,
        vector=dict(
            records=copy.deepcopy(records),
            capacity=3,
            begin=new_vector_pointer,
            end=new_vector_pointer + 24,
            capacity_pointer=new_vector_pointer + 24,
        ),
        vector_heap_request=dict(
            continuation=0x00789463, handle=0x12345678, flags=0, bytes=24
        ),
        vector_free_request=dict(
            continuation=0x00789172,
            handle=0x12345678,
            flags=0,
            pointer=second_vector_pointer,
        ),
        tree_heap_requests=[],
        field_updates={
            4: new_vector_pointer,
            8: new_vector_pointer + 24,
            12: new_vector_pointer + 24,
            56: count,
        },
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12, 56)
        ],
        normal_field_updates={
            0: first_arguments["source_word"],
            4: new_vector_pointer,
            8: new_vector_pointer + 24,
            12: new_vector_pointer + 24,
            56: count,
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ],
        sentinel_link_ids=links,
        sentinel_preserved_offsets=list(range(24)),
    )
    third.pop("record_preserved_size")
    third.pop("heap_request")
    return dict(
        first=copy.deepcopy(prior["first"]), second=copy.deepcopy(second), third=third
    )
