"""Upstream Lua 5.1.5 reference experiment for filtered assignment requests."""

from __future__ import annotations
import hashlib
from src.observatory import lua51_marker_reference as runtime
from src.observatory.native_assertion_helper_fill_conformance import (
    _canonical_sha256,
    _canonical_bytes,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "lua51_filtered_assignment_reference_conformance"
SEALED_SHA256 = "7d82034b09049dd4eefa96cb02f004dfc15661e8572d4a2267ec4e0473185b35"
MASKS = [0, 1, 2, 4, 7, 255]
MODES = ["direct_table", "redirect_table", "callback_userdata", "error_userdata"]


class AssignmentReferenceError(RuntimeError):
    pass


def _require(ok, message):
    if not ok:
        raise AssignmentReferenceError(message)


def probe_source():
    return r"""/* Independent Lua API experiment, with no game code or DLL. */
#include <stdio.h>
#include <string.h>
#include "lua.h"
#include "lauxlib.h"
static int before_top, after_top, prefix_ok, requests, callbacks, eq_calls;
static int equal_key(lua_State *L) { ++eq_calls;lua_pushboolean(L,1);return 1; }
static int record(lua_State *L) {
  ++callbacks;
  lua_pushvalue(L,lua_upvalueindex(1));lua_pushvalue(L,2);lua_pushvalue(L,3);
  lua_rawset(L,-3);return 0;
}
static int fail(lua_State *L) { ++callbacks;return luaL_error(L,"assignment sentinel"); }
static int reserved(lua_State *L,int index) {
  const char *s;
  size_t length;
  if(lua_type(L,index)!=LUA_TSTRING)return 0;
  s=lua_tolstring(L,index,&length);
  return (length==6 && memcmp(s,"__init",6)==0) || (length==10 && memcmp(s,"__finalize",10)==0);
}
static int experiment(lua_State *L) {
  const void *d=lua_topointer(L,-2),*s=lua_topointer(L,-1);
  before_top=lua_gettop(L);
  lua_pushnil(L);
  while(lua_next(L,-2)) {
    lua_pushliteral(L,"__init");
    if(lua_equal(L,-1,-3)) { lua_settop(L,-3);continue; }
    lua_settop(L,-2);lua_pushliteral(L,"__finalize");
    if(lua_equal(L,-1,-3)) { lua_settop(L,-3);continue; }
    lua_settop(L,-2);lua_pushvalue(L,-2);lua_insert(L,-2);
    ++requests;lua_settable(L,-5);
  }
  after_top=lua_gettop(L);
  prefix_ok=before_top==after_top && lua_topointer(L,-2)==d && lua_topointer(L,-1)==s;
  if(before_top==4)prefix_ok=prefix_ok && lua_tonumber(L,1)==17 && strcmp(lua_tostring(L,2),"tail")==0;
  lua_pushboolean(L,1);return 1;
}
static void push_key(lua_State *L,int kind) {
  if(kind==0)lua_pushliteral(L,"__init");
  else if(kind==1)lua_pushliteral(L,"__finalize");
  else if(kind==2)lua_pushliteral(L,"keep");
  else if(kind==3)lua_pushnumber(L,0);
  else if(kind==4)lua_pushliteral(L,"");
  else if(kind==5) {
    lua_newuserdata(L,1);lua_newtable(L);lua_pushcfunction(L,equal_key);
    lua_setfield(L,-2,"__eq");lua_setmetatable(L,-2);
  }
  else if(kind==6)lua_pushboolean(L,0);
  else lua_pushlstring(L,"__init\0extra",12);
}
int main(void) {
  int mode,pattern,prefix,kind,masks[]={0,1,2,4,7,255};
  printf("version %s\n",LUA_RELEASE);printf("pointer %u\n",(unsigned)sizeof(void*));
  for(mode=0;mode<4;++mode)for(pattern=0;pattern<6;++pattern)for(prefix=0;prefix<2;++prefix) {
    int rref,sref,status,match,count=0;
    lua_State *L=luaL_newstate();if(!L)return 2;
    before_top=-1;after_top=-1;prefix_ok=0;requests=0;callbacks=0;eq_calls=0;
    lua_newtable(L);rref=luaL_ref(L,LUA_REGISTRYINDEX);
    lua_newtable(L);
    for(kind=0;kind<8;++kind)if(masks[pattern]&(1<<kind)) {
      push_key(L,kind);lua_pushnumber(L,(kind+1)*10);lua_rawset(L,-3);
    }
    lua_pushvalue(L,-1);sref=luaL_ref(L,LUA_REGISTRYINDEX);lua_pop(L,1);
    if(prefix){lua_pushnumber(L,17);lua_pushliteral(L,"tail");}
    if(mode==0)lua_rawgeti(L,LUA_REGISTRYINDEX,rref);
    else {
      if(mode==1)lua_newtable(L);else lua_newuserdata(L,1);
      lua_newtable(L);
      if(mode==1)lua_rawgeti(L,LUA_REGISTRYINDEX,rref);
      else if(mode==2){lua_rawgeti(L,LUA_REGISTRYINDEX,rref);lua_pushcclosure(L,record,1);}
      else lua_pushcfunction(L,fail);
      lua_setfield(L,-2,"__newindex");lua_setmetatable(L,-2);
    }
    lua_rawgeti(L,LUA_REGISTRYINDEX,sref);
    lua_pushcfunction(L,experiment);lua_insert(L,1);
    status=lua_pcall(L,2+prefix*2,1,0);
    match=status?-1:1;
    if(!status) {
      lua_rawgeti(L,LUA_REGISTRYINDEX,rref);lua_rawgeti(L,LUA_REGISTRYINDEX,sref);lua_pushnil(L);
      while(lua_next(L,-2)) {
        int skip=reserved(L,-2);
        lua_pushvalue(L,-2);lua_rawget(L,-5);
        if(skip ? !lua_isnil(L,-1) : !lua_rawequal(L,-1,-2))match=0;
        lua_pop(L,2);
      }
      lua_pop(L,1);lua_pushnil(L);
      while(lua_next(L,-2)){++count;lua_pop(L,1);}
      lua_pop(L,1);
    }
    printf("case %d %d %d %d %d %d %d %d %d %d %d %d\n",mode,pattern,prefix,status,requests,callbacks,before_top,after_top,prefix_ok,eq_calls,match,count);
    lua_close(L);
  }
  return 0;
}
"""


def expected_rows():
    rows = []
    for mode in range(4):
        for pattern, mask in enumerate(MASKS):
            total = (mask & ~3).bit_count()
            for prefix in range(2):
                error = mode == 3 and total > 0
                rows.append(
                    [
                        mode,
                        pattern,
                        prefix,
                        2 if error else 0,
                        1 if error else total,
                        1 if error else total if mode == 2 else 0,
                        2 + 2 * prefix,
                        -1 if error else 2 + 2 * prefix,
                        0 if error else 1,
                        0,
                        -1 if error else 1,
                        0 if error else total,
                    ]
                )
    return rows


def parse_probe(text):
    lines = text.splitlines()
    _require(
        lines[:2] == ["version Lua 5.1.5", "pointer 4"], "reference version differs"
    )
    rows = []
    for line in lines[2:]:
        parts = line.split()
        _require(len(parts) == 13 and parts[0] == "case", "case shape differs")
        try:
            rows.append([int(s) for s in parts[1:]])
        except ValueError as exc:
            raise AssignmentReferenceError("invalid integer") from exc
    _require(
        rows == expected_rows(), "filtered assignment reference differs from oracle"
    )
    return rows


def _build_unsealed(archive):
    measured = runtime._measure(
        archive, source_text=probe_source(), parse_output=parse_probe
    )
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        upstream_archive_sha256=runtime.ARCHIVE_SHA256,
        configuration=dict(
            architecture="x86",
            pointer_bytes=4,
            msvc_version=runtime.sdk.MSVC_VERSION,
            sdk_version=runtime.sdk.SDK_VERSION,
            game_dll_loaded=False,
        ),
        modes=MODES,
        source_masks=MASKS,
        key_classes=[
            "init",
            "finalize",
            "ordinary_string",
            "zero_number",
            "empty_string",
            "userdata_with_equal_handler",
            "false_boolean",
            "embedded_nul_string",
        ],
        columns=[
            "mode",
            "source_pattern",
            "prefix_pair",
            "pcall_status",
            "assignment_requests",
            "newindex_calls",
            "before_top",
            "after_top",
            "prefix_ok",
            "key_equal_calls",
            "destination_match",
            "destination_entries",
        ],
        experiment=measured,
        summary=dict(
            cases=48,
            normal_returns=42,
            protected_errors=6,
            game_code_executions=0,
            native_helper_executions=0,
        ),
        scope=dict(
            claim="Finite official Lua 5.1.5 filtered assignment API experiment",
            not_claimed=[
                "Installed Lua DLL equivalence",
                "Native helper execution",
                "Arbitrary iteration order or source mutation termination",
                "Raw writes to destination under metamethods",
                "Normal helper cleanup after errors",
                "Whole-game accounting promotion",
            ],
        ),
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence):
    _validate_json_tree(evidence, "evidence")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256,
        "sealed assignment reference differs",
    )
    _require(
        evidence["experiment"]["rows"] == expected_rows()
        and evidence["experiment"]["probe_source_sha256"]
        == hashlib.sha256(probe_source().encode("ascii")).hexdigest(),
        "probe or oracle differs",
    )
    return dict(
        status="structurally_verified",
        evidence_sha256=SEALED_SHA256,
        summary=evidence["summary"],
    )


def build_reference(archive):
    result = _build_unsealed(archive)
    validate_structure(result)
    return result


def validate_reference(archive, evidence):
    validate_structure(evidence)
    _require(
        _canonical_bytes(build_reference(archive)) == _canonical_bytes(evidence),
        "reference rebuild differs",
    )
    return dict(
        status="verified", evidence_sha256=SEALED_SHA256, summary=evidence["summary"]
    )


encode_reference = runtime.encode_reference
