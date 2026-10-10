// Binding C++ weapon ports to weapon tables (weapon_ports.hpp).

#include "weapon_ports.hpp"

#include <fstream>

#include "lua_host_detail.hpp"
#include "lua_native.hpp"

extern "C" {
#include "lauxlib.h"
#include "lua.h"
}

namespace itb::lua {

uint64_t fnv1a(std::string_view s, uint64_t h) {
  for (unsigned char c : s) {
    h ^= c;
    h *= 0x100000001b3ull;
  }
  return h;
}

bool FieldValue::truthy() const { return !(type == LUA_TNIL || (type == LUA_TBOOLEAN && !b)); }

bool FieldValue::equals(double v) const { return type == LUA_TNUMBER && n == v; }

int32_t FieldValue::as_int() const { return native::to_int(n); }

void PortContext::log(const std::string& s) {
  // global.lua LOG: output = tostring(v) .. "    " per argument, then
  // ConsolePrint(output) and print(output).
  const std::string line = s + "    ";
  console.push_back(line);
  console.push_back(line);
}

namespace {

// The game's CallMethod (global.lua): every native -> Lua call goes through
// it; the ports assume it dispatches to _G[obj][func](_G[obj], ...).
constexpr DepSpec kCallMethod{DepSpec::Global, "CallMethod", "global.lua", 526, 0x445a7dbe0887860bull};

}  // namespace

LuaFunctionId WeaponPortTable::identify(lua_State* L) {
  LuaFunctionId id;
  if (!lua_isfunction(L, -1) || lua_iscfunction(L, -1)) return id;
  lua_Debug ar;
  lua_pushvalue(L, -1);
  if (!lua_getinfo(L, ">S", &ar) || !ar.source || ar.source[0] != '@') return id;
  const std::string source(ar.source + 1);
  const size_t at = source.rfind("scripts/");
  if (at == std::string::npos) return id;
  id.file = source.substr(at + 8);
  id.line = ar.linedefined;
  id.last_line = ar.lastlinedefined;
  bool ok = false;
  id.hash = hash_lines(source, ar.linedefined, ar.lastlinedefined, &ok);
  if (!ok) id.file.clear();
  return id;
}

uint64_t WeaponPortTable::hash_lines(const std::string& path, int first, int last, bool* ok) {
  auto it = files_.find(path);
  if (it == files_.end()) {
    std::vector<std::string> lines;
    std::ifstream in(path, std::ios::binary);
    std::string line;
    while (std::getline(in, line)) lines.push_back(line);
    it = files_.emplace(path, std::move(lines)).first;
  }
  const std::vector<std::string>& lines = it->second;
  *ok = first >= 1 && last >= first && static_cast<size_t>(last) <= lines.size();
  if (!*ok) return 0;
  uint64_t h = fnv1a("");
  for (int i = first; i <= last; ++i) {
    h = fnv1a(lines[static_cast<size_t>(i - 1)], h);
    h = fnv1a("\n", h);
  }
  return h;
}

LuaFunctionId WeaponPortTable::function_of(lua_State* L, std::string_view weapon, const char* method) {
  const int top = lua_gettop(L);
  LuaFunctionId id;
  lua_getglobal(L, std::string(weapon).c_str());
  if (lua_istable(L, -1)) {
    lua_getfield(L, -1, method);
    id = identify(L);
  }
  lua_settop(L, top);
  return id;
}

const PortSpec* WeaponPortTable::bind(lua_State* L, std::string_view weapon, const char* method, Fields& fields,
                                      std::string* why) {
  auto fail = [&](std::string w) -> const PortSpec* {
    if (why) *why = std::move(w);
    return nullptr;
  };
  // CallMethod sends names containing "Mission" to the mission first.
  if (weapon.find("Mission") != std::string_view::npos) return fail("a mission name");
  const int top = lua_gettop(L);
  struct Restore {
    lua_State* L;
    int top;
    ~Restore() { lua_settop(L, top); }
  } restore{L, top};

  lua_getglobal(L, kCallMethod.name);
  const LuaFunctionId call = identify(L);
  lua_pop(L, 1);
  if (call.file != kCallMethod.file || call.line != kCallMethod.line || call.hash != kCallMethod.hash) {
    return fail("CallMethod is not the one the ports assume");
  }
  if (!dir_vectors_ok(L)) return fail("DIR_VECTORS is not the one the ports assume");

  lua_getglobal(L, std::string(weapon).c_str());
  if (!lua_istable(L, -1)) return fail("no such table");
  const int table = lua_gettop(L);
  lua_getfield(L, table, method);
  const LuaFunctionId id = identify(L);
  lua_pop(L, 1);
  if (id.file.empty()) return fail("not a Lua function from a script");
  const PortSpec* spec = nullptr;
  for (const PortSpec& s : port_specs()) {
    if (id.file == s.file && id.line == s.line && std::string_view(method) == s.method) spec = &s;
  }
  if (!spec) return fail("no port for " + id.key());
  if (spec->hash != id.hash) return fail("source of " + id.key() + " differs from the ported one");
  for (const DepSpec& d : spec->deps) {
    if (d.where == DepSpec::Global) {
      lua_getglobal(L, d.name);
    } else {
      lua_getfield(L, table, d.name);
    }
    const LuaFunctionId dep = identify(L);
    lua_pop(L, 1);
    if (dep.file != d.file || dep.line != d.line || dep.hash != d.hash) {
      return fail(std::string("helper ") + d.name + " differs from the ported one");
    }
  }
  Fields values;
  for (const FieldSpec& f : spec->fields) {
    lua_getfield(L, table, f.name);
    FieldValue v;
    v.type = lua_type(L, -1);
    switch (v.type) {
      case LUA_TBOOLEAN:
        v.b = lua_toboolean(L, -1) != 0;
        break;
      case LUA_TNUMBER:
        v.n = lua_tonumber(L, -1);
        break;
      case LUA_TSTRING: {
        size_t len = 0;
        const char* s = lua_tolstring(L, -1, &len);
        v.s.assign(s, len);
        break;
      }
      case LUA_TNIL:
        break;
      default:
        v.type = -1;  // tables, functions, ...: not modelled
        break;
    }
    lua_pop(L, 1);
    const bool ok = f.kind == FieldKind::Num    ? v.type == LUA_TNUMBER
                    : f.kind == FieldKind::Str  ? v.type == LUA_TSTRING
                    : f.kind == FieldKind::Bool ? v.type == LUA_TBOOLEAN
                                                : v.type != -1;
    if (!ok) return fail(std::string("field ") + f.name + " has another type");
    values.push_back(std::move(v));
  }
  fields = std::move(values);
  return spec;
}

// The ports use kDirVectors for DIR_VECTORS[0..3], and nil beyond.
bool WeaponPortTable::dir_vectors_ok(lua_State* L) {
  if (dir_vectors_ok_ >= 0) return dir_vectors_ok_ == 1;
  bool ok = true;
  lua_getglobal(L, "DIR_VECTORS");
  if (!lua_istable(L, -1)) ok = false;
  for (int i = 0; ok && i <= 4; ++i) {
    lua_rawgeti(L, -1, i);
    if (i == 4) {
      ok = lua_isnil(L, -1);
    } else {
      Instance* in = to_instance(L, -1, Cls::Point);
      ok = in && *static_cast<Point*>(resolve(in)) == kDirVectors[static_cast<size_t>(i)];
    }
    lua_pop(L, 1);
  }
  lua_pop(L, 1);
  dir_vectors_ok_ = ok ? 1 : 0;
  return ok;
}

const WeaponPort* WeaponPortTable::find(lua_State* L, std::string_view weapon) {
  const std::string key(weapon);
  auto it = cache_.find(key);
  if (it == cache_.end()) {
    auto wp = std::make_unique<WeaponPort>();
    wp->area = bind(L, weapon, "GetTargetArea", wp->area_fields, nullptr);
    wp->effect = bind(L, weapon, "GetSkillEffect", wp->effect_fields, nullptr);
    if (!wp->area && !wp->effect) wp.reset();
    it = cache_.emplace(key, std::move(wp)).first;
  }
  return it->second.get();
}

std::string WeaponPortTable::why_not(lua_State* L, std::string_view weapon, const char* method) {
  Fields fields;
  std::string why;
  return bind(L, weapon, method, fields, &why) ? std::string() : why;
}

}  // namespace itb::lua
