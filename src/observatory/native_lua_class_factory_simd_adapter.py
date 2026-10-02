"""Exact factory source7/destination8 adapter for the fixed SIMD class join.

Only an actual retained factory fixture may select this mode. This adapter
does not construct a fresh replacement fixture or establish native conformance.
"""

from __future__ import annotations

from src.observatory import native_lua_class_simd_vector_return_conformance as child

SIMD_FACTORY = True
growth, _model_pages = child.growth, child._model_pages
ConformanceError, _require = child.ConformanceError, child._require
VECTOR_KEYS = (child.VECTOR_KEYS - {"xmm_profile"}) | {
    "marker_words",
    "transfers",
    "source_word",
    "destination_word",
    "source_refs",
    "destination_refs",
}
SOURCE_KEYS = {0, 1, 7, 17, 255, 0x80000000, 0xFFFFFFFF}


def _fixture(*args, **kwargs):
    raise ConformanceError("SIMD factory requires an actual retained capture")


def _expected(vector, fixture):
    _require(
        type(vector) is dict and set(vector) == VECTOR_KEYS,
        "factory SIMD vector schema differs",
    )
    _require(
        type(fixture) is dict and set(fixture) == child.FIXTURE_KEYS,
        "factory SIMD class fixture schema differs",
    )
    scalar = child.VECTOR_KEYS - {
        "profile",
        "source_keys",
        "destination_keys",
        "xmm_profile",
    }
    _require(
        all(type(vector[k]) is int and 0 <= vector[k] <= 0xFFFFFFFF for k in scalar)
        and vector["profile"] == "all_existing"
        and vector["old_size"] == 4
        and vector["vector_alignment"] in (0, 7, 31)
        and vector["old_alignment"] == vector["vector_alignment"]
        and vector["node_alignment"] in (0, 7, 31)
        and vector["frame_alignment"] in (0, 15)
        and vector["nil_flag"] == 1,
        "factory SIMD vector geometry differs",
    )
    try:
        source_checked = child.prefix.model.validate_state(fixture["source_state"])
        destination_checked = child.prefix.model.validate_state(
            fixture["destination_state"]
        )
    except (
        child.prefix.model.TransferError,
        child.prefix.model.balancing.BalancingError,
    ) as exc:
        raise ConformanceError(str(exc)) from exc
    source_keys = [n["key"] for n in fixture["source_state"]["tree"]["nodes"]]
    destination_keys = [n["key"] for n in fixture["destination_state"]["tree"]["nodes"]]
    _require(
        source_checked["nodes"] == 7
        and destination_checked["nodes"] == 8
        and set(source_keys) == SOURCE_KEYS
        and set(destination_keys) == SOURCE_KEYS | {16}
        and type(vector["source_keys"]) is list
        and vector["source_keys"] == source_keys
        and type(vector["destination_keys"]) is list
        and vector["destination_keys"] == destination_keys
        and all(
            type(k) is int for k in vector["source_keys"] + vector["destination_keys"]
        ),
        "factory SIMD existing-key domain differs",
    )
    for name, count in (
        ("marker_words", 2),
        ("source_refs", 2),
        ("destination_refs", 2),
    ):
        _require(
            type(vector[name]) is list
            and len(vector[name]) == count
            and all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in vector[name]),
            "factory SIMD Lua word schema differs",
        )
    _require(
        all(
            type(vector[k]) is int and 0 <= vector[k] <= 0xFFFFFFFF
            for k in ("source_word", "destination_word")
        )
        and vector["source_word"] == vector["destination_word"]
        and type(vector["transfers"]) is list
        and len(vector["transfers"]) == 2
        and all(
            type(v) is list
            and len(v) <= 3
            and all(k in ("init", "finalize", "other") for k in v)
            for v in vector["transfers"]
        ),
        "factory SIMD Lua recipe differs",
    )
    result = child._composed_expected(dict(vector, xmm_profile=0), fixture)
    _require(
        result["tree_heap_count"] == 0
        and len(result["insertions"]) == 7
        and all(not row["inserted"] for row in result["insertions"]),
        "factory SIMD tree allocation differs",
    )
    return result
