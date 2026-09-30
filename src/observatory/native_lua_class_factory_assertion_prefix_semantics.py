"""Independent factory and initializer requests before the context assertion."""

from __future__ import annotations
import copy
from src.observatory import native_lua_class_factory_prefix_semantics as prefix


class FactoryAssertionPrefixError(RuntimeError):
    pass


def apply(
    *,
    state,
    first_pointer,
    second_pointer,
    userdata,
    name_bytes,
    context_pointer,
    context_guard,
    references,
):
    if type(context_pointer) is not int or not 1 <= context_pointer <= 0xFFFFFFFF - 15:
        raise FactoryAssertionPrefixError(
            "context pointer must cover its guard without wrapping"
        )
    if type(context_guard) is not int or context_guard != 0xFFFFFFFE:
        raise FactoryAssertionPrefixError("context guard must select the assertion arm")
    if (
        type(references) is not list
        or len(references) != 2
        or any(type(r) is not int or not 1 <= r <= 0x7FFFFFFF for r in references)
        or len(set(references)) != 2
    ):
        raise FactoryAssertionPrefixError(
            "references must be two distinct positive int32 words"
        )
    try:
        first = prefix.apply(
            name_bytes,
            state=state,
            first_pointer=first_pointer,
            second_pointer=second_pointer,
            userdata=userdata,
        )
    except prefix.FactoryPrefixError as exc:
        raise FactoryAssertionPrefixError(str(exc)) from exc
    if userdata + 63 > 0xFFFFFFFF:
        raise FactoryAssertionPrefixError("userdata write extent wraps uint32")
    calls = [
        {
            k: copy.deepcopy(c[k])
            for k in ("api", "arguments", "result", "before", "after")
        }
        | dict(phase="factory_prefix", literal_role=None)
        for c in first["calls"]
    ]
    stack = list(first["final_lua_stack"])

    def request(name, args, result=0, remove=0, additions=(), role=None):
        before = list(stack)
        if remove:
            del stack[-remove:]
        stack.extend(additions)
        calls.append(
            dict(
                api=name,
                arguments=list(args),
                result=result,
                before=before,
                after=list(stack),
                phase="initializer",
                literal_role=role,
            )
        )

    for i, reference in enumerate(references, 1):
        table = ("table", i)
        request("lua_createtable", [state, 0, 0], additions=[table])
        request("lua_pushvalue", [state, -1], additions=[table])
        request("luaL_ref", [state, -10000], reference, remove=1)
    request("lua_settop", [state, -3], remove=2)
    request(
        "lua_pushstring",
        [state, 0x83BF18],
        additions=[("literal", "classes")],
        role="classes",
    )
    request(
        "lua_gettable",
        [state, -10000],
        remove=1,
        additions=[("registry_value", "classes", context_pointer)],
    )
    request("lua_touserdata", [state, -1], context_pointer)
    request("lua_settop", [state, -2], remove=1)
    fields = {
        0: 0x89D1D4,
        4: 0,
        8: 0,
        12: 0,
        16: second_pointer,
        20: 0,
        24: 0xFFFFFFFE,
        28: state,
        32: references[0],
        36: state,
        40: references[1],
        44: 1,
        56: 0,
        60: 0,
    }
    return dict(
        calls=calls,
        initial_lua_stack=list(first["initial_lua_stack"]),
        boundary_lua_stack=list(stack),
        registry_bindings=[
            dict(reference=r, value=("table", i)) for i, r in enumerate(references, 1)
        ],
        final_fields=fields,
        unmodeled_fields=[48, 52, 64, 68],
        context_reads=[dict(offset=12, value=context_guard)],
        native_boundary=dict(
            target_rva=0x379CC2,
            call_rva=0x2EAE76,
            continuation=0x6EAE7B,
            arguments=[0x83C6B0, 0x83C680, 96],
        ),
        frame=dict(
            boundary_esp_delta_from_initializer_ebp=-48,
            stack_words=[0x6EAE7B, 0x83C6B0, 0x83C680, 96],
        ),
    )
