#!/usr/bin/env python3
"""Build or verify the exact native Lua ``property`` consumer chain."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUTPUT_ROOT = _REPO_ROOT / "data" / "observatory" / "programs"
sys.path.insert(0, str(_REPO_ROOT))

from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _read_json_document,
    _read_json_object,
)
from scripts.itb_native_lua_property_factory_chain import (  # noqa: E402
    _prepare_output_root,
    _recheck_output_root,
)
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError  # noqa: E402
from src.observatory.native_lua_property_factory_chain import (  # noqa: E402
    NativeLuaPropertyFactoryChainError,
)
from src.observatory.native_lua_property_consumer_chain import (  # noqa: E402
    ANALYSIS_KIND,
    SCHEMA_VERSION,
    NativeLuaPropertyConsumerChainError,
    _canonical_bytes,
    build_native_lua_property_consumer_chain,
    encode_native_lua_property_consumer_chain,
    validate_native_lua_property_consumer_chain,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("build", "build exact property-consumer evidence"),
        ("verify", "verify committed property-consumer evidence"),
    ):
        item = subparsers.add_parser(command, help=help_text)
        item.add_argument("--executable", required=True, type=Path)
        item.add_argument("--inventory", required=True, type=Path)
        item.add_argument("--program-facts", required=True, type=Path)
        item.add_argument("--direct-calls", required=True, type=Path)
        item.add_argument("--callbacks", required=True, type=Path)
        item.add_argument("--setfield-publications", required=True, type=Path)
        item.add_argument("--direct-table-setter-publications", required=True, type=Path)
        item.add_argument("--indirect-settable-publications", required=True, type=Path)
        item.add_argument("--table-key-provenance", required=True, type=Path)
        item.add_argument("--terminal-dispositions", required=True, type=Path)
        item.add_argument("--property-factory-chain", required=True, type=Path)
        if command == "build":
            item.add_argument("--output", type=Path)
        else:
            item.add_argument("--evidence", required=True, type=Path)
    return parser


def _replacement_identity(value: dict[str, Any], label: str) -> bytes:
    if (
        value.get("schema_version") != SCHEMA_VERSION
        or value.get("analysis_kind") != ANALYSIS_KIND
    ):
        raise NativeLuaPropertyConsumerChainError(
            f"{label} has another schema or analysis kind"
        )
    identity = value.get("build_identity")
    prerequisite_fields = (
        "atlas",
        "direct_call_census",
        "callback_census",
        "setfield_publication_census",
        "direct_table_setter_publication_census",
        "indirect_settable_publication_census",
        "table_key_provenance_census",
        "terminal_disposition_census",
        "property_factory_chain",
    )
    prerequisites = [value.get(field) for field in prerequisite_fields]
    if not isinstance(identity, dict) or not all(
        isinstance(item, dict) for item in prerequisites
    ):
        raise NativeLuaPropertyConsumerChainError(
            f"{label} lacks prerequisite identity"
        )
    hashes = [item.get("canonical_sha256") for item in prerequisites]
    if not all(type(item) is str for item in hashes):
        raise NativeLuaPropertyConsumerChainError(
            f"{label} lacks canonical prerequisites"
        )
    return _canonical_bytes(
        {
            "schema_version": value["schema_version"],
            "analysis_kind": value["analysis_kind"],
            "build_identity": identity,
            "prerequisites": dict(zip(prerequisite_fields, hashes)),
        }
    )


def _write_evidence_immutably(
    output: Path, rendered: str, result: dict[str, Any]
) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeLuaPropertyConsumerChainError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    identity = _replacement_identity(result, "new evidence")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file():
            raise NativeLuaPropertyConsumerChainError(
                "refusing to replace non-regular output"
            )
        try:
            existing, payload = _read_json_document(destination, "existing output")
            existing_identity = _replacement_identity(existing, "existing output")
        except (
            NativeLuaPropertyConsumerChainError,
            NativeLuaDirectCallError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise NativeLuaPropertyConsumerChainError(
                "refusing to replace unrelated property-consumer evidence"
            ) from exc
        if existing_identity != identity:
            raise NativeLuaPropertyConsumerChainError(
                "refusing to replace evidence for other prerequisites"
            )
        expected = rendered.encode("utf-8")
        if _canonical_bytes(existing) != _canonical_bytes(result) or payload != expected:
            raise NativeLuaPropertyConsumerChainError(
                "refusing to overwrite differing property-consumer evidence"
            )
        _recheck_output_root(configured, resolved, before)
        confirmation, confirmation_payload = _read_json_document(
            destination, "existing output confirmation"
        )
        if (
            _canonical_bytes(confirmation) != _canonical_bytes(result)
            or confirmation_payload != expected
        ):
            raise NativeLuaPropertyConsumerChainError(
                "existing property-consumer evidence changed during comparison"
            )
        _recheck_output_root(configured, resolved, before)
        return
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=resolved
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        _recheck_output_root(configured, resolved, before)
        os.link(temporary, destination)
        os.unlink(temporary)
        _recheck_output_root(configured, resolved, before)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = _read_json_object(args.inventory, "inventory")
        facts = _read_json_object(args.program_facts, "program facts")
        direct = _read_json_object(args.direct_calls, "direct calls")
        callbacks = _read_json_object(args.callbacks, "callbacks")
        setfield = _read_json_object(args.setfield_publications, "setfield publications")
        direct_table = _read_json_object(
            args.direct_table_setter_publications, "direct table-setter publications"
        )
        indirect = _read_json_object(
            args.indirect_settable_publications, "indirect settable publications"
        )
        table_keys = _read_json_object(args.table_key_provenance, "table-key provenance")
        terminal = _read_json_object(args.terminal_dispositions, "terminal dispositions")
        property_factory = _read_json_object(
            args.property_factory_chain, "property-factory chain"
        )
        common = (
            args.executable,
            property_factory,
            direct,
            callbacks,
            setfield,
            direct_table,
            indirect,
            table_keys,
            terminal,
            facts,
        )
        if args.command == "build":
            result = build_native_lua_property_consumer_chain(
                *common, inventory=inventory
            )
            rendered = encode_native_lua_property_consumer_chain(result)
            if args.output is None:
                sys.stdout.write(rendered)
            else:
                _write_evidence_immutably(args.output, rendered, result)
        else:
            evidence, payload = _read_json_document(args.evidence, "evidence")
            if payload != encode_native_lua_property_consumer_chain(evidence).encode("utf-8"):
                raise NativeLuaPropertyConsumerChainError(
                    "evidence is not deterministically encoded"
                )
            result = validate_native_lua_property_consumer_chain(
                args.executable, evidence, *common[1:], inventory=inventory
            )
            sys.stdout.write(encode_native_lua_property_consumer_chain(result))
        return 0
    except (
        NativeLuaPropertyConsumerChainError,
        NativeLuaPropertyFactoryChainError,
        NativeLuaDirectCallError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
