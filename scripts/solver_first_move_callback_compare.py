"""Compare conditional original stock Move target membership with Rust replay."""
import argparse,faulthandler,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def sha(raw):return hashlib.sha256(raw).hexdigest()
if __name__=='__main__':
 faulthandler.disable();parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--original-report',type=Path,required=True);parser.add_argument('--original-report-sha256',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 source=args.original_report;expected=args.original_report_sha256;assert not args.output.exists(),'output create-only';raw=source.read_bytes();assert sha(raw)==expected
 native=json.loads(raw);assert native['failure'] is None and native['status']=='complete_conditional_stock_Move_callbacks'
 assert native['corpus_version']=='s1-original-stock-Move-callback-development-v1' and native['attempted']==native['admitted']==native['matched']==1 and native['failed']==native['excluded']==0
 assert native['original_completed_action_transitions']==native['full_turn_original_comparisons']==native['fair_input_admissions']==native['gate_promotions']==0
 assert native['game_build']==13725832 and native['simulator_version']==413 and native['executable_sha256']=='31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9','original report build differs'
 o=native['observations'];assert o['actor_getters']==[3,18,False,False,False,False] and o['actor_getter_types']==[3,3,1,1,1,1]
 assert o['direct_reachable']==o['Move_target_area']==[[0,1],[0,2],[0,3]]
 import itb_solver
 from scripts.solver_first_s0 import corridor,loaded_extension_path
 from src.solver.observation_contract import encode_observation
 extension=loaded_extension_path(itb_solver);extension_sha='f3dfe1c3cb1aacea28abe654419c76ca7c1353afc998e4087c3b6ec86483c674'
 assert sha(extension.read_bytes())==extension_sha and itb_solver.simulator_version()==413
 paths=[Path(__file__)]+[ROOT/f for f in ['scripts/solver_first_s0.py','src/solver/observation_contract.py','data/solver_first/s0_information_contract.json','rust_solver/src/movement.rs','rust_solver/src/lib.rs','rust_solver/src/serde_bridge.rs']]
 before={str(p.relative_to(ROOT)):sha(p.read_bytes().replace(b'\r\n',b'\n')) for p in paths}
 observation=encode_observation(corridor(True,3));accepted=[];mismatches=[];origin=None;projections=[]
 for x in range(8):
  for y in range(8):
   dest=[x,y];plan=[dict(mech_uid=0,move_to=dest,weapon_id='None',target=dest)]
   replay=json.loads(itb_solver.replay_solution(observation,json.dumps(plan)));events=replay['action_results'][0]['events'];legal=not any(e.startswith('illegal_move:') for e in events)
   actor=next(u for u in replay['predicted_states'][0]['post_move']['units'] if u['uid']==0)
   row=dict(destination=dest,accepted=legal,position=actor['pos'],hp=actor['hp'],events=events,post_move_active=actor.get('active'),post_attack_active=next(u for u in replay['predicted_states'][0]['post_attack']['units'] if u['uid']==0).get('active'));projections.append(row)
   if dest==[0,0]:origin=row;continue
   if legal:accepted.append(dest)
   if legal!=(dest in o['Move_target_area']) or actor['pos']!=(dest if legal else [0,0]) or actor['hp']!=3:mismatches.append(row)
 assert sha(source.read_bytes())==expected and sha(extension.read_bytes())==extension_sha
 after={str(p.relative_to(ROOT)):sha(p.read_bytes().replace(b'\r\n',b'\n')) for p in paths};assert before==after,'comparison source changed during execution'
 origin_contract_matched=origin['accepted'] and origin['position']==[0,0] and origin['hp']==3
 result=dict(evidence_class='conditional original stock Move target callback versus Rust replay distinct-destination validation',schema_version=1,corpus_version='s1-stock-Move-target-membership-Rust-development-v1',original_report_sha256=expected,original_receipt_sha256=native['private_receipt_sha256'],game_build=13725832,baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',extension_sha256=extension_sha,simulator_version=413,observation_sha256=sha(observation.encode()),source_lf_sha256=before,native_targets=o['Move_target_area'],rust_distinct_destinations=accepted,distinct_destinations_attempted=63,matched_distinct_destinations=63-len(mismatches),mismatches=mismatches,origin_probe=origin,origin_no_displacement_replay_contract_matched=origin_contract_matched,all_replay_projections=projections,exclusions=['Original occupied origin absent from Move target callback; Rust origin acceptance and action-state consumption are recorded separately. This is an explicit action-identity boundary, not erased by set normalization.','Original declared Pawn/Pilot query state is not genuine loaded/deployed actor; Rust active/can_move observation is supplied.','Replay validation is not full solver action enumeration, completed original action or full event/turn parity.','One development corridor; no fair player input corpus, heldout cases, exhaustive search certificate or practical comparison.'],original_action_admissions=0,full_turn_comparisons=0,fair_input_admissions=0,held_out_cases=0,gate_promotions=0,ledger_promotions=0)
 out=args.output;assert not out.exists();out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps(dict(attempted=63,matched=63-len(mismatches),rust_distinct_destinations=accepted,origin_accepted=origin['accepted'],mismatches=len(mismatches),receipt_sha256=sha(out.read_bytes()))));sys.exit(bool(mismatches))
