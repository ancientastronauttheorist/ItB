"""Independent Lua 5.1.5 API reference probe for metatable-marker lookup."""

from __future__ import annotations
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
from pathlib import Path
from src.observatory import windows_exception_layout as sdk
from src.observatory.native_assertion_helper_fill_conformance import (
    _canonical_bytes,
    _canonical_sha256,
    _validate_json_tree,
    _assert_publication_safe,
)

ANALYSIS_KIND = "lua51_marker_reference_conformance"
SEALED_SHA256 = "e6212ef1dc1f91861a894dfafca844607c8e4a2aecf9e95dd4fea8c565ef9a34"
ARCHIVE_SHA256 = "2640fc56a795f29d28ef15e13c34a47e223960b0240e8cb0a82d9b0738695333"
MODES = ["no_metatable", "direct", "index_table", "index_function", "index_error"]
VALUES = ["nil", "false", "true", "zero", "empty_string", "table", "function"]


class ReferenceError(RuntimeError):
    pass


def _require(condition, message):
    if not condition:
        raise ReferenceError(message)


def probe_source():
    return r"""/* Independently authored API experiment; no game code is linked. */
#include <stdio.h>
#include <string.h>
#include "lua.h"
#include "lauxlib.h"
static int index_arg, calls, before_count, after_count, prefix_ok;
static int inert(lua_State *L) { (void)L; return 0; }
static int indexed(lua_State *L) {
  ++calls;
  lua_pushvalue(L, lua_upvalueindex(1));
  return 1;
}
static int errored(lua_State *L) { ++calls; return luaL_error(L,"reference sentinel"); }
static void value(lua_State *L, int kind) {
  switch(kind) {
  case 0: lua_pushnil(L); break;
  case 1: lua_pushboolean(L,0); break;
  case 2: lua_pushboolean(L,1); break;
  case 3: lua_pushnumber(L,0); break;
  case 4: lua_pushliteral(L,""); break;
  case 5: lua_newtable(L); break;
  default: lua_pushcfunction(L,inert); break;
  }
}
static int experiment(lua_State *L) {
  int result=0;
  const void *subject=lua_topointer(L,2);
  before_count=lua_gettop(L);
  if(lua_getmetatable(L,index_arg)) {
    lua_pushliteral(L,"__luabind_classrep");
    lua_gettable(L,-2);
    result=lua_toboolean(L,-1);
    lua_settop(L,-3);
  }
  after_count=lua_gettop(L);
  prefix_ok=after_count==3 && lua_tonumber(L,1)==17 &&
    lua_topointer(L,2)==subject && lua_type(L,3)==LUA_TSTRING &&
    strcmp(lua_tostring(L,3),"tail")==0;
  lua_pushboolean(L,result);
  return 1;
}
int main(void) {
  int mode,kind,negative;
  printf("version %s\n",LUA_RELEASE);
  printf("pointer %u\n",(unsigned)sizeof(void*));
  for(mode=0;mode<5;++mode) for(kind=0;kind<7;++kind) for(negative=0;negative<2;++negative) {
    int status,result;
    lua_State *L=luaL_newstate();
    if(!L)return 2;
    calls=0;before_count=-1;after_count=-1;prefix_ok=0;
    index_arg=negative?-2:2;
    lua_pushnumber(L,17);lua_newtable(L);lua_pushliteral(L,"tail");
    if(mode) {
      lua_newtable(L); /* T, the subject's metatable */
      if(mode==1) { value(L,kind);lua_setfield(L,-2,"__luabind_classrep"); }
      else {
        lua_newtable(L); /* M, the metatable of T */
        if(mode==2) {
          lua_newtable(L);value(L,kind);lua_setfield(L,-2,"__luabind_classrep");
        } else if(mode==3) { value(L,kind);lua_pushcclosure(L,indexed,1); }
        else lua_pushcfunction(L,errored);
        lua_setfield(L,-2,"__index");lua_setmetatable(L,-2);
      }
      lua_setmetatable(L,2);
    }
    lua_pushcfunction(L,experiment);lua_insert(L,1);
    status=lua_pcall(L,3,1,0);
    result=status?-1:lua_toboolean(L,-1);
    printf("case %d %d %d %d %d %d %d %d %d %d\n",mode,kind,negative,status,result,before_count,after_count,prefix_ok,calls,lua_gettop(L));
    lua_close(L);
  }
  return 0;
}
"""


def expected_rows():
    result = []
    for mode in range(5):
        for kind in range(7):
            for negative in range(2):
                error = mode == 4
                result.append(
                    [
                        mode,
                        kind,
                        negative,
                        2 if error else 0,
                        -1 if error else int(mode != 0 and kind >= 2),
                        3,
                        -1 if error else 3,
                        0 if error else 1,
                        int(mode in (3, 4)),
                        1,
                    ]
                )
    return result


def parse_probe(text):
    _require(type(text) is str, "probe output requires text")
    lines = text.splitlines()
    _require(
        lines[:2] == ["version Lua 5.1.5", "pointer 4"],
        "reference configuration differs",
    )
    rows = []
    for line in lines[2:]:
        fields = line.split()
        _require(len(fields) == 11 and fields[0] == "case", "probe record differs")
        try:
            row = [int(s) for s in fields[1:]]
        except ValueError as exc:
            raise ReferenceError("probe integer differs") from exc
        rows.append(row)
    _require(
        rows == expected_rows(), "reference API results differ from independent oracle"
    )
    return rows


def _measure(archive: Path, *, source_text=None, parse_output=None):
    _require(os.name == "nt", "fixed reference build requires Windows")
    payload = archive.read_bytes()
    _require(
        len(payload) == 221213
        and hashlib.sha256(payload).hexdigest() == ARCHIVE_SHA256,
        "official source archive differs",
    )
    before = sdk._pinned_files()
    root = Path(__file__).resolve().parents[2] / ".local_decompile/lua51_reference"
    root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="probe-", dir=root)).resolve()
    source_dir = work / "src"
    source_dir.mkdir()
    source_manifest = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tf:
        selected = [
            m
            for m in tf.getmembers()
            if m.name.startswith("lua-5.1.5/src/") and m.name.endswith((".c", ".h"))
        ]
        for member in sorted(selected, key=lambda m: m.name):
            parts = member.name.split("/")
            _require(
                member.isfile()
                and len(parts) == 3
                and parts[:2] == ["lua-5.1.5", "src"]
                and "\\" not in parts[2]
                and ":" not in parts[2],
                "source member path differs",
            )
            contents = tf.extractfile(member).read()
            with (source_dir / parts[2]).open("xb") as f:
                f.write(contents)
            source_manifest.append(
                dict(
                    name=parts[2],
                    sha256=hashlib.sha256(contents).hexdigest(),
                    size=len(contents),
                )
            )
    _require(len(source_manifest) > 40, "source manifest incomplete")
    source = probe_source() if source_text is None else source_text
    (work / "probe.c").write_bytes(source.encode("ascii"))
    env = dict(os.environ)
    for key in list(env):
        if key.upper() in {"CL", "_CL_", "LINK", "_LINK_", "INCLUDE", "LIB", "LIBPATH"}:
            del env[key]
    env["PATH"] = (
        str(sdk.BIN) + os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")
    )
    env["VSLANG"] = "1033"
    env["LIB"] = os.pathsep.join(
        str(p)
        for p in [
            sdk.MSVC / "lib/x86",
            sdk.SDK / "Lib" / sdk.SDK_VERSION / "ucrt/x86",
            sdk.SDK / "Lib" / sdk.SDK_VERSION / "um/x86",
        ]
    )
    includes = [source_dir, sdk.MSVC / "include"] + [
        sdk.SDK / "Include" / sdk.SDK_VERSION / n
        for n in ("ucrt", "shared", "um", "winrt")
    ]
    command = [
        str(sdk.BIN / "cl.exe"),
        "/nologo",
        "/X",
        "/showIncludes",
        "/MT",
        "/TC",
        "/D_CRT_SECURE_NO_WARNINGS",
        "/Fe:probe.exe",
    ]
    for path in includes:
        command += ["/I", str(path)]
    compiled_names = [
        r["name"]
        for r in source_manifest
        if r["name"].endswith(".c") and r["name"] not in ("lua.c", "luac.c", "print.c")
    ]
    command += [str(source_dir / n) for n in compiled_names] + [
        "probe.c",
        "/link",
        "/MACHINE:X86",
    ]
    built = subprocess.run(command, cwd=work, env=env, capture_output=True, timeout=60)
    (work / "compile.stdout").write_bytes(built.stdout)
    (work / "compile.stderr").write_bytes(built.stderr)
    _require(built.returncode == 0, "reference compile failed; private logs retained")
    paths = set()
    for line in (
        (built.stdout + built.stderr).decode("utf-8", errors="replace").splitlines()
    ):
        if line.startswith("Note: including file:"):
            paths.add(Path(line.split("Note: including file:", 1)[1].strip()).resolve())
    closure = []
    for path in paths:
        labels = [
            (name, base.resolve())
            for name, base in [
                ("lua", source_dir),
                ("msvc", sdk.MSVC / "include"),
                ("sdk", sdk.SDK / "Include" / sdk.SDK_VERSION),
            ]
            if path.is_relative_to(base.resolve())
        ]
        _require(len(labels) == 1, "header outside fixed roots")
        name, base = labels[0]
        closure.append(
            dict(
                root=name,
                components=list(path.relative_to(base).parts),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    closure.sort(key=lambda r: (r["root"], r["components"]))
    _require(
        any(r["root"] == "lua" and r["components"] == ["lua.h"] for r in closure),
        "Lua header was not measured",
    )
    ran = subprocess.run(
        [str(work / "probe.exe")], cwd=work, env=env, capture_output=True, timeout=15
    )
    (work / "probe.stdout").write_bytes(ran.stdout)
    (work / "probe.stderr").write_bytes(ran.stderr)
    _require(ran.returncode == 0 and not ran.stderr, "reference experiment failed")
    rows = (parse_probe if parse_output is None else parse_output)(
        ran.stdout.decode("ascii")
    )
    _require(
        all(
            hashlib.sha256((source_dir / r["name"]).read_bytes()).hexdigest()
            == r["sha256"]
            for r in source_manifest
        )
        and (work / "probe.c").read_bytes() == source.encode("ascii"),
        "compiled source changed during reference probe",
    )
    _require(
        sdk._pinned_files() == before and archive.read_bytes() == payload,
        "inputs changed during reference probe",
    )
    return dict(
        source_manifest=source_manifest,
        compiled_sources=compiled_names,
        include_closure=closure,
        toolchain_sha256=before,
        probe_source_sha256=hashlib.sha256(source.encode("ascii")).hexdigest(),
        rows=rows,
    )


def _build_unsealed(archive):
    measured = _measure(archive)
    result = dict(
        schema_version=1,
        analysis_kind=ANALYSIS_KIND,
        source=dict(
            host="www.lua.org",
            archive_components=["ftp", "lua-5.1.5.tar.gz"],
            sha256=ARCHIVE_SHA256,
            bytes=221213,
            version="5.1.5",
        ),
        configuration=dict(
            architecture="x86",
            pointer_bytes=4,
            msvc_version=sdk.MSVC_VERSION,
            sdk_version=sdk.SDK_VERSION,
            linking="static Lua reference sources and static C runtime",
            game_dll_loaded=False,
        ),
        experiment=measured,
        modes=MODES,
        values=VALUES,
        columns=[
            "mode",
            "value",
            "negative_index",
            "pcall_status",
            "result",
            "before_top",
            "after_top",
            "prefix_ok",
            "metamethod_calls",
            "protected_call_top",
        ],
        summary=dict(
            cases=70,
            normal_returns=56,
            protected_errors=14,
            metamethod_function_calls=28,
            game_code_executions=0,
            native_helper_executions=0,
        ),
        scope=dict(
            claim="Reference Lua 5.1.5 API sequence and protected-error behavior on the declared finite domain",
            not_claimed=[
                "Identity or equivalence of the installed Lua DLL",
                "Native helper instruction execution or EAX upper bits",
                "Heap or global preservation under arbitrary metamethods",
                "Normal helper cleanup on an error path",
                "Whole-game conformance or accounting promotion",
            ],
        ),
    )
    _assert_publication_safe(result)
    return result


def validate_structure(evidence):
    _validate_json_tree(evidence, "evidence")
    _require(
        _canonical_sha256(evidence) == SEALED_SHA256, "sealed reference receipt differs"
    )
    _require(
        evidence["experiment"]["rows"] == expected_rows()
        and evidence["experiment"]["probe_source_sha256"]
        == hashlib.sha256(probe_source().encode("ascii")).hexdigest(),
        "reference oracle or probe differs",
    )
    _assert_publication_safe(evidence)
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


def encode_reference(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    )
