//! Exact replay helpers for the pinned Windows build's observable MSVC RNG.
//!
//! These helpers are intentionally input-driven. They do not infer a future
//! native state from ordinary bridge/save data and therefore do not weaken the
//! solver's non-fabrication guard for unresolved spawns.

pub const MSVC_MULTIPLIER: u32 = 214_013;
pub const MSVC_INCREMENT: u32 = 2_531_011;
pub const MSVC_RESULT_MASK: u32 = 0x7fff;
pub const MSVC_OBSERVABLE_STATE_MASK: u32 = 0x7fff_ffff;

pub const NATIVE_TEAM_ENEMY: u8 = 6;
pub const NATIVE_TURN_ZERO_FOREST_RETRY_MODE: u8 = 9;
pub const NATIVE_TERRAIN_ROAD: u8 = 0;
pub const NATIVE_TERRAIN_WATER: u8 = 3;
pub const NATIVE_TERRAIN_REJECT_5: u8 = 5;
pub const NATIVE_TERRAIN_FOREST: u8 = 6;
pub const NATIVE_BLOCKED_TEMP: i32 = 1;
pub const NATIVE_BLOCKED_PERM: i32 = 2;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum NativeSpawnPoolKind {
    OrdinaryPrimary,
    OrdinaryTurnZeroForestRetry,
    EmergencyMaxXRow,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NativeSpawnCandidatePool {
    pub kind: NativeSpawnPoolKind,
    pub validation_mode: u8,
    pub rng_caller_id: u8,
    pub candidates: Vec<(u8, u8)>,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct NativeEnemySpawnTileFacts {
    pub has_item: bool,
    pub active_pod: bool,
    pub block_spawn: i32,
    pub dangerous: bool,
    pub blocked_for_ground: bool,
    pub terrain: u8,
    pub acid: bool,
    pub existing_spawn_marker: bool,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeSpawnCoordinateReplay {
    pub raw_rng: u16,
    pub post_state: u32,
    pub selected_index: usize,
    pub selected: (u8, u8),
}

/// Return the exact absent-`enemy`-zone fallback order.
///
/// Native fallback enumerates the last three x columns and y=2..5. Boards
/// smaller than that reviewed domain are rejected instead of fabricating
/// out-of-bounds points.
pub fn default_native_enemy_spawn_zone(width: u8, height: u8) -> Option<Vec<(u8, u8)>> {
    if width < 3 || height < 6 {
        return None;
    }
    let mut points = Vec::with_capacity(12);
    for x in (width - 3)..width {
        for y in 2..6 {
            points.push((x, y));
        }
    }
    Some(points)
}

/// Replay the ordinary enemy validity branch from explicit candidate-time
/// facts. Mode 9 is a selector/validity mode, not PATH_PHASING.
pub fn native_enemy_spawn_tile_is_valid(
    mode: u8,
    facts: NativeEnemySpawnTileFacts,
) -> Option<bool> {
    if mode != NATIVE_TEAM_ENEMY && mode != NATIVE_TURN_ZERO_FOREST_RETRY_MODE {
        return None;
    }
    Some(
        !(facts.has_item
            || facts.active_pod
            || matches!(facts.block_spawn, NATIVE_BLOCKED_TEMP | NATIVE_BLOCKED_PERM)
            || facts.dangerous
            || facts.blocked_for_ground
            || matches!(
                facts.terrain,
                NATIVE_TERRAIN_REJECT_5 | NATIVE_TERRAIN_WATER
            )
            || (facts.terrain == NATIVE_TERRAIN_FOREST
                && mode != NATIVE_TURN_ZERO_FOREST_RETRY_MODE)
            || facts.acid
            || facts.existing_spawn_marker),
    )
}

/// Return the terrain after the selector's retry-only forest cleanup.
pub fn native_spawn_selected_terrain(kind: NativeSpawnPoolKind, terrain: u8) -> u8 {
    if kind == NativeSpawnPoolKind::OrdinaryTurnZeroForestRetry && terrain == NATIVE_TERRAIN_FOREST
    {
        NATIVE_TERRAIN_ROAD
    } else {
        terrain
    }
}

/// Construct the exact ordered enemy-spawn candidate pool without drawing RNG.
///
/// The predicate is intentionally supplied by the caller. Ordinary bridge/save
/// input does not yet expose exact candidate-time Board:IsDangerous or
/// BlockSpawn values, so this helper must not be wired to future projection
/// until those inputs are present.
pub fn build_native_enemy_spawn_candidate_pool<F>(
    source: &[(u8, u8)],
    board_width: u8,
    board_height: u8,
    turn: u32,
    mut is_valid: F,
) -> Option<NativeSpawnCandidatePool>
where
    F: FnMut((u8, u8), u8) -> bool,
{
    let primary: Vec<(u8, u8)> = source
        .iter()
        .copied()
        .filter(|point| is_valid(*point, NATIVE_TEAM_ENEMY))
        .collect();
    if !primary.is_empty() {
        return Some(NativeSpawnCandidatePool {
            kind: NativeSpawnPoolKind::OrdinaryPrimary,
            validation_mode: NATIVE_TEAM_ENEMY,
            rng_caller_id: 60,
            candidates: primary,
        });
    }

    if turn == 0 {
        let retry: Vec<(u8, u8)> = source
            .iter()
            .copied()
            .filter(|point| is_valid(*point, NATIVE_TURN_ZERO_FOREST_RETRY_MODE))
            .collect();
        if !retry.is_empty() {
            return Some(NativeSpawnCandidatePool {
                kind: NativeSpawnPoolKind::OrdinaryTurnZeroForestRetry,
                validation_mode: NATIVE_TURN_ZERO_FOREST_RETRY_MODE,
                rng_caller_id: 60,
                candidates: retry,
            });
        }
    }

    let mut emergency = Vec::new();
    for x in 0..board_width {
        let mut row = Vec::new();
        for y in 0..board_height {
            let point = (x, y);
            if is_valid(point, NATIVE_TEAM_ENEMY) {
                row.push(point);
            }
        }
        if !row.is_empty() {
            emergency = row;
        }
    }
    if emergency.is_empty() {
        None
    } else {
        Some(NativeSpawnCandidatePool {
            kind: NativeSpawnPoolKind::EmergencyMaxXRow,
            validation_mode: NATIVE_TEAM_ENEMY,
            rng_caller_id: 59,
            candidates: emergency,
        })
    }
}

#[inline]
pub fn advance_msvc_state(state: u32) -> u32 {
    state
        .wrapping_mul(MSVC_MULTIPLIER)
        .wrapping_add(MSVC_INCREMENT)
}

#[inline]
pub fn canonical_msvc_state(state: u32) -> u32 {
    state & MSVC_OBSERVABLE_STATE_MASK
}

#[inline]
pub fn draw_msvc_rand(state: u32) -> (u16, u32) {
    let post_state = advance_msvc_state(state);
    let result = ((post_state >> 16) & MSVC_RESULT_MASK) as u16;
    (result, post_state)
}

/// Replay the standard native coordinate selector from an exact pre-call state.
///
/// Candidate order is semantic input. An empty vector is the native caller's
/// separate failure/fallback domain and is rejected here without advancing RNG.
pub fn replay_spawn_coordinate(
    pre_state: u32,
    candidates: &[(u8, u8)],
) -> Option<NativeSpawnCoordinateReplay> {
    if candidates.is_empty() {
        return None;
    }
    let (raw_rng, post_state) = draw_msvc_rand(pre_state);
    let selected_index = usize::from(raw_rng) % candidates.len();
    Some(NativeSpawnCoordinateReplay {
        raw_rng,
        post_state,
        selected_index,
        selected: candidates[selected_index],
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hidden_state_bit_never_changes_observable_results() {
        let low = 0x1612_29bc;
        let high = low ^ 0x8000_0000;
        let (low_result, low_post) = draw_msvc_rand(low);
        let (high_result, high_post) = draw_msvc_rand(high);

        assert_eq!(low_result, high_result);
        assert_eq!(
            canonical_msvc_state(low_post),
            canonical_msvc_state(high_post)
        );
    }

    #[test]
    fn empty_candidate_vector_does_not_fabricate_a_coordinate() {
        assert_eq!(replay_spawn_coordinate(0x1612_29bc, &[]), None);
    }

    #[test]
    fn exact_default_enemy_zone_is_x_major() {
        assert_eq!(
            default_native_enemy_spawn_zone(8, 8),
            Some(vec![
                (5, 2),
                (5, 3),
                (5, 4),
                (5, 5),
                (6, 2),
                (6, 3),
                (6, 4),
                (6, 5),
                (7, 2),
                (7, 3),
                (7, 4),
                (7, 5),
            ])
        );
        assert_eq!(default_native_enemy_spawn_zone(2, 8), None);
    }

    #[test]
    fn forest_is_retry_only_and_then_becomes_road() {
        let forest = NativeEnemySpawnTileFacts {
            terrain: NATIVE_TERRAIN_FOREST,
            ..NativeEnemySpawnTileFacts::default()
        };
        assert_eq!(
            native_enemy_spawn_tile_is_valid(NATIVE_TEAM_ENEMY, forest),
            Some(false)
        );
        assert_eq!(
            native_enemy_spawn_tile_is_valid(NATIVE_TURN_ZERO_FOREST_RETRY_MODE, forest),
            Some(true)
        );
        assert_eq!(
            native_spawn_selected_terrain(
                NativeSpawnPoolKind::OrdinaryTurnZeroForestRetry,
                NATIVE_TERRAIN_FOREST
            ),
            NATIVE_TERRAIN_ROAD
        );
    }

    #[test]
    fn explicit_enemy_tile_facts_cover_every_native_rejection() {
        let rejected = [
            NativeEnemySpawnTileFacts {
                has_item: true,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                active_pod: true,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                block_spawn: NATIVE_BLOCKED_TEMP,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                block_spawn: NATIVE_BLOCKED_PERM,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                dangerous: true,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                blocked_for_ground: true,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                terrain: NATIVE_TERRAIN_REJECT_5,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                terrain: NATIVE_TERRAIN_WATER,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                acid: true,
                ..NativeEnemySpawnTileFacts::default()
            },
            NativeEnemySpawnTileFacts {
                existing_spawn_marker: true,
                ..NativeEnemySpawnTileFacts::default()
            },
        ];
        assert!(rejected.into_iter().all(|facts| {
            native_enemy_spawn_tile_is_valid(NATIVE_TEAM_ENEMY, facts) == Some(false)
        }));
        assert_eq!(
            native_enemy_spawn_tile_is_valid(
                NATIVE_TEAM_ENEMY,
                NativeEnemySpawnTileFacts {
                    block_spawn: 3,
                    ..NativeEnemySpawnTileFacts::default()
                }
            ),
            Some(true)
        );
        assert_eq!(
            native_enemy_spawn_tile_is_valid(1, NativeEnemySpawnTileFacts::default()),
            None
        );
    }
}
