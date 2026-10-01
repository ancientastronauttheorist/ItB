"""Independent third-call payload, vector growth, identity and ABI laws."""

import copy
import pytest

from src.observatory import native_lua_class_factory_callback_third_semantics as model
from src.observatory import native_tree_balancing_semantics as balancing


def source(keys, seed=0x75310000):
    return dict(
        tree=balancing.from_keys(keys),
        payloads=[
            (seed ^ index * 0x01010101) & 0xFFFFFFFF for index in range(len(keys))
        ],
    )


def arguments(keys=None, **changes):
    entry = changes.get("callback_entry", 0x30001030)
    userdata = changes.get("userdata", 0x14000087)
    result = dict(
        source_state=source([5, 1, 3] if keys is None else keys),
        state=0x12001000,
        userdata=userdata,
        record_pointer=0x16000FFF,
        source_pointer=0x1A000100,
        callback_entry=entry,
        registers=dict(
            eax=0xFFFFFFFF,
            ebx=0x80000000,
            ecx=0x12345678,
            edx=0,
            esi=0xAAAAAAAA,
            edi=0x55555555,
            ebp=0x87654321,
            esp=entry,
        ),
        closure_target=0x006EC110,
        closure_upvalues=[userdata],
        upvalue_has_metatable=True,
        argument_has_metatable=True,
        upvalue_marker_kind="zero",
        argument_marker_kind="table",
        vector_pointer=0x06002007,
        cookie=0xD43782A1,
        source_word=0xFEDCBA98,
        destination_word=0x87654321,
        destination_refs=[11, 22],
        source_refs=[33, 44],
        transfers=[["init", "other", "finalize"], ["other", "finalize", "init"]],
    )
    result.update(changes)
    return result


def inputs(first=None, second_keys=None, **changes):
    first = arguments() if first is None else first
    entry = changes.get("second_entry", 0x31001037)
    first_result = model.tree_model.apply(**first)
    second = source([6, 0, 3] if second_keys is None else second_keys, 0xFFFFFFFF)
    second_registers = dict(first_result["full_return"]["registers"], esp=entry)
    prior = model.extend_model.apply(
        first_arguments=first,
        second_source_state=second,
        new_vector_pointer=0x0700301F,
        second_entry=entry,
        second_registers=second_registers,
    )
    third_entry = changes.get("third_entry", 0x3200103F)
    third = copy.deepcopy(second)
    third["payloads"] = [value ^ 0xFFFFFFFF for value in third["payloads"]]
    result = dict(
        first_arguments=first,
        second_source_state=second,
        second_vector_pointer=0x0700301F,
        second_entry=entry,
        second_registers=second_registers,
        third_source_state=third,
        new_vector_pointer=0x08004007,
        third_entry=third_entry,
        third_registers=dict(
            prior["second"]["full_return"]["registers"], esp=third_entry
        ),
    )
    result.update(changes)
    return result


def values(state):
    return {
        node["key"]: state["payloads"][index]
        for index, node in enumerate(state["tree"]["nodes"])
    }


def check_redblack(tree):
    nodes, visited, inorder = tree["nodes"], set(), []

    def visit(index, parent, low, high):
        if index is None:
            return 1
        assert type(index) is int and 0 <= index < len(nodes) and index not in visited
        visited.add(index)
        node = nodes[index]
        assert node["parent"] == parent and low < node["key"] < high
        assert type(node["color"]) is int and node["color"] in (0, 1)
        if node["color"] == 0:
            assert all(
                child is None or nodes[child]["color"] == 1
                for child in (node["left"], node["right"])
            )
        left = visit(node["left"], index, low, node["key"])
        inorder.append(node["key"])
        right = visit(node["right"], index, node["key"], high)
        assert left == right
        return left + node["color"]

    if tree["root"] is not None:
        assert nodes[tree["root"]]["color"] == 1
    visit(tree["root"], None, -1, 2**32)
    assert len(visited) == len(nodes)
    return inorder


SCENARIOS = [
    ([], []),
    ([], [0xFFFFFFFF]),
    ([5, 1, 3], []),
    ([5, 1, 3], [6, 0, 3]),
    (list(range(6, -1, -1)), list(range(7))),
    (list(range(6, -1, -1)), list(range(13, 6, -1))),
    ([1, 16, 255], [0xFFFFFFFF, 0x80000000, 255, 17, 7, 1, 0]),
    (
        [0xFFFFFFFF, 0xFFFFFFFE, 0x80000000, 255, 16, 1, 0],
        [0xFFFFFFFD, 0xFFFFFFFC, 0x80000001, 254, 17, 2, 3],
    ),
]


@pytest.mark.parametrize("first_keys,second_keys", SCENARIOS)
@pytest.mark.parametrize("profile", ("unchanged", "flip", "distinct"))
def test_third_union_topology_existing_ids_and_omitted_payloads(
    first_keys, second_keys, profile
):
    kwargs = inputs(arguments(first_keys), second_keys)
    if profile == "unchanged":
        kwargs["third_source_state"] = kwargs["second_source_state"]
    elif profile == "distinct":
        kwargs["third_source_state"]["payloads"] = [
            (0xA50F7312 + index * 0x112233) & 0xFFFFFFFF
            for index in range(len(second_keys))
        ]
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    assert kwargs == before and set(result) == {"first", "second", "third"}
    first, second, third = (result[key] for key in ("first", "second", "third"))
    prior = second["callback_operation"]["destination"]
    final = third["callback_operation"]["destination"]
    assert final["tree"] == prior["tree"]
    assert check_redblack(final["tree"]) == sorted(set(first_keys) | set(second_keys))
    assert values(prior) == {
        **values(first["callback_operation"]["destination"]),
        **values(kwargs["second_source_state"]),
    }
    assert values(final) == {**values(prior), **values(kwargs["third_source_state"])}
    destination_keys = [node["key"] for node in prior["tree"]["nodes"]]
    source_keys = [
        node["key"] for node in kwargs["third_source_state"]["tree"]["nodes"]
    ]
    copies = [
        dict(
            source=source_keys.index(key),
            destination=destination_keys.index(key),
            key=key,
            inserted=False,
            payload=values(kwargs["third_source_state"])[key],
        )
        for key in sorted(second_keys)
    ]
    assert third["callback_operation"] == dict(
        destination=final,
        copies=copies,
        vector=dict(
            records=[[0, kwargs["first_arguments"]["source_pointer"]]] * 3, capacity=3
        ),
        return_word=kwargs["first_arguments"]["source_pointer"],
        argument_kind="external",
        grew=True,
    )
    assert third["class_transfer"] == dict(destination=final, copies=copies)
    assert third["source_state"] == kwargs["third_source_state"]
    for identity, key in enumerate(destination_keys):
        assert final["tree"]["nodes"][identity]["key"] == key
        if key not in second_keys:
            assert final["payloads"][identity] == prior["payloads"][identity]
    assert (
        third["tree_count"]
        == second["tree_count"]
        == len(set(first_keys) | set(second_keys))
    )
    assert third["sentinel_link_ids"] == second["sentinel_link_ids"]
    assert third["sentinel_preserved_offsets"] == list(range(24))
    assert third["tree_heap_requests"] == []


def test_maximum_fourteen_node_retained_union_and_all_seven_third_updates():
    kwargs = inputs(arguments(list(range(7))), list(range(7, 14)))
    result = model.apply(**kwargs)
    assert result["third"]["tree_count"] == 14
    assert len(result["third"]["class_transfer"]["copies"]) == 7
    assert all(
        not row["inserted"] for row in result["third"]["class_transfer"]["copies"]
    )
    assert (
        result["third"]["callback_operation"]["destination"]["payloads"][:7]
        == result["first"]["callback_operation"]["destination"]["payloads"]
    )


@pytest.mark.parametrize("alignment", (0, 7, 31))
@pytest.mark.parametrize("source_pointer", (1, 0x80000000, 0x1A000100, 0xFFFFFFB8))
def test_two_records_copy_and_third_append_grow_to_capacity_three_24_bytes(
    alignment, source_pointer
):
    kwargs = inputs(
        arguments(source_pointer=source_pointer),
        new_vector_pointer=0x08004000 + alignment,
    )
    result = model.apply(**kwargs)
    second, third = result["second"], result["third"]
    new, old = kwargs["new_vector_pointer"], kwargs["second_vector_pointer"]
    records = [[0, source_pointer], [0, source_pointer], [0, source_pointer]]
    assert (
        second["vector"]["records"] == records[:2] and second["vector"]["capacity"] == 2
    )
    assert third["vector"] == dict(
        records=records, capacity=3, begin=new, end=new + 24, capacity_pointer=new + 24
    )
    pair = b"\0" * 4 + source_pointer.to_bytes(4, "little")
    encoded = b"".join(
        word.to_bytes(4, "little")
        for record in third["vector"]["records"]
        for word in record
    )
    assert encoded[:16] == pair * 2 and encoded[16:] == pair and len(encoded) == 24
    assert third["vector_heap_request"] == dict(
        continuation=0x00789463, handle=0x12345678, flags=0, bytes=24
    )
    assert third["old_vector_pointer"] == old
    assert third["vector_free_request"] == dict(
        continuation=0x00789172, handle=0x12345678, flags=0, pointer=old
    )


@pytest.mark.parametrize("entry", (56, 57, 0x3200103F, 0xFFFFFFF8))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_actual_second_gprs_third_class_free_response_and_full_normal_return(
    entry, cookie
):
    kwargs = inputs(arguments(cookie=cookie), third_entry=entry)
    result = model.apply(**kwargs)
    third, original, incoming = (
        result["third"],
        kwargs["first_arguments"],
        kwargs["third_registers"],
    )
    assert incoming == dict(result["second"]["full_return"]["registers"], esp=entry)
    assert third["full_return"] == dict(
        registers=dict(
            eax=0,
            ebx=incoming["ebx"],
            ecx=cookie,
            edx=0xB0000317,
            esi=incoming["esi"],
            edi=incoming["edi"],
            ebp=incoming["ebp"],
            esp=entry + 4,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x0400A000,
        return_count=0,
    )
    assert third["class_return"] == dict(
        registers=dict(
            eax=original["source_pointer"],
            ebx=original["state"],
            ecx=cookie,
            edx=0xB0000001,
            esi=original["userdata"],
            edi=original["source_pointer"],
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    assert third["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert third["class_caller"]["argument_record"] == [0, original["source_pointer"]]
    assert third["class_caller"]["argaddress"] == entry - 20


RECIPES = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["init", "other"], ["other", "finalize"]),
    (["other"] * 3, ["other"] * 3),
]


@pytest.mark.parametrize("recipes", RECIPES)
@pytest.mark.parametrize("word", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_reused_identity_prefix_registry_tables_requests_and_five_lua_values(
    recipes, word
):
    kwargs = inputs(
        arguments(
            source_word=word,
            destination_refs=[0, 0xFFFFFFFF],
            source_refs=[0xFFFFFFFF, 0],
            transfers=list(recipes),
        )
    )
    result = model.apply(**kwargs)
    third = result["third"]
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in recipes
    ]
    for stage in (result["first"], result["second"]):
        for key in (
            "prefix_calls",
            "registry_table_calls",
            "normal_requests",
            "normal_initial_lua_stack",
            "normal_final_lua_stack",
            "registry_requests",
            "table_transfers",
            "requested_assignments",
        ):
            assert third[key] == stage[key]
    assert len(third["prefix_calls"]) == 12
    assert len(third["normal_requests"]) == 16 + sum(counts)
    assert third["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert third["requested_assignments"] == [
        [index for index, kind in enumerate(recipe) if kind == "other"]
        for recipe in recipes
    ]
    assert third["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert third["source_word"] == third["destination_word"] == word
    assert third["normal_lua_stack_delta"] == 4 and third["return_count"] == 0
    assert all(
        left["after"] == right["before"]
        for left, right in zip(third["normal_requests"], third["normal_requests"][1:])
    )


def test_third_updates_preserve_thirteen_userdata_words_and_twenty_four_sentinel_bytes():
    kwargs = inputs()
    third = model.apply(**kwargs)["third"]
    pointer, word = (
        kwargs["new_vector_pointer"],
        kwargs["first_arguments"]["source_word"],
    )
    assert third["normal_field_updates"] == {
        0: word,
        4: pointer,
        8: pointer + 24,
        12: pointer + 24,
        56: 5,
    }
    assert third["field_updates"] == {
        4: pointer,
        8: pointer + 24,
        12: pointer + 24,
        56: 5,
    }
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert (
        third["normal_preserved_userdata_offsets"] == preserved and len(preserved) == 13
    )
    assert third["preserved_userdata_offsets"] == [0] + preserved
    before = bytes((index * 71 + 13) % 256 for index in range(72))
    after = bytearray(before)
    for offset, value in third["normal_field_updates"].items():
        after[offset : offset + 4] = value.to_bytes(4, "little")
    assert all(
        after[offset : offset + 4] == before[offset : offset + 4]
        for offset in preserved
    )
    assert third["sentinel_preserved_offsets"] == list(range(24))


@pytest.mark.parametrize("state", (1, 0x80000000, 0xFFFFFFFF))
@pytest.mark.parametrize(
    "upvalue_kind,argument_kind",
    [
        (u, a)
        for u in ("zero", "empty_string", "table")
        for a in ("zero", "empty_string", "table")
    ],
)
def test_identity_prefix_marker_order_signed_arguments_and_original_pair(
    state, upvalue_kind, argument_kind
):
    kwargs = inputs(
        arguments(
            state=state,
            upvalue_marker_kind=upvalue_kind,
            argument_marker_kind=argument_kind,
        )
    )
    third = model.apply(**kwargs)["third"]
    prefix = third["prefix_calls"]
    signed_state = state if state < 0x80000000 else state - 2**32
    assert [row["api"] for row in prefix] == ["lua_touserdata"] + [
        "lua_getmetatable",
        "lua_pushstring",
        "lua_gettable",
        "lua_toboolean",
        "lua_settop",
    ] * 2 + ["lua_touserdata"]
    assert prefix[0]["arguments"] == [signed_state, -10003]
    assert prefix[6]["arguments"] == [signed_state, 1]
    assert prefix[-1]["arguments"] == [signed_state, 1]
    assert prefix[3]["after"][-1] == (
        "marker_value",
        kwargs["first_arguments"]["userdata"],
        upvalue_kind,
    )
    assert prefix[8]["after"][-1] == (
        "marker_value",
        kwargs["first_arguments"]["source_pointer"],
        argument_kind,
    )
    assert prefix[-1]["after"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"])
    ]
    assert third["class_caller"]["argument_record"] == [
        0,
        kwargs["first_arguments"]["source_pointer"],
    ]


@pytest.mark.parametrize(
    "field",
    (
        "source_word",
        "destination_word",
        "state",
        "cookie",
        "destination_ref",
        "source_ref",
        "closure_target",
        "closure_upvalue",
        "source_alias",
        "transfer_kind",
        "transfer_bound",
    ),
)
def test_inherited_word_reference_closure_extent_and_iterator_validation(field):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    if field in ("source_word", "destination_word", "state", "cookie"):
        first[field] = True
    elif field in ("destination_ref", "source_ref"):
        first["destination_refs" if field == "destination_ref" else "source_refs"][
            0
        ] = True
    elif field == "closure_target":
        first["closure_target"] ^= 1
    elif field == "closure_upvalue":
        first["closure_upvalues"][0] ^= 1
    elif field == "source_alias":
        first["source_pointer"] = first["userdata"]
    elif field == "transfer_kind":
        first["transfers"][0] = ["unreviewed"]
    else:
        first["transfers"][0] = ["other"] * 4
    with pytest.raises(model.FactoryCallbackThirdError):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_every_incoming_third_gpr_must_equal_actual_second_return(register):
    kwargs = inputs()
    kwargs["third_registers"][register] ^= 1
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackThirdError, match="actual second return"):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field", ("new_vector_pointer", "third_entry", "third_register_word")
)
@pytest.mark.parametrize("value", (False, True, -1, 2**32, 1.0, "1", None))
def test_strict_third_words(field, value):
    kwargs = inputs()
    if field == "third_register_word":
        kwargs["third_registers"]["eax"] = value
    else:
        kwargs[field] = value
    with pytest.raises(model.FactoryCallbackThirdError):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "kind",
    (
        "register_missing",
        "register_extra",
        "register_tuple",
        "source_schema",
        "payload_bool",
        "payload_wide",
        "payload_count",
        "source_key",
        "source_topology",
        "source_color",
        "source_eight",
        "entry_below_cookie",
        "entry_wrap",
        "new_zero",
        "new_wrap",
        "first_eight",
        "second_eight",
        "first_schema",
        "second_register",
    ),
)
def test_strict_first_second_third_schemas_topology_payloads_and_extents(kind):
    kwargs = inputs()
    if kind == "register_missing":
        kwargs["third_registers"].pop("eax")
    elif kind == "register_extra":
        kwargs["third_registers"]["eip"] = 0
    elif kind == "register_tuple":
        kwargs["third_registers"] = tuple(kwargs["third_registers"].items())
    elif kind == "source_schema":
        kwargs["third_source_state"]["extra"] = 0
    elif kind == "payload_bool":
        kwargs["third_source_state"]["payloads"][0] = True
    elif kind == "payload_wide":
        kwargs["third_source_state"]["payloads"][0] = 2**32
    elif kind == "payload_count":
        kwargs["third_source_state"]["payloads"].pop()
    elif kind == "source_key":
        kwargs["third_source_state"]["tree"]["nodes"][0]["key"] = 2**32
    elif kind == "source_topology":
        kwargs["third_source_state"] = source([0, 3, 6], 0xFFFFFFFF)
    elif kind == "source_color":
        kwargs["third_source_state"]["tree"]["nodes"][0]["color"] = True
    elif kind in ("source_eight", "first_eight", "second_eight"):
        state = source(list(range(8)))
        if kind == "first_eight":
            kwargs["first_arguments"]["source_state"] = state
        else:
            kwargs[
                (
                    "third_source_state"
                    if kind == "source_eight"
                    else "second_source_state"
                )
            ] = state
    elif kind == "first_schema":
        kwargs["first_arguments"]["extra"] = 0
    elif kind == "second_register":
        kwargs["second_registers"]["eax"] ^= 1
    elif kind.startswith("entry_"):
        kwargs["third_entry"] = 55 if kind == "entry_below_cookie" else 0xFFFFFFF9
        kwargs["third_registers"]["esp"] = kwargs["third_entry"]
    else:
        kwargs["new_vector_pointer"] = 0 if kind == "new_zero" else 0xFFFFFFE8
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackThirdError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "region", ("old_vector", "userdata", "sentinel", "source", "frame")
)
@pytest.mark.parametrize("edge", ("first", "last", "new_tail"))
def test_old_sixteen_new_twenty_four_and_all_retained_extents_disjoint(region, edge):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    start, size = {
        "old_vector": (kwargs["second_vector_pointer"], 16),
        "userdata": (first["userdata"], 72),
        "sentinel": (first["record_pointer"], 24),
        "source": (first["source_pointer"], 72),
        "frame": (kwargs["third_entry"] - 48, 56),
    }[region]
    kwargs["new_vector_pointer"] = (
        start if edge == "first" else start + size - 1 if edge == "last" else start - 23
    )
    with pytest.raises(model.FactoryCallbackThirdError, match="overlap"):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "relation", ("old_before", "old_after", "uint32_end", "reuses_first_freed_domain")
)
def test_adjacent_extents_and_first_freed_address_reuse_have_no_ownership_claim(
    relation,
):
    kwargs = inputs()
    if relation == "old_before":
        kwargs["new_vector_pointer"] = kwargs["second_vector_pointer"] - 24
    elif relation == "old_after":
        kwargs["new_vector_pointer"] = kwargs["second_vector_pointer"] + 16
    elif relation == "uint32_end":
        kwargs["new_vector_pointer"] = 0xFFFFFFE7
    else:
        kwargs["new_vector_pointer"] = kwargs["first_arguments"]["vector_pointer"]
    third = model.apply(**kwargs)["third"]
    assert third["vector"]["end"] == kwargs["new_vector_pointer"] + 24


@pytest.mark.parametrize(
    "field", ("destination", "copies", "vector", "return_word", "argument_kind", "grew")
)
def test_corrupted_actual_third_class_packet_rejected_independently(monkeypatch, field):
    kwargs, original, reached = inputs(), model.callback.apply, []

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original(source_state, destination_state, vector, **arguments)
        if len(vector["records"]) == 2:
            reached.append(True)
            operation = result["class_operation"]
            if field == "destination":
                operation["destination"]["payloads"][1] ^= 1
            elif field == "copies":
                operation["copies"][0]["destination"] ^= 1
            elif field == "vector":
                operation["vector"]["capacity"] = 4
            elif field == "return_word":
                operation["return_word"] ^= 1
            elif field == "argument_kind":
                operation["argument_kind"] = "inline"
            else:
                operation["grew"] = False
        return result

    monkeypatch.setattr(model.callback, "apply", corrupted)
    with pytest.raises(
        model.FactoryCallbackThirdError,
        match="third existing-key class operation packet",
    ):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize("field", ("registry", "tables", "assignments", "stack"))
def test_coordinated_empty_baseline_and_actual_third_suffix_still_rejected(
    monkeypatch, field
):
    kwargs = inputs()
    original_callback, original_full = (
        model.callback.apply,
        model.tree_model.full_return_model.apply,
    )
    baseline, reached = [], []

    def full(**arguments):
        baseline.append(arguments["callback_entry"] == kwargs["third_entry"])
        try:
            return original_full(**arguments)
        finally:
            baseline.pop()

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original_callback(source_state, destination_state, vector, **arguments)
        if (baseline and baseline[-1]) or len(vector["records"]) == 2:
            reached.append(len(vector["records"]))
            if field == "registry":
                result["registry_requests"][0]["reference"] ^= 1
            elif field == "tables":
                result["table_transfers"][0]["assignments"].append(80)
            elif field == "assignments":
                result["requested_assignments"][0].append(80)
            else:
                result["final_lua_stack"].append(("extra",))
        return result

    monkeypatch.setattr(model.tree_model.full_return_model, "apply", full)
    monkeypatch.setattr(model.callback, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackThirdError, match="table contract"):
        model.apply(**kwargs)
    assert reached == [0, 2]


@pytest.mark.parametrize(
    "field", ("prefix", "caller", "class_return", "full_return", "cookie", "requests")
)
def test_corrupted_third_empty_baseline_prefix_or_abi_rejected(monkeypatch, field):
    kwargs, original, reached = inputs(), model.tree_model.full_return_model.apply, []

    def corrupted(**arguments):
        result = original(**arguments)
        if arguments["callback_entry"] == kwargs["third_entry"]:
            reached.append(True)
            if field == "prefix":
                result["prefix_calls"][0]["result"] ^= 1
            elif field == "caller":
                result["class_caller"]["argument_record"][0] = 1
            elif field in ("class_return", "full_return"):
                result[field]["registers"]["eax"] ^= 1
            elif field == "cookie":
                result["native_cookie"]["stored_word"] ^= 1
            else:
                result["normal_requests"][-1]["arguments"][0] ^= 1
        return result

    monkeypatch.setattr(model.tree_model.full_return_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackThirdError, match="third"):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize("field", ("tree_count", "links", "vector"))
def test_corrupted_retained_second_metadata_rejected(monkeypatch, field):
    kwargs, original = inputs(), model.extend_model.apply

    def corrupted(**arguments):
        result = original(**arguments)
        if field == "tree_count":
            result["second"]["tree_count"] += 1
        elif field == "links":
            result["second"]["sentinel_link_ids"]["leftmost"] = None
        else:
            result["second"]["vector"]["records"][0][0] = 1
        return result

    monkeypatch.setattr(model.extend_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackThirdError, match="retained second packet"):
        model.apply(**kwargs)


def test_all_input_and_output_trees_records_requests_and_abis_detached():
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    untouched = copy.deepcopy(result)
    result["third"]["source_state"]["payloads"][0] ^= 1
    result["third"]["callback_operation"]["destination"]["payloads"][0] ^= 1
    result["third"]["class_transfer"]["destination"]["tree"]["nodes"][0]["key"] ^= 1
    result["third"]["vector"]["records"][0][1] ^= 1
    result["third"]["vector_free_request"]["pointer"] ^= 1
    result["third"]["normal_requests"][0]["after"].clear()
    result["third"]["full_return"]["registers"]["eax"] = 1
    assert kwargs == before
    assert (
        result["first"] == untouched["first"]
        and result["second"] == untouched["second"]
    )
    assert (
        result["third"]["class_transfer"]["destination"]["payloads"]
        == untouched["third"]["class_transfer"]["destination"]["payloads"]
    )
    assert (
        result["third"]["callback_operation"]["vector"]["records"]
        == untouched["third"]["callback_operation"]["vector"]["records"]
    )
    assert model.apply(**kwargs) == untouched
    kwargs["first_arguments"]["source_state"]["payloads"][0] ^= 1
    kwargs["second_source_state"]["payloads"][0] ^= 1
    kwargs["third_source_state"]["payloads"][0] ^= 1
    kwargs["third_registers"]["eax"] ^= 1
    assert untouched == model.apply(**before)


def test_third_error_is_an_extend_and_full_return_error():
    assert issubclass(
        model.FactoryCallbackThirdError, model.extend_model.FactoryCallbackExtendError
    )
    assert issubclass(
        model.FactoryCallbackThirdError,
        model.tree_model.full_return_model.FactoryCallbackReturnError,
    )
