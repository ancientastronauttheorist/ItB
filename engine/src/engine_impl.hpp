// Engine internals shared by the action API (engine.cpp) and the enemy phase
// (enemy_phase.cpp).
#pragma once

#include <memory>

#include "itb/engine.hpp"
#include "itb/game_data.hpp"

namespace itb {

struct Engine::Impl {
  EngineOptions options;
  GameData data;
  std::unique_ptr<LuaHost> host;
  // The Lua `Pawn` global: the pawn selected last (sticky, as in game).
  int32_t selected = -1;

  // Fills `ctx` for a resolution with the Lua hooks wired (sScripts, death
  // effects and their writes) and the caller's options. Lua diagnostics go to
  // `diag`; `ctx` and `diag` must outlive every Resolver that uses `ctx`.
  void wire(Engine& engine, ResolveContext& ctx, const ActionOptions& opts, ActionResult& diag);

  // SkillManager::FireQueued up to the effect: the stored shot is used up, the
  // shooter selected and the effect recomputed from its current tile. On
  // success (`out.ok()`) `out.effect` is prepared and `info` describes it;
  // NoEffect = the shot fizzled.
  ActionResult queued_effect(Board& board, int32_t uid, WeaponInfo& info);
};

}  // namespace itb
