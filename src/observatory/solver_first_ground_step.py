"""Bounded original N2 route continuation; loaded Move and full turns remain open."""
import json
from pathlib import Path
import struct
from src.observatory import solver_first_path_oracle as api
from src.observatory import solver_first_cache_emitter as cache
from src.observatory.solver_first_cache_emitter import CacheEmitterMachine
WORLD = 0x11000000
BOUNDARY = api.ROOT / 'data/solver_first/s1_ground_step_boundary.json'
BOUNDARY_SHA = '8d2e038327acbe10a6ab08591c83e69e9abc232af0499a247f2df43e6ccea971'

def boundary():
    raw = BOUNDARY.read_bytes()
    api.require(api.sha(raw) == BOUNDARY_SHA, 'ground-step boundary identity differs')
    return json.loads(raw)

class RandMachine(CacheEmitterMachine):
    def __init__(self,exe,admission):
        super().__init__(exe,admission)
        self.service_packet=boundary();self.service_packet_sha256=BOUNDARY_SHA
        for row in self.service_packet['body_pins']:
            entry=int(row['entry_rva'],16);self.source.verify(entry)
            api.require(self.source.verified[entry]['body_sha256']==row['body_sha256'],'CRT body pin differs')
        for row in self.service_packet['initializer_windows']:self.admit_window(row)
        for row in self.service_packet['data_pins']:
            offset=self.source.image.rva_to_file_offset(int(row['start_rva'],16));api.require(offset is not None and api.sha(self.source.data[offset:offset+row['size']])==row['sha256'],'CRT/biome mapped-data pin differs')
        self.win_events=[];self.last_error=0;self.criticals={};self.modules={};self.fls={};self.fls_callbacks={}
        self.dynamic={};self.last_service_attempt=None
        for i,row in enumerate(self.service_packet['dynamic_export_seams']):
            at=api.IMPORT+0x9000+i*16;api.require(at not in self.stubs,'external-service entry collision')
            self.stubs[at]=dict(library='KERNEL32.dll',name=row['name'],external_dynamic=True)
            self.uc.mem_write(at,b'\xc3');self.dynamic[row['name']]=(at,row)
    def admit_window(self,row):
        rva=int(row['start_rva'],16);size=row['size'];self.source.check_window(rva,size,row['sha256'])
        raw=self.source.bytes_at(rva,size);cursor=rva
        for ins in self.source.decoder.disasm(raw,api.BASE+rva):
            api.require(ins.address==api.BASE+cursor,'initializer decoder gap');self.source.points[cursor]=bytes(ins.bytes);cursor+=ins.size
        api.require(cursor==rva+size,'initializer decode extent differs')
        self.source.verified[rva]=dict(entry_rva=hex(rva),body_size=size,body_sha256=row['sha256'],ranges=[dict(start_rva=hex(rva),size=size)],admission='explicit pinned initializer window, not atlas owner')
    def cstring(self,at,wide=False):
        data=bytearray();unit=2 if wide else 1
        for i in range(128):
            raw=bytes(self.uc.mem_read(at+i*unit,unit))
            if raw==b'\0'*unit:return data.decode('utf-16-le' if wide else 'ascii')
            data.extend(raw)
        raise api.OracleError('external name exceeds declared bound')
    def respond_import(self,at):
        row=self.stubs[at];esp=self.uc.reg_read(self.x.UC_X86_REG_ESP);ret=self.get(esp)-api.BASE
        if row.get('external_dynamic'):
            _,seam=self.dynamic[row['name']];call=int(seam['dynamic_call_rva'],16)
            api.require(ret==int(seam['dynamic_return_rva'],16),'dynamic service caller differs')
            api.require(self.trace and self.trace[-1]==[call,2],'dynamic call trace differs')
            api.require(api.sha(self.source.bytes_at(call,2))==seam['opcode_sha256'],'dynamic call opcode differs')
        else:
            seams=[s for s in self.service_packet['import_seams'] if s['name']==row['name'] and int(s['return_rva'],16)==ret]
            if not seams:return super().respond_import(at)
            api.require(len(seams)==1,'ambiguous service seam');seam=seams[0];call=int(seam['call_rva'],16)
            api.require(row['library'].lower()=='kernel32.dll' and int(row['iat_rva'],16)==int(seam['iat_rva'],16),'Win32 import identity differs')
            api.require(self.get(api.BASE+int(seam['iat_rva'],16))==at,'Win32 IAT target differs')
            api.require(self.trace and self.trace[-1]==[call,seam['opcode_size']],'Win32 import call trace differs')
            api.require(api.sha(self.source.bytes_at(call,seam['opcode_size']))==seam['opcode_sha256'],'Win32 import opcode differs')
        argc=seam['argc'];api.require(api.STACK<=esp and esp+4+4*argc<=api.STACK+0x10000,'Win32 frame outside stack')
        args=[self.get(esp+4+i*4) for i in range(argc)];name=row['name'];result=0;detail={}
        self.last_service_attempt=dict(name=name,arguments=args,caller_return_rva=ret)
        if name=='GetLastError':result=self.last_error
        elif name=='SetLastError':self.last_error=args[0]
        elif name=='HeapAlloc':
            api.require(ret==0x388c7d and args==[0x12345678,8,868],'calloc heap contract differs')
            count=args[2];result=self.next_alloc;self.next_alloc+=(count+15)&~15
            api.require(self.next_alloc<=api.HEAP+0x400000,'heap exhausted')
            self.allocations[result]=count;self.allocation_starts.append(result);self.live.add(result);self.uc.mem_write(result,b'\0'*count)
        elif name=='LoadLibraryExW':
            alias=self.cstring(args[0],True);allowed=[x['name'] for x in self.service_packet['resolver_module_names']]
            api.require(alias in allowed and args[0] in [api.BASE+int(x['string_rva'],16) for x in self.service_packet['resolver_module_names']] and args[1:]==[0,0x800],'module acquisition arguments differ')
            result=0x5c000000+len(self.modules)*16;self.modules[result]=dict(alias=alias,refs=1);detail=dict(alias=alias)
        elif name=='GetProcAddress':
            api.require(args[0] in self.modules and self.modules[args[0]]['refs']>0,'module handle not owned')
            export=self.cstring(args[1]);api.require(export in self.dynamic,'undeclared CRT export')
            result=self.dynamic[export][0];detail=dict(export=export)
        elif name=='FreeLibrary':
            api.require(args[0] in self.modules and self.modules[args[0]]['refs']>0,'module release without ownership')
            self.modules[args[0]]['refs']-=1;result=1
        elif name=='InitializeCriticalSectionEx':
            ptr,spin,flags=args;api.require(ptr not in self.criticals and ptr in range(0x8b70a8,0x8b70a8+13*24,24) and spin==4000 and flags==0,'critical-section initialization differs')
            self.criticals[ptr]=0;result=1
        elif name=='EnterCriticalSection':
            ptr=args[0];api.require(ptr in self.criticals,'enter before critical-section initialization');self.criticals[ptr]+=1
        elif name=='LeaveCriticalSection':
            ptr=args[0];api.require(ptr in self.criticals and self.criticals[ptr]>0,'unbalanced critical-section release');self.criticals[ptr]-=1
        elif name=='FlsAlloc':
            api.require(args==[0x78ec1d] and not self.fls,'FLS slot initialization differs');result=0;self.fls[result]=0;self.fls_callbacks[result]=args[0]
        elif name=='FlsGetValue':
            api.require(args[0] in self.fls,'FLS read of unallocated slot');result=self.fls[args[0]]
        elif name=='FlsSetValue':
            slot,ptr=args;api.require(slot in self.fls and ptr in self.live and self.allocations[ptr]==868,'FLS assignment without native PTD ownership');self.fls[slot]=ptr;result=1
        else:raise api.OracleError('unimplemented positive Win32 CRT service '+name)
        event=dict(name=name,arguments=args,result=result,caller_return_rva=ret,external='supplied normal one-thread/FLS-present Win32 service',**detail)
        self.win_events.append(event);self.imports.append(event)
        self.uc.reg_write(self.x.UC_X86_REG_EAX,result);self.uc.reg_write(self.x.UC_X86_REG_ESP,esp+4+seam['stdcall_callee_cleanup_bytes']);self.uc.reg_write(self.x.UC_X86_REG_EIP,api.BASE+ret)
    def platform_snapshot(self):
        return json.loads(json.dumps(dict(last_service_attempt=self.last_service_attempt,service_packet_sha256=self.service_packet_sha256,events=self.win_events,last_error=self.last_error,critical_recursion=self.criticals,modules=self.modules,fls_slots=self.fls,fls_callbacks=self.fls_callbacks)))

def fixture_at(self, recipe, board):
    self.put(board, api.BASE + 0x42e2fc)
    self.put(board + 0xc, api.BASE + 0x42e258)
    head, columns = board + 0x3000, board + 0x4000
    self.put(board + 4, head)
    for offset in (0, 4, 8):
        self.put(head + offset, head)
    self.uc.mem_write(head + 0xc, b"\1\1")
    self.put(board + 0x48, 8); self.put(board + 0x4c, 8)
    for offset, value in [(0x50, columns), (0x54, columns + 96), (0x58, columns + 96)]:
        self.put(board + offset, value)
    for px in range(8):
        begin = board + 0x10000 + px * 8 * 0x2bbc
        for offset, value in [(0, begin), (4, begin + 8 * 0x2bbc), (8, begin + 8 * 0x2bbc)]:
            self.put(columns + px * 12 + offset, value)
        for py in range(8):
            terrain = (3 if py == 1 and recipe["water"] else 0) if px == 0 and py <= 3 else 4
            self.put(begin + py * 0x2bbc + 0x2ae0, terrain)
    for py, team in [(0, 1 if recipe["occupied"] else None), (1, recipe["blocker_team"])]:
        if team is None:
            continue
        pawn, vector = board + 0x100000 + py * 0x1000, board + 0x6000 + py * 16
        self.put(pawn, api.BASE + 0x42e320); self.put(pawn + 0x8a8, 3)
        self.put(pawn + 0xb0, team); self.put(pawn + 0x8ec, 0); self.put(pawn + 0x8f0, py)
        self.put(vector, pawn)
        tile = board + 0x10000 + py * 0x2bbc
        for offset, value in [(0xa0, vector), (0xa4, vector + 4), (0xa8, vector + 4)]:
            self.put(tile + offset, value)
    return api.sha(bytes(self.uc.mem_read(board, 0x200000)))

def vector_points(m,header):
    begin,end,cap=[m.get(header+4*i) for i in range(3)]
    if begin==0:
        api.require(end==cap==0,'null vector differs');return []
    api.require(begin in m.live and begin<=end<=cap and cap-begin<=m.allocations[begin] and (end-begin)%8==0,'point vector ownership/extent differs')
    return [list(struct.unpack('<ii',m.uc.mem_read(at,8))) for at in range(begin,end,8)]

def continue_step(m,calls,observations,original,dll):
    # Native process-init prefix, retaining the original PE cookie.
    api.require(m.get(0x893f28)==0xbb40e64e,'original security cookie differs')
    for entry in [0x39172a,0x388b84,0x38cdde,0x38ee3b]:
        result=original(entry)
        if entry==0x39172a:
            words=[m.get(0x8b75a8+4*i) for i in range(32)]
            api.require(len(set(words))==1 and words[0]!=0,'native encoded-NULL cache extent differs')
            observations['encoded_cache_after_initializer']=words
        if entry!=0x38cdde:api.require(result&255==1,'native initializer did not return AL1')
    slot=m.get(0x894290);ptd=m.fls[slot]
    api.require(ptd in m.live and m.allocations[ptd]==868 and m.get(ptd+0x18)==1,'native PTD ownership/default seed differs')
    api.require(m.get(0x8b7550)==0x894298 and m.get(ptd+0x4c)==0x894298 and m.get(ptd+0x48)==0x894710,'native default locale pointers differ')
    api.require(len(m.criticals)==13 and not any(m.criticals.values()),'native lock initialization/recursion differs')
    observations['native_CRT_initialization']=dict(slot=slot,ptd=ptd,seed=m.get(ptd+0x18),locale=m.get(ptd+0x4c),multibyte=m.get(ptd+0x48),cookie=m.get(0x893f28),export_cache_words=[m.get(0x8b75a8+4*i) for i in range(32)],platform=m.platform_snapshot())
    m.uc.mem_map(WORLD,0x200000)
    recipe=api.recipes()[1];fixture_at(m,recipe,WORLD)
    pawn,definition,control=WORLD+0x100000,WORLD+0x110000,WORLD+0x113000
    m.put(pawn+0x944,WORLD);m.put(pawn+0x874,definition);m.put(pawn+0x1168,0x7fffffff)
    m.uc.mem_write(pawn+0x99d,b'\1');m.uc.mem_write(pawn+0x91e,b'\1')
    original(0x15dfb0,receiver=pawn+0xa74)
    pilot=control+12;m.put(pawn+0xa6c,pilot);m.put(pawn+0xa70,control)
    for offset,value in [(0,api.BASE+0x42b804),(4,1),(8,1)]:m.put(control+offset,value)
    m.put(pilot,0x835dcc);m.put(pilot+0x74,15)
    # Separate source-pinned call-free movement DIR initializer, not atlas ownership.
    init_rva,init_size,init_sha=0x2fb0,81,'04acd19f82e7f95d52dccef7989876e50bf3adab40aae1b037ce5996265d9b3e'
    m.source.check_window(init_rva,init_size,init_sha)
    raw=m.source.bytes_at(init_rva,init_size);cursor=init_rva
    for ins in m.source.decoder.disasm(raw,api.BASE+init_rva):
        api.require(ins.address==api.BASE+cursor,'DIR initializer decoder gap');m.source.points[cursor]=bytes(ins.bytes);cursor+=ins.size
    api.require(cursor==init_rva+init_size,'DIR initializer decode extent differs')
    m.source.verified[init_rva]=dict(entry_rva=hex(init_rva),body_size=init_size,body_sha256=init_sha,ranges=[dict(start_rva=hex(init_rva),size=init_size)],admission='explicit initializer window; not atlas owner')
    original(init_rva);original(0x3030)
    dir_values=list(struct.unpack('<8i',m.uc.mem_read(0x8cc608,32)))
    api.require(dir_values==[0,-1,1,0,0,1,-1,0],'original movement DIR table differs')
    original(0x7e10,[0x82ed4c],0x8d68bc,cleanup=4)
    api.require(m.get(0x8d68bc+16)==11 and m.get(0x8d68bc+20)==15 and bytes(m.uc.mem_read(0x8d68bc,12))==b'tiles_grass\0','native biome-string constructor differs')
    m.put(0x8d57e4,17);m.put(0x8d57ec,0x3f800000)
    out=WORLD+0x8000
    original(0x1742d0,[out,0,0,0,1,18],WORLD,cleanup=24)
    query_words=[m.get(out+4*i) for i in range(3)]
    points=m.output(out);api.require(points==[[0,0],[0,1]],'native N2 query vector differs')
    # Genuine original clone preserves the separately owned query vector.
    # The installer call-frame/flag premise remains supplied, not loaded Move.
    clone=WORLD+0x8100;original(0x9a8e0,[out],clone,cleanup=4)
    input_words=[m.get(clone+4*i) for i in range(3)]
    api.require(input_words[0]!=m.get(out) and input_words[0] in m.live and m.get(out) in m.live,'native query clone ownership differs')
    events=[];emitter_names=[];rng_events=[];rng_pending=[];bursts=[]
    tracked={pawn+0x8ec:'pawn_x',pawn+0x8f0:'pawn_y',pawn+0x8fc:'route_begin',pawn+0x900:'route_end',pawn+0x904:'route_capacity',pawn+0x99e:'bMoved',pawn+0x919:'route_timer_active',WORLD+0x10000+0xa4:'origin_occupancy_end',WORLD+0x10000+0x2bbc+0xa4:'target_occupancy_end',WORLD+0x10000+0x2ad0:'origin_emitter_end'}
    def writes(uc,kind,at,width,value,user):
        if at in tracked:
            events.append(dict(field=tracked[at],address=at,width=width,value=value,pc=uc.reg_read(m.x.UC_X86_REG_EIP),rng_completed=len(rng_events)))
    def entries(uc,at,size,user):
        if at==api.BASE+0xbcb10:
            bursts.append(dict(receiver=uc.reg_read(m.x.UC_X86_REG_ECX),seed_before=m.get(ptd+0x18),rng_completed=len(rng_events)))
        if at==api.BASE+0x387f16:
            rng_pending.append(dict(seed_before=m.get(ptd+0x18),return_va=m.get(uc.reg_read(m.x.UC_X86_REG_ESP))))
        if rng_pending and at==rng_pending[-1]['return_va']:
            event=rng_pending.pop();event['seed_after']=m.get(ptd+0x18);event['eax']=uc.reg_read(m.x.UC_X86_REG_EAX)
            expected=(event['seed_before']*0x343fd+0x269ec3)&0xffffffff
            api.require(event['seed_after']==expected and event['eax']==((expected>>16)&0x7fff),'native rand output differs from pinned source recurrence')
            rng_events.append(event)
        if at==api.BASE+0xbb910:
            esp=uc.reg_read(m.x.UC_X86_REG_ESP);length=m.get(esp+4+16);cap=m.get(esp+4+20)
            pointer=m.get(esp+4) if cap>=16 else esp+4
            emitter_names.append(dict(name=bytes(uc.mem_read(pointer,length)).decode('ascii'),length=length,capacity=cap,receiver=uc.reg_read(m.x.UC_X86_REG_ECX)))
    m.uc.hook_add(m.u.UC_HOOK_MEM_WRITE,writes);m.uc.hook_add(m.u.UC_HOOK_CODE,entries)
    observations['joined_route_fixture']=dict(board=WORLD,pawn=pawn,definition=definition,point_query=points,query_words_before=query_words,stored_active_before=bytes(m.uc.mem_read(pawn+0x91c,1))[0],profile=18,team=1,hp=3,Massive_byte=1,Flying_definition_byte=0,biome_native_string='tiles_grass',movement_DIR=dir_values,installer_input_words=input_words,origin_flag=1,caller_transfer='original9a8e0 constructed disjoint clone; supplied root frame copies owned triple and origin-match flag; query vector retained; loaded Move/original caller excluded',before_world_sha256=api.sha(bytes(m.uc.mem_read(WORLD,0x200000))))
    begin=len(calls);exc=None
    try:
        returned=original(0x235f00,input_words+[1],pawn,cleanup=16)
        api.require(returned&255==1,'route installer did not return AL=1')
    except Exception as e:
        exc=str(e)
    finally:
        observations['joined_route_projection']=dict(root_call_index=begin,root_failure=exc,ordered_writes=events,emitter_names=emitter_names,coordinates=[m.get(pawn+0x8ec),m.get(pawn+0x8f0)],route=[m.get(pawn+x) for x in [0x8fc,0x900,0x904]],bMoved=bytes(m.uc.mem_read(pawn+0x99e,1))[0],hp=m.get(pawn+0x8a8),stored_active_after=bytes(m.uc.mem_read(pawn+0x91c,1))[0],target_pawn_pointer=m.get(m.get(WORLD+0x10000+0x2bbc+0xa0)),target_terrain=m.get(WORLD+0x10000+0x2bbc+0x2ae0),query_header=[m.get(out+4*i) for i in range(3)],query_points=vector_points(m,out),clone_live=input_words[0] in m.live,pending_points=vector_points(m,pawn+0x8fc),bursts=bursts,pending_allocation_bytes=list(bytes(m.uc.mem_read(m.get(pawn+0x8fc),8))) if m.get(pawn+0x8fc) in m.live else None,query_live=m.get(out) in m.live,rng_events=rng_events,rng_unreturned=rng_pending,final_seed=m.get(ptd+0x18),platform=m.platform_snapshot(),origin_occupants=(m.get(WORLD+0x10000+0xa4)-m.get(WORLD+0x10000+0xa0))//4,target_occupants=(m.get(WORLD+0x10000+0x2bbc+0xa4)-m.get(WORLD+0x10000+0x2bbc+0xa0))//4,last_trace=calls[-1]['trace'][-30:],guest_pc=m.uc.reg_read(m.x.UC_X86_REG_EIP))
    if exc:raise RuntimeError(exc)
    api.require(observations['joined_route_projection']['coordinates']==[0,1],'joined route did not reach Water')
    api.require(m.get(pawn+0x8fc)==m.get(pawn+0x900),'pending route did not empty')
    api.require(any(e['name']=='Emitter_tiles_grass' for e in emitter_names),'native biome-substituted Dust name missing')
    projection=observations['joined_route_projection']
    api.require(projection['query_points']==points and projection['query_header']==query_words and projection['query_live'],'retained query vector changed')
    api.require(not projection['clone_live'] and m.get(pawn+0x8fc) in m.live and m.get(pawn+0x8fc) not in [input_words[0],m.get(out)],'input/pending/query ownership differs')
    api.require(projection['pending_allocation_bytes']==list(struct.pack('<ii',0,1)),'native pending copy differs')
    api.require(projection['origin_occupants']==0 and projection['target_occupants']==1 and m.get(m.get(WORLD+0x10000+0x2bbc+0xa0))==pawn,'native occupancy transfer differs')
    api.require(len(bursts)==15 and len({e['receiver'] for e in bursts})==1,'native origin emitter burst count/receiver differs')
    grade_burst(m,observations,bursts,rng_events)
    api.require(not rng_pending and rng_events and not any(m.criticals.values()) and m.last_error==0,'native RNG/CRT pending or ownership differs')


def grade_burst(m, observations, bursts, draws):
    """Grade source-derived nontrig cells from observed native RNG results."""
    expected = boundary()['grass_burst_expected_projection']
    returns = [api.BASE + int(row['return_rva'], 16) for row in expected['draws_per_particle']]
    api.require(len(draws) == 120 and [r['return_va'] for r in draws] == returns * 15,
                'native grass RNG draw count/order differs')
    api.require([r['rng_completed'] for r in bursts] == list(range(0, 120, 8)),
                'native per-particle RNG segmentation differs')
    emitter = bursts[0]['receiver']
    api.require(m.get(emitter + 0x20) == float_bits(-10) and m.get(emitter + 0x24) == float_bits(25)
                and bytes(m.uc.mem_read(emitter + 0x59, 1)) == b'\0', 'native burst final emitter cells differ')
    begin, end, capacity = [m.get(emitter + offset) for offset in (0, 4, 8)]
    api.require(end == capacity == begin + 1408 and m.allocations.get(begin) == 1408
                and begin in m.live, 'native burst particle ownership differs')
    life = struct.unpack('<f', m.uc.mem_read(emitter + 0x18, 4))[0]
    rows = []
    for index in range(32):
        at = begin + index * 44
        cells = {offset: m.get(at + offset) for offset in (0, 4, 8, 12, 16, 20, 24, 32, 36, 40)}
        live = bytes(m.uc.mem_read(at + 28, 1))[0]
        if index < 15:
            values = [row['eax'] for row in draws[index * 8:(index + 1) * 8]]
            lifespan = f32(f32(f32(f32(values[7] % 3 - 1) * life) * f32(0.3)) + f32(life * 1.0))
            wanted = {0: float_bits(20 - 2 * index + values[0] % 12 - 6),
                      4: float_bits(10 + index + values[1] % 12 - 6), 16: 0, 20: 0,
                      24: float_bits(lifespan), 32: float_bits(90 * (values[4] % 4)),
                      36: float_bits(f32((1.0 if values[5] % 2 else -1.0) * f32(values[6] % 20))), 40: 0}
            api.require(live == 1 and all(cells[k] == v for k, v in wanted.items()),
                        'native particle nontrig cell differs')
        else:
            api.require(live == 0 and not any(cells.values()), 'native untouched particle cells differ')
        rows.append(dict(index=index, dword_cells={hex(k): v for k, v in cells.items()}, live=live))
    tile = WORLD + 0x10000
    owners = [m.get(tile + 0x2acc + 4 * i) for i in range(3)]
    api.require(owners[0] in m.live and owners[1] == owners[0] + 4 and owners[2] >= owners[1]
                and owners[2] <= owners[0] + m.allocations[owners[0]] and m.get(owners[0]) == emitter,
                'native origin Tile emitter ownership differs')
    append_writes = [r for r in observations['joined_route_projection']['ordered_writes'] if r['field'] == 'origin_emitter_end']
    api.require(append_writes and all(r['rng_completed'] == 120 for r in append_writes), 'Tile emitter append preceded complete burst')
    draw = m.get(emitter + 0x3c)
    api.require(m.get(draw + 0xc) == observations['native_registered_resources'][0]['resource'],
                'native movement Dust resource differs')
    observations['native_grass_burst'] = dict(emitter=emitter, particle_storage=begin,
        storage_sha256=api.sha(m.live_bytes(begin, 1408)), particle_rows=rows,
        live_indices=list(range(15)), untouched_indices=list(range(15, 32)),
        nontrig_graded_dword_offsets=[0, 4, 16, 20, 24, 32, 36, 40],
        ungraded_active_velocity_offsets=[8, 12], ungraded_padding_offsets=[29, 30, 31],
        draw_count=120, draw_order_return_rvas=[at - api.BASE for at in returns],
        Tile_emitter_header=owners, resource=m.get(draw + 0xc))


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def float_bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def run(executable, private_dir):
    from src.observatory.solver_first_image_resource import ARCHIVE_SHA
    from src.observatory.solver_first_lua_emitters import SOURCES
    from src.observatory import solver_first_lua_vm as vm
    executable, private_dir = Path(executable), Path(private_dir)
    api.require(not private_dir.exists(), 'private output directory is create-only')
    private_dir.mkdir(parents=True)
    paths = ['src/observatory/solver_first_ground_step.py', 'scripts/solver_first_ground_step.py',
             'src/observatory/solver_first_cache_emitter.py', 'src/observatory/solver_first_lua_emitters.py',
             'src/observatory/solver_first_lua_vm.py', 'src/observatory/solver_first_image_resource.py',
             'src/observatory/solver_first_gl_texture.py', 'src/observatory/solver_first_path_oracle.py',
             'src/observatory/pe_anchor_map.py', 'src/observatory/resource_archive.py',
             'data/solver_first/s1_ground_step_boundary.json', 'data/solver_first/s1_cache_emitter_boundary.json']
    source_pins = {p: api.sha((api.ROOT / p).read_bytes().replace(b'\r\n', b'\n')) for p in paths}
    runtime = api.runtime_identity()
    scripts = {p: row['sha256'] for p, row in cache.boundary()['game_sources'].items()} | SOURCES
    api.require(all(api.sha((executable.parent / p).read_bytes()) == h for p, h in scripts.items()),
                'installed stock scripts differ')
    for row in boundary()['grass_burst_expected_projection']['script_slice_pins']:
        raw = (executable.parent / row['game_relative_path']).read_bytes()
        api.require(api.sha(raw[row['byte_start']:row['byte_end_exclusive']]) == row['raw_sha256'],
                    'stock burst source slice differs')
    map_raw = cache.MAP.read_bytes()
    api.require(api.sha(map_raw) == cache.MAP_SHA, 'reused frozen DLL instruction map differs')
    private, machine = cache.acquire(executable, json.loads(map_raw)['instructions'],
                                     continuation=continue_step, machine_type=RandMachine)
    private['platform_final'] = machine.platform_snapshot()
    private['boundaries'][0] = ('Cache-prefix type guard uses supplied completed CRT/TLS epoch; '
        'the continuation separately executes native export-cache, lock, locale and FLS/PTD initializers.')
    private['source_lf_sha256'] = source_pins
    receipt = private_dir / 'joined_world.json'
    with receipt.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(private, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')
    api.require(source_pins == {p: api.sha((api.ROOT / p).read_bytes().replace(b'\r\n', b'\n')) for p in paths},
                'tool sources changed')
    api.require(runtime == api.runtime_identity() and cache.MAP.read_bytes() == map_raw, 'runtime/map changed')
    api.require(api.sha(executable.read_bytes()) == api.EXE_SHA
                and api.sha((executable.parent / 'lua5.1.dll').read_bytes()) == vm.DLL_SHA
                and api.sha((executable.parent / 'resources/resource.dat').read_bytes()) == ARCHIVE_SHA,
                'original input identities changed')
    api.require(all(api.sha((executable.parent / p).read_bytes()) == h for p, h in scripts.items()),
                'stock scripts changed')
    matched = private['status'] == 'complete_joined_dependency_and_declared_continuation' and private['failure'] is None
    observations = private['observations']
    if 'joined_route_projection' in observations:
        observations['joined_route_projection'].pop('last_trace')
    return dict(schema_version=1, corpus_version='s1-original-joined-ground-N2-development-v1',
        game_build=13725832, baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e', simulator_version=413,
        evidence_class='bounded original-body continuation under supplied world/platform services',
        information_mode='offline validation oracle; native default RNG and supplied process state; no fair input admission',
        objective='Continuous N2 installer/pump/arrival and route/membership/RNG ownership projections',
        attempted=1, admitted=int(matched), matched=int(matched), failed=int(not matched), excluded=0,
        status=private['status'], failure=private['failure'], observations=observations,
        platform_final=private['platform_final'], source_lf_sha256=source_pins,
        stock_script_sha256=scripts, runtime=runtime, executable_sha256=api.EXE_SHA,
        lua_dll_sha256=vm.DLL_SHA, archive_sha256=ARCHIVE_SHA,
        private_receipt_sha256=api.sha(receipt.read_bytes()), instruction_map_sha256=cache.MAP_SHA,
        instruction_admission='reused exact frozen observed cache/Point/Dust DLL map; EXE source owner/windows verified',
        observed_DLL_instruction_points=len(machine.dll_points), original_call_count=len(private['calls']),
        instruction_count=sum(row['instructions'] for row in private['calls']),
        calls=[{k: v for k, v in row.items() if k not in ('trace', 'allocator_calls')} for row in private['calls']],
        lua_allocator_callback_count=sum(len(row['allocator_calls']) for row in private['calls']),
        retained_guest_allocations=len(machine.live), retained_guest_requested_bytes=sum(machine.allocations[p] for p in machine.live),
        verified_original_bodies=list(machine.source.verified.values()),
        supplied_boundaries=private['boundaries'] + [
            'Separate relocated supplied Board/Pawn/definition/pilot fixture; mapped unspecified bytes zero. Full game/Pawn/Board/type bootstrap excluded.',
            'Actual native DIR initializer and source grass-literal string constructor; caller-selected biome, full mission biome selection/tileset loading excluded.',
            'Actual GetPath query and disjoint original vector clone. Supplied by-value installer frame/origin-match flag; actual loaded Move/dispatcher/admission and bMoved mutation excluded.',
            'Native CRT cache/locks/locale/FLS/PTD bodies run under supplied successful single-thread/FLS-present Win32 module/heap/lock/slot services. Retain modules/CS/PTD/FLS ownership; no kernel32 or full CRT startup/shutdown/failure-path claim.',
            'Native constructor supplies fresh PTD seed1; every sample/state recurrence executes original rand. Live-game RNG history and planner access to this oracle state excluded.',
            'Original audio-disabled BSS gate is retained; enabled audio startup/callbacks excluded.',
            'Burst nontrig cells, all120 ordered RNG draws and untouched rows graded; active velocity/trig semantics, padding, later particle evolution and rendering excluded.',
            'All continuation calls execute before actual host GL cleanup. Retained guest graphics handles become unusable; receipt cannot resume guest execution.',
            'One shared guest world and its components are not independent cases or complete legal actions. Enemy/environment/spawn/undo/save/mission continuation excluded.'],
        original_completed_action_transitions=0, full_turn_original_comparisons=0, fair_input_admissions=0,
        held_out_cases=0, search_certificates=0, gate_promotions=0, ledger_promotions=0,
        next_blocker='Genuine loaded Move skill/dispatcher and action admission, then extended route/control cases and enemy/environment/spawn continuity.')
