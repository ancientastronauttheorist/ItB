"""Caller-local result slots in native balancing and composed hint contracts."""

import copy

import pytest

from src.observatory import native_tree_balancing_conformance as balancing
from src.observatory import native_tree_empty_hint_conformance as empty
from src.observatory import native_tree_extreme_hint_conformance as extreme
from src.observatory import native_tree_interior_hint_conformance as interior

MODULES = [balancing, empty, extreme, interior]


def read(pages, address, width=4):
    return sum(
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] << (8 * i)
        for i in range(width)
    )


def put(pages, address, value, width=4):
    for i, byte in enumerate(value.to_bytes(width, "little")):
        pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte


def rebase(fixture, output):
    result = copy.deepcopy(fixture)
    pages = {p: bytearray(payload) for p, payload in fixture["pages"].items()}
    put(pages, fixture["s"] + 4, output)
    result["pages"] = {p: bytes(payload) for p, payload in pages.items()}
    result["output"] = output
    return result


@pytest.fixture(
    scope="module",
    params=[(m, edge) for m in MODULES for edge in (0, -1)],
    ids=[f"{m.__name__.split('.')[-1]}-{edge}" for m in MODULES for edge in (0, -1)],
)
def case(request):
    module, edge = request.param
    vector = module.vectors()[edge]
    fixture = module._fixture(vector)
    return module, vector, fixture


def test_default_output_is_identical_when_explicit(case):
    module, vector, fixture = case
    default = module._expected(vector, fixture)
    explicit = module._expected(vector, dict(fixture, output=module.OUTPUT))
    assert default == explicit


def test_caller_local_output_and_untouched_default_page(case):
    module, vector, fixture = case
    baseline = module._expected(vector, fixture)
    # For the enclosing hint owner, H = O-40 and its local O-8 is H+32.
    # The same S+32 address lies above the direct balancing entry/arguments.
    entry = fixture["s"]
    owner = entry + 40
    output = owner - 8
    assert output == entry + 32
    local = rebase(fixture, output)
    before = copy.deepcopy(local)
    expected = module._expected(vector, local)
    assert local == before
    assert expected["registers"] == dict(baseline["registers"], eax=output)
    assert expected["flags"] == baseline["flags"]
    assert expected["endpoint"] == baseline["endpoint"]
    assert read(expected["pages"], output) == fixture["node"]
    assert [
        event
        for event in expected["events"]
        if event["access"] == "write" and event["address"] == output
    ] == [dict(access="write", address=output, width=4, value=fixture["node"])]
    assert not any(
        event["access"] == "write" and event["address"] == module.OUTPUT
        for event in expected["events"]
    )
    assert (
        expected["pages"][module.OUTPUT & ~0xFFF]
        == fixture["pages"][module.OUTPUT & ~0xFFF]
    )
    assert read(expected["pages"], entry + 4) == output
    for offset in (-8, -4, 4, 8):
        assert read(expected["pages"], output + offset) == read(
            local["pages"], output + offset
        )


@pytest.mark.parametrize("edge", [0, -1])
def test_independent_model_repairs_forged_stack_local_result(edge):
    vector = balancing.vectors()[edge]
    fixture = balancing._fixture(vector)
    output = fixture["s"] + 32
    fixture = rebase(fixture, output)
    expected = balancing._expected(vector, fixture)
    assert balancing._model_pages(fixture, expected) == expected["pages"]
    forged = copy.deepcopy(expected)
    pages = {p: bytearray(payload) for p, payload in forged["pages"].items()}
    put(pages, output, fixture["node"] ^ 1)
    forged["pages"] = {p: bytes(payload) for p, payload in pages.items()}
    repaired = balancing._model_pages(fixture, forged)
    # Copying stack pages after writing the modeled output would conceal this
    # corruption by copying the forged value back over the independent result.
    assert repaired != forged["pages"]
    assert repaired == expected["pages"]
    assert read(repaired, output) == fixture["node"]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.split(".")[-1])
@pytest.mark.parametrize("output", [True, -1, 2**32, 0xFFFFFFFE, 0xDEADC000])
def test_invalid_or_unmapped_output_is_rejected(module, output):
    vector = module.vectors()[0]
    fixture = module._fixture(vector)
    if type(output) is int and 0 <= output < 2**32:
        fixture = rebase(fixture, output)
    else:
        fixture["output"] = output
    with pytest.raises(RuntimeError):
        module._expected(vector, fixture)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_result_cannot_cross_from_mapped_page_into_unmapped_page(module):
    vector = module.vectors()[0]
    fixture = module._fixture(vector)
    page = module.OUTPUT & ~0xFFF
    assert page in fixture["pages"] and page + 0x1000 not in fixture["pages"]
    fixture = rebase(fixture, page + 0xFFE)
    with pytest.raises(RuntimeError):
        module._expected(vector, fixture)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.split(".")[-1])
def test_output_contract_must_match_actual_stack_argument(module):
    vector = module.vectors()[0]
    fixture = module._fixture(vector)
    fixture["output"] = fixture["s"] + 32
    with pytest.raises(RuntimeError):
        module._expected(vector, fixture)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.split(".")[-1])
@pytest.mark.parametrize("region", ["frame", "node", "head", "tree"])
def test_output_cannot_overlap_live_frame_or_tree_storage(module, region):
    vector = module.vectors()[0]
    fixture = module._fixture(vector)
    output = {
        "frame": fixture["s"] - 4,
        "node": fixture["node"] + 22,
        "head": balancing.attachment.HEAD + 22,
        "tree": balancing.attachment.TREE + 6,
    }[region]
    fixture = rebase(fixture, output)
    with pytest.raises(RuntimeError, match="output overlaps live storage"):
        module._expected(vector, fixture)
