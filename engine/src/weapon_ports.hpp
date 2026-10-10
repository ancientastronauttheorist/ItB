// C++ ports of the game's hottest weapon scripts (internal).
//
// Lua stays the reference: a port mirrors one Lua function (GetTargetArea or
// GetSkillEffect of some Skill class) line by line on top of the same native
// bindings (lua_native.hpp) and must produce exactly what the Lua produces:
// the same points in the same order, the same SpaceDamage entries with every
// field, the same console output. It is used for a weapon table only when
//   - the table's method resolves (through inheritance) to a Lua function
//     whose source file, first line and source text (FNV-1a hash of its
//     lines) are the ones the port was written from,
//   - every other Lua function the port stands in for (a global helper such
//     as GetProjectileEnd, or a method called on self) matches the same way,
//   - every field the port reads from the table (`self.Damage`, ...) has the
//     Lua type the port expects (else the Lua could take another branch or
//     raise; the table keeps running in Lua).
// Fields are read once, when the port is bound to the table: weapon tables
// are static after loading. A port returns false for any input it does not
// reproduce exactly (typically where the Lua would raise an error); the
// call then runs in Lua. weapon_ports_list.cpp has the ports themselves.
#pragma once

#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

#include "itb/board.hpp"
#include "itb/lua_host.hpp"

struct lua_State;

namespace itb::lua {

// A field of a weapon table as Lua sees it (`self.Name`).
struct FieldValue {
  int type = 0;  // LUA_TNIL, LUA_TBOOLEAN, LUA_TNUMBER or LUA_TSTRING
  bool b = false;
  double n = 0;
  std::string s;

  // `if self.X then`: anything but nil and false.
  bool truthy() const;
  // `self.X == v` for a number v (false for any other type).
  bool equals(double v) const;
  // As an int parameter of a binding (the field is a number).
  int32_t as_int() const;
  float as_float() const { return static_cast<float>(n); }
};

// What a port reads: the board, the Lua `Pawn` global, and where its console
// output goes (kept until the port succeeds).
struct PortContext {
  const Board& board;
  const Pawn* pawn;  // the selected pawn; null when nil or not on the board
  lua_State* L;
  std::vector<std::string> console;

  // LOG(...) of one string: ConsolePrint and print of "<s>    ".
  void log(const std::string& s);
};

using Fields = std::vector<FieldValue>;
using AreaPort = bool (*)(PortContext& ctx, const Fields& self, Point origin, std::vector<Point>& out);
using EffectPort = bool (*)(PortContext& ctx, const Fields& self, Point p1, Point p2, LuaSkillEffect& out);

enum class FieldKind : uint8_t {
  Num,   // a number
  Str,   // a string
  Bool,  // a boolean
  Any,   // anything (only tested for truthiness or compared)
};

struct FieldSpec {
  const char* name;
  FieldKind kind;
};

// Another Lua function a port stands in for.
struct DepSpec {
  enum Where : uint8_t { Global, SelfMethod } where;
  const char* name;  // global name, or method name looked up on the table
  const char* file;  // source path relative to scripts/, e.g. "weapons_base.lua"
  int line;          // linedefined
  uint64_t hash;     // FNV-1a of its source lines
};

// One ported Lua function.
struct PortSpec {
  const char* method;  // "GetTargetArea" or "GetSkillEffect"
  const char* file;    // source path relative to scripts/
  int line;            // linedefined
  uint64_t hash;       // FNV-1a of its source lines (linedefined..lastlinedefined)
  std::vector<FieldSpec> fields;
  std::vector<DepSpec> deps;
  // The port may run Lua code (pawn-type lookups): the pending selection
  // is assigned first, as it is before any Lua code runs.
  bool runs_lua = false;
  AreaPort area = nullptr;
  EffectPort effect = nullptr;
};

// Every port (weapon_ports_list.cpp).
const std::vector<PortSpec>& port_specs();

// What applies to one weapon table.
struct WeaponPort {
  const PortSpec* area = nullptr;
  Fields area_fields;
  const PortSpec* effect = nullptr;
  Fields effect_fields;
};

// A Lua function's identity: where it is defined and a hash of its text.
struct LuaFunctionId {
  std::string file;  // relative to scripts/ ("" when not a Lua function from a file)
  int line = 0;
  int last_line = 0;
  uint64_t hash = 0;
  std::string key() const { return file + ":" + std::to_string(line); }
};

class WeaponPortTable {
 public:
  // The ports bound to `weapon` (resolved on first use), or null if none
  // applies.
  const WeaponPort* find(lua_State* L, std::string_view weapon);
  // Why `method` of `weapon` has no port ("" if it has one).
  std::string why_not(lua_State* L, std::string_view weapon, const char* method);
  // The function `method` of `weapon` resolves to (for reports).
  LuaFunctionId function_of(lua_State* L, std::string_view weapon, const char* method);

 private:
  // The function on top of the stack (not popped).
  LuaFunctionId identify(lua_State* L);
  uint64_t hash_lines(const std::string& path, int first, int last, bool* ok);
  const PortSpec* bind(lua_State* L, std::string_view weapon, const char* method, Fields& fields,
                       std::string* why);
  bool dir_vectors_ok(lua_State* L);
  int dir_vectors_ok_ = -1;  // -1: not checked yet

  std::unordered_map<std::string, std::unique_ptr<WeaponPort>> cache_;  // null: no port
  std::unordered_map<std::string, std::vector<std::string>> files_;     // source lines
};

uint64_t fnv1a(std::string_view s, uint64_t h = 0xcbf29ce484222325ull);

}  // namespace itb::lua
