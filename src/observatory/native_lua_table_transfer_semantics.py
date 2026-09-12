"""Conditional Lua API request model for the two-value helper at 0x002ec050.

Entry keys are categorized by normal lua_equal results against the two sealed
string literals. This models requested stack effects, not imported Lua execution
or destination-table/metamethod effects.
"""

from __future__ import annotations
import copy

KINDS = ("init", "finalize", "other")


class TransferError(RuntimeError):
    pass


def transfer_requests(kinds, prefix_length=0):
    if (
        type(kinds) is not list
        or len(kinds) > 8
        or any(type(k) is not str or k not in KINDS for k in kinds)
    ):
        raise TransferError("invalid finite iterator key categories")
    if type(prefix_length) is not int or not 0 <= prefix_length <= 8:
        raise TransferError("invalid entry prefix length")
    initial = [("prefix", i) for i in range(prefix_length)] + [
        ("destination",),
        ("source",),
    ]
    stack = list(initial)
    trace, assignments = [], []
    cursor = 0

    def api(name, *args):
        nonlocal cursor
        before = list(stack)
        result = None
        if name == "lua_pushnil":
            stack.append(("nil",))
        elif name == "lua_next":
            assert args == (-2,) and stack[-2] == ("source",)
            previous = stack.pop()
            assert previous == (
                ("nil",) if cursor == 0 else ("key", cursor - 1, kinds[cursor - 1])
            )
            if cursor < len(kinds):
                stack.extend([("key", cursor, kinds[cursor]), ("value", cursor)])
                cursor += 1
                result = 1
            else:
                result = 0
        elif name == "lua_pushstring":
            stack.append(("literal", args[0]))
        elif name == "lua_equal":
            assert args == (-1, -3)
            literal, key = stack[-1], stack[-3]
            assert literal[0] == "literal" and key[0] == "key"
            result = int(
                key[2] == {"__init": "init", "__finalize": "finalize"}[literal[1]]
            )
        elif name == "lua_settop":
            assert args in ((-2,), (-3,))
            del stack[len(stack) + args[0] + 1 :]
        elif name == "lua_pushvalue":
            assert args == (-2,)
            stack.append(stack[-2])
        elif name == "lua_insert":
            assert args == (-2,)
            index = len(stack) - 2
            top = stack.pop()
            stack.insert(index, top)
        elif name == "lua_settable":
            assert args == (-5,) and stack[-5] == ("destination",)
            key, value = stack[-2:]
            assert key[0] == "key" and value == ("value", key[1])
            assignments.append(key[1])
            del stack[-2:]
        else:
            raise TransferError("unknown modeled API")
        trace.append(
            dict(
                api=name,
                arguments=list(args),
                before=before,
                after=list(stack),
                truth=result,
            )
        )
        return result

    api("lua_pushnil")
    while api("lua_next", -2):
        api("lua_pushstring", "__init")
        if api("lua_equal", -1, -3):
            api("lua_settop", -3)
            continue
        api("lua_settop", -2)
        api("lua_pushstring", "__finalize")
        if api("lua_equal", -1, -3):
            api("lua_settop", -3)
            continue
        api("lua_settop", -2)
        api("lua_pushvalue", -2)
        api("lua_insert", -2)
        api("lua_settable", -5)
    if stack != initial or assignments != [
        i for i, k in enumerate(kinds) if k == "other"
    ]:
        raise TransferError("independent filter or stack restoration differs")
    return dict(
        initial=copy.deepcopy(initial),
        final=copy.deepcopy(stack),
        assignments=assignments,
        skipped=[i for i, k in enumerate(kinds) if k != "other"],
        calls=trace,
        api_count=len(trace),
        lua_stack_delta=0,
    )
