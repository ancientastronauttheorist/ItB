#!/usr/bin/env python3
"""Build or verify the first-callee pointer-target static boundary."""
from __future__ import annotations
import argparse, json, os, stat, sys, tempfile
from pathlib import Path
_ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(_ROOT))
from scripts.itb_native_assertion_helper_static_boundary import NativeAssertionHelperStaticBoundaryError,_locked_output,_read_locked_json_document,_regular_child
from scripts.itb_native_lua_direct_calls import _is_reparse,_read_json_document,_read_json_object
from scripts.itb_native_lua_property_factory_chain import _prepare_output_root,_recheck_output_root
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import *
from src.observatory.native_query_handler_first_callee_pointer_target_static_boundary import _canonical_bytes
from src.observatory.native_lua_cclosure_setfield_publications import NativeLuaCClosurePublicationError
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError
from src.observatory.native_lua_property_factory_chain import NativeLuaPropertyFactoryChainError

def build_parser():
 p=argparse.ArgumentParser(description=__doc__); subs=p.add_subparsers(dest="command",required=True)
 for command in ("build","verify","verify-structure"):
  q=subs.add_parser(command)
  for name in ("first-callee-static-boundary","query-handler-static-boundary","direct-calls","program-facts"): q.add_argument("--"+name,required=True,type=Path)
  if command!="verify-structure": q.add_argument("--executable",required=True,type=Path); q.add_argument("--inventory",required=True,type=Path)
  if command=="build": q.add_argument("--output",type=Path)
  else: q.add_argument("--evidence",required=True,type=Path)
 return p
def _identity(value):
 if type(value.get("schema_version")) is not int or value.get("schema_version")!=SCHEMA_VERSION or value.get("analysis_kind")!=ANALYSIS_KIND or not isinstance(value.get("build_identity"),dict): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("evidence has another schema, kind, or lacks build identity")
 prerequisite=value.get("first_callee_static_boundary")
 if not isinstance(prerequisite,dict) or type(prerequisite.get("canonical_sha256")) is not str: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("evidence lacks first-callee prerequisite identity")
 return _canonical_bytes({"schema_version":value["schema_version"],"analysis_kind":value["analysis_kind"],"build_identity":value["build_identity"],"first_callee_canonical_sha256":prerequisite["canonical_sha256"]})
def _same(value,payload,identity,expected): return _identity(value)==identity and _canonical_bytes(value)==_canonical_bytes(json.loads(expected)) and payload==expected
def _write_immutably_impl(output,rendered,value):
 configured,resolved,before=_prepare_output_root(); requested=Path(os.path.abspath(output))
 if requested.parent!=configured: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("output must be a direct child of data observatory programs")
 destination,expected,identity=resolved/output.name,rendered.encode("utf-8"),_identity(value)
 if os.path.lexists(destination):
  initial=_regular_child(destination,resolved); existing,payload=_read_json_document(destination,"existing output"); final=_regular_child(destination,resolved,(initial.st_dev,initial.st_ino)); _recheck_output_root(configured,resolved,before)
  if not _same(existing,payload,identity,expected): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("refusing to overwrite differing first-callee pointer-target evidence")
  with _locked_output(destination,resolved,(final.st_dev,final.st_ino)) as fd:
   _recheck_output_root(configured,resolved,before); final_value,final_payload=_read_locked_json_document(fd,"final existing output")
   if not _same(final_value,final_payload,identity,expected): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("existing output changed during final content validation")
   return
 fd,name=tempfile.mkstemp(prefix="."+output.name+".",suffix=".tmp",dir=resolved); temporary,linked,source_identity=Path(name),False,None
 try:
  with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream: stream.write(rendered); stream.flush(); os.fsync(stream.fileno())
  source=temporary.lstat()
  if stat.S_ISLNK(source.st_mode) or _is_reparse(source) or not stat.S_ISREG(source.st_mode): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("temporary output is not a real regular file")
  source_identity=(source.st_dev,source.st_ino); _recheck_output_root(configured,resolved,before); os.link(temporary,destination); linked=True; _regular_child(destination,resolved,source_identity); _recheck_output_root(configured,resolved,before); temporary.unlink(); _regular_child(destination,resolved,source_identity); _recheck_output_root(configured,resolved,before)
  with _locked_output(destination,resolved,source_identity) as locked:
   _recheck_output_root(configured,resolved,before); final_value,final_payload=_read_locked_json_document(locked,"final created output")
   if not _same(final_value,final_payload,identity,expected): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("created output changed during final content validation")
 except Exception:
  if linked and source_identity is not None:
   try:
    made=destination.lstat()
    if (made.st_dev,made.st_ino)==source_identity: destination.unlink()
   except FileNotFoundError: pass
  try: temporary.unlink()
  except FileNotFoundError: pass
  raise
def _write_immutably(output,rendered,value):
 try: _write_immutably_impl(output,rendered,value)
 except (NativeAssertionHelperStaticBoundaryError,NativeLuaPropertyFactoryChainError) as exc: raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError(str(exc)) from exc
def main(argv=None):
 args=build_parser().parse_args(argv)
 try:
  get=lambda name:_read_json_object(getattr(args,name.replace("-","_")),name)
  first,query,direct,facts=(get(name) for name in ("first-callee-static-boundary","query-handler-static-boundary","direct-calls","program-facts")); common=(first,query,direct,facts)
  if args.command=="build":
   result=build_native_query_handler_first_callee_pointer_target_static_boundary(args.executable,*common,inventory=get("inventory")); rendered=encode_native_query_handler_first_callee_pointer_target_static_boundary(result)
   if args.output is None: sys.stdout.write(rendered)
   else: _write_immutably(args.output,rendered,result)
  else:
   evidence,payload=_read_json_document(args.evidence,"evidence")
   if payload!=encode_native_query_handler_first_callee_pointer_target_static_boundary(evidence).encode("utf-8"): raise NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError("evidence is not deterministically encoded")
   result=validate_native_query_handler_first_callee_pointer_target_static_boundary(args.executable,evidence,*common,inventory=get("inventory")) if args.command=="verify" else validate_native_query_handler_first_callee_pointer_target_static_boundary_structure(evidence,*common)
   sys.stdout.write(encode_native_query_handler_first_callee_pointer_target_static_boundary(result))
  return 0
 except (NativeQueryHandlerFirstCalleePointerTargetStaticBoundaryError,NativeAssertionHelperStaticBoundaryError,NativeLuaCClosurePublicationError,NativeLuaDirectCallError,NativeLuaPropertyFactoryChainError,OSError,UnicodeError,json.JSONDecodeError) as exc: print(f"error: {exc}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
