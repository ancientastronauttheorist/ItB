use itb_solver::native_rng::{canonical_msvc_state, draw_msvc_rand, replay_spawn_coordinate};
use serde::Deserialize;

const RECEIPT_JSON: &str = include_str!(
    "../../data/observatory/captures/\
windows_build_13725832_owner_local_modified_20260822_\
spawn_coordinate_state_replay_receipt.json"
);

#[derive(Debug, Deserialize)]
struct Receipt {
    kind: String,
    schema_version: u8,
    solver_conformance: SolverConformance,
    vectors: Vec<Vector>,
}

#[derive(Debug, Deserialize)]
struct SolverConformance {
    simulator_version_bump_required: bool,
}

#[derive(Debug, Deserialize)]
struct Vector {
    candidate_count: usize,
    candidates: Vec<[u8; 2]>,
    native_result_window: Vec<u16>,
    observable_post_state: u32,
    observable_pre_state: u32,
    raw_rng: u16,
    selected: [u8; 2],
    selected_index: usize,
}

#[test]
fn committed_native_selector_states_replay_all_three_coordinates() {
    let receipt: Receipt = serde_json::from_str(RECEIPT_JSON).expect("valid receipt JSON");
    assert_eq!(receipt.schema_version, 1);
    assert_eq!(
        receipt.kind,
        "observatory_spawn_coordinate_state_replay_receipt"
    );
    assert!(!receipt.solver_conformance.simulator_version_bump_required);
    assert_eq!(receipt.vectors.len(), 3);

    for vector in receipt.vectors {
        assert_eq!(vector.candidate_count, vector.candidates.len());
        assert_eq!(vector.native_result_window.len(), 3);
        let candidates: Vec<(u8, u8)> = vector
            .candidates
            .iter()
            .map(|point| (point[0], point[1]))
            .collect();
        let replay = replay_spawn_coordinate(vector.observable_pre_state, &candidates)
            .expect("nonempty native candidate vector");

        assert_eq!(replay.raw_rng, vector.raw_rng);
        assert_eq!(replay.raw_rng, vector.native_result_window[0]);
        assert_eq!(replay.selected_index, vector.selected_index);
        assert_eq!(replay.selected, (vector.selected[0], vector.selected[1]));
        assert_eq!(
            canonical_msvc_state(replay.post_state),
            vector.observable_post_state
        );

        let (second, second_state) = draw_msvc_rand(replay.post_state);
        let (third, _) = draw_msvc_rand(second_state);
        assert_eq!(second, vector.native_result_window[1]);
        assert_eq!(third, vector.native_result_window[2]);
    }
}
