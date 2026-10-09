// Internals of the Lua host: a small emulation of the luabind 0.9 runtime
// rules the game's bindings follow (exact-arity overloads, strict argument
// types, one shared instance metatable, aliasing references), the value
// classes, and the game's rand() stream.
#pragma once

#include <cstdint>
#include <initializer_list>
#include <new>
#include <span>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "itb/core.hpp"
#include "itb/lua_host.hpp"

extern "C" {
#include "lua.h"
}

namespace itb::lua {

// glibc rand()/srand() (TYPE_3 additive feedback generator, degree 31,
// separation 3). The game draws every random_int/random_bool/math.random from
// this one process-wide stream.
class GlibcRand {
 public:
  GlibcRand() { srand(1); }
  explicit GlibcRand(uint32_t seed) { srand(seed); }
  // Seeding is deferred to the first draw (the state fill and warm-up are
  // the costly part, and most seeded calls never draw).
  void srand(uint32_t seed) {
    pending_ = seed;
    has_pending_ = true;
  }
  int32_t rand() {
    if (has_pending_) seed_now();
    return next();
  }
  // rand() calls made by scripts so far (srand's own warm-up not counted).
  uint64_t draws() const { return draws_; }

 private:
  void seed_now();
  int32_t next();
  uint32_t pending_ = 1;
  bool has_pending_ = false;
  int32_t state_[31];
  uint64_t draws_ = 0;
  int front_ = 3;  // index of the "f" pointer
  int rear_ = 0;   // index of the "r" pointer
};

// ---- luabind-style instances --------------------------------------------

enum class Cls : uint8_t {
  Point,
  SpaceDamage,
  SkillEffect,
  PointList,
  IntList,
  DamageList,
  GLColor,
  Objective,
  Board,
  BoardPawn,
  GameMap,
  ValueBar,
  PawnFactory,
  Count
};

const char* class_name(Cls c);

enum class Kind : uint8_t {
  Owned,    // the userdata owns the object (by-value results, constructors)
  Ref,      // non-owning pointer (singletons)
  Element,  // element `index` of the parent's vector (SpaceDamage& results)
  Member,   // a member of the parent (class-typed def_readwrite fields)
  Pawn,     // a board pawn, looked up by uid (`index`)
};

struct Instance {
  Cls cls;
  Kind kind;
  void* ptr;          // Owned/Ref: the object
  Instance* parent;   // Element/Member: the owner (kept alive by the env table)
  uintptr_t index;    // Element: vector index; Pawn: uid
  void* (*project)(void* parent_obj, uintptr_t index);  // Element/Member
  void (*destroy)(void* obj);                             // Owned
};

// Raised by binding code; converted to a Lua error after C++ unwinding.
struct LuaError : std::runtime_error {
  using std::runtime_error::runtime_error;
};

[[noreturn]] void no_overload(const char* candidates);

// The object an instance refers to; throws LuaError for a dangling alias.
void* resolve(const Instance* in);

// The instance at idx, or null if the value is not a host instance.
Instance* to_instance(lua_State* L, int idx);
Instance* to_instance(lua_State* L, int idx, Cls cls);

// Pushes a new owning userdata with room for the object; the caller
// constructs it at `ptr` and then sets `destroy`.
Instance* new_owned(lua_State* L, Cls cls, size_t size, size_t align);

template <class T>
T* push_owned(lua_State* L, Cls cls, T value) {
  Instance* in = new_owned(L, cls, sizeof(T), alignof(T));
  T* obj = new (in->ptr) T(std::move(value));
  in->destroy = [](void* p) { static_cast<T*>(p)->~T(); };
  return obj;
}

// Non-owning alias of a sub-object of the instance at parent_idx.
void push_alias(lua_State* L, int parent_idx, Cls cls, Kind kind, uintptr_t index,
                void* (*project)(void*, uintptr_t));
void push_ref(lua_State* L, Cls cls, void* obj);
// Gives the userdata on top of the stack the instance metatable and the
// shared empty per-instance table.
void finish_instance(lua_State* L);

template <class T>
T& get(lua_State* L, int idx, Cls cls) {
  Instance* in = to_instance(L, idx, cls);
  if (!in) throw LuaError(std::string("expected ") + class_name(cls));
  return *static_cast<T*>(resolve(in));
}

// ---- argument matching ----------------------------------------------------

enum class A : uint8_t {
  Int,    // LUA_TNUMBER only (truncated like lua_tointeger)
  Num,    // LUA_TNUMBER only
  Bool,   // LUA_TBOOLEAN only
  Str,    // LUA_TSTRING only
  Point,
  SD,
  SE,
  PL,
  IL,
  DL,
  Color,
  Objective,
  Board,
  Pawn,     // BoardPawn reference (nil rejected)
  PawnPtr,  // Pawn*: nil accepted
  Game,
  ValueBar,
  Factory,
  ClassTable,  // a constructor's class table
  Any,
};

// True iff lua_gettop(L) == sig.size() and each argument converts.
bool match(lua_State* L, std::initializer_list<A> sig);
bool match_one(lua_State* L, int idx, A a);

// lua_tointeger as the game's build does it: truncate toward zero to 64 bits,
// keep the low 32 bits; NaN/huge give 0.
int32_t to_int(lua_State* L, int idx);
inline float to_float(lua_State* L, int idx) { return static_cast<float>(lua_tonumber(L, idx)); }
inline bool to_bool(lua_State* L, int idx) { return lua_toboolean(L, idx) != 0; }
std::string to_str(lua_State* L, int idx);

Point& point_arg(lua_State* L, int idx);
void push_point(lua_State* L, Point p);
void push_point_list(lua_State* L, std::vector<Point> list);
void push_int_list(lua_State* L, std::vector<int> list);

// ---- class registration ---------------------------------------------------

using Getter = void (*)(lua_State* L, int self_idx, void* obj);
using Setter = void (*)(lua_State* L, void* obj, int value_idx);

struct Property {
  const char* name;
  Getter get;
  Setter set;  // null: read-only
};

struct Method {
  const char* name;
  lua_CFunction fn;  // already guarded
};

// Operators a class defines (luabind's self + other style).
struct Operators {
  lua_CFunction add = nullptr;
  lua_CFunction sub = nullptr;
  lua_CFunction mul = nullptr;
  lua_CFunction eq = nullptr;
};

// Creates the class: global `name` (when non-null) callable as a constructor,
// methods, properties and operators.
// `properties` must have static storage (the class keeps pointers to them).
void register_class(lua_State* L, Cls cls, const char* global_name, lua_CFunction ctor,
                    std::initializer_list<Method> methods,
                    std::span<const Property> properties = {}, Operators ops = {});

// Wraps a binding body: LuaError and other C++ exceptions become Lua errors
// after the C++ frames have unwound (Lua is built as C and longjmps).
template <int (*F)(lua_State*)>
int guarded(lua_State* L) {
  try {
    return F(L);
  } catch (const std::exception& e) {
    lua_pushstring(L, e.what());
  }
  return lua_error(L);
}

void add_methods(lua_State* L, Cls cls, std::span<const Method> methods);

#define ITB_G(fn) (&::itb::lua::guarded<fn>)

void set_global_function(lua_State* L, const char* name, lua_CFunction fn);

// Constants, value classes (Point, SpaceDamage, SkillEffect, lists,
// GL_Color, Objective) and the global value functions (GetDirection,
// random_int, random_bool, math.random, SoundEffect).
void install_value_bindings(lua_State* L);

GlibcRand& rng(lua_State* L);

// Values the Board/Pawn bindings need from the value module.
LuaSpaceDamage& sd_arg(lua_State* L, int idx);
void push_skill_effect(lua_State* L, LuaSkillEffect se);
std::string point_string(Point p);  // "Point( x, y )"

}  // namespace itb::lua
