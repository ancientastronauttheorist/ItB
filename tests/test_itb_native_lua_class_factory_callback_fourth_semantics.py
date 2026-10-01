"""Independent fourth-call payload, four-record growth and normal ABI laws."""

import copy

import pytest

from src.observatory import native_lua_class_factory_callback_fourth_semantics as model
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
    first_result = model.tree_model.apply(**first)
    second_entry = 0x31001037
    second = source([6, 0, 3] if second_keys is None else second_keys, 0xFFFFFFFF)
    second_registers = dict(first_result["full_return"]["registers"], esp=second_entry)
    second_result = model.third_model.extend_model.apply(
        first_arguments=first,
        second_source_state=second,
        new_vector_pointer=0x0700301F,
        second_entry=second_entry,
        second_registers=second_registers,
    )
    third_entry = 0x3200103F
    third = copy.deepcopy(second)
    third["payloads"] = [value ^ 0xFFFFFFFF for value in third["payloads"]]
    third_registers = dict(
        second_result["second"]["full_return"]["registers"], esp=third_entry
    )
    third_result = model.third_model.apply(
        first_arguments=first,
        second_source_state=second,
        second_vector_pointer=0x0700301F,
        second_entry=second_entry,
        second_registers=second_registers,
        third_source_state=third,
        new_vector_pointer=0x08004007,
        third_entry=third_entry,
        third_registers=third_registers,
    )
    fourth_entry = changes.get("fourth_entry", 0x33001017)
    fourth = copy.deepcopy(third)
    fourth["payloads"] = [value ^ 0xFFFFFFFF for value in fourth["payloads"]]
    result = dict(
        first_arguments=first,
        second_source_state=second,
        second_vector_pointer=0x0700301F,
        second_entry=second_entry,
        second_registers=second_registers,
        third_source_state=third,
        third_vector_pointer=0x08004007,
        third_entry=third_entry,
        third_registers=third_registers,
        fourth_source_state=fourth,
        new_vector_pointer=0x0900501F,
        fourth_entry=fourth_entry,
        fourth_registers=dict(
            third_result["third"]["full_return"]["registers"], esp=fourth_entry
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

    def visit(identity, parent, low, high):
        if identity is None:
            return 1
        assert (
            type(identity) is int
            and 0 <= identity < len(nodes)
            and identity not in visited
        )
        visited.add(identity)
        node = nodes[identity]
        assert node["parent"] == parent and low < node["key"] < high
        assert type(node["color"]) is int and node["color"] in (0, 1)
        if node["color"] == 0:
            assert all(
                child is None or nodes[child]["color"] == 1
                for child in (node["left"], node["right"])
            )
        left = visit(node["left"], identity, low, node["key"])
        inorder.append(node["key"])
        right = visit(node["right"], identity, node["key"], high)
        assert left == right
        return left + node["color"]

    if tree["root"] is not None:
        assert nodes[tree["root"]]["color"] == 1
    visit(tree["root"], None, -1, 2**32)
    assert visited == set(range(len(nodes)))
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
def test_fourth_retains_union_tree_ids_count_links_and_omitted_payloads(
    first_keys, second_keys, profile
):
    kwargs = inputs(arguments(first_keys), second_keys)
    if profile == "unchanged":
        kwargs["fourth_source_state"] = kwargs["third_source_state"]
    elif profile == "distinct":
        kwargs["fourth_source_state"]["payloads"] = [
            (0xAD017312 + identity * 0x112233) & 0xFFFFFFFF
            for identity in range(len(second_keys))
        ]
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    assert kwargs == before and set(result) == {"first", "second", "third", "fourth"}
    third, fourth = result["third"], result["fourth"]
    prior, final = (
        third["callback_operation"]["destination"],
        fourth["callback_operation"]["destination"],
    )
    assert final["tree"] == prior["tree"]
    assert check_redblack(final["tree"]) == sorted(set(first_keys) | set(second_keys))
    assert values(prior) == {
        **values(result["first"]["callback_operation"]["destination"]),
        **values(kwargs["third_source_state"]),
    }
    assert values(final) == {**values(prior), **values(kwargs["fourth_source_state"])}
    destination_keys = [node["key"] for node in prior["tree"]["nodes"]]
    source_keys = [
        node["key"] for node in kwargs["fourth_source_state"]["tree"]["nodes"]
    ]
    copies = [
        dict(
            source=source_keys.index(key),
            destination=destination_keys.index(key),
            key=key,
            inserted=False,
            payload=values(kwargs["fourth_source_state"])[key],
        )
        for key in sorted(second_keys)
    ]
    assert fourth["callback_operation"] == dict(
        destination=final,
        copies=copies,
        vector=dict(
            records=[[0, kwargs["first_arguments"]["source_pointer"]]] * 4, capacity=4
        ),
        return_word=kwargs["first_arguments"]["source_pointer"],
        argument_kind="external",
        grew=True,
    )
    assert fourth["class_transfer"] == dict(destination=final, copies=copies)
    assert fourth["source_state"] == kwargs["fourth_source_state"]
    for identity, key in enumerate(destination_keys):
        assert final["tree"]["nodes"][identity]["key"] == key
        if key not in second_keys:
            assert final["payloads"][identity] == prior["payloads"][identity]
    assert (
        fourth["tree_count"]
        == third["tree_count"]
        == len(set(first_keys) | set(second_keys))
    )
    assert fourth["sentinel_link_ids"] == third["sentinel_link_ids"]
    assert (
        fourth["sentinel_preserved_offsets"] == list(range(24))
        and fourth["tree_heap_requests"] == []
    )


def test_fourteen_node_union_remains_stable_with_all_seven_fourth_payload_updates():
    kwargs = inputs(arguments(list(range(7))), list(range(7, 14)))
    result = model.apply(**kwargs)
    fourth = result["fourth"]
    assert fourth["tree_count"] == 14 and len(fourth["class_transfer"]["copies"]) == 7
    assert all(row["inserted"] is False for row in fourth["class_transfer"]["copies"])
    assert (
        fourth["callback_operation"]["destination"]["payloads"][:7]
        == result["first"]["callback_operation"]["destination"]["payloads"]
    )


@pytest.mark.parametrize("alignment", (0, 7, 31))
@pytest.mark.parametrize("source_pointer", (1, 0x80000000, 0x1A000100, 0xFFFFFFB8))
def test_three_actual_records_copy24_and_fourth_append_grows_capacity4_allocation32(
    alignment, source_pointer
):
    kwargs = inputs(
        arguments(source_pointer=source_pointer),
        new_vector_pointer=0x09005000 + alignment,
    )
    result = model.apply(**kwargs)
    fourth, new, old = (
        result["fourth"],
        kwargs["new_vector_pointer"],
        kwargs["third_vector_pointer"],
    )
    records = [[0, source_pointer]] * 4
    assert (
        result["third"]["vector"]["records"] == records[:3]
        and result["third"]["vector"]["capacity"] == 3
    )
    assert fourth["vector"] == dict(
        records=records, capacity=4, begin=new, end=new + 32, capacity_pointer=new + 32
    )
    pair = b"\0" * 4 + source_pointer.to_bytes(4, "little")
    encoded = b"".join(
        word.to_bytes(4, "little")
        for record in fourth["vector"]["records"]
        for word in record
    )
    assert encoded[:24] == pair * 3 and encoded[24:] == pair and len(encoded) == 32
    assert fourth["vector_heap_request"] == dict(
        continuation=0x00789463, handle=0x12345678, flags=0, bytes=32
    )
    assert fourth["old_vector_pointer"] == old
    assert fourth["vector_free_request"] == dict(
        continuation=0x00789172, handle=0x12345678, flags=0, pointer=old
    )


@pytest.mark.parametrize("entry", (56, 57, 0x33001017, 0xFFFFFFF8))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_fourth_actual_incoming_third_gprs_class_free_response_cookie_and_full_return(
    entry, cookie
):
    kwargs = inputs(arguments(cookie=cookie), fourth_entry=entry)
    result = model.apply(**kwargs)
    fourth, first, incoming = (
        result["fourth"],
        kwargs["first_arguments"],
        kwargs["fourth_registers"],
    )
    assert incoming == dict(result["third"]["full_return"]["registers"], esp=entry)
    assert fourth["full_return"] == dict(
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
    assert fourth["class_return"] == dict(
        registers=dict(
            eax=first["source_pointer"],
            ebx=first["state"],
            ecx=cookie,
            edx=0xB0000001,
            esi=first["userdata"],
            edi=first["source_pointer"],
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    assert fourth["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert fourth["class_caller"]["argument_record"] == [0, first["source_pointer"]]
    assert fourth["class_caller"]["argaddress"] == entry - 20


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
def test_fourth_reuses_reference_recipes_requests_and_final_five_identity_bound_lua_values(
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
    fourth = result["fourth"]
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in recipes
    ]
    for stage in (result["first"], result["second"], result["third"]):
        for field in (
            "prefix_calls",
            "registry_table_calls",
            "normal_requests",
            "normal_initial_lua_stack",
            "normal_final_lua_stack",
            "registry_requests",
            "table_transfers",
            "requested_assignments",
        ):
            assert fourth[field] == stage[field]
    assert len(fourth["prefix_calls"]) == 12 and len(
        fourth["normal_requests"]
    ) == 16 + sum(counts)
    assert fourth["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert fourth["requested_assignments"] == [
        [identity for identity, kind in enumerate(recipe) if kind == "other"]
        for recipe in recipes
    ]
    assert fourth["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert fourth["source_word"] == fourth["destination_word"] == word
    assert fourth["normal_lua_stack_delta"] == 4 and fourth["return_count"] == 0
    assert all(
        left["after"] == right["before"]
        for left, right in zip(fourth["normal_requests"], fourth["normal_requests"][1:])
    )


@pytest.mark.parametrize("state", (1, 0x80000000, 0xFFFFFFFF))
@pytest.mark.parametrize(
    "upvalue_kind,argument_kind",
    [
        (u, a)
        for u in ("zero", "empty_string", "table")
        for a in ("zero", "empty_string", "table")
    ],
)
def test_fourth_prefix_marker_order_signed_arguments_and_pair_identity(
    state, upvalue_kind, argument_kind
):
    kwargs = inputs(
        arguments(
            state=state,
            upvalue_marker_kind=upvalue_kind,
            argument_marker_kind=argument_kind,
        )
    )
    fourth = model.apply(**kwargs)["fourth"]
    prefix = fourth["prefix_calls"]
    signed = state if state < 0x80000000 else state - 2**32
    assert [row["api"] for row in prefix] == ["lua_touserdata"] + [
        "lua_getmetatable",
        "lua_pushstring",
        "lua_gettable",
        "lua_toboolean",
        "lua_settop",
    ] * 2 + ["lua_touserdata"]
    assert prefix[0]["arguments"] == [signed, -10003] and prefix[-1]["arguments"] == [
        signed,
        1,
    ]
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


def test_fourth_field_updates_preserve_thirteen_userdata_words_and_entire_sentinel():
    kwargs = inputs()
    fourth = model.apply(**kwargs)["fourth"]
    pointer, word = (
        kwargs["new_vector_pointer"],
        kwargs["first_arguments"]["source_word"],
    )
    assert fourth["normal_field_updates"] == {
        0: word,
        4: pointer,
        8: pointer + 32,
        12: pointer + 32,
        56: 5,
    }
    assert fourth["field_updates"] == {
        4: pointer,
        8: pointer + 32,
        12: pointer + 32,
        56: 5,
    }
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert (
        fourth["normal_preserved_userdata_offsets"] == preserved
        and len(preserved) == 13
    )
    assert fourth["preserved_userdata_offsets"] == [0] + preserved
    before = bytes((identity * 71 + 13) % 256 for identity in range(72))
    after = bytearray(before)
    for offset, value in fourth["normal_field_updates"].items():
        after[offset : offset + 4] = value.to_bytes(4, "little")
    assert all(
        after[offset : offset + 4] == before[offset : offset + 4]
        for offset in preserved
    )
    assert fourth["sentinel_preserved_offsets"] == list(range(24))


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_every_fourth_incoming_gpr_must_equal_actual_third_return(register):
    kwargs = inputs()
    kwargs["fourth_registers"][register] ^= 1
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackFourthError, match="actual third return"):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field", ("new_vector_pointer", "fourth_entry", "fourth_register_word")
)
@pytest.mark.parametrize("value", (False, True, -1, 2**32, 1.0, "1", None))
def test_strict_fourth_words(field, value):
    kwargs = inputs()
    if field == "fourth_register_word":
        kwargs["fourth_registers"]["eax"] = value
    else:
        kwargs[field] = value
    with pytest.raises(model.FactoryCallbackFourthError):
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
        "third_eight",
        "first_schema",
        "second_register",
        "third_register",
        "third_vector",
    ),
)
def test_first_through_fourth_schema_topology_payload_and_extent_validation(kind):
    kwargs = inputs()
    if kind == "register_missing":
        kwargs["fourth_registers"].pop("eax")
    elif kind == "register_extra":
        kwargs["fourth_registers"]["eip"] = 0
    elif kind == "register_tuple":
        kwargs["fourth_registers"] = tuple(kwargs["fourth_registers"].items())
    elif kind == "source_schema":
        kwargs["fourth_source_state"]["extra"] = 0
    elif kind == "payload_bool":
        kwargs["fourth_source_state"]["payloads"][0] = True
    elif kind == "payload_wide":
        kwargs["fourth_source_state"]["payloads"][0] = 2**32
    elif kind == "payload_count":
        kwargs["fourth_source_state"]["payloads"].pop()
    elif kind == "source_key":
        kwargs["fourth_source_state"]["tree"]["nodes"][0]["key"] = 2**32
    elif kind == "source_topology":
        kwargs["fourth_source_state"] = source([0, 3, 6], 0xFFFFFFFF)
    elif kind == "source_color":
        kwargs["fourth_source_state"]["tree"]["nodes"][0]["color"] = True
    elif kind in ("source_eight", "first_eight", "second_eight", "third_eight"):
        state = source(list(range(8)))
        if kind == "first_eight":
            kwargs["first_arguments"]["source_state"] = state
        else:
            kwargs[
                {
                    "source_eight": "fourth_source_state",
                    "second_eight": "second_source_state",
                    "third_eight": "third_source_state",
                }[kind]
            ] = state
    elif kind == "first_schema":
        kwargs["first_arguments"]["extra"] = 0
    elif kind in ("second_register", "third_register"):
        kwargs["second_registers" if kind == "second_register" else "third_registers"][
            "eax"
        ] ^= 1
    elif kind == "third_vector":
        kwargs["third_vector_pointer"] = kwargs["new_vector_pointer"]
    elif kind.startswith("entry_"):
        kwargs["fourth_entry"] = 55 if kind == "entry_below_cookie" else 0xFFFFFFF9
        kwargs["fourth_registers"]["esp"] = kwargs["fourth_entry"]
    else:
        kwargs["new_vector_pointer"] = 0 if kind == "new_zero" else 0xFFFFFFE0
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackFourthError):
        model.apply(**kwargs)
    assert kwargs == before


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
def test_inherited_words_references_closure_source_extent_and_iterator_contracts(field):
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
    with pytest.raises(model.FactoryCallbackFourthError):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "region", ("old_vector", "userdata", "sentinel", "source", "frame")
)
@pytest.mark.parametrize("edge", ("first", "last", "new_tail"))
def test_old24_new32_source_userdata_sentinel_and_current_frame_are_disjoint(
    region, edge
):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    start, size = {
        "old_vector": (kwargs["third_vector_pointer"], 24),
        "userdata": (first["userdata"], 72),
        "sentinel": (first["record_pointer"], 24),
        "source": (first["source_pointer"], 72),
        "frame": (kwargs["fourth_entry"] - 48, 56),
    }[region]
    kwargs["new_vector_pointer"] = (
        start if edge == "first" else start + size - 1 if edge == "last" else start - 31
    )
    with pytest.raises(model.FactoryCallbackFourthError, match="overlap"):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "relation",
    (
        "old_before",
        "old_after",
        "uint32_end",
        "first_freed_domain",
        "second_freed_domain",
    ),
)
def test_adjacent_extents_and_previously_freed_address_reuse_make_no_ownership_claim(
    relation,
):
    kwargs = inputs()
    kwargs["new_vector_pointer"] = {
        "old_before": kwargs["third_vector_pointer"] - 32,
        "old_after": kwargs["third_vector_pointer"] + 24,
        "uint32_end": 0xFFFFFFDF,
        "first_freed_domain": kwargs["first_arguments"]["vector_pointer"],
        "second_freed_domain": kwargs["second_vector_pointer"],
    }[relation]
    fourth = model.apply(**kwargs)["fourth"]
    assert fourth["vector"]["end"] == kwargs["new_vector_pointer"] + 32


@pytest.mark.parametrize(
    "field",
    (
        "destination",
        "copies",
        "vector",
        "old_record",
        "return_word",
        "argument_kind",
        "grew",
    ),
)
def test_corrupted_actual_fourth_class_operation_independently_rejected(
    monkeypatch, field
):
    kwargs, original, reached = inputs(), model.callback.apply, []

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original(source_state, destination_state, vector, **arguments)
        if len(vector["records"]) == 3:
            reached.append(True)
            operation = result["class_operation"]
            if field == "destination":
                operation["destination"]["payloads"][1] ^= 1
            elif field == "copies":
                operation["copies"][0]["destination"] ^= 1
            elif field == "vector":
                operation["vector"]["capacity"] = 5
            elif field == "old_record":
                operation["vector"]["records"][1][0] = 1
            elif field == "return_word":
                operation["return_word"] ^= 1
            elif field == "argument_kind":
                operation["argument_kind"] = "inline"
            else:
                operation["grew"] = False
        return result

    monkeypatch.setattr(model.callback, "apply", corrupted)
    with pytest.raises(
        model.FactoryCallbackFourthError,
        match="fourth existing-key class operation packet",
    ):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize("field", ("registry", "tables", "assignments", "stack"))
def test_coordinated_empty_baseline_and_actual_fourth_suffix_rejected_by_contract(
    monkeypatch, field
):
    kwargs = inputs()
    original_callback, original_full = (
        model.callback.apply,
        model.tree_model.full_return_model.apply,
    )
    baseline, reached = [], []

    def full(**arguments):
        baseline.append(arguments["callback_entry"] == kwargs["fourth_entry"])
        try:
            return original_full(**arguments)
        finally:
            baseline.pop()

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original_callback(source_state, destination_state, vector, **arguments)
        if (baseline and baseline[-1]) or len(vector["records"]) == 3:
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
    with pytest.raises(model.FactoryCallbackFourthError, match="table contract"):
        model.apply(**kwargs)
    assert reached == [0, 3]


@pytest.mark.parametrize(
    "field", ("prefix", "caller", "class_return", "full_return", "cookie", "requests")
)
def test_corrupted_fourth_baseline_prefix_caller_return_or_cookie_rejected(
    monkeypatch, field
):
    kwargs, original, reached = inputs(), model.tree_model.full_return_model.apply, []

    def corrupted(**arguments):
        result = original(**arguments)
        if arguments["callback_entry"] == kwargs["fourth_entry"]:
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
    with pytest.raises(model.FactoryCallbackFourthError, match="fourth"):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize("field", ("tree_count", "links", "vector", "capacity"))
def test_corrupted_retained_third_metadata_rejected_independently(monkeypatch, field):
    kwargs, original = inputs(), model.third_model.apply

    def corrupted(**arguments):
        result = original(**arguments)
        if field == "tree_count":
            result["third"]["tree_count"] += 1
        elif field == "links":
            result["third"]["sentinel_link_ids"]["leftmost"] = None
        elif field == "vector":
            result["third"]["vector"]["records"][0][0] = 1
        else:
            result["third"]["vector"]["capacity"] = 4
        return result

    monkeypatch.setattr(model.third_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackFourthError, match="retained third packet"):
        model.apply(**kwargs)


def test_all_four_stages_input_output_records_trees_requests_and_abis_are_detached():
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    untouched = copy.deepcopy(result)
    result["fourth"]["source_state"]["payloads"][0] ^= 1
    result["fourth"]["callback_operation"]["destination"]["payloads"][0] ^= 1
    result["fourth"]["class_transfer"]["destination"]["tree"]["nodes"][0]["key"] ^= 1
    result["fourth"]["vector"]["records"][0][1] ^= 1
    result["fourth"]["vector_free_request"]["pointer"] ^= 1
    result["fourth"]["normal_requests"][0]["after"].clear()
    result["fourth"]["full_return"]["registers"]["eax"] = 1
    assert kwargs == before
    assert all(
        result[stage] == untouched[stage] for stage in ("first", "second", "third")
    )
    assert (
        result["fourth"]["class_transfer"]["destination"]["payloads"]
        == untouched["fourth"]["class_transfer"]["destination"]["payloads"]
    )
    assert (
        result["fourth"]["callback_operation"]["vector"]["records"]
        == untouched["fourth"]["callback_operation"]["vector"]["records"]
    )
    assert (
        result["fourth"]["vector"]["records"][1:]
        == untouched["fourth"]["vector"]["records"][1:]
    )
    assert model.apply(**kwargs) == untouched
    kwargs["first_arguments"]["source_state"]["payloads"][0] ^= 1
    kwargs["second_source_state"]["payloads"][0] ^= 1
    kwargs["third_source_state"]["payloads"][0] ^= 1
    kwargs["fourth_source_state"]["payloads"][0] ^= 1
    kwargs["fourth_registers"]["eax"] ^= 1
    assert untouched == model.apply(**before)


def test_fourth_error_is_a_third_and_full_return_error():
    assert issubclass(
        model.FactoryCallbackFourthError, model.third_model.FactoryCallbackThirdError
    )
    assert issubclass(
        model.FactoryCallbackFourthError,
        model.tree_model.full_return_model.FactoryCallbackReturnError,
    )
