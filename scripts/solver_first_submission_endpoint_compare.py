"""Conditional Rust endpoint/HP comparison after an original submission join."""
import argparse,faulthandler,hashlib,json,sys
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
sha=lambda b:hashlib.sha256(b).hexdigest()
if not __debug__:raise RuntimeError('Receipt checks require normal Python execution; optimized mode is not admitted')
EXE_SHA='31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9'
EXTENSION_SHA='f3dfe1c3cb1aacea28abe654419c76ca7c1353afc998e4087c3b6ec86483c674'

def main():
 p=argparse.ArgumentParser();p.add_argument('--original-report',type=Path,required=True);p.add_argument('--original-report-sha256',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists(),'create-only comparison output';faulthandler.disable()
 import itb_solver
 from scripts.solver_first_s0 import corridor,loaded_extension_path
 from src.solver.observation_contract import encode_observation
 raw=a.original_report.read_bytes();assert sha(raw)==a.original_report_sha256;original=json.loads(raw)
 assert original['schema']=='solver_first_selected_move_submission_v1' and original['evidence_class'].startswith('conditional')
 assert original['admitted']==original['matched']==original['attempted']==1 and original['failed']==0 and original['failure'] is None
 assert original['submission']['grade_complete'] and original['postflight_identity_equal']
 assert original['original_inputs']['exe']==EXE_SHA,'Original executable build differs'
 assert all(original[k]==0 for k in ('original_completed_action_transitions','full_turn_original_comparisons','fair_input_admissions','held_out_cases','search_certificates','gate_promotions','ledger_promotions'))
 before=original['before'];after=original['submission']['after']
 assert before['actor']==dict(position=[0,0],hp=3,stored_active=0,bMoved=0) and after['actor']==dict(position=[0,1],hp=3,stored_active=0,bMoved=0)
 assert before['terrain']==after['terrain']==[0,3] and after['origin_occupants']['count']==0 and after['destination_occupants']['count']==1
 assert after['queues']['effects']['count']==after['queues']['delays']['count']==1 and after['queues']['delays']['contents']==[0xbf800000]
 paths=[Path(__file__).relative_to(ROOT).as_posix(),'scripts/solver_first_s0.py','src/solver/observation_contract.py','data/solver_first/s0_information_contract.json','rust_solver/src/movement.rs','rust_solver/src/primitive.rs','rust_solver/src/lib.rs','rust_solver/src/serde_bridge.rs']
 pins={f:sha((ROOT/f).read_bytes().replace(b'\r\n',b'\n')) for f in paths}
 prior_path=ROOT/'data/solver_first/s1_ground_step_Rust_20261003.json';prior_raw=prior_path.read_bytes();assert sha(prior_raw)=='2e72b0946272a282c702376890b21393635c57ef9067e2d1e7ebcedd41a47e2d';prior=json.loads(prior_raw)
 assert all(pins[f]==prior['source_lf_sha256'][f] for f in paths if f.startswith('rust_solver/'))
 extension=loaded_extension_path(itb_solver);assert sha(extension.read_bytes())==EXTENSION_SHA==prior['extension_sha256'] and itb_solver.simulator_version()==413==prior['simulator_version']
 observation=encode_observation(corridor(True,3));plan=[dict(mech_uid=0,move_to=[0,1],weapon_id='None',target=[0,1])]
 replay=json.loads(itb_solver.replay_solution(observation,json.dumps(plan)))
 actor=next(u for u in replay['predicted_states'][0]['post_move']['units'] if u['uid']==0);events=replay['action_results'][0]['events']
 accepted=not any(e.startswith('illegal_move:') for e in events);matched=accepted and actor['pos']==after['actor']['position'] and actor['hp']==after['actor']['hp']
 assert pins=={f:sha((ROOT/f).read_bytes().replace(b'\r\n',b'\n')) for f in paths} and sha(extension.read_bytes())==EXTENSION_SHA and a.original_report.read_bytes()==raw and prior_path.read_bytes()==prior_raw
 report=dict(schema='solver_first_selected_move_submission_Rust_endpoint_v1',evidence_class='conditional pinned original submission versus installed Rust endpoint/HP replay',objective='post-move position and HP only',movement_budget=dict(original_native=3,Rust_observation=3),exe_sha256=EXE_SHA,original_report_raw_sha256=sha(raw),original_private_world_raw_sha256=original['private_world_raw_sha256'],game_build=13725832,simulator_version=413,extension_raw_sha256=EXTENSION_SHA,prior_baseline_provenance=dict(receipt_raw_sha256=sha(prior_raw),baseline_solver_commit=prior['baseline_solver_commit'],four_current_Rust_sources_match=True),source_lf_sha256=pins,observation_sha256=sha(observation.encode()),original_projection=dict(position=after['actor']['position'],hp=after['actor']['hp']),Rust_projection=dict(position=actor['pos'],hp=actor['hp'],replay_accepted=accepted),Rust_action_events=events,attempted=1,admitted=1,matched=int(matched),failed=int(not matched),excluded=0,information_mode='declared development corridor; no native RNG/Stats/cache/queue inputs supplied to Rust; no fair corpus admission',exclusions=['Native owner -1/query actor stored_active0/bMoved0; Rust starts with available-action observation, so no readiness/action-eligibility equivalence','Native queue remains nonempty; no Rust/native scheduler or next-decision equivalence','Original route ownership, Stats, particle events and RNG graded separately, not compared to Rust','One shared declared development family; full action/turn, held-out/search/strength gates remain open'],original_completed_action_transitions=0,full_turn_original_comparisons=0,fair_input_admissions=0,held_out_cases=0,search_certificates=0,gate_promotions=0,ledger_promotions=0,search_status='not evaluated',valid_bounds=None,held_out_evaluation='not evaluated')
 with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(report,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 print(json.dumps({k:report[k] for k in ('attempted','admitted','matched','failed','excluded','original_projection','Rust_projection')}))
 raise SystemExit(int(not matched))
if __name__=='__main__':main()
