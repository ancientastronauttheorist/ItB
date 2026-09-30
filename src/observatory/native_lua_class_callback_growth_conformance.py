"""Continuous returned-class callback with first-null and bounded full-vector growth."""

from __future__ import annotations
import hashlib
import json
from pathlib import Path
from src.observatory import native_lua_class_callback_conformance as joined
from src.observatory import native_lua_class_empty_vector_return_conformance as empty
from src.observatory import native_lua_class_old_vector_return_conformance as old
from src.observatory.native_assertion_helper_fill_conformance import (
    BASE,
    EXE_SHA256,
    _load_executable,
    _source_identity,
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "pe_native_lua_class_callback_growth_conformance"
SEALED_SHA256 = "59a2123f649633045e35102d2900cf936048f7252095152a27cee6774d60d443"
SOURCE_PINS = {
    "program_facts": joined.SOURCE_PINS["program_facts"],
    "factory_chain": joined.SOURCE_PINS["factory_chain"],
    "class_empty": (empty.ANALYSIS_KIND, empty.SEALED_SHA256),
    "class_old": (old.ANALYSIS_KIND, old.SEALED_SHA256),
    "marker": joined.SOURCE_PINS["marker"],
    "table": joined.SOURCE_PINS["table"],
    "spare_callback": (joined.ANALYSIS_KIND, joined.SEALED_SHA256),
}
FAMILIES = {"first_null": empty, "old_full": old}
ConformanceError, _require = joined.ConformanceError, joined._require


def vectors():
    result = []
    for family in FAMILIES:
        for index, vector in enumerate(joined.vectors()):
            item = {
                k: v
                for k, v in vector.items()
                if k not in ("buffer_address", "spare_records", "old_size")
            }
            alignment = (0, 7, 31)[index % 3]
            item.update(
                class_family=family,
                vector_alignment=alignment,
                old_size=0 if family == "first_null" else (index // 6 + index % 6) % 4,
                old_alignment=(
                    0 if family == "first_null" else (7 + 13 * alignment) % 32
                ),
            )
            result.append(item)
    return result


def _preflight(sources):
    _require(
        set(sources) == set(SOURCE_PINS), "callback growth source partition differs"
    )
    return {
        key: _source_identity(sources[key], *pin, key)
        for key, pin in SOURCE_PINS.items()
    }


def _load_code(data, image, sources):
    # The old-vector receipt includes the first-allocation and copy/free code
    # ranges. Reuse exact decoding and union-conflict checks after our own pins.
    return joined._load_code(
        data,
        image,
        dict(
            program_facts=sources["program_facts"],
            factory_chain=sources["factory_chain"],
            class_spare=sources["class_old"],
            marker=sources["marker"],
            table=sources["table"],
        ),
    )


def _run_case(codes, points, vector, negative=None):
    _require(vector["class_family"] in FAMILIES, "callback growth family differs")
    return joined._run_case(
        codes, points, vector, negative, class_module=FAMILIES[vector["class_family"]]
    )


def _build_unsealed(executable, sources):
    identities = _preflight(sources)
    data, image, digest = _load_executable(Path(executable))
    _require(
        digest == EXE_SHA256 and image.image_base == BASE,
        "exact callback growth executable differs",
    )
    codes, points = _load_code(data, image, sources)
    observations = [_run_case(codes, points, vector) for vector in vectors()]
    unions = {
        family: sorted(
            {
                pc
                for o in observations
                if o["vector"]["class_family"] == family
                for pc in o["trace_rvas"]
            }
        )
        for family in FAMILIES
    }
    all_sites = set().union(*(set(v) for v in unions.values()))
    parent_excluded = ((0x2EC140, 0x2EC154), (0x2EC164, 0x2EC178), (0x2EC188, 0x2EC19E))
    parent_required = {
        p["rva"]
        for p in points
        if joined.START <= int(p["rva"], 16) < joined.END
        and not any(a <= int(p["rva"], 16) < b for a, b in parent_excluded)
    }
    for family, key in (("first_null", "class_empty"), ("old_full", "class_old")):
        union = set(unions[family])
        _require(
            set(sources[key]["executed_rvas"]) <= union
            and set(sources["table"]["executed_rvas"]) <= union
            and parent_required <= union,
            "callback growth selected normal coverage differs",
        )
        _require(
            not any(a <= int(pc, 16) < b for pc in union for a, b in parent_excluded)
            and not joined.CLASS_ARGUMENT_BELOW_END_SITES.intersection(union),
            "callback growth excluded arm executed",
        )
    controls = []
    for family in FAMILIES:
        sample = next(
            v
            for v in vectors()
            if v["class_family"] == family
            and len(v["source_keys"]) == 7
            and v["profile"] == "mixed"
            and len(v["transfers"][0]) == 3
            and (family == "first_null" or v["old_size"] == 3)
        )
        for kind, reason in (
            ("ancestor", "callback ancestor memory differs"),
            ("record", "callback ancestor memory differs"),
            ("word", "callback protected memory differs"),
            ("reference", "callback protected memory differs"),
            ("literal", "callback protected memory differs"),
            ("iat", "callback protected memory differs"),
            ("vector", "callback protected memory differs"),
            ("capacity", "callback protected memory differs"),
            ("result", "callback registers or flags differ"),
            ("lua_prefix", "callback Lua request trace differs"),
            ("heap_request", "callback heap handoff differs"),
            *(
                [
                    ("old", "callback protected memory differs"),
                    ("free_request", "callback free handoff differs"),
                ]
                if family == "old_full"
                else []
            ),
        ):
            try:
                _run_case(codes, points, sample, kind)
            except ConformanceError as exc:
                _require(
                    str(exc) == reason, "callback growth mutation failed incidentally"
                )
                controls.append(
                    dict(family=family, kind=kind, rejected=True, reason=reason)
                )
            else:
                raise ConformanceError("callback growth mutation survived")
        controls.append(dict(_run_case(codes, points, sample, "cookie"), family=family))
    family_summaries = {}
    for family in FAMILIES:
        selected = [o for o in observations if o["vector"]["class_family"] == family]
        family_summaries[family] = dict(
            cases=len(selected),
            executed_sites=len(unions[family]),
            native_instructions=sum(len(o["trace_rvas"]) for o in selected),
            api_calls=sum(o["api_calls"] for o in selected),
            allocations=sum(len(o["allocations"]) for o in selected),
            frees=sum(len(o["frees"]) for o in selected),
            requested_assignments=sum(
                sum(map(len, o["assignments"])) for o in selected
            ),
        )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source_receipts=identities,
        build_identity=sources["program_facts"]["identity"],
        body=dict(
            start_rva=f"0x{joined.START:08x}",
            end_rva=f"0x{joined.END:08x}",
            sha256=joined.BODY_SHA256,
            cfg_sha256=joined.CFG_SHA256,
            ranges=[
                dict(start_rva=f"0x{a:08x}", end_rva=f"0x{a+len(b):08x}")
                for a, b in sorted(codes.items())
            ],
            points=points,
        ),
        vectors=vectors(),
        engine=dict(name="Unicorn", version="2.1.4", architecture="x86_32"),
        executed_rvas=sorted(all_sites),
        executed_rvas_by_family=unions,
        observations_sha256=_canonical_sha256(observations),
        negative_controls=controls,
        summary=dict(
            cases=len(observations),
            families=family_summaries,
            static_sites=len(points),
            executed_sites=len(all_sites),
            instruction_bytes=len(
                {a + i for a, b in codes.items() for i in range(len(b))}
            ),
            callback_bytes=joined.END - joined.START,
            retained_lua_values=4,
            result_count=0,
            opaque_native_instructions=0,
            accounting_promotions=0,
        ),
        scope=dict(
            continuous_machine=True,
            supplied_apis=list(joined.layout.TARGETS) + ["HeapAlloc", "HeapFree"],
            normal_premises=[
                "True class markers and valid disjoint finite class representations",
                "Compatible registry values and supplied normal cdecl Lua responses",
                "Successful stdcall heap responses preserving mapped memory and nonvolatile registers",
                "First-null or full external vector with zero through three live records",
                "Original stack-local record above finite old and new vector storage",
            ],
            checked=[
                "One continuous callback with both markers and both table helpers",
                "Native tree mutation, vector allocation, old live byte copy and free wrapper",
                "Independent logical vector capacity and all original record words",
                "Exact native events, pages, registers, flags, heap requests and continuations",
                "Actual retained Lua identities, filtered requests and zero result count",
            ],
            excluded=[
                "Assertions, Lua errors, allocator failure and exceptions",
                "Real Lua VM or imported DLL instructions and table metamethod effects",
                "Actual heap ownership and host handling of Lua results",
                "Internal record aliases, larger vectors and arbitrary memory domains",
                "No accounting promotion",
            ],
        ),
    )
    _require(
        hashlib.sha256(Path(executable).read_bytes()).hexdigest() == digest,
        "callback growth executable changed",
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence, sources):
    _validate_json_tree(evidence, "evidence")
    identities = _preflight(sources)
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256
        and evidence["source_receipts"] == identities
        and evidence["vectors"] == vectors(),
        "sealed callback growth differs",
    )
    _assert_publication_safe(evidence)
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_conformance(executable, sources):
    result = _build_unsealed(executable, sources)
    validate_structure(result, sources)
    return result


def validate_conformance(executable, evidence, sources):
    validate_structure(evidence, sources)
    _require(
        _canonical_bytes(build_conformance(executable, sources))
        == _canonical_bytes(evidence),
        "exact callback growth differs",
    )
    return dict(status="verified", evidence_sha256=SEALED_SHA256)


encode_conformance = joined.encode_conformance
