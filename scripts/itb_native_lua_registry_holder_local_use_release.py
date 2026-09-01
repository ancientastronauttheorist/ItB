#!/usr/bin/env python3
"""Build or verify native Lua registry-holder local-use evidence."""
from __future__ import annotations
import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OUT = _REPO_ROOT / "data" / "observatory" / "programs"
sys.path.insert(0, str(_REPO_ROOT))
from scripts.itb_native_lua_direct_calls import (  # noqa: E402
    _is_reparse,
    _read_json_document,
    _read_json_object,
)
from scripts.itb_native_lua_property_factory_chain import _prepare_output_root, _recheck_output_root
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError
from src.observatory.native_lua_property_factory_chain import (
    NativeLuaPropertyFactoryChainError,
)
from src.observatory.native_lua_registry_holder_local_use_release import (
    ANALYSIS_KIND, SCHEMA_VERSION, NativeLuaRegistryHolderError, _canonical_bytes,
    build_native_lua_registry_holder_local_use_release_census,
    encode_native_lua_registry_holder_local_use_release_census,
    validate_native_lua_registry_holder_local_use_release_census,
)

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="command",required=True)
    for command in ("build","verify"):
        q=sub.add_parser(command)
        for name in ("executable","inventory","program-facts","direct-calls","terminal-dispositions"):
            q.add_argument("--"+name,required=True,type=Path)
        q.add_argument("--output",type=Path) if command=="build" else q.add_argument("--evidence",required=True,type=Path)
    return p

def _identity(value: dict) -> bytes:
    if value.get("schema_version")!=SCHEMA_VERSION or value.get("analysis_kind")!=ANALYSIS_KIND: raise NativeLuaRegistryHolderError("evidence has another schema or kind")
    return _canonical_bytes({"schema_version":value["schema_version"],"analysis_kind":value["analysis_kind"],"build_identity":value.get("build_identity"),"prerequisites":value.get("prerequisites")})

def _write_immutably(output: Path, rendered: str, value: dict) -> None:
    configured, resolved, before = _prepare_output_root()
    requested = Path(os.path.abspath(output))
    if requested.parent != configured:
        raise NativeLuaRegistryHolderError(
            "output must be a direct child of data observatory programs"
        )
    destination = resolved / output.name
    expected = rendered.encode("utf-8")
    identity = _identity(value)
    if os.path.lexists(destination):
        initial = destination.lstat()
        if (
            stat.S_ISLNK(initial.st_mode)
            or _is_reparse(initial)
            or not stat.S_ISREG(initial.st_mode)
            or destination.resolve(strict=True).parent != resolved
        ):
            raise NativeLuaRegistryHolderError(
                "refusing to replace a linked, reparse, or non-regular output"
            )
        existing, payload = _read_json_document(destination, "existing output")
        final = destination.lstat()
        _recheck_output_root(configured, resolved, before)
        if (
            stat.S_ISLNK(final.st_mode)
            or _is_reparse(final)
            or not stat.S_ISREG(final.st_mode)
            or destination.resolve(strict=True).parent != resolved
            or (initial.st_dev, initial.st_ino) != (final.st_dev, final.st_ino)
        ):
            raise NativeLuaRegistryHolderError(
                "existing output changed during validation"
            )
        if (
            _identity(existing) != identity
            or _canonical_bytes(existing) != _canonical_bytes(value)
            or payload != expected
        ):
            raise NativeLuaRegistryHolderError(
                "refusing to overwrite differing registry-holder evidence"
            )
        return
    fd, temp_name = tempfile.mkstemp(
        prefix="." + output.name + ".", suffix=".tmp", dir=resolved
    )
    temp = Path(temp_name)
    linked = False
    source_identity: tuple[int, int] | None = None
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        source = temp.lstat()
        if (
            stat.S_ISLNK(source.st_mode)
            or _is_reparse(source)
            or not stat.S_ISREG(source.st_mode)
        ):
            raise NativeLuaRegistryHolderError(
                "temporary output is not a real regular file"
            )
        source_identity = (source.st_dev, source.st_ino)
        _recheck_output_root(configured, resolved, before)
        os.link(temp, destination)
        linked = True
        created = destination.lstat()
        if (
            stat.S_ISLNK(created.st_mode)
            or _is_reparse(created)
            or not stat.S_ISREG(created.st_mode)
            or destination.resolve(strict=True).parent != resolved
            or (created.st_dev, created.st_ino) != source_identity
        ):
            raise NativeLuaRegistryHolderError(
                "created output failed the regular-file identity check"
            )
        _recheck_output_root(configured, resolved, before)
        temp.unlink()
        final = destination.lstat()
        if (
            stat.S_ISLNK(final.st_mode)
            or _is_reparse(final)
            or not stat.S_ISREG(final.st_mode)
            or (final.st_dev, final.st_ino) != source_identity
        ):
            raise NativeLuaRegistryHolderError(
                "created output changed after publication"
            )
        _recheck_output_root(configured, resolved, before)
    except Exception:
        if linked and source_identity is not None:
            try:
                created = destination.lstat()
                if (created.st_dev, created.st_ino) == source_identity:
                    destination.unlink()
            except FileNotFoundError:
                pass
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise

def main(argv: list[str]|None=None) -> int:
    a=build_parser().parse_args(argv)
    try:
        get=lambda n:_read_json_object(getattr(a,n.replace("-","_")),n)
        inventory,facts,direct,terminal=(get(n) for n in ("inventory","program-facts","direct-calls","terminal-dispositions"))
        common=(inventory,facts,direct,terminal)
        if a.command=="build":
            result=build_native_lua_registry_holder_local_use_release_census(a.executable,*common); rendered=encode_native_lua_registry_holder_local_use_release_census(result)
            if a.output:
                _write_immutably(a.output,rendered,result)
            else:
                sys.stdout.write(rendered)
        else:
            evidence,payload=_read_json_document(a.evidence,"evidence")
            if payload!=encode_native_lua_registry_holder_local_use_release_census(evidence).encode("utf-8"): raise NativeLuaRegistryHolderError("evidence is not deterministically encoded")
            sys.stdout.write(encode_native_lua_registry_holder_local_use_release_census(validate_native_lua_registry_holder_local_use_release_census(a.executable,evidence,*common)))
        return 0
    except (
        NativeLuaRegistryHolderError,
        NativeLuaDirectCallError,
        NativeLuaPropertyFactoryChainError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        print("error: "+str(exc),file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
