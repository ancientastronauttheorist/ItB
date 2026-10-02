"""Exact logical fifth callback over the retained seven-source/eight-node tree.

The full four-record vector grows to capacity six, copies thirty-two bytes and
appends one external [0,A] record under supplied successful heap responses.
The logical packet states byte-preservation obligations without executing native
memory, SIMD, a Lua VM, allocation, deallocation or ownership operations. Native
XMM/DF machine evidence belongs to the separate fifth conformance receipt.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_fourth_semantics as fourth_model,
)

tree_model = fourth_model.tree_model
callback = tree_model.callback
MAX_SOURCE_NODES = 7
MAX_DESTINATION_NODES = 8


class FactoryCallbackFifthError(fourth_model.FactoryCallbackFourthError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackFifthError(message)


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
    fourth_vector_pointer,
    fourth_entry,
    fourth_registers,
    fifth_source_state,
    new_vector_pointer,
    fifth_entry,
    fifth_registers,
):
    """Return detached first-through-fifth packets under exact finite premises.

    Fifth GPRs equal the actual fourth full return except ESP. Seven source node
    identities, keys, links and colors equal fourth; strict DWORD payloads may
    change or stay equal. Eight destination IDs and omitted key16 survive, with
    no tree allocation. Growth requests48, copies32, frees old32, appends8 and
    leaves the final eight capacity bytes intact. U13/P24 and old8/16/24/32
    obligations are explicit. The entire [T-188,T+8) callback/growth stack
    must remain disjoint from all data buffers; XMM/DF is outside this schema.
    """
    try:
        prior = fourth_model.apply(
            first_arguments=first_arguments,
            second_source_state=second_source_state,
            second_vector_pointer=second_vector_pointer,
            second_entry=second_entry,
            second_registers=second_registers,
            third_source_state=third_source_state,
            third_vector_pointer=third_vector_pointer,
            third_entry=third_entry,
            third_registers=third_registers,
            fourth_source_state=fourth_source_state,
            new_vector_pointer=fourth_vector_pointer,
            fourth_entry=fourth_entry,
            fourth_registers=fourth_registers,
        )
        fourth = prior["fourth"]
        checked = callback.operation.tree.validate_state(fifth_source_state)
        _require(
            checked["nodes"] == MAX_SOURCE_NODES,
            "fifth source must contain exactly seven nodes",
        )
        _require(
            fifth_source_state["tree"] == fourth_source_state["tree"],
            "fifth source topology differs from fourth",
        )
        _word(fifth_entry, "fifth entry")
        _require(
            188 <= fifth_entry <= 0xFFFFFFF8,
            "fifth callback and growth stack extent wraps uint32",
        )
        _word(new_vector_pointer, "new vector pointer", nonzero=True)
        _require(
            new_vector_pointer + 48 <= 0xFFFFFFFF,
            "new forty-eight-byte vector extent wraps uint32",
        )
        _require(
            type(fifth_registers) is dict
            and set(fifth_registers) == set(fourth["full_return"]["registers"]),
            "fifth register schema differs",
        )
        for register, value in fifth_registers.items():
            _word(value, "fifth " + register)
        _require(
            fifth_registers
            == dict(fourth["full_return"]["registers"], esp=fifth_entry),
            "fifth incoming registers differ from actual fourth return",
        )
        arguments = copy.deepcopy(first_arguments)
        arguments.pop("source_state")
        arguments.update(
            callback_entry=fifth_entry,
            registers=copy.deepcopy(fifth_registers),
            vector_pointer=new_vector_pointer,
            destination_word=first_arguments["source_word"],
        )
        fifth = tree_model.full_return_model.apply(**arguments)
        spans = (
            (first_arguments["vector_pointer"], 8, "retained first vector"),
            (second_vector_pointer, 16, "retained second vector"),
            (third_vector_pointer, 24, "retained third vector"),
            (fourth_vector_pointer, 32, "old vector"),
            (new_vector_pointer, 48, "new vector"),
            (first_arguments["userdata"], 72, "userdata"),
            (first_arguments["record_pointer"], 24, "sentinel"),
            (first_arguments["source_pointer"], 72, "source"),
            (fifth_entry - 188, 196, "fifth callback and growth stack"),
        )
        for index, (start, size, label) in enumerate(spans):
            for other, other_size, other_label in spans[index + 1 :]:
                _require(
                    start + size <= other or other + other_size <= start,
                    label + " overlaps " + other_label,
                )
        initial = copy.deepcopy(fourth["callback_operation"]["destination"])
        initial_checked = callback.operation.tree.validate_state(initial)
        _require(
            initial_checked["nodes"] == MAX_DESTINATION_NODES,
            "retained destination must contain exactly eight nodes",
        )
        source_pointer = first_arguments["source_pointer"]
        suffix = callback.apply(
            copy.deepcopy(fifth_source_state),
            copy.deepcopy(initial),
            dict(
                records=[[0, source_pointer] for _ in range(4)],
                capacity=4,
            ),
            source_pointer=source_pointer,
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_growth=True,
            allow_fifth_growth=True,
        )
    except (
        fourth_model.FactoryCallbackFourthError,
        tree_model.full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackFifthError(str(exc)) from exc

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
        raise FactoryCallbackFifthError(str(exc)) from exc
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
            fifth[baseline_key] == suffix[suffix_key],
            "fifth full-return and callback suffix packets disagree",
        )
    prefix, caller = fourth_model.third_model._prefix_contract(
        first_arguments, fifth_entry
    )
    _require(
        fifth["calls"] == prefix
        and fifth["prefix_calls"] == prefix
        and fifth["class_caller"] == caller
        and fifth["initial_lua_stack"] == suffix["initial_lua_stack"]
        and fifth["boundary_lua_stack"] == suffix["initial_lua_stack"],
        "fifth identity prefix packet disagrees",
    )
    _require(
        fifth["normal_requests"] == prefix + suffix["calls"],
        "fifth full-return and callback request packets disagree",
    )
    class_return = dict(
        registers=dict(
            eax=source_pointer,
            ebx=first_arguments["state"],
            ecx=first_arguments["cookie"],
            edx=0,
            esi=first_arguments["userdata"],
            edi=source_pointer,
            ebp=fifth_entry - 4,
            esp=fifth_entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    full_return = dict(
        registers=dict(
            eax=0,
            ebx=fifth_registers["ebx"],
            ecx=first_arguments["cookie"],
            edx=0xB0000300 + len(suffix["table_transfers"][1]["calls"]),
            esi=fifth_registers["esi"],
            edi=fifth_registers["edi"],
            ebp=fifth_registers["ebp"],
            esp=fifth_entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    cookie = dict(
        frame=fifth_entry - 52,
        protected_address=fifth_entry - 56,
        stored_word=first_arguments["cookie"] ^ (fifth_entry - 52),
    )
    _require(
        fifth["class_return"] == class_return
        and fifth["full_return"] == full_return
        and fifth["native_cookie"] == cookie,
        "fifth independent normal return packet disagrees",
    )
    _require(
        16 in {node["key"] for node in initial["tree"]["nodes"]}
        and 16 not in {node["key"] for node in fifth_source_state["tree"]["nodes"]},
        "fifth retained key16 must be omitted from source",
    )
    source_ids = {
        node["key"]: index
        for index, node in enumerate(fifth_source_state["tree"]["nodes"])
    }
    destination_ids = {
        node["key"]: index for index, node in enumerate(initial["tree"]["nodes"])
    }
    _require(
        set(source_ids) <= set(destination_ids),
        "fifth source key missing from retained destination",
    )
    destination = copy.deepcopy(initial)
    copies = []
    for key in checked["inorder"]:
        source_id, destination_id = source_ids[key], destination_ids[key]
        payload = fifth_source_state["payloads"][source_id]
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
        [0, source_pointer],
    ]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=records, capacity=6),
        return_word=source_pointer,
        argument_kind="external",
        grew=True,
    )
    _require(
        suffix["class_operation"] == expected_operation,
        "fifth existing-key class operation packet disagrees",
    )
    nodes = destination["tree"]["nodes"]
    count = len(nodes)
    links = dict(
        root=destination["tree"]["root"],
        leftmost=min(range(count), key=lambda i: nodes[i]["key"]) if count else None,
        rightmost=max(range(count), key=lambda i: nodes[i]["key"]) if count else None,
    )
    _require(
        fourth["tree_count"] == count
        and fourth["sentinel_link_ids"] == links
        and fourth["vector"]
        == dict(
            records=records[:4],
            capacity=4,
            begin=fourth_vector_pointer,
            end=fourth_vector_pointer + 32,
            capacity_pointer=fourth_vector_pointer + 32,
        ),
        "fifth retained fourth packet disagrees",
    )
    fifth["class_return"]["registers"]["edx"] = 0xB0000001
    fifth.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(fifth_source_state),
        tree_count=count,
        old_vector_pointer=fourth_vector_pointer,
        vector=dict(
            records=copy.deepcopy(records),
            capacity=6,
            begin=new_vector_pointer,
            end=new_vector_pointer + 40,
            capacity_pointer=new_vector_pointer + 48,
        ),
        vector_heap_request=dict(
            continuation=0x00789463, handle=0x12345678, flags=0, bytes=48
        ),
        vector_free_request=dict(
            continuation=0x00789172,
            handle=0x12345678,
            flags=0,
            pointer=fourth_vector_pointer,
        ),
        tree_heap_requests=[],
        field_updates={
            4: new_vector_pointer,
            8: new_vector_pointer + 40,
            12: new_vector_pointer + 48,
            56: count,
        },
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (4, 8, 12, 56)
        ],
        normal_field_updates={
            0: first_arguments["source_word"],
            4: new_vector_pointer,
            8: new_vector_pointer + 40,
            12: new_vector_pointer + 48,
            56: count,
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
        ],
        sentinel_link_ids=links,
        sentinel_preserved_offsets=list(range(24)),
        preserved_vector_buffers=[
            dict(pointer=first_arguments["vector_pointer"], bytes=8),
            dict(pointer=second_vector_pointer, bytes=16),
            dict(pointer=third_vector_pointer, bytes=24),
            dict(pointer=fourth_vector_pointer, bytes=32),
        ],
        vector_copy_bytes=32,
        vector_append_offset=32,
        vector_append_bytes=8,
        vector_preserved_capacity_offsets=list(range(40, 48)),
    )
    fifth.pop("record_preserved_size")
    fifth.pop("heap_request")
    return dict(
        first=copy.deepcopy(prior["first"]),
        second=copy.deepcopy(prior["second"]),
        third=copy.deepcopy(prior["third"]),
        fourth=copy.deepcopy(fourth),
        fifth=fifth,
    )
