//! Offline atomic planner. Its `steps` wire format is not a live action batch.
//! Ordinary once-per-turn readiness; extra movement/use grants stay unsupported.
use crate::board::{ActionResult, Board, UnitFlags};
use crate::evaluate::{EvalWeights, PsionState};
use crate::movement::{illegal_move_reason, reachable_tiles};
use crate::plan_evaluation::{evaluate_terminal, PlanTotals, TerminalEvaluation};
use crate::simulate::{
    finalize_player_transition, simulate_action_with_target2, simulate_attack_with_target2,
};
use crate::solver::{
    count_buildings, enumerate_actions, get_weapon_target_area, get_weapon_targets, make_action, player_plan_is_clean,
    precompute_threats, prefer_clean_score, MechAction,
};
use crate::types::DisabledMask;
use crate::weapons::*;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::time::{Duration, Instant};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::board::{Unit, WeaponId};
    use crate::types::{Team, Terrain};

    fn actor(uid: u16, x: u8, y: u8, weapon: WId) -> Unit {
        let mut unit = Unit {
            uid,
            x,
            y,
            hp: 3,
            max_hp: 3,
            move_speed: 3,
            team: Team::Player,
            weapon: WeaponId(weapon as u16),
            flags: UnitFlags::IS_MECH
                | UnitFlags::MASSIVE
                | UnitFlags::ACTIVE
                | UnitFlags::CAN_MOVE
                | UnitFlags::PUSHABLE,
            ..Default::default()
        };
        unit.set_type_name(if weapon == WId::BruteTankmech {
            "TankMech"
        } else {
            "PunchMech"
        });
        unit
    }
    fn witness() -> Board {
        let mut board = Board::default();
        for tile in &mut board.tiles {
            tile.terrain = Terrain::Chasm;
        }
        for (x, y) in [
            (0, 3),
            (1, 3),
            (2, 3),
            (3, 3),
            (4, 3),
            (3, 4),
            (4, 4),
            (5, 4),
            (5, 3),
        ] {
            board.tile_mut(x, y).terrain = Terrain::Ground;
        }
        for (x, y) in [(4, 2), (6, 3)] {
            board.tile_mut(x, y).terrain = Terrain::Building;
            board.tile_mut(x, y).building_hp = 2;
        }
        board.add_unit(actor(0, 3, 3, WId::BruteTankmech));
        board.add_unit(actor(1, 0, 3, WId::PrimePunchmech));
        let mut enemy = Unit {
            uid: 2,
            x: 4,
            y: 3,
            hp: 3,
            max_hp: 3,
            team: Team::Enemy,
            weapon: WeaponId(WId::FireflyAtk1 as u16),
            queued_target_x: 6,
            queued_target_y: 3,
            flags: UnitFlags::PUSHABLE | UnitFlags::HAS_QUEUED_ATTACK,
            ..Default::default()
        };
        enemy.set_type_name("Firefly1");
        board.add_unit(enemy);
        board.current_turn = 1;
        board.total_turns = 1;
        board
    }
    fn steps() -> Vec<Step> {
        vec![
            Step::Move {
                mech_uid: 0,
                to: [5, 4],
            },
            Step::Move {
                mech_uid: 1,
                to: [3, 3],
            },
            Step::Use {
                mech_uid: 1,
                weapon_id: "Prime_Punchmech".into(),
                target: [4, 3],
                target2: None,
            },
            Step::Use {
                mech_uid: 0,
                weapon_id: "Brute_Tankmech".into(),
                target: [5, 3],
                target2: None,
            },
        ]
    }

    #[test]
    fn interleaved_witness_saves_buildings_and_beats_compound() {
        let board = witness();
        let weights = EvalWeights::default();
        let compound =
            crate::solver::solve_turn(&board, &[], 5.0, 99999, &weights, [0; 2], &WEAPONS);
        let replay: Value = serde_json::from_str(
            &replay(&board, &steps(), &[], &weights, [0; 2], &WEAPONS).unwrap(),
        )
        .unwrap();
        assert!(replay["complete"].as_bool().unwrap());
        assert_eq!(replay["projected_kills"], 1);
        assert_eq!(replay["final_board"]["grid_power"], 7);
        assert_eq!(replay["score"], 70420.0);
        assert!(replay["score"].as_f64().unwrap() > compound.score + 8000.0);
        let selected: Value =
            serde_json::from_str(&solve(&board, &[], &weights, [0; 2], &WEAPONS, 5.0).unwrap())
                .unwrap();
        assert_eq!(selected["score"], replay["score"]);
        assert_eq!(selected["proof_status"], "best_found");
        assert!(selected["certificate"].is_null() && selected["valid_bounds"].is_null());
    }
    #[test]
    fn base_tank_and_punch_keep_building_bound_directions() {
        let mut board = Board::default();
        board.add_unit(actor(0, 3, 3, WId::BruteTankmech));
        let expected = vec![(2, 3), (3, 2), (3, 4), (4, 3)];
        for &(x, y) in &expected {
            board.tile_mut(x, y).terrain = Terrain::Building;
            board.tile_mut(x, y).building_hp = 2;
        }
        for weapon in [WId::BruteTankmech, WId::PrimePunchmech] {
            let mut actual = get_weapon_targets(&board, 3, 3, weapon, (3, 3), &WEAPONS);
            actual.sort();
            assert_eq!(actual, expected);
        }
    }
    #[test]
    fn move_preserves_use_but_spends_movement_and_rejects_reuse() {
        let board = witness();
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let initial = State::new(&board);
        let (moved, _) = apply(&initial, &steps()[0], &context, 0).unwrap();
        assert!(moved.board.units[0].active());
        assert!(!moved.board.units[0].can_move());
        assert!(apply(
            &moved,
            &Step::Move {
                mech_uid: 0,
                to: [4, 4]
            },
            &context,
            1
        )
        .err()
        .unwrap()
        .contains("movement_spent"));
        let (used, _) = apply(&moved, &Step::Wait { mech_uid: 0 }, &context, 1).unwrap();
        assert!(!used.board.units[0].active());
        assert!(apply(&used, &Step::Wait { mech_uid: 0 }, &context, 2).is_err());
        assert!(apply(
            &initial,
            &Step::Move {
                mech_uid: 0,
                to: [3, 3]
            },
            &context,
            0
        )
        .is_err());
    }
    #[test]
    fn use_without_move_closes_movement_and_repair_can_be_full_hp() {
        let board = witness();
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let repair = Step::Use {
            mech_uid: 0,
            weapon_id: "_REPAIR".into(),
            target: [3, 3],
            target2: None,
        };
        let (used, _) = apply(&State::new(&board), &repair, &context, 0).unwrap();
        assert_eq!(used.board.units[0].hp, 3);
        assert!(!used.board.units[0].active() && !used.board.units[0].can_move());
        assert!(apply(
            &used,
            &Step::Move {
                mech_uid: 0,
                to: [3, 4]
            },
            &context,
            1
        )
        .is_err());
    }
    #[test]
    fn pushed_unacted_actor_keeps_its_entitlements() {
        let mut board = Board::default();
        board.add_unit(actor(0, 1, 3, WId::PrimePunchmech));
        board.add_unit(actor(1, 2, 3, WId::BruteTankmech));
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let punch = Step::Use {
            mech_uid: 0,
            weapon_id: "Prime_Punchmech".into(),
            target: [2, 3],
            target2: None,
        };
        let (pushed, _) = apply(&State::new(&board), &punch, &context, 0).unwrap();
        assert_eq!((pushed.board.units[1].x, pushed.board.units[1].y), (3, 3));
        assert!(!pushed.entitlements[&1].moved && !pushed.entitlements[&1].used);
        assert!(apply(
            &pushed,
            &Step::Move {
                mech_uid: 1,
                to: [3, 4]
            },
            &context,
            1
        )
        .is_ok());
    }
    #[test]
    fn dead_and_unequipped_uses_reject_without_mutating_prefix() {
        let board = witness();
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let mut state = State::new(&board);
        state.board.units[0].hp = 0;
        assert!(apply(&state, &steps()[0], &context, 0).is_err());
        let state = State::new(&board);
        assert!(apply(
            &state,
            &Step::Use {
                mech_uid: 0,
                weapon_id: "Prime_Punchmech".into(),
                target: [4, 3],
                target2: None
            },
            &context,
            0
        )
        .is_err());
        assert_eq!((state.board.units[0].x, state.board.units[0].y), (3, 3));
    }
    #[test]
    fn wait_does_not_pick_up_current_tile_items() {
        let mut board = Board::default();
        board.add_unit(actor(0, 1, 1, WId::BruteTankmech));
        board.tile_mut(1, 1).set_has_pod(true);
        board.tile_mut(1, 1).set_acid(true);
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let (waited, result) = apply(
            &State::new(&board),
            &Step::Wait { mech_uid: 0 },
            &context,
            0,
        )
        .unwrap();
        assert!(waited.board.tile(1, 1).has_pod() && waited.board.tile(1, 1).acid());
        assert!(!waited.board.units[0].acid());
        assert_eq!(result.pods_collected, 0);
    }

    #[test]
    fn use_and_repair_do_not_repeat_landing_pickups() {
        let mut board = Board::default();
        board.add_unit(actor(0, 1, 1, WId::BruteTankmech));
        board.tile_mut(1, 1).set_has_pod(true);
        board.tile_mut(1, 1).set_acid(true);
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        for (weapon, target) in [("Brute_Tankmech", [1, 2]), ("_REPAIR", [1, 1])] {
            let step = Step::Use {
                mech_uid: 0,
                weapon_id: weapon.into(),
                target,
                target2: None,
            };
            let (used, result) = apply(&State::new(&board), &step, &context, 0).unwrap();
            assert!(used.board.tile(1, 1).has_pod() && used.board.tile(1, 1).acid());
            assert!(!used.board.units[0].acid());
            assert_eq!(result.pods_collected, 0);
        }
    }
    #[test]
    fn dynamic_armed_nonmech_admission_is_required_before_completion() {
        let mut board = Board::default();
        board.add_unit(actor(0, 1, 1, WId::BruteTankmech));
        let weights = EvalWeights::default();
        let context = Context::new(&board, &[], &weights, &WEAPONS, [0; 2]);
        let (mut state, _) = apply(
            &State::new(&board),
            &Step::Wait { mech_uid: 0 },
            &context,
            0,
        )
        .unwrap();
        assert!(state.complete());
        let mut ally = actor(10, 4, 4, WId::BruteTankmech);
        ally.flags.remove(UnitFlags::IS_MECH);
        ally.set_type_name("ArchiveTank");
        state.board.add_unit(ally);
        state.admit(1);
        assert!(!state.complete());
        assert_eq!(state.admissions.len(), 2);
        assert!(apply(&state, &Step::Wait { mech_uid: 10 }, &context, 1)
            .unwrap()
            .0
            .complete());
    }

    #[test]
    fn hacking_conversion_admits_fresh_armed_actor_before_completion() {
        // Synthetic callback regression, not an original-game timing observation.
        let input = json!({
            "mission_id":"Mission_Hacking", "mission_hacking_bot_id":41,
            "mission_hacking_hack_id":40, "tiles":[], "units":[
                {"uid":1,"type":"TankMech","x":3,"y":3,"hp":3,"max_hp":3,
                 "team":1,"mech":true,"move":3,"active":true,
                 "weapons":["Brute_Tankmech"]},
                {"uid":40,"type":"Hacked_Building","x":3,"y":4,"hp":1,
                 "max_hp":1,"team":6,"minor":true},
                {"uid":41,"type":"Snowtank1","x":5,"y":4,"hp":3,"max_hp":3,
                 "team":6,"shield":true,"weapons":["SnowtankAtk1"]}
            ], "grid_power":7,"grid_max":7,"spawning":[],
            "environment_danger":[],"remaining_spawns":0,"turn":1,"total_turns":5
        });
        let (board, _, _, weights, disabled, _) =
            crate::serde_bridge::board_from_json(&input.to_string()).unwrap();
        let context = Context::new(&board, &[], &weights, &WEAPONS, disabled);
        let shot = Step::Use {
            mech_uid: 1,
            weapon_id: "Brute_Tankmech".into(),
            target: [3, 4],
            target2: None,
        };
        let (converted, _) = apply(&State::new(&board), &shot, &context, 0).unwrap();
        assert_eq!(converted.board.mission_hacking_bot_id, Some(42));
        assert!(converted.entitlements[&1].used);
        assert!(!converted.entitlements[&42].used);
        assert!(!converted.complete());
        let bot = converted.board.units[..converted.board.unit_count as usize]
            .iter()
            .find(|u| u.uid == 42)
            .unwrap();
        assert!(bot.active() && bot.can_move() && !bot.is_mech());
        assert_eq!(bot.type_name_str(), "Snowtank1_Player");
        let (finished, _) = apply(&converted, &Step::Wait { mech_uid: 42 }, &context, 1).unwrap();
        assert!(finished.complete());
    }
    #[test]
    fn zero_budget_is_explicitly_incomplete_without_fake_score() {
        let board = witness();
        let weights = EvalWeights::default();
        let result: Value =
            serde_json::from_str(&solve(&board, &[], &weights, [0; 2], &WEAPONS, 0.0).unwrap())
                .unwrap();
        assert!(result["score"].is_null());
        assert_eq!(result["stats"]["terminal_plans_evaluated"], 0);
        assert_eq!(result["stats"]["deadline_cutoffs"], 1);
        assert_eq!(result["generated_tree_exhausted"], false);
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum Step {
    Move {
        mech_uid: u16,
        to: [u8; 2],
    },
    Use {
        mech_uid: u16,
        weapon_id: String,
        target: [u8; 2],
        #[serde(default, skip_serializing_if = "Option::is_none")]
        target2: Option<[u8; 2]>,
    },
    Wait {
        mech_uid: u16,
    },
}
impl Step {
    fn uid(&self) -> u16 {
        match self {
            Self::Move { mech_uid, .. } | Self::Use { mech_uid, .. } | Self::Wait { mech_uid } => {
                *mech_uid
            }
        }
    }
}

#[derive(Clone, Serialize)]
struct Entitlement {
    uid: u16,
    moved: bool,
    used: bool,
}
#[derive(Clone)]
struct State {
    board: Board,
    entitlements: BTreeMap<u16, Entitlement>,
    admissions: Vec<Value>,
    totals: PlanTotals,
    actions: Vec<MechAction>,
}
impl State {
    fn new(board: &Board) -> Self {
        let mut state = Self {
            board: board.clone(),
            entitlements: BTreeMap::new(),
            admissions: Vec::new(),
            totals: PlanTotals::default(),
            actions: Vec::new(),
        };
        state.admit(0);
        state
    }
    fn admit(&mut self, step_index: usize) {
        for unit in self.board.units.iter().take(self.board.unit_count as usize) {
            if unit.is_player_action_unit() && !self.entitlements.contains_key(&unit.uid) {
                self.entitlements.insert(
                    unit.uid,
                    Entitlement {
                        uid: unit.uid,
                        moved: !unit.can_move(),
                        used: false,
                    },
                );
                self.admissions
                    .push(json!({"uid":unit.uid,"step_index":step_index,
                    "mech":unit.is_mech(),"source":"current_model_active_player_actor"}));
            }
        }
    }
    fn eligible(&self, idx: usize) -> bool {
        let unit = &self.board.units[idx];
        unit.is_player_action_unit()
            && self
                .entitlements
                .get(&unit.uid)
                .map(|e| !e.used)
                .unwrap_or(false)
    }
    fn complete(&self) -> bool {
        !(0..self.board.unit_count as usize).any(|idx| self.eligible(idx))
    }
}

struct Context<'a> {
    positions: [(u8, u8); 16],
    spawn_points: &'a [(u8, u8)],
    weights: &'a EvalWeights,
    weapons: &'a WeaponTable,
    disabled: DisabledMask,
    psions: PsionState,
    building_threats: u64,
    initial_buildings: i32,
}
impl<'a> Context<'a> {
    fn new(
        board: &Board,
        spawn_points: &'a [(u8, u8)],
        weights: &'a EvalWeights,
        weapons: &'a WeaponTable,
        disabled: DisabledMask,
    ) -> Self {
        let mut positions = [(0, 0); 16];
        for i in 0..board.unit_count as usize {
            positions[i] = (board.units[i].x, board.units[i].y);
        }
        Self {
            positions,
            spawn_points,
            weights,
            weapons,
            disabled,
            psions: PsionState::capture(board),
            building_threats: precompute_threats(board).1,
            initial_buildings: count_buildings(board),
        }
    }
    fn terminal(&self, state: &State) -> TerminalEvaluation {
        evaluate_terminal(
            &state.board,
            &state.actions,
            &state.totals,
            &self.positions,
            self.spawn_points,
            self.weights,
            self.weapons,
            &self.psions,
            self.building_threats,
            false,
        )
    }
    fn clean(&self, state: &State, terminal: &TerminalEvaluation) -> bool {
        player_plan_is_clean(
            self.initial_buildings,
            terminal.buildings_before_enemy,
            state.totals.buildings_damaged_so_far,
        )
    }
    fn disabled(&self, weapon: WId) -> bool {
        let bit = weapon as usize;
        ((self.disabled[bit / 128] >> (bit % 128)) & 1) != 0
    }
}

fn paired(weapon: WId) -> bool {
    is_force_swap(weapon)
        || is_control_shot(weapon)
        || is_deploy_bomb_two_click(weapon)
        || is_quick_fire_rockets(weapon)
        || is_ricochet_rocket(weapon)
}

/// Validates first and mutates a clone. A rejected step never changes the prefix.
fn apply(
    state: &State,
    step: &Step,
    context: &Context,
    step_index: usize,
) -> Result<(State, ActionResult), String> {
    let uid = step.uid();
    let idx = (0..state.board.unit_count as usize)
        .find(|&i| state.board.units[i].uid == uid && !state.board.units[i].is_extra_tile())
        .ok_or_else(|| format!("unknown_actor:{uid}"))?;
    if !state.eligible(idx) {
        return Err(format!("actor_not_ready:{uid}"));
    }
    let unit = &state.board.units[idx];
    let pos = (unit.x, unit.y);
    let mut next = state.clone();
    let (result, legacy) = match step {
        Step::Move { to, .. } => {
            if state.entitlements[&uid].moved || !unit.can_move() {
                return Err(format!("movement_spent:{uid}"));
            }
            let to = (to[0], to[1]);
            if to == pos {
                return Err(format!("noop_move:{uid}"));
            }
            if let Some(reason) = illegal_move_reason(&state.board, idx, to) {
                return Err(format!("illegal_move:{uid}:{reason}"));
            }
            let result = simulate_action_with_target2(
                &mut next.board,
                idx,
                to,
                WId::None,
                (255, 255),
                None,
                context.weapons,
            );
            next.entitlements.get_mut(&uid).unwrap().moved = true;
            next.board.units[idx].flags.remove(UnitFlags::CAN_MOVE);
            (result, make_action(unit, to, WId::None, (255, 255), None))
        }
        Step::Use {
            weapon_id,
            target,
            target2,
            ..
        } => {
            let weapon = wid_from_str(weapon_id);
            if weapon == WId::None {
                return Err(format!("unknown_weapon:{weapon_id}"));
            }
            if !unit.powered() {
                return Err(format!("actor_unpowered:{uid}"));
            }
            if context.disabled(weapon) {
                return Err(format!("disabled_weapon:{weapon_id}"));
            }
            if weapon != WId::Repair
                && unit.weapon.0 != weapon as u16
                && unit.weapon2.0 != weapon as u16
            {
                return Err(format!("weapon_not_equipped:{uid}:{weapon_id}"));
            }
            if unit.frozen() && weapon != WId::Repair {
                return Err(format!("actor_frozen:{uid}"));
            }
            let target = (target[0], target[1]);
            let second = target2.map(|v| (v[0], v[1]));
            if weapon == WId::Repair {
                if target != pos || second.is_some() {
                    return Err("invalid_repair_target".into());
                }
            } else if paired(weapon) {
                let mut stationary = state.board.clone();
                stationary.units[idx].flags.remove(UnitFlags::CAN_MOVE);
                if !enumerate_actions(&stationary, idx, context.weapons)
                    .iter()
                    .any(|&a| a == (pos, weapon, target, second))
                {
                    return Err("invalid_paired_target".into());
                }
            } else if second.is_some()
                || !get_weapon_target_area(&state.board, pos.0, pos.1, weapon, pos, context.weapons)
                    .contains(&target)
            {
                return Err("invalid_weapon_target".into());
            }
            let result = simulate_attack_with_target2(
                &mut next.board,
                idx,
                weapon,
                target,
                second,
                context.weapons,
            );
            finalize_player_transition(&mut next.board, &result);
            if result.events.iter().any(|e| e.starts_with("illegal_")) {
                return Err(format!("rejected_model_action:{}", result.events.join(";")));
            }
            let entitlement = next.entitlements.get_mut(&uid).unwrap();
            entitlement.used = true;
            entitlement.moved = true;
            next.board.units[idx]
                .flags
                .remove(UnitFlags::ACTIVE | UnitFlags::CAN_MOVE);
            (result, make_action(unit, pos, weapon, target, second))
        }
        Step::Wait { .. } => {
            let entitlement = next.entitlements.get_mut(&uid).unwrap();
            entitlement.used = true;
            entitlement.moved = true;
            next.board.units[idx]
                .flags
                .remove(UnitFlags::ACTIVE | UnitFlags::CAN_MOVE);
            // Finalize without a same-position move or landing/item pickup.
            let result = simulate_attack_with_target2(
                &mut next.board,
                idx,
                WId::None,
                (255, 255),
                None,
                context.weapons,
            );
            finalize_player_transition(&mut next.board, &result);
            (result, make_action(unit, pos, WId::None, (255, 255), None))
        }
    };
    next.totals.record(&state.board, &next.board, &result);
    next.actions.push(legacy);
    next.admit(step_index + 1);
    Ok((next, result))
}

fn candidates(state: &State, context: &Context) -> Vec<Step> {
    let mut steps = Vec::new();
    let mut actors: Vec<_> = (0..state.board.unit_count as usize)
        .filter(|&i| state.eligible(i))
        .collect();
    actors.sort_by_key(|&i| state.board.units[i].uid);
    for idx in actors {
        let unit = &state.board.units[idx];
        let uid = unit.uid;
        let pos = (unit.x, unit.y);
        if !state.entitlements[&uid].moved && unit.can_move() {
            let mut stops = reachable_tiles(&state.board, idx);
            stops.sort();
            stops.dedup();
            for to in stops {
                if to != pos {
                    steps.push(Step::Move {
                        mech_uid: uid,
                        to: [to.0, to.1],
                    });
                }
            }
        }
        for raw in [unit.weapon.0, unit.weapon2.0] {
            let weapon = WId::from_raw(raw);
            if weapon == WId::None || context.disabled(weapon) {
                continue;
            }
            if paired(weapon) {
                let mut stationary = state.board.clone();
                stationary.units[idx].flags.remove(UnitFlags::CAN_MOVE);
                for (_, w, target, second) in enumerate_actions(&stationary, idx, context.weapons) {
                    if w == weapon {
                        steps.push(Step::Use {
                            mech_uid: uid,
                            weapon_id: wid_to_str(w).into(),
                            target: [target.0, target.1],
                            target2: second.map(|s| [s.0, s.1]),
                        });
                    }
                }
            } else {
                for target in
                    get_weapon_targets(&state.board, pos.0, pos.1, weapon, pos, context.weapons)
                {
                    steps.push(Step::Use {
                        mech_uid: uid,
                        weapon_id: wid_to_str(weapon).into(),
                        target: [target.0, target.1],
                        target2: None,
                    });
                }
            }
        }
        steps.push(Step::Use {
            mech_uid: uid,
            weapon_id: "_REPAIR".into(),
            target: [pos.0, pos.1],
            target2: None,
        });
        steps.push(Step::Wait { mech_uid: uid });
    }
    // Duplicate weapon slots must not create duplicate branches.
    let mut unique = Vec::with_capacity(steps.len());
    for step in steps {
        if !unique.contains(&step) {
            unique.push(step);
        }
    }
    unique
}

fn board_value(board: &Board, spawn_points: &[(u8, u8)]) -> Value {
    serde_json::from_str(&crate::turn_projection::board_to_json(board, spawn_points)).unwrap()
}
fn scope() -> Value {
    json!({"readiness":"ordinary_once_per_turn; no extra movement/use grants",
        "action_generation":"current Rust target/path model; paired target generator retains its existing filters",
        "actor_admission":"dynamic currently active controllable player actors, including armed non-mechs",
        "transition_boundary":"Move delegates to simulate_action(None); Use/Wait use attack-only update and shared finalization without movement/landing",
        "disabled_policy":"hard exclusion, no forced-use fallback",
        "execution":"offline steps API; not compatible with legacy live actions batches",
        "original_transition_fidelity":"unproved","information_admission":"caller must supply fair admitted inputs"})
}

pub fn replay(
    board: &Board,
    steps: &[Step],
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    disabled: DisabledMask,
    weapons: &WeaponTable,
) -> Result<String, String> {
    replay_with_inspection(board, steps, spawn_points, weights, disabled, weapons, false)
}

/// Opt-in whole typed Board representation for offline reduction checks.
/// This build-local Debug representation is not a portable state protocol.
pub fn replay_with_inspection(
    board: &Board,
    steps: &[Step],
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    disabled: DisabledMask,
    weapons: &WeaponTable,
    include_internal_state: bool,
) -> Result<String, String> {
    let context = Context::new(board, spawn_points, weights, weapons, disabled);
    let mut state = State::new(board);
    let mut results = Vec::new();
    for (i, step) in steps.iter().enumerate() {
        let (next, result) = apply(&state, step, &context, i)?;
        results.push(
            json!({"events":result.events,"buildings_damaged":result.buildings_damaged,
            "buildings_lost":result.buildings_lost,"grid_damage":result.grid_damage,
            "enemies_killed":result.enemies_killed,"mech_damage_taken":result.mech_damage_taken,
            "mech_hp_repaired":result.mech_hp_repaired,
            "buildings_bump_damaged":result.buildings_bump_damaged,
            "mission_kills":result.mission_kills,"unit_deaths":result.unit_deaths,
            "leech_credit_kills":result.leech_credit_kills,"leech_uncapped_kills":result.leech_uncapped_kills,
            "enemy_damage_dealt":result.enemy_damage_dealt,"mechs_killed":result.mechs_killed,
            "pods_collected":result.pods_collected,"repair_platforms_used":result.repair_platforms_used,
            "spawns_blocked":result.spawns_blocked}),
        );
        state = next;
    }
    let complete = state.complete();
    let terminal = complete.then(|| context.terminal(&state));
    Ok(
        json!({"schema_version":1,"scope":scope(),"complete":complete,
            "post_player_board":board_value(&state.board,spawn_points),
            "actor_entitlements":state.entitlements.values().collect::<Vec<_>>(),
            "admissions":state.admissions,"action_results":results,
            "objective_totals":state.totals,
            "model_internal_board":include_internal_state.then(|| format!("{:?}",state.board)),
            "score":terminal.as_ref().map(|t| t.score),
            "clean":terminal.as_ref().map(|t| context.clean(&state,t)),
            "final_board":terminal.as_ref().map(|t| board_value(&t.final_board,spawn_points)),
            "projected_kills":terminal.as_ref().map(|t| t.projected_kills),
            "projected_mission_kills":terminal.as_ref().map(|t| t.projected_mission_kills),
            "projected_unit_deaths":terminal.as_ref().map(|t| t.projected_unit_deaths)
        })
        .to_string(),
    )
}

#[derive(Default, Serialize)]
struct Stats {
    nodes_visited: u64,
    terminal_plans_evaluated: u64,
    steps_generated: u64,
    rejected_steps: u64,
    rejected_by_reason: BTreeMap<String, u64>,
    deadline_cutoffs: u64,
    depth_cutoffs: u64,
    max_depth: usize,
}
struct Best {
    score: f64,
    steps: Vec<Step>,
}
struct Search<'a, 'b> {
    context: &'a Context<'b>,
    deadline: Instant,
    stats: Stats,
    raw: Option<Best>,
    clean: Option<Best>,
}
impl Search<'_, '_> {
    fn visit(&mut self, state: &State, steps: &mut Vec<Step>) {
        if Instant::now() >= self.deadline {
            self.stats.deadline_cutoffs += 1;
            return;
        }
        self.stats.nodes_visited += 1;
        self.stats.max_depth = self.stats.max_depth.max(steps.len());
        if state.complete() {
            let terminal = self.context.terminal(state);
            let score = terminal.score;
            if self.raw.as_ref().map(|b| score > b.score).unwrap_or(true) {
                self.raw = Some(Best {
                    score,
                    steps: steps.clone(),
                });
            }
            if self.context.clean(state, &terminal)
                && self.clean.as_ref().map(|b| score > b.score).unwrap_or(true)
            {
                self.clean = Some(Best {
                    score,
                    steps: steps.clone(),
                });
            }
            self.stats.terminal_plans_evaluated += 1;
            return;
        }
        if steps.len() >= 64 {
            self.stats.depth_cutoffs += 1;
            return;
        }
        let choices = candidates(state, self.context);
        self.stats.steps_generated += choices.len() as u64;
        for step in choices {
            if Instant::now() >= self.deadline {
                self.stats.deadline_cutoffs += 1;
                return;
            }
            match apply(state, &step, self.context, steps.len()) {
                Ok((next, _)) => {
                    steps.push(step);
                    self.visit(&next, steps);
                    steps.pop();
                }
                Err(reason) => {
                    self.stats.rejected_steps += 1;
                    *self
                        .stats
                        .rejected_by_reason
                        .entry(reason.split(':').next().unwrap().to_string())
                        .or_default() += 1;
                }
            }
        }
    }
}
pub fn solve(
    board: &Board,
    spawn_points: &[(u8, u8)],
    weights: &EvalWeights,
    disabled: DisabledMask,
    weapons: &WeaponTable,
    budget: f64,
) -> Result<String, String> {
    if !budget.is_finite() || budget < 0.0 {
        return Err("invalid_budget".into());
    }
    let duration = Duration::try_from_secs_f64(budget).map_err(|_| "invalid_budget")?;
    let start = Instant::now();
    let deadline = start.checked_add(duration).ok_or("invalid_budget")?;
    let context = Context::new(board, spawn_points, weights, weapons, disabled);
    let mut search = Search {
        context: &context,
        deadline,
        stats: Stats::default(),
        raw: None,
        clean: None,
    };
    search.visit(&State::new(board), &mut Vec::new());
    let raw_score = search.raw.as_ref().map(|b| b.score);
    let clean_score = search.clean.as_ref().map(|b| b.score);
    let prefer_clean = match (raw_score, clean_score) {
        (Some(r), Some(c)) => prefer_clean_score(r, c, weights),
        _ => false,
    };
    let best = if prefer_clean {
        search.clean
    } else {
        search.raw
    };
    Ok(json!({"schema_version":1,"proof_status":"best_found","certificate":null,"valid_bounds":null,
        "horizon_player_turns":1,"scope":scope(),"steps":best.as_ref().map(|b|b.steps.clone()).unwrap_or_default(),
        "score":best.as_ref().map(|b|b.score),"raw_best_score":raw_score,"clean_best_score":clean_score,
        "clean_selected":prefer_clean,"elapsed_seconds":start.elapsed().as_secs_f64(),"budget_seconds":budget,
        "generated_tree_exhausted":search.stats.deadline_cutoffs==0 && search.stats.depth_cutoffs==0,
        "stats":search.stats}).to_string())
}
