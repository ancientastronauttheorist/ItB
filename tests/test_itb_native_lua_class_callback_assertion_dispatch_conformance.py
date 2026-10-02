"""Independent retained callback-to-dispatch frame, access and page equations."""

import copy
import faulthandler
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = next(
    p for p in Path(__file__).resolve().parents if (p / "src/observatory").is_dir()
)
sys.path.insert(0, str(ROOT))
from src.observatory import (
    native_lua_class_callback_assertion_dispatch_conformance as c,
)
from tests import test_itb_native_lua_class_callback_assertion_prefix_conformance as p
from tests import test_itb_native_assertion_helper_parent_dispatch_conformance as d

PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"
EVIDENCE = PROGRAMS / (
    PREFIX + "native_lua_class_callback_assertion_dispatch_conformance.json"
)
RECIPES = ((1, 0xFFFFFFFF), (0, 1), (0, 2), (2, 0xFFFFFFFF))
FAMILIES = ("null", "absent", "nil", "false")


def old_vector(vector):
    return {k: vector[k] for k in ("alignment", "profile", "family")}


def getter_vector(vector):
    first, second = RECIPES[vector["dispatch_profile"]]
    return dict(first_global=first, second_global=second)


def independent(vector, fixture):
    old = old_vector(vector)
    f = fixture["prefix_fixture"]
    prefix = p.independent_composition(old, f)
    assert prefix["pages"] == p.independent_pages(old, f)
    boundary = p.boundary_for(old)
    q = f["entry"] - 56
    join_registers = dict(prefix["registers"])
    assert join_registers["esp"] == q
    join_pages = dict(prefix["pages"], **{})
    join_pages[0x008B7000] = fixture["global_page"]
    getter = getter_vector(vector)
    assert d.word(join_pages, 0x008B7534) == getter["first_global"]
    assert d.word(join_pages, 0x008B7318) == getter["second_global"]
    arguments = dict(
        entry=q,
        registers=join_registers,
        caller_return=boundary["continuation"],
        condition=boundary["arguments"][0],
        file=boundary["arguments"][1],
        line=boundary["arguments"][2],
        **getter,
    )
    rows = d.independent_events(arguments)
    final_pages = copy.deepcopy(join_pages)
    for access, address, value, _ in rows:
        if access == "write":
            d.patch(final_pages, address, value)
    alt = d.alternate(getter)
    final_registers = dict(
        join_registers,
        eax=(
            getter["second_global"]
            if getter["first_global"] == 0
            else getter["first_global"]
        ),
        ecx=3,
        esi=boundary["continuation"],
        ebp=q - 4,
        esp=q - (24 if alt else 28),
    )
    events = [
        dict(access=a, address=at, width=4, value=value, rva=rva)
        for a, at, value, rva in rows
    ]
    return dict(
        prefix=prefix,
        join_pages=join_pages,
        join_registers=join_registers,
        final_pages=final_pages,
        final_registers=final_registers,
        flags=d.independent_flags(getter),
        events=events,
        trace=[f"0x{pc:08x}" for pc in d.independent_trace(getter)],
        arguments=boundary["arguments"] + ([] if alt else [boundary["continuation"]]),
        endpoint=0x00779B31 if alt else 0x00779550,
    )


def sources():
    return {
        key: json.loads(
            (
                PROGRAMS
                / (
                    PREFIX
                    + (
                        "program_facts"
                        if key == "program_facts"
                        else kind.removeprefix("pe_")
                    )
                    + ".json"
                )
            ).read_text()
        )
        for key, (kind, _) in c.SOURCE_PINS.items()
    }


def test_matrix_is_exact_old_corpus_times_four_distinct_dispatch_recipes():
    expected = [
        dict(v, dispatch_profile=i) for v in c.prefix.vectors() for i in range(4)
    ]
    assert c.vectors() == expected
    assert len(expected) == len({tuple(sorted(v.items())) for v in expected}) == 768
    assert len(c.SOURCE_PINS) == 9
    assert c.SOURCE_PINS["callback_assertion_prefix"] == (
        "pe_native_lua_class_callback_assertion_prefix_conformance",
        "b6486105640001ae644f9ea2023c98ca62626df5f1ab2c2041ba2dea2879484e",
    )


@pytest.mark.parametrize("a", range(16))
def test_independent_actual_frame_pages_events_and_both_argument_shapes(a):
    for family in FAMILIES:
        for dp in range(4):
            vector = dict(
                alignment=a, profile=a % 3, family=family, dispatch_profile=dp
            )
            fixture = c._fixture(vector)
            before = copy.deepcopy(fixture)
            assert set(fixture) == {"prefix_fixture", "global_page"}
            assert (
                type(fixture["global_page"]) is bytes
                and len(fixture["global_page"]) == 4096
            )
            assert 0x008B7000 not in fixture["prefix_fixture"]["pages"]
            wanted = independent(vector, fixture)
            result = c._expected(vector, fixture)
            assert set(result) == {"prefix", "dispatch"}
            assert result["prefix"]["pages"] == wanted["prefix"]["pages"]
            assert result["prefix"]["events"] == wanted["prefix"]["events"]
            assert result["prefix"]["registers"] == wanted["join_registers"]
            dispatch = result["dispatch"]
            assert dispatch["pages"] == wanted["final_pages"]
            assert dispatch["registers"] == wanted["final_registers"]
            assert dispatch["events"] == wanted["events"]
            assert [f"0x{rva:08x}" for rva in dispatch["trace_rvas"]] == wanted["trace"]
            assert (dispatch["flags"], dispatch["flag_mask"]) == wanted["flags"]
            assert dispatch["call"]["arguments"] == wanted["arguments"]
            assert dispatch["endpoint"] == wanted["endpoint"]
            assert fixture == before


@pytest.mark.parametrize("field", ("alignment", "profile", "dispatch_profile"))
@pytest.mark.parametrize("value", (False, True, -1, 16, 2**32, 1.0, None))
def test_strict_vector_words_reject_bool_and_invalid_recipe_indices(field, value):
    vector = dict(alignment=0, profile=0, family="null", dispatch_profile=0)
    vector[field] = value
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind", ("missing", "extra", "family_bool", "family_unknown", "list")
)
def test_closed_vector_schema(kind):
    vector = dict(alignment=0, profile=0, family="null", dispatch_profile=0)
    if kind == "missing":
        vector.pop("family")
    elif kind == "extra":
        vector["unused"] = 0
    elif kind == "family_bool":
        vector["family"] = False
    elif kind == "family_unknown":
        vector["family"] = "true"
    else:
        vector = list(vector.items())
    with pytest.raises(c.ConformanceError):
        c._fixture(vector)


@pytest.mark.parametrize(
    "kind",
    (
        "list",
        "missing",
        "extra",
        "mutable_global",
        "short_global",
        "global_word",
        "global_padding",
        "prefix_list",
        "prefix_extra",
        "prefix_bool_word",
        "prefix_changed_page",
    ),
)
def test_expected_fixture_is_typed_and_bound_to_its_declared_vector(kind):
    vector = dict(alignment=7, profile=1, family="nil", dispatch_profile=2)
    fixture = c._fixture(vector)
    if kind == "list":
        fixture = list(fixture.items())
    elif kind == "missing":
        fixture.pop("global_page")
    elif kind == "extra":
        fixture["unused"] = 0
    elif kind == "mutable_global":
        fixture["global_page"] = bytearray(fixture["global_page"])
    elif kind == "short_global":
        fixture["global_page"] = fixture["global_page"][:-1]
    elif kind in ("global_word", "global_padding"):
        b = bytearray(fixture["global_page"])
        b[0x534 if kind == "global_word" else 0] ^= 1
        fixture["global_page"] = bytes(b)
    elif kind == "prefix_list":
        fixture["prefix_fixture"] = list(fixture["prefix_fixture"].items())
    elif kind == "prefix_extra":
        fixture["prefix_fixture"]["unused"] = 0
    elif kind == "prefix_bool_word":
        fixture["prefix_fixture"]["registers"]["eax"] = False
    else:
        pf = fixture["prefix_fixture"]
        at = pf["entry"] + 12
        pf["pages"] = p.change(pf["pages"], at, p.raw(pf["pages"], at) ^ 1)
    with pytest.raises(c.ConformanceError):
        c._expected(vector, fixture)


SELECTED = [
    dict(alignment=a, profile=a % 3, family=FAMILIES[a // 4], dispatch_profile=a % 4)
    for a in range(16)
]


def supplied_join(vector, fixture, expected):
    wanted = independent(vector, fixture)
    pages = wanted["join_pages"]
    return dict(
        registers=wanted["join_registers"],
        flags=0x246,
        endpoint=0x00779CC2,
        pages=pages,
        pages_sha256={
            f"0x{at:08x}": hashlib.sha256(body).hexdigest()
            for at, body in pages.items()
        },
        prefix_observation=c._prefix_projection(vector, expected["prefix"]),
    )


@pytest.mark.parametrize(
    "kind",
    (
        "schema",
        "register_bool",
        "register_coordinated",
        "flags_bool",
        "flags_df",
        "endpoint",
        "page_mutable",
        "page_padding_refresh",
        "global_refresh",
        "page_missing",
        "hash_bool",
        "prefix_event_hash",
        "prefix_register_bool",
        "prefix_trace",
        "prefix_extra",
    ),
)
def test_join_rejects_coordinated_forgery_even_after_hash_refresh(kind):
    vector = dict(alignment=15, profile=2, family="false", dispatch_profile=2)
    fixture = c._fixture(vector)
    expected = c._expected(vector, fixture)
    packet = supplied_join(vector, fixture, expected)
    if kind == "schema":
        packet["unused"] = 0
    elif kind == "register_bool":
        packet["registers"]["eax"] = False
    elif kind == "register_coordinated":
        packet["registers"]["edx"] ^= 1
        packet["prefix_observation"]["registers"]["edx"] ^= 1
    elif kind == "flags_bool":
        packet["flags"] = True
    elif kind == "flags_df":
        packet["flags"] ^= 0x400
    elif kind == "endpoint":
        packet["endpoint"] += 1
    elif kind == "page_mutable":
        at = next(iter(packet["pages"]))
        packet["pages"][at] = bytearray(packet["pages"][at])
    elif kind in ("page_padding_refresh", "global_refresh"):
        at = (
            0x008B7000
            if kind == "global_refresh"
            else fixture["prefix_fixture"]["entry"] + 12
        )
        d.patch(packet["pages"], at, d.word(packet["pages"], at) ^ 1)
        packet["pages_sha256"] = {
            f"0x{a:08x}": hashlib.sha256(b).hexdigest()
            for a, b in packet["pages"].items()
        }
    elif kind == "page_missing":
        packet["pages"].pop(0x008B7000)
    elif kind == "hash_bool":
        packet["pages_sha256"]["0x008b7000"] = True
    elif kind == "prefix_event_hash":
        packet["prefix_observation"]["memory_events_sha256"] = "0" * 64
    elif kind == "prefix_register_bool":
        packet["prefix_observation"]["registers"]["eax"] = False
    elif kind == "prefix_trace":
        packet["prefix_observation"]["trace_rvas"].append("0x00379550")
    else:
        packet["prefix_observation"]["unused"] = 0
    with pytest.raises(c.ConformanceError):
        c._check_join(packet, vector, fixture, expected)


def test_join_preserves_actual_unclaimed_AF_and_detaches_capture():
    vector = dict(alignment=1, profile=0, family="null", dispatch_profile=0)
    fixture = c._fixture(vector)
    expected = c._expected(vector, fixture)
    packet = supplied_join(vector, fixture, expected)
    packet["flags"] |= 0x10
    before = copy.deepcopy(packet)
    captured = c._check_join(packet, vector, fixture, expected)
    assert captured == before and captured is not packet
    packet["registers"]["edx"] ^= 1
    packet["pages"].clear()
    packet["prefix_observation"]["trace_rvas"].clear()
    assert captured == before


def native_inputs():
    data, image, digest = c.common._load_executable(Path(os.environ["ITB_EXACT_EXE"]))
    assert digest == c.common.EXE_SHA256
    codes, points = c._load_code(data, image, sources())
    assert len(points) == 119 and sum(map(len, codes.values())) == 326
    return codes, points


def packet(index):
    from unicorn import x86_const as x

    codes, points = native_inputs()
    vector = SELECTED[index]
    fixture = c._fixture(vector)
    wanted = independent(vector, fixture)
    captured = {}

    def capture(machine, ids, expected, actual_join):
        captured.update(
            join=copy.deepcopy(actual_join),
            registers={r: machine.reg_read(i) for r, i in ids.items()},
            flags=machine.reg_read(x.UC_X86_REG_EFLAGS),
            endpoint=machine.reg_read(x.UC_X86_REG_EIP),
            pages={p: bytes(machine.mem_read(p, 4096)) for p in wanted["final_pages"]},
        )

    observation = c._run_case(codes, points, vector, capture=capture)
    join = captured["join"]
    assert join["registers"] == wanted["join_registers"]
    assert join["pages"] == wanted["join_pages"]
    assert join["endpoint"] == 0x00779CC2
    assert join["flags"] & 0xCC5 == 0x44
    old_observation = join["prefix_observation"]
    assert old_observation["vector"] == old_vector(vector)
    assert old_observation["registers"] == wanted["join_registers"]
    assert old_observation["memory_events_sha256"] == d.canonical_hash(
        wanted["prefix"]["events"]
    )
    assert old_observation["pages_sha256"] == {
        f"0x{p:08x}": hashlib.sha256(b).hexdigest()
        for p, b in wanted["prefix"]["pages"].items()
    }
    assert captured["registers"] == wanted["final_registers"]
    assert captured["pages"] == wanted["final_pages"]
    flags, mask = wanted["flags"]
    assert captured["flags"] & mask == flags
    assert captured["endpoint"] == wanted["endpoint"]
    assert set(observation) == {
        "vector",
        "prefix_observation",
        "join",
        "dispatch",
        "trace_rvas",
        "opaque_child_executed",
    }
    assert observation["vector"] == vector
    assert observation["prefix_observation"] == old_observation
    assert observation["opaque_child_executed"] is False
    assert observation["join"] == dict(
        registers=join["registers"],
        flags=join["flags"],
        endpoint="0x00379cc2",
        pages_sha256={
            f"0x{at:08x}": hashlib.sha256(body).hexdigest()
            for at, body in wanted["join_pages"].items()
        },
    )
    dispatch = observation["dispatch"]
    assert dispatch["registers"] == wanted["final_registers"]
    assert (dispatch["flags"], dispatch["flag_mask"]) == wanted["flags"]
    assert dispatch["trace_rvas"] == wanted["trace"]
    assert dispatch["events_sha256"] == d.canonical_hash(wanted["events"])
    assert dispatch["memory_sha256"] == d.canonical_hash(
        {
            str(at): hashlib.sha256(body).hexdigest()
            for at, body in wanted["final_pages"].items()
        }
    )
    assert dispatch["arguments"] == wanted["arguments"]
    assert dispatch["second_getter"] is (getter_vector(vector)["first_global"] == 0)
    assert dispatch["opaque_child_executed"] is False
    assert observation["trace_rvas"] == old_observation["trace_rvas"] + wanted["trace"]
    return observation


def controls():
    codes, points = native_inputs()
    vector = dict(alignment=15, profile=2, family="false", dispatch_profile=2)
    for kind, reason in c.CONTROLS.items():
        with pytest.raises(c.ConformanceError) as caught:
            c._run_case(codes, points, vector, kind)
        assert str(caught.value) == reason, kind


def isolated(action, index=0):
    if not os.environ.get("ITB_EXACT_EXE"):
        pytest.skip("set ITB_EXACT_EXE and reviewed private native runtime")
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), action, str(index)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=2400,
    )
    assert result.returncode == 0, (result.stdout + result.stderr).decode(
        "utf-8", errors="replace"
    )[-4000:]


@pytest.mark.parametrize("index", range(16))
def test_selected_continuous_native_join_all_alignments_profiles_families_and_branches(
    index,
):
    isolated("packet", index)


def test_all_controls_fail_at_the_declared_phase():
    isolated("controls")


@pytest.fixture
def receipt():
    if not EVIDENCE.is_file():
        pytest.skip("primary has not published the sealed native receipt")
    return json.loads(EVIDENCE.read_text())


def test_sealed_receipt_exact_prefix_projection_and_independently_derived_totals(
    receipt,
):
    raw = EVIDENCE.read_bytes()
    assert b"\r" not in raw
    assert raw == c.encode_conformance(receipt).encode("utf-8")
    assert d.canonical_hash(receipt) == c.SEALED_SHA256
    assert c.validate_structure(receipt, sources())["status"] == "structurally_verified"
    assert receipt["vectors"] == c.vectors()
    assert (
        receipt["prefix_observations_sha256"]
        == "49e83a1601e72244d5cfab28d2e059ee2bdeb135dbce5687acb01183fd6fccc8"
    )
    old = sources()["callback_assertion_prefix"]
    assert receipt["prefix_executed_rvas"] == old["executed_rvas"]
    assert len(receipt["body"]["ranges"]) == 5
    assert len(receipt["body"]["points"]) == 119
    assert len(receipt["executed_rvas"]) == 98
    assert set(receipt["executed_rvas"]) == set(receipt["prefix_executed_rvas"]) | set(
        receipt["dispatch_executed_rvas"]
    )
    assert len(receipt["dispatch_executed_rvas"]) == 39
    summary = receipt["summary"]
    for key, value in dict(
        cases=768,
        unique_prefixes=192,
        static_sites=119,
        executed_sites=98,
        instruction_bytes=326,
        native_instructions=57216,
        prefix_native_instructions=33024,
        dispatch_native_instructions=24192,
        supplied_api_calls=2880,
        assertion_joins=768,
        first_getters=768,
        second_getters=384,
        normal=384,
        alternate=384,
        marker_calls=576,
        global_writes=0,
        opaque_native_instructions=0,
        accounting_promotions=0,
    ).items():
        assert type(summary[key]) is int and summary[key] == value, key
    assert summary["families"] == {family: 192 for family in FAMILIES}
    assert summary["controls"] == len(c.CONTROLS)
    assert {
        row["kind"]: row["reason"] for row in receipt["negative_controls"]
    } == c.CONTROLS
    assert all(row["rejected"] is True for row in receipt["negative_controls"])
    assert len(receipt["source_receipts"]) == 9
    for forbidden in (
        "0x00379550",
        "0x00379b31",
        "0x00379cf5",
        "0x00379cfa",
        "0x00379d09",
        "0x0038e3af",
        "0x0038e3bc",
        "0x0038e3c7",
    ):
        assert forbidden not in receipt["executed_rvas"]


@pytest.mark.parametrize(
    "kind",
    (
        "summary",
        "vectors",
        "prefix_hash",
        "join_hash",
        "observation_hash",
        "controls",
        "sites",
        "body",
        "pins",
        "scope",
    ),
)
def test_mutations_cannot_reseal_receipt(kind, receipt):
    forged = copy.deepcopy(receipt)
    if kind == "summary":
        forged["summary"]["cases"] += 1
    elif kind == "vectors":
        forged["vectors"][0]["dispatch_profile"] = 2
    elif kind == "prefix_hash":
        forged["prefix_observations_sha256"] = "0" * 64
    elif kind == "join_hash":
        forged["join_observations_sha256"] = "0" * 64
    elif kind == "observation_hash":
        forged["observations_sha256"] = "0" * 64
    elif kind == "controls":
        forged["negative_controls"][0]["rejected"] = False
    elif kind == "sites":
        forged["executed_rvas"].append("0x00379550")
    elif kind == "body":
        forged["body"]["ranges"][0]["sha256"] = "0" * 64
    elif kind == "pins":
        forged["source_receipts"]["parent"]["canonical_sha256"] = "0" * 64
    else:
        forged["scope"]["checked"].append("forged claim")
    with pytest.raises(c.ConformanceError):
        c.validate_structure(forged, sources())


@pytest.mark.parametrize(
    "key",
    (
        "program_facts",
        "factory_chain",
        "marker_semantics",
        "marker_conformance",
        "callback_error",
        "parent",
        "first",
        "second",
        "callback_assertion_prefix",
    ),
)
def test_all_static_dependencies_are_pinned(key, receipt):
    supplied = sources()
    supplied[key]["analysis_kind"] = "forged_analysis"
    with pytest.raises(c.ConformanceError):
        c.validate_structure(receipt, supplied)


@pytest.mark.parametrize("shape", ("missing", "extra", "list", "bool_document"))
def test_source_partition_types_fail_before_pe_loading(shape):
    supplied = sources()
    if shape == "missing":
        supplied.pop("parent")
    elif shape == "extra":
        supplied["unused"] = {}
    elif shape == "list":
        supplied = list(supplied.items())
    else:
        supplied["first"] = True
    with pytest.raises(c.ConformanceError):
        c._preflight(supplied)


@pytest.mark.parametrize("command", ("build", "verify", "verify-structure"))
def test_exact_cli_build_verify_and_structure(command, receipt):
    executable = os.environ.get("ITB_EXACT_EXE")
    if command != "verify-structure" and not executable:
        pytest.skip("set ITB_EXACT_EXE and reviewed private native runtime")
    args = [
        sys.executable,
        str(
            ROOT
            / "scripts/itb_native_lua_class_callback_assertion_dispatch_conformance.py"
        ),
        command,
    ]
    for key, (kind, _) in c.SOURCE_PINS.items():
        path = PROGRAMS / (
            PREFIX
            + ("program_facts" if key == "program_facts" else kind.removeprefix("pe_"))
            + ".json"
        )
        args += ["--" + key.replace("_", "-"), str(path)]
    if command != "verify-structure":
        args += ["--executable", executable]
    if command != "build":
        args += ["--evidence", str(EVIDENCE)]
    env = os.environ.copy()
    env.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=2400)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")[
        -4000:
    ]
    output = json.loads(result.stdout)
    if command == "build":
        assert result.stdout == EVIDENCE.read_bytes()
    else:
        assert output["status"] == (
            "verified" if command == "verify" else "structurally_verified"
        )
        assert output["evidence_sha256"] == c.SEALED_SHA256


if __name__ == "__main__":
    faulthandler.disable()
    if sys.argv[1] == "packet":
        packet(int(sys.argv[2]))
    else:
        controls()
