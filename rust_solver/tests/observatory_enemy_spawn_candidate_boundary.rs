use itb_solver::native_rng::{
    build_native_enemy_spawn_candidate_pool, default_native_enemy_spawn_zone,
    replay_spawn_coordinate, NativeSpawnPoolKind,
};
use serde::Deserialize;

const BOUNDARY_JSON: &str = include_str!(
    "../../data/observatory/native/\
windows_build_13725832_31fe35265598_enemy_spawn_candidate_boundary.json"
);

#[derive(Debug, Deserialize)]
struct Boundary {
    analysis_kind: String,
    replay_vectors: Vec<ReplayVector>,
    capture_join: CaptureJoin,
    solver_impact: SolverImpact,
}

#[derive(Debug, Deserialize)]
struct ReplayVector {
    source_points: Vec<[u8; 2]>,
    board_dimensions: [u8; 2],
    turn: u32,
    valid_points: Vec<ValidPoints>,
    expected: ExpectedPool,
}

#[derive(Debug, Deserialize)]
struct ValidPoints {
    mode: u8,
    points: Vec<[u8; 2]>,
}

#[derive(Debug, Deserialize)]
struct ExpectedPool {
    pool_kind: String,
    validation_mode: Option<u8>,
    rng_caller_id: Option<u8>,
    candidates: Vec<[u8; 2]>,
    rng_consumed: bool,
}

#[derive(Debug, Deserialize)]
struct CaptureJoin {
    observable_pre_state: u32,
    raw_rng: u16,
    candidates: Vec<[u8; 2]>,
    selected_index: usize,
    selected: [u8; 2],
}

#[derive(Debug, Deserialize)]
struct SolverImpact {
    production_forecast_enabled: bool,
    simulator_version_bump_required: bool,
    current_simulator_version: u16,
}

fn expected_kind(value: &str) -> Option<NativeSpawnPoolKind> {
    match value {
        "ordinary_primary" => Some(NativeSpawnPoolKind::OrdinaryPrimary),
        "ordinary_turn_zero_forest_retry" => Some(NativeSpawnPoolKind::OrdinaryTurnZeroForestRetry),
        "emergency_max_x_row" => Some(NativeSpawnPoolKind::EmergencyMaxXRow),
        "failure" => None,
        other => panic!("unknown committed pool kind: {other}"),
    }
}

#[test]
fn committed_candidate_vectors_replay_every_native_branch() {
    let boundary: Boundary = serde_json::from_str(BOUNDARY_JSON).expect("valid boundary JSON");
    assert_eq!(
        boundary.analysis_kind,
        "native_enemy_spawn_candidate_boundary_map"
    );
    assert!(!boundary.solver_impact.production_forecast_enabled);
    assert!(!boundary.solver_impact.simulator_version_bump_required);
    assert_eq!(boundary.solver_impact.current_simulator_version, 408);
    assert_eq!(boundary.replay_vectors.len(), 5);

    for vector in boundary.replay_vectors {
        let source: Vec<(u8, u8)> = vector
            .source_points
            .iter()
            .map(|point| (point[0], point[1]))
            .collect();
        let pool = build_native_enemy_spawn_candidate_pool(
            &source,
            vector.board_dimensions[0],
            vector.board_dimensions[1],
            vector.turn,
            |point, mode| {
                vector.valid_points.iter().any(|valid| {
                    valid.mode == mode
                        && valid
                            .points
                            .iter()
                            .any(|candidate| point == (candidate[0], candidate[1]))
                })
            },
        );

        match expected_kind(&vector.expected.pool_kind) {
            None => {
                assert!(pool.is_none());
                assert_eq!(vector.expected.validation_mode, None);
                assert_eq!(vector.expected.rng_caller_id, None);
                assert!(vector.expected.candidates.is_empty());
            }
            Some(kind) => {
                let pool = pool.expect("committed nonempty pool");
                assert_eq!(pool.kind, kind);
                assert_eq!(Some(pool.validation_mode), vector.expected.validation_mode);
                assert_eq!(Some(pool.rng_caller_id), vector.expected.rng_caller_id);
                assert_eq!(
                    pool.candidates,
                    vector
                        .expected
                        .candidates
                        .iter()
                        .map(|point| (point[0], point[1]))
                        .collect::<Vec<_>>()
                );
            }
        }
        assert!(!vector.expected.rng_consumed);
    }
}

#[test]
fn candidate_pool_joins_existing_exact_state_replay_without_forecasting() {
    let boundary: Boundary = serde_json::from_str(BOUNDARY_JSON).expect("valid boundary JSON");
    let capture = boundary.capture_join;
    let candidates: Vec<(u8, u8)> = capture
        .candidates
        .iter()
        .map(|point| (point[0], point[1]))
        .collect();
    let pool = build_native_enemy_spawn_candidate_pool(&candidates, 8, 8, 1, |point, mode| {
        mode == 6 && candidates.contains(&point)
    })
    .expect("capture-backed ordinary pool");
    let replay = replay_spawn_coordinate(capture.observable_pre_state, &pool.candidates)
        .expect("capture-backed selector replay");

    assert_eq!(pool.kind, NativeSpawnPoolKind::OrdinaryPrimary);
    assert_eq!(replay.raw_rng, capture.raw_rng);
    assert_eq!(replay.selected_index, capture.selected_index);
    assert_eq!(replay.selected, (capture.selected[0], capture.selected[1]));
    assert_eq!(
        default_native_enemy_spawn_zone(8, 8).expect("standard Board"),
        vec![
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
        ]
    );
}
