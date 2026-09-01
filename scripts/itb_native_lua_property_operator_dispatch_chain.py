#!/usr/bin/env python3
"""Build or verify exact native Lua ``property`` operator-dispatch evidence."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(_REPO_ROOT))

from scripts.itb_native_lua_direct_calls import _read_json_document,_read_json_object  # noqa: E402
from scripts.itb_native_lua_property_factory_chain import _prepare_output_root,_recheck_output_root  # noqa: E402
from src.observatory.native_lua_property_operator_dispatch_chain import (  # noqa: E402
    ANALYSIS_KIND,SCHEMA_VERSION,NativeLuaPropertyOperatorDispatchChainError,_canonical_bytes,
    build_native_lua_property_operator_dispatch_chain,encode_native_lua_property_operator_dispatch_chain,
    validate_native_lua_property_operator_dispatch_chain,
)


def build_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest="command",required=True)
    for command in ("build","verify"):
        item=sub.add_parser(command)
        for name in ("executable","inventory","program-facts","direct-calls","callbacks","setfield-publications","direct-table-setter-publications","indirect-settable-publications","table-key-provenance","terminal-dispositions","property-factory-chain","property-consumer-chain","property-initializer-chain"):
            item.add_argument("--"+name,required=True,type=Path)
        item.add_argument("--output",type=Path) if command=="build" else item.add_argument("--evidence",required=True,type=Path)
    return parser


def _identity(value: dict) -> bytes:
    if value.get("schema_version")!=SCHEMA_VERSION or value.get("analysis_kind")!=ANALYSIS_KIND: raise NativeLuaPropertyOperatorDispatchChainError("evidence has another schema or kind")
    init=value.get("initializer_chain")
    if not isinstance(init,dict) or not isinstance(init.get("canonical_sha256"),str): raise NativeLuaPropertyOperatorDispatchChainError("evidence lacks initializer identity")
    return _canonical_bytes({"schema_version":value["schema_version"],"analysis_kind":value["analysis_kind"],"build_identity":value.get("build_identity"),"initializer_chain":init["canonical_sha256"]})


def _write_immutably(output: Path,rendered: str,value: dict) -> None:
    configured,resolved,before=_prepare_output_root(); requested=Path(os.path.abspath(output))
    if requested.parent!=configured: raise NativeLuaPropertyOperatorDispatchChainError("output must be a direct child of data observatory programs")
    destination=resolved/output.name; identity=_identity(value); payload=rendered.encode("utf-8")
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not destination.is_file(): raise NativeLuaPropertyOperatorDispatchChainError("refusing to replace non-regular output")
        existing,current=_read_json_document(destination,"existing output")
        if _identity(existing)!=identity or _canonical_bytes(existing)!=_canonical_bytes(value) or current!=payload: raise NativeLuaPropertyOperatorDispatchChainError("refusing to overwrite differing operator evidence")
        _recheck_output_root(configured,resolved,before); return
    fd,temp=tempfile.mkstemp(prefix="."+output.name+".",suffix=".tmp",dir=resolved)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream: stream.write(rendered); stream.flush(); os.fsync(stream.fileno())
        _recheck_output_root(configured,resolved,before); os.link(temp,destination); os.unlink(temp); _recheck_output_root(configured,resolved,before)
    except Exception:
        try: os.unlink(temp)
        except FileNotFoundError: pass
        raise


def main(argv: list[str]|None=None) -> int:
    args=build_parser().parse_args(argv)
    try:
        get=lambda name:_read_json_object(getattr(args,name.replace("-","_")),name)
        inventory,facts,direct,callbacks,setfield,direct_table,indirect,keys,terminal,property_factory,consumer,initializer=(get(name) for name in ("inventory","program-facts","direct-calls","callbacks","setfield-publications","direct-table-setter-publications","indirect-settable-publications","table-key-provenance","terminal-dispositions","property-factory-chain","property-consumer-chain","property-initializer-chain"))
        common=(initializer,consumer,property_factory,direct,callbacks,setfield,direct_table,indirect,keys,terminal,facts)
        if args.command=="build":
            value=build_native_lua_property_operator_dispatch_chain(args.executable,*common,inventory=inventory); rendered=encode_native_lua_property_operator_dispatch_chain(value)
            _write_immutably(args.output,rendered,value) if args.output else sys.stdout.write(rendered)
        else:
            evidence,payload=_read_json_document(args.evidence,"evidence")
            if payload!=encode_native_lua_property_operator_dispatch_chain(evidence).encode("utf-8"): raise NativeLuaPropertyOperatorDispatchChainError("evidence is not deterministically encoded")
            sys.stdout.write(encode_native_lua_property_operator_dispatch_chain(validate_native_lua_property_operator_dispatch_chain(args.executable,evidence,*common,inventory=inventory)))
        return 0
    except (NativeLuaPropertyOperatorDispatchChainError,OSError,UnicodeError,json.JSONDecodeError) as exc:
        print(f"error: {exc}",file=sys.stderr); return 1


if __name__=="__main__": raise SystemExit(main())
