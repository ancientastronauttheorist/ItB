// The Lua host's bindings as plain C++ (internal). Every binding that a C++
// weapon port (weapon_ports.cpp) needs runs through the same function here,
// so a port and the Lua script it mirrors see exactly the same values and
// build exactly the same SpaceDamage entries.
#pragma once

#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include "itb/board.hpp"
#include "itb/lua_host.hpp"

struct lua_State;

namespace itb::lua::native {

using SD = LuaSpaceDamage;
using SE = LuaSkillEffect;

// ---- values ----------------------------------------------------------------------

// A Lua number passed to an int parameter (lua_tointeger as the game's build
// does it: truncate to 64 bits, keep the low 32; NaN and huge values give 0).
int32_t to_int(double d);
// GetDirection(v): DIR_NONE for (0,0), else the dominant axis.
int direction(Point v);
// Point * int: float multiply, rounded (the native operator).
Point mul(Point p, int k);
// tostring(n) for a Lua number ("%.14g"), as `..` formats numbers.
std::string number_string(double n);
// "Point( x, y )".
std::string point_string(Point p);

// SpaceDamage constructors (the overloads of SpaceDamage(...)).
SD space_damage(Point loc);
SD space_damage(Point loc, int damage);
SD space_damage(Point loc, int damage, int push);
// SoundEffect(p, sound).
SD sound_effect(Point loc, std::string sound);
// `name = <a SpaceDamage>` in Lua: the global gets a new SpaceDamage object.
void set_global_space_damage(lua_State* L, const char* name, const SD& sd);

// ---- SkillEffect adders (the bindings' effects; the SD is taken by value as
// the bindings copy their argument) -------------------------------------------------

void add_damage(SE& se, SD sd);
void add_queued_damage(SE& se, SD sd);
// AddProjectile([source,] sd, art[, delay]); `source` invalid: no source.
void add_projectile(SE& se, Point source, SD sd, std::string art, float delay);
void add_queued_projectile(SE& se, SD sd, std::string art, float delay);
void add_artillery(SE& se, Point source, SD sd, std::string art, float delay);
void add_queued_artillery(SE& se, SD sd, std::string art, float delay);
void add_melee(SE& se, bool queued, Point from, SD sd, float delay);
// AddMove (kind 0), AddCharge (2), AddBurrow (5) and their queued forms:
// appended only for paths of two or more points; returns whether it was.
bool add_move(SE& se, bool queued, const std::vector<Point>& path, float delay, int kind);
// AddLeap(path, delay); the path must not be empty.
void add_leap(SE& se, const std::vector<Point>& path, float delay);
void add_teleport(SE& se, Point a, Point b, float delay);
void add_grapple(SE& se, Point loc, Point source, std::string anim);
void add_script(SE& se, std::string script, bool queued);
void add_bounce(SE& se, Point p, int amount);
void add_board_shake(SE& se, float seconds);
void add_delay(SE& se, float seconds);
void add_animation(SE& se, Point p, std::string anim, int flags);
void add_sound(SE& se, std::string sound);

// ---- Board queries (Board:...) -------------------------------------------------------

bool is_blocked(const Board& b, Point p, int path_prof);  // IsBlocked(p, prof)
bool is_pawn_space(const Board& b, Point p);               // IsPawnSpace(p)
const Pawn* pawn_at(const Board& b, Point p);              // GetPawn(p)
int pawn_team(const Board& b, Point p);                    // GetPawnTeam(p)
bool is_pawn_team(lua_State* L, const Board& b, Point p, int team);  // IsPawnTeam(p, team)
bool is_building(const Board& b, Point p);                 // IsBuilding(p)
bool is_pod(const Board& b, Point p);                      // IsPod(p)
int terrain(const Board& b, Point p);                      // GetTerrain(p)
std::vector<Point> simple_path(const Board& b, Point from, Point to);           // GetSimplePath
std::vector<Point> simple_reachable(const Board& b, Point p, int len, bool corners);  // GetSimpleReachable
std::vector<Point> reachable(const Board& b, Point p, int move, int path_prof);  // GetReachable
std::vector<Point> path(const Board& b, Point from, Point to, int path_prof);    // GetPath
std::vector<int> pawn_ids(lua_State* L, const Board& b, int team);              // GetPawns(team)

// ---- Pawn queries (Pawn:...) -----------------------------------------------------------

int path_prof(const Board& b, const Pawn& p);  // GetPathProf
int move_speed(const Board& b, const Pawn& p);  // GetMoveSpeed
bool is_ability(const Pawn& p, std::string_view name);  // IsAbility
bool is_jumper(const Pawn& p);      // IsJumper
bool is_teleporter(const Pawn& p);  // IsTeleporter
bool is_guarding(const Pawn& p);    // IsGuarding
bool is_fire(const Pawn& p);        // IsFire

// IsPassiveSkill(name).
bool is_passive_skill(lua_State* L, const std::string& name);

}  // namespace itb::lua::native
