"""Bounded fourth normal callback on a retained factory receiver.

The retained tree has at most fourteen logical nodes. A fourth source preserves
the third source's canonical topology and updates existing payloads. Successful
heap responses grow the full three-record vector to four records. These are
logical requests, without native memory, Lua VM, lifetime or ownership claims.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_third_semantics as third_model,
)

tree_model = third_model.tree_model
callback = tree_model.callback
MAX_SOURCE_NODES = 7
MAX_DESTINATION_NODES = 14


class FactoryCallbackFourthError(third_model.FactoryCallbackThirdError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackFourthError(message)


def _word(value, label, *, nonzero=False):
    _require(
        type(value) is int and int(nonzero) <= value <= 0xFFFFFFFF,
        label + " must be " + ("nonzero " if nonzero else "") + "uint32",
    )


def apply(
    *,
    first_arguments,
    second_source_state,
    second_vector_pointer,
    second_entry,
    second_registers,
    third_source_state,
    third_vector_pointer,
    third_entry,
    third_registers,
    fourth_source_state,
    new_vector_pointer,
    fourth_entry,
    fourth_registers,
):
    """Return detached first/second/third/fourth packets under finite premises.

    Fourth incoming GPRs equal the actual third full return except ESP. Source
    IDs, keys, links and colors equal the third source; strict DWORD payloads may
    change or stay equal. The destination IDs, omitted payloads, count and all
    sentinel bytes survive. Growth requests thirty-two bytes, copies three
    records, appends the same [0,A] pair and conditionally frees the old
    twenty-four-byte vector. Source words, references and recipes are reused.
    """
    try:
        prior = third_model.apply(
            first_arguments=first_arguments,
            second_source_state=second_source_state,
            second_vector_pointer=second_vector_pointer,
            second_entry=second_entry,
            second_registers=second_registers,
            third_source_state=third_source_state,
            new_vector_pointer=third_vector_pointer,
            third_entry=third_entry,
            third_registers=third_registers,
        )
        third = prior["third"]
        checked = callback.operation.tree.validate_state(fourth_source_state)
        _require(
            checked["nodes"] <= MAX_SOURCE_NODES,
            "fourth source exceeds seven-node model bound",
        )
        _require(
            fourth_source_state["tree"] == third_source_state["tree"],
            "fourth source topology differs from third",
        )
        _word(fourth_entry, "fourth entry")
        _word(new_vector_pointer, "new vector pointer", nonzero=True)
        _require(
            new_vector_pointer + 32 <= 0xFFFFFFFF,
            "new thirty-two-byte vector extent wraps uint32",
        )
        _require(
            type(fourth_registers) is dict
            and set(fourth_registers) == set(third["full_return"]["registers"]),
            "fourth register schema differs",
        )
        for register, value in fourth_registers.items():
            _word(value, "fourth " + register)
        _require(
            fourth_registers
            == dict(third["full_return"]["registers"], esp=fourth_entry),
            "fourth incoming registers differ from actual third return",
        )
        arguments = copy.deepcopy(first_arguments)
        arguments.pop("source_state")
        arguments.update(
            callback_entry=fourth_entry,
            registers=copy.deepcopy(fourth_registers),
            vector_pointer=new_vector_pointer,
            destination_word=first_arguments["source_word"],
        )
        fourth = tree_model.full_return_model.apply(**arguments)
        spans = (
            (third_vector_pointer, 24, "old vector"),
            (new_vector_pointer, 32, "new vector"),
            (first_arguments["userdata"], 72, "userdata"),
            (first_arguments["record_pointer"], 24, "sentinel"),
            (first_arguments["source_pointer"], 72, "source"),
            (fourth_entry - 48, 56, "fourth callback frame"),
        )
        for index, (start, size, label) in enumerate(spans):
            for other, other_size, other_label in spans[index + 1 :]:
                _require(
                    start + size <= other or other + other_size <= start,
                    label + " overlaps " + other_label,
                )
        initial = copy.deepcopy(third["callback_operation"]["destination"])
        initial_checked = callback.operation.tree.validate_state(initial)
        _require(
            initial_checked["nodes"] <= MAX_DESTINATION_NODES,
            "retained destination exceeds fourteen-node model bound",
        )
        source_pointer = first_arguments["source_pointer"]
        suffix = callback.apply(
            copy.deepcopy(fourth_source_state),
            copy.deepcopy(initial),
            dict(
                records=[[0, source_pointer], [0, source_pointer], [0, source_pointer]],
                capacity=3,
            ),
            source_pointer=source_pointer,
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_growth=True,
        )
    except (
        third_model.FactoryCallbackThirdError,
        tree_model.full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackFourthError(str(exc)) from exc

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
        raise FactoryCallbackFourthError(str(exc)) from exc
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
            fourth[baseline_key] == suffix[suffix_key],
            "fourth full-return and callback suffix packets disagree",
        )
    prefix, caller = third_model._prefix_contract(first_arguments, fourth_entry)
    _require(
        fourth["calls"] == prefix
        and fourth["prefix_calls"] == prefix
        and fourth["class_caller"] == caller
        and fourth["initial_lua_stack"] == suffix["initial_lua_stack"]
        and fourth["boundary_lua_stack"] == suffix["initial_lua_stack"],
        "fourth identity prefix packet disagrees",
    )
    _require(
        fourth["normal_requests"] == prefix + suffix["calls"],
        "fourth full-return and callback request packets disagree",
    )
    class_return = dict(
        registers=dict(
            eax=source_pointer,
            ebx=first_arguments["state"],
            ecx=first_arguments["cookie"],
            edx=0,
            esi=first_arguments["userdata"],
            edi=source_pointer,
            ebp=fourth_entry - 4,
            esp=fourth_entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    full_return = dict(
        registers=dict(
            eax=0,
            ebx=fourth_registers["ebx"],
            ecx=first_arguments["cookie"],
            edx=0xB0000300 + len(suffix["table_transfers"][1]["calls"]),
            esi=fourth_registers["esi"],
            edi=fourth_registers["edi"],
            ebp=fourth_registers["ebp"],
            esp=fourth_entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    cookie = dict(
        frame=fourth_entry - 52,
        protected_address=fourth_entry - 56,
        stored_word=first_arguments["cookie"] ^ (fourth_entry - 52),
    )
    _require(
        fourth["class_return"] == class_return
        and fourth["full_return"] == full_return
        and fourth["native_cookie"] == cookie,
        "fourth independent normal return packet disagrees",
    )
    source_ids = {
        node["key"]: index
        for index, node in enumerate(fourth_source_state["tree"]["nodes"])
    }
    destination_ids = {
        node["key"]: index for index, node in enumerate(initial["tree"]["nodes"])
    }
    _require(
        set(source_ids) <= set(destination_ids),
        "fourth source key missing from retained destination",
    )
    destination = copy.deepcopy(initial)
    copies = []
    for key in checked["inorder"]:
        source_id, destination_id = source_ids[key], destination_ids[key]
        payload = fourth_source_state["payloads"][source_id]
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
    records = [
        [0, source_pointer],
        [0, source_pointer],
        [0, source_pointer],
        [0, source_pointer],
    ]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=records, capacity=4),
        return_word=source_pointer,
        argument_kind="external",
        grew=True,
    )
    _require(
        suffix["class_operation"] == expected_operation,
        "fourth existing-key class operation packet disagrees",
    )
    nodes = destination["tree"]["nodes"]
    count = len(nodes)
    links = dict(
        root=destination["tree"]["root"],
        leftmost=min(range(count), key=lambda i: nodes[i]["key"]) if count else None,
        rightmost=max(range(count), key=lambda i: nodes[i]["key"]) if count else None,
    )
    _require(
        third["tree_count"] == count
        and third["sentinel_link_ids"] == links
        and third["vector"]
        == dict(
            records=records[:3],
            capacity=3,
            begin=third_vector_pointer,
            end=third_vector_pointer + 24,
            capacity_pointer=third_vector_pointer + 24,
        ),
        "fourth retained third packet disagrees",
    )
    fourth["class_return"]["registers"]["edx"] = 0xB0000001
    fourth.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(fourth_source_state),
        tree_count=count,
        old_vector_pointer=third_vector_pointer,
        vector=dict(
            records=copy.deepcopy(records),
            capacity=4,
            begin=new_vector_pointer,
            end=new_vector_pointer + 32,
            capacity_pointer=new_vector_pointer + 32,
        ),
        vector_heap_request=dict(
            continuation=0x00789463, handle=0x12345678, flags=0, bytes=32
        ),
        vector_free_request=dict(
            continuation=0x00789172,
            handle=0x12345678,
            flags=0,
            pointer=third_vector_pointer,
        ),
        tree_heap_requests=[],
        field_updates={
            4: new_vector_pointer,
            8: new_vector_pointer + 32,
            12: new_vector_pointer + 32,
            56: count,
        },
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12, 56)
        ],
        normal_field_updates={
            0: first_arguments["source_word"],
            4: new_vector_pointer,
            8: new_vector_pointer + 32,
            12: new_vector_pointer + 32,
            56: count,
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ],
        sentinel_link_ids=links,
        sentinel_preserved_offsets=list(range(24)),
    )
    fourth.pop("record_preserved_size")
    fourth.pop("heap_request")
    return dict(
        first=copy.deepcopy(prior["first"]),
        second=copy.deepcopy(prior["second"]),
        third=copy.deepcopy(third),
        fourth=fourth,
    )
