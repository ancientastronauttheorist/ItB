#!/usr/bin/env python3
"""Build or verify exact native ``__callnewh`` static-boundary evidence."""
from __future__ import annotations
import argparse, json, os, stat, sys, tempfile
from pathlib import Path
from typing import Any

_ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(_ROOT))
from scripts.itb_native_assertion_helper_static_boundary import NativeAssertionHelperStaticBoundaryError,_locked_output,_read_locked_json_document  # noqa:E402
from scripts.itb_native_lua_direct_calls import _is_reparse,_read_json_document,_read_json_object  # noqa:E402
from scripts.itb_native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError,_prepare_output_root,_recheck_output_root  # noqa:E402
from src.observatory.native_callnewh_static_boundary import (  # noqa:E402
 ANALYSIS_KIND,SCHEMA_VERSION,NativeCallnewhStaticBoundaryError,_canonical_bytes,
 build_native_callnewh_static_boundary,encode_native_callnewh_static_boundary,
 validate_native_callnewh_static_boundary,validate_native_callnewh_static_boundary_structure)
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError  # noqa:E402

def build_parser()->argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest="command",required=True)
    for command in ("build","verify","verify-structure"):
        item=commands.add_parser(command)
        for name in ("operator-new-static-boundary","direct-calls","program-facts"):item.add_argument("--"+name,required=True,type=Path)
        if command!="verify-structure":item.add_argument("--executable",required=True,type=Path); item.add_argument("--inventory",required=True,type=Path)
        if command=="build":item.add_argument("--output",type=Path)
        else:item.add_argument("--evidence",required=True,type=Path)
    return parser
def _identity(value:dict[str,Any])->bytes:
    if type(value.get("schema_version")) is not int or value.get("schema_version")!=SCHEMA_VERSION or value.get("analysis_kind")!=ANALYSIS_KIND or not isinstance(value.get("build_identity"),dict):raise NativeCallnewhStaticBoundaryError("evidence schema, kind, or identity differs")
    predecessor=value.get("operator_new_static_boundary")
    if not isinstance(predecessor,dict) or type(predecessor.get("canonical_sha256")) is not str:raise NativeCallnewhStaticBoundaryError("evidence lacks operator-new identity")
    return _canonical_bytes({"schema_version":value["schema_version"],"analysis_kind":value["analysis_kind"],"build_identity":value["build_identity"],"operator_new_canonical_sha256":predecessor["canonical_sha256"]})
def _same(value:dict[str,Any],payload:bytes,identity:bytes,expected:bytes)->bool:return _identity(value)==identity and _canonical_bytes(value)==_canonical_bytes(json.loads(expected)) and payload==expected
def _regular(path:Path,root:Path,identity:tuple[int,int]|None=None)->os.stat_result:
    value=path.lstat()
    if stat.S_ISLNK(value.st_mode) or _is_reparse(value) or not stat.S_ISREG(value.st_mode) or path.resolve(strict=True).parent!=root or (identity is not None and (value.st_dev,value.st_ino)!=identity):raise NativeCallnewhStaticBoundaryError("output failed regular-file identity check")
    return value
def _write_immutably_impl(output:Path,rendered:str,value:dict[str,Any])->None:
    configured,resolved,before=_prepare_output_root(); requested=Path(os.path.abspath(output))
    if requested.parent!=configured:raise NativeCallnewhStaticBoundaryError("output must be a direct child of data observatory programs")
    destination,expected,identity=resolved/output.name,rendered.encode("utf-8"),_identity(value)
    if os.path.lexists(destination):
        initial=_regular(destination,resolved); existing,payload=_read_json_document(destination,"existing output"); final=_regular(destination,resolved,(initial.st_dev,initial.st_ino)); _recheck_output_root(configured,resolved,before)
        if not _same(existing,payload,identity,expected):raise NativeCallnewhStaticBoundaryError("refusing to overwrite differing callnewh boundary evidence")
        with _locked_output(destination,resolved,(final.st_dev,final.st_ino)) as descriptor:
            _regular(destination,resolved,(final.st_dev,final.st_ino)); _recheck_output_root(configured,resolved,before); final_value,final_payload=_read_locked_json_document(descriptor,"final existing output")
            if not _same(final_value,final_payload,identity,expected):raise NativeCallnewhStaticBoundaryError("existing output changed during final content validation")
            return
    fd,name=tempfile.mkstemp(prefix="."+output.name+".",suffix=".tmp",dir=resolved); temporary=Path(name)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream:stream.write(rendered);stream.flush();os.fsync(stream.fileno())
        source=temporary.lstat()
        if stat.S_ISLNK(source.st_mode) or _is_reparse(source) or not stat.S_ISREG(source.st_mode):raise NativeCallnewhStaticBoundaryError("temporary output is not a real regular file")
        source_id=(source.st_dev,source.st_ino); _recheck_output_root(configured,resolved,before); os.link(temporary,destination); _regular(destination,resolved,source_id); _recheck_output_root(configured,resolved,before); temporary.unlink(); _regular(destination,resolved,source_id); _recheck_output_root(configured,resolved,before)
        with _locked_output(destination,resolved,source_id) as descriptor:
            _regular(destination,resolved,source_id); _recheck_output_root(configured,resolved,before); final_value,final_payload=_read_locked_json_document(descriptor,"final created output")
            if not _same(final_value,final_payload,identity,expected):raise NativeCallnewhStaticBoundaryError("created output changed during final content validation")
    except Exception:
        try:temporary.unlink()
        except FileNotFoundError:pass
        raise
def _write_immutably(output:Path,rendered:str,value:dict[str,Any])->None:
    try:_write_immutably_impl(output,rendered,value)
    except (NativeAssertionHelperStaticBoundaryError,NativeLuaPropertyFactoryChainError) as exc:raise NativeCallnewhStaticBoundaryError(str(exc)) from exc
def main(argv:list[str]|None=None)->int:
    args=build_parser().parse_args(argv)
    try:
        get=lambda name:_read_json_object(getattr(args,name.replace("-","_")),name)
        operator,direct,facts=(get(name) for name in ("operator-new-static-boundary","direct-calls","program-facts")); common=(operator,direct,facts)
        if args.command=="build":
            result=build_native_callnewh_static_boundary(args.executable,*common,inventory=get("inventory")); rendered=encode_native_callnewh_static_boundary(result)
            if args.output is None:sys.stdout.write(rendered)
            else:_write_immutably(args.output,rendered,result)
        else:
            evidence,payload=_read_json_document(args.evidence,"evidence")
            if payload!=encode_native_callnewh_static_boundary(evidence).encode("utf-8"):raise NativeCallnewhStaticBoundaryError("evidence is not deterministically encoded")
            result=validate_native_callnewh_static_boundary(args.executable,evidence,*common,inventory=get("inventory")) if args.command=="verify" else validate_native_callnewh_static_boundary_structure(evidence,*common); sys.stdout.write(encode_native_callnewh_static_boundary(result))
        return 0
    except (NativeCallnewhStaticBoundaryError,NativeLuaDirectCallError,NativeLuaPropertyFactoryChainError,OSError,UnicodeError,json.JSONDecodeError) as exc:print(f"error: {exc}",file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
