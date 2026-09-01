#!/usr/bin/env python3
"""Build or verify the exact five-record native Lua ``__gc`` census."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

_ROOT=Path(__file__).resolve().parents[1]; _OUT=_ROOT/"data"/"observatory"/"programs"
sys.path.insert(0,str(_ROOT))
from scripts.itb_native_lua_direct_calls import _is_reparse,_read_json_document,_read_json_object  # noqa:E402
from src.observatory.native_lua_cclosure_gc_metatable_consumers import (  # noqa:E402
    ANALYSIS_KIND,SCHEMA_VERSION,NativeLuaCClosureGcMetatableConsumersError,_canonical_bytes,
    build_native_lua_cclosure_gc_metatable_consumers,encode_native_lua_cclosure_gc_metatable_consumers,
    validate_native_lua_cclosure_gc_metatable_consumers)

def build_parser():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest="command",required=True)
    for command in ("build","verify"):
        q=s.add_parser(command)
        q.add_argument("--executable",required=True,type=Path); q.add_argument("--inventory",required=True,type=Path); q.add_argument("--program-facts",required=True,type=Path); q.add_argument("--direct-calls",required=True,type=Path); q.add_argument("--callbacks",required=True,type=Path); q.add_argument("--setfield-publications",required=True,type=Path); q.add_argument("--direct-table-setter-publications",required=True,type=Path); q.add_argument("--indirect-settable-publications",required=True,type=Path); q.add_argument("--table-key-provenance",required=True,type=Path)
        q.add_argument("--output",type=Path) if command=="build" else q.add_argument("--evidence",required=True,type=Path)
    return p

def _output_root():
    root=_ROOT.resolve(strict=True); out=_OUT
    for part in ("data","observatory","programs"):
        part_path=root/part if part=="data" else out if part=="programs" else root/"data"/"observatory"
        part_path.mkdir(exist_ok=True)
    info=out.lstat()
    if stat.S_ISLNK(info.st_mode) or _is_reparse(info) or not stat.S_ISDIR(info.st_mode): raise NativeLuaCClosureGcMetatableConsumersError("output root is not a real directory")
    return out.resolve(strict=True)

def _identity(v):
    if not isinstance(v,dict) or v.get("schema_version")!=SCHEMA_VERSION or v.get("analysis_kind")!=ANALYSIS_KIND: raise NativeLuaCClosureGcMetatableConsumersError("artifact identity differs")
    return _canonical_bytes({"schema_version":v["schema_version"],"analysis_kind":v["analysis_kind"],"build_identity":v.get("build_identity"),"sources":[v.get(x) for x in ("atlas","direct_call_census","callback_census","setfield_publication_census","direct_table_setter_publication_census","indirect_settable_publication_census","table_key_provenance_census")]})

def _write(output,rendered,result):
    root=_output_root(); requested=Path(os.path.abspath(output))
    if requested.parent != root: raise NativeLuaCClosureGcMetatableConsumersError("output must be a direct programs child")
    dest=root/output.name
    if os.path.lexists(dest):
        before=dest.lstat()
        if stat.S_ISLNK(before.st_mode) or _is_reparse(dest) or not stat.S_ISREG(before.st_mode) or dest.resolve(strict=True).parent!=root:
            raise NativeLuaCClosureGcMetatableConsumersError("existing output is not a real programs file")
        old,payload=_read_json_document(dest,"existing output")
        after=dest.lstat()
        if stat.S_ISLNK(after.st_mode) or _is_reparse(dest) or not stat.S_ISREG(after.st_mode) or dest.resolve(strict=True).parent!=root or (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
            raise NativeLuaCClosureGcMetatableConsumersError("existing output changed during validation")
        if _identity(old)!=_identity(result) or _canonical_bytes(old)!=_canonical_bytes(result) or payload!=rendered.encode(): raise NativeLuaCClosureGcMetatableConsumersError("refusing to overwrite differing evidence")
        return
    fd,tmp=tempfile.mkstemp(prefix=f".{output.name}.",suffix=".tmp",dir=root)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as f: f.write(rendered); f.flush(); os.fsync(f.fileno())
        os.link(tmp,dest)
        created=dest.lstat(); source=Path(tmp).lstat()
        if stat.S_ISLNK(created.st_mode) or _is_reparse(dest) or not stat.S_ISREG(created.st_mode) or dest.resolve(strict=True).parent!=root or (created.st_dev,created.st_ino)!=(source.st_dev,source.st_ino):
            if (created.st_dev,created.st_ino)==(source.st_dev,source.st_ino): dest.unlink()
            raise NativeLuaCClosureGcMetatableConsumersError("created output failed the regular-file identity check")
        os.unlink(tmp)
    except Exception:
        try: os.unlink(tmp)
        except FileNotFoundError: pass
        raise

def main(argv=None):
    a=build_parser().parse_args(argv)
    try:
        inventory=_read_json_object(a.inventory,"inventory"); facts=_read_json_object(a.program_facts,"program facts"); direct=_read_json_object(a.direct_calls,"direct calls"); callbacks=_read_json_object(a.callbacks,"callbacks"); setfield=_read_json_object(a.setfield_publications,"setfield publications"); direct_setters=_read_json_object(a.direct_table_setter_publications,"direct setters"); indirect=_read_json_object(a.indirect_settable_publications,"indirect setters"); keys=_read_json_object(a.table_key_provenance,"table-key provenance")
        common=(a.executable,direct,callbacks,setfield,direct_setters,indirect,keys,facts)
        if a.command=="build":
            r=build_native_lua_cclosure_gc_metatable_consumers(*common,inventory=inventory); out=encode_native_lua_cclosure_gc_metatable_consumers(r)
            if a.output: _write(a.output,out,r)
            else: sys.stdout.write(out)
        else:
            evidence,payload=_read_json_document(a.evidence,"evidence")
            if payload!=encode_native_lua_cclosure_gc_metatable_consumers(evidence).encode(): raise NativeLuaCClosureGcMetatableConsumersError("evidence is not deterministically encoded")
            sys.stdout.write(encode_native_lua_cclosure_gc_metatable_consumers(validate_native_lua_cclosure_gc_metatable_consumers(a.executable,evidence,direct,callbacks,setfield,direct_setters,indirect,keys,facts,inventory=inventory)))
        return 0
    except (NativeLuaCClosureGcMetatableConsumersError,OSError,UnicodeError,json.JSONDecodeError) as e:
        print(f"error: {e}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
