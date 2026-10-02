"""Selected inline string erasure without heap storage or capacity growth.

Offset and requested removal are actual unsigned caller words. Positive
interior erasure composes the selected forward memmove law with complete joins.
"""
from __future__ import annotations
import copy
from src.observatory import native_movement_memmove_forward_semantics as memmove
from src.observatory import native_movement_effect_record_default_semantics as memory
from src.observatory import native_movement_path_small_clone_semantics as flags
ANALYSIS_KIND = "pe_native_movement_inline_string_erase_semantics"
BASE,U32,ENTRY=0x400000,0xFFFFFFFF,0x8410
REGISTERS,XMM=memory.REGISTERS,memory.XMM
_read,_write,_pages=memory._read,memory._write,memory._pages
BODY_PINS=dict(memmove.BODY_PINS)
BODY_PINS[ENTRY]=(153,"fb7238468a109aeabf0d45ce924e0591ab679bf07e3882f08605a15ae18af0b7")
SOURCE_PINS=dict(memmove.SOURCE_PINS)
class InlineStringEraseError(ValueError):pass
def _require(condition,message):
    if not condition:raise InlineStringEraseError(message)

def _same(a,b):
    if type(a) is not type(b):return False
    if type(a) is dict:
        return {(type(k),k) for k in a}=={(type(k),k) for k in b} and all(_same(a[k],b[k]) for k in a)
    if type(a) in (list,tuple):return len(a)==len(b) and all(_same(x,y) for x,y in zip(a,b))
    return a==b

def _logic(n):
    return (int((n&255).bit_count()%2==0)<<2)|(int(n==0)<<6)|((n>>31)<<7)

def _child_check(child,packet,g,d,s,n):
    keys={'geometry','registers','xmm','pages','events','trace_rvas','flags','flag_mask','df','endpoint','source_snapshot'}
    _require(type(child) is dict and set(child)==keys and all(type(k) is str for k in child),"inline erase memcpy packet keys differ")
    expected_regs=dict(packet['registers'],eax=d,ecx=0,edx=int.from_bytes(_read(packet['pages'],s+4*(n//4-1),4),'little') if n//4 else n,esp=g+4)
    _require(_same(child['geometry'],dict(entry=g,source=s,destination=d,count=n)) and _same(child['registers'],expected_regs) and _same(child['xmm'],packet['xmm']) and _same(child['flags'],0x44) and _same(child['flag_mask'],0x8D5 if n%4 else 0x8C5) and _same(child['df'],0) and _same(child['endpoint'],BASE+0x8476) and _same(child['source_snapshot'],_read(packet['pages'],s,n)),"inline erase memcpy terminal binding differs")
    _require(type(child['pages']) is dict and set(child['pages'])==set(packet['pages']) and all(type(p) is int and type(b) is bytes and len(b)==4096 for p,b in child['pages'].items()) and type(child['events']) is list and type(child['trace_rvas']) is list and all(type(t) is str and len(t)==10 and t[:2]=='0x' and all(ch in '0123456789abcdef' for ch in t[2:]) for t in child['trace_rvas']),"inline erase memcpy state schema differs")
    mutable={p:bytearray(b) for p,b in packet['pages'].items()}
    for event in child['events']:
        _require(type(event) is dict and set(event)=={'access','address','width','value'} and all(type(k) is str for k in event) and type(event['access']) is str and event['access'] in ('read','write') and type(event['address']) is int and type(event['width']) is int and event['width'] in (1,4) and type(event['value']) is int and 0<=event['value']<1<<(8*event['width']) and 0<=event['address'] and event['address']+event['width']<=2**32,"inline erase memcpy access schema differs")
        at,width,value=event['address'],event['width'],event['value']
        if event['access']=='read':_require(int.from_bytes(_read(mutable,at,width),'little')==value,"inline erase memcpy actual read differs")
        else:
            _require(g-8<=at and at+width<=g or d<=at and at+width<=d+n,"inline erase memcpy write escapes selected buffers")
            _write(mutable,at,value.to_bytes(width,'little'))
    _require(_same(child['pages'],_pages(mutable)) and _read(mutable,d,n)==_read(packet['pages'],s,n),"inline erase memcpy pages or copied bytes differ")
    # Complete selected scalar accesses are bound; reviewed instruction labels remain trusted.
    expected=[]
    def e(a,p,w,v):expected.append(dict(access=a,address=p,width=w,value=v))
    e('write',g-4,4,packet['registers']['edi']);e('write',g-8,4,packet['registers']['esi'])
    for at in (g+8,g+12,g+4):e('read',at,4,int.from_bytes(_read(packet['pages'],at,4),'little'))
    for i in range(n//4):
        v=int.from_bytes(_read(packet['pages'],s+4*i,4),'little');e('read',s+4*i,4,v);e('write',d+4*i,4,v)
    for i in range(n%4):
        a=s+4*(n//4)+i;v=int.from_bytes(_read(packet['pages'],a,1),'little');e('read',a,1,v);e('write',d+4*(n//4)+i,1,v)
    for at,v in ((g+4,d),(g-8,packet['registers']['esi']),(g-4,packet['registers']['edi']),(g,BASE+0x8476)):e('read',at,4,v)
    _require(_same(child['events'],expected),"inline erase memcpy complete accesses differ")

def _validate(pages,registers,xmm,return_address,entry_flags):
    _require(type(pages) is dict and bool(pages) and all(type(p) is int and 0<=p<=0xFFFFF000 and p%4096==0 and type(b) is bytes and len(b)==4096 for p,b in pages.items()),"inline erase immutable pages differ")
    _require(type(registers) is dict and set(registers)==set(REGISTERS) and all(type(k) is str and type(v) is int and 0<=v<=U32 for k,v in registers.items()),"inline erase GPR schema differs")
    _require(type(xmm) is dict and set(xmm)==set(XMM) and all(type(k) is str and type(v) is int and 0<=v<2**128 for k,v in xmm.items()),"inline erase XMM schema differs")
    _require(type(return_address) is int and 0<return_address<=U32 and type(entry_flags) is int and 0<=entry_flags<=U32 and entry_flags&~0xAD7==0 and entry_flags&2==2,"inline erase return or ordinary flags differ")
    g,h=registers['esp'],registers['ecx']
    _require(40<=g and g+12<=U32 and 0<h and h+24<=U32,"inline erase frame or object wraps")
    _read(pages,g-40,52);_read(pages,h,24)
    ret,off,requested=(int.from_bytes(_read(pages,g+i,4),'little') for i in (0,4,8))
    length=int.from_bytes(_read(pages,h+16,4),'little')
    _require(ret==return_address and length<=15 and off<=length and int.from_bytes(_read(pages,h+20,4),'little')==15,"inline erase caller size capacity or offset differs")
    spans=((g-40,g+12),(h,h+24))
    _require(g+12<=h or h+24<=g-40,"inline erase stack and object overlap")
    _require(not ({0x408000,0x76E000}&set(pages)),"inline erase data overlaps selected code pages")
    _require(all(not lo<=return_address<hi for lo,hi in spans) and not 0x408410<=return_address<0x4084A9 and not 0x76E580<=return_address<0x76EAF4,"inline erase return overlaps selected spans")
    return g,h,length,off,requested,min(requested,length-off)

def apply(*,pages,registers,xmm,return_address,entry_flags):
    try:return _apply(pages,registers,xmm,return_address,entry_flags)
    except InlineStringEraseError:raise
    except Exception as exc:raise InlineStringEraseError(str(exc)) from exc

def _apply(pages,registers,xmm,return_address,entry_flags):
    g,h,length,off,requested,removed=_validate(pages,registers,xmm,return_address,entry_flags)
    mutable={p:bytearray(b) for p,b in pages.items()};events=[];states=[];trace=[];child=None
    regs=dict(registers)
    def pc(*offsets):trace.extend(f'0x{ENTRY+t:08x}' for t in offsets)
    def r(at,width=4):
        v=int.from_bytes(_read(mutable,at,width),'little');events.append(dict(access='read',address=at,width=width,value=v));return v
    def w(at,v,width=4):
        _write(mutable,at,v.to_bytes(width,'little'));events.append(dict(access='write',address=at,width=width,value=v))
    w(g-4,registers['ebp']);w(g-8,registers['esi']);r(g+4);w(g-12,registers['edi']);r(h+16);r(g+8)
    regs.update(ebp=g-4,esi=h,edi=length,ecx=off,edx=requested,eax=length-off,esp=g-12)
    pc(0,1,3,4,6,9,10,13,15,17,20,22,24,26)
    available=length-off
    if available<=requested:
        pc(28,31,35,51,53,54,55,59,60)
        w(h+16,off);r(h+20);r(g-12);r(g-8);w(h+off,0,1);r(g-4);r(g)
        final_flags,mask=0x85,0x8D5
        regs.update(eax=h,edi=registers['edi'],esi=registers['esi'],ebp=registers['ebp'],esp=g+12)
    elif requested==0:
        pc(63,65,135,136,138,139,140)
        r(g-12);r(g-8);r(g-4);r(g)
        final_flags,mask=0x44,0x8C5
        regs.update(eax=h,edi=registers['edi'],esi=registers['esi'],ebp=registers['ebp'],esp=g+12)
    else:
        pc(63,65,67,71,77,79,81,82,85,87,89,91,92,95,96,97)
        r(h+20);w(g-16,registers['ebx'])
        newlength=length-requested;count=newlength-off;d=h+off;s=d+requested
        for at,v in ((g-20,count),(g-24,s),(g-28,d),(g-32,BASE+0x8476)):w(at,v)
        regs.update(ebx=d,edi=newlength,eax=s,esp=g-32)
        state=dict(registers=dict(regs),xmm=dict(xmm),pages=_pages(mutable),events=copy.deepcopy(events),flags=flags._sub_flags(newlength,off),flag_mask=0x8D5,df=0,endpoint=BASE+0x36E580)
        states.append(dict(state,phase='entry'))
        packet=dict(pages=_pages(mutable),registers=dict(regs),xmm=dict(xmm),return_address=BASE+0x8476,entry_flags=(entry_flags&~0x8D5)|state['flags']|2)
        child=memmove.apply(**packet);_child_check(child,packet,g-32,d,s,count)
        _require(len(child['trace_rvas'])==24+6*(count//4)+6*(count%4)+2*int(count%4!=0),"inline erase child trace length differs")
        prefix=copy.deepcopy(events);events.extend(copy.deepcopy(child['events']));trace.extend(child['trace_rvas']);mutable={p:bytearray(b) for p,b in child['pages'].items()};regs=dict(child['registers'])
        states.append(dict(registers=dict(regs),xmm=dict(xmm),pages=_pages(mutable),events=prefix+copy.deepcopy(child['events']),flags=child['flags'],flag_mask=child['flag_mask'],df=0,endpoint=BASE+0x8476,phase='return'))
        pc(102,105,109,112,113,129,131,135,136,138,139,140)
        regs['esp']+=12;r(h+20);w(h+16,newlength);r(g-16);w(h+newlength,0,1)
        for at in (g-12,g-8,g-4,g):r(at)
        regs.update(eax=h,ebx=registers['ebx'],edi=registers['edi'],esi=registers['esi'],ebp=registers['ebp'],esp=g+12)
        final_flags,mask=0x85,0x8D5
    return dict(geometry=dict(entry=g,object=h,old_length=length,offset=off,requested=requested,removed=removed,count=length-off-removed),registers=regs,xmm=dict(xmm),pages=_pages(mutable),events=events,trace_rvas=trace,flags=final_flags,flag_mask=mask,df=0,endpoint=return_address,source_snapshot=_read(pages,h,24),string_bytes=_read(mutable,h,24),memmove_packet=copy.deepcopy(child),boundaries=states)
