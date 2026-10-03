//! Shared completed-plan objective for compound and primitive callers.
//!
//! These counters and the terminal expression preserve the compound search's
//! scoring contract. Action admission, disabled-weapon penalty accrual and the
//! clean-building selection policy remain the caller's responsibility.

use crate::board::{count_unit_deaths_between, ActionResult, Board};
use crate::enemy::{apply_spawn_blocking, simulate_enemy_attacks};
use crate::evaluate::{consumed_spawn_block_bonus, evaluate, EvalWeights, PsionState};
use crate::solver::{
    arachnoid_spawns_from_events, boosted_from_events, core_of_the_earth_chasm_falls_from_events,
    efficient_explosives_from_events, feed_the_flame_from_events,
    lets_walk_control_distance_from_events, maximum_firepower_from_events,
    miner_inconvenience_mountain_damage_from_events, mission_missiles_action_bonus,
    powered_blast_from_events, reverse_thrusters_four_damage_from_events,
    viscera_nanobots_heal_from_events, working_together_from_events, MechAction,
};
use crate::types::Terrain;
use crate::weapons::WeaponTable;

#[derive(Default, Clone)]
pub(crate) struct PlanTotals {
    pub(crate) kills_so_far: i32,
    pub(crate) mission_kills_so_far: i32,
    pub(crate) unit_deaths_so_far: i32,
    pub(crate) bumps_so_far: i32,
    pub(crate) buildings_damaged_so_far: i32,
    pub(crate) nanobots_heal_so_far: i32,
    pub(crate) powered_blast_so_far: i32,
    pub(crate) reverse_thrusters_four_damage_so_far: i32,
    pub(crate) feed_the_flame_so_far: i32,
    pub(crate) boosted_so_far: i32,
    pub(crate) maximum_firepower_so_far: i32,
    pub(crate) arachnoid_spawns_so_far: i32,
    pub(crate) efficient_explosives_so_far: i32,
    pub(crate) working_together_so_far: i32,
    pub(crate) lets_walk_control_distance_so_far: i32,
    pub(crate) core_of_the_earth_so_far: i32,
    pub(crate) miner_inconvenience_mountain_damage_so_far: i32,
    pub(crate) stay_with_me_heal_so_far: i32,
    pub(crate) pods_collected_so_far: i32,
    pub(crate) soft_disable_penalty_so_far: f64,
}

impl PlanTotals {
    /// Record one admitted transition, using the compound search's extractors.
    /// Disabled-weapon penalties depend on the caller's weapon/mask admission,
    /// so the caller accrues `soft_disable_penalty_so_far` separately.
    pub(crate) fn record(&mut self, before: &Board, after: &Board, result: &ActionResult) {
        self.kills_so_far += result.enemies_killed;
        self.mission_kills_so_far += result.mission_kills;
        self.unit_deaths_so_far += count_unit_deaths_between(before, after);
        self.bumps_so_far += result.buildings_bump_damaged;
        self.buildings_damaged_so_far += result.buildings_damaged;
        self.nanobots_heal_so_far += viscera_nanobots_heal_from_events(&result.events);
        self.powered_blast_so_far += powered_blast_from_events(&result.events);
        self.reverse_thrusters_four_damage_so_far +=
            reverse_thrusters_four_damage_from_events(&result.events);
        self.feed_the_flame_so_far += feed_the_flame_from_events(&result.events);
        self.boosted_so_far += boosted_from_events(&result.events);
        self.maximum_firepower_so_far += maximum_firepower_from_events(&result.events);
        self.arachnoid_spawns_so_far += arachnoid_spawns_from_events(&result.events);
        self.efficient_explosives_so_far += efficient_explosives_from_events(&result.events);
        self.working_together_so_far += working_together_from_events(&result.events);
        self.lets_walk_control_distance_so_far +=
            lets_walk_control_distance_from_events(&result.events);
        self.core_of_the_earth_so_far += core_of_the_earth_chasm_falls_from_events(&result.events);
        self.miner_inconvenience_mountain_damage_so_far +=
            miner_inconvenience_mountain_damage_from_events(&result.events);
        self.stay_with_me_heal_so_far += result.mech_hp_repaired;
        self.pods_collected_so_far += result.pods_collected;
    }
}

pub(crate) struct TerminalEvaluation {
    /// Board after environment/enemy attacks and spawn blocking, without a
    /// next-turn refresh or heuristic enemy requeue.
    pub(crate) final_board: Board,
    pub(crate) score: f64,
    pub(crate) buildings_before_enemy: i32,
    pub(crate) projected_kills: i32,
    pub(crate) projected_mission_kills: i32,
    pub(crate) projected_unit_deaths: i32,
}

fn count_buildings(board: &Board) -> i32 {
    let mut count = 0;
    for tile in &board.tiles {
        if tile.terrain == Terrain::Building && tile.building_hp > 0 {
            count += 1;
        }
    }
    count
}

pub(crate) fn evaluate_terminal(
    board: &Board,
    actions: &[MechAction],
    totals: &PlanTotals,
    original_positions: &[(u8, u8); 16],
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    weapons: &WeaponTable,
    psion_before: &PsionState,
    building_threats: u64,
    allow_disabled_weapons: bool,
) -> TerminalEvaluation {
    let mut b_eval = board.clone();
    let buildings_before_enemy = count_buildings(&b_eval);
    let before_enemy_phase = b_eval.clone();
    let enemy_phase_result = simulate_enemy_attacks(&mut b_eval, original_positions, weapons);
    let enemy_phase_unit_deaths = count_unit_deaths_between(&before_enemy_phase, &b_eval);
    let before_spawn_block = b_eval.clone();
    let spawn_block_result = apply_spawn_blocking(&mut b_eval, spawn_points);
    let spawn_block_unit_deaths = count_unit_deaths_between(&before_spawn_block, &b_eval);
    let projected_kills =
        totals.kills_so_far + enemy_phase_result.enemies_killed + spawn_block_result.enemies_killed;
    let projected_mission_kills = totals.mission_kills_so_far
        + enemy_phase_result.mission_kills
        + spawn_block_result.mission_kills;
    let projected_unit_deaths =
        totals.unit_deaths_so_far + enemy_phase_unit_deaths + spawn_block_unit_deaths;
    let raw = evaluate(
        &b_eval,
        spawn_points,
        weights,
        projected_kills,
        projected_mission_kills,
        totals.bumps_so_far,
        psion_before,
        building_threats,
    ) + consumed_spawn_block_bonus(
        &b_eval,
        spawn_points,
        weights,
        spawn_block_result.spawns_blocked,
    );

    // Preserve the forced-use penalty scaling and floating-point addition
    // order of the compound search's completed-plan objective.
    let penalty_scale = if allow_disabled_weapons {
        let eff_grid_eval = b_eval.grid_power as f64
            + b_eval.enemy_grid_save_expected as f64
            + b_eval.player_grid_save_expected as f64;
        let grid_health_eval = eff_grid_eval / (b_eval.grid_power_max as f64).max(1.0);
        (weights.bld_grid_floor + weights.bld_grid_scale * grid_health_eval).max(0.1)
    } else {
        1.0
    };
    let mission_action_bonus = mission_missiles_action_bonus(&b_eval, actions);
    let nanobots_heal_bonus =
        totals.nanobots_heal_so_far as f64 * weights.viscera_nanobots_heal_bonus;
    let powered_blast_bonus = totals.powered_blast_so_far as f64 * weights.powered_blast_bonus;
    let reverse_thrusters_four_damage_bonus = totals.reverse_thrusters_four_damage_so_far as f64
        * weights.reverse_thrusters_four_damage_bonus;
    let feed_the_flame_bonus = totals.feed_the_flame_so_far as f64 * weights.feed_the_flame_bonus;
    let boosted_bonus = totals.boosted_so_far as f64 * weights.boosted_bonus;
    let maximum_firepower_bonus =
        totals.maximum_firepower_so_far as f64 * weights.maximum_firepower_bonus;
    let arachnoid_spawn_bonus =
        totals.arachnoid_spawns_so_far as f64 * weights.arachnoid_spawn_bonus;
    let efficient_explosives_bonus =
        totals.efficient_explosives_so_far as f64 * weights.efficient_explosives_bonus;
    let working_together_bonus =
        totals.working_together_so_far as f64 * weights.working_together_bonus;
    let lets_walk_control_distance_bonus =
        totals.lets_walk_control_distance_so_far as f64 * weights.lets_walk_control_distance_bonus;
    let core_of_the_earth_bonus =
        totals.core_of_the_earth_so_far as f64 * weights.core_of_the_earth_bonus;
    let miner_inconvenience_bonus = totals.miner_inconvenience_mountain_damage_so_far as f64
        * weights.miner_inconvenience_mountain_damage_bonus;
    let stay_with_me_heal_bonus =
        totals.stay_with_me_heal_so_far as f64 * weights.stay_with_me_heal_bonus;
    let no_survivors_bonus = if projected_unit_deaths >= 7 {
        projected_unit_deaths as f64 * weights.no_survivors_death_bonus
    } else {
        0.0
    };
    let pod_collected_penalty = totals.pods_collected_so_far as f64 * weights.pod_collected;
    let score = raw
        + mission_action_bonus
        + nanobots_heal_bonus
        + powered_blast_bonus
        + reverse_thrusters_four_damage_bonus
        + feed_the_flame_bonus
        + boosted_bonus
        + maximum_firepower_bonus
        + arachnoid_spawn_bonus
        + efficient_explosives_bonus
        + working_together_bonus
        + lets_walk_control_distance_bonus
        + core_of_the_earth_bonus
        + miner_inconvenience_bonus
        + stay_with_me_heal_bonus
        + no_survivors_bonus
        + pod_collected_penalty
        - totals.soft_disable_penalty_so_far * penalty_scale;

    TerminalEvaluation {
        final_board: b_eval,
        score,
        buildings_before_enemy,
        projected_kills,
        projected_mission_kills,
        projected_unit_deaths,
    }
}
