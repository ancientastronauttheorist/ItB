"""Independent alias arithmetic, partial-pointer and ordered-copy checks."""

from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from src.observatory import native_lua_class_vector_append_semantics as helper

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "data/observatory/programs"
PREFIX = "windows_build_13725832_31fe35265598_"


@pytest.mark.parametrize(
    "argument,internal,source",
    [
        (99, False, 99),
        (100, True, 100),
        (108, True, 108),
        (109, True, 108),
        (115, True, 108),
        (116, False, 116),
        (120, False, 120),
    ],
)
def test_independent_alias_partition(argument, internal, source):
    r = helper.append_spec(100, 116, 132, argument, 100, 116)
    assert r["branch"] == ("internal" if internal else "external")
    assert r["source"] == source and r["destination"] == 116 and r["end_after"] == 124
    assert (
        r["copy_words"] == 2
        and not r["growth_requested"]
        and r["native_esp_delta"] == 0
    )


def test_growth_rebases_internal_source_and_keeps_external_source():
    internal = helper.append_spec(0x1000, 0x1010, 0x1010, 0x1008, 0x3000, 0x3010)
    external = helper.append_spec(0x1000, 0x1010, 0x1010, 0x800, 0x3000, 0x3010)
    assert internal["source"] == 0x3008 and external["source"] == 0x800
    assert internal["growth_requested"] and external["growth_requested"]
    assert internal["destination"] == external["destination"] == 0x3010


def test_null_skips_copy_but_advances_end():
    r = helper.append_spec(0, 0, 8, 0x1000, 0, 0)
    assert r["copy_words"] == 0 and r["end_after"] == 8


def test_signed_shift_is_not_unsigned_division():
    r = helper.append_spec(
        0x1000, 0x80001008, 0x80001010, 0x80001000, 0x1000, 0x80001008
    )
    assert r["signed_index"] == -0x10000000 and r["source"] == 0x80001000


@pytest.mark.parametrize("source,destination", [(0, 4), (4, 0), (0, 0), (0, 8)])
def test_ordered_dword_copy_is_not_a_snapshot(source, destination):
    before = bytes(range(20))
    expected = bytearray(before)
    for delta in (0, 4):
        expected[destination + delta : destination + delta + 4] = expected[
            source + delta : source + delta + 4
        ]
    r = helper.ordered_copy_spec(before, source, destination)
    assert r["after"] == bytes(expected)
    assert [e["access"] for e in r["events"]] == ["read", "write", "read", "write"]


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize("bad", [True, -1, 0x100000000, None])
def test_invalid_words_rejected(index, bad):
    args = [100, 116, 132, 108, 100, 116]
    args[index] = bad
    with pytest.raises(helper.AppendError):
        helper.append_spec(*args)


@pytest.fixture(scope="module")
def chain():
    suffixes = {
        "chain": "native_lua_class_return_helper_chain",
        "program_facts": "program_facts",
        "evidence": "native_lua_class_vector_append_semantics",
    }
    paths = {k: PROGRAMS / (PREFIX + v + ".json") for k, v in suffixes.items()}
    data = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in paths.items()}
    return paths, {k: data[k] for k in helper.SOURCE_PINS}, data["evidence"]


def test_sealed_receipt(chain):
    paths, sources, evidence = chain
    assert (
        hashlib.sha256(paths["evidence"].read_bytes()).hexdigest()
        == "ef64ab85719c9764808721a0e99689e75af987a51441553b5b7f0e54e3021495"
    )
    assert evidence["summary"] == dict(
        accounting_promotions=0,
        actual_growth_calls=0,
        actual_import_executions=0,
        cases=416,
        modeled_growth_calls=128,
        modeled_nodes=36,
        slice_bytes=95,
        slice_nodes=36,
    )
    assert helper._canonical_sha256(evidence) == helper.SEALED_SHA256
    assert helper.encode_semantics(evidence).encode() == paths["evidence"].read_bytes()
    assert (
        helper.validate_structure(evidence, sources)["status"]
        == "structurally_verified"
    )


@pytest.mark.parametrize(
    "key,value", [("schema_version", True), ("scope", {}), ("raw_bytes", "private")]
)
def test_mutated_receipt_rejected(chain, key, value):
    _, sources, evidence = chain
    changed = copy.deepcopy(evidence)
    changed[key] = value
    with pytest.raises(helper.AppendError):
        helper.validate_structure(changed, sources)


def test_exact_pe_binary_build(chain):
    executable = os.environ.get("ITB_EXACT_EXE")
    if not executable:
        pytest.skip("set ITB_EXACT_EXE for append rebuild")
    paths, sources, _ = chain
    args = ["build", "--executable", executable]
    for k in sources:
        args += ["--" + k.replace("_", "-"), str(paths[k])]
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/itb_native_lua_class_vector_append_semantics.py"),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == b"" and r.stdout == paths["evidence"].read_bytes()
