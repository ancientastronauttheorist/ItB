"""Exact logical sixth spare callback over the retained fifth return.

Five external records occupy capacity six. The existing forty bytes survive
and one [0,A] record fills the last eight bytes, with no allocation, copy or
free request. Logical packets describe preservation and supplied Lua contracts;
native XMM/DF, VM effects, ownership and accounting require separate evidence.
"""

from __future__ import annotations

import copy

from src.observatory import (
    native_lua_class_factory_callback_fifth_semantics as fifth_model,
)

tree_model = fifth_model.tree_model
callback = tree_model.callback
MAX_SOURCE_NODES = 7
MAX_DESTINATION_NODES = 8


class FactoryCallbackSixthError(fifth_model.FactoryCallbackFifthError):
    pass


def _require(condition, message):
    if not condition:
        raise FactoryCallbackSixthError(message)


def _word(value, label, *, nonzero=False):
    _require(
        type(value) is int and int(nonzero) <= value <= 0xFFFFFFFF,
        label + " must be " + ("nonzero " if nonzero else "") + "uint32",
    )


def _same_packet(actual, expected):
    """Equality includes exact container and scalar types at every depth."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return set(actual) == set(expected) and all(
            _same_packet(actual[key], value) for key, value in expected.items()
        )
    if type(expected) in (list, tuple):
        return len(actual) == len(expected) and all(
            _same_packet(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


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
    fifth_vector_pointer,
    fifth_entry,
    fifth_registers,
    sixth_source_state,
    sixth_entry,
    sixth_registers,
):
    """Return detached first-through-sixth packets under exact spare premises.

    Sixth GPRs equal the fifth full return except ESP. Seven source identities,
    keys, links and colors stay fixed while strict DWORD payloads may change.
    Eight destination identities and omitted key16 survive. Exact size5/cap6
    appends eight bytes at offset40 with unchanged begin/capacity and no heap,
    copy or free. U16 (including established U13), P24 and old8/16/24/32/40
    obligations are explicit. The selected spare callback's complete stack
    [T-140,T+8) must be disjoint from all modeled data extents.
    """
    try:
        prior = fifth_model.apply(
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
            fourth_vector_pointer=fourth_vector_pointer,
            fourth_entry=fourth_entry,
            fourth_registers=fourth_registers,
            fifth_source_state=fifth_source_state,
            new_vector_pointer=fifth_vector_pointer,
            fifth_entry=fifth_entry,
            fifth_registers=fifth_registers,
        )
        fifth = prior["fifth"]
        # Rebuild the fifth transfer by key/identity before consuming any of
        # its duplicated views. Coordinated changes to those views cannot
        # authorize a changed omitted payload or a malformed retained record.
        retained = copy.deepcopy(prior["fourth"]["class_transfer"]["destination"])
        retained_checked = callback.operation.tree.validate_state(retained)
        fifth_checked = callback.operation.tree.validate_state(fifth_source_state)
        retained_ids = {
            node["key"]: identity
            for identity, node in enumerate(retained["tree"]["nodes"])
        }
        fifth_ids = {
            node["key"]: identity
            for identity, node in enumerate(fifth_source_state["tree"]["nodes"])
        }
        _require(
            retained_checked["nodes"] == MAX_DESTINATION_NODES
            and fifth_checked["nodes"] == MAX_SOURCE_NODES
            and set(fifth_ids) <= set(retained_ids)
            and 16 in retained_ids
            and 16 not in fifth_ids,
            "sixth retained fifth views disagree",
        )
        fifth_destination = copy.deepcopy(retained)
        fifth_copies = []
        for key in fifth_checked["inorder"]:
            source_id, destination_id = fifth_ids[key], retained_ids[key]
            payload = fifth_source_state["payloads"][source_id]
            fifth_destination["payloads"][destination_id] = payload
            fifth_copies.append(
                dict(
                    source=source_id,
                    destination=destination_id,
                    key=key,
                    inserted=False,
                    payload=payload,
                )
            )
        fifth_transfer = dict(destination=fifth_destination, copies=fifth_copies)
        fifth_operation = dict(
            **fifth_transfer,
            vector=dict(
                records=[[0, first_arguments["source_pointer"]] for _ in range(5)],
                capacity=6,
            ),
            return_word=first_arguments["source_pointer"],
            argument_kind="external",
            grew=True,
        )
        _require(
            type(fifth) is dict
            and _same_packet(fifth.get("source_state"), fifth_source_state)
            and _same_packet(fifth.get("class_transfer"), fifth_transfer)
            and _same_packet(fifth.get("callback_operation"), fifth_operation),
            "sixth retained fifth views disagree",
        )
        checked = callback.operation.tree.validate_state(sixth_source_state)
        _require(
            checked["nodes"] == MAX_SOURCE_NODES,
            "sixth source must contain exactly seven nodes",
        )
        _require(
            sixth_source_state["tree"] == fifth_source_state["tree"],
            "sixth source topology differs from fifth",
        )
        _word(sixth_entry, "sixth entry")
        _require(
            140 <= sixth_entry <= 0xFFFFFFF8,
            "sixth callback and spare stack extent wraps uint32",
        )
        _word(fifth_vector_pointer, "retained fifth vector pointer", nonzero=True)
        _require(
            fifth_vector_pointer + 48 <= 0xFFFFFFFF,
            "retained forty-eight-byte vector extent wraps uint32",
        )
        _require(
            type(sixth_registers) is dict
            and set(sixth_registers) == set(fifth["full_return"]["registers"]),
            "sixth register schema differs",
        )
        for register, value in sixth_registers.items():
            _word(value, "sixth " + register)
        _require(
            _same_packet(
                sixth_registers,
                dict(fifth["full_return"]["registers"], esp=sixth_entry),
            ),
            "sixth incoming registers differ from actual fifth return",
        )
        arguments = copy.deepcopy(first_arguments)
        arguments.pop("source_state")
        arguments.update(
            callback_entry=sixth_entry,
            registers=copy.deepcopy(sixth_registers),
            vector_pointer=fifth_vector_pointer,
            destination_word=first_arguments["source_word"],
        )
        sixth = tree_model.full_return_model.apply(**arguments)
        spans = (
            (first_arguments["vector_pointer"], 8, "retained first vector"),
            (second_vector_pointer, 16, "retained second vector"),
            (third_vector_pointer, 24, "retained third vector"),
            (fourth_vector_pointer, 32, "retained fourth vector"),
            (fifth_vector_pointer, 48, "retained fifth vector capacity"),
            (first_arguments["userdata"], 72, "userdata"),
            (first_arguments["record_pointer"], 24, "sentinel"),
            (first_arguments["source_pointer"], 72, "source"),
            (sixth_entry - 140, 148, "sixth callback and spare stack"),
        )
        for index, (start, size, label) in enumerate(spans):
            for other, other_size, other_label in spans[index + 1 :]:
                _require(
                    start + size <= other or other + other_size <= start,
                    label + " overlaps " + other_label,
                )
        initial = copy.deepcopy(fifth["callback_operation"]["destination"])
        initial_checked = callback.operation.tree.validate_state(initial)
        _require(
            initial_checked["nodes"] == MAX_DESTINATION_NODES,
            "retained destination must contain exactly eight nodes",
        )
        source_pointer = first_arguments["source_pointer"]
        suffix = callback.apply(
            copy.deepcopy(sixth_source_state),
            copy.deepcopy(initial),
            dict(
                records=[[0, source_pointer] for _ in range(5)],
                capacity=6,
            ),
            source_pointer=source_pointer,
            source_word=first_arguments["source_word"],
            destination_word=first_arguments["source_word"],
            destination_refs=copy.deepcopy(first_arguments["destination_refs"]),
            source_refs=copy.deepcopy(first_arguments["source_refs"]),
            transfers=copy.deepcopy(first_arguments["transfers"]),
            allow_sixth_spare=True,
        )
    except (
        fifth_model.FactoryCallbackFifthError,
        tree_model.full_return_model.FactoryCallbackReturnError,
        callback.CallbackError,
        callback.operation.tree.TransferError,
        callback.operation.tree.balancing.BalancingError,
    ) as exc:
        raise FactoryCallbackSixthError(str(exc)) from exc

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
        raise FactoryCallbackSixthError(str(exc)) from exc
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
            _same_packet(sixth[baseline_key], suffix[suffix_key]),
            "sixth full-return and callback suffix packets disagree",
        )
    prefix, caller = fifth_model.fourth_model.third_model._prefix_contract(
        first_arguments, sixth_entry
    )
    _require(
        _same_packet(sixth["calls"], prefix)
        and _same_packet(sixth["prefix_calls"], prefix)
        and _same_packet(sixth["class_caller"], caller)
        and _same_packet(sixth["initial_lua_stack"], suffix["initial_lua_stack"])
        and _same_packet(sixth["boundary_lua_stack"], suffix["initial_lua_stack"]),
        "sixth identity prefix packet disagrees",
    )
    _require(
        _same_packet(sixth["normal_requests"], prefix + suffix["calls"]),
        "sixth full-return and callback request packets disagree",
    )
    class_return = dict(
        registers=dict(
            eax=source_pointer,
            ebx=first_arguments["state"],
            ecx=first_arguments["cookie"],
            edx=0,
            esi=first_arguments["userdata"],
            edi=source_pointer,
            ebp=sixth_entry - 4,
            esp=sixth_entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    full_return = dict(
        registers=dict(
            eax=0,
            ebx=sixth_registers["ebx"],
            ecx=first_arguments["cookie"],
            edx=0xB0000300 + len(suffix["table_transfers"][1]["calls"]),
            esi=sixth_registers["esi"],
            edi=sixth_registers["edi"],
            ebp=sixth_registers["ebp"],
            esp=sixth_entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    cookie = dict(
        frame=sixth_entry - 52,
        protected_address=sixth_entry - 56,
        stored_word=first_arguments["cookie"] ^ (sixth_entry - 52),
    )
    _require(
        _same_packet(sixth["class_return"], class_return)
        and _same_packet(sixth["full_return"], full_return)
        and _same_packet(sixth["native_cookie"], cookie),
        "sixth independent normal return packet disagrees",
    )
    _require(
        16 in {node["key"] for node in initial["tree"]["nodes"]}
        and 16 not in {node["key"] for node in sixth_source_state["tree"]["nodes"]},
        "sixth retained key16 must be omitted from source",
    )
    source_ids = {
        node["key"]: index
        for index, node in enumerate(sixth_source_state["tree"]["nodes"])
    }
    destination_ids = {
        node["key"]: index for index, node in enumerate(initial["tree"]["nodes"])
    }
    _require(
        set(source_ids) <= set(destination_ids),
        "sixth source key missing from retained destination",
    )
    destination = copy.deepcopy(initial)
    copies = []
    for key in checked["inorder"]:
        source_id, destination_id = source_ids[key], destination_ids[key]
        payload = sixth_source_state["payloads"][source_id]
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
    records = [[0, source_pointer] for _ in range(6)]
    expected_operation = dict(
        destination=destination,
        copies=copies,
        vector=dict(records=records, capacity=6),
        return_word=source_pointer,
        argument_kind="external",
        grew=False,
    )
    _require(
        _same_packet(suffix["class_operation"], expected_operation),
        "sixth existing-key class operation packet disagrees",
    )
    nodes = destination["tree"]["nodes"]
    count = len(nodes)
    links = dict(
        root=destination["tree"]["root"],
        leftmost=min(range(count), key=lambda i: nodes[i]["key"]) if count else None,
        rightmost=max(range(count), key=lambda i: nodes[i]["key"]) if count else None,
    )
    _require(
        type(fifth["tree_count"]) is int
        and fifth["tree_count"] == count
        and _same_packet(fifth["sentinel_link_ids"], links)
        and _same_packet(
            fifth["vector"],
            dict(
                records=records[:5],
                capacity=6,
                begin=fifth_vector_pointer,
                end=fifth_vector_pointer + 40,
                capacity_pointer=fifth_vector_pointer + 48,
            ),
        ),
        "sixth retained fifth packet disagrees",
    )
    # Every existing-key tree iteration ends in successor(slot=class_frame-8).
    # Spare append and the cookie checker preserve that EDX; class_frame=T-52.
    sixth["class_return"]["registers"]["edx"] = sixth_entry - 60
    sixth.update(
        callback_operation=copy.deepcopy(expected_operation),
        class_transfer=copy.deepcopy(dict(destination=destination, copies=copies)),
        source_state=copy.deepcopy(sixth_source_state),
        tree_count=count,
        vector=dict(
            records=copy.deepcopy(records),
            capacity=6,
            begin=fifth_vector_pointer,
            end=fifth_vector_pointer + 48,
            capacity_pointer=fifth_vector_pointer + 48,
        ),
        tree_heap_requests=[],
        field_updates={8: fifth_vector_pointer + 48},
        preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset != 8
        ],
        normal_field_updates={
            0: first_arguments["source_word"],
            8: fifth_vector_pointer + 48,
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 8)
        ],
        sentinel_link_ids=links,
        sentinel_preserved_offsets=list(range(24)),
        preserved_vector_buffers=[
            dict(pointer=first_arguments["vector_pointer"], bytes=8),
            dict(pointer=second_vector_pointer, bytes=16),
            dict(pointer=third_vector_pointer, bytes=24),
            dict(pointer=fourth_vector_pointer, bytes=32),
            dict(pointer=fifth_vector_pointer, bytes=40),
        ],
        vector_copy_bytes=0,
        vector_append_offset=40,
        vector_append_bytes=8,
        vector_preserved_capacity_offsets=[],
    )
    sixth.pop("record_preserved_size")
    sixth.pop("heap_request")
    return dict(
        first=copy.deepcopy(prior["first"]),
        second=copy.deepcopy(prior["second"]),
        third=copy.deepcopy(prior["third"]),
        fourth=copy.deepcopy(prior["fourth"]),
        fifth=copy.deepcopy(fifth),
        sixth=sixth,
    )
