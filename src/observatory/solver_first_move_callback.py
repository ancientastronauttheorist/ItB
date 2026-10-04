"""Original stock Move callbacks under declared source-backed actor inputs.

Offline conditional target/effect materialization evidence. No loaded actor,
selected native action, dispatch, settlement or full-turn admission.
"""
import json
from pathlib import Path
import struct
from src.observatory import solver_first_path_oracle as api
from src.observatory import solver_first_cache_emitter as cache
from src.observatory import solver_first_loaded_skill as skill
from src.observatory import solver_first_ground_step as ground
from src.observatory import solver_first_lua_vm as vm
BOUNDARY=api.ROOT/'data/solver_first/s1_move_callback_boundary.json'
BOUNDARY_SHA='2d0e17e1dadb833cba2993f5ae130e506150dd0fa5a901bb40ad01102f17b7fa'
MAP=api.ROOT/'data/solver_first/s1_move_callback_instruction_admission.json'
MAP_SHA='5bfc800d2baf0c1271413c182008f5966b135ea8582e4aaeaf747117bc306877'

def boundary():
 raw=BOUNDARY.read_bytes();api.require(api.sha(raw)==BOUNDARY_SHA,'callback boundary differs');return json.loads(raw)

def admit(m,rva,size,digest):
 m.source.check_window(rva,size,digest);cursor=rva
 for i in m.source.decoder.disasm(m.source.bytes_at(rva,size),api.BASE+rva):
  api.require(i.address==api.BASE+cursor,'window decode gap');m.source.points[cursor]=bytes(i.bytes);cursor+=i.size
 api.require(cursor==rva+size,'window decode extent')
 m.source.verified[rva]=dict(entry_rva=hex(rva),body_size=size,body_sha256=digest,ranges=[dict(start_rva=hex(rva),size=size)],admission='explicit complete source-pinned window; not atlas owner')

def continuation(EXE,m,calls,o,original,dll):
 skill.continue_skills(EXE,m,calls,o,original,dll)
 packet=boundary()
 for row in packet['original_body_pins']:
  rva=int(row['entry_rva'],16);m.source.verify(rva);api.require(m.source.verified[rva]['body_sha256']==row['body_sha256'],'binding body differs')
 for row in packet['binding_data_windows']:
  rva=int(row.get('rva',row.get('va','0')),16);rva=rva-api.BASE if 'va' in row else rva
  off=m.source.image.rva_to_file_offset(rva);api.require(api.sha(m.source.data[off:off+row['size']])==row['raw_sha256'],'binding data/window differs')
  if row.get('kind')=='decoded_callable_thunk_window_not_atlas_owner':admit(m,rva,row['size'],row['raw_sha256'])
 for entry in (0x4d00,0x4d20,0x5940,0x5960,0x5980):original(entry)
 L=o['lua_state'];module=api.BOARD+0x73000;key=api.BOARD+0x77000;chunk=api.BOARD+0x78000
 descriptors={}
 for n,row in enumerate(packet['class_registration']['classes']):
  desc=api.BOARD+0x7a000+n*0x100;descriptors[row['name']]=desc;original(int(row['builder_rva'],16),[0],desc,cleanup=4)
 for n,row in enumerate(packet['methods']):
  pair=api.BOARD+0x7a400+n*8;m.put(pair,int(row['member_pair'][0],16));m.put(pair+4,0)
  original(int(row['builder_rva'],16),[int(row['name_va'],16),pair,0,0,0],descriptors[row['class']],cleanup=20)
 for desc in descriptors.values():original(0x2e66c0,[m.get(desc)],module,cleanup=4)
 for row in packet['effect_data_windows']:
  rva=int(row['start_rva'],16);off=m.source.image.rva_to_file_offset(rva);api.require(api.sha(m.source.data[off:off+row['size']])==row['raw_sha256'],'effect data pin differs')
 original(0x6a70);effect_desc=api.BOARD+0x7ac00;effect_pair=api.BOARD+0x7ad00
 original(0x281da0,[0],effect_desc,cleanup=4);original(0x28b420,[0,0],effect_desc,cleanup=8)
 m.put(effect_pair,0x657340);m.put(effect_pair+4,0);original(0x28b780,[0x838d20,effect_pair,0,0,0],effect_desc,cleanup=20)
 original(0x2e66c0,[m.get(effect_desc)],module,cleanup=4)
 o['declared_native_export_constants']=[]
 for row in packet['native_export_constants']:
  name=row['name'];m.source.check_window(int(row['start_rva'],16),row['size'],row['code_sha256'])
  if row.get('backing') is not None:
   b=row['backing'];off=m.source.image.rva_to_file_offset(int(b['RVA'],16));api.require(api.sha(m.source.data[off:off+b['size']])==b['sha256'],'export backing data differs')
  m.uc.mem_write(key,name.encode()+b'\0');dll('lua_pushinteger',[L,row['value']]);dll('lua_setfield',[L,0xffffd8ee,key]);o['declared_native_export_constants'].append(dict(name=name,value=row['value'],original_export_executed=False))
 def load(raw,label):
  m.uc.mem_write(key,raw);m.uc.mem_write(chunk,label.encode()+b'\0');api.require(dll('luaL_loadbuffer',[L,key,len(raw),chunk])==0,'compile '+label)
  status=dll('lua_pcall',[L,0,0,0])
  if status:
   ptr=dll('lua_tolstring',[L,0xffffffff,0]);o['lua_error']=bytes(m.uc.mem_read(ptr,512)).split(b'\0',1)[0].decode('utf-8',errors='replace')
  api.require(status==0,'execute '+label+': '+str(o.get('lua_error')))
 o['additional_stock_slices']=[]
 for row in packet['exact_stock_slices']:
  full=(EXE.parent/row['game_relative_path']).read_bytes();api.require(api.sha(full)==row['complete_file_raw_sha256'],'stock file differs')
  raw=full[row['byte_start']:row['byte_start']+row['size']];api.require(api.sha(raw)==row['raw_sha256'],'stock slice differs')
  load(raw,row['game_relative_path']+':'+str(row['line_start'])+'-'+str(row['line_end']));o['additional_stock_slices'].append(row)
 W=ground.WORLD;m.uc.mem_map(W,0x200000);ground.fixture_at(m,dict(water=True,occupied=True,blocker_team=None),W)
 pawn=W+0x100000;pilot=W+0x120000;ctrl=W+0x121000
 # Supplied source-backed RAW initial state, not execution of Pawn/Pilot constructors.
 m.put(pawn+0x990,3);m.put(pawn+0xa6c,pilot);m.put(pawn+0xa70,ctrl);m.uc.mem_write(pawn+0x99d,b'\1');m.uc.mem_write(pawn+0x10c0,b'\1\0')
 m.put(pawn+0xc4c,W+0x122000);m.put(pawn+0xc50,W+0x122004);m.put(pawn+0xc54,W+0x122004);m.put(W+0x122000,0)
 m.put(pilot,0x835dcc);m.put(pilot+0x74,15);m.put(ctrl,0x82b804);m.put(ctrl+4,1);m.put(ctrl+8,1);m.put(ctrl+12,pilot)
 # Genuine constructor of definition-name MSVC string; owner read by original Lua property getters.
 m.uc.mem_write(key,b'PunchMech\0');original(0x7e10,[key],pawn+0x94,cleanup=4)
 o['declared_actor_boundary']=dict(pawn=pawn,pilot=pilot,control=ctrl,full_Pawn_constructor=False,full_Pilot_constructor=False,base_speed=3,team=1,hp=3,massive=True,ready_byte=1,main_ability='',earned_ability_count=0,unspecified_actor_and_pilot_cells_zero=True,definition='PunchMech',origin=[0,0])
 def words(raw):return list(struct.unpack('<4I',(raw+b'\0').ljust(16,b'\0')))+[len(raw),15]
 original(0x176f00,[W]+words(b'SetBoard'),0x896038,cleanup=28);original(0xf88f0,[pawn]+words(b'SetPawn'),0x896038,cleanup=28)
 raw=b'return Pawn:GetMoveSpeed(),Pawn:GetPathProf(),Pawn:IsJumper(),Pawn:IsTeleporter(),Pawn:IsAbility("Web_Vek"),Pawn:IsAbility("Adjacent_Heal")'
 m.uc.mem_write(key,raw);m.uc.mem_write(chunk,b'original getters\0');api.require(dll('luaL_loadbuffer',[L,key,len(raw),chunk])==0,'getter compile')
 status=dll('lua_pcall',[L,0,6,0]);api.require(status==0,'getter call failed')
 api.require(dll('lua_gettop',[L])==6,'getter result stack shape differs');got=[];types=[]
 for i in range(1,7):
  t=dll('lua_type',[L,i]);types.append(t);got.append(dll('lua_tointeger',[L,i]) if t==3 else bool(dll('lua_toboolean',[L,i])))
 o['actor_getter_types']=types;api.require(types==[3,3,1,1,1,1],'getter result types differ');o['actor_getters']=got;api.require(got==[3,18,False,False,False,False],'original actor getters differ');dll('lua_settop',[L,0])
 admit(m,0x2fb0,81,'04acd19f82e7f95d52dccef7989876e50bf3adab40aae1b037ce5996265d9b3e');original(0x2fb0);original(0x3030)
 direct=W+0x130000;target=W+0x130020
 original(0x174180,[direct,0,0,got[0],got[1]],W,cleanup=20);o['direct_reachable']=ground.vector_points(m,direct)
 api.require(original(0x2726d0,[target]+words(b'Move')+words(b'GetTargetArea')+[0,0],cleanup=60)==target,'Move target consumer result')
 o['Move_target_area']=ground.vector_points(m,target)
 api.require(o['Move_target_area']==o['direct_reachable'],'callback/direct target query differ')
 api.require(o['Move_target_area']==[[0,1],[0,2],[0,3]],'independent corridor target expectation differs')
 direct_path=W+0x130040;effect_out=W+0x131000
 original(0x1742d0,[direct_path,0,0,0,1,got[1]],W,cleanup=24);o['direct_path']=ground.vector_points(m,direct_path)
 api.require(original(0x272190,[effect_out]+words(b'Move')+words(b'GetSkillEffect')+[0,0,0,1],cleanup=68)==effect_out,'Move effect consumer result')
 begin,end,cap=[m.get(effect_out+i*4) for i in range(3)]
 api.require(begin in m.live and begin<=end<=cap and end-begin==308 and cap-begin<=m.allocations[begin],'event vector ownership/extent differs')
 event=begin;path=ground.vector_points(m,event+0xcc)
 o['Move_effect']=dict(output=effect_out,primary_count=1,primary_allocation=begin,primary_capacity=cap-begin,type=m.get(event+0xc),mode=m.get(event+0xd8),delay_bits=hex(m.get(event+0xc8)),path=path,secondary_header=[m.get(effect_out+0xc+i*4) for i in range(3)],origin_target=[m.get(effect_out+x) for x in (0x48,0x4c,0x50,0x54)],default_flags=[m.get(effect_out+0x58),m.get(effect_out+0x5c)],skill_effect_type_id=m.get(0x8d90cc))
 strings=[]
 for off in (0x18,0x30,0x60):
  row=dict(offset=hex(off),length=m.get(effect_out+off+0x10),capacity=m.get(effect_out+off+0x14),first_byte=bytes(m.uc.mem_read(effect_out+off,1))[0]);strings.append(row)
  api.require(row['length']==0 and row['capacity']==15 and row['first_byte']==0,'effect empty SSO metadata differs')
 o['Move_effect']['empty_SSO_strings']=strings;o['Move_effect']['metadata_flag_bytes']=list(bytes(m.uc.mem_read(effect_out+0x78,2)));api.require(o['Move_effect']['metadata_flag_bytes']==[0,0],'effect metadata flags differ')
 e=o['Move_effect'];api.require(e['type']==4 and e['mode']==0 and e['delay_bits']=='0xbf800000','normal effect scalar fields differ')
 api.require(path==o['direct_path']==[[0,0],[0,1]],'original callback/direct path differ')
 api.require(e['secondary_header']==[0,0,0] and e['origin_target']==[0x80000001]*4 and e['default_flags']==[2,0xffffffff],'lower effect defaults differ')
 api.require(m.get(event+0xcc)!=m.get(direct_path),'effect path must own separate clone')
 o['pilot_strong_final']=m.get(ctrl+4);api.require(o['pilot_strong_final']==1,'temporary shared ownership leaked');api.require(dll('lua_gettop',[L])==0,'Lua stack leaked')


def run(executable,private_dir):
 from src.observatory.solver_first_image_resource import ARCHIVE_SHA
 executable,private_dir=Path(executable),Path(private_dir);api.require(not private_dir.exists(),'private output create-only')
 packet=boundary();map_raw=MAP.read_bytes();api.require(api.sha(map_raw)==MAP_SHA,'callback instruction map differs');map_doc=json.loads(map_raw)
 api.require(map_doc['dll_sha256']==vm.DLL_SHA,'DLL map identity differs')
 paths=['src/observatory/solver_first_move_callback.py','scripts/solver_first_move_callback.py','src/observatory/solver_first_loaded_skill.py','src/observatory/solver_first_ground_step.py','src/observatory/solver_first_cache_emitter.py','src/observatory/solver_first_lua_emitters.py','src/observatory/solver_first_lua_vm.py','src/observatory/solver_first_image_resource.py','src/observatory/solver_first_gl_texture.py','src/observatory/solver_first_path_oracle.py','src/observatory/pe_anchor_map.py','src/observatory/resource_archive.py','data/solver_first/s1_move_callback_boundary.json','data/solver_first/s1_move_callback_instruction_admission.json','data/solver_first/s1_loaded_skill_boundary.json','data/solver_first/s1_cache_emitter_boundary.json']
 source_pins={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths};runtime_base=api.runtime_identity();runtime={**runtime_base,'wall_time_limit_us':30_000_000}
 script_pins={row['game_relative_path']:row['complete_file_raw_sha256'] for row in skill.boundary()['exact_stock_slices']+packet['exact_stock_slices']}
 from src.observatory.solver_first_lua_emitters import SOURCES
 script_pins.update(SOURCES);script_pins.update({p:row['sha256'] for p,row in cache.boundary()['game_sources'].items()})
 api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'original scripts differ')
 private_dir.mkdir(parents=True)
 private,m=cache.acquire(executable,map_doc['instructions'],continuation=lambda m,calls,o,original,dll:continuation(executable,m,calls,o,original,dll),machine_type=skill.SkillMachine)
 private['source_lf_sha256']=source_pins;private['runtime']=runtime;private['driver_limits']=dict(native_and_DLL_wall_time_limit_us=30_000_000,instruction_limit_per_call=api.LIMIT)
 receipt=private_dir/'world.json'
 with receipt.open('x',encoding='utf-8',newline='\n') as f:json.dump(private,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
 api.require(source_pins=={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths},'acquisition sources changed')
 api.require(runtime_base==api.runtime_identity() and MAP.read_bytes()==map_raw,'runtime/map changed')
 api.require(api.sha(executable.read_bytes())==api.EXE_SHA and api.sha((executable.parent/'lua5.1.dll').read_bytes())==vm.DLL_SHA and api.sha((executable.parent/'resources/resource.dat').read_bytes())==ARCHIVE_SHA,'original inputs changed')
 api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'original scripts changed')
 matched=private['status']=='complete_joined_dependency_and_declared_continuation' and private['failure'] is None
 identities=[]
 for row in private['verified_source_bodies']:
  visited=any(int(span['start_rva'],16)<=at<int(span['start_rva'],16)+span['size'] for span in row['ranges'] for at in m.source.executed_rvas)
  identities.append({**row,'executed':visited})
 return dict(schema_version=1,corpus_version='s1-original-stock-Move-callback-development-v1',game_build=13725832,baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',simulator_version=413,
  objective='Close conditional original stock Move target and normal effect callback composition through actual typed bindings and native extraction.',information_mode='Offline supplied query/actor/Pilot world; no fair planner-input admission.',
  attempted=1,admitted=int(matched),matched=int(matched),failed=int(not matched),excluded=0,status='complete_conditional_stock_Move_callbacks' if matched else 'failed',failure=private['failure'],observations=private['observations'],source_lf_sha256=source_pins,stock_script_sha256=script_pins,runtime=runtime,
  executable_sha256=api.EXE_SHA,lua_dll_sha256=vm.DLL_SHA,archive_sha256=ARCHIVE_SHA,boundary_sha256=BOUNDARY_SHA,instruction_map_sha256=MAP_SHA,private_receipt_sha256=api.sha(receipt.read_bytes()),
  original_call_count=len(private['calls']),instruction_count=sum(c['instructions'] for c in private['calls']),executed_DLL_instruction_points=len(m.dll_points),lua_allocator_callback_count=sum(len(c['allocator_calls']) for c in private['calls']),retained_guest_allocations=len(m.live),retained_guest_requested_bytes=sum(m.allocations[p] for p in m.live),original_body_identities=identities,
  calls=[{k:v for k,v in c.items() if k not in ('trace','allocator_calls')} for c in private['calls']],
  supplied_boundaries=[
   'Reuses pinned genuine Point/Tip/cache/Dust/Move/Repair/base-manager construction and original Lua base/string libraries. Inherited loaded-Skill boundary applies; normal game/overlay/bootstrap/rendering and host error branches excluded.',
   'Actual isolated native type insertion and class/method registration, original SetBoard/SetPawn typed borrowed-pointer producers. IDs are outputs, not full-game registry ordering.',
   'Five unchanged stock slices load Pawn/CreateClass through the final call, Pawn list state/AddPawn, PunchMech and SetBoard/SetPawn. Seven native constant values are source-pinned supplied globals; export bootstrap is not executed.',
   'Supplied Board/maphead/Tile occupancy and RAW actor/Pilot/control cells. Genuine definition-name MSVC constructor and original movement/ability/property getters execute. Base speed3,HP3,team1,Massive1,readiness gate1,zero bonuses/statuses,onezero upgrade cell,empty mainSkill/earnedcount0 are inputs; full Pawn/Pilot/animation/equipment load and deployment excluded.',
   'Owned24B source-backed SSO caller names are supplied byvalue inputs. Lower2726d0 and272190 execute unchanged stock callbacks and original typed PointList/SkillEffect extraction; no host final target/path/event substitute.',
   'Ordered targets G8/F8/E8 and normal H8/G8 path/type4/mode0/FULL_DELAY event are graded; original occupied origin is absent. Original269cc0/268050 selected context/passive postprocessing, dispatcher, settled coordinates/action eligibility/fullactionevents and next-decision continuity remain open.',
   'Guest userdata/cache/Skill/path/event ownership remains retained after graded copies and temporary shared-reference restoration. Host GL cleanup is separate; saved guest handles cannot resume. No full guest destruction/temporal ownership proof.',
   'Frozen observed DLL instruction map and byte-pinned EXE body/window admission. Native/DLL percall30second and2million instruction acquisition budgets are not planner performance.'
  ],original_completed_action_transitions=0,full_turn_original_comparisons=0,fair_input_admissions=0,held_out_cases=0,search_certificates=0,gate_promotions=0,ledger_promotions=0,
  next_blocker='Admit original selected Move/action context and join actual callback effect to dispatcher/settlement and next decision state; then broaden independently sourced fidelity corpus before S1/whole gates.')
