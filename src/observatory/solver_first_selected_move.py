"""Conditional original selected Move target/effect producers.

Declared query actor and empty passive world; dispatch and action settlement
remain outside this acquisition. See the pinned boundary for supplied premises.
"""
import json
from pathlib import Path
import struct
from src.observatory import solver_first_path_oracle as api
from src.observatory import solver_first_cache_emitter as cache
from src.observatory import solver_first_loaded_skill as skill
from src.observatory import solver_first_move_callback as move
from src.observatory import solver_first_ground_step as ground
from src.observatory import solver_first_lua_vm as vm

BOUNDARY=api.ROOT/'data/solver_first/s1_selected_move_boundary.json'
BOUNDARY_SHA='cc43bd050c1f24048072758f11a0fa5386bd5b891c3040395b878c1ec9b6c51c'
MAP=api.ROOT/'data/solver_first/s1_selected_move_instruction_admission.json'
MAP_SHA='2d65a98d749bb133b498432dc603d519e79ad4461ae5ead9a9cdb5dfb4b0153d'

def boundary():
 raw=BOUNDARY.read_bytes();api.require(api.sha(raw)==BOUNDARY_SHA,'selected boundary differs');return json.loads(raw)

def actor_projection(m,pawn):
 return dict(position=[m.get(pawn+0x8ec),m.get(pawn+0x8f0)],hp=m.get(pawn+0x8a8),stored_active=bytes(m.uc.mem_read(pawn+0x91c,1))[0],bMoved=bytes(m.uc.mem_read(pawn+0x99e,1))[0])

def sso(m,at):
 length,capacity=m.get(at+0x10),m.get(at+0x14)
 ptr=m.get(at) if capacity>=16 else at
 api.require(length<=capacity and (capacity<16 or ptr in m.live),'SSO extent/owner differs')
 return dict(length=length,capacity=capacity,value=bytes(m.uc.mem_read(ptr,length)).decode('ascii'),terminator=bytes(m.uc.mem_read(ptr+length,1))[0])

def continuation(executable,m,calls,o,original,dll):
 move.continuation(executable,m,calls,o,original,dll)
 for row in boundary()['original_body_pins']:
  rva=int(row['entry_rva'],16)
  if rva in m.source.owners:m.source.verify(rva)
  else:move.admit(m,rva,row['body_size'],row['body_sha256'])
  api.require(m.source.verified[rva]['body_sha256']==row['body_sha256'],'selected body differs')
 for row in boundary()['data_windows']:
  off=m.source.image.rva_to_file_offset(int(row['rva'],16));api.require(api.sha(m.source.data[off:off+row['size']])==row['raw_sha256'],'selected data differs')
 W=ground.WORLD;manager=api.BOARD+0x79100;native=o['native_Move']['skill'];pawn=W+0x100000;out=W+0x132000;effect=native+0x18
 before=actor_projection(m,pawn);start=len(calls)
 original(0x2287b0,[W+0xc],manager,cleanup=4)
 o['selected_context']=dict(manager_context=m.get(manager+0x3c),Move_context=m.get(native+0x110),Repair_context=m.get(m.get(manager+0x68)+0x110),owner=m.get(native+0x188),selected_index=m.get(manager+0x40))
 api.require(all(o['selected_context'][k]==W+0xc for k in ('manager_context','Move_context','Repair_context')),'native context propagation differs')
 api.require(o['selected_context']['owner']==o['selected_context']['selected_index']==0xffffffff,'declared base-manager defaults differ')
 api.require(original(0x269cc0,[out,0,0],native,cleanup=12)==out,'selected target result differs')
 o['selected_targets']=dict(output=ground.vector_points(m,out),cached=ground.vector_points(m,native+0x118),origin=[m.get(native+0x12c),m.get(native+0x130)],separate_owner=m.get(out)!=m.get(native+0x118))
 api.require(o['selected_targets']['output']==o['selected_targets']['cached']==o['Move_target_area'],'selected target query differs')
 api.require(o['selected_targets']['origin']==[0,0] and o['selected_targets']['separate_owner'],'selected target coordinates/ownership differ')
 # Complete callable constructors produce an explicitly empty passive world.
 # Global initializers and their exit registration are separate excluded roots.
 api.require(original(0x25a2e0,receiver=0x8d6c38)==0x8d6c38,'aggregate constructor result differs')
 api.require(original(0x7e10,[0x80dfdc],0x8d6c84,cleanup=4)==0x8d6c84,'empty string constructor result differs')
 empty=lambda:dict(length=0,capacity=15,value='',terminator=0)
 aggregate=dict(primary=[m.get(0x8d6c38+4*i) for i in range(3)],secondary=[m.get(0x8d6c44+4*i) for i in range(3)],extra=m.get(0x8d6c50),strings=[sso(m,0x8d6c54),sso(m,0x8d6c6c)],query_string=sso(m,0x8d6c84))
 api.require(aggregate==dict(primary=[0,0,0],secondary=[0,0,0],extra=0,strings=[empty(),empty()],query_string=empty()),'empty aggregate semantic fields differ')
 arg=W+0x132100;api.require(original(0x7e10,[0x837f68],arg,cleanup=4)==arg,'passive argument constructor result differs')
 words=list(struct.unpack('<6I',m.uc.mem_read(arg,24)));owned=words[0]
 api.require(sso(m,arg)['value']=='Passive_FriendlyFire','query argument differs')
 # cdecl RET0: the driver restores its outer stack between calls; no callee pop.
 result=original(0x25e700,words,cleanup=0)
 api.require(result&0xff==0 and owned not in m.live,'native passive query/destruction differs')
 o['empty_passive_world']=dict(**aggregate,query_AL=result&0xff,argument_allocation_released=True,global_initializers_executed=False,exit_registration_executed=False,empty_base_no_passives_declared=True)
 def grade(result):
  begin,end,cap=[m.get(effect+4*i) for i in range(3)]
  api.require(begin in m.live and begin<=end<=cap and end-begin==308 and cap-begin<=m.allocations[begin],'selected event vector extent/owner differs')
  row=dict(result=result,origin=[m.get(native+0x12c),m.get(native+0x130)],target=[m.get(native+0x124),m.get(native+0x128)],effect_origin_target=[m.get(effect+x) for x in (0x48,0x4c,0x50,0x54)],value=m.get(effect+0x58),owner=m.get(effect+0x5c),name=sso(m,effect+0x60),type=m.get(begin+0xc),mode=m.get(begin+0xd8),delay_bits=hex(m.get(begin+0xc8)),path=ground.vector_points(m,begin+0xcc),record_position=[m.get(begin),m.get(begin+4)],record_origin=[m.get(begin+0x9c),m.get(begin+0xa0)],record_value=m.get(begin+0xc0),animation=sso(m,begin+0x38),metadata_flag_bytes=list(bytes(m.uc.mem_read(effect+0x78,2))),secondary_header=[m.get(effect+0xc+4*i) for i in range(3)],path_separate_from_direct=m.get(begin+0xcc)!=m.get(W+0x130040),root_call_index=start)
  api.require(row['result']==1 and row['origin']==[0,0] and row['target']==[0,1] and row['effect_origin_target']==[0,0,0,1],'selected coordinates differ')
  api.require(row['value']==row['record_value']==m.get(native+0x150)==0 and row['owner']==m.get(native+0x188)==0xffffffff,'selected scalar metadata differs')
  api.require(row['name']==dict(length=4,capacity=15,value='Move',terminator=0) and row['animation']==empty(),'selected string metadata differs')
  api.require(row['type']==4 and row['mode']==0 and row['delay_bits']=='0xbf800000' and row['path']==[[0,0],[0,1]],'selected movement record differs')
  api.require(row['record_position']==[0xffffffff]*2 and row['record_origin']==[0,0] and row['metadata_flag_bytes']==[0,0] and row['secondary_header']==[0,0,0] and row['path_separate_from_direct'],'selected record metadata/ownership differs')
  return row
 o['selected_effect']=grade(original(0x268920,[0,0,0,1],native,cleanup=16))
 o['negative_controls']=[]
 for xy in ((0,4),(0,0)):
  result=original(0x268920,[0,0,*xy],native,cleanup=16)
  row=dict(requested=list(xy),result=result,target=[m.get(native+0x124),m.get(native+0x128)],primary_empty=m.get(effect)==m.get(effect+4),secondary_empty=m.get(effect+12)==m.get(effect+16))
  o['negative_controls'].append(row);api.require(result==0 and row['target']==[0xffffffff]*2 and row['primary_empty'] and row['secondary_empty'],'nonmember target accepted')
 o['restored_selected_effect']=grade(original(0x268920,[0,0,0,1],native,cleanup=16))
 after=actor_projection(m,pawn);o['actor_before_after']=dict(before=before,after=after)
 api.require(before==after==dict(position=[0,0],hp=3,stored_active=0,bMoved=0),'effect construction changed actor accounting')
 o['selected_Lua_stack']=dll('lua_gettop',[o['lua_state']]);api.require(o['selected_Lua_stack']==0,'selected Lua stack leaked')
 o['selected_shared_ownership']=dict(Move_strong=m.get(o['native_Move']['control']+4),pilot_strong=m.get(W+0x121004))
 api.require(o['selected_shared_ownership']==dict(Move_strong=1,pilot_strong=1),'temporary shared references leaked')

def run(executable,private_dir):
 from src.observatory.solver_first_image_resource import ARCHIVE_SHA
 from src.observatory.solver_first_lua_emitters import SOURCES
 executable,private_dir=Path(executable),Path(private_dir);api.require(not private_dir.exists(),'private output create-only')
 packet=boundary();map_raw=MAP.read_bytes();api.require(api.sha(map_raw)==MAP_SHA,'selected instruction map differs');map_doc=json.loads(map_raw);api.require(map_doc['dll_sha256']==vm.DLL_SHA,'DLL map identity differs')
 paths=['src/observatory/solver_first_selected_move.py','scripts/solver_first_selected_move.py','data/solver_first/s1_selected_move_boundary.json','data/solver_first/s1_selected_move_instruction_admission.json']
 paths+=['src/observatory/'+x+'.py' for x in ('solver_first_move_callback','solver_first_loaded_skill','solver_first_ground_step','solver_first_cache_emitter','solver_first_lua_emitters','solver_first_lua_vm','solver_first_image_resource','solver_first_gl_texture','solver_first_path_oracle','pe_anchor_map','resource_archive')]
 paths+=['data/solver_first/'+x for x in ('s1_move_callback_boundary.json','s1_move_callback_instruction_admission.json','s1_loaded_skill_boundary.json','s1_cache_emitter_boundary.json')]
 pins={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths};runtime_base=api.runtime_identity();runtime={**runtime_base,'wall_time_limit_us':30000000}
 scripts={row['game_relative_path']:row['complete_file_raw_sha256'] for row in skill.boundary()['exact_stock_slices']+move.boundary()['exact_stock_slices']};scripts.update(SOURCES);scripts.update({p:row['sha256'] for p,row in cache.boundary()['game_sources'].items()})
 def inputs_unchanged():
  return api.sha(executable.read_bytes())==api.EXE_SHA and api.sha((executable.parent/'lua5.1.dll').read_bytes())==vm.DLL_SHA and api.sha((executable.parent/'resources/resource.dat').read_bytes())==ARCHIVE_SHA and all(api.sha((executable.parent/p).read_bytes())==h for p,h in scripts.items())
 api.require(inputs_unchanged(),'original inputs differ');private_dir.mkdir(parents=True)
 private,m=cache.acquire(executable,map_doc['instructions'],continuation=lambda m,calls,o,original,dll:continuation(executable,m,calls,o,original,dll),machine_type=skill.SkillMachine)
 private['source_lf_sha256']=pins;private['runtime']=runtime;private['driver_limits']=dict(native_and_DLL_wall_time_limit_us=30000000,instruction_limit_per_call=api.LIMIT)
 receipt=private_dir/'world.json'
 with receipt.open('x',encoding='utf-8',newline='\n') as f:json.dump(private,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 api.require(pins=={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths},'acquisition sources changed')
 api.require(runtime_base==api.runtime_identity() and MAP.read_bytes()==map_raw and inputs_unchanged(),'runtime/map/original inputs changed')
 matched=private['status']=='complete_joined_dependency_and_declared_continuation' and private['failure'] is None
 identities=[]
 for row in private['verified_source_bodies']:
  visited=any(int(span['start_rva'],16)<=at<int(span['start_rva'],16)+span['size'] for span in row['ranges'] for at in m.source.executed_rvas)
  identities.append({**row,'executed':visited})
 return dict(schema_version=1,corpus_version='s1-original-selected-Move-development-v1',game_build=13725832,baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',simulator_version=413,
  objective='Close conditional native selected Move target membership and metadata-producing effect construction.',information_mode='Offline declared actor/query Board and empty passive world; no fair planner-input admission.',
  attempted=1,admitted=int(matched),matched=int(matched),failed=int(not matched),excluded=0,status='complete_conditional_selected_Move_producers' if matched else 'failed',failure=private['failure'],observations=private['observations'],source_lf_sha256=pins,stock_script_sha256=scripts,runtime=runtime,
  executable_sha256=api.EXE_SHA,lua_dll_sha256=vm.DLL_SHA,archive_sha256=ARCHIVE_SHA,boundary_sha256=BOUNDARY_SHA,instruction_map_sha256=MAP_SHA,private_receipt_sha256=api.sha(receipt.read_bytes()),
  original_call_count=len(private['calls']),instruction_count=sum(c['instructions'] for c in private['calls']),executed_DLL_instruction_points=len(m.dll_points),lua_allocator_callback_count=sum(len(c['allocator_calls']) for c in private['calls']),retained_guest_allocations=len(m.live),retained_guest_requested_bytes=sum(m.allocations[p] for p in m.live),original_body_identities=identities,
  calls=[{k:v for k,v in c.items() if k not in ('trace','allocator_calls')} for c in private['calls']],supplied_boundaries=packet['supplied_boundaries'],
  original_completed_action_transitions=0,full_turn_original_comparisons=0,fair_input_admissions=0,held_out_cases=0,search_certificates=0,gate_promotions=0,ledger_promotions=0,
  next_blocker='Original submitted-action stats/context dispatch, Board event dispatch and route settlement with consistent actor accounting; then next-decision/full-turn continuity and independent corpus.')
