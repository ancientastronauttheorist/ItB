"""Original native Skill constructors under pinned unchanged stock Lua defaults.

Offline dependency evidence only: no loaded Pawn, original action admission,
completed tactical transition, fair input or whole-turn claim.
"""
import json
from pathlib import Path
import time

from src.observatory import solver_first_path_oracle as api
from src.observatory import solver_first_cache_emitter as cache
from src.observatory import solver_first_lua_vm as vm
from src.observatory.solver_first_lua_vm import DLL_BASE

BOUNDARY=api.ROOT/'data/solver_first/s1_loaded_skill_boundary.json'
BOUNDARY_SHA='f3a933bb079ce263139db6cfb7e4d4c15b2ab48d09a45edcc0725386a59e9571'
MAP=api.ROOT/'data/solver_first/s1_loaded_skill_instruction_admission.json'
MAP_SHA='e3f0ad3a89f46efa687604e325c8e6cc13b2c67531b68b5e6f525e3da27785d0'


def boundary():
    raw=BOUNDARY.read_bytes()
    api.require(api.sha(raw)==BOUNDARY_SHA,'loaded Skill boundary differs')
    return json.loads(raw)


class SkillMachine(cache.CacheEmitterMachine):
    def execute(self, entry, args, receiver=0, edx=0, cleanup=0):
        self.trace, self.imports, self.failure = [], [], None
        esp = api.STACK + 0x8000
        self.put(esp, api.RETURN)
        for i, arg in enumerate(args):
            self.put(esp + 4 + 4 * i, arg)
        for reg, value in ((self.x.UC_X86_REG_ESP, esp), (self.x.UC_X86_REG_ECX, receiver),
                           (self.x.UC_X86_REG_EDX, edx), (self.x.UC_X86_REG_EFLAGS, 0x202)):
            self.uc.reg_write(reg, value)
        started = time.perf_counter()
        try:
            self.uc.emu_start(api.BASE + entry, api.RETURN + 1, count=api.LIMIT, timeout=30_000_000)
        except Exception as exc:
            self.fail(exc)
        returned = self.uc.reg_read(self.x.UC_X86_REG_EIP) == api.RETURN
        stack_ok = self.uc.reg_read(self.x.UC_X86_REG_ESP) == esp + 4 + cleanup
        return dict(entry_rva=entry, arguments=args, ecx=receiver, edx=edx, cleanup_bytes=cleanup,
            returned=returned, stack_ok=stack_ok, failure=self.failure, eax=self.uc.reg_read(self.x.UC_X86_REG_EAX),
            trace=list(self.trace), imports=list(self.imports), instructions=len(self.trace),
            wall_seconds=time.perf_counter() - started, summary=self.diagnostic())


    def cdecl(self, name, args):
        entry = self.exports[name]
        self.trace, self.imports, self.failure = [], [], None
        allocation_start = len(self.allocator_calls)
        esp = api.STACK + 0x8000
        self.put(esp, api.RETURN)
        for i, arg in enumerate(args):
            self.put(esp + 4 + i * 4, arg)
        self.uc.reg_write(self.x.UC_X86_REG_ESP, esp)
        self.uc.reg_write(self.x.UC_X86_REG_ECX, 0)
        self.uc.reg_write(self.x.UC_X86_REG_EFLAGS, 0x202)
        try:
            self.uc.emu_start(DLL_BASE + entry, api.RETURN + 1, count=api.LIMIT, timeout=30_000_000)
        except Exception as exc:
            self.fail(exc)
        returned = self.uc.reg_read(self.x.UC_X86_REG_EIP) == api.RETURN
        stack_ok = self.uc.reg_read(self.x.UC_X86_REG_ESP) == esp + 4
        result = dict(name=name, dll_rva=entry, arguments=args, returned=returned, cdecl_stack_ok=stack_ok,
            eax=self.uc.reg_read(self.x.UC_X86_REG_EAX), instructions=len(self.trace),
            failure=self.failure if self.failure else None, trace=self.trace,
            imports=self.imports, allocator_calls=self.allocator_calls[allocation_start:])
        if not returned and not result["failure"]:
            result["failure"] = "instruction/time limit exhausted"
        return result


def register_tip_data(m,calls,observations,original,dll):
    L=observations['lua_state']
    descriptor,key,chunk,module=[api.BOARD+x for x in (0x76000,0x77000,0x78000,0x73000)]
    original(0x7360)
    observations['tip_registry']=dict(native_id=m.get(0x8d9100),counter=m.get(0x8d8948),size=m.get(0x8d91b4))
    original(0x2823e0,[0],descriptor,cleanup=4)
    for entry in (0x289dc0,0x289ea0):
        api.require(original(entry,[0,0],descriptor,cleanup=8)==descriptor,'Tip builder receiver differs')
    for name,offset in ((0x82e58c,0),(0x837e40,24)):
        api.require(original(0x283010,[name,offset],descriptor,cleanup=8)==descriptor,'Tip property receiver differs')
    original(0x2e66c0,[m.get(descriptor)],module,cleanup=4)
    text=b'local a=TipData(); local b=TipData("marker_type","marker_value"); return a,a.type,a.value,b,b.type,b.value'
    m.uc.mem_write(key,text);m.uc.mem_write(chunk,b'TipData original control\0')
    api.require(dll('luaL_loadbuffer',[L,key,len(text),chunk])==0,'Tip control compile failed')
    status=dll('lua_pcall',[L,0,6,0])
    values=[]
    count=dll('lua_gettop',[L])
    for i in range(1,count+1):
        typ=dll('lua_type',[L,i]);row=dict(lua_type=typ)
        if typ==4:
            ptr=dll('lua_tolstring',[L,i,0]);raw=bytes(m.uc.mem_read(ptr,128));row['text']=raw.split(b'\0',1)[0].decode()
        values.append(row)
    observations['tip_control']=dict(pcall_status=status,values=values)
    api.require(status==0,'Tip control pcall failed: '+str(values))
    api.require(values==[{'lua_type':7},{'lua_type':4,'text':''},{'lua_type':4,'text':''},{'lua_type':7},{'lua_type':4,'text':'marker_type'},{'lua_type':4,'text':'marker_value'}],'native Tip properties differ')
    dll('lua_settop',[L,0])


def continue_skills(executable,m,calls,o,original,dll):
    executable=Path(executable)
    register_tip_data(m,calls,o,original,dll)
    L=o['lua_state'];key=api.BOARD+0x77000;chunk=api.BOARD+0x78000
    packet=boundary()
    for row in packet['original_body_pins']:
        entry=int(row['entry_rva'],16);m.source.verify(entry)
        api.require(m.source.verified[entry]['body_sha256']==row['body_sha256'],'skill source body differs')
    for row in packet['data_pins']:
        off=m.source.image.rva_to_file_offset(int(row['start_rva'],16))
        api.require(api.sha(m.source.data[off:off+row['size']])==row['sha256'],'skill source data differs')
    for row in packet['original_windows']:
        rva=int(row.get('start_rva',row.get('entry_rva')),16);size=row['size'];m.source.check_window(rva,size,row['sha256'])
        if row.get('atlas_entry_present') is False:
            cursor=rva
            for ins in m.source.decoder.disasm(m.source.bytes_at(rva,size),api.BASE+rva):
                api.require(ins.address==api.BASE+cursor,'initializer decoder gap');m.source.points[cursor]=bytes(ins.bytes);cursor+=ins.size
            api.require(cursor==rva+size,'initializer extent differs')
            m.source.verified[rva]=dict(entry_rva=hex(rva),body_size=size,body_sha256=row['sha256'],ranges=[dict(start_rva=hex(rva),size=size)],admission='explicit source-pinned complete vector constructor window; not atlas owner')
    api.require(m.exports['luaopen_string']==int(packet['original_lua_library_export']['entry_rva'],16),'Lua string export differs')
    dll('luaopen_string',[L]);dll('lua_settop',[L,0])
    for name,value in [('ZONE_NONE',0),('FULL_DELAY',-1)]:
        m.uc.mem_write(key,name.encode()+b'\0');dll('lua_pushinteger',[L,value&0xffffffff]);dll('lua_setfield',[L,0xffffd8ee,key])
    o['loaded_stock_slices']=[]
    for row in packet['exact_stock_slices']:
        raw=(executable.parent/row['game_relative_path']).read_bytes()
        api.require(api.sha(raw)==row['complete_file_raw_sha256'],'whole stock script differs')
        source=raw[row['byte_start']:row['byte_end_exclusive']]
        api.require(api.sha(source)==row['raw_sha256'],'stock slice differs')
        m.uc.mem_write(key,source);m.uc.mem_write(chunk,row['id'].encode()+b'\0')
        api.require(dll('luaL_loadbuffer',[L,key,len(source),chunk])==0,'compile '+row['id'])
        api.require(dll('lua_pcall',[L,0,0,0])==0,'execute '+row['id'])
        o['loaded_stock_slices'].append(row['id'])
    from src.observatory.resource_archive import scan_resource_archive
    asset=packet['default_icon']
    archive_path=executable.parent/'resources/resource.dat';archive=scan_resource_archive(archive_path)
    api.require(archive['sha256']==asset['archive_sha256'],'icon archive differs')
    record=next(r for r in archive['records'] if r['path']==asset['path'])
    with archive_path.open('rb') as h:
        h.seek(record['payload_offset']);encoded=h.read(record['payload_size'])
    api.require(api.sha(encoded)==asset['encoded_sha256'],'icon encoded input differs')
    dctx,data,w,h,n,bitmap=[api.BOARD+x for x in (0x1000,0x10000,0x2000,0x2004,0x2008,0x3000)]
    m.uc.mem_write(dctx,b'\0'*0x100);m.uc.mem_write(data,encoded)
    for off,value in [(0x10,0),(0x20,0),(0xa8,data),(0xac,data+len(encoded)),(0xb0,data)]:m.put(dctx+off,value)
    pixels=original(0x3f330,[h,n,4],dctx,edx=w)
    width,height=m.get(w),m.get(h)
    api.require((width,height,m.get(n))==(asset['width'],asset['height'],asset['components']),'icon decode projection differs')
    rgba=m.live_bytes(pixels,width*height*4);api.require(api.sha(rgba)==asset['rgba_sha256'],'icon pixels differ')
    m.uc.mem_write(bitmap,b'\0'*16);original(0x99ea0,[pixels,width,height],bitmap,cleanup=12);m.put(0x894b54,0xde1)
    texture=original(0x9a2c0,receiver=bitmap);api.require(m.context.readback(texture,width,height)==rgba,'icon GPU storage differs')
    name=asset['path'].encode();ptr=original(0x3574db,[len(name)+1]);m.uc.mem_write(ptr,name+b'\0')
    original(0xc0d60,[texture,width,height,ptr,0,0,0,len(name),len(name)],cleanup=36)
    lookup=asset['path'][4:].encode();ptr=original(0x3574db,[len(lookup)+1]);m.uc.mem_write(ptr,lookup+b'\0')
    wrapper=original(0xbe8f0,[ptr,0,0,0,len(lookup),len(lookup)],0x8d5660,cleanup=24)
    o['default_icon']=dict(texture=texture,wrapper=wrapper,width=width,height=height,rgba_sha256=api.sha(rgba))
    original(0x9a1b0,receiver=bitmap);original(0x36fb17,[pixels])
    pair,name,context,tag,manager=[api.BOARD+x for x in (0x79000,0x79010,0x79030,0x79034,0x79100)]
    original(0x7e10,[0x82a7a0],name,cleanup=4);m.put(context,0);m.put(tag,0)
    api.require(original(0x1c9bf0,[name,tag],pair,edx=context)==pair,'Move factory result differs')
    move,control=m.get(pair),m.get(pair+4)
    def projection(skill,ctrl):
        vec=[]
        for off in (0x164,0x174,0x18c):
            begin,end,capacity=[m.get(skill+off+i*4) for i in range(3)]
            api.require(begin<=end<=capacity and (end-begin)%4==0,'native vector bounds differ')
            vec.append([m.get(begin+i*4) for i in range((end-begin)//4)])
        return dict(skill=skill,control=ctrl,strong=m.get(ctrl+4),weak=m.get(ctrl+8),vtable=m.get(ctrl),allocation_size=m.allocations[ctrl],upgrades=m.get(skill+0x184),current_upgrades=m.get(skill+0x200),power_cost=m.get(skill+0x15c),limited=m.get(skill+0x160),upgrade_cost_cells=vec[:2],power_cost_cells=vec[2],icon=m.get(skill+0x1fc))
    o['native_Move']=projection(move,control)
    api.require(o['native_Move']['allocation_size']==568 and o['native_Move']['vtable']==0x82b7f0,'Move control identity differs')
    api.require(move==control+12 and o['native_Move']['strong']==1 and o['native_Move']['weak']==1,'Move shared ownership differs')
    api.require(o['native_Move']['upgrades']==0 and o['native_Move']['current_upgrades']==0 and o['native_Move']['power_cost']==0 and o['native_Move']['limited']==0 and o['native_Move']['upgrade_cost_cells']==[[0],[0]] and o['native_Move']['power_cost_cells']==[] and o['native_Move']['icon']==wrapper,'Move stock fields differ')
    api.require(original(0x226f00,[0],manager,cleanup=4)==manager,'manager result differs')
    repair,repair_control=m.get(manager+0x68),m.get(manager+0x6c)
    o['native_Repair']=projection(repair,repair_control)
    api.require(o['native_Repair']['allocation_size']==568 and o['native_Repair']['vtable']==0x82b7f0,'Repair control identity differs')
    api.require(repair==repair_control+12 and o['native_Repair']['strong']==1 and o['native_Repair']['weak']==1 and o['native_Repair']['upgrades']==2 and o['native_Repair']['current_upgrades']==2 and o['native_Repair']['power_cost']==0 and o['native_Repair']['limited']==0 and o['native_Repair']['upgrade_cost_cells']==[[0],[0]] and o['native_Repair']['power_cost_cells']==[] and o['native_Repair']['icon']==wrapper,'Repair stock fields differ')
    before=[m.get(manager+x) for x in (4,8,12)]
    original(0x227110,[move,control],manager,cleanup=8)
    begin,end,cap=[m.get(manager+x) for x in (4,8,12)]
    o['base_manager_append']=dict(before=before,after=[begin,end,cap],owned_pair=[m.get(begin),m.get(begin+4)],strong=m.get(control+4),weak=m.get(control+8),manager_vtable=m.get(manager),context=m.get(move+0x110),owner=m.get(move+0x188),mod=bytes(m.uc.mem_read(move+0x228,1))[0],conservative=bytes(m.uc.mem_read(move+0x229,1))[0])
    api.require(before==[0,0,0] and end-begin==8 and [m.get(begin),m.get(begin+4)]==[move,control] and m.get(control+4)==1,'actual append/refcount differs')
    api.require(o['base_manager_append']['manager_vtable']==0x82e184 and o['base_manager_append']['owner']==0xffffffff and o['base_manager_append']['context']==0 and o['base_manager_append']['mod']==0 and o['base_manager_append']['conservative']==0,'base manager postappend defaults differ')
    api.require(dll('lua_gettop',[L])==0,'Lua stack leaked')

def run(executable, private_dir):
    """Acquire one fresh frozen-map world; components share its provenance."""
    from src.observatory.solver_first_image_resource import ARCHIVE_SHA
    executable,private_dir=Path(executable),Path(private_dir)
    api.require(not private_dir.exists(),'private output directory is create-only')
    packet=boundary()
    map_raw=MAP.read_bytes()
    api.require(api.sha(map_raw)==MAP_SHA,'loaded Skill instruction map differs')
    map_doc=json.loads(map_raw)
    api.require(map_doc['dll_sha256']==vm.DLL_SHA,'instruction map DLL differs')
    paths=['src/observatory/solver_first_loaded_skill.py','scripts/solver_first_loaded_skill.py',
        'src/observatory/solver_first_cache_emitter.py','src/observatory/solver_first_lua_emitters.py',
        'src/observatory/solver_first_lua_vm.py','src/observatory/solver_first_image_resource.py',
        'src/observatory/solver_first_gl_texture.py','src/observatory/solver_first_path_oracle.py',
        'src/observatory/pe_anchor_map.py','src/observatory/resource_archive.py',
        'data/solver_first/s1_loaded_skill_boundary.json','data/solver_first/s1_loaded_skill_instruction_admission.json',
        'data/solver_first/s1_cache_emitter_boundary.json']
    source_pins={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths}
    runtime_base=api.runtime_identity()
    script_pins={row['game_relative_path']:row['complete_file_raw_sha256'] for row in packet['exact_stock_slices']}
    from src.observatory.solver_first_lua_emitters import SOURCES
    script_pins.update(SOURCES)
    script_pins.update({p:row['sha256'] for p,row in cache.boundary()['game_sources'].items()})
    api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'installed stock sources differ')
    private_dir.mkdir(parents=True)
    def continuation(m,calls,o,original,dll):
        continue_skills(executable,m,calls,o,original,dll)
    private,m=cache.acquire(executable,map_doc['instructions'],continuation=continuation,machine_type=SkillMachine)
    private['source_lf_sha256']=source_pins
    private['driver_limits']=dict(native_and_DLL_wall_time_limit_us=30_000_000,instruction_limit_per_call=api.LIMIT)
    receipt=private_dir/'world.json'
    with receipt.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(private,handle,indent=2,sort_keys=True,allow_nan=False);handle.write('\n')
    api.require(source_pins=={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths},'acquisition sources changed')
    api.require(runtime_base==api.runtime_identity(),'runtime changed')
    api.require(MAP.read_bytes()==map_raw,'instruction map changed')
    api.require(api.sha(executable.read_bytes())==api.EXE_SHA and api.sha((executable.parent/'lua5.1.dll').read_bytes())==vm.DLL_SHA and api.sha((executable.parent/'resources/resource.dat').read_bytes())==ARCHIVE_SHA,'original inputs changed')
    api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'installed stock sources changed')
    matched=private['status']=='complete_joined_dependency_and_declared_continuation' and private['failure'] is None
    runtime={**runtime_base,'wall_time_limit_us':30_000_000}
    identities=[]
    for row in private['verified_source_bodies']:
        executed=any(int(span['start_rva'],16)<=at<int(span['start_rva'],16)+span['size'] for span in row['ranges'] for at in m.source.executed_rvas)
        identities.append({**row,'executed':executed})
    o=private['observations']
    return dict(schema_version=1,corpus_version='s1-original-loaded-Skill-dependency-development-v1',
        game_build=13725832,baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',simulator_version=413,
        information_mode='Supplied offline stock-source/native dependency world; no player-information or legal-action admission.',
        objective='Close genuine Skill defaults, Move/Repair construction and base-manager ownership prerequisites for loaded Move action acquisition.',
        attempted=1,admitted=int(matched),matched=int(matched),failed=int(not matched),excluded=0,
        status='complete_native_Move_Repair_base_manager_dependency' if matched else 'failed',failure=private['failure'],
        planned_component_checks=dict(TipData_constructor_controls=2,default_icon_assets=1,Move_factories=1,Repair_factories=1,base_manager_appends=1),
        observations=o,source_lf_sha256=source_pins,stock_script_sha256=script_pins,runtime=runtime,
        executable_sha256=api.EXE_SHA,lua_dll_sha256=vm.DLL_SHA,archive_sha256=ARCHIVE_SHA,
        boundary_sha256=BOUNDARY_SHA,instruction_map_sha256=MAP_SHA,private_receipt_sha256=api.sha(receipt.read_bytes()),
        instruction_admission='Frozen observed DLL instructions; every visited original EXE instruction has byte-verified atlas or explicit-window admission.',
        original_call_count=len(private['calls']),instruction_count=sum(c['instructions'] for c in private['calls']),
        executed_DLL_instruction_points=len(m.dll_points),lua_allocator_callback_count=sum(len(c['allocator_calls']) for c in private['calls']),
        retained_guest_allocations=len(m.live),retained_guest_requested_bytes=sum(m.allocations[p] for p in m.live),
        original_body_identities=identities,calls=[{k:v for k,v in c.items() if k not in ('trace','allocator_calls')} for c in private['calls']],
        supplied_boundaries=[
            'Bounded unchanged original-body and actual Lua DLL execution. Supplied successful heap/custom allocator/empty SEH and completed CRT guard/TLS epoch premises; full process/bootstrap/error paths excluded.',
            'Actual null_type/Point then TipData type insertion in a fresh isolated three-type registry. IDs are outputs, not supplied full-game type ordering. Constructor/property-only bindings omit other class methods and the full namespace.',
            'Nine exact unchanged stock slices and actual Lua base/string libraries supplied through their original interpreters; normal game/module/overlay bootstrap and unused GAME/LOG branches excluded.',
            'Source-backed ZONE_NONE0,FULL_DELAY-1,INT_MAX constants supplied through original Lua APIs. Whole native constant-export bootstrap excluded.',
            'Pinned archive default-icon input independently decoded for expectations; native PNG decode, CPU/texture/cache constructors and actual host GL readback execute. This reachable constructor prerequisite does not admit normal file loading/rendering.',
            'Source caller strings, context0/tag0 and constructor scratch are supplied. Original Move/Repair shared factories and fields execute; no final Skill/control/cache result substitution.',
            'Actual base-manager226f00 initializes Repair, actual227110 copies/consumes the byvalue Move pair and leaves the vector sole strong owner. Factory pair scratch becomes an unowned alias; it is not another strong owner.',
            'Base-manager native vtable/default virtual methods are retained. This is not Pawn virtual behavior, definition/Pilot/animation loading, deployed actor readiness, complete legal targets, SkillEffect dispatch or action settlement.',
            'Guest Lua/registry/cache/Skill/manager ownership remains retained. Host graphics teardown completes separately; saved guest handles cannot resume execution afterward. No full guest destruction or unified temporal ownership ledger claim.',
            'Per-call native/DLL host driver budgets are30seconds and2million instructions; original opcode/script contents, callbacks and ABIs remain unchanged. Acquisition time/memory is not planner performance.',
            'Component checks share one world. Movement/attack/wait/end-turn, enemy/environment/spawn, undo/save, mission and campaign continuation remain excluded.'],
        original_completed_action_transitions=0,full_turn_original_comparisons=0,fair_input_admissions=0,
        held_out_cases=0,search_certificates=0,gate_promotions=0,ledger_promotions=0,
        next_blocker='Genuine loaded Pawn/Pilot/animation dependencies and deployed actor state, typed Board/Pawn/PointList callbacks, then Move target/effect/dispatcher admission and next-decision continuity.')
