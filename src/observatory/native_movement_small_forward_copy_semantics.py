"""Selected forward copies of zero through 31 bytes, including leftward overlap at the selected CRT entry.

The actual count and pointers come from cdecl caller words. No imported
response or native delegation is needed on this bounded scalar branch.
"""
from __future__ import annotations
from src.observatory import native_movement_effect_record_default_semantics as memory
from src.observatory import native_movement_path_small_clone_semantics as flags

ANALYSIS_KIND = "pe_native_movement_small_forward_copy_semantics"
SOURCE_PINS = {
    "program_facts": (
        "pe_ghidra_program_facts",
        "631968cedac0e8ca8e2521a540fbedd23f2c0c267ef2b3e86a931fdda484a803",
    ),
}
BASE, U32, ENTRY = 0x400000, 0xFFFFFFFF, 0x3703E0
REGISTERS, XMM = memory.REGISTERS, memory.XMM
BODY_PINS = {ENTRY: (1330, "027f9747b24b79e7aa5a3511ddfd2890a8d50a72072ac6c7df83959091aa9ec5")}
_read, _write, _pages = memory._read, memory._write, memory._pages
_sub_flags = flags._sub_flags


class SmallForwardCopyError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise SmallForwardCopyError(message)


def _logic(value):
    value &= U32
    return ((int((value & 255).bit_count() % 2 == 0) << 2)
            | (int(value == 0) << 6) | ((value >> 31) << 7))


def _validate(pages, registers, xmm, return_address, entry_flags):
    _require(type(pages) is dict and bool(pages)
             and all(type(p) is int and 0 <= p <= 0xFFFFF000 and p % 4096 == 0
                     and type(b) is bytes and len(b) == 4096 for p,b in pages.items()),
             "small memcpy immutable pages differ")
    _require(type(registers) is dict and set(registers) == set(REGISTERS)
             and all(type(k) is str and type(v) is int and 0 <= v <= U32
                     for k,v in registers.items()), "small memcpy GPR schema differs")
    _require(type(xmm) is dict and set(xmm) == set(XMM)
             and all(type(k) is str and type(v) is int and 0 <= v < 2**128
                     for k,v in xmm.items()), "small memcpy XMM schema differs")
    _require(type(return_address) is int and 0 < return_address <= U32
             and type(entry_flags) is int and 0 <= entry_flags <= U32
             and entry_flags & ~0xAD7 == 0 and entry_flags & 2 == 2,
             "small memcpy return or ordinary DF clear flags differ")
    g = registers["esp"]
    _require(8 <= g and g + 16 <= U32, "small memcpy frame wraps")
    _read(pages,g-8,24)
    ret,d,o,n = (int.from_bytes(_read(pages,g+i,4),"little") for i in (0,4,8,12))
    _require(ret == return_address and n <= 31, "small memcpy caller words differ")
    spans = [(g-8,g+16)]
    if n:
        _require(0 < d and 0 < o and d+n <= U32 and o+n <= U32,
                 "small memcpy positive extent wraps")
        _require(d <= o or o+n <= d,
                 "small forward copy selects the backward overlapping arm")
        if d+n <= o or o+n <= d:
            spans.extend(((d,d+n),(o,o+n)))
        else:
            spans.append((min(d,o),max(d+n,o+n)))
        _read(pages,d,n);_read(pages,o,n)
    _require(all(hi <= a or z <= lo for i,(lo,hi) in enumerate(spans)
                 for a,z in spans[i+1:]), "small memcpy selected spans overlap")
    # All selected instructions occupy this atlas-backed code page.
    _require(not ({BASE+0x370000} & set(pages)),
             "small memcpy data pages overlap body code")
    _require(all(not lo <= return_address < hi for lo,hi in spans)
             and not BASE+0x3703E0 <= return_address < BASE+0x370954,
             "small memcpy return overlaps selected data or body")
    return g,d,o,n


def apply(*, pages, registers, xmm, return_address, entry_flags):
    try:
        return _apply(pages,registers,xmm,return_address,entry_flags)
    except SmallForwardCopyError:
        raise
    except Exception as exc:
        raise SmallForwardCopyError(str(exc)) from exc


def _apply(pages, registers, xmm, return_address, entry_flags):
    g,d,o,n = _validate(pages,registers,xmm,return_address,entry_flags)
    mutable = {p:bytearray(b) for p,b in pages.items()}
    events,trace = [],[]
    regs = dict(registers)
    source_snapshot = _read(pages,o,n) if n else b""

    def pc(*offsets):
        trace.extend(f"0x{ENTRY+offset:08x}" for offset in offsets)

    def event(access,address,width,value):
        if access == "write":
            _write(mutable,address,value.to_bytes(width,"little"))
        else:
            _require(int.from_bytes(_read(mutable,address,width),"little") == value,
                     "small memcpy actual read differs")
        events.append(dict(access=access,address=address,width=width,value=value))

    def r(address,width=4):
        value = int.from_bytes(_read(mutable,address,width),"little")
        event("read",address,width,value)
        return value

    def w(address,value,width=4):
        event("write",address,width,value)

    w(g-4,registers["edi"]);w(g-8,registers["esi"])
    r(g+8);r(g+12);r(g+4)
    pc(0,1,2,6,0xA,0xE,0x10,0x12,0x14,0x16)
    if d > o:
        pc(0x18,0x1A)
    pc(0x20,0x23,0x4FB,0x4FE)
    q,tail = divmod(n,4)
    regs.update(eax=n,ecx=n,edx=n,esi=o,edi=d,esp=g-8)
    result_flags,mask = _logic(n),0x8C5
    if n:
        pc(0x500,0x502,0x505)
        regs["ecx"] = q
        for i in range(q):
            pc(0x507,0x509,0x50B,0x50E,0x511,0x514)
            value = r(o+4*i)
            w(d+4*i,value)
            regs.update(edx=value,esi=o+4*(i+1),edi=d+4*(i+1),ecx=q-i-1)
        pc(0x516,0x518,0x51B)
        regs["ecx"] = tail
        result_flags = _logic(tail)
        for i in range(tail):
            pc(0x51D,0x51F,0x521,0x522,0x523,0x524)
            value = r(o+4*q+i,1)
            w(d+4*q+i,value,1)
            regs.update(eax=(regs["eax"]&0xFFFFFF00)|value,
                        esi=o+4*q+i+1,edi=d+4*q+i+1,ecx=tail-i-1)
        if tail:
            pc(0x526,0x52D)
            result_flags,mask = _sub_flags(1,1),0x8D5
    pc(0x530,0x534,0x535,0x536)
    r(g+4);r(g-8);r(g-4);r(g)
    regs.update(eax=d,esi=registers["esi"],edi=registers["edi"],esp=g+4)
    _require(len(events) == 9+2*q+2*tail, "small memcpy access count differs")
    return dict(geometry=dict(entry=g,source=o,destination=d,count=n),
                registers=regs,xmm=dict(xmm),pages=_pages(mutable),events=events,
                trace_rvas=trace,flags=result_flags,flag_mask=mask,df=0,
                endpoint=return_address,source_snapshot=source_snapshot)
