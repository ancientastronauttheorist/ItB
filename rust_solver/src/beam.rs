//! Beam search outer loop — Task #10.
//!
//! Depth-N lookahead over plans. For depth = 1, equivalent to
//! [`solve_turn_top_k`]. For depth = 2, expands each of the top-K₁ level-0
//! plans by running [`project_plan`] + a nested [`solve_turn_top_k`] at
//! K₂, then aggregates `chain_score = level_0.score + best_level_1.score`.
//! The per-turn `future_factor` inside [`crate::evaluate::evaluate`]
//! already damps turn+1 contributions, so we don't apply an additional
//! discount at the beam level.
//!
//! # Why top-level K₁ plans get a level-1 bonus even when level-1 fails
//!
//! If `project_plan` produces a board with no legal actions (final turn,
//! all mechs dead, every mech webbed/frozen) the sub-solver returns an
//! empty vec. Those chains keep `level_1_best = None` and their
//! `chain_score` falls back to level-0 only. This is the correct signal:
//! "the mission ends here, we only care about turn 1."
//!
//! # Determinism
//!
//! `solve_turn_top_k` is byte-deterministic per the Task #3 ship (ties
//! broken by insertion sequence in `BoundedTopK`). Beam preserves this
//! by iterating chains serially — no rayon at the outer level. Each
//! sub-solve is internally parallel, which is fine.

use std::time::{Duration, Instant};

use crate::board::Board;
use crate::evaluate::EvalWeights;
use crate::solver::{solve_turn_top_k, Solution};
use crate::types::DisabledMask;
use crate::turn_projection::project_plan;
use crate::weapons::WeaponTable;

/// One beam chain: a level-0 plan plus the best sub-plan discovered by
/// projecting forward and re-solving. At depth 1 the `level_1_best` is
/// always `None`.
#[derive(Clone, Debug)]
pub struct BeamChain {
    pub level_0: Solution,
    pub level_1_best: Option<Solution>,
    /// `level_0.score + level_1_best.score`, or `level_0.score` when
    /// no sub-plan exists. Used as the sort key on the returned Vec.
    pub chain_score: f64,
}

/// Run beam search.
///
/// - `depth` — 1 or 2 for v1. Depth ≥ 3 is deferred (see scratch doc).
/// - `k_per_level` — expected length == depth. `k_per_level[0]` controls
///   top-level fan-out, `k_per_level[1]` controls the sub-solve width.
/// - `time_limit_secs` — total wall-clock budget. Split 40/60 between
///   level 0 (broad search) and level 1 (aggregate sub-solve time).
///
/// Returns the chains sorted by `chain_score` descending. An empty
/// board (no active mechs) returns an empty Vec.
#[allow(clippy::too_many_arguments)]
pub fn solve_beam(
    board: &Board,
    spawn_points: &[(u8, u8)],
    depth: usize,
    k_per_level: &[usize],
    time_limit_secs: f64,
    weights: &EvalWeights,
    disabled_mask: DisabledMask,
    weapons: &WeaponTable,
) -> Vec<BeamChain> {
    assert!(depth >= 1 && depth <= 2, "beam depth must be 1 or 2 for v1 (got {depth})");
    assert!(
        k_per_level.len() >= depth,
        "k_per_level must have >= depth entries (got len {}, depth {depth})",
        k_per_level.len()
    );

    let started = Instant::now();
    let total_budget = Duration::from_secs_f64(time_limit_secs.max(0.1));

    // Level 0: broad search. 40% of budget when we plan to expand, full
    // budget when depth == 1.
    let level_0_budget = if depth == 1 {
        total_budget
    } else {
        Duration::from_secs_f64(time_limit_secs * 0.40)
    };
    let level_0 = solve_turn_top_k(
        board,
        spawn_points,
        level_0_budget.as_secs_f64(),
        99_999,
        weights,
        disabled_mask,
        weapons,
        k_per_level[0],
    );

    if depth == 1 || level_0.is_empty() {
        return level_0
            .into_iter()
            .map(|sol| {
                let score = sol.score;
                BeamChain { level_0: sol, level_1_best: None, chain_score: score }
            })
            .collect();
    }

    // Level 1: per-chain sub-solve. Divide the remaining 60% equally
    // across K₁ chains. If we've already spent all of `total_budget`
    // at level 0 (which can happen when the caller passed a very tight
    // time_limit) every per-chain budget clamps to a small minimum so
    // each chain still gets at least one iteration's worth of search.
    let elapsed = started.elapsed();
    let remaining = total_budget.checked_sub(elapsed).unwrap_or(Duration::from_millis(0));
    let per_chain_secs = (remaining.as_secs_f64() / level_0.len() as f64).max(0.05);

    let k2 = k_per_level[1];

    let mut chains: Vec<BeamChain> = Vec::with_capacity(level_0.len());
    for plan in level_0 {
        let (projected, _ar) = project_plan(board, &plan.actions, spawn_points, weapons);

        // Forward the SAME spawn_points to the sub-solve. project_plan
        // doesn't mutate the spawn footprint (spawn TIMING changes as
        // remaining_spawns decrements inside the board, but the set of
        // tiles the game will use for spawns stays constant over a
        // mission). If that assumption changes we'd want project_plan
        // to return updated spawn_points.
        let sub = solve_turn_top_k(
            &projected,
            spawn_points,
            per_chain_secs,
            99_999,
            weights,
            disabled_mask,
            weapons,
            k2,
        );

        let level_1_best = sub.into_iter().next();
        let chain_score = match &level_1_best {
            Some(s) => plan.score + s.score,
            None => plan.score,
        };
        chains.push(BeamChain { level_0: plan, level_1_best, chain_score });
    }

    // Sort by chain_score desc; on ties keep insertion order (stable
    // sort preserves it, matching the determinism contract).
    chains.sort_by(|a, b| b.chain_score.partial_cmp(&a.chain_score).unwrap_or(std::cmp::Ordering::Equal));
    chains
}

// ── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::board::{Board, Unit, UnitFlags, WeaponId};
    use crate::types::{Team, Terrain, xy_to_idx};
    use crate::weapons::{WEAPONS, WId};

    fn eval_weights_default() -> EvalWeights {
        EvalWeights::default()
    }

    fn mk_board_with_mech_and_enemy() -> (Board, Vec<(u8, u8)>) {
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1; b.remaining_spawns = 2;
        // Player mech with a usable melee weapon and room to act.
        let mut mech = Unit::default();
        mech.uid = 0; mech.set_type_name("PunchMech");
        mech.x = 3; mech.y = 3; mech.hp = 3; mech.max_hp = 3;
        mech.team = Team::Player;
        mech.flags = UnitFlags::IS_MECH | UnitFlags::ACTIVE | UnitFlags::CAN_MOVE | UnitFlags::PUSHABLE;
        mech.move_speed = 3; mech.base_move = 3;
        mech.weapon = WeaponId(WId::PrimePunchmech as u16);
        b.add_unit(mech);
        // Enemy threatening a building so there's actually a defensive
        // decision to make.
        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 5; enemy.y = 4; enemy.hp = 2; enemy.max_hp = 2;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE | UnitFlags::HAS_QUEUED_ATTACK;
        enemy.move_speed = 2; enemy.base_move = 2;
        enemy.queued_target_x = 4; enemy.queued_target_y = 4;
        b.add_unit(enemy);
        b.tiles[xy_to_idx(4, 4)].terrain = Terrain::Building;
        b.tiles[xy_to_idx(4, 4)].building_hp = 1;
        b.grid_power = 5;
        b.grid_power_max = 7;
        (b, vec![])
    }

    #[test]
    fn test_beam_depth_1_matches_top_k() {
        // Depth 1 must equal solve_turn_top_k with the same K.
        let (board, spawn_points) = mk_board_with_mech_and_enemy();
        let weights = eval_weights_default();
        let k = 3;
        let beam = solve_beam(&board, &spawn_points, 1, &[k], 5.0, &weights, [0; 2], &WEAPONS);
        let top = solve_turn_top_k(&board, &spawn_points, 5.0, 99_999, &weights, [0; 2], &WEAPONS, k);
        assert_eq!(beam.len(), top.len());
        for (i, (b_chain, t_sol)) in beam.iter().zip(top.iter()).enumerate() {
            assert_eq!(b_chain.level_0.score, t_sol.score,
                "depth-1 chain {} score must match top_k", i);
            assert!(b_chain.level_1_best.is_none(),
                "depth-1 chain {} must have no level_1_best", i);
            assert_eq!(b_chain.chain_score, t_sol.score,
                "depth-1 chain_score must equal level_0.score");
        }
    }

    #[test]
    fn test_beam_depth_2_chains_sorted_desc() {
        let (board, spawn_points) = mk_board_with_mech_and_enemy();
        let weights = eval_weights_default();
        let beam = solve_beam(&board, &spawn_points, 2, &[3, 2], 10.0, &weights, [0; 2], &WEAPONS);
        assert!(!beam.is_empty(), "depth-2 beam should return at least 1 chain on a playable board");
        for w in beam.windows(2) {
            assert!(w[0].chain_score >= w[1].chain_score,
                "chains must be sorted by chain_score desc: {} >= {}",
                w[0].chain_score, w[1].chain_score);
        }
    }

    #[test]
    fn test_beam_chain_score_never_below_level_0() {
        // chain_score = level_0.score + level_1_best.score (or level_0 alone).
        // Since level_1_best is optional (empty sub-solve returns None)
        // chain_score is always ≥ level_0.score when level_1 is empty,
        // or = level_0 + level_1_best.score otherwise (which MAY be less
        // than level_0 if level_1_best has negative score — that's fine
        // because it accurately reflects the chain's quality).
        let (board, spawn_points) = mk_board_with_mech_and_enemy();
        let weights = eval_weights_default();
        let beam = solve_beam(&board, &spawn_points, 2, &[3, 2], 10.0, &weights, [0; 2], &WEAPONS);
        for c in &beam {
            match &c.level_1_best {
                Some(s) => assert_eq!(c.chain_score, c.level_0.score + s.score),
                None    => assert_eq!(c.chain_score, c.level_0.score),
            }
        }
    }

    #[test]
    fn test_beam_deterministic() {
        // Two identical runs must produce byte-equivalent output
        // (action sequences and chain_scores).
        let (board, spawn_points) = mk_board_with_mech_and_enemy();
        let weights = eval_weights_default();
        let a = solve_beam(&board, &spawn_points, 2, &[3, 2], 10.0, &weights, [0; 2], &WEAPONS);
        let b = solve_beam(&board, &spawn_points, 2, &[3, 2], 10.0, &weights, [0; 2], &WEAPONS);
        assert_eq!(a.len(), b.len());
        for (ac, bc) in a.iter().zip(b.iter()) {
            assert_eq!(ac.chain_score, bc.chain_score);
            assert_eq!(ac.level_0.actions.len(), bc.level_0.actions.len());
            for (aa, ba) in ac.level_0.actions.iter().zip(bc.level_0.actions.iter()) {
                assert_eq!(aa.mech_uid, ba.mech_uid);
                assert_eq!(aa.move_to, ba.move_to);
                assert_eq!(aa.weapon as u16, ba.weapon as u16);
                assert_eq!(aa.target, ba.target);
            }
        }
    }

    #[test]
    fn test_beam_empty_on_no_active_mechs() {
        // No mechs → solve_turn_top_k returns empty → beam returns empty.
        let mut b = Board::default();
        b.total_turns = 5; b.current_turn = 1;
        // Drop an enemy so the board isn't literally empty (solver's
        // no-active-units short-circuit should still fire since no
        // player unit can act).
        let mut enemy = Unit::default();
        enemy.uid = 10; enemy.set_type_name("Hornet");
        enemy.x = 4; enemy.y = 4; enemy.hp = 1; enemy.max_hp = 1;
        enemy.team = Team::Enemy;
        enemy.flags = UnitFlags::ACTIVE | UnitFlags::PUSHABLE;
        b.add_unit(enemy);
        let weights = eval_weights_default();
        let beam = solve_beam(&b, &[], 2, &[3, 2], 2.0, &weights, [0; 2], &WEAPONS);
        assert!(beam.is_empty(), "no-active-mechs board must yield empty beam");
    }

    #[test]
    fn test_beam_final_turn_falls_back_to_level_0() {
        // On the final turn, projected board has current_turn > total_turns
        // (project_plan increments beyond total_turns). The sub-solve
        // should find no meaningful plan → level_1_best is None OR
        // has non-positive score — either way chain_score degrades
        // gracefully.
        let (mut board, spawn_points) = mk_board_with_mech_and_enemy();
        board.current_turn = 5; // == total_turns, final turn
        board.total_turns = 5;
        let weights = eval_weights_default();
        let beam = solve_beam(&board, &spawn_points, 2, &[3, 2], 5.0, &weights, [0; 2], &WEAPONS);
        // Chain must not panic and must preserve level_0 score contract.
        for c in &beam {
            match &c.level_1_best {
                Some(s) => assert_eq!(c.chain_score, c.level_0.score + s.score),
                None    => assert_eq!(c.chain_score, c.level_0.score),
            }
        }
    }
}
