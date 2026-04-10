/// JSON serialization/deserialization bridge.
///
/// Converts bridge JSON (from /tmp/itb_state.json) into Board struct,
/// and Solution back to JSON for Python consumption.

use serde::{Deserialize, Serialize};
use crate::types::*;
use crate::board::*;
use crate::evaluate::EvalWeights;
use crate::weapons::*;
use crate::solver::{Solution, MechAction};

// ── Input JSON schema ────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct JsonInput {
    pub tiles: Option<Vec<JsonTile>>,
    pub units: Option<Vec<JsonUnit>>,
    pub grid_power: Option<u8>,
    pub grid_power_max: Option<u8>,
    pub turn: Option<u8>,
    pub total_turns: Option<u8>,
    pub spawning_tiles: Option<Vec<Vec<u8>>>,
    pub environment_danger: Option<Vec<Vec<u8>>>,
    pub environment_danger_v2: Option<Vec<Vec<u8>>>, // [[x, y, damage, kill_int], ...]
    pub eval_weights: Option<EvalWeights>,
}

#[derive(Deserialize)]
pub struct JsonTile {
    pub x: u8,
    pub y: u8,
    pub terrain: Option<String>,
    pub fire: Option<bool>,
    pub smoke: Option<bool>,
    pub acid: Option<bool>,
    pub frozen: Option<bool>,
    pub cracked: Option<bool>,
    pub pod: Option<bool>,
    pub has_pod: Option<bool>,
    pub building_hp: Option<u8>,
    pub population: Option<u8>,
    pub conveyor: Option<i8>,
}

#[derive(Deserialize)]
pub struct JsonUnit {
    pub uid: Option<u16>,
    #[serde(rename = "type")]
    pub unit_type: String,
    pub x: u8,
    pub y: u8,
    pub hp: Option<i8>,
    pub max_hp: Option<i8>,
    pub team: Option<u8>,
    pub mech: Option<bool>,
    #[serde(rename = "move")]
    pub move_speed: Option<u8>,
    pub flying: Option<bool>,
    pub armor: Option<bool>,
    pub massive: Option<bool>,
    pub pushable: Option<bool>,
    pub active: Option<bool>,
    pub shield: Option<bool>,
    pub acid: Option<bool>,
    pub frozen: Option<bool>,
    pub fire: Option<bool>,
    pub web: Option<bool>,
    pub weapons: Option<Vec<String>>,
    pub queued_target: Option<Vec<i8>>,
    pub weapon_damage: Option<u8>,
    pub weapon_target_behind: Option<bool>,
    pub weapon_push: Option<u8>,
    pub ranged: Option<u8>,
}

// ── Deserialize Board from JSON ──────────────────────────────────────────────

pub fn board_from_json(json_str: &str) -> Result<(Board, Vec<(u8, u8)>, Vec<(u8, u8)>, EvalWeights), String> {
    let input: JsonInput = serde_json::from_str(json_str)
        .map_err(|e| format!("JSON parse error: {}", e))?;
    let weights = input.eval_weights.clone().unwrap_or_default();

    let mut board = Board::default();

    // Grid power
    board.grid_power = input.grid_power.unwrap_or(7);
    board.grid_power_max = input.grid_power_max.unwrap_or(7);

    // Tiles
    if let Some(tiles) = &input.tiles {
        for jt in tiles {
            if jt.x >= 8 || jt.y >= 8 { continue; }
            let tile = board.tile_mut(jt.x, jt.y);
            tile.terrain = Terrain::from_str(jt.terrain.as_deref().unwrap_or("ground"));
            // Mountains default to 2 HP if not specified (bridge doesn't send mountain HP)
            let default_hp = if tile.terrain == Terrain::Mountain { 2 } else { 0 };
            tile.building_hp = jt.building_hp.unwrap_or(default_hp);
            tile.population = jt.population.unwrap_or(0);

            let mut flags = TileFlags::empty();
            if jt.fire.unwrap_or(false) { flags |= TileFlags::ON_FIRE; }
            if jt.smoke.unwrap_or(false) { flags |= TileFlags::SMOKE; }
            if jt.acid.unwrap_or(false) { flags |= TileFlags::ACID; }
            if jt.frozen.unwrap_or(false) { flags |= TileFlags::FROZEN; }
            if jt.cracked.unwrap_or(false) { flags |= TileFlags::CRACKED; }
            if jt.pod.unwrap_or(false) || jt.has_pod.unwrap_or(false) { flags |= TileFlags::HAS_POD; }
            tile.flags = flags;
            tile.conveyor_dir = jt.conveyor.unwrap_or(-1);
        }
    }

    // Environment danger (legacy v1: bitset of dangerous tiles)
    let mut env_danger = 0u64;
    let mut danger_tiles = Vec::new();
    if let Some(danger) = &input.environment_danger {
        for d in danger {
            if d.len() >= 2 && d[0] < 8 && d[1] < 8 {
                env_danger |= 1u64 << xy_to_idx(d[0], d[1]);
                danger_tiles.push((d[0], d[1]));
            }
        }
    }

    // Environment danger v2: per-tile {damage, kill} metadata.
    // Each entry is [x, y, damage, kill_int] where kill_int != 0 means
    // Deadly Threat (instant-kill, bypasses shield/frozen/armor/ACID).
    // v2 entries implicitly populate the v1 bitset too (a v2 entry IS a danger tile).
    // If v2 is missing entirely (older bridge), conservatively treat ALL existing
    // env_danger tiles as lethal — over-pessimistic on tidal waves but never
    // under-predicts air strike deaths.
    let mut env_danger_kill = 0u64;
    if let Some(v2) = &input.environment_danger_v2 {
        for entry in v2 {
            if entry.len() >= 4 && entry[0] < 8 && entry[1] < 8 {
                let bit = 1u64 << xy_to_idx(entry[0], entry[1]);
                env_danger |= bit;  // v2 entry is also a v1 danger tile
                if entry[3] != 0 {
                    env_danger_kill |= bit;
                }
            }
        }
    } else if env_danger != 0 {
        // Backwards compat: no v2 → assume all dangers are lethal
        env_danger_kill = env_danger;
    }
    board.env_danger = env_danger;
    board.env_danger_kill = env_danger_kill;

    // Spawn points
    let mut spawn_points = Vec::new();
    if let Some(spawns) = &input.spawning_tiles {
        for s in spawns {
            if s.len() >= 2 && s[0] < 8 && s[1] < 8 {
                spawn_points.push((s[0], s[1]));
            }
        }
    }

    // Units
    if let Some(units) = &input.units {
        for ju in units {
            if board.unit_count >= 16 { break; }

            let is_mech = ju.mech.unwrap_or(false);
            let team = Team::from_int(ju.team.unwrap_or(if is_mech { 1 } else { 6 }));
            let hp = ju.hp.unwrap_or(1);

            let mut flags = UnitFlags::empty();
            if is_mech { flags |= UnitFlags::IS_MECH; }
            if ju.flying.unwrap_or(false) { flags |= UnitFlags::FLYING; }
            if ju.massive.unwrap_or(false) { flags |= UnitFlags::MASSIVE; }
            if ju.armor.unwrap_or(false) { flags |= UnitFlags::ARMOR; }
            if ju.pushable.unwrap_or(true) { flags |= UnitFlags::PUSHABLE; }
            if ju.ranged.unwrap_or(0) > 0 { flags |= UnitFlags::RANGED; }
            if ju.active.unwrap_or(true) { flags |= UnitFlags::ACTIVE; }
            if ju.shield.unwrap_or(false) { flags |= UnitFlags::SHIELD; }
            if ju.acid.unwrap_or(false) { flags |= UnitFlags::ACID; }
            if ju.frozen.unwrap_or(false) { flags |= UnitFlags::FROZEN; }
            if ju.fire.unwrap_or(false) { flags |= UnitFlags::FIRE; }
            if ju.web.unwrap_or(false) { flags |= UnitFlags::WEB; }

            // Weapons
            let mut weapon = crate::board::WeaponId::NONE;
            let mut weapon2 = crate::board::WeaponId::NONE;
            if let Some(weapons) = &ju.weapons {
                if !weapons.is_empty() {
                    weapon = crate::board::WeaponId(wid_from_str(&weapons[0]) as u16);
                }
                if weapons.len() > 1 {
                    weapon2 = crate::board::WeaponId(wid_from_str(&weapons[1]) as u16);
                }
            }

            // Queued target
            let (qtx, qty) = if let Some(qt) = &ju.queued_target {
                if qt.len() >= 2 { (qt[0], qt[1]) } else { (-1, -1) }
            } else {
                (-1, -1)
            };

            let mut unit = Unit {
                uid: ju.uid.unwrap_or(board.unit_count as u16),
                pawn_type: PawnType(0),
                type_name: [0u8; 20],
                x: ju.x,
                y: ju.y,
                hp,
                max_hp: ju.max_hp.unwrap_or(hp),
                team,
                move_speed: ju.move_speed.unwrap_or(3),
                flags,
                weapon,
                weapon2,
                queued_target_x: qtx,
                queued_target_y: qty,
                weapon_damage: ju.weapon_damage.unwrap_or(0),
                weapon_push: ju.weapon_push.unwrap_or(0),
                weapon_target_behind: ju.weapon_target_behind.unwrap_or(false),
            };

            unit.set_type_name(&ju.unit_type);
            board.add_unit(unit);
        }
    }

    // Turn info
    board.current_turn = input.turn.unwrap_or(0);
    board.total_turns = input.total_turns.unwrap_or(5);

    // Detect Blast Psion: if Jelly_Explode1 is alive, all Vek explode on death
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Explode1" && board.units[i].hp > 0 {
            board.blast_psion = true;
            break;
        }
    }

    // Detect Shell Psion: if Jelly_Armor1 is alive, all Vek gain Armor
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Armor1" && board.units[i].hp > 0 {
            board.armor_psion = true;
            break;
        }
    }
    if board.armor_psion {
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy() {
                board.units[i].flags.set(UnitFlags::ARMOR, true);
            }
        }
    }

    // Detect Soldier Psion (Jelly_Health1): all Vek +1 HP
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Health1" && board.units[i].hp > 0 {
            board.soldier_psion = true;
            break;
        }
    }
    if board.soldier_psion {
        // Bridge sends HP already buffed but max_hp as base — adjust max_hp to match
        for i in 0..board.unit_count as usize {
            if board.units[i].is_enemy() && board.units[i].type_name_str() != "Jelly_Health1" {
                board.units[i].max_hp += 1;
            }
        }
    }

    // Detect Blood Psion (Jelly_Regen1): all Vek regen 1 HP/turn
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Regen1" && board.units[i].hp > 0 {
            board.regen_psion = true;
            break;
        }
    }

    // Detect Psion Tyrant (Jelly_Lava1): 1 dmg to all player units/turn
    for i in 0..board.unit_count as usize {
        if board.units[i].type_name_str() == "Jelly_Lava1" && board.units[i].hp > 0 {
            board.tyrant_psion = true;
            break;
        }
    }

    // Detect passive abilities from mech weapon names
    if let Some(units) = &input.units {
        for ju in units {
            if ju.mech.unwrap_or(false) {
                if let Some(weapons) = &ju.weapons {
                    for wname in weapons {
                        match wname.as_str() {
                            "Passive_Electric" => board.storm_generator = true,
                            "Passive_FlameImmune" => board.flame_shielding = true,
                            "Passive_FriendlyFire" => board.vek_hormones = true,
                            _ => {}
                        }
                    }
                }
            }
        }
    }

    Ok((board, spawn_points, danger_tiles, weights))
}

// ── Serialize Solution to JSON ───────────────────────────────────────────────

#[derive(Serialize)]
struct JsonOutput {
    actions: Vec<JsonAction>,
    score: f64,
    stats: JsonStats,
}

#[derive(Serialize)]
struct JsonAction {
    mech_uid: u16,
    mech_type: String,
    move_to: [u8; 2],
    weapon: String,
    weapon_id: String,
    target: [u8; 2],
    description: String,
}

#[derive(Serialize)]
struct JsonStats {
    elapsed: f64,
    timed_out: bool,
    permutations_tried: usize,
    total_permutations: usize,
}

pub fn solution_to_json(solution: &Solution) -> String {
    let actions: Vec<JsonAction> = solution.actions.iter().map(|a| {
        JsonAction {
            mech_uid: a.mech_uid,
            mech_type: a.mech_type.clone(),
            move_to: [a.move_to.0, a.move_to.1],
            weapon: weapon_name(a.weapon).to_string(),
            weapon_id: wid_to_str(a.weapon).to_string(),
            target: [a.target.0, a.target.1],
            description: a.description.clone(),
        }
    }).collect();

    let output = JsonOutput {
        actions,
        score: solution.score,
        stats: JsonStats {
            elapsed: solution.elapsed_secs,
            timed_out: solution.timed_out,
            permutations_tried: solution.permutations_tried,
            total_permutations: solution.total_permutations,
        },
    };

    serde_json::to_string(&output).unwrap_or_else(|_| "{}".to_string())
}
