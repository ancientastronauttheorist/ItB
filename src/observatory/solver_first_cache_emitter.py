"""Joined original Point metadata, texture/cache registration and Dust constructor.

Supplied initialized CRT/TLS and stock-source worlds are bounded offline inputs.
Full process/cache/emitter teardown, normal file loader and movement stay outside.
"""
import json
from pathlib import Path
import struct

from src.observatory import solver_first_path_oracle as api
from src.observatory.solver_first_lua_emitters import EmitterMachine
from src.observatory.solver_first_image_resource import ImageMachine,ASSETS,PINS
from src.observatory.solver_first_gl_texture import TextureContext
BOUNDARY = api.ROOT / 'data/solver_first/s1_cache_emitter_boundary.json'
BOUNDARY_SHA = 'f631ab5bd40e02129559cb81b1a30945c5d8931ca91579d116ea5e0283632d84'
MAP = api.ROOT / 'data/solver_first/s1_cache_emitter_instruction_admission.json'
MAP_SHA = '952c1b3e6ff35f09e93f4dfad82f5b44fadb05a2590dd4eef8dd54d3233e6e38'


def boundary():
    raw = BOUNDARY.read_bytes()
    api.require(api.sha(raw) == BOUNDARY_SHA, 'cache-emitter boundary identity differs')
    return json.loads(raw)


class CacheEmitterMachine(EmitterMachine):
    execute=ImageMachine.execute
    live_bytes=ImageMachine.live_bytes
    def respond_import(self,at):
        if self.stubs[at]['library'].lower()=='opengl32.dll':
            return ImageMachine.respond_import(self,at)
        return api.Machine.respond_import(self,at)
    def __init__(self,exe,admission):
        super().__init__(exe,admission)
        rva,size,digest=0x1a150,146,'caa5e3f8ebe8cc4f554ed7c63f2e7d528532bdc3d7dd045740fe7355cefff2fa'
        off=self.dll.rva_to_file_offset(rva)
        api.require(api.sha(self.dll_raw[off:off+size])==digest,'userdata allocation source window differs')
        self.allocator_returns=self.allocator_returns|{0x1a188}
        for row in boundary()['original_body_pins']:
            entry=int(row['entry_rva'],16)
            self.source.verify(entry)
            api.require(self.source.verified[entry]['body_sha256']==row['body_sha256'], 'static dependency body differs')
    def memory(self,uc,kind,at,width,value,user):
        if at==0x2c:
            if kind==self.u.UC_MEM_READ and width==4 and uc.reg_read(self.x.UC_X86_REG_EIP)==api.BASE+0x2e8d48:
                return
            self.fail('undeclared TLS-slot access');return
        super().memory(uc,kind,at,width,value,user)
def acquire(executable, admission=None):
    exe=Path(executable);m=CacheEmitterMachine(exe,admission)
    calls=[];observations={};status='failed';failure=None
    def original(entry,args=(),receiver=0,cleanup=0,edx=0):
        begin=len(m.allocator_calls);row=m.execute(entry,list(args),receiver,edx,cleanup)
        row['allocator_calls']=m.allocator_calls[begin:];calls.append(row)
        api.require(row['returned'] and row['stack_ok'] and row['failure'] is None,f"call {entry:#x}: returned={row['returned']}, stack_ok={row['stack_ok']}, failure={row['failure']}")
        return row['eax']
    try:
        tls_rva,tls_size=m.source.image.data_directories[9]
        tls_offset=m.source.image.rva_to_file_offset(tls_rva)
        tls_fields=struct.unpack_from('<6I',m.source.data,tls_offset)
        begin,end,index,callbacks,fill,characteristics=tls_fields
        api.require((begin,end,index)==(0x8dc000,0x8dc008,0x8b6e5c),'TLS layout differs')
        template_offset=m.source.image.rva_to_file_offset(begin-api.BASE)
        template=m.source.data[template_offset:template_offset+8]
        api.require(template==struct.pack('<II',0,0x80000000),'TLS initial template differs')
        api.require(m.get(0x893f20)==0x80000000 and m.get(0x8d91ac)==0 and m.get(0x8d8948)==0,
          'original registry seed differs')
        head=original(0x7c600)
        api.require([m.get(head+i*4) for i in range(3)]==[head]*3 and bytes(m.uc.mem_read(head+12,2))==b'\x01\x01','native sentinel differs')
        vector,block=api.BOARD+0x70000,api.BOARD+0x71000
        m.uc.mem_write(block,template);m.put(vector,block);m.put(0x2c,vector)
        # Source-derived completed one-time initialization premise. No type ID
        # or class result is supplied; the actual RTTI insertion assigns them.
        m.put(0x8d91b0,head);m.put(0x8d91b4,0)
        for at in [0x893f20,0x8d91ac,block+4]:m.put(at,0x80000001)
        original(0x1890)
        null_id=m.get(0x8d8dc4);counter_after_null=m.get(0x8d8948)
        original(0x1910)
        point_id=m.get(0x8d8dd4);counter_after_point=m.get(0x8d8948)
        original(0x1910)
        api.require(m.get(0x8d8dd4)==point_id and m.get(0x8d8948)==counter_after_point,'type ID is not stable')
        api.require(null_id!=point_id and counter_after_null==1 and counter_after_point==2 and m.get(0x8d91b4)==2,
          'isolated native registry insertion projection differs')
        observations=dict(tls_directory_rva=tls_rva,tls_fields=list(tls_fields),template_sha256=api.sha(template),
          completed_guard_epoch=0x80000001,null_type_id=null_id,point_type_id=point_id,type_counter=counter_after_point,
          registry_size=m.get(0x8d91b4),registry_head=head,
          tls_reads=sum(x['trace'].count([0x2e8d48,6]) for x in calls))
        from src.observatory import solver_first_lua_vm as vm
        def dll(name,args):
            row=m.cdecl(name,args);calls.append(row)
            api.require(row['returned'] and row['cdecl_stack_ok'] and row['failure'] is None,str(row['failure']))
            return row['eax']
        L=dll('lua_newstate',[vm.ALLOC,vm.UD])
        dll('luaopen_base',[L]);dll('lua_settop',[L,0]);m.put(0x896048,L)
        original(0x2e6900,receiver=L)
        descriptor=api.BOARD+0x72000
        original(0x4f540,[0],descriptor,cleanup=4)
        class_node=m.get(descriptor)
        for entry in [0x52590,0x52670,0x52750]:
            api.require(original(entry,[0,0],descriptor,cleanup=8)==descriptor,'Point builder receiver differs')
        module=api.BOARD+0x73000;m.put(module,L);m.put(module+4,0)
        original(0x2e66c0,[class_node],module,cleanup=4)
        key=api.BOARD+0x74000;m.uc.mem_write(key,b'Point\0')
        dll('lua_getfield',[L,0xffffd8ee,key])
        observations.update(point_global_type=dll('lua_type',[L,0xffffffff]))
        dll('lua_settop',[L,0])
        # Independently declared integer pair through the actual Point class.
        m.uc.mem_write(key,b'return Point(2147483647,2147483647)\0')
        length=len(b'return Point(2147483647,2147483647)')
        chunk=key+0x1000;m.uc.mem_write(chunk,b'Point control\0')
        api.require(dll('luaL_loadbuffer',[L,key,length,chunk])==0,'Point control compile failed')
        api.require(dll('lua_pcall',[L,0,1,0])==0,'Point control construction failed')
        observations.update(point_result_type=dll('lua_type',[L,0xffffffff]),lua_state=L)
        out=api.BOARD+0x75000
        conversion=original(0x54690,[L,m.get(0x8d86fd)&0xff,0xffffffff],out,cleanup=12)
        point=m.get(out)
        values=[m.get(point),m.get(point+4)]
        api.require(conversion<0x80000000 and values==[0x7fffffff,0x7fffffff],'native Point extraction differs')
        observations.update(native_point_pointer=point,native_point_values=values,conversion_status=conversion)
        dll('lua_settop',[L,0])
        packet=boundary()
        for window in packet['original_windows']:
            rva,size=int(window['start_rva'],16),window['size']
            off=m.source.image.rva_to_file_offset(rva)
            api.require(m.source.image.rva_to_file_offset(rva+size-1)==off+size-1,'source data/code window extent differs')
            api.require(api.sha(m.source.data[off:off+size])==window['sha256'],'source data/code window identity differs')
        m.uc.mem_write(key,b'INT_MAX\0')
        dll('lua_pushinteger',[L,0x7fffffff]);dll('lua_setfield',[L,0xffffd8ee,key])
        slices=packet['exact_stock_slices']
        for filename in ['Location_empty','RetrievedThings','GetImageLoc']:
            row=next(x for x in slices if x['id']==filename)
            source=(exe.parent/row['game_relative_path']).read_bytes()
            raw=source[row['start_offset']:row['end_offset_exclusive']]
            api.require(len(raw)==row['size'] and api.sha(raw)==row['sha256'],'exact metadata slice differs')
            m.uc.mem_write(key,raw);m.uc.mem_write(chunk,filename.encode()+b'\0')
            api.require(dll('luaL_loadbuffer',[L,key,len(raw),chunk])==0,'metadata slice compile failed')
            api.require(dll('lua_pcall',[L,0,0,0])==0,'metadata slice execution failed')
        metadata=[]
        for name in ['combat/tiles_grass/dust.png','nullResource.png']:
            raw=name.encode();ptr=original(0x3574db,[len(raw)+1]);m.uc.mem_write(ptr,raw+b'\0')
            name_words=[ptr,0,0,0,len(raw),len(raw)]
            m.put(out,0xdeadbeef);m.put(out+4,0xdeadbeef)
            api.require(original(0x4d7d0,[out]+name_words,cleanup=28)==out,'metadata output receiver differs')
            values=[m.get(out),m.get(out+4)]
            api.require(values==[0x7fffffff,0x7fffffff],'native stock missing-key Point differs')
            api.require(dll('lua_gettop',[L])==0,'metadata wrapper changed Lua stack')
            m.uc.mem_write(key,b'RetrievedThings\0');dll('lua_getfield',[L,0xffffd8ee,key])
            m.uc.mem_write(key,raw+b'\0');dll('lua_getfield',[L,0xffffffff,key])
            api.require(dll('lua_type',[L,0xffffffff])==1 and dll('lua_toboolean',[L,0xffffffff])==1,'stock getter retrieval marker missing')
            dll('lua_settop',[L,0])
            metadata.append(dict(image=name,native_words=values,retrieved=True))
        observations['stock_GetImageLoc_empty_Location']=metadata
        from src.observatory.resource_archive import scan_resource_archive
        from src.observatory.solver_first_image_resource import ARCHIVE_SHA
        archive_path=exe.parent/'resources/resource.dat'
        archive=scan_resource_archive(archive_path)
        api.require(archive['sha256']==ARCHIVE_SHA and archive['entry_count']==2854,'resource archive differs')
        records={row['path']:row for row in archive['records']}
        context=TextureContext();m.context=context
        try:
            original(0xc8d80,[0,0,0,0],cleanup=16)
            resources=[]
            for asset in ASSETS:
                record=records[asset['path']]
                with archive_path.open('rb') as handle:
                    handle.seek(record['payload_offset']);encoded=handle.read(record['payload_size'])
                api.require(api.sha(encoded)==asset['encoded_sha256'],'asset input differs')
                dctx,data,w,h,n,bitmap=api.BOARD+0x1000,api.BOARD+0x10000,api.BOARD+0x2000,api.BOARD+0x2004,api.BOARD+0x2008,api.BOARD+0x3000
                m.uc.mem_write(dctx,b'\0'*0x100);m.uc.mem_write(data,encoded)
                for off,value in [(0x10,0),(0x20,0),(0xa8,data),(0xac,data+len(encoded)),(0xb0,data)]:m.put(dctx+off,value)
                for ptr in [w,h,n]:m.put(ptr,0xdeadbeef)
                pixels=original(0x3f330,[h,n,4],dctx,edx=w)
                width,height=m.get(w),m.get(h)
                api.require((width,height,m.get(n))==(asset['width'],asset['height'],asset['components']),'decode projection differs')
                rgba=m.live_bytes(pixels,width*height*4);api.require(api.sha(rgba)==asset['rgba_sha256'],'pixels differ')
                m.uc.mem_write(bitmap,b'\0'*16)
                original(0x99ea0,[pixels,width,height],bitmap,cleanup=12);m.put(0x894b54,0xde1)
                texture=original(0x9a2c0,receiver=bitmap)
                api.require(context.readback(texture,width,height)==rgba,'GPU storage differs')
                name=asset['path'].encode();ptr=original(0x3574db,[len(name)+1]);m.uc.mem_write(ptr,name+b'\0')
                original(0xc0d60,[texture,width,height,ptr,0,0,0,len(name),len(name)],cleanup=36)
                lookup=asset['path'][4:].encode();ptr=original(0x3574db,[len(lookup)+1]);m.uc.mem_write(ptr,lookup+b'\0')
                wrapper=original(0xbe8f0,[ptr,0,0,0,len(lookup),len(lookup)],0x8d5660,cleanup=24)
                resource=m.get(wrapper);words=[m.get(resource+i*4) for i in range(8)]
                flag=bytes(m.uc.mem_read(resource+12,1))[0]
                api.require(words[:3]==[texture,width,height] and flag==0 and words[4:]==[0,0,0x3f800000,0x3f800000],'native cache resource differs')
                metadata=[m.get(wrapper+12),m.get(wrapper+16)]
                api.require(metadata==[0x7fffffff,0x7fffffff],'native cache metadata differs')
                resources.append(dict(asset=asset,archive_record=record,texture=texture,wrapper=wrapper,resource=resource,raw_words=words,flag_byte=flag,metadata=metadata,rgba_sha256=api.sha(rgba)))
                original(0x9a1b0,receiver=bitmap);original(0x36fb17,[pixels])
            observations['native_registered_resources']=resources
            from src.observatory.solver_first_lua_emitters import SOURCES,SLICES
            for name,source,begin,end,digest in SLICES:
                full=(exe.parent/source).read_bytes();api.require(api.sha(full)==SOURCES[source],'emitter source differs')
                raw=full[begin:end];api.require(api.sha(raw)==digest,'emitter slice differs')
                m.uc.mem_write(key,raw);m.uc.mem_write(chunk,name.encode()+b'\0')
                if name=='CreateClass':
                    for layer,value in [('LAYER_FRONT',1),('LAYER_BACK',2)]:
                        m.uc.mem_write(chunk,layer.encode()+b'\0');dll('lua_pushinteger',[L,value]);dll('lua_setfield',[L,0xffffd8ee,chunk])
                    m.uc.mem_write(chunk,name.encode()+b'\0')
                api.require(dll('luaL_loadbuffer',[L,key,len(raw),chunk])==0,'emitter slice compile failed')
                api.require(dll('lua_pcall',[L,0,0,0])==0,'emitter slice execution failed')
            name=b'Emitter_Dust';words=list(struct.unpack('<4I',(name+b'\0').ljust(16,b'\0')))+[len(name),15]
            emitter=api.BOARD+0x90000
            api.require(original(0xbb910,words,emitter,cleanup=24)==emitter,'native emitter receiver differs')
            constructor_trace=calls[-1]['trace']
            api.require([0xbc1f6,5] in constructor_trace and
                not any(len(row)==2 and row[0] in (0xbc200,0xbc32e,0xbc33c) for row in constructor_trace),
                'native Dust did not take its single-image branch')
            integer_fields={0x30:0,0x34:0,0x38:0,0x6c:1,0x70:20,0x7c:1,0x80:32,0x84:15}
            byte_fields={0xc:0,0x88:0,0x89:1}
            float_fields={0x10:0,0x18:0.4,0x1c:0.75,0x20:0,0x24:10,0x28:12,
                0x2c:12,0x50:270,0x54:25,0x5c:0.25,0x74:0,0x8c:-1}
            for offset,value in integer_fields.items():
                api.require(m.get(emitter+offset)==value,'native Dust integer field differs')
            for offset,value in byte_fields.items():
                api.require(bytes(m.uc.mem_read(emitter+offset,1))[0]==value,'native Dust byte field differs')
            for offset,value in float_fields.items():
                api.require(bytes(m.uc.mem_read(emitter+offset,4))==struct.pack('<f',value),'native Dust float field differs')
            begin,end,capacity=[m.get(emitter+offset) for offset in (0,4,8)]
            api.require(end-begin==32*44 and capacity==end and m.allocations.get(begin)==1408,
                'native Dust particle vector extent differs')
            particle_bytes=m.live_bytes(begin,end-begin)
            for i in range(32):
                for offset in (0,4,8,12,16,20,24,32,36,40):
                    api.require(m.get(begin+i*44+offset)==0,'native particle default DWORD differs')
                api.require(particle_bytes[i*44+28]==0,'native particle default flag differs')
            draw=m.get(emitter+0x3c)
            api.require(m.get(draw+0xc)==resources[0]['resource'],'native Dust draw resource differs')
            api.require([m.get(draw+offset) for offset in (0x28,0x30,0x34)]==[6,4,2],'native CPU geometry layout differs')
            vertices=[(0,0,0,0),(15,0,1,0),(15,13,1,1),(0,0,0,0),(15,13,1,1),(0,13,0,1)]
            vertex_bytes=m.live_bytes(m.get(draw+0x2c),6*4*4)
            api.require(vertex_bytes==b''.join(struct.pack('<4f',*row) for row in vertices),'native Dust CPU vertices differ')
            for offset in (0x14,0x18,0x1c,0x20):
                api.require(bytes(m.uc.mem_read(draw+offset,4))==struct.pack('<f',1),'native draw color differs')
            for offset,value in {8:1,0x10:0,0x11:0,0x24:0}.items():
                api.require(bytes(m.uc.mem_read(draw+offset,1))[0]==value,'native draw flag differs')
            final_stack=dll('lua_gettop',[L])
            api.require(final_stack==0,'native emitter changed Lua stack')
            observations['native_Dust_constructor']=dict(receiver=emitter,lua_stack=final_stack,
                integer_fields={hex(k):v for k,v in integer_fields.items()},byte_fields={hex(k):v for k,v in byte_fields.items()},
                float32_fields={hex(k):struct.unpack('<I',struct.pack('<f',v))[0] for k,v in float_fields.items()},
                particle_count=32,particle_stride=44,particle_storage=begin,particle_storage_sha256=api.sha(particle_bytes),
                initialized_particle_cells_per_row=11,particle_padding_offsets_ungraded=[29,30,31],
                particle_evolution_ungraded=True,draw_record=draw,draw_resource=m.get(draw+0xc),
                vertices=vertices,vertex_storage_sha256=api.sha(vertex_bytes))
            status='complete_native_resource_cache_metadata_and_Dust_constructor'
        except Exception as exc:
            failure=str(exc)
            status='failed'
        finally:
            try:
                context.close()
            except Exception as exc:
                failure=(failure+'; ' if failure else '')+'host cleanup: '+str(exc)
                status='failed'
            observations['host_context_identity']=context.identity
            observations['host_context_cleanup']=context.cleanup
    except Exception as exc:
        failure=str(exc)
        status='failed'
    r=dict(status=status,failure=failure,calls=calls,observations=observations,
      verified_source_bodies=list(m.source.verified.values()),remaining_allocations=len(m.live),
      allocations=m.allocations,live_allocations=sorted(m.live),dll_instructions=m.dll_points,
      boundaries=['Exact native sentinel constructor plus supplied completed CRT guard/TLS epoch after one initialization; no CRT startup or locks executed.',
        'Actual null_type and Point RTTI insertion/static assignments in a fresh two-type universe; IDs are outputs, not supplied constants or original full-game ID ordering.',
        'Registry/Lua/process allocations retained; Process/Lua/cache/emitter allocations retained; no guest ownership closure or completed gameplay claim. Native Point/stock metadata, real texture/cache registration and Dust constructor are attempted; full startup/file loader/biome/action settlement excluded. Host graphics cleanup is separate.'])
    return r,m


def run(executable, private_dir, *, exploratory=False):
    from src.observatory.solver_first_image_resource import ARCHIVE_SHA
    from src.observatory import solver_first_lua_vm as vm
    executable,private_dir=Path(executable),Path(private_dir)
    api.require(not private_dir.exists(),'private output directory is create-only')
    private_dir.mkdir(parents=True)
    paths=['src/observatory/solver_first_cache_emitter.py','scripts/solver_first_cache_emitter.py',
        'src/observatory/solver_first_lua_emitters.py','src/observatory/solver_first_lua_vm.py',
        'src/observatory/solver_first_image_resource.py','src/observatory/solver_first_gl_texture.py',
        'src/observatory/solver_first_path_oracle.py','src/observatory/pe_anchor_map.py',
        'src/observatory/resource_archive.py','data/solver_first/s1_cache_emitter_boundary.json']
    source_pins={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths}
    runtime=api.runtime_identity()
    source_rows=boundary()['game_sources']
    from src.observatory.solver_first_lua_emitters import SOURCES
    script_pins={p:row['sha256'] for p,row in source_rows.items()}|SOURCES
    api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'installed stock scripts differ')
    map_raw=None if exploratory else MAP.read_bytes()
    api.require(exploratory or api.sha(map_raw)==MAP_SHA,'instruction admission map differs')
    private,machine=acquire(executable,None if exploratory else json.loads(map_raw)['instructions'])
    receipt=private_dir/'joined_world.json'
    with receipt.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(private,handle,indent=2,sort_keys=True,allow_nan=False);handle.write('\n')
    instruction_map=dict(schema_version=1,dll_sha256=vm.DLL_SHA,instructions=machine.dll_points,
        information_mode='Observed joined Point/cache/Dust source-world paths only; not a function atlas or general Lua proof.')
    if exploratory:
        with (private_dir/'instruction_map.json').open('x',encoding='utf-8',newline='\n') as handle:
            json.dump(instruction_map,handle,indent=2,sort_keys=True,allow_nan=False);handle.write('\n')
    else:
        api.require(MAP.read_bytes()==map_raw,'instruction admission map changed')
    api.require(source_pins=={p:api.sha((api.ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in paths},'tool sources changed')
    api.require(runtime==api.runtime_identity(),'runtime changed')
    api.require(api.sha(executable.read_bytes())==api.EXE_SHA and
        api.sha((executable.parent/'lua5.1.dll').read_bytes())==vm.DLL_SHA and
        api.sha((executable.parent/'resources/resource.dat').read_bytes())==ARCHIVE_SHA,'original inputs changed')
    api.require(all(api.sha((executable.parent/p).read_bytes())==h for p,h in script_pins.items()),'installed stock scripts changed')
    matched=private['status']=='complete_native_resource_cache_metadata_and_Dust_constructor' and private['failure'] is None
    return dict(schema_version=1,corpus_version='s1-original-cache-Point-Dust-development-v1',game_build=13725832,
        baseline_solver_commit='84c186ae440163056c5c39b9aea9c20e6f49983e',simulator_version=413,
        information_mode='Supplied offline initialized registry/TLS and exact empty-Location stock-source world; no fair input admission.',
        objective='Join genuine Point metadata, original resource/cache ownership flow and graded single-image Dust construction.',
        attempted=1,admitted=int(matched),matched=int(matched),failed=int(not matched),excluded=0,
        graded_components=dict(stock_missing_image_queries=2,resource_cache_assets=2,Dust_constructors=1),
        status=private['status'],failure=private['failure'],observations=private['observations'],
        source_lf_sha256=source_pins,stock_script_sha256=script_pins,runtime=runtime,
        executable_sha256=api.EXE_SHA,lua_dll_sha256=vm.DLL_SHA,archive_sha256=ARCHIVE_SHA,
        private_receipt_sha256=api.sha(receipt.read_bytes()),instruction_admission='exploratory' if exploratory else 'frozen observed map',
        instruction_map_sha256=api.sha((private_dir/'instruction_map.json').read_bytes()) if exploratory else MAP_SHA,
        original_call_count=len(private['calls']),instruction_count=sum(c['instructions'] for c in private['calls']),
        calls=[{k:v for k,v in row.items() if k not in ('trace','allocator_calls')} for row in private['calls']],
        lua_allocator_callback_count=sum(len(row['allocator_calls']) for row in private['calls']),
        retained_guest_allocations=len(machine.live),retained_guest_requested_bytes=sum(machine.allocations[p] for p in machine.live),
        verified_original_bodies=list(machine.source.verified.values()),supplied_boundaries=private['boundaries']+[
            'Successful host heap/allocator services, scratch objects and caller strings are supplied. Marker arguments are unused constructor-tag storage.',
            'Constructor-only Point registration excludes other Point methods/properties and full native game namespace/class bootstrap.',
            'Actual Windows x64 OpenGL service supplies original x86 upload imports; no original x86 graphics/SDL/driver startup execution.',
            'Host texture/context teardown completes after all native calls; retained guest handles are not usable afterward. No guest/global/cache/emitter teardown claim.',
            'Dust scalar/vector/default/CPU vertex projections are graded; unwritten/padding bytes, particle evolution, rendering, normal file loading and original biome/action settlement remain excluded.'],
        original_completed_action_transitions=0,full_turn_original_comparisons=0,fair_input_admissions=0,
        held_out_cases=0,search_certificates=0,gate_promotions=0,ledger_promotions=0,
        next_blocker='Original biome selection and loaded Move/dispatch context, then joined Ground N2 callbacks/arrival/settlement before original enemy/environment/spawn continuation.')
