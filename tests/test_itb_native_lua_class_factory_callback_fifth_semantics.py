"""Independent finite fifth-call logical laws; no native/SIMD execution."""

import copy
import inspect

import pytest

from src.observatory import native_lua_class_factory_callback_fifth_semantics as model
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


def inputs(first=None, **changes):
    first = arguments([0, 1, 16]) if first is None else first
    first_result = model.tree_model.apply(**first)
    second_entry = 0x31001037
    second = source(list(reversed(SECOND_KEYS)), 0xFFFFFFFF)
    second_registers = dict(first_result["full_return"]["registers"], esp=second_entry)
    second_result = model.fourth_model.third_model.extend_model.apply(
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
    third_result = model.fourth_model.third_model.apply(
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
    prior = model.fourth_model.apply(**prior_arguments)
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


def prior_inputs(kwargs):
    result = {
        key: copy.deepcopy(value)
        for key, value in kwargs.items()
        if key
        not in {
            "fifth_source_state",
            "new_vector_pointer",
            "fifth_entry",
            "fifth_registers",
        }
    }
    result["new_vector_pointer"] = result.pop("fourth_vector_pointer")
    return result


def values(state):
    return {
        node["key"]: state["payloads"][identity]
        for identity, node in enumerate(state["tree"]["nodes"])
    }


def test_schema_has_exact_seventeen_keyword_only_arguments():
    parameters = inspect.signature(model.apply).parameters
    assert len(parameters) == 17
    assert all(
        parameter.kind == inspect.Parameter.KEYWORD_ONLY
        for parameter in parameters.values()
    )
    assert set(parameters) == set(inputs())


@pytest.mark.parametrize("first_keys", ([0, 1, 16], [1, 16, 255]))
@pytest.mark.parametrize("payload_profile", ("unchanged", "flip", "distinct"))
def test_seven_updates_preserve_eight_node_ids_topology_and_omitted_key16(
    first_keys, payload_profile
):
    kwargs = inputs(arguments(first_keys))
    if payload_profile == "unchanged":
        kwargs["fifth_source_state"] = kwargs["fourth_source_state"]
    elif payload_profile == "distinct":
        kwargs["fifth_source_state"]["payloads"] = [
            (0xF0123456 + identity * 0x1020304) & 0xFFFFFFFF for identity in range(7)
        ]
    before = copy.deepcopy(kwargs)
    prior = model.fourth_model.apply(**prior_inputs(kwargs))
    result = model.apply(**kwargs)
    assert kwargs == before
    assert set(result) == {"first", "second", "third", "fourth", "fifth"}
    assert {key: result[key] for key in prior} == prior
    fourth, fifth = result["fourth"], result["fifth"]
    initial = fourth["callback_operation"]["destination"]
    final = fifth["callback_operation"]["destination"]
    assert len(final["tree"]["nodes"]) == 8
    assert final["tree"] == initial["tree"]
    assert values(final) == {**values(initial), **values(kwargs["fifth_source_state"])}
    assert (
        values(final)[16]
        == values(initial)[16]
        == values(kwargs["first_arguments"]["source_state"])[16]
    )
    destination_keys = [node["key"] for node in initial["tree"]["nodes"]]
    source_keys = [
        node["key"] for node in kwargs["fifth_source_state"]["tree"]["nodes"]
    ]
    copies = [
        dict(
            source=source_keys.index(key),
            destination=destination_keys.index(key),
            key=key,
            inserted=False,
            payload=values(kwargs["fifth_source_state"])[key],
        )
        for key in sorted(SECOND_KEYS)
    ]
    assert fifth["class_transfer"] == dict(destination=final, copies=copies)
    assert fifth["callback_operation"]["copies"] == copies
    assert fifth["source_state"] == kwargs["fifth_source_state"]
    assert fifth["tree_count"] == fourth["tree_count"] == 8
    assert fifth["sentinel_link_ids"] == fourth["sentinel_link_ids"]
    assert fifth["tree_heap_requests"] == []


@pytest.mark.parametrize("alignment", (0, 7, 31))
@pytest.mark.parametrize("source_pointer", (1, 0x80000000, 0x1A000100, 0xFFFFFFB8))
def test_copy32_append8_allocate48_freeold32_and_spare8_logical_obligations(
    alignment, source_pointer
):
    kwargs = inputs(
        arguments([0, 1, 16], source_pointer=source_pointer),
        new_vector_pointer=0x0A006000 + alignment,
    )
    result = model.apply(**kwargs)
    fifth, new, old = (
        result["fifth"],
        kwargs["new_vector_pointer"],
        kwargs["fourth_vector_pointer"],
    )
    records = [[0, source_pointer] for _ in range(5)]
    assert result["fourth"]["vector"]["records"] == records[:4]
    assert fifth["vector"] == dict(
        records=records, capacity=6, begin=new, end=new + 40, capacity_pointer=new + 48
    )
    assert fifth["callback_operation"]["vector"] == dict(records=records, capacity=6)
    pair = bytes(4) + source_pointer.to_bytes(4, "little")
    encoded = b"".join(
        word.to_bytes(4, "little") for record in records for word in record
    )
    assert encoded[:32] == pair * 4 and encoded[32:40] == pair and len(encoded) == 40
    assert fifth["vector_heap_request"] == dict(
        continuation=0x00789463, handle=0x12345678, flags=0, bytes=48
    )
    assert fifth["vector_free_request"] == dict(
        continuation=0x00789172, handle=0x12345678, flags=0, pointer=old
    )
    assert fifth["old_vector_pointer"] == old
    assert fifth["preserved_vector_buffers"] == [
        dict(pointer=kwargs["first_arguments"]["vector_pointer"], bytes=8),
        dict(pointer=kwargs["second_vector_pointer"], bytes=16),
        dict(pointer=kwargs["third_vector_pointer"], bytes=24),
        dict(pointer=old, bytes=32),
    ]
    assert fifth["vector_copy_bytes"] == 32
    assert fifth["vector_append_offset"] == 32 and fifth["vector_append_bytes"] == 8
    assert fifth["vector_preserved_capacity_offsets"] == list(range(40, 48))
    assert all(key not in fifth for key in ("xmm", "xmm_registers", "df"))


@pytest.mark.parametrize("entry", (188, 189, 0x3400102F, 0xFFFFFFF8))
@pytest.mark.parametrize("cookie", (0, 1, 0x80000000, 0xFFFFFFFF))
def test_actual_fourth_gprs_fifth_class_return_cookie_and_caller_restore(entry, cookie):
    kwargs = inputs(arguments([0, 1, 16], cookie=cookie), fifth_entry=entry)
    result = model.apply(**kwargs)
    fifth, first, incoming = (
        result["fifth"],
        kwargs["first_arguments"],
        kwargs["fifth_registers"],
    )
    assert incoming == dict(result["fourth"]["full_return"]["registers"], esp=entry)
    assert fifth["class_return"] == dict(
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
    assert fifth["full_return"] == dict(
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
    assert fifth["native_cookie"] == dict(
        frame=entry - 52,
        protected_address=entry - 56,
        stored_word=cookie ^ (entry - 52),
    )
    assert fifth["class_caller"]["argument_record"] == [0, first["source_pointer"]]
    assert fifth["class_caller"]["argaddress"] == entry - 20


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
def test_fifth_reuses_registry_tables_recipes_and_preserves_normal_lua_requests(
    recipes, word
):
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
    fifth = result["fifth"]
    counts = [
        2 + sum({"init": 4, "finalize": 7, "other": 10}[kind] for kind in recipe)
        for recipe in recipes
    ]
    for stage in (result[name] for name in ("first", "second", "third", "fourth")):
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
            assert fifth[field] == stage[field]
    assert len(fifth["prefix_calls"]) == 12
    assert len(fifth["normal_requests"]) == 16 + sum(counts)
    assert fifth["full_return"]["registers"]["edx"] == 0xB0000300 + counts[1]
    assert fifth["requested_assignments"] == [
        [identity for identity, kind in enumerate(recipe) if kind == "other"]
        for recipe in recipes
    ]
    assert fifth["normal_final_lua_stack"] == [
        ("argument", kwargs["first_arguments"]["source_pointer"]),
        ("registry", 0),
        ("registry", 0xFFFFFFFF),
        ("registry", 0xFFFFFFFF),
        ("registry", 0),
    ]
    assert fifth["source_word"] == fifth["destination_word"] == word
    assert fifth["normal_lua_stack_delta"] == 4 and fifth["return_count"] == 0
    assert all(
        left["after"] == right["before"]
        for left, right in zip(fifth["normal_requests"], fifth["normal_requests"][1:])
    )


def test_field_updates_preserve_thirteen_userdata_words_and_entire_sentinel():
    kwargs = inputs()
    fifth = model.apply(**kwargs)["fifth"]
    pointer, word = (
        kwargs["new_vector_pointer"],
        kwargs["first_arguments"]["source_word"],
    )
    assert fifth["normal_field_updates"] == {
        0: word,
        4: pointer,
        8: pointer + 40,
        12: pointer + 48,
        56: 8,
    }
    assert fifth["field_updates"] == {
        4: pointer,
        8: pointer + 40,
        12: pointer + 48,
        56: 8,
    }
    preserved = [
        offset for offset in range(0, 72, 4) if offset not in (0, 4, 8, 12, 56)
    ]
    assert (
        fifth["normal_preserved_userdata_offsets"] == preserved and len(preserved) == 13
    )
    assert fifth["preserved_userdata_offsets"] == [0] + preserved
    before = bytes((identity * 71 + 13) % 256 for identity in range(72))
    after = bytearray(before)
    for offset, value in fifth["normal_field_updates"].items():
        after[offset : offset + 4] = value.to_bytes(4, "little")
    assert all(
        after[offset : offset + 4] == before[offset : offset + 4]
        for offset in preserved
    )
    assert fifth["sentinel_preserved_offsets"] == list(range(24))


@pytest.mark.parametrize(
    "register", ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp")
)
def test_every_fifth_gpr_must_equal_actual_fourth_return(register):
    kwargs = inputs()
    kwargs["fifth_registers"][register] ^= 1
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackFifthError, match="actual fourth return"):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field", ("new_vector_pointer", "fifth_entry", "fifth_register_word")
)
@pytest.mark.parametrize("value", (False, True, -1, 2**32, 1.0, "1", None))
def test_strict_fifth_uint32_words(field, value):
    kwargs = inputs()
    if field == "fifth_register_word":
        kwargs["fifth_registers"]["eax"] = value
    else:
        kwargs[field] = value
    with pytest.raises(model.FactoryCallbackFifthError):
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
        "source_six",
        "entry_below_growth_stack",
        "entry_wrap",
        "new_zero",
        "new_wrap",
        "fourth_register",
        "fourth_vector",
    ),
)
def test_finite_schema_topology_payload_and_extent_validation(kind):
    kwargs = inputs()
    if kind == "register_missing":
        kwargs["fifth_registers"].pop("eax")
    elif kind == "register_extra":
        kwargs["fifth_registers"]["eip"] = 0
    elif kind == "register_tuple":
        kwargs["fifth_registers"] = tuple(kwargs["fifth_registers"].items())
    elif kind == "source_schema":
        kwargs["fifth_source_state"]["extra"] = 0
    elif kind == "payload_bool":
        kwargs["fifth_source_state"]["payloads"][0] = True
    elif kind == "payload_wide":
        kwargs["fifth_source_state"]["payloads"][0] = 2**32
    elif kind == "payload_count":
        kwargs["fifth_source_state"]["payloads"].pop()
    elif kind == "source_key":
        kwargs["fifth_source_state"]["tree"]["nodes"][0]["key"] = 2**32
    elif kind == "source_topology":
        kwargs["fifth_source_state"] = source(SECOND_KEYS)
    elif kind == "source_color":
        kwargs["fifth_source_state"]["tree"]["nodes"][0]["color"] = True
    elif kind in ("source_eight", "source_six"):
        kwargs["fifth_source_state"] = source(
            list(range(8 if kind == "source_eight" else 6))
        )
    elif kind == "fourth_register":
        kwargs["fourth_registers"]["eax"] ^= 1
    elif kind == "fourth_vector":
        kwargs["fourth_vector_pointer"] = kwargs["third_vector_pointer"]
    elif kind.startswith("entry_"):
        kwargs["fifth_entry"] = (
            187 if kind == "entry_below_growth_stack" else 0xFFFFFFF9
        )
        kwargs["fifth_registers"]["esp"] = kwargs["fifth_entry"]
    else:
        kwargs["new_vector_pointer"] = 0 if kind == "new_zero" else 0xFFFFFFD0
    before = copy.deepcopy(kwargs)
    with pytest.raises(model.FactoryCallbackFifthError):
        model.apply(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "extent",
    ("first", "second", "third", "fourth", "userdata", "sentinel", "source", "frame"),
)
@pytest.mark.parametrize("edge", ("first", "last", "spare_last_byte"))
def test_new48_disjoint_extents_include_retained_old_buffers_and_spare8(extent, edge):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    start, size = {
        "first": (first["vector_pointer"], 8),
        "second": (kwargs["second_vector_pointer"], 16),
        "third": (kwargs["third_vector_pointer"], 24),
        "fourth": (kwargs["fourth_vector_pointer"], 32),
        "userdata": (first["userdata"], 72),
        "sentinel": (first["record_pointer"], 24),
        "source": (first["source_pointer"], 72),
        "frame": (kwargs["fifth_entry"] - 188, 196),
    }[extent]
    kwargs["new_vector_pointer"] = {
        "first": start,
        "last": start + size - 1,
        "spare_last_byte": start - 47,
    }[edge]
    with pytest.raises(model.FactoryCallbackFifthError, match="overlap"):
        model.apply(**kwargs)


@pytest.mark.parametrize("relation", ("before", "after", "uint32_end"))
def test_adjacent_extents_and_uint32_capacity_endpoint_are_accepted(relation):
    kwargs = inputs()
    kwargs["new_vector_pointer"] = {
        "before": kwargs["fourth_vector_pointer"] - 48,
        "after": kwargs["fourth_vector_pointer"] + 32,
        "uint32_end": 0xFFFFFFCF,
    }[relation]
    fifth = model.apply(**kwargs)["fifth"]
    assert fifth["vector"]["capacity_pointer"] == kwargs["new_vector_pointer"] + 48


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
def test_actual_fifth_class_operation_is_checked_independently(monkeypatch, field):
    kwargs, original, reached = inputs(), model.callback.apply, []

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original(source_state, destination_state, vector, **arguments)
        if len(vector["records"]) == 4:
            reached.append(True)
            operation = result["class_operation"]
            if field == "destination":
                operation["destination"]["payloads"][0] ^= 1
            elif field == "copies":
                operation["copies"][0]["destination"] ^= 1
            elif field == "vector":
                operation["vector"]["capacity"] = 5
            elif field == "old_record":
                operation["vector"]["records"][1][0] = 1
            elif field == "return_word":
                operation["return_word"] ^= 1
            elif field == "argument_kind":
                operation["argument_kind"] = "internal"
            else:
                operation["grew"] = False
        return result

    monkeypatch.setattr(model.callback, "apply", corrupted)
    with pytest.raises(
        model.FactoryCallbackFifthError,
        match="fifth existing-key class operation packet",
    ):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize(
    "field", ("prefix", "caller", "class_return", "full_return", "cookie", "requests")
)
def test_fifth_baseline_prefix_caller_return_and_cookie_have_independent_guards(
    monkeypatch, field
):
    kwargs, original, reached = inputs(), model.tree_model.full_return_model.apply, []

    def corrupted(**arguments):
        result = original(**arguments)
        if arguments["callback_entry"] == kwargs["fifth_entry"]:
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
    with pytest.raises(model.FactoryCallbackFifthError, match="fifth"):
        model.apply(**kwargs)
    assert reached == [True]


@pytest.mark.parametrize("field", ("tree_count", "links", "vector", "capacity"))
def test_retained_fourth_metadata_corruption_is_rejected(monkeypatch, field):
    kwargs, original = inputs(), model.fourth_model.apply

    def corrupted(**arguments):
        result = original(**arguments)
        if field == "tree_count":
            result["fourth"]["tree_count"] += 1
        elif field == "links":
            result["fourth"]["sentinel_link_ids"]["leftmost"] = None
        elif field == "vector":
            result["fourth"]["vector"]["records"][0][0] = 1
        else:
            result["fourth"]["vector"]["capacity"] = 6
        return result

    monkeypatch.setattr(model.fourth_model, "apply", corrupted)
    with pytest.raises(model.FactoryCallbackFifthError, match="retained fourth packet"):
        model.apply(**kwargs)


def test_all_five_packets_and_inputs_are_detached():
    kwargs = inputs()
    before = copy.deepcopy(kwargs)
    result = model.apply(**kwargs)
    untouched = copy.deepcopy(result)
    result["fifth"]["source_state"]["payloads"][0] ^= 1
    result["fifth"]["callback_operation"]["destination"]["payloads"][0] ^= 1
    result["fifth"]["class_transfer"]["destination"]["tree"]["nodes"][0]["key"] ^= 1
    result["fifth"]["vector"]["records"][0][1] ^= 1
    result["fifth"]["vector_free_request"]["pointer"] ^= 1
    result["fifth"]["normal_requests"][0]["after"].clear()
    result["fifth"]["full_return"]["registers"]["eax"] = 1
    assert kwargs == before
    assert all(
        result[name] == untouched[name]
        for name in ("first", "second", "third", "fourth")
    )
    assert (
        result["fifth"]["class_transfer"]["destination"]["payloads"]
        == untouched["fifth"]["class_transfer"]["destination"]["payloads"]
    )
    assert (
        result["fifth"]["callback_operation"]["vector"]["records"]
        == untouched["fifth"]["callback_operation"]["vector"]["records"]
    )
    assert (
        result["fifth"]["vector"]["records"][1:]
        == untouched["fifth"]["vector"]["records"][1:]
    )
    assert model.apply(**kwargs) == untouched


def test_fifth_error_preserves_predecessor_error_hierarchy():
    assert issubclass(
        model.FactoryCallbackFifthError, model.fourth_model.FactoryCallbackFourthError
    )
    assert issubclass(
        model.FactoryCallbackFifthError,
        model.tree_model.full_return_model.FactoryCallbackReturnError,
    )


@pytest.mark.parametrize(
    "size,capacity", ((0, 0), (1, 1), (2, 2), (3, 3), (4, 5), (5, 6), (5, 5))
)
def test_fifth_growth_option_cannot_expand_other_geometry(size, capacity):
    operation = model.callback.operation
    with pytest.raises(operation.OperationError, match="exactly four full"):
        operation.next_capacity(size, capacity, allow_fifth_growth=True)


def test_operation_defaults_stay_small_and_exact_fifth_flag_is_required():
    operation = model.callback.operation
    assert [operation.next_capacity(size, size) for size in range(4)] == [1, 2, 3, 4]
    assert operation.next_capacity(4, 5) == 5
    with pytest.raises(operation.OperationError, match="small-vector domain"):
        operation.next_capacity(4, 4)
    assert operation.next_capacity(4, 4, allow_fifth_growth=True) == 6


@pytest.mark.parametrize("value", (None, 0, 1, "yes", [], {}))
def test_fifth_growth_flag_must_be_strict_bool(value):
    with pytest.raises(
        model.callback.operation.OperationError, match="allow_fifth_growth must be bool"
    ):
        model.callback.operation.next_capacity(4, 4, allow_fifth_growth=value)


@pytest.mark.parametrize("size,capacity", ((3, 3), (4, 5), (5, 6), (5, 5)))
def test_callback_fifth_flag_admits_no_fourth_or_sixth_frontier(size, capacity):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    vector = dict(
        records=[[0, first["source_pointer"]] for _ in range(size)], capacity=capacity
    )
    with pytest.raises(
        model.callback.CallbackError, match="exactly four full external"
    ):
        model.callback.apply(
            copy.deepcopy(kwargs["fifth_source_state"]),
            copy.deepcopy(kwargs["fourth_source_state"]),
            vector,
            source_pointer=first["source_pointer"],
            source_word=first["source_word"],
            destination_word=first["source_word"],
            destination_refs=first["destination_refs"],
            source_refs=first["source_refs"],
            transfers=first["transfers"],
            allow_growth=True,
            allow_fifth_growth=True,
        )


@pytest.mark.parametrize(
    "first_keys,reason",
    (
        ([0, 1, 17], "exactly eight"),
        ([3, 16, 20], "exactly eight"),
        ([0, 1, 3], "key16"),
    ),
)
def test_retained_destination_count_and_omitted_key16_are_exact(first_keys, reason):
    kwargs = inputs(arguments(first_keys))
    with pytest.raises(model.FactoryCallbackFifthError, match=reason):
        model.apply(**kwargs)


@pytest.mark.parametrize("field", ("registry", "tables", "assignments", "stack"))
def test_coordinated_fifth_baseline_and_suffix_corruption_fails_independent_contract(
    monkeypatch, field
):
    kwargs = inputs()
    original_callback = model.callback.apply
    original_full = model.tree_model.full_return_model.apply
    baseline, reached = [], []

    def full(**arguments):
        baseline.append(arguments["callback_entry"] == kwargs["fifth_entry"])
        try:
            return original_full(**arguments)
        finally:
            baseline.pop()

    def corrupted(source_state, destination_state, vector, **arguments):
        result = original_callback(source_state, destination_state, vector, **arguments)
        if (baseline and baseline[-1]) or len(vector["records"]) == 4:
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
    with pytest.raises(model.FactoryCallbackFifthError, match="table contract"):
        model.apply(**kwargs)
    assert reached == [0, 4]


def callback_arguments(first):
    return dict(
        source_pointer=first["source_pointer"],
        source_word=first["source_word"],
        destination_word=first["source_word"],
        destination_refs=first["destination_refs"],
        source_refs=first["source_refs"],
        transfers=first["transfers"],
    )


@pytest.mark.parametrize("value", (None, 0, 1, "yes", [], {}))
def test_callback_fifth_flag_requires_strict_bool(value):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    with pytest.raises(
        model.callback.CallbackError, match="allow_fifth_growth must be bool"
    ):
        model.callback.apply(
            copy.deepcopy(kwargs["fifth_source_state"]),
            copy.deepcopy(kwargs["fourth_source_state"]),
            dict(records=[[0, first["source_pointer"]] for _ in range(4)], capacity=4),
            **callback_arguments(first),
            allow_growth=True,
            allow_fifth_growth=value
        )


def test_callback_fifth_flag_requires_growth_and_default_stays_at_three_records():
    kwargs = inputs()
    first = kwargs["first_arguments"]
    source_state, destination = copy.deepcopy(
        kwargs["fifth_source_state"]
    ), copy.deepcopy(kwargs["fourth_source_state"])
    vector = dict(records=[[0, first["source_pointer"]] for _ in range(4)], capacity=4)
    with pytest.raises(
        model.callback.CallbackError, match="fifth growth requires allow_growth"
    ):
        model.callback.apply(
            source_state,
            destination,
            vector,
            **callback_arguments(first),
            allow_fifth_growth=True
        )
    for allow_growth in (False, True):
        with pytest.raises(
            model.callback.CallbackError, match="at most three live records"
        ):
            model.callback.apply(
                source_state,
                destination,
                vector,
                **callback_arguments(first),
                allow_growth=allow_growth
            )


@pytest.mark.parametrize("bad_record", ([True, 1], [0, 2**32], [0], (0, 1)))
def test_fifth_operation_validates_each_old_record_and_does_not_mutate_inputs(
    bad_record,
):
    kwargs = inputs()
    first = kwargs["first_arguments"]
    source_state, destination = copy.deepcopy(
        kwargs["fifth_source_state"]
    ), copy.deepcopy(kwargs["fourth_source_state"])
    vector = dict(records=[[0, first["source_pointer"]] for _ in range(4)], capacity=4)
    vector["records"][2] = bad_record
    before = copy.deepcopy((source_state, destination, vector))
    with pytest.raises(model.callback.CallbackError, match="two uint32 words"):
        model.callback.apply(
            source_state,
            destination,
            vector,
            **callback_arguments(first),
            allow_growth=True,
            allow_fifth_growth=True
        )
    assert (source_state, destination, vector) == before


@pytest.mark.parametrize("entry", (0, 55, 56, 187, 0xFFFFFFF9, 0xFFFFFFFF))
def test_complete_fifth_callback_and_growth_stack_cannot_wrap(entry):
    kwargs = inputs(fifth_entry=entry)
    with pytest.raises(
        model.FactoryCallbackFifthError, match="callback and growth stack extent wraps"
    ):
        model.apply(**kwargs)


@pytest.mark.parametrize(
    "relation,accepted",
    (
        ("ends_at_lower", True),
        ("ends_one_into_lower", False),
        ("starts_at_upper", True),
        ("starts_one_into_upper", False),
    ),
)
def test_new48_exact_growth_stack_adjacency_and_single_spare_byte_overlap(
    relation, accepted
):
    kwargs = inputs()
    entry = kwargs["fifth_entry"]
    kwargs["new_vector_pointer"] = {
        "ends_at_lower": entry - 188 - 48,
        "ends_one_into_lower": entry - 187 - 48,
        "starts_at_upper": entry + 8,
        "starts_one_into_upper": entry + 7,
    }[relation]
    if accepted:
        result = model.apply(**kwargs)["fifth"]
        assert result["vector"]["begin"] == kwargs["new_vector_pointer"]
        assert result["vector"]["capacity_pointer"] == kwargs["new_vector_pointer"] + 48
    else:
        with pytest.raises(
            model.FactoryCallbackFifthError,
            match="overlap",
        ):
            model.apply(**kwargs)
