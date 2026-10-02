"""Independent sixth spare logical equations; no native/SIMD execution."""

import copy
import inspect

import pytest

from src.observatory import native_lua_class_factory_callback_sixth_semantics as model
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


SECOND_KEYS = [0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF]


def fifth_inputs(first=None, **changes):
    first = arguments([0, 1, 16]) if first is None else first
    first_result = model.tree_model.apply(**first)
    second_entry = 0x31001037
    second = source(list(reversed(SECOND_KEYS)), 0xFFFFFFFF)
    second_registers = dict(first_result["full_return"]["registers"], esp=second_entry)
    second_result = model.fifth_model.fourth_model.third_model.extend_model.apply(
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
    third_result = model.fifth_model.fourth_model.third_model.apply(
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
    fourth_entry = 0x33001017
    fourth = copy.deepcopy(third)
    fourth["payloads"] = [value ^ 0x11111111 for value in fourth["payloads"]]
    fourth_registers = dict(
        third_result["third"]["full_return"]["registers"], esp=fourth_entry
    )
    prior_arguments = dict(
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
        fourth_registers=fourth_registers,
    )
    prior = model.fifth_model.fourth_model.apply(**prior_arguments)
    fifth_entry = changes.get("fifth_entry", 0x3400102F)
    fifth = copy.deepcopy(fourth)
    fifth["payloads"] = [value ^ 0xFFFFFFFF for value in fifth["payloads"]]
    prior_arguments["fourth_vector_pointer"] = prior_arguments.pop("new_vector_pointer")
    result = dict(
        prior_arguments,
        fifth_source_state=fifth,
        new_vector_pointer=0x0A006007,
        fifth_entry=fifth_entry,
        fifth_registers=dict(
            prior["fourth"]["full_return"]["registers"], esp=fifth_entry
        ),
    )
    result.update(changes)
    return result


def inputs(first=None, **changes):
    predecessor = fifth_inputs(first)
    if "fifth_vector_pointer" in changes:
        predecessor["new_vector_pointer"] = changes["fifth_vector_pointer"]
    prior = model.fifth_model.apply(**predecessor)
    entry = changes.get("sixth_entry", 0x3500103F)
    sixth = copy.deepcopy(predecessor["fifth_source_state"])
    sixth["payloads"] = [value ^ 0x10203040 for value in sixth["payloads"]]
    predecessor["fifth_vector_pointer"] = predecessor.pop("new_vector_pointer")
    result = dict(
        predecessor,
        sixth_source_state=sixth,
        sixth_entry=entry,
        sixth_registers=dict(prior["fifth"]["full_return"]["registers"], esp=entry),
    )
    result.update(changes)
    return result


def prior_inputs(kwargs):
    result = {
        key: copy.deepcopy(value)
        for key, value in kwargs.items()
        if key not in {"sixth_source_state", "sixth_entry", "sixth_registers"}
    }
    result["new_vector_pointer"] = result.pop("fifth_vector_pointer")
    return result


def values(state):
    return {
        node["key"]: state["payloads"][identity]
        for identity, node in enumerate(state["tree"]["nodes"])
    }


def test_sixth_api_has_exact_twenty_keyword_only_arguments():
    parameters = inspect.signature(model.apply).parameters
    assert len(parameters) == 20 and set(parameters) == set(inputs())
    assert all(
        value.kind == inspect.Parameter.KEYWORD_ONLY for value in parameters.values()
    )
    assert "new_vector_pointer" not in parameters


@pytest.mark.parametrize("first_keys", ([0, 1, 16], [1, 16, 255]))
@pytest.mark.parametrize("profile", ("unchanged", "flip", "distinct"))
def test_sixth_routes_seven_payloads_retains_all_eight_ids_and_prior_packets(
    first_keys, profile
):
    kwargs = inputs(arguments(first_keys))
    if profile == "unchanged":
        kwargs["sixth_source_state"] = kwargs["fifth_source_state"]
    elif profile == "flip":
        kwargs["sixth_source_state"]["payloads"] = [
            value ^ 0xFFFFFFFF for value in kwargs["fifth_source_state"]["payloads"]
        ]
    else:
        kwargs["sixth_source_state"]["payloads"] = [
            (0xFEDCBA98 - identity * 0x1020304) & 0xFFFFFFFF for identity in range(7)
        ]
    before = copy.deepcopy(kwargs)
    prior = model.fifth_model.apply(**prior_inputs(kwargs))
    result = model.apply(**kwargs)
    assert kwargs == before
    assert set(result) == {"first", "second", "third", "fourth", "fifth", "sixth"}
    assert {name: result[name] for name in prior} == prior
    fifth, sixth = result["fifth"], result["sixth"]
    initial = fifth["callback_operation"]["destination"]
    final = sixth["callback_operation"]["destination"]
    assert len(final["tree"]["nodes"]) == 8
    assert final["tree"] == initial["tree"]
    assert values(final) == values(initial) | values(kwargs["sixth_source_state"])
    assert (
        values(final)[16]
        == values(initial)[16]
        == values(kwargs["first_arguments"]["source_state"])[16]
    )
    source_keys = [
        node["key"] for node in kwargs["sixth_source_state"]["tree"]["nodes"]
    ]
    destination_keys = [node["key"] for node in initial["tree"]["nodes"]]
    copies = [
        dict(
            source=source_keys.index(key),
            destination=destination_keys.index(key),
            key=key,
            inserted=False,
            payload=values(kwargs["sixth_source_state"])[key],
        )
        for key in sorted(SECOND_KEYS)
    ]
    assert sixth["class_transfer"] == dict(destination=final, copies=copies)
    assert sixth["callback_operation"]["copies"] == copies
    assert sixth["source_state"] == kwargs["sixth_source_state"]
    assert sixth["tree_count"] == fifth["tree_count"] == 8
    assert sixth["sentinel_link_ids"] == fifth["sentinel_link_ids"]
    assert sixth["tree_heap_requests"] == []


@pytest.mark.parametrize("alignment", (0, 7, 31))
@pytest.mark.parametrize("source_pointer", (1, 0x80000000, 0x1A000100, 0xFFFFFFB8))
def test_exact_five_to_six_spare_append_fills_capacity_preserves_existing40(
    alignment, source_pointer
):
    kwargs = inputs(
        arguments([0, 1, 16], source_pointer=source_pointer),
        fifth_vector_pointer=0x0A006000 + alignment,
    )
    result = model.apply(**kwargs)
    fifth, sixth, pointer = (
        result["fifth"],
        result["sixth"],
        kwargs["fifth_vector_pointer"],
    )
    pair = bytes(4) + source_pointer.to_bytes(4, "little")
    before = pair * 5 + bytes((index * 59 + 23) % 256 for index in range(8))
    after = bytearray(before)
    after[40:48] = pair
    encoded = b"".join(
        value.to_bytes(4, "little")
        for record in sixth["vector"]["records"]
        for value in record
    )
    assert len(encoded) == 48 and encoded == bytes(after) == pair * 6
    assert bytes(after[:40]) == before[:40]
    assert fifth["vector"] == dict(
        records=[[0, source_pointer] for _ in range(5)],
        capacity=6,
        begin=pointer,
        end=pointer + 40,
        capacity_pointer=pointer + 48,
    )
    assert sixth["vector"] == dict(
        records=[[0, source_pointer] for _ in range(6)],
        capacity=6,
        begin=pointer,
        end=pointer + 48,
        capacity_pointer=pointer + 48,
    )
    assert sixth["callback_operation"]["vector"] == dict(
        records=[[0, source_pointer] for _ in range(6)], capacity=6
    )
    assert sixth["callback_operation"]["grew"] is False
    assert sixth["callback_operation"]["argument_kind"] == "external"
    assert sixth["vector_copy_bytes"] == 0
    assert sixth["vector_append_offset"] == 40 and sixth["vector_append_bytes"] == 8
    assert sixth["vector_preserved_capacity_offsets"] == []
    assert sixth["preserved_vector_buffers"] == [
        dict(pointer=kwargs["first_arguments"]["vector_pointer"], bytes=8),
        dict(pointer=kwargs["second_vector_pointer"], bytes=16),
        dict(pointer=kwargs["third_vector_pointer"], bytes=24),
        dict(pointer=kwargs["fourth_vector_pointer"], bytes=32),
        dict(pointer=pointer, bytes=40),
    ]
    assert set(sixth).isdisjoint(
        {
            "heap_request",
            "vector_heap_request",
            "vector_free_request",
            "old_vector_pointer",
            "xmm",
            "df",
        }
    )


@pytest.mark.parametrize("entry", (140, 141, 0x3500103F, 0xFFFFFFF8))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_sixth_normal_abi_and_source_derived_successor_edx(entry, cookie):
    kwargs = inputs(arguments([0, 1, 16], cookie=cookie), sixth_entry=entry)
    result = model.apply(**kwargs)
    sixth, first, incoming = (
        result["sixth"],
        kwargs["first_arguments"],
        kwargs["sixth_registers"],
    )
    assert incoming == dict(result["fifth"]["full_return"]["registers"], esp=entry)
    assert sixth["class_return"] == dict(
        registers=dict(
            eax=first["source_pointer"],
            ebx=first["state"],
            ecx=cookie,
            edx=entry - 60,
            esi=first["userdata"],
            edi=first["source_pointer"],
            ebp=entry - 4,
            esp=entry - 40,
        ),
        flags=0x44,
        flag_mask=0xCD5,
        endpoint=0x006EC1BD,
    )
    assert sixth["full_return"] == dict(
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
    assert sixth["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert sixth["class_caller"]["argaddress"] == entry - 20
    assert sixth["class_caller"]["argument_record"] == [0, first["source_pointer"]]


RECIPES = [
    ([], []),
    (["init"], ["finalize"]),
    (["other"], []),
    ([], ["other"]),
    (["other", "init", "finalize"], ["finalize", "other", "init"]),
    (["other"] * 3, ["other"] * 3),
]


@pytest.mark.parametrize("recipes", RECIPES)
@pytest.mark.parametrize("word", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_sixth_independent_prefix_suffix_lua_count_routing_and_return(recipes, word):
    kwargs = inputs(
        arguments(
            [0, 1, 16],
            source_word=word,
            destination_refs=[0, 0xFFFFFFFF],
            source_refs=[0xFFFFFFFF, 0],
            transfers=list(recipes),
        )
    )
    result = model.apply(**kwargs)
    sixth = result["sixth"]
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in recipes
    ]
    for name in ("first", "second", "third", "fourth", "fifth"):
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
            assert sixth[field] == result[name][field]
    assert len(sixth["prefix_calls"]) == 12
    assert len(sixth["normal_requests"]) == 16 + sum(counts)
    assert sixth["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert sixth["requested_assignments"] == [
        [index for index, kind in enumerate(recipe) if kind == "other"]
        for recipe in recipes
    ]
    assert sixth["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert sixth["normal_lua_stack_delta"] == 4 and sixth["return_count"] == 0
    assert sixth["source_word"] == sixth["destination_word"] == word
    assert all(
        left["after"] == right["before"]
        for left, right in zip(sixth["normal_requests"], sixth["normal_requests"][1:])
    )


def test_sixth_exact_write_maps_preserve_begin_capacity_count_u16_including_u13_p24():
    kwargs = inputs()
    sixth = model.apply(**kwargs)["sixth"]
    pointer = kwargs["fifth_vector_pointer"]
    assert sixth["field_updates"] == {8: pointer + 48}
    assert sixth["normal_field_updates"] == {
        0: kwargs["first_arguments"]["source_word"],
        8: pointer + 48,
    }
    assert sixth["preserved_userdata_offsets"] == [
        offset for offset in range(0, 72, 4) if offset != 8
    ]
    expected = [offset for offset in range(0, 72, 4) if offset not in (0, 8)]
    assert (
        sixth["normal_preserved_userdata_offsets"] == expected and len(expected) == 16
    )
    established = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert len(established) == 13 and set(established) <= set(expected)
    assert {4, 12, 56} <= set(expected)
    assert sixth["sentinel_preserved_offsets"] == list(range(24))
    before = bytes((index * 71 + 13) % 256 for index in range(72))
    after = bytearray(before)
    for offset, value in sixth["normal_field_updates"].items():
        after[offset : offset + 4] = value.to_bytes(4, "little")
    assert all(
        after[offset : offset + 4] == before[offset : offset + 4] for offset in expected
    )


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_each_sixth_incoming_gpr_must_equal_actual_fifth_return(register):
    kwargs = inputs()
    kwargs["sixth_registers"][register] ^= 1
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackSixthError, match="actual fifth return"):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize("kind", ("extra", "missing", "tuple", "boolean"))
def test_sixth_closed_gpr_schema(kind):
    kwargs = inputs()
    if kind == "extra":
        kwargs["sixth_registers"]["xmm0"] = 0
    elif kind == "missing":
        kwargs["sixth_registers"].pop("eax")
    elif kind == "tuple":
        kwargs["sixth_registers"] = tuple(kwargs["sixth_registers"].items())
    else:
        kwargs["sixth_registers"]["eax"] = False
    with pytest.raises(model.FactoryCallbackSixthError):
        model.apply(**kwargs)


@pytest.mark.parametrize("value", (False, True, -1, 2**32, 1.0, "1", None))
def test_sixth_entry_and_payload_words_are_strict_uint32(value):
    for field in ("entry", "payload", "register"):
        kwargs = inputs()
        if field == "entry":
            kwargs["sixth_entry"] = value
        elif field == "payload":
            kwargs["sixth_source_state"]["payloads"][0] = value
        else:
            kwargs["sixth_registers"]["eax"] = value
        before = copy.deepcopy(kwargs)
        with pytest.raises(model.FactoryCallbackSixthError):
            model.apply(**kwargs)
        assert kwargs == before


@pytest.mark.parametrize("entry", (0, 139, 0xFFFFFFF9, 0xFFFFFFFF))
def test_sixth_stack_extent_rejects_underflow_or_wrap(entry):
    kwargs = inputs(sixth_entry=entry)
    with pytest.raises(model.FactoryCallbackSixthError, match="stack extent wraps"):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "kind", ("topology", "fewer", "payload_count", "extra", "node_bool", "key_bool")
)
def test_sixth_source_domain_is_exact_seven_with_predecessor_topology(kind):
    kwargs = inputs()
    state = kwargs["sixth_source_state"]
    if kind == "topology":
        state["tree"] = balancing.from_keys(SECOND_KEYS)
    elif kind == "fewer":
        kwargs["sixth_source_state"] = source([0, 1])
    elif kind == "payload_count":
        state["payloads"].pop()
    elif kind == "extra":
        state["ownership"] = True
    elif kind == "node_bool":
        state["tree"]["nodes"][0]["color"] = False
    else:
        state["tree"]["nodes"][0]["key"] = False
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackSixthError):
        model.apply(**kwargs)
    assert kwargs == before


EXTENTS = [
    ("first", 8),
    ("second", 16),
    ("third", 24),
    ("fourth", 32),
    ("fifth", 48),
    ("userdata", 72),
    ("sentinel", 24),
    ("source", 72),
]


def with_extent(name, address, entry=0x3500103F):
    first = arguments([0, 1, 16])
    changes = {}
    if name in ("first", "userdata", "sentinel", "source"):
        first[
            {
                "first": "vector_pointer",
                "userdata": "userdata",
                "sentinel": "record_pointer",
                "source": "source_pointer",
            }[name]
        ] = address
        if name == "userdata":
            first["closure_upvalues"] = [address]
    elif name == "fifth":
        changes["fifth_vector_pointer"] = address
    else:
        # Rebuild the full predecessor after changing an earlier vector pointer.
        predecessor = fifth_inputs(first)
        predecessor[name + "_vector_pointer"] = address
        prior = model.fifth_model.apply(**predecessor)
        predecessor["fifth_vector_pointer"] = predecessor.pop("new_vector_pointer")
        return dict(
            predecessor,
            sixth_source_state=copy.deepcopy(predecessor["fifth_source_state"]),
            sixth_entry=entry,
            sixth_registers=dict(prior["fifth"]["full_return"]["registers"], esp=entry),
        )
    return inputs(first, sixth_entry=entry, **changes)


@pytest.mark.parametrize("name,size", EXTENTS)
@pytest.mark.parametrize("side", ("below", "above"))
def test_every_data_extent_accepts_stack_adjacency_and_rejects_one_byte_overlap(
    name, size, side
):
    entry = 0x3500103F
    address = entry - 140 - size if side == "below" else entry + 8
    kwargs = with_extent(name, address, entry)
    before = copy.deepcopy(kwargs)
    assert model.apply(**kwargs)["sixth"]["vector"]["capacity"] == 6
    assert kwargs == before
    overlap = address + 1 if side == "below" else address - 1
    kwargs = with_extent(name, overlap, entry)
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackSixthError, match="overlap"):
        model.apply(**kwargs)
    assert kwargs == before


def test_sixth_spare_append_cannot_hide_its_last_capacity_byte_in_stack():
    entry = 0x3500103F
    pointer = entry - 140 - 48
    assert (
        model.apply(**inputs(fifth_vector_pointer=pointer, sixth_entry=entry))["sixth"][
            "vector_append_offset"
        ]
        == 40
    )
    with pytest.raises(model.FactoryCallbackSixthError, match="spare stack"):
        model.apply(**inputs(fifth_vector_pointer=pointer + 1, sixth_entry=entry))


def test_all_packets_and_nested_views_are_detached():
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    for name, packet in result.items():
        packet["vector"]["records"][0][0] = 0xABCDEF01
        packet["full_return"]["registers"]["eax"] = 1
        packet["table_transfers"][0]["calls"].clear()
        if "source_state" in packet:
            packet["source_state"]["payloads"][0] ^= 1
        if "callback_operation" in packet:
            packet["callback_operation"]["destination"]["payloads"][0] ^= 1
    assert kwargs == before
    fresh = model.apply(**kwargs)
    assert all(packet["vector"]["records"][0][0] == 0 for packet in fresh.values())
    sixth = fresh["sixth"]
    sixth["vector"]["records"][0][0] ^= 1
    assert sixth["callback_operation"]["vector"]["records"][0][0] == 0
    sixth["class_transfer"]["destination"]["payloads"][0] ^= 1
    assert (
        sixth["class_transfer"]["destination"]
        != sixth["callback_operation"]["destination"]
    )
    assert (
        fresh["fifth"]["callback_operation"]["destination"]
        == model.fifth_model.apply(**prior_inputs(kwargs))["fifth"][
            "callback_operation"
        ]["destination"]
    )


def callback_inputs(size=5, capacity=6):
    kwargs = inputs()
    result = model.fifth_model.apply(**prior_inputs(kwargs))
    first = kwargs["first_arguments"]
    return (
        copy.deepcopy(kwargs["sixth_source_state"]),
        copy.deepcopy(result["fifth"]["callback_operation"]["destination"]),
        dict(
            records=[[0, first["source_pointer"]] for _ in range(size)],
            capacity=capacity,
        ),
        dict(
            source_pointer=first["source_pointer"],
            source_word=first["source_word"],
            destination_word=first["source_word"],
            destination_refs=copy.deepcopy(first["destination_refs"]),
            source_refs=copy.deepcopy(first["source_refs"]),
            transfers=copy.deepcopy(first["transfers"]),
        ),
    )


@pytest.mark.parametrize("growth", (False, True))
def test_sixth_opt_in_is_exact_and_operation_spare_domain_needs_no_new_flag(growth):
    source_state, destination, vector, kwargs = callback_inputs()
    before = copy.deepcopy((source_state, destination, vector, kwargs))
    result = model.callback.apply(
        source_state,
        destination,
        vector,
        **kwargs,
        allow_growth=growth,
        allow_sixth_spare=True
    )
    assert result["class_operation"]["vector"] == dict(
        records=vector["records"] + [[0, kwargs["source_pointer"]]], capacity=6
    )
    assert result["class_operation"]["grew"] is False
    assert (source_state, destination, vector, kwargs) == before
    assert model.callback.operation.next_capacity(5, 6) == 6
    assert (
        "allow_sixth_spare"
        not in inspect.signature(model.callback.operation.apply).parameters
    )
    assert (
        "allow_sixth_spare"
        not in inspect.signature(model.callback.operation.next_capacity).parameters
    )


@pytest.mark.parametrize(
    "size,capacity", ((4, 4), (4, 6), (5, 5), (5, 7), (6, 6), (6, 7), (0, 6))
)
def test_sixth_flag_cannot_select_any_other_vector_domain(size, capacity):
    source_state, destination, vector, kwargs = callback_inputs(size, capacity)
    with pytest.raises(
        model.callback.CallbackError, match="exactly five records and capacity six"
    ):
        model.callback.apply(
            source_state, destination, vector, **kwargs, allow_sixth_spare=True
        )


@pytest.mark.parametrize("value", (None, 0, 1, [], "true"))
def test_sixth_opt_in_requires_exact_bool(value):
    source_state, destination, vector, kwargs = callback_inputs()
    with pytest.raises(
        model.callback.CallbackError, match="allow_sixth_spare must be bool"
    ):
        model.callback.apply(
            source_state, destination, vector, **kwargs, allow_sixth_spare=value
        )


@pytest.mark.parametrize("growth", (False, True))
def test_sixth_and_fifth_opt_ins_cannot_coexist(growth):
    source_state, destination, vector, kwargs = callback_inputs()
    with pytest.raises(model.callback.CallbackError, match="cannot coexist"):
        model.callback.apply(
            source_state,
            destination,
            vector,
            **kwargs,
            allow_growth=growth,
            allow_fifth_growth=True,
            allow_sixth_spare=True
        )


@pytest.mark.parametrize(
    "flag",
    ({}, {"allow_growth": True}, {"allow_growth": True, "allow_fifth_growth": True}),
)
def test_old_callback_defaults_and_old_opt_ins_still_reject_size5cap6(flag):
    source_state, destination, vector, kwargs = callback_inputs()
    with pytest.raises(model.callback.CallbackError):
        model.callback.apply(source_state, destination, vector, **kwargs, **flag)


@pytest.mark.parametrize(
    "growth,size,capacity", ((False, 0, 1), (False, 3, 5), (True, 0, 0), (True, 3, 3))
)
def test_explicit_false_sixth_flag_preserves_old_callback_output_schema(
    growth, size, capacity
):
    source_state, destination, vector, kwargs = callback_inputs(size, capacity)
    default = model.callback.apply(
        source_state, destination, vector, **kwargs, allow_growth=growth
    )
    explicit = model.callback.apply(
        source_state,
        destination,
        vector,
        **kwargs,
        allow_growth=growth,
        allow_sixth_spare=False
    )
    assert explicit == default
    assert set(explicit) == {
        "class_operation",
        "destination_word",
        "return_count",
        "initial_lua_stack",
        "final_lua_stack",
        "lua_stack_delta",
        "registry_requests",
        "table_transfers",
        "requested_assignments",
        "calls",
    }


@pytest.mark.parametrize(
    "kind",
    (
        "extra",
        "missing",
        "tuple",
        "capacity_bool",
        "record_tuple",
        "record_bool",
        "records_tuple",
    ),
)
def test_sixth_shared_callback_vector_schema_remains_strict(kind):
    source_state, destination, vector, kwargs = callback_inputs()
    if kind == "extra":
        vector["ownership"] = True
    elif kind == "missing":
        vector.pop("capacity")
    elif kind == "tuple":
        vector = tuple(vector.items())
    elif kind == "capacity_bool":
        vector["capacity"] = True
    elif kind == "record_tuple":
        vector["records"][0] = tuple(vector["records"][0])
    elif kind == "record_bool":
        vector["records"][0][0] = False
    else:
        vector["records"] = tuple(vector["records"])
    with pytest.raises(model.callback.CallbackError):
        model.callback.apply(
            source_state, destination, vector, **kwargs, allow_sixth_spare=True
        )


@pytest.mark.parametrize(
    "kind",
    (
        "payload",
        "payload_bool",
        "destination_id",
        "grew",
        "grew_int",
        "record",
        "capacity",
        "lua",
        "recipe",
    ),
)
def test_independent_sixth_equations_reject_corrupt_child_packets(monkeypatch, kind):
    kwargs = inputs()
    original = model.callback.apply

    def corrupted(*args, **keywords):
        packet = original(*args, **keywords)
        if not keywords.get("allow_sixth_spare"):
            return packet
        if kind in ("payload", "payload_bool"):
            packet["class_operation"]["copies"][0]["payload"] = (
                False if kind == "payload_bool" else 0x123
            )
        elif kind == "destination_id":
            packet["class_operation"]["copies"][0]["destination"] ^= 1
        elif kind == "grew":
            packet["class_operation"]["grew"] = True
        elif kind == "grew_int":
            packet["class_operation"]["grew"] = 0
        elif kind == "record":
            packet["class_operation"]["vector"]["records"][-1][0] = 1
        elif kind == "capacity":
            packet["class_operation"]["vector"]["capacity"] = 7
        elif kind == "lua":
            packet["final_lua_stack"].append(("hidden", 1))
        else:
            packet["requested_assignments"][0].append(9)
        return packet

    monkeypatch.setattr(model.callback, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackSixthError):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "kind", ("class", "class_bool", "full", "cookie", "prefix", "caller", "requests")
)
def test_independent_sixth_checks_reject_corrupted_baseline_equations(
    monkeypatch, kind
):
    kwargs = inputs()
    original = model.tree_model.full_return_model.apply

    def corrupted(**keywords):
        packet = original(**keywords)
        if keywords["callback_entry"] != kwargs["sixth_entry"]:
            return packet
        if kind == "class":
            packet["class_return"]["registers"]["eax"] ^= 1
        elif kind == "class_bool":
            packet["class_return"]["registers"]["edx"] = False
        elif kind == "full":
            packet["full_return"]["registers"]["edi"] ^= 1
        elif kind == "cookie":
            packet["native_cookie"]["stored_word"] ^= 1
        elif kind == "prefix":
            packet["prefix_calls"][0]["arguments"][0] ^= 1
        elif kind == "caller":
            packet["class_caller"]["argaddress"] ^= 1
        else:
            packet["normal_requests"].pop()
        return packet

    monkeypatch.setattr(model.tree_model.full_return_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackSixthError):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "kind", ("records", "capacity", "begin", "end", "capacity_pointer")
)
def test_independent_sixth_checks_exact_retained_fifth_geometry(monkeypatch, kind):
    kwargs = inputs()
    original = model.fifth_model.apply

    def corrupted(**keywords):
        packet = original(**keywords)
        if kind == "records":
            packet["fifth"]["vector"]["records"][0][0] = 1
        else:
            packet["fifth"]["vector"][kind] ^= 1
        return packet

    monkeypatch.setattr(model.fifth_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackSixthError, match="retained fifth packet"):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "kind",
    (
        "record_bool",
        "prior_gpr_bool",
        "sentinel_bool",
        "source_view",
        "source_key_bool",
        "transfer_destination",
        "transfer_copy",
        "transfer_inserted_int",
        "operation_destination",
        "operation_copy",
        "operation_record_bool",
        "operation_capacity",
        "operation_grew_int",
        "operation_return",
        "operation_argument",
        "coordinated_omitted_payload",
        "coordinated_source_payload",
        "missing_source_view",
    ),
)
def test_retained_fifth_views_reject_typed_and_coordinated_corruption(
    monkeypatch, kind
):
    kwargs = inputs()
    original = model.fifth_model.apply

    def corrupted(**keywords):
        packet = original(**keywords)
        fifth = packet["fifth"]
        if kind == "record_bool":
            fifth["vector"]["records"][0][0] = False
        elif kind == "prior_gpr_bool":
            fifth["full_return"]["registers"]["eax"] = False
        elif kind == "sentinel_bool":
            link = next(
                key for key, value in fifth["sentinel_link_ids"].items() if value == 0
            )
            fifth["sentinel_link_ids"][link] = False
        elif kind == "source_view":
            fifth["source_state"]["payloads"][0] ^= 1
        elif kind == "source_key_bool":
            node = next(
                n for n in fifth["source_state"]["tree"]["nodes"] if n["key"] == 0
            )
            node["key"] = False
        elif kind == "missing_source_view":
            fifth.pop("source_state")
        elif kind in ("transfer_destination", "operation_destination"):
            name = (
                "class_transfer"
                if kind.startswith("transfer")
                else "callback_operation"
            )
            fifth[name]["destination"]["payloads"][0] ^= 1
        elif kind in ("transfer_copy", "operation_copy"):
            name = (
                "class_transfer"
                if kind.startswith("transfer")
                else "callback_operation"
            )
            fifth[name]["copies"][0]["payload"] ^= 1
        elif kind == "transfer_inserted_int":
            fifth["class_transfer"]["copies"][0]["inserted"] = 0
        elif kind == "operation_record_bool":
            fifth["callback_operation"]["vector"]["records"][0][0] = False
        elif kind == "operation_capacity":
            fifth["callback_operation"]["vector"]["capacity"] = 5
        elif kind == "operation_grew_int":
            fifth["callback_operation"]["grew"] = 1
        elif kind == "operation_return":
            fifth["callback_operation"]["return_word"] ^= 1
        elif kind == "operation_argument":
            fifth["callback_operation"]["argument_kind"] = "internal"
        elif kind == "coordinated_omitted_payload":
            for name in ("class_transfer", "callback_operation"):
                state = fifth[name]["destination"]
                identity = next(
                    i for i, n in enumerate(state["tree"]["nodes"]) if n["key"] == 16
                )
                state["payloads"][identity] ^= 1
        else:
            source_id = 0
            key = fifth["source_state"]["tree"]["nodes"][source_id]["key"]
            fifth["source_state"]["payloads"][source_id] ^= 1
            for name in ("class_transfer", "callback_operation"):
                state = fifth[name]["destination"]
                identity = next(
                    i for i, n in enumerate(state["tree"]["nodes"]) if n["key"] == key
                )
                state["payloads"][identity] ^= 1
                row = next(row for row in fifth[name]["copies"] if row["key"] == key)
                row["payload"] ^= 1
        return packet

    monkeypatch.setattr(model.fifth_model, "apply", corrupted)
    with pytest.raises(
        model.FactoryCallbackSixthError, match="retained fifth|incoming registers"
    ):
        model.apply(**kwargs)
