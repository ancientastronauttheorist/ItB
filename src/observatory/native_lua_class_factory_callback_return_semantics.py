"""Bounded normal return of the factory's actual returned class callback.

Both supplied class trees are empty, the first eight-byte allocation succeeds,
and registry values and finite Lua iterator responses obey the supplied normal
contracts. This composes logical models; it executes no native code, Lua VM,
memory access, allocator or ownership operation. The retained stack is the
callback stack immediately before returning zero values to its host.
"""

from __future__ import annotations

import copy

from src.observatory import native_lua_class_callback_semantics as callback
from src.observatory import (
    native_lua_class_factory_callback_empty_class_semantics as empty_class,
)


class FactoryCallbackReturnError(empty_class.FactoryCallbackEmptyClassError):
    pass


def apply(
    *,
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
    """Compose the identity-bound twelve-call prefix and registry suffix.

    Source words and registry references are explicit uint32 premises, rather
    than reads from the supplied addresses. The source's 72 bytes, userdata,
    record, vector and original [T-48,T+8) callback frame must be disjoint.
    This checks only modeled extents, not deeper native helper scratch or heap
    ownership. It narrows the prefix's permitted source/userdata identity alias.
    The EDX response law is conditional
    on the frozen supplied Lua responses: 0xb0000300 plus the second transfer's
    API count. Preserved incoming GPRs, cookie and zero results describe the
    complete normal callback return, beyond the class helper's earlier return.
    """
    try:
        result = empty_class.apply(
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
        )
        if source_pointer + 72 > 0x100000000:
            raise FactoryCallbackReturnError("source pointer extent wraps uint32")
        spans = (
            (userdata, 72, "userdata"),
            (record_pointer, 24, "record"),
            (source_pointer, 72, "source"),
            (vector_pointer, 8, "vector"),
            (callback_entry - 48, 56, "original callback frame"),
        )
        for index, (pointer, size, label) in enumerate(spans):
            for other_pointer, other_size, other_label in spans[index + 1 :]:
                if (
                    pointer < other_pointer + other_size
                    and other_pointer < pointer + size
                ):
                    raise FactoryCallbackReturnError(f"{label} overlaps {other_label}")
        suffix = callback.apply(
            {"tree": {"root": None, "nodes": []}, "payloads": []},
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
    except (empty_class.FactoryCallbackEmptyClassError, callback.CallbackError) as exc:
        raise FactoryCallbackReturnError(str(exc)) from exc

    operation = suffix["class_operation"]
    if (
        operation["vector"]
        != {
            "records": result["vector"]["records"],
            "capacity": result["vector"]["capacity"],
        }
        or operation["vector"]["records"] != [result["class_caller"]["argument_record"]]
        or operation["return_word"] != result["class_return"]["registers"]["eax"]
        or operation["argument_kind"] != "external"
        or operation["grew"] is not True
        or operation["destination"]
        != {"tree": {"root": None, "nodes": []}, "payloads": []}
        or operation["copies"] != []
    ):
        raise FactoryCallbackReturnError(
            "class and vector continuation packets disagree"
        )

    def identity_bound(snapshot):
        return [
            ("argument", source_pointer) if token == ("argument", 0) else token
            for token in snapshot
        ]

    suffix["initial_lua_stack"] = identity_bound(suffix["initial_lua_stack"])
    suffix["final_lua_stack"] = identity_bound(suffix["final_lua_stack"])
    for call in suffix["calls"]:
        call["before"] = identity_bound(call["before"])
        call["after"] = identity_bound(call["after"])
    for transfer in suffix["table_transfers"]:
        transfer["initial"] = identity_bound(transfer["initial"])
        transfer["final"] = identity_bound(transfer["final"])
        for call in transfer["calls"]:
            call["before"] = identity_bound(call["before"])
            call["after"] = identity_bound(call["after"])

    if result["boundary_lua_stack"] != suffix["initial_lua_stack"]:
        raise FactoryCallbackReturnError(
            "prefix and suffix Lua stack identities disagree"
        )
    prefix_calls = copy.deepcopy(result["calls"])
    registry_table_calls = copy.deepcopy(suffix["calls"])
    result.update(
        callback_operation=copy.deepcopy(operation),
        source_word=source_word,
        destination_word=suffix["destination_word"],
        return_count=suffix["return_count"],
        full_return=dict(
            registers=dict(
                eax=0,
                ebx=registers["ebx"],
                ecx=cookie,
                edx=0xB0000300 + len(suffix["table_transfers"][1]["calls"]),
                esi=registers["esi"],
                edi=registers["edi"],
                ebp=registers["ebp"],
                esp=callback_entry + 4,
            ),
            flags=0x44,
            flag_mask=0xCD5,
            endpoint=0x0400A000,
            return_count=0,
        ),
        normal_field_updates={
            0: source_word,
            4: vector_pointer,
            8: vector_pointer + 8,
            12: vector_pointer + 8,
        },
        normal_preserved_userdata_offsets=[
            offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12)
        ],
        prefix_calls=prefix_calls,
        registry_table_calls=registry_table_calls,
        normal_requests=copy.deepcopy(prefix_calls + registry_table_calls),
        normal_initial_lua_stack=copy.deepcopy(suffix["initial_lua_stack"]),
        normal_final_lua_stack=copy.deepcopy(suffix["final_lua_stack"]),
        normal_lua_stack_delta=suffix["lua_stack_delta"],
        requested_assignments=copy.deepcopy(suffix["requested_assignments"]),
        registry_requests=copy.deepcopy(suffix["registry_requests"]),
        table_transfers=copy.deepcopy(suffix["table_transfers"]),
    )
    return result
