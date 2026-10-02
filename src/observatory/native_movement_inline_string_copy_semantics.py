"""Selected disjoint inline-string substring copy with no capacity growth.

The small scalar memcpy child has closed ABI/page/access joins; its reviewed
instruction metadata is trusted. Self-copy, heap strings and growth are open.
"""
from __future__ import annotations
import copy
from src.observatory import native_movement_small_memcpy_semantics as memcpy
from src.observatory import native_movement_effect_record_default_semantics as memory
from src.observatory import native_movement_path_small_clone_semantics as flags

ANALYSIS_KIND = "pe_native_movement_inline_string_copy_semantics"
BASE,U32,ENTRY = 0x400000,0xFFFFFFFF,0x80D0
REGISTERS,XMM = memory.REGISTERS,memory.XMM
_read,_write,_pages = memory._read,memory._write,memory._pages
_sub_flags,_add_flags = flags._sub_flags,flags._add_flags
BODY_PINS = dict(memcpy.BODY_PINS)
BODY_PINS[ENTRY] = (288,"062ae02111f4145fc3b614c93355bc20d6ae59544117d4c8bdcff4d82c488333")
SOURCE_PINS = dict(memcpy.SOURCE_PINS)
PREFIX = (0,1,3,4,7,8,0xA,0xD,0xE,0x11,0x13,0x19,0x1C,0x1E,0x20,0x23,0x25,0x6E,0x71,0x77,0x7A,0xA0,0xA2)
ZERO = (0xA4,0xA8,0xAB,0xBB,0xBD,0xBE,0xBF,0xC0,0xC3,0xC4)
POSITIVE = (0x8E,0x92,0x96,0x9A,0xC7,0xC9,0xCB,0xCD,0xCE,0xD1,0xD2,0xD3)
SUFFIX = (0xD8,0xDB,0xDF,0xE2,0xF3,0xF5,0xF9,0xFA,0xFC,0xFD,0xFE,0xFF)

class InlineStringCopyError(ValueError):
    pass

def _require(condition,message):
    if not condition:raise InlineStringCopyError(message)

def _same(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:
        return {(type(k),k) for k in a}=={(type(k),k) for k in b} and all(_same(a[k],b[k]) for k in a)
    if type(a) in (list,tuple):return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    return a==b

def _logic(n):
    return (int((n&255).bit_count()%2==0)<<2)|(int(n==0)<<6)|((n>>31)<<7)

def _validate(pages,registers,xmm,return_address,entry_flags):
    _require(type(pages) is dict and bool(pages) and all(type(p) is int and 0<=p<=0xFFFFF000 and p%4096==0 and type(b) is bytes and len(b)==4096 for p,b in pages.items()),"inline copy immutable pages differ")
    _require(type(registers) is dict and set(registers)==set(REGISTERS) and all(type(k) is str and type(v) is int and 0<=v<=U32 for k,v in registers.items()),"inline copy GPR schema differs")
    _require(type(xmm) is dict and set(xmm)==set(XMM) and all(type(k) is str and type(v) is int and 0<=v<2**128 for k,v in xmm.items()),"inline copy XMM schema differs")
    _require(type(return_address) is int and 0<return_address<=U32 and type(entry_flags) is int and 0<=entry_flags<=U32 and entry_flags&~0xAD7==0 and entry_flags&2==2,"inline copy return or ordinary flags differ")
    g,d=registers['esp'],registers['ecx']
    _require(40<=g and g+16<=U32 and 0<d and d+24<=U32,"inline copy frame or object wraps")
    _read(pages,g-40,56)
    ret,s,off,requested=(int.from_bytes(_read(pages,g+i,4),'little') for i in (0,4,8,12))
    _require(ret==return_address and 0<s and s+24<=U32,"inline copy caller words differ")
    source_size=int.from_bytes(_read(pages,s+16,4),'little')
    destination_size=int.from_bytes(_read(pages,d+16,4),'little')
    _require(source_size<=15 and destination_size<=15 and off<=source_size and int.from_bytes(_read(pages,s+20,4),'little')==15 and int.from_bytes(_read(pages,d+20,4),'little')==15,"inline copy size capacity or offset differs")
    spans=((g-40,g+16),(s,s+24),(d,d+24))
    for i,(lo,hi) in enumerate(spans):
        _read(pages,lo,hi-lo)
        _require(all(hi<=a or z<=lo for a,z in spans[i+1:]),"inline copy selected spans overlap")
    _require(not ({BASE+0x8000,BASE+0x370000}&set(pages)),"inline copy data pages overlap selected code")
    _require(all(not lo<=return_address<hi for lo,hi in spans) and not BASE+ENTRY<=return_address<BASE+ENTRY+288 and not BASE+0x3703E0<=return_address<BASE+0x370954,"inline copy return overlaps selected data or code")
    return g,d,s,source_size,off,requested,min(requested,source_size-off)

def _child_check(child,packet,g,d,s,n):
    keys={'geometry','registers','xmm','pages','events','trace_rvas','flags','flag_mask','df','endpoint','source_snapshot'}
    _require(type(child) is dict and set(child)==keys and all(type(k) is str for k in child),"inline copy memcpy packet keys differ")
    expected_regs=dict(packet['registers'],eax=d,ecx=0,edx=int.from_bytes(_read(packet['pages'],s+4*(n//4-1),4),'little') if n//4 else n,esp=g+4)
    _require(_same(child['geometry'],dict(entry=g,source=s,destination=d,count=n)) and _same(child['registers'],expected_regs) and _same(child['xmm'],packet['xmm']) and _same(child['flags'],0x44) and _same(child['flag_mask'],0x8D5 if n%4 else 0x8C5) and _same(child['df'],0) and _same(child['endpoint'],BASE+0x81A8) and _same(child['source_snapshot'],_read(packet['pages'],s,n)),"inline copy memcpy terminal binding differs")
    _require(type(child['pages']) is dict and set(child['pages'])==set(packet['pages']) and all(type(p) is int and type(b) is bytes and len(b)==4096 for p,b in child['pages'].items()) and type(child['events']) is list and type(child['trace_rvas']) is list and all(type(t) is str and len(t)==10 and t[:2]=='0x' and all(ch in '0123456789abcdef' for ch in t[2:]) for t in child['trace_rvas']),"inline copy memcpy state schema differs")
    mutable={p:bytearray(b) for p,b in packet['pages'].items()}
    for event in child['events']:
        _require(type(event) is dict and set(event)=={'access','address','width','value'} and all(type(k) is str for k in event) and type(event['access']) is str and event['access'] in ('read','write') and type(event['address']) is int and type(event['width']) is int and event['width'] in (1,4) and type(event['value']) is int and 0<=event['value']<1<<(8*event['width']) and 0<=event['address'] and event['address']+event['width']<=2**32,"inline copy memcpy access schema differs")
        at,width,value=event['address'],event['width'],event['value']
        if event['access']=='read':_require(int.from_bytes(_read(mutable,at,width),'little')==value,"inline copy memcpy actual read differs")
        else:
            _require(g-8<=at and at+width<=g or d<=at and at+width<=d+n,"inline copy memcpy write escapes selected buffers")
            _write(mutable,at,value.to_bytes(width,'little'))
    _require(_same(child['pages'],_pages(mutable)) and _read(mutable,d,n)==_read(packet['pages'],s,n),"inline copy memcpy pages or copied bytes differ")
    # Complete selected scalar accesses are bound; reviewed instruction labels remain trusted.
    expected=[]
    def e(a,p,w,v):expected.append(dict(access=a,address=p,width=w,value=v))
    e('write',g-4,4,packet['registers']['edi']);e('write',g-8,4,packet['registers']['esi'])
    for at in (g+8,g+12,g+4):e('read',at,4,int.from_bytes(_read(packet['pages'],at,4),'little'))
    for i in range(n//4):
        v=int.from_bytes(_read(packet['pages'],s+4*i,4),'little');e('read',s+4*i,4,v);e('write',d+4*i,4,v)
    for i in range(n%4):
        a=s+4*(n//4)+i;v=int.from_bytes(_read(packet['pages'],a,1),'little');e('read',a,1,v);e('write',d+4*(n//4)+i,1,v)
    for at,v in ((g+4,d),(g-8,packet['registers']['esi']),(g-4,packet['registers']['edi']),(g,BASE+0x81A8)):e('read',at,4,v)
    _require(_same(child['events'],expected),"inline copy memcpy complete accesses differ")

def apply(*,pages,registers,xmm,return_address,entry_flags):
    try:return _apply(pages,registers,xmm,return_address,entry_flags)
    except InlineStringCopyError:raise
    except Exception as exc:raise InlineStringCopyError(str(exc)) from exc

def _apply(pages,registers,xmm,return_address,entry_flags):
    g,d,s,source_size,off,requested,n=_validate(pages,registers,xmm,return_address,entry_flags)
    mutable={p:bytearray(b) for p,b in pages.items()};regs=dict(registers);events=[];states=[];child=None
    trace=[f'0x{ENTRY+t:08x}' for t in PREFIX]
    def r(at,width=4):
        v=int.from_bytes(_read(mutable,at,width),'little');events.append(dict(access='read',address=at,width=width,value=v));return v
    def w(at,v,width=4):
        _write(mutable,at,v.to_bytes(width,'little'));events.append(dict(access='write',address=at,width=width,value=v))
    for at,v in ((g-4,registers['ebp']),(g-8,registers['ebx'])):w(at,v)
    r(g+4);w(g-12,registers['esi']);r(g+8);w(g-16,registers['edi']);r(s+16);r(g+12);r(d+20)
    regs.update(ebp=g-4,ebx=s,esi=d,edi=n,ecx=off,esp=g-16,eax=source_size-off)
    if n:
        trace.extend(f'0x{ENTRY+t:08x}' for t in POSITIVE)
        r(s+20);r(d+20)
        for at,v in ((g-20,n),(g-24,s+off),(g-28,d),(g-32,BASE+0x81A8)):w(at,v)
        regs.update(eax=s+off,edx=d,esp=g-32)
        state=dict(registers=dict(regs),xmm=dict(xmm),pages=_pages(mutable),events=copy.deepcopy(events),flags=_logic(n),flag_mask=0x8C5,df=0,endpoint=BASE+0x3703E0)
        states.append(dict(state,phase='entry'))
        packet=dict(pages=_pages(mutable),registers=dict(regs),xmm=dict(xmm),return_address=BASE+0x81A8,entry_flags=(entry_flags&~0x8D5)|_logic(n)|2)
        child=memcpy.apply(**packet);_child_check(child,packet,g-32,d,s+off,n)
        prefix=copy.deepcopy(events);events.extend(copy.deepcopy(child['events']));trace.extend(child['trace_rvas'])
        mutable={p:bytearray(b) for p,b in child['pages'].items()};regs=dict(child['registers'])
        states.append(dict(registers=dict(regs),xmm=dict(xmm),pages=_pages(mutable),events=prefix+copy.deepcopy(child['events']),flags=child['flags'],flag_mask=child['flag_mask'],df=0,endpoint=BASE+0x81A8,phase='return'))
        regs['esp']+=12;r(d+20);w(d+16,n);w(d+n,0,1)
        for at in (g-16,g-12,g-8,g-4,g):r(at)
        trace.extend(f'0x{ENTRY+t:08x}' for t in SUFFIX)
    else:
        r(d+20);w(d+16,0);r(g-16);r(g-12);r(g-8);w(d,0,1);r(g-4);r(g)
        trace.extend(f'0x{ENTRY+t:08x}' for t in ZERO)
    final=dict(registers,eax=d,ecx=0 if n else off,edx=regs['edx'],esp=g+16)
    return dict(geometry=dict(entry=g,source_object=s,destination_object=d,source_length=source_size,offset=off,requested=requested,count=n),registers=final,xmm=dict(xmm),pages=_pages(mutable),events=events,trace_rvas=trace,flags=0x85,flag_mask=0x8D5,df=0,endpoint=return_address,source_snapshot=_read(pages,s,24),string_bytes=_read(mutable,d,24),memcpy_packet=copy.deepcopy(child),boundaries=states)
