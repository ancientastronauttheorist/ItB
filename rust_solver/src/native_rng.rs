//! Exact replay helpers for the pinned Windows build's observable MSVC RNG.
//!
//! These helpers are intentionally input-driven. They do not infer a future
//! native state from ordinary bridge/save data and therefore do not weaken the
//! solver's non-fabrication guard for unresolved spawns.

pub const MSVC_MULTIPLIER: u32 = 214_013;
pub const MSVC_INCREMENT: u32 = 2_531_011;
pub const MSVC_RESULT_MASK: u32 = 0x7fff;
pub const MSVC_OBSERVABLE_STATE_MASK: u32 = 0x7fff_ffff;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct NativeSpawnCoordinateReplay {
    pub raw_rng: u16,
    pub post_state: u32,
    pub selected_index: usize,
    pub selected: (u8, u8),
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
}
