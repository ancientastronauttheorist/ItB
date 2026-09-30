"""Shared callback import/literal storage and isolated exact native replay."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.observatory import native_lua_class_marker_conformance as marker
from src.observatory import native_lua_table_transfer_conformance as transfer
from src.observatory import native_lua_shared_api_layout as shared

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
BASE = 0x00400000
IMPORT = 0x05000000
STATE = 0x12000000
SLOTS = {
    "lua_equal": 0x3D64C4,
    "lua_getmetatable": 0x3D6534,
    "lua_gettable": 0x3D64BC,
    "lua_insert": 0x3D6514,
    "lua_next": 0x3D64B4,
    "lua_pushnil": 0x3D64B8,
    "lua_pushstring": 0x3D6494,
    "lua_pushvalue": 0x3D64E4,
    "lua_rawgeti": 0x3D64C0,
    "lua_settable": 0x3D6550,
    "lua_settop": 0x3D6510,
    "lua_toboolean": 0x3D64F8,
    "lua_touserdata": 0x3D649C,
}
TARGETS = {name: IMPORT + 0x100 * (i + 1) for i, name in enumerate(sorted(SLOTS))}
LITERALS = {
    BASE + 0x420F68: b"__init\0",
    BASE + 0x43C50C: b"__finalize\0",
    BASE + 0x43C738: b"__luabind_classrep\0",
}


def put(pages, address, value):
    for i, byte in enumerate(value.to_bytes(4, "little")):
        page = (address + i) & ~4095
        payload = bytearray(pages[page])
        payload[(address + i) & 4095] = byte
        pages[page] = bytes(payload)


def raw(pages, address, size):
    return bytes(
        pages[(address + i) & ~4095][(address + i) & 4095] for i in range(size)
    )


def vector_for(helper, *, alignment=15):
    if helper is marker:
        return dict(
            alignment=alignment,
            prefix_length=3,
            has_metatable=True,
            value_kind="zero",
            final_void_eax=0x12345678,
        )
    return dict(
        alignment=alignment, prefix_length=1, kinds=["other", "init", "finalize"]
    )


def caller_for(helper, vector):
    frame = 0x30001000 + vector["alignment"]
    entry = frame - (40 if helper is marker else 64)
    endpoint = BASE + (0x2EC160 if helper is marker else 0x2EC1E0)
    pages = {
        0x30000000 + j * 4096: bytes((i * 31 + j * 17) % 256 for i in range(4096))
        for j in range(2)
    }
    # Retained callback arguments above the table helper's return word.
    for offset, value in (
        (-60, STATE),
        (-56, 0xFFFFD8F0),
        (-52, 23),
        (-48, STATE),
        (-44, 0xFFFFD8F0),
        (-40, 17),
        (-16, 0),
        (-12, 0x14000000),
    ):
        put(pages, frame + offset, value)
    put(pages, entry, endpoint)
    return dict(
        entry=entry,
        return_address=endpoint,
        stack_pages=pages,
        registers=dict(
            eax=0xA2345678,
            ebx=STATE,
            ecx=STATE,
            edx=0xFFFFD8ED,
            esi=TARGETS["lua_rawgeti"],
            edi=0x14000000,
            ebp=frame,
            esp=entry,
        ),
    )


def test_canonical_union_slots_heap_reservation_and_shared_literal_page():
    layout = shared.make_layout()
    assert set(layout) == {"targets", "pages"}
    assert shared.TARGETS == layout["targets"] == TARGETS
    assert shared.SLOTS == SLOTS
    assert shared.LITERALS == LITERALS
    assert len(set(TARGETS.values())) == 13
    assert IMPORT not in TARGETS.values()
    assert {target & ~4095 for target in TARGETS.values()} == {IMPORT}
    assert set(layout["pages"]) == {BASE + 0x3D6000, BASE + 0x420000, BASE + 0x43C000}
    assert all(
        type(payload) is bytes and len(payload) == 4096
        for payload in layout["pages"].values()
    )
    for name, slot in SLOTS.items():
        assert (
            int.from_bytes(raw(layout["pages"], BASE + slot, 4), "little")
            == TARGETS[name]
        )
    assert int.from_bytes(raw(layout["pages"], BASE + 0x3D6220, 4), "little") == IMPORT
    for address, payload in LITERALS.items():
        assert raw(layout["pages"], address, len(payload)) == payload
    assert marker.LITERAL & ~4095 == (BASE + 0x43C50C) & ~4095
    shared.validate_layout(layout)


@pytest.mark.parametrize("alignment", [0, 15])
def test_both_helpers_share_state_targets_pages_and_preserve_callback_storage(
    alignment,
):
    layout = shared.make_layout()
    before_layout = copy.deepcopy(layout)
    fixtures = []
    for helper in (marker, transfer):
        vector = vector_for(helper, alignment=alignment)
        caller = caller_for(helper, vector)
        before_caller = copy.deepcopy(caller)
        fixture = helper._fixture(vector, caller=caller, api_layout=layout)
        expected = helper._expected(vector, fixture)
        fixtures.append(fixture)
        assert layout == before_layout and caller == before_caller
        assert fixture["api_targets"] == TARGETS
        assert expected["endpoint"] == caller["return_address"]
        assert expected["registers"]["esp"] == caller["entry"] + 4
        for name in ("ebx", "esi", "edi", "ebp"):
            assert expected["registers"][name] == caller["registers"][name]
        assert expected["calls"]
        assert all(call["arguments"][0] == STATE for call in expected["calls"])
        assert all(call["target"] == TARGETS[call["api"]] for call in expected["calls"])
        for address in range(caller["entry"], 0x30002000):
            assert raw(expected["pages"], address, 1) == raw(
                caller["stack_pages"], address, 1
            )
        for page, payload in layout["pages"].items():
            assert fixture["pages"][page] == expected["pages"][page] == payload
    for page in layout["pages"]:
        assert fixtures[0]["pages"][page] == fixtures[1]["pages"][page]
    # A caller retaining the source mapping cannot alter either captured fixture.
    layout["targets"]["lua_settop"] = IMPORT
    layout["pages"][BASE + 0x43C000] = bytes(4096)
    assert all(f["api_targets"] == TARGETS for f in fixtures)
    assert all(
        f["pages"][BASE + 0x43C000] == before_layout["pages"][BASE + 0x43C000]
        for f in fixtures
    )


@pytest.mark.parametrize("helper", [marker, transfer])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing_api",
        "unknown_api",
        "bool_target",
        "collision",
        "heap_alias",
        "retarget_and_iat",
        "iat_mismatch",
        "heap_iat",
        "sibling_literal",
        "missing_page",
        "short_page",
        "mutable_page",
        "bool_page",
        "unknown_field",
    ],
)
def test_untrusted_layout_rejected_before_native_execution(helper, mutation):
    layout = shared.make_layout()
    if mutation == "missing_api":
        del layout["targets"]["lua_rawgeti"]
    elif mutation == "unknown_api":
        layout["targets"]["lua_unreviewed"] = IMPORT + 0xE00
    elif mutation == "bool_target":
        layout["targets"]["lua_settop"] = True
    elif mutation == "collision":
        layout["targets"]["lua_settop"] = layout["targets"]["lua_pushstring"]
    elif mutation == "heap_alias":
        layout["targets"]["lua_settop"] = IMPORT
    elif mutation == "retarget_and_iat":
        layout["targets"]["lua_settop"] = IMPORT + 0xE00
        put(layout["pages"], BASE + SLOTS["lua_settop"], IMPORT + 0xE00)
    elif mutation == "iat_mismatch":
        put(layout["pages"], BASE + SLOTS["lua_settop"], TARGETS["lua_pushstring"])
    elif mutation == "heap_iat":
        put(layout["pages"], BASE + 0x3D6220, TARGETS["lua_gettable"])
    elif mutation == "sibling_literal":
        literal = BASE + (0x43C50C if helper is marker else 0x43C738)
        put(layout["pages"], literal, 0)
    elif mutation == "missing_page":
        del layout["pages"][BASE + 0x420000]
    elif mutation == "short_page":
        layout["pages"][BASE + 0x43C000] = bytes(4095)
    elif mutation == "mutable_page":
        layout["pages"][BASE + 0x43C000] = bytearray(layout["pages"][BASE + 0x43C000])
    elif mutation == "bool_page":
        layout["pages"][True] = bytes(4096)
    else:
        layout["unknown"] = 0
    with pytest.raises(RuntimeError):
        helper._fixture(vector_for(helper), api_layout=layout)


@pytest.mark.parametrize("helper", [marker, transfer])
@pytest.mark.parametrize("mutation", ["target", "iat", "literal"])
def test_supplied_fixture_cannot_bypass_layout_validation(helper, mutation):
    vector = vector_for(helper)
    fixture = helper._fixture(vector, api_layout=shared.make_layout())
    if mutation == "target":
        fixture["api_targets"]["lua_settop"] = IMPORT
    elif mutation == "iat":
        put(fixture["pages"], BASE + SLOTS["lua_rawgeti"], 0)
    else:
        put(fixture["pages"], BASE + 0x43C738, 0)
    with pytest.raises(RuntimeError):
        helper._expected(vector, fixture)


@pytest.mark.parametrize("helper", [marker, transfer])
def test_custom_layout_preserves_existing_caller_stack_alias_rejection(helper):
    vector = vector_for(helper)
    caller = caller_for(helper, vector)
    caller["stack_pages"][BASE + 0x420000] = shared.make_layout()["pages"][
        BASE + 0x420000
    ]
    with pytest.raises(RuntimeError):
        helper._fixture(vector, caller=caller, api_layout=shared.make_layout())


def test_exact_native_shared_layout_and_protected_storage_subprocess():
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE and private native dependencies")
    script = """
import json, os, runpy
from pathlib import Path
ns = runpy.run_path(TEST_PATH)
positive = negative = 0
for helper in (ns['marker'], ns['transfer']):
    sources = {
        key: json.loads((ns['PROGRAMS'] / (ns['PREFIX'] +
                         ('program_facts' if key == 'program_facts' else kind.removeprefix('pe_')) + '.json')).read_text())
        for key, (kind, _) in helper.SOURCE_PINS.items()
    }
    data, image, digest = helper._load_executable(Path(os.environ['ITB_EXACT_EXE']))
    assert digest == helper.EXE_SHA256 and image.image_base == helper.BASE
    helper._preflight(sources)
    code, points = helper._load_code(data, image, sources)
    if helper is ns['marker']:
        variants = [dict(has_metatable=False, value_kind='nil'),
                    dict(has_metatable=True, value_kind='false'),
                    dict(has_metatable=True, value_kind='zero')]
    else:
        variants = [dict(kinds=v) for v in ([], ['init'], ['finalize'], ['other','init','finalize'])]
    for variant in variants:
        vector = ns['vector_for'](helper)
        vector.update(variant)
        fixture = helper._fixture(vector, caller=ns['caller_for'](helper, vector),
                                  api_layout=ns['shared'].make_layout())
        result = helper._run_case(code, points, vector, fixture=fixture)
        assert all(v['target'] == ns['TARGETS'][v['api']] for v in result['calls'])
        assert all(v['arguments'][0] == ns['STATE'] for v in result['calls'])
        positive += 1
    for control in ('ancestor', 'literal_padding', 'iat_padding'):
        try:
            helper._run_case(code, points, vector, negative=control, fixture=fixture)
        except RuntimeError as error:
            assert 'protected memory' in str(error), str(error)
            negative += 1
        else:
            raise AssertionError('shared layout accepted ' + control)
print(positive, negative)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "TEST_PATH = " + repr(str(Path(__file__).resolve())) + "\n" + script,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == b"7 6"
