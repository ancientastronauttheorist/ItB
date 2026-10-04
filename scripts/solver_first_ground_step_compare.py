"""Compare retained original N2 endpoint/HP evidence with installed Rust replay.

Run in a fresh process after original acquisition. This conditional projection
does not compare loaded Move legality, stored readiness, or a full action/turn.
"""
import argparse
import faulthandler
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXTENSION_SHA = 'f3dfe1c3cb1aacea28abe654419c76ca7c1353afc998e4087c3b6ec86483c674'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(original_path, original_sha):
    import itb_solver
    from scripts.solver_first_s0 import corridor, loaded_extension_path
    from src.solver.observation_contract import encode_observation

    raw = original_path.read_bytes()
    assert sha(raw) == original_sha, 'original report identity differs'
    report = json.loads(raw)
    assert report['corpus_version'] == 's1-original-joined-ground-N2-development-v1'
    assert report['game_build'] == 13725832 and report['simulator_version'] == 413
    assert report['attempted'] == report['admitted'] == report['matched'] == 1
    assert report['failed'] == report['excluded'] == 0 and report['failure'] is None
    assert report['original_completed_action_transitions'] == report['full_turn_original_comparisons'] == 0
    native = report['observations']['joined_route_projection']
    fixture = report['observations']['joined_route_fixture']
    assert fixture['point_query'] == [[0, 0], [0, 1]] and fixture['profile'] == 18
    assert fixture['Massive_byte'] == 1 and fixture['Flying_definition_byte'] == 0
    assert native['coordinates'] == [0, 1] and native['hp'] == 3 and native['target_terrain'] == 3
    assert native['origin_occupants'] == 0 and native['target_occupants'] == 1
    paths = ['scripts/solver_first_ground_step_compare.py', 'scripts/solver_first_s0.py',
             'src/solver/observation_contract.py', 'data/solver_first/s0_information_contract.json',
             'rust_solver/src/movement.rs', 'rust_solver/src/primitive.rs',
             'rust_solver/src/lib.rs', 'rust_solver/src/serde_bridge.rs']
    pins = {p: sha((ROOT / p).read_bytes().replace(b'\r\n', b'\n')) for p in paths}
    extension = loaded_extension_path(itb_solver)
    assert sha(extension.read_bytes()) == EXTENSION_SHA and itb_solver.simulator_version() == 413
    observation = encode_observation(corridor(True, 1))
    plan = [dict(mech_uid=0, move_to=[0, 1], weapon_id='None', target=[0, 1])]
    replay = json.loads(itb_solver.replay_solution(observation, json.dumps(plan)))
    actor = next(u for u in replay['predicted_states'][0]['post_move']['units'] if u['uid'] == 0)
    accepted = not any(e.startswith('illegal_move:') for e in replay['action_results'][0]['events'])
    matched = accepted and actor['pos'] == native['coordinates'] and actor['hp'] == native['hp']
    assert pins == {p: sha((ROOT / p).read_bytes().replace(b'\r\n', b'\n')) for p in paths}
    assert original_path.read_bytes() == raw and sha(extension.read_bytes()) == EXTENSION_SHA
    return dict(schema_version=1, corpus_version='s1-original-ground-N2-endpoint-Rust-development-v1',
        evidence_class='retained bounded original continuation versus conditional installed Rust replay',
        game_build=13725832, baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',
        simulator_version=413, extension_sha256=EXTENSION_SHA,
        information_mode='offline supplied corridor; privileged native RNG excluded from Rust inputs; no fair corpus admission',
        objective='conditional post-move pawn position and HP only',
        attempted=1, admitted=1, matched=int(matched), failed=int(not matched), excluded=0,
        original_report_sha256=original_sha, original_receipt_sha256=report['private_receipt_sha256'],
        original_projection=dict(position=native['coordinates'], hp=native['hp']),
        rust_projection=dict(position=actor['pos'], hp=actor['hp'], replay_accepted=accepted),
        rust_action_events=replay['action_results'][0]['events'],
        observation_sha256=sha(observation.encode()), source_lf_sha256=pins,
        exclusions=[
            'Original route installer is entered under a supplied frame; native loaded Move/action admission is unacquired.',
            'Rust replay starts with available-action observation; original supplied pawn stored active remains zero and bMoved remains zero. No readiness/action eligibility equivalence claim.',
            'Native membership, route/vector ownership and particle/RNG fields are independently graded by acquisition, not by Rust replay.',
            'Full legal action sets, extended route/status/item controls, ordered full action events, enemy/environment/spawn, undo/save and mission continuity remain open.',
            'A shared development family with no held-out evidence, search certificate or practical baseline/candidate evaluation.'],
        original_completed_action_transitions=0, full_turn_original_comparisons=0, fair_input_admissions=0,
        held_out_cases=0, search_certificates=0, gate_promotions=0, ledger_promotions=0,
        search_status='not evaluated', valid_bounds=None, held_out_evaluation='not evaluated')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-report', type=Path, required=True)
    parser.add_argument('--original-report-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output is create-only')
    faulthandler.disable()
    result = run(args.original_report, args.original_report_sha256)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    print(json.dumps({k: result[k] for k in ('attempted', 'admitted', 'matched', 'failed', 'excluded')}))
    return int(result['failed'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
