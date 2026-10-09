// Value classes and runtime rules shared by the script loader and the Lua
// host. Semantics follow notes/stage6_lua_api_spec.md §3E (the game's luabind
// bindings); the implementation is ours.

#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "lua_host_detail.hpp"

extern "C" {
#include "lauxlib.h"
#include "lualib.h"
}

namespace itb::lua {

// ---- glibc rand() ---------------------------------------------------------

void GlibcRand::seed_now() {
  has_pending_ = false;
  uint32_t seed = pending_;
  if (seed == 0) seed = 1;
  // Park-Miller "minimal standard" fill, done with Schrage's split so no
  // intermediate overflows 31 bits (glibc keeps the running value as int32).
  int32_t word = static_cast<int32_t>(seed);
  state_[0] = word;
  for (int i = 1; i < 31; ++i) {
    const int64_t hi = word / 127773;
    const int64_t lo = word % 127773;
    int64_t next = 16807 * lo - 2836 * hi;
    if (next < 0) next += 2147483647;
    word = static_cast<int32_t>(next);
    state_[i] = word;
  }
  front_ = 3;
  rear_ = 0;
  const uint64_t draws = draws_;
  for (int i = 0; i < 310; ++i) next();  // glibc discards 10 * degree outputs
  draws_ = draws;
}

int32_t GlibcRand::next() {
  const uint32_t sum = static_cast<uint32_t>(state_[front_]) + static_cast<uint32_t>(state_[rear_]);
  state_[front_] = static_cast<int32_t>(sum);
  if (++front_ == 31) front_ = 0;
  if (++rear_ == 31) rear_ = 0;
  ++draws_;
  return static_cast<int32_t>(sum >> 1);
}

namespace {

// Registry keys (addresses are unique per process).
char kInstanceMtKey;
char kClassesKey;
char kEmptyEnvKey;
char kStateKey;
char kParentKey;

struct ValueState {
  GlibcRand rand;
};

Operators g_ops[static_cast<int>(Cls::Count)];

const char* const kClassNames[] = {"Point",      "SpaceDamage", "SkillEffect", "PointList",
                                   "IntList",    "DamageList",  "GL_Color",    "Objective",
                                   "Board",      "BoardPawn",   "GameMap",     "ValueBar",
                                   "PawnFactory"};

void push_registry(lua_State* L, void* key) {
  lua_pushlightuserdata(L, key);
  lua_rawget(L, LUA_REGISTRYINDEX);
}

}  // namespace

const char* class_name(Cls c) { return kClassNames[static_cast<int>(c)]; }

GlibcRand& rng(lua_State* L) {
  push_registry(L, &kStateKey);
  auto* st = static_cast<ValueState*>(lua_touserdata(L, -1));
  lua_pop(L, 1);
  if (!st) throw LuaError("value bindings not installed");
  return st->rand;
}

[[noreturn]] void no_overload(const char* candidates) {
  throw LuaError(std::string("No matching overload found, candidates:\n") + candidates);
}

void* resolve(const Instance* in) {
  switch (in->kind) {
    case Kind::Owned:
    case Kind::Ref:
      return in->ptr;
    case Kind::Element:
    case Kind::Member: {
      void* parent = resolve(in->parent);
      void* obj = parent ? in->project(parent, in->index) : nullptr;
      if (!obj) {
        throw LuaError(std::string("dangling ") + class_name(in->cls) +
                       " reference (index out of range)");
      }
      return obj;
    }
    case Kind::Pawn:
      break;
  }
  throw LuaError("internal: pawn instance used as a value");
}

Instance* to_instance(lua_State* L, int idx) {
  void* p = lua_touserdata(L, idx);
  if (!p || lua_islightuserdata(L, idx)) return nullptr;
  if (!lua_getmetatable(L, idx)) return nullptr;
  push_registry(L, &kInstanceMtKey);
  const bool ours = lua_rawequal(L, -1, -2) != 0;
  lua_pop(L, 2);
  return ours ? static_cast<Instance*>(p) : nullptr;
}

Instance* to_instance(lua_State* L, int idx, Cls cls) {
  Instance* in = to_instance(L, idx);
  return in && in->cls == cls ? in : nullptr;
}

void finish_instance(lua_State* L) {
  push_registry(L, &kInstanceMtKey);
  lua_setmetatable(L, -2);
  push_registry(L, &kEmptyEnvKey);
  lua_setfenv(L, -2);
}

Instance* new_owned(lua_State* L, Cls cls, size_t size, size_t align) {
  const size_t off = (sizeof(Instance) + align - 1) / align * align;
  void* mem = lua_newuserdata(L, off + size);
  auto* in = static_cast<Instance*>(mem);
  *in = Instance{cls, Kind::Owned, static_cast<char*>(mem) + off, nullptr, 0, nullptr, nullptr};
  finish_instance(L);
  return in;
}

void push_alias(lua_State* L, int parent_idx, Cls cls, Kind kind, uintptr_t index,
                void* (*project)(void*, uintptr_t)) {
  parent_idx = parent_idx < 0 ? lua_gettop(L) + parent_idx + 1 : parent_idx;
  Instance* parent = to_instance(L, parent_idx);
  auto* in = static_cast<Instance*>(lua_newuserdata(L, sizeof(Instance)));
  *in = Instance{cls, kind, nullptr, parent, index, project, nullptr};
  push_registry(L, &kInstanceMtKey);
  lua_setmetatable(L, -2);
  // The env table keeps the owner alive (luabind's dependency policy).
  lua_createtable(L, 0, 1);
  lua_pushlightuserdata(L, &kParentKey);
  lua_pushvalue(L, parent_idx);
  lua_rawset(L, -3);
  lua_setfenv(L, -2);
}

void push_ref(lua_State* L, Cls cls, void* obj) {
  auto* in = static_cast<Instance*>(lua_newuserdata(L, sizeof(Instance)));
  *in = Instance{cls, Kind::Ref, obj, nullptr, 0, nullptr, nullptr};
  finish_instance(L);
}

// ---- argument conversion ---------------------------------------------------

int32_t to_int(lua_State* L, int idx) {
  const double d = lua_tonumber(L, idx);
  // cvttsd2si to 64 bits returns 0x8000000000000000 for NaN/out of range,
  // whose low 32 bits are 0.
  if (!(d > -9223372036854775808.0 && d < 9223372036854775808.0)) return 0;
  const auto wide = static_cast<int64_t>(d);
  return static_cast<int32_t>(static_cast<uint32_t>(static_cast<uint64_t>(wide)));
}

std::string to_str(lua_State* L, int idx) {
  size_t len = 0;
  const char* s = lua_tolstring(L, idx, &len);
  return s ? std::string(s, len) : std::string();
}

bool match_one(lua_State* L, int i, A a) {
  switch (a) {
    case A::Int:
    case A::Num:
      return lua_type(L, i) == LUA_TNUMBER;
    case A::Bool:
      return lua_type(L, i) == LUA_TBOOLEAN;
    case A::Str:
      return lua_type(L, i) == LUA_TSTRING;
    case A::Point:
      return to_instance(L, i, Cls::Point) != nullptr;
    case A::SD:
      return to_instance(L, i, Cls::SpaceDamage) != nullptr;
    case A::SE:
      return to_instance(L, i, Cls::SkillEffect) != nullptr;
    case A::PL:
      return to_instance(L, i, Cls::PointList) != nullptr;
    case A::IL:
      return to_instance(L, i, Cls::IntList) != nullptr;
    case A::DL:
      return to_instance(L, i, Cls::DamageList) != nullptr;
    case A::Color:
      return to_instance(L, i, Cls::GLColor) != nullptr;
    case A::Objective:
      return to_instance(L, i, Cls::Objective) != nullptr;
    case A::Board:
      return to_instance(L, i, Cls::Board) != nullptr;
    case A::Pawn:
      return to_instance(L, i, Cls::BoardPawn) != nullptr;
    case A::PawnPtr:
      return lua_isnil(L, i) || to_instance(L, i, Cls::BoardPawn) != nullptr;
    case A::Game:
      return to_instance(L, i, Cls::GameMap) != nullptr;
    case A::ValueBar:
      return to_instance(L, i, Cls::ValueBar) != nullptr;
    case A::Factory:
      return to_instance(L, i, Cls::PawnFactory) != nullptr;
    case A::ClassTable:
      return lua_istable(L, i);
    case A::Any:
      return true;
  }
  return false;
}

bool match(lua_State* L, std::initializer_list<A> sig) {
  if (lua_gettop(L) != static_cast<int>(sig.size())) return false;
  int i = 1;
  for (A a : sig) {
    if (!match_one(L, i++, a)) return false;
  }
  return true;
}

Point& point_arg(lua_State* L, int idx) { return get<Point>(L, idx, Cls::Point); }

void push_point(lua_State* L, Point p) { push_owned(L, Cls::Point, p); }

void push_point_list(lua_State* L, std::vector<Point> list) {
  push_owned(L, Cls::PointList, std::move(list));
}

void push_int_list(lua_State* L, std::vector<int> list) {
  push_owned(L, Cls::IntList, std::move(list));
}

LuaSpaceDamage& sd_arg(lua_State* L, int idx) {
  return get<LuaSpaceDamage>(L, idx, Cls::SpaceDamage);
}

void push_skill_effect(lua_State* L, LuaSkillEffect se) {
  push_owned(L, Cls::SkillEffect, std::move(se));
}

std::string point_string(Point p) {
  return "Point( " + std::to_string(p.x) + ", " + std::to_string(p.y) + " )";
}

// ---- the shared instance metatable ------------------------------------------

namespace {

int instance_index(lua_State* L) {
  auto* in = static_cast<Instance*>(lua_touserdata(L, 1));
  lua_rawgeti(L, lua_upvalueindex(1), static_cast<int>(in->cls));
  lua_pushvalue(L, 2);
  lua_rawget(L, -2);
  if (lua_islightuserdata(L, -1)) {
    const auto* prop = static_cast<const Property*>(lua_touserdata(L, -1));
    lua_settop(L, 2);
    prop->get(L, 1, resolve(in));
    return 1;
  }
  if (!lua_isnil(L, -1)) return 1;
  lua_settop(L, 2);
  lua_getfenv(L, 1);
  lua_pushvalue(L, 2);
  lua_rawget(L, -2);
  return 1;
}

int instance_newindex(lua_State* L) {
  auto* in = static_cast<Instance*>(lua_touserdata(L, 1));
  lua_rawgeti(L, lua_upvalueindex(1), static_cast<int>(in->cls));
  lua_pushvalue(L, 2);
  lua_rawget(L, -2);
  if (lua_islightuserdata(L, -1)) {
    const auto* prop = static_cast<const Property*>(lua_touserdata(L, -1));
    if (!prop->set) throw LuaError(std::string("property '") + prop->name + "' is read only");
    lua_settop(L, 3);
    prop->set(L, resolve(in), 3);
    return 0;
  }
  // Unknown names live in a per-instance table and never reach C++.
  lua_settop(L, 3);
  lua_getfenv(L, 1);
  push_registry(L, &kEmptyEnvKey);
  if (lua_rawequal(L, -1, -2)) {
    lua_pop(L, 2);
    lua_newtable(L);
    lua_pushvalue(L, -1);
    lua_setfenv(L, 1);
  } else {
    lua_pop(L, 1);
  }
  lua_pushvalue(L, 2);
  lua_pushvalue(L, 3);
  lua_rawset(L, -3);
  return 0;
}

int instance_gc(lua_State* L) {
  auto* in = static_cast<Instance*>(lua_touserdata(L, 1));
  if (in && in->kind == Kind::Owned && in->destroy) {
    in->destroy(in->ptr);
    in->destroy = nullptr;
  }
  return 0;
}

enum OpSlot { kOpAdd, kOpSub, kOpMul, kOpEq, kOpOther };

lua_CFunction op_fn(Cls cls, int slot) {
  const Operators& o = g_ops[static_cast<int>(cls)];
  switch (slot) {
    case kOpAdd: return o.add;
    case kOpSub: return o.sub;
    case kOpMul: return o.mul;
    case kOpEq: return o.eq;
    default: return nullptr;
  }
}

// luabind's operator dispatcher: the first operand's class operator, else the
// second's, else "No such operator defined".
int operator_dispatch(lua_State* L) {
  const int slot = static_cast<int>(lua_tointeger(L, lua_upvalueindex(1)));
  for (int i = 1; i <= 2 && i <= lua_gettop(L); ++i) {
    if (Instance* in = to_instance(L, i)) {
      if (lua_CFunction fn = op_fn(in->cls, slot)) {
        lua_settop(L, 2);
        return fn(L);
      }
    }
  }
  throw LuaError("No such operator defined");
}

const char* const kOperatorNames[] = {"__add", "__sub", "__mul", "__div", "__pow",
                                      "__lt",  "__le",  "__eq",  "__call", "__unm",
                                      "__tostring", "__len", "__concat"};

int operator_slot(const char* name) {
  if (std::strcmp(name, "__add") == 0) return kOpAdd;
  if (std::strcmp(name, "__sub") == 0) return kOpSub;
  if (std::strcmp(name, "__mul") == 0) return kOpMul;
  if (std::strcmp(name, "__eq") == 0) return kOpEq;
  return kOpOther;
}

void ensure_runtime(lua_State* L) {
  push_registry(L, &kInstanceMtKey);
  const bool have = !lua_isnil(L, -1);
  lua_pop(L, 1);
  if (have) return;

  lua_pushlightuserdata(L, &kStateKey);
  auto* st = static_cast<ValueState*>(lua_newuserdata(L, sizeof(ValueState)));
  new (st) ValueState();
  lua_rawset(L, LUA_REGISTRYINDEX);  // trivially destructible: no __gc needed

  lua_pushlightuserdata(L, &kEmptyEnvKey);
  lua_newtable(L);
  lua_rawset(L, LUA_REGISTRYINDEX);

  lua_pushlightuserdata(L, &kClassesKey);
  lua_newtable(L);
  for (int c = 0; c < static_cast<int>(Cls::Count); ++c) {
    lua_newtable(L);
    lua_rawseti(L, -2, c);
  }
  const int classes = lua_gettop(L);

  lua_pushlightuserdata(L, &kInstanceMtKey);
  lua_newtable(L);
  lua_pushvalue(L, classes);
  lua_pushcclosure(L, ITB_G(instance_index), 1);
  lua_setfield(L, -2, "__index");
  lua_pushvalue(L, classes);
  lua_pushcclosure(L, ITB_G(instance_newindex), 1);
  lua_setfield(L, -2, "__newindex");
  lua_pushcfunction(L, instance_gc);
  lua_setfield(L, -2, "__gc");
  for (const char* name : kOperatorNames) {
    lua_pushinteger(L, operator_slot(name));
    lua_pushcclosure(L, ITB_G(operator_dispatch), 1);
    lua_setfield(L, -2, name);
  }
  lua_rawset(L, LUA_REGISTRYINDEX);

  lua_rawset(L, LUA_REGISTRYINDEX);  // classes table
}

}  // namespace

void register_class(lua_State* L, Cls cls, const char* global_name, lua_CFunction ctor,
                    std::initializer_list<Method> methods,
                    std::span<const Property> properties, Operators ops) {
  ensure_runtime(L);
  g_ops[static_cast<int>(cls)] = ops;
  push_registry(L, &kClassesKey);
  lua_rawgeti(L, -1, static_cast<int>(cls));
  for (const Method& m : methods) {
    lua_pushcfunction(L, m.fn);
    lua_setfield(L, -2, m.name);
  }
  for (const Property& p : properties) {
    lua_pushlightuserdata(L, const_cast<Property*>(&p));
    lua_setfield(L, -2, p.name);
  }
  lua_pop(L, 2);
  if (global_name) {
    // The class object: callable as the constructor.
    lua_newtable(L);
    if (ctor) {
      lua_newtable(L);
      lua_pushcfunction(L, ctor);
      lua_setfield(L, -2, "__call");
      lua_setmetatable(L, -2);
    }
    lua_setglobal(L, global_name);
  }
}

void add_methods(lua_State* L, Cls cls, std::span<const Method> methods) {
  push_registry(L, &kClassesKey);
  lua_rawgeti(L, -1, static_cast<int>(cls));
  for (const Method& m : methods) {
    lua_pushcfunction(L, m.fn);
    lua_setfield(L, -2, m.name);
  }
  lua_pop(L, 2);
}

void set_global_function(lua_State* L, const char* name, lua_CFunction fn) {
  lua_pushcfunction(L, fn);
  lua_setglobal(L, name);
}

// ---- property helpers --------------------------------------------------------

namespace {

[[noreturn]] void bad_property_value(const char* type) {
  no_overload((std::string("void <property>(") + type + " const&)").c_str());
}

template <class C, int C::*M>
void get_int(lua_State* L, int, void* o) {
  lua_pushinteger(L, static_cast<C*>(o)->*M);
}
template <class C, int C::*M>
void set_int(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TNUMBER) bad_property_value("int");
  static_cast<C*>(o)->*M = to_int(L, v);
}
template <class C, bool C::*M>
void get_bool(lua_State* L, int, void* o) {
  lua_pushboolean(L, static_cast<C*>(o)->*M);
}
template <class C, bool C::*M>
void set_bool(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TBOOLEAN) bad_property_value("bool");
  static_cast<C*>(o)->*M = lua_toboolean(L, v) != 0;
}
template <class C, float C::*M>
void get_float(lua_State* L, int, void* o) {
  lua_pushnumber(L, static_cast<C*>(o)->*M);
}
template <class C, float C::*M>
void set_float(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TNUMBER) bad_property_value("float");
  static_cast<C*>(o)->*M = to_float(L, v);
}
template <class C, std::string C::*M>
void get_string(lua_State* L, int, void* o) {
  const std::string& s = static_cast<C*>(o)->*M;
  lua_pushlstring(L, s.data(), s.size());
}
template <class C, std::string C::*M>
void set_string(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TSTRING) bad_property_value("std::string");
  static_cast<C*>(o)->*M = to_str(L, v);
}
// Class-typed fields: the getter returns a reference that aliases the owner.
template <class C, class T, T C::*M, Cls K>
void get_member(lua_State* L, int self, void*) {
  push_alias(L, self, K, Kind::Member, 0,
             [](void* parent, uintptr_t) -> void* { return &(static_cast<C*>(parent)->*M); });
}
template <class C, class T, T C::*M, Cls K>
void set_member(lua_State* L, void* o, int v) {
  Instance* in = to_instance(L, v, K);
  if (!in) bad_property_value(class_name(K));
  static_cast<C*>(o)->*M = *static_cast<T*>(resolve(in));
}

#define ITB_INT(C, f) Property{#f, &get_int<C, &C::f>, &set_int<C, &C::f>}
#define ITB_BOOL(C, f) Property{#f, &get_bool<C, &C::f>, &set_bool<C, &C::f>}
#define ITB_FLOAT(C, f) Property{#f, &get_float<C, &C::f>, &set_float<C, &C::f>}
#define ITB_STR(C, f) Property{#f, &get_string<C, &C::f>, &set_string<C, &C::f>}

// ---- Point -------------------------------------------------------------------

int point_ctor(lua_State* L) {
  if (match(L, {A::ClassTable})) {
    push_point(L, kLuaPointNone);
  } else if (match(L, {A::ClassTable, A::Int, A::Int})) {
    push_point(L, Point{to_int(L, 2), to_int(L, 3)});
  } else if (match(L, {A::ClassTable, A::Point})) {
    push_point(L, point_arg(L, 2));
  } else {
    no_overload("Point()\nPoint(int,int)\nPoint(Point const&)");
  }
  return 1;
}

// Stub values ("sinks") only exist while loading UI code without the
// native UI bindings; arithmetic with them stays a sink.
bool sink_operand(lua_State* L) {
  lua_getglobal(L, "ITB_SINK");
  const bool sink = !lua_isnil(L, -1) && (lua_rawequal(L, 1, -1) || lua_rawequal(L, 2, -1));
  if (!sink) lua_pop(L, 1);
  return sink;
}

int point_add(lua_State* L) {
  if (!match(L, {A::Point, A::Point})) {
    if (sink_operand(L)) return 1;
    no_overload("Point __add(Point const&,Point const&)");
  }
  push_point(L, point_arg(L, 1) + point_arg(L, 2));
  return 1;
}

int point_sub(lua_State* L) {
  if (!match(L, {A::Point, A::Point})) {
    if (sink_operand(L)) return 1;
    no_overload("Point __sub(Point const&,Point const&)");
  }
  push_point(L, point_arg(L, 1) - point_arg(L, 2));
  return 1;
}

int point_eq(lua_State* L) {
  if (!match(L, {A::Point, A::Point})) no_overload("bool __eq(Point const&,Point const&)");
  lua_pushboolean(L, point_arg(L, 1) == point_arg(L, 2));
  return 1;
}

int point_mul(lua_State* L) {
  if (!match(L, {A::Point, A::Int})) {
    if (sink_operand(L)) return 1;
    no_overload("void __mul(lua_State*,Point&,int)");
  }
  const Point p = point_arg(L, 1);
  const float k = static_cast<float>(to_int(L, 2));
  push_point(L, Point{static_cast<int>(std::roundf(static_cast<float>(p.x) * k)),
                      static_cast<int>(std::roundf(static_cast<float>(p.y) * k))});
  return 1;
}

int point_manhattan(lua_State* L) {
  if (!match(L, {A::Point, A::Point})) no_overload("int Manhattan(Point const&,Point)");
  const Point a = point_arg(L, 1), b = point_arg(L, 2);
  lua_pushinteger(L, std::abs(a.x - b.x) + std::abs(a.y - b.y));
  return 1;
}

int point_get_string(lua_State* L) {
  if (!match(L, {A::Point})) no_overload("std::string GetString(Point&)");
  const std::string s = point_string(point_arg(L, 1));
  lua_pushlstring(L, s.data(), s.size());
  return 1;
}

int point_get_lua_string(lua_State* L) {
  if (!match(L, {A::Point})) no_overload("std::string GetLuaString(Point&)");
  const std::string s = point_string(point_arg(L, 1));
  lua_pushlstring(L, s.data(), s.size());
  return 1;
}

void get_point_x(lua_State* L, int, void* o) { lua_pushinteger(L, static_cast<Point*>(o)->x); }
void set_point_x(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TNUMBER) bad_property_value("int");
  static_cast<Point*>(o)->x = to_int(L, v);
}
void get_point_y(lua_State* L, int, void* o) { lua_pushinteger(L, static_cast<Point*>(o)->y); }
void set_point_y(lua_State* L, void* o, int v) {
  if (lua_type(L, v) != LUA_TNUMBER) bad_property_value("int");
  static_cast<Point*>(o)->y = to_int(L, v);
}

const Property kPointProps[] = {{"x", &get_point_x, &set_point_x}, {"y", &get_point_y, &set_point_y}};

// ---- SpaceDamage -------------------------------------------------------------

using SD = LuaSpaceDamage;

int sd_ctor(lua_State* L) {
  SD sd;
  if (match(L, {A::ClassTable})) {
  } else if (match(L, {A::ClassTable, A::Int})) {
    sd.iDamage = to_int(L, 2);
  } else if (match(L, {A::ClassTable, A::Point})) {
    sd.loc = point_arg(L, 2);
  } else if (match(L, {A::ClassTable, A::Point, A::Int})) {
    sd.loc = point_arg(L, 2);
    sd.iDamage = to_int(L, 3);
  } else if (match(L, {A::ClassTable, A::Point, A::Int, A::Int})) {
    sd.loc = point_arg(L, 2);
    sd.iDamage = to_int(L, 3);
    sd.iPush = to_int(L, 4);
  } else {
    no_overload("SpaceDamage()\nSpaceDamage(int)\nSpaceDamage(Point)\nSpaceDamage(Point,int,int)\n"
                "SpaceDamage(Point,int)");
  }
  push_owned(L, Cls::SpaceDamage, std::move(sd));
  return 1;
}

int sd_is_movement(lua_State* L) {
  if (!match(L, {A::SD})) no_overload("bool IsMovement(SpaceDamage&)");
  lua_pushboolean(L, sd_arg(L, 1).is_movement());
  return 1;
}

int sd_move_start(lua_State* L) {
  if (!match(L, {A::SD})) no_overload("Point MoveStart(SpaceDamage&)");
  const SD& sd = sd_arg(L, 1);
  push_point(L, sd.path.empty() ? Point{-1, 1} : sd.path.front());
  return 1;
}

int sd_move_end(lua_State* L) {
  if (!match(L, {A::SD})) no_overload("Point MoveEnd(SpaceDamage&)");
  const SD& sd = sd_arg(L, 1);
  if (sd.path.empty()) throw LuaError("MoveEnd on a SpaceDamage without a path (undefined in game)");
  push_point(L, sd.path.back());
  return 1;
}

const Property kSdProps[] = {
    {"loc", &get_member<SD, Point, &SD::loc, Cls::Point>, &set_member<SD, Point, &SD::loc, Cls::Point>},
    ITB_INT(SD, iDamage),
    ITB_INT(SD, iPush),
    ITB_INT(SD, iShield),
    ITB_BOOL(SD, bSimpleMark),
    ITB_INT(SD, iFire),
    ITB_INT(SD, iFrozen),
    ITB_INT(SD, iInjure),
    ITB_INT(SD, iSmoke),
    ITB_INT(SD, iAcid),
    ITB_INT(SD, iCrack),
    ITB_BOOL(SD, bKO_Effect),
    ITB_STR(SD, sAnimation),
    ITB_STR(SD, sSound),
    ITB_STR(SD, sImageMark),
    ITB_STR(SD, sPawn),
    ITB_INT(SD, iPawnTeam),
    ITB_BOOL(SD, bHide),
    ITB_BOOL(SD, bHidePath),
    ITB_BOOL(SD, bHideIcon),
    ITB_BOOL(SD, bEvacuate),
    ITB_FLOAT(SD, fDelay),
    ITB_INT(SD, iTerrain),
    ITB_STR(SD, sScript),
    ITB_STR(SD, sItem),
};

// ---- lists ---------------------------------------------------------------------

using PointList = std::vector<Point>;
using IntList = std::vector<int>;
using DamageList = std::vector<SD>;

[[noreturn]] void bad_index(const char* what, int i, size_t n) {
  throw LuaError(std::string(what) + ": index " + std::to_string(i) + " outside 1.." +
                 std::to_string(n) + " (undefined in game)");
}

template <class V, Cls K, A Self>
int list_ctor(lua_State* L) {
  if (!match(L, {A::ClassTable})) no_overload("()");
  push_owned(L, K, V{});
  return 1;
}

template <class V, Cls K, A Self>
int list_size(lua_State* L) {
  if (!match(L, {Self})) no_overload("int size()");
  lua_pushinteger(L, static_cast<lua_Integer>(get<V>(L, 1, K).size()));
  return 1;
}

template <class V, Cls K, A Self>
int list_empty(lua_State* L) {
  if (!match(L, {Self})) no_overload("bool empty()");
  lua_pushboolean(L, get<V>(L, 1, K).empty());
  return 1;
}

template <class V, Cls K, A Self>
int list_erase(lua_State* L) {
  if (!match(L, {Self, A::Int})) no_overload("void erase(int)");
  V& v = get<V>(L, 1, K);
  const int i = to_int(L, 2);
  if (i < 1 || static_cast<size_t>(i) > v.size()) bad_index("erase", i, v.size());
  v.erase(v.begin() + (i - 1));
  return 0;
}

int point_list_index(lua_State* L) {
  if (!match(L, {A::PL, A::Int})) no_overload("Point index(PointList&,int)");
  const PointList& v = get<PointList>(L, 1, Cls::PointList);
  const int i = to_int(L, 2);
  if (i < 1 || static_cast<size_t>(i) > v.size()) bad_index("PointList:index", i, v.size());
  push_point(L, v[static_cast<size_t>(i - 1)]);
  return 1;
}

int point_list_push_back(lua_State* L) {
  if (!match(L, {A::PL, A::Point})) no_overload("void push_back(PointList&,Point)");
  const Point p = point_arg(L, 2);
  get<PointList>(L, 1, Cls::PointList).push_back(p);
  return 0;
}

int point_list_back(lua_State* L) {
  if (!match(L, {A::PL})) no_overload("Point back(PointList&)");
  const PointList& v = get<PointList>(L, 1, Cls::PointList);
  if (v.empty()) throw LuaError("PointList:back on an empty list (undefined in game)");
  push_point(L, v.back());
  return 1;
}

int int_list_index(lua_State* L) {
  if (!match(L, {A::IL, A::Int})) no_overload("int index(IntList&,int)");
  const IntList& v = get<IntList>(L, 1, Cls::IntList);
  const int i = to_int(L, 2);
  if (i < 1 || static_cast<size_t>(i) > v.size()) bad_index("IntList:index", i, v.size());
  lua_pushinteger(L, v[static_cast<size_t>(i - 1)]);
  return 1;
}

int int_list_push_back(lua_State* L) {
  if (!match(L, {A::IL, A::Int})) no_overload("void push_back(IntList&,int)");
  get<IntList>(L, 1, Cls::IntList).push_back(to_int(L, 2));
  return 0;
}

int int_list_back(lua_State* L) {
  if (!match(L, {A::IL})) no_overload("int back(IntList&)");
  const IntList& v = get<IntList>(L, 1, Cls::IntList);
  if (v.empty()) throw LuaError("IntList:back on an empty list (undefined in game)");
  lua_pushinteger(L, v.back());
  return 1;
}

void* damage_list_element(void* list, uintptr_t i) {
  auto& v = *static_cast<DamageList*>(list);
  return i < v.size() ? &v[i] : nullptr;
}

int damage_list_index(lua_State* L) {
  if (!match(L, {A::DL, A::Int})) no_overload("SpaceDamage& index(DamageList&,int)");
  const DamageList& v = get<DamageList>(L, 1, Cls::DamageList);
  const int i = to_int(L, 2);
  if (i < 1 || static_cast<size_t>(i) > v.size()) bad_index("DamageList:index", i, v.size());
  push_alias(L, 1, Cls::SpaceDamage, Kind::Element, static_cast<uintptr_t>(i - 1),
             &damage_list_element);
  return 1;
}

int damage_list_push_back(lua_State* L) {
  if (!match(L, {A::DL, A::SD})) no_overload("void push_back(DamageList&,SpaceDamage)");
  SD copy = sd_arg(L, 2);
  get<DamageList>(L, 1, Cls::DamageList).push_back(std::move(copy));
  return 0;
}

int damage_list_back(lua_State* L) {
  if (!match(L, {A::DL})) no_overload("SpaceDamage& back(DamageList&)");
  const DamageList& v = get<DamageList>(L, 1, Cls::DamageList);
  if (v.empty()) throw LuaError("DamageList:back on an empty list (undefined in game)");
  push_alias(L, 1, Cls::SpaceDamage, Kind::Element, v.size() - 1, &damage_list_element);
  return 1;
}

// ---- SkillEffect ------------------------------------------------------------------

using SE = LuaSkillEffect;

int se_ctor(lua_State* L) {
  if (!match(L, {A::ClassTable})) no_overload("SkillEffect()");
  push_skill_effect(L, SE{});
  return 1;
}

SE& se_self(lua_State* L) { return get<SE>(L, 1, Cls::SkillEffect); }

// A freshly built SpaceDamage at (-1,-1) (what the cosmetic adders append).
SD template_sd() { return SD{}; }

bool contains_laser(const std::string& art) { return art.find("laser") != std::string::npos; }

int se_add_damage(lua_State* L) {
  if (!match(L, {A::SE, A::SD})) no_overload("void AddDamage(SkillEffect&,SpaceDamage)");
  SD copy = sd_arg(L, 2);
  se_self(L).effect.push_back(std::move(copy));
  return 0;
}

int se_add_queued_damage(lua_State* L) {
  if (!match(L, {A::SE, A::SD})) no_overload("void AddQueuedDamage(SkillEffect&,SpaceDamage)");
  SD copy = sd_arg(L, 2);
  se_self(L).q_effect.push_back(std::move(copy));
  return 0;
}

int se_add_projectile(lua_State* L) {
  Point source = kInvalidPoint;
  int first = 2;
  float delay = kProjDelay;
  if (match(L, {A::SE, A::SD, A::Str, A::Num})) {
    delay = to_float(L, 4);
  } else if (match(L, {A::SE, A::SD, A::Str})) {
  } else if (match(L, {A::SE, A::Point, A::SD, A::Str, A::Num})) {
    source = point_arg(L, 2);
    first = 3;
    delay = to_float(L, 5);
  } else {
    no_overload("void AddProjectile(SkillEffect&,SpaceDamage,std::string,float)\n"
                "void AddProjectile(SkillEffect&,SpaceDamage,std::string)\n"
                "void AddProjectile(SkillEffect&,Point,SpaceDamage,std::string,float)");
  }
  SD sd = sd_arg(L, first);
  sd.projectile_art = to_str(L, first + 1);
  if (contains_laser(sd.projectile_art)) {
    sd.projectile_kind = 5;
    sd.fDelay = 0.0f;
  } else {
    sd.projectile_kind = 2;
    sd.fDelay = delay;
  }
  sd.projectile_source = source;
  se_self(L).effect.push_back(std::move(sd));
  return 0;
}

int se_add_queued_projectile(lua_State* L) {
  float delay = kProjDelay;
  if (match(L, {A::SE, A::SD, A::Str, A::Num})) {
    delay = to_float(L, 4);
  } else if (!match(L, {A::SE, A::SD, A::Str})) {
    no_overload("void AddQueuedProjectile(SkillEffect&,SpaceDamage,std::string,float)\n"
                "void AddQueuedProjectile(SkillEffect&,SpaceDamage,std::string)");
  }
  SD sd = sd_arg(L, 2);
  sd.projectile_art = to_str(L, 3);
  sd.projectile_kind = contains_laser(sd.projectile_art) ? 5 : 2;
  sd.fDelay = delay;
  se_self(L).q_effect.push_back(std::move(sd));
  return 0;
}

int se_add_artillery(lua_State* L) {
  Point source = kInvalidPoint;
  int first = 2;
  float delay = kProjDelay;
  if (match(L, {A::SE, A::Point, A::SD, A::Str, A::Num})) {
    source = point_arg(L, 2);
    first = 3;
    delay = to_float(L, 5);
  } else if (match(L, {A::SE, A::SD, A::Str, A::Num})) {
    delay = to_float(L, 4);
  } else if (!match(L, {A::SE, A::SD, A::Str})) {
    no_overload("void AddArtillery(SkillEffect&,Point,SpaceDamage,std::string,float)\n"
                "void AddArtillery(SkillEffect&,SpaceDamage,std::string,float)\n"
                "void AddArtillery(SkillEffect&,SpaceDamage,std::string)");
  }
  SD sd = sd_arg(L, first);
  sd.projectile_art = to_str(L, first + 1);
  sd.projectile_kind = 1;
  sd.fDelay = delay;
  sd.projectile_source = source;
  se_self(L).effect.push_back(std::move(sd));
  return 0;
}

int se_add_queued_artillery(lua_State* L) {
  float delay = kProjDelay;
  if (match(L, {A::SE, A::SD, A::Str, A::Num})) {
    delay = to_float(L, 4);
  } else if (!match(L, {A::SE, A::SD, A::Str})) {
    no_overload("void AddQueuedArtillery(SkillEffect&,SpaceDamage,std::string,float)\n"
                "void AddQueuedArtillery(SkillEffect&,SpaceDamage,std::string)");
  }
  SD sd = sd_arg(L, 2);
  sd.projectile_art = to_str(L, 3);
  sd.projectile_kind = 1;
  sd.fDelay = delay;
  se_self(L).q_effect.push_back(std::move(sd));
  return 0;
}

int add_melee(lua_State* L, bool queued) {
  float delay = kFullDelay;
  if (match(L, {A::SE, A::Point, A::SD, A::Num})) {
    delay = to_float(L, 4);
  } else if (!match(L, {A::SE, A::Point, A::SD})) {
    no_overload(queued ? "void AddQueuedMelee(SkillEffect&,Point,SpaceDamage,float)\n"
                         "void AddQueuedMelee(SkillEffect&,Point,SpaceDamage)"
                       : "void AddMelee(SkillEffect&,Point,SpaceDamage,float)\n"
                         "void AddMelee(SkillEffect&,Point,SpaceDamage)");
  }
  SD sd = sd_arg(L, 3);
  sd.move_kind = 3;
  sd.path.push_back(point_arg(L, 2));
  sd.fDelay = delay;
  SE& se = se_self(L);
  (queued ? se.q_effect : se.effect).push_back(std::move(sd));
  return 0;
}
int se_add_melee(lua_State* L) { return add_melee(L, false); }
int se_add_queued_melee(lua_State* L) { return add_melee(L, true); }

// AddMove: a movement entry, only for paths of two or more points.
bool append_move(std::vector<SD>& list, const PointList& path, float delay, int kind) {
  if (path.size() < 2) return false;
  SD sd = template_sd();
  sd.path = path;
  sd.move_kind = kind;
  sd.fDelay = delay;
  list.push_back(std::move(sd));
  return true;
}

int move_like(lua_State* L, bool queued, int kind, bool returns, const char* sig) {
  if (!match(L, {A::SE, A::PL, A::Num})) no_overload(sig);
  const PointList path = get<PointList>(L, 2, Cls::PointList);
  const float delay = to_float(L, 3);
  SE& se = se_self(L);
  const bool ok = append_move(queued ? se.q_effect : se.effect, path, delay, kind);
  if (!returns) return 0;
  lua_pushboolean(L, ok);
  return 1;
}
int se_add_move(lua_State* L) {
  return move_like(L, false, 0, true, "bool AddMove(SkillEffect&,PointList,float)");
}
int se_add_queued_move(lua_State* L) {
  return move_like(L, true, 0, true, "bool AddQueuedMove(SkillEffect&,PointList,float)");
}
int se_add_charge(lua_State* L) {
  return move_like(L, false, 2, false, "void AddCharge(SkillEffect&,PointList,float)");
}
int se_add_queued_charge(lua_State* L) {
  return move_like(L, true, 2, false, "void AddQueuedCharge(SkillEffect&,PointList,float)");
}
int se_add_burrow(lua_State* L) {
  return move_like(L, false, 5, false, "void AddBurrow(SkillEffect&,PointList,float)");
}

int direction_of(Point v) {
  if (v.x == 0 && v.y == 0) return 4;
  if (std::abs(v.x) > std::abs(v.y)) return v.x > 0 ? 1 : 3;
  return v.y > 0 ? 2 : 0;
}

int se_add_leap(lua_State* L) {
  if (!match(L, {A::SE, A::PL, A::Num})) no_overload("void AddLeap(SkillEffect&,PointList,float)");
  const PointList path = get<PointList>(L, 2, Cls::PointList);
  if (path.empty()) throw LuaError("AddLeap with an empty path (undefined in game)");
  const float delay = to_float(L, 3);
  SE& se = se_self(L);
  SD mark = template_sd();
  mark.loc = path.front();
  mark.sImageMark = "advanced/combat/throw_" +
                    std::to_string(direction_of(path.back() - path.front())) + ".png";
  se.effect.push_back(std::move(mark));
  append_move(se.effect, path, delay, 1);
  return 0;
}

int se_add_teleport(lua_State* L) {
  if (!match(L, {A::SE, A::Point, A::Point, A::Num})) {
    no_overload("void AddTeleport(SkillEffect&,Point,Point,float)");
  }
  const Point a = point_arg(L, 2), b = point_arg(L, 3);
  SE& se = se_self(L);
  append_move(se.effect, {a, b}, to_float(L, 4), 4);
  for (Point p : {a, b}) {
    SD glow = template_sd();
    glow.loc = p;
    glow.sImageMark = "advanced/combat/icons/icon_teleport_glow";
    se.effect.push_back(std::move(glow));
  }
  return 0;
}

int se_add_grapple(lua_State* L) {
  if (!match(L, {A::SE, A::Point, A::Point, A::Str})) {
    no_overload("void AddGrapple(SkillEffect&,Point,Point,std::string)");
  }
  SD sd = template_sd();
  sd.loc = point_arg(L, 2);
  sd.grapple_source = point_arg(L, 3);
  sd.grapple_anim = to_str(L, 4);
  sd.sAnimation = "dummy";
  se_self(L).effect.push_back(std::move(sd));
  return 0;
}

void add_script(SE& se, std::string script, bool queued) {
  SD sd = template_sd();
  sd.sScript = std::move(script);
  (queued ? se.q_effect : se.effect).push_back(std::move(sd));
}

int se_add_script(lua_State* L) {
  if (!match(L, {A::SE, A::Str})) no_overload("void AddScript(SkillEffect&,std::string)");
  add_script(se_self(L), to_str(L, 2), false);
  return 0;
}

int se_add_queued_script(lua_State* L) {
  if (!match(L, {A::SE, A::Str})) no_overload("void AddQueuedScript(SkillEffect&,std::string)");
  add_script(se_self(L), to_str(L, 2), true);
  return 0;
}

int se_add_bounce(lua_State* L) {
  if (!match(L, {A::SE, A::Point, A::Int})) no_overload("void AddBounce(SkillEffect&,Point,int)");
  add_script(se_self(L),
             "Board:Bounce(" + point_string(point_arg(L, 2)) + "," + std::to_string(to_int(L, 3)) + ")",
             false);
  return 0;
}

int se_add_board_shake(lua_State* L) {
  if (!match(L, {A::SE, A::Num})) no_overload("void AddBoardShake(SkillEffect&,float)");
  char buf[64];
  std::snprintf(buf, sizeof buf, "%f", static_cast<double>(to_float(L, 2)));
  add_script(se_self(L), std::string("Board:StartShake(") + buf + ")", false);
  return 0;
}

int se_add_burst(lua_State* L) {
  if (!match(L, {A::SE, A::Point, A::Str, A::Int})) {
    no_overload("void AddBurst(SkillEffect&,Point,std::string,int)");
  }
  add_script(se_self(L),
             "Board:AddBurst(" + point_string(point_arg(L, 2)) + ",\"" + to_str(L, 3) + "\"," +
                 std::to_string(to_int(L, 4)) + ")",
             false);
  return 0;
}

int se_add_sound(lua_State* L) {
  if (!match(L, {A::SE, A::Str})) no_overload("void AddSound(SkillEffect&,std::string)");
  SD sd = template_sd();
  sd.sSound = to_str(L, 2);
  se_self(L).effect.push_back(std::move(sd));
  return 0;
}

int add_voice(lua_State* L, bool queued) {
  if (!match(L, {A::SE, A::Str, A::Int})) {
    no_overload(queued ? "void AddQueuedVoice(SkillEffect&,std::string,int)"
                       : "void AddVoice(SkillEffect&,std::string,int)");
  }
  add_script(se_self(L),
             "PrepareVoiceEvent(\"" + to_str(L, 2) + "\"," + std::to_string(to_int(L, 3)) + ")",
             queued);
  return 0;
}
int se_add_voice(lua_State* L) { return add_voice(L, false); }
int se_add_queued_voice(lua_State* L) { return add_voice(L, true); }

void add_animation(SE& se, Point p, std::string anim, int flags) {
  SD sd = template_sd();
  sd.loc = p;
  sd.sAnimation = std::move(anim);
  sd.anim_flags = flags;
  se.effect.push_back(std::move(sd));
}

int se_add_animation(lua_State* L) {
  if (match(L, {A::SE, A::Point, A::Str})) {
    add_animation(se_self(L), point_arg(L, 2), to_str(L, 3), 2);
  } else if (match(L, {A::SE, A::Point, A::Str, A::Int})) {
    add_animation(se_self(L), point_arg(L, 2), to_str(L, 3), to_int(L, 4));
  } else {
    no_overload("void AddAnimation(SkillEffect&,Point,std::string)\n"
                "void AddAnimation(SkillEffect&,Point,std::string,int)");
  }
  return 0;
}

int se_add_emitter(lua_State* L) {
  if (!match(L, {A::SE, A::Point, A::Str})) no_overload("void AddEmitter(SkillEffect&,Point,std::string)");
  add_animation(se_self(L), point_arg(L, 2), "add_emitter_" + to_str(L, 3), 2);
  return 0;
}

void add_delay(SE& se, float f) {
  SD sd = template_sd();
  sd.bHide = true;
  sd.fDelay = f;
  se.effect.push_back(std::move(sd));
}

int se_add_delay(lua_State* L) {
  if (!match(L, {A::SE, A::Num})) no_overload("void AddDelay(SkillEffect&,float)");
  add_delay(se_self(L), to_float(L, 2));
  return 0;
}

int airstrike(lua_State* L, bool reverse) {
  if (!match(L, {A::SE, A::Point, A::Str})) {
    no_overload(reverse ? "void AddReverseAirstrike(SkillEffect&,Point,std::string)"
                        : "void AddAirstrike(SkillEffect&,Point,std::string)");
  }
  const Point p = point_arg(L, 2);
  SE& se = se_self(L);
  SD sd = template_sd();
  sd.loc = reverse ? Point{p.x, 0} : Point{0, p.y};
  sd.projectile_kind = reverse ? 6 : 3;
  sd.projectile_art = to_str(L, 3);
  sd.fDelay = kProjDelay;
  se.effect.push_back(std::move(sd));
  const int along = reverse ? p.y : p.x;
  add_delay(se, static_cast<float>(along) * 0.125f + 0.375f);
  return 0;
}
int se_add_airstrike(lua_State* L) { return airstrike(L, false); }
int se_add_reverse_airstrike(lua_State* L) { return airstrike(L, true); }

int se_add_dropper(lua_State* L) {
  if (!match(L, {A::SE, A::SD, A::Str})) no_overload("void AddDropper(SkillEffect&,SpaceDamage,std::string)");
  SD sd = sd_arg(L, 2);
  sd.projectile_art = to_str(L, 3);
  sd.projectile_kind = 4;
  sd.fDelay = 0.0f;
  se_self(L).effect.push_back(std::move(sd));
  return 0;
}

int se_get_damage_count(lua_State* L) {
  if (!match(L, {A::SE})) no_overload("int GetDamageCount(SkillEffect&)");
  lua_pushinteger(L, static_cast<lua_Integer>(se_self(L).effect.size()));
  return 1;
}

int se_get_queued_count(lua_State* L) {
  if (!match(L, {A::SE})) no_overload("int GetQueuedCount(SkillEffect&)");
  lua_pushinteger(L, static_cast<lua_Integer>(se_self(L).q_effect.size()));
  return 1;
}

void* se_effect_element(void* se, uintptr_t i) {
  auto& v = static_cast<SE*>(se)->effect;
  return i < v.size() ? &v[i] : nullptr;
}
void* se_queued_element(void* se, uintptr_t i) {
  auto& v = static_cast<SE*>(se)->q_effect;
  return i < v.size() ? &v[i] : nullptr;
}

int get_damage_ref(lua_State* L, bool queued) {
  if (!match(L, {A::SE, A::Int})) {
    no_overload(queued ? "SpaceDamage& GetQueuedDamage(SkillEffect&,int)"
                       : "SpaceDamage& GetDamage(SkillEffect&,int)");
  }
  const SE& se = se_self(L);
  const auto& v = queued ? se.q_effect : se.effect;
  const int i = to_int(L, 2);
  if (i < 1 || static_cast<size_t>(i) > v.size()) {
    bad_index(queued ? "GetQueuedDamage" : "GetDamage", i, v.size());
  }
  push_alias(L, 1, Cls::SpaceDamage, Kind::Element, static_cast<uintptr_t>(i - 1),
             queued ? &se_queued_element : &se_effect_element);
  return 1;
}
int se_get_damage(lua_State* L) { return get_damage_ref(L, false); }
int se_get_queued_damage(lua_State* L) { return get_damage_ref(L, true); }

const Property kSeProps[] = {
    {"effect", &get_member<SE, DamageList, &SE::effect, Cls::DamageList>,
     &set_member<SE, DamageList, &SE::effect, Cls::DamageList>},
    {"q_effect", &get_member<SE, DamageList, &SE::q_effect, Cls::DamageList>,
     &set_member<SE, DamageList, &SE::q_effect, Cls::DamageList>},
    {"piOrigin", &get_member<SE, Point, &SE::piOrigin, Cls::Point>,
     &set_member<SE, Point, &SE::piOrigin, Cls::Point>},
    ITB_STR(SE, impact_sound),
    ITB_INT(SE, iOwner),
};

// ---- GL_Color (UI only; values are never used by the rules) -------------------

struct GLColor {
  float r = 0, g = 0, b = 0, a = 1;
};

int color_ctor(lua_State* L) {
  GLColor c;
  if (match(L, {A::ClassTable})) {
  } else if (match(L, {A::ClassTable, A::Num, A::Num, A::Num, A::Num})) {
    c = {to_float(L, 2), to_float(L, 3), to_float(L, 4), to_float(L, 5)};
  } else if (match(L, {A::ClassTable, A::Num, A::Num, A::Num})) {
    c = {to_float(L, 2), to_float(L, 3), to_float(L, 4), 1.0f};
  } else {
    no_overload("GL_Color()\nGL_Color(float,float,float,float)\nGL_Color(float,float,float)");
  }
  push_owned(L, Cls::GLColor, c);
  return 1;
}

int color_normalize(lua_State* L) {
  if (!match(L, {A::Color})) no_overload("GL_Color Normalize(GL_Color&)");
  GLColor c = get<GLColor>(L, 1, Cls::GLColor);
  push_owned(L, Cls::GLColor, GLColor{c.r / 255.0f, c.g / 255.0f, c.b / 255.0f, c.a});
  return 1;
}

int color_with_alpha(lua_State* L) {
  if (!match(L, {A::Color, A::Num})) no_overload("GL_Color WithAlpha(GL_Color&,float)");
  GLColor c = get<GLColor>(L, 1, Cls::GLColor);
  c.a = to_float(L, 2);
  push_owned(L, Cls::GLColor, c);
  return 1;
}

const Property kColorProps[] = {ITB_FLOAT(GLColor, r), ITB_FLOAT(GLColor, g),
                                ITB_FLOAT(GLColor, b), ITB_FLOAT(GLColor, a)};

// ---- Objective (C++ RepObj) ---------------------------------------------------------

struct RepObj {
  std::string text, param1, param2;
  int category = 0, rep = 0, potential = 0;
  bool failed = false;
  std::string item;  // +0x28
};

int objective_ctor(lua_State* L) {
  RepObj o;
  if (match(L, {A::ClassTable, A::Str, A::Int})) {
    o.text = to_str(L, 2);
    o.rep = o.potential = to_int(L, 3);
  } else if (match(L, {A::ClassTable, A::Str, A::Int, A::Int})) {
    o.text = to_str(L, 2);
    o.rep = to_int(L, 3);
    o.potential = to_int(L, 4);
  } else if (match(L, {A::ClassTable, A::Str, A::Str, A::Str, A::Int})) {
    o.text = to_str(L, 2);
    o.param1 = to_str(L, 3);
    o.param2 = to_str(L, 4);
    o.rep = o.potential = to_int(L, 5);
  } else if (match(L, {A::ClassTable, A::Str, A::Str, A::Str, A::Int, A::Int})) {
    o.text = to_str(L, 2);
    o.param1 = to_str(L, 3);
    o.param2 = to_str(L, 4);
    o.rep = to_int(L, 5);
    o.potential = to_int(L, 6);
  } else if (match(L, {A::ClassTable, A::Str, A::Str})) {
    o.text = to_str(L, 2);
    o.category = 2;
    o.rep = o.potential = 1;
    o.item = to_str(L, 3);
  } else if (match(L, {A::ClassTable, A::Str, A::Str, A::Str, A::Str})) {
    o.text = to_str(L, 2);
    o.param1 = to_str(L, 3);
    o.param2 = to_str(L, 4);
    o.category = 2;
    o.rep = o.potential = 1;
    o.item = to_str(L, 5);
  } else {
    no_overload("Objective(std::string,int)\nObjective(std::string,std::string,std::string,int)\n"
                "Objective(std::string,int,int)\nObjective(std::string,std::string,std::string,int,int)\n"
                "Objective(std::string,std::string)\n"
                "Objective(std::string,std::string,std::string,std::string)");
  }
  push_owned(L, Cls::Objective, std::move(o));
  return 1;
}

int objective_failed(lua_State* L) {
  if (!match(L, {A::Objective})) no_overload("RepObj Failed(RepObj&)");
  RepObj o = get<RepObj>(L, 1, Cls::Objective);
  o.rep = 0;
  o.failed = true;
  push_owned(L, Cls::Objective, std::move(o));
  return 1;
}

int objective_lua_string(lua_State* L) {
  if (!match(L, {A::Objective})) no_overload("std::string GetLuaString(RepObj&)");
  const RepObj& o = get<RepObj>(L, 1, Cls::Objective);
  const std::string s = "Objective(\"" + o.text + "\"," + std::to_string(o.rep) + "," +
                        std::to_string(o.potential) + ")";
  lua_pushlstring(L, s.data(), s.size());
  return 1;
}

const Property kObjectiveProps[] = {ITB_STR(RepObj, text),    ITB_STR(RepObj, param1),
                                    ITB_STR(RepObj, param2),  ITB_INT(RepObj, category),
                                    ITB_INT(RepObj, rep),     ITB_INT(RepObj, potential)};

// ---- global functions ------------------------------------------------------------------

int get_direction(lua_State* L) {
  if (!match(L, {A::Point})) no_overload("int GetDirection(Point)");
  lua_pushinteger(L, direction_of(point_arg(L, 1)));
  return 1;
}

int random_int(lua_State* L) {
  GlibcRand& r = rng(L);
  if (match(L, {A::Int})) {
    const int n = to_int(L, 1);
    lua_pushinteger(L, n == 0 ? 0 : r.rand() % n);
  } else if (match(L, {A::Int, A::Int})) {
    const int a = to_int(L, 1), b = to_int(L, 2);
    lua_pushinteger(L, a == b ? a : a + r.rand() % (b - a));
  } else {
    no_overload("int random_int(int,int)\nint random_int(int)");
  }
  return 1;
}

int random_bool(lua_State* L) {
  GlibcRand& r = rng(L);
  if (match(L, {A::Int})) {
    const int n = to_int(L, 1);
    if (n == 0) throw LuaError("random_bool(0): division by zero (crashes the game)");
    lua_pushboolean(L, r.rand() % n == 0);
  } else if (match(L, {A::Int, A::Int})) {
    const int a = to_int(L, 1), b = to_int(L, 2);
    if (b == 0) throw LuaError("random_bool(a, 0): division by zero (crashes the game)");
    lua_pushboolean(L, r.rand() % b < a);
  } else {
    no_overload("bool random_bool(int,int)\nbool random_bool(int)");
  }
  return 1;
}

// Stock lmathlib math.random / math.randomseed over the game's rand().
int math_random(lua_State* L) {
  constexpr double kRandMax = 2147483647.0;
  const double r = static_cast<double>(rng(L).rand() % 2147483647) / kRandMax;
  switch (lua_gettop(L)) {
    case 0:
      lua_pushnumber(L, r);
      break;
    case 1: {
      const int u = luaL_checkint(L, 1);
      luaL_argcheck(L, 1 <= u, 1, "interval is empty");
      lua_pushnumber(L, std::floor(r * u) + 1);
      break;
    }
    case 2: {
      const int l = luaL_checkint(L, 1);
      const int u = luaL_checkint(L, 2);
      luaL_argcheck(L, l <= u, 2, "interval is empty");
      lua_pushnumber(L, std::floor(r * (u - l + 1)) + l);
      break;
    }
    default:
      return luaL_error(L, "wrong number of arguments");
  }
  return 1;
}

int math_randomseed(lua_State* L) {
  rng(L).srand(static_cast<uint32_t>(luaL_checkint(L, 1)));
  return 0;
}

int sound_effect(lua_State* L) {
  if (!match(L, {A::Point, A::Str})) no_overload("SpaceDamage SoundEffect(Point,std::string)");
  SD sd;
  sd.loc = point_arg(L, 1);
  sd.sSound = to_str(L, 2);
  push_owned(L, Cls::SpaceDamage, std::move(sd));
  return 1;
}

// Constants bound by ActiveLua::BindDefinitions / LuaEnv::BindUniversalDefinitions.
constexpr const char* kConstants = R"lua(
DIR_UP, DIR_RIGHT, DIR_DOWN, DIR_LEFT, DIR_NONE, DIR_ANY, DIR_FLIP = 0, 1, 2, 3, 4, 4, 6
DIR_START, DIR_END, DIR_TOTAL = 0, 3, 4
TEAM_PLAYER, TEAM_NONE, TEAM_ANY, TEAM_MECH, TEAM_ENEMY, TEAM_BOTS, TEAM_ENEMY_MAJOR = 1, 2, 2, 4, 6, 8, -1
FACTION_DEFAULT, FACTION_BOTS, FACTION_TOTAL = 0, 1, 2
TERRAIN_ROAD, TERRAIN_BUILDING, TERRAIN_RUBBLE, TERRAIN_WATER, TERRAIN_MOUNTAIN = 0, 1, 2, 3, 4
TERRAIN_ICE, TERRAIN_FOREST, TERRAIN_SAND, TERRAIN_HOLE = 5, 6, 7, 9
TERRAIN_FIRE, TERRAIN_ACID, TERRAIN_LAVA = 11, 12, 14
PATH_GROUND, PATH_FLYER, PATH_MASSIVE, PATH_PROJECTILE, PATH_ROADRUNNER = 0, 1, 2, 3, 4
PATH_BURROWER, PATH_PHASING = 7, 9
LEADER_NONE, LEADER_HEALTH, LEADER_VINES, LEADER_REGEN, LEADER_ARMOR = 0, 1, 2, 4, 5
LEADER_EXPLODE, LEADER_BOSS, LEADER_TENTACLE, LEADER_SPIDER, LEADER_FIRE = 6, 7, 8, 9, 10
LEADER_BOOSTED, LEADER_NECRO = 11, 12
TIER_NORMAL, TIER_ALPHA, TIER_BOSS = 0, 1, 2
DAMAGE_ZERO, DAMAGE_DEATH = 500, 1000
NO_DELAY, FULL_DELAY, PROJ_DELAY = 0, -1, -2
ENV_EFFECT = -10
EFFECT_NONE, EFFECT_CREATE, EFFECT_REMOVE = 0, 1, 2
EFFECT_DEADLY, EFFECT_WARNING = true, false
SERIOUSLY_JUST_ONE = 3626
INT_MAX = 2147483647
INVALID_NODE = 4294967295.0
NULL = 0
IMPACT_NULL, IMPACT_METAL, IMPACT_ROCK, IMPACT_FLESH, IMPACT_INSECT = 0, 1, 2, 3, 4
IMPACT_BLOB, IMPACT_SHIELD, IMPACT_WATER = 5, 6, 7
UNPOPULATED, POPULATED, TOTAL = 0, 1, 2
ZONE_NONE, ZONE_DIR, ZONE_ALL, ZONE_CUSTOM = 0, 1, 2, 3
BLOCKED_NONE, BLOCKED_TEMP, BLOCKED_PERM = 0, 1, 2
CRACK_LAVA, CRACK_TENTACLE = 0, 1
OBJ_STANDARD, OBJ_FAILED, OBJ_COMPLETE = 0, 1, 2
REWARD_REP, REWARD_POWER, REWARD_TECH, REWARD_POD = 0, 1, 2, 3
EVENT_ENEMY_KILLED, EVENT_MOUNTAIN_DESTROYED, EVENT_SPAWNBLOCKED = 2, 3, 16
EVENT_ACID_DESTROYED, EVENT_REPAIR_PICKUP, EVENT_REPAIR_UNDO = 18, 72, 73
DIFF_EASY, DIFF_NORMAL, DIFF_HARD, DIFF_UNFAIR = 0, 1, 2, 3
DIFF_MOD_NONE, DIFF_MOD_EASY, DIFF_MOD_HARD = 0, 1, 2
ANIM_NO_DELAY, ANIM_DELAY, ANIM_REVERSE = 1, 2, 4
LAYER_SKY, LAYER_FRONT, LAYER_BACK, LAYER_FLOOR, LAYER_LESS_BACK = 0, 1, 2, 3, 4
RAIN_NORMAL, RAIN_ACID, RAIN_SNOW = 0, 1, 2
FADE_IN, FADE_OUT, FADE_EXPLODE = 0, 1, 2
ALIGN_RIGHT, ALIGN_CENTER, ALIGN_LEFT, ALIGN_CENTER_ALL = 0, 1, 2, 3
QUEST_OBJECTIVES, QUEST_MECH, QUEST_BUILDINGS, QUEST_REPUTATION, QUEST_POWER = 0, 1, 2, 3, 4
NAME_NORMAL, NAME_FIRST, NAME_SECOND, NAME_REVERSE = 0, 2, 3, 4
FONT_MODE_NORMAL, FONT_MODE_LARGE, FONT_MODE_PHONE = 0, 1, 2
PAWN_ID_MECH, PAWN_ID_CEO, PAWN_ID_ARCHIVE, PAWN_ID_RST, PAWN_ID_PINNACLE = 1000, 2000, 2001, 2002, 2003
SQUAD_ARCHIVE_A, SQUAD_RUST_A, SQUAD_PINNACLE_A, SQUAD_DETRITUS_A = 0, 1, 2, 3
SQUAD_ARCHIVE_B, SQUAD_RUST_B, SQUAD_PINNACLE_B, SQUAD_DETRITUS_B = 4, 5, 6, 7
SQUAD_SECRET = 10
ADVANCED_SQUAD_1, ADVANCED_SQUAD_2, ADVANCED_SQUAD_3, ADVANCED_SQUAD_4 = 11, 12, 13, 14
ADVANCED_SQUAD_5, ADVANCED_SQUAD_6, ADVANCED_SQUAD_7 = 15, 16, 17
SEX_MALE, SEX_FEMALE, SEX_NEUTRAL, SEX_VEK, SEX_AI = 0, 1, 2, 3, 4
VEC_UP, VEC_RIGHT, VEC_DOWN, VEC_LEFT = Point(0, -1), Point(1, 0), Point(0, 1), Point(-1, 0)
-- UI colours: the RGB values are placeholders (never read by the rules).
COLOR_WHITE, COLOR_GRAY, COLOR_DARK_GRAY = GL_Color(255, 255, 255), GL_Color(128, 128, 128), GL_Color(64, 64, 64)
COLOR_BLACK, COLOR_BROWN, COLOR_RED = GL_Color(0, 0, 0), GL_Color(120, 80, 40), GL_Color(255, 0, 0)
COLOR_GREEN, COLOR_PURPLE, COLOR_BLUE = GL_Color(0, 255, 0), GL_Color(128, 0, 128), GL_Color(0, 0, 255)
COLOR_ORANGE, COLOR_YELLOW, COLOR_NONE = GL_Color(255, 128, 0), GL_Color(255, 255, 0), GL_Color(0, 0, 0, 0)
COLOR_PURPLE_STRAT, COLOR_PURPLE_LIGHT = GL_Color(128, 0, 128), GL_Color(200, 150, 255)
COLOR_RED_RUST, COLOR_BLUE_DARK, COLOR_BLUE_LIGHT = GL_Color(180, 60, 40), GL_Color(0, 0, 128), GL_Color(150, 200, 255)
COLOR_CB_BLUE, COLOR_CB_RED, COLOR_CB_ORANGE, COLOR_CB_WHITE = GL_Color(0, 0, 255), GL_Color(255, 0, 0), GL_Color(255, 128, 0), GL_Color(255, 255, 255)
)lua";

}  // namespace

void install_value_bindings(lua_State* L) {
  ensure_runtime(L);
  register_class(L, Cls::Point, "Point", ITB_G(point_ctor),
                 {{"Manhattan", ITB_G(point_manhattan)},
                  {"GetString", ITB_G(point_get_string)},
                  {"GetLuaString", ITB_G(point_get_lua_string)}},
                 kPointProps,
                 Operators{ITB_G(point_add), ITB_G(point_sub), ITB_G(point_mul), ITB_G(point_eq)});
  register_class(L, Cls::SpaceDamage, "SpaceDamage", ITB_G(sd_ctor),
                 {{"IsMovement", ITB_G(sd_is_movement)},
                  {"MoveStart", ITB_G(sd_move_start)},
                  {"MoveEnd", ITB_G(sd_move_end)}},
                 kSdProps);
  register_class(
      L, Cls::SkillEffect, "SkillEffect", ITB_G(se_ctor),
      {{"AddDamage", ITB_G(se_add_damage)},
       {"AddAnimation", ITB_G(se_add_animation)},
       {"AddEmitter", ITB_G(se_add_emitter)},
       {"AddVoice", ITB_G(se_add_voice)},
       {"AddQueuedVoice", ITB_G(se_add_queued_voice)},
       {"AddQueuedDamage", ITB_G(se_add_queued_damage)},
       {"AddMove", ITB_G(se_add_move)},
       {"AddCharge", ITB_G(se_add_charge)},
       {"AddAirstrike", ITB_G(se_add_airstrike)},
       {"AddReverseAirstrike", ITB_G(se_add_reverse_airstrike)},
       {"AddDropper", ITB_G(se_add_dropper)},
       {"AddQueuedScript", ITB_G(se_add_queued_script)},
       {"AddScript", ITB_G(se_add_script)},
       {"AddSound", ITB_G(se_add_sound)},
       {"AddBurst", ITB_G(se_add_burst)},
       {"AddQueuedCharge", ITB_G(se_add_queued_charge)},
       {"AddLeap", ITB_G(se_add_leap)},
       {"AddBurrow", ITB_G(se_add_burrow)},
       {"AddGrapple", ITB_G(se_add_grapple)},
       {"AddQueuedMove", ITB_G(se_add_queued_move)},
       {"GetDamageCount", ITB_G(se_get_damage_count)},
       {"GetQueuedCount", ITB_G(se_get_queued_count)},
       {"AddDelay", ITB_G(se_add_delay)},
       {"GetDamage", ITB_G(se_get_damage)},
       {"GetQueuedDamage", ITB_G(se_get_queued_damage)},
       {"AddProjectile", ITB_G(se_add_projectile)},
       {"AddQueuedProjectile", ITB_G(se_add_queued_projectile)},
       {"AddQueuedArtillery", ITB_G(se_add_queued_artillery)},
       {"AddArtillery", ITB_G(se_add_artillery)},
       {"AddMelee", ITB_G(se_add_melee)},
       {"AddQueuedMelee", ITB_G(se_add_queued_melee)},
       {"AddBounce", ITB_G(se_add_bounce)},
       {"AddTeleport", ITB_G(se_add_teleport)},
       {"AddBoardShake", ITB_G(se_add_board_shake)}},
      kSeProps);
  register_class(L, Cls::PointList, "PointList",
                 ITB_G((list_ctor<PointList, Cls::PointList, A::PL>)),
                 {{"size", ITB_G((list_size<PointList, Cls::PointList, A::PL>))},
                  {"index", ITB_G(point_list_index)},
                  {"push_back", ITB_G(point_list_push_back)},
                  {"back", ITB_G(point_list_back)},
                  {"erase", ITB_G((list_erase<PointList, Cls::PointList, A::PL>))},
                  {"empty", ITB_G((list_empty<PointList, Cls::PointList, A::PL>))}});
  register_class(L, Cls::IntList, "IntList", ITB_G((list_ctor<IntList, Cls::IntList, A::IL>)),
                 {{"size", ITB_G((list_size<IntList, Cls::IntList, A::IL>))},
                  {"index", ITB_G(int_list_index)},
                  {"push_back", ITB_G(int_list_push_back)},
                  {"back", ITB_G(int_list_back)},
                  {"erase", ITB_G((list_erase<IntList, Cls::IntList, A::IL>))},
                  {"empty", ITB_G((list_empty<IntList, Cls::IntList, A::IL>))}});
  register_class(L, Cls::DamageList, "DamageList",
                 ITB_G((list_ctor<DamageList, Cls::DamageList, A::DL>)),
                 {{"size", ITB_G((list_size<DamageList, Cls::DamageList, A::DL>))},
                  {"index", ITB_G(damage_list_index)},
                  {"push_back", ITB_G(damage_list_push_back)},
                  {"back", ITB_G(damage_list_back)},
                  {"empty", ITB_G((list_empty<DamageList, Cls::DamageList, A::DL>))}});
  register_class(L, Cls::GLColor, "GL_Color", ITB_G(color_ctor),
                 {{"Normalize", ITB_G(color_normalize)}, {"WithAlpha", ITB_G(color_with_alpha)}},
                 kColorProps);
  register_class(L, Cls::Objective, "Objective", ITB_G(objective_ctor),
                 {{"Failed", ITB_G(objective_failed)}, {"GetLuaString", ITB_G(objective_lua_string)}},
                 kObjectiveProps);

  set_global_function(L, "GetDirection", ITB_G(get_direction));
  set_global_function(L, "random_int", ITB_G(random_int));
  set_global_function(L, "random_bool", ITB_G(random_bool));
  set_global_function(L, "SoundEffect", ITB_G(sound_effect));
  lua_getglobal(L, "math");
  if (lua_istable(L, -1)) {
    lua_pushcfunction(L, ITB_G(math_random));
    lua_setfield(L, -2, "random");
    lua_pushcfunction(L, ITB_G(math_randomseed));
    lua_setfield(L, -2, "randomseed");
  }
  lua_pop(L, 1);

  if (luaL_dostring(L, kConstants) != 0) {
    const std::string msg = to_str(L, -1);
    lua_pop(L, 1);
    throw std::runtime_error("native constants: " + msg);
  }
}

}  // namespace itb::lua
