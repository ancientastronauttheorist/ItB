"""Exact wrapper and numeric-slot recognizer chain for native Lua ``property``."""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from src.observatory.native_function_accounting import atlas_record_sha256
from src.observatory.native_lua_cclosure_setfield_publications import (
    NativeLuaCClosurePublicationError, _array, _assert_publication_safe,
    _atlas_functions, _canonical_bytes, _canonical_sha256, _decode_range,
    _exact_keys, _hex, _mapping, _rva, _validate_json_tree,
)
from src.observatory.native_lua_cclosure_table_key_provenance import _enhanced_cfg
from src.observatory.native_lua_direct_calls import NativeLuaDirectCallError, _decoder, _load_executable
from src.observatory.native_lua_property_consumer_chain import _with_edi_writes
from src.observatory.native_lua_property_initializer_chain import (
    ANALYSIS_KIND as INITIALIZER_ANALYSIS_KIND,
    STRUCTURE_VERIFICATION_KIND as INITIALIZER_STRUCTURE_VERIFICATION_KIND,
    VERIFICATION_KIND as INITIALIZER_VERIFICATION_KIND,
    NativeLuaPropertyInitializerChainError,
    validate_native_lua_property_initializer_chain,
    validate_native_lua_property_initializer_chain_structure,
)
from src.observatory.pe_anchor_map import PEAnchorError


SCHEMA_VERSION = 1
ANALYSIS_KIND = "pe_native_lua_property_operator_dispatch_chain"
VERIFICATION_KIND = ANALYSIS_KIND + "_verification"
STRUCTURE_VERIFICATION_KIND = ANALYSIS_KIND + "_structure_verification"
_LUA_LIBRARY = "lua5.1.dll"
_WRITABLE = 0x80000000
_EXE_SHA = "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
_INIT_SHA = "b76b3d46d30da4801a3bc4f67be78d3818f847557a0b275f6048120873b44bc4"


class NativeLuaPropertyOperatorDispatchChainError(RuntimeError):
    """Raised when the sealed operator-dispatch chain is stale or malformed."""


_FUNCTIONS = (
    ("operator_wrapper", 0x002EA1A0, 302, "bea28c212b1b1b163611046a80f2c3da4c4886aaa1bea785bde455f7b0e5b9a3", "19cb92f34c9935478df596f4acf5864d08da8d54df33d125e6ee7b9c74dd98dd", 113, 117,
     ((0x002EA1B2,"lua_touserdata"),(0x002EA1C3,"lua_getmetatable"),(0x002EA1D5,"lua_rawgeti"),(0x002EA1DE,"lua_tocfunction"),(0x002EA1F1,"lua_settop"),(0x002EA1FF,"lua_gettop"),(0x002EA20D,"lua_pushvalue"),(0x002EA215,"lua_gettable"),(0x002EA21E,"lua_type"),(0x002EA24F,"lua_gettop"),(0x002EA264,"lua_pushstring"),(0x002EA26B,"lua_error"),(0x002EA27E,"lua_insert"),(0x002EA2AE,"lua_remove"),(0x002EA2BB,"lua_call"))),
    ("numeric_slot_recognizer", 0x002EA3D0, 93, "fb64dfb22aa5813027232506af9b60f97a85e1d5b79b7d63182dc4ce957f02c0", "7b3681a93f0cad3cb8f73d2a25ad7302a2295bf04199591b7d56651efb7af313", 42, 42,
     ((0x002EA3D9,"lua_touserdata"),(0x002EA3EA,"lua_getmetatable"),(0x002EA3FC,"lua_rawgeti"),(0x002EA405,"lua_tocfunction"),(0x002EA418,"lua_settop"))),
)

# Owner/call/hash tuples are a deliberate finite, source-free partition.
_RECOGNIZER_CALLS = (
 (0x00054610,0x0005463C,"bbff3ba3794d7f662b41849d76fbacbf13b2edac240195a765c386244074b26d"),(0x00054690,0x000546BC,"d8314559c8aa47370a7d131fc23342777314199198b075df9598bedc6372255c"),(0x00060CA0,0x00060D00,"69a088cd75254e44a4bc7ae00f2f6f5ec8e3a562ede3b047a239f318a4c7740d"),(0x00067000,0x00067010,"33e845350f965598ee8a1fa45a73fdab735bfa7108cf13060baca820d0ad1daa"),(0x00067080,0x0006708F,"6ca5f3dc14b2fb0f7cebef71f6c17d99c57033e0db6300b0ac3c39ca6f65e282"),(0x000670E0,0x0006710C,"62774e5ed44c4cd6974adeecf91201d223cc7df0923fbfb35d1109923c45ae0f"),(0x00067270,0x00067282,"af686cc3fcc4c24a629066696534de57baa21b251fe020cbe6723a26eb6c6423"),(0x00067380,0x0006738F,"1aa48dc3ee1800c1f5cbf56c8f05551cb26a5ab4d3e4e87df040d34a6666db5e"),(0x00067610,0x00067620,"c402aca55246babd4684817b2bb782c2178b98a98c485ca590e663584917515e"),(0x00067690,0x000676A2,"aabc3b9011cb134fc925c30ec8258d4ff8e23036b43688550417c5a7386919f4"),(0x00067710,0x00067722,"8dc2ab6933c6fc86762a54e9c06577249d05a12f31cd0c65fdf88ff3f790ce6c"),(0x00067A90,0x00067AF8,"c5a08e65cb75c2b6f46dad7016c0146e846ede9f0821502aa01e5da2c0899c5f"),
 (0x000688E0,0x000688F1,"c061ba56e7cc5e33bb08a83c459441fc5604906c49e50d46f319a973382e9593"),(0x00068950,0x00068961,"0bbb80cb2b0625d1c56dd9b65e538120a61eb9d5b7981f8905f3e6c6afc3debd"),(0x000689C0,0x000689D1,"d55c1263f500906094933efc1322fe4f18ae1ec5607b801cd028f7c925553e7e"),(0x00075E90,0x00075EBB,"576947d341d49ed5dfe04fdf19a703758faefd53900d87c0e8a7a5a7787911b5"),(0x0007CBF0,0x0007CC1B,"bc867366a5a5722609a46639f1021fe1001d4a2fd796194bcd0c538431ee1f03"),(0x000A97B0,0x000A97DB,"b9fcefbe94383f4cf5ad6779154ff9f07e5847548225b7f3abf8a4208ccd0401"),(0x000C6FF0,0x000C701B,"6b1250e2026fe56e130e4f52229c7260d475fdd1ddac93cf1d06867a1da242da"),(0x0010DB80,0x0010DBAC,"bf4aa00e830cf58d77c7077c213fd4ca73f61c6d65f00ffa9fb81fede9fb43b0"),(0x001781A0,0x001781CC,"eb841e98778305dbad8acbfca703e68198cb278e4d4b608305afb8f339bc9763"),(0x00198E70,0x00198EF3,"d7621f25bacd709a2d2dc0688c0555e855ce3a9afa685942bf5bbf9a61b074c1"),(0x001B3500,0x001B352C,"dde340656133e9a920ad0237602768d9ecca308a8d7ef5c2ffd5623b81c9ec25"),(0x00205E10,0x00205E7F,"675cf4630daa280a798fe8516fa6f3ad41e1d358a1af57ac153e909410c58635"),(0x00226D50,0x00226D7B,"de171f9f7f8880a18bce6cdd5b2631640b879fc67d9b350d6693d7e1d2c98309"),(0x00244C70,0x00244C9C,"ce43fc1ccbaa56b8ab36d8fd0b01c32ca2aa4c8099893c80a9e6ae9c6184b6cf"),(0x00291FB0,0x00291FD8,"83f5695d0004e26cb2ace2fc1b5381a5feedba8b46a98fed9bf36f2a1276b720"),(0x00292030,0x00292058,"a3623440226b7fd5e03feb06f9c2d62e7dc988022dc86919c6999b02f8c6835b"),(0x002920B0,0x002920D9,"b359b36a3b2287f023f2053b040ec64e9425efec47c1c48c05077d12af9e5cd3"),
 (0x002DD660,0x002DD671,"e8a3a5fc855c8140de7d1d267cc4eb57d07b0ed0a82f6e9c9d8c2ea2470a42da"),(0x002DD6D0,0x002DD6E1,"41ec42b28b1f508b0b8b0a6f7eebeae8d8a666c6cef029f2d6c6c859c86d56f3"),(0x002DD740,0x002DD751,"e4a5b7bb22165200e598c075f2968dc9cef6c1a985f65b1ac3442df86277e276"),(0x002DD7B0,0x002DD7C2,"a4d4a16377a77464ff2fbd58e020c18dddce0181b0b2102de0691ebe4d7ee7f9"),(0x002DD8D0,0x002DD8E1,"a328e3ec4fc886c05250eae6dc023860b996a5f576588403d59ace99c73b001d"),(0x002DD940,0x002DD951,"54a434c3b5ab57c14d6902deae22d24307423762d896702f393561e154e6a46b"),(0x002DD9B0,0x002DD9C1,"b2f863241d5ebd0d394addbbcb57c25e27fa90146588e37188ee9e698bac5a39"),(0x002DDA20,0x002DDA4C,"291c1e40f9e1a1d19258ebe956d3c53a7e80766ea9f490c3721658212dc39184"),(0x002DDAC0,0x002DDAD1,"a6226ce936feb4d447fe7cbc247918222f8f3906166c86358d4f82e57fb32d37"),(0x002DDB30,0x002DDB40,"594e1a1edce8643fa0f90e769ea18ff864df043fafce1b02a0fb17adedf62827"),(0x002DDBB0,0x002DDBC1,"edc0b26992c55ed5f444658c36372f7a5be80c02b56d46151ccf65418e73abed"),(0x002DDC20,0x002DDC31,"05ffc753c586596dfd426b7b9a3f807d95dec16c49e6e1db17cee36fc7500c2f"),(0x002DDD90,0x002DDDA1,"6dbfa7bc4cadf95391e7c1454c0946ac1211aab36046d73fcc0be423cd13b388"),(0x002DDE00,0x002DDE11,"d0282a3a0790c1554f972faea6b1270cc209a7135eda11608b3425967952d562"),(0x002DDE70,0x002DDE82,"89739e3dac4238cc3090c670eecf26db73fa2aa24db6e871923929a874241331"),(0x002DDEF0,0x002DDF01,"18fde46b9052e7118d1443739e714582192e288dd8b0447e59eec37a3190309f"),(0x002DDF60,0x002DDF71,"b3f97554eec33a4d020ce7b440f26b443d6bf840bdd912262b0db940e6e2edf8"),(0x002DE060,0x002DE071,"d38059651c5eac6d52af770de83e3e6bb6db71fa32d7b94e44ba163737b886df"),(0x002DE330,0x002DE35C,"fad59b12dc0b9f8541c9523b08553c08acad7e4d1480bf814f41f1359de21800"),(0x002DE3D0,0x002DE3FC,"a30ab08abc0321c9b93ab9b64fed9ee7db4c4ec8ff13e542cdd453a259a7b394"),(0x002DE500,0x002DE511,"ee29873b55814268d49505e4a5a0d25deb96f52edc32ee24b04d01c0f0aaa025"),(0x002DE570,0x002DE581,"60451a09c781eddb84372374982390892251714301ba494b2412012f43cc46f4"),(0x002DE670,0x002DE682,"03f6ecb4cdba66d0a50469a187f6effbe804f23811e1cd55ceb37b45a306d996"),(0x002DE6F0,0x002DE702,"d45eb66f0d45c206580806c60588c3826c6b333e10a0e763313797639c700ebb"),(0x002DE770,0x002DE782,"b0f57929c71daf9bb9f412483a5fd4ff17d8cb8fae7c17442abe7bf97b31365a"),(0x002DE7F0,0x002DE802,"f72a7b6c89b1aab065026a5db450ae374c3958e2da403848d565882614ba293b"),(0x002DE870,0x002DE880,"ef92d1667f4d7a51b40dab85d3aa08cb6f2b9b6ab403bbeba55384ead52b96bb"),(0x002DE8F0,0x002DE902,"225558d836a520bdfb91338cc6173b3e7c4ef3be6b1c7c2de3c0b533ab5b5fe6"),(0x002DE970,0x002DE982,"02bce01dc3274e2436315e1ce6921e9404cc917c7f4af1b0fb821a8b8f4f1830"),(0x002DE9F0,0x002DEA02,"9f29a6eadd0d0cd6815d3926873c743c1250084014bb7a0e9360f6fd25f7e468"),(0x002DEA70,0x002DEA82,"b42b8455d5c3e83bf2b73b471950d71850178c719afc46cd4c8ddc6acbde299a"),(0x002DEAF0,0x002DEB02,"bc81fd49511e9fabff83bcc321d7c455b10026cc78210fb1e04fb268cb8e2dd3"),(0x002DEB70,0x002DEB82,"7e704708234bb0678d677f544a22922e30bb55d88cd945b529c26b8275173989"),(0x002DEBF0,0x002DEC02,"a86f4d69b6fa255396e12a638c5b6169b4f48546711a275844a2fe234bd60c56"),(0x002DEC70,0x002DEC82,"7441652577f52b891bbe6c63cc4005f806dbf2b21da0e793a27e22a6c6da0dce"),(0x002DECF0,0x002DED02,"a9138aa970cb01b18eb62697cfeb5149809c9a2ae5a522d94eca3dee970a99f3"),(0x002DED70,0x002DED82,"dafc64b51b93adde874d2c2941ef3d5cbc0215f92c5cd06acd9950720cbf0570"),
 (0x002E2560,0x002E2571,"f788890457f0130eb0751e7f295f349603557b0b21cf225d9a4857403a2c6395"),(0x002E25D0,0x002E25E0,"cebd7be8a5bfea378c1a3be699f9c6f51bf836ded97ea527b3b76907d2a988eb"),(0x002E2650,0x002E2661,"fe21a96006c8a1d6eedfeb634ecde8ef6758bdcc5f2b07a40b99d284979e39f8"),(0x002E26C0,0x002E26D1,"05e206060f1e23de28fb7303f4b50b8f4616354f77037d038d7f390e0ececb2f"),(0x002E2730,0x002E2741,"18f8c70b0da70f50a58cb3da69897705f3d582dd170a81acc14fd50bf9f8542d"),(0x002E27A0,0x002E27B1,"99e910a6b91708725fed81ad7d5f70df1a742fdea2f5d779dbe07e8d1a31a4bf"),(0x002E2810,0x002E2821,"40fb7a2b496a46999f517f7fc59e42ae22af2066d917c00f49e4f572932a33f7"),(0x002E2880,0x002E2891,"f327c6e5be7850519ba4bdde68404777e79af97512981f0f6c7e2cd4f969ca20"),(0x002E28F0,0x002E2901,"bdaff3718997380f5edd34e467de90fbf327ecc7a89dca648a56ad02ba665f5b"),(0x002E2960,0x002E2971,"eb677c271c141bad706106fda41dd00182636e0de5ff58357ee98522e9502743"),
)

_METHOD = {"accepted_chain":"One exact initializer wrapper-closure producer is joined to the wrapper, reusable numeric-slot recognizer, complete direct and staged Lua call partitions, literal, and exhaustive two-target operand scan.","lua51_abi_premises":["Lua stack indices use Lua 5.1 meanings","lua_type zero denotes nil","lua_error does not return normally","Lua upvalue pseudo-indices -10003 and -10004 name upvalues one and two","x86 Windows cdecl preserves EBX and EDI across calls"],"not_claimed":["runtime reachability, execution, ordering, frequency, or persistence","successful lookup or invocation, selected-value callability, operator or metamethod invocation","arbitrary entry arity behavior, source-level operator contract, factory provenance, type identity, ownership, or lifetime","recognizer caller semantic homogeneity","computed, indirect, data, un-atlased, or Lua-side references"]}


def _direct_records(direct_calls: Mapping[str, Any], entry: int, calls: tuple[tuple[int,str], ...]) -> list[dict[str, Any]]:
    found=[_mapping(x,"direct census record") for x in _array(direct_calls.get("records"),"direct census records") if isinstance(x,Mapping) and _rva(x.get("entry_rva"),"direct entry")==entry]
    if len(found)!=1: raise NativeLuaPropertyOperatorDispatchChainError("operator direct census body is not unique")
    result=[]
    for raw in _array(found[0].get("direct_lua_import_calls"),"direct Lua calls"):
        x=_mapping(raw,"direct Lua call")
        if x.get("library")!=_LUA_LIBRARY or x.get("call_form")!="x86_absolute_iat_indirect_call_ff15": raise NativeLuaPropertyOperatorDispatchChainError("operator Lua call form changed")
        result.append({"rva":x["call_rva"],"api":x["import_name"],"instruction_size":x["instruction_size"],"instruction_sha256":x["instruction_sha256"]})
    if [(x["rva"],x["api"]) for x in result] != [(_hex(r),a) for r,a in calls]: raise NativeLuaPropertyOperatorDispatchChainError("operator direct Lua-call partition changed")
    return result


def _staged() -> list[dict[str, Any]]:
    return [
      {"api":"lua_settop","register":"EBX","stages":[{"rva":"0x002ea22b","instruction_sha256":"bb29acd6af54bacbc55c5d74c46f0281756d777615e72b7475d4cd57a0d575d4"},{"rva":"0x002ea23b","instruction_sha256":"bb29acd6af54bacbc55c5d74c46f0281756d777615e72b7475d4cd57a0d575d4"}],"calls":[{"rva":"0x002ea234","last_definition_stage_rvas":["0x002ea22b"]},{"rva":"0x002ea25c","last_definition_stage_rvas":["0x002ea22b","0x002ea23b"]}]},
      {"api":"lua_toboolean","register":"EDI","stages":[{"rva":"0x002ea284","instruction_sha256":"813ea1d7a37ad05d6ee023cc7f3955d4f5a971157eee2dd8ffffb9b8d16741de"}],"calls":[{"rva":"0x002ea290","last_definition_stage_rvas":["0x002ea284"]},{"rva":"0x002ea2a2","last_definition_stage_rvas":["0x002ea284"]}]},
    ]


def _audit() -> list[dict[str, Any]]:
    retained={"ffd3":["0x002ea234","0x002ea25c"],"ffd7":["0x002ea290","0x002ea2a2"]}
    return [{"opcode_hex":f"ffd{n:x}","call_rvas":retained.get(f"ffd{n:x}",[])} for n in range(8)]


def _body_records(facts: Mapping[str, Any], direct: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions=_atlas_functions(facts); result=[]
    for role,entry,size,body,cfg,nodes,edges,calls in _FUNCTIONS:
        f=functions.get(entry)
        if f is None or f.get("thunk") is not False or f.get("body_size")!=size or f.get("body_sha256")!=body: raise NativeLuaPropertyOperatorDispatchChainError("operator atlas body identity changed")
        item={"role":role,"entry_rva":_hex(entry),"atlas_record_sha256":atlas_record_sha256(f),"body_size":size,"body_sha256":body,"control_flow_graph_canonical_sha256":cfg,"control_flow_graph_node_count":nodes,"control_flow_graph_edge_count":edges,"direct_lua_calls":_direct_records(direct,entry,calls),"staged_lua_calls":_staged() if entry==0x002EA1A0 else [],"call_r32_audit":_audit() if entry==0x002EA1A0 else _audit_empty()}
        result.append(item)
    return result


def _audit_empty() -> list[dict[str, Any]]: return [{"opcode_hex":f"ffd{n:x}","call_rvas":[]} for n in range(8)]


def _last_reaching_definitions(graph: Mapping[str, Any], decoded: Mapping[int, Any], *, entry: int, call: int, register: int) -> set[int]:
    """Prove ``stage`` is the last decoded definition of ``register`` at ``call``.

    This is a fixed-point reaching-definition proof, deliberately not a simple
    stage-to-call no-writer path check: the a23b stage is revisited after loop
    paths which can clobber EBX, and the final revisit must dominate the error
    call as the *last* definition.
    """
    nodes={_rva(x["rva"],"CFG node"):x for x in _array(graph["nodes"],"CFG nodes")}
    if set(nodes)!=set(decoded) or entry not in nodes or call not in nodes: return set()
    predecessors={r:set() for r in nodes}
    for r,node in nodes.items():
        for raw in _array(node["successor_rvas"],"CFG successors"):
            nxt=_rva(raw,"CFG successor")
            if nxt not in predecessors: return set()
            predecessors[nxt].add(r)
    def writes(rva: int) -> bool:
        try:
            _reads, written=decoded[rva].regs_access()
        except Exception:
            return True
        return register in written

    def outgoing(rva: int) -> set[int]:
        return {rva} if writes(rva) else set(incoming[rva])

    incoming={r:set() for r in nodes}; incoming[entry]={-1}
    changed=True
    while changed:
        changed=False
        for r in sorted(nodes):
            if r==entry: continue
            merged=set().union(*(outgoing(p) for p in predecessors[r])) if predecessors[r] else set()
            if merged!=incoming[r]: incoming[r]=merged; changed=True
    return incoming[call]



def _literal_expected() -> dict[str, Any]:
    return {"role":"operator_error","text":"No such operator defined","rva":"0x0043c4a4","byte_length_excluding_nul":24,"bytes_including_nul":25,"nul_terminated_bytes_sha256":"d16f10ee15af8c2e95b531a7149f4063e4c2239b47ac228e943c74e08712ad56","section_name":".rdata","section_rva":"0x003d6000","section_characteristics":"0x40000040","section_writable":False}


def _literal_exact(data: bytes,image: Any) -> dict[str, Any]:
    offset=image.rva_to_file_offset(0x0043C4A4)
    if offset is None: raise NativeLuaPropertyOperatorDispatchChainError("operator error literal is not file backed")
    raw=data[offset:offset+25]; sec=image.section_for_offset(offset)
    if raw!=b"No such operator defined\0" or hashlib.sha256(raw).hexdigest()!=_literal_expected()["nul_terminated_bytes_sha256"] or sec is None or sec.name!=".rdata" or sec.virtual_address!=0x003D6000 or sec.characteristics!=0x40000040 or sec.characteristics&_WRITABLE: raise NativeLuaPropertyOperatorDispatchChainError("operator error literal changed")
    return _literal_expected()


def _placement(initializer: Mapping[str, Any]) -> dict[str, Any]:
    if initializer.get("analysis_kind")!=INITIALIZER_ANALYSIS_KIND or _canonical_sha256(initializer)!=_INIT_SHA: raise NativeLuaPropertyOperatorDispatchChainError("initializer prerequisite identity changed")
    loop=_mapping(_mapping(initializer.get("semantics"),"initializer semantics").get("wrapper_loop"),"initializer wrapper loop")
    rows=_array(loop.get("ordered_rows"),"operator wrapper rows")
    if loop.get("callback_entry_rva")!="0x002ea1a0" or loop.get("closure_upvalue_count")!=2 or loop.get("upvalue_order")!=["K","B"] or loop.get("true_boolean_indices")!=[9,12] or len(rows)!=13:
        raise NativeLuaPropertyOperatorDispatchChainError("initializer wrapper placement changed")
    if [(_mapping(row,"operator row").get("index"),row.get("boolean_upvalue")) for row in rows] != [(index,index in {9,12}) for index in range(13)]:
        raise NativeLuaPropertyOperatorDispatchChainError("initializer wrapper row partition changed")
    return {"initializer_entry_rva":"0x002ea2d0","initializer_atlas_record_sha256":"9bebfe870176e21574adce7ab56dc323785c19e0cdb73d03afc267a3edf84c1f","closure_count":13,"callback_entry_rva":"0x002ea1a0","upvalue_order":["K","B"],"true_boolean_indices":[9,12]}


def _references(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    functions=_atlas_functions(facts); rows=[]
    def row(ins,owner,target,sha,use):
        f=functions.get(owner)
        if f is None: raise NativeLuaPropertyOperatorDispatchChainError("target-reference owner is absent")
        return {"instruction_rva":_hex(ins),"instruction_size":5,"instruction_sha256":sha,"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(f),"target_rva":_hex(target),"operand_class":"immediate","operand_index":0,"use_class":use}
    for owner,ins,sha in _RECOGNIZER_CALLS: rows.append(row(ins,owner,0x002EA3D0,sha,"recognizer_direct_call"))
    rows.append(row(0x002EA3A7,0x002EA2D0,0x002EA1A0,"33e9988ef68a664f937a5920541f4beb1f1cf901ac168c2486e17d9fa2749c24","initializer_wrapper_closure_producer"))
    return rows


def _semantics() -> dict[str, Any]:
    return {"wrapper_two_input_search":{"entry_arity_guard":False,"examined_input_indices":[1,2],"never_examines_input_index":3,"marker":{"metatable_numeric_slot":1,"getter_callback_entry_rva":"0x002ea110","cleanup_index":-3,"marker_mismatch_restores_entry_stack":True},"key_upvalue_index":-10003,"boolean_upvalue_index":-10004,"nil_candidate_cleanup_index":-2,"error_clear_index_formula":"-top-1","error_api":"lua_error","error_normal_return_claimed":False,"success":{"insert_index":1,"boolean_read_count":2,"false_nargs":"saved_entry_top","true_nargs":1,"true_remove_absolute_index":3,"lua_call_result_count":1,"normal_result_count":1},"true_arm_arbitrary_arity_claimed":False,"candidate_callability_proven":False},"recognizer_predicate":{"state_register":"ECX","index_register":"EDX","input_conversion":"lua_touserdata","requires_non_null_conversion_result":True,"requires_getmetatable_success":True,"metatable_numeric_slot":1,"getter_callback_entry_rva":"0x002ea110","cleanup_index":-3,"match_returns_original_conversion_result":True,"pointer_type_identity_claimed":False,"caller_semantics_claimed":False}}


def _summary(value: Mapping[str, Any]) -> dict[str, Any]:
    bodies=_array(value["source_bodies"],"bodies"); refs=_array(value["target_reference_scan"]["references"],"references")
    return {"initializer_prerequisite_count":1,"source_body_count":len(bodies),"source_body_bytes":sum(x["body_size"] for x in bodies),"source_cfg_node_count":sum(x["control_flow_graph_node_count"] for x in bodies),"source_cfg_edge_count":sum(x["control_flow_graph_edge_count"] for x in bodies),"direct_lua_call_count":sum(len(x["direct_lua_calls"]) for x in bodies),"staged_lua_call_count":sum(len(c["calls"]) for x in bodies for c in x["staged_lua_calls"]),"literal_count":1,"target_reference_count":len(refs),"wrapper_closure_producer_count":sum(x["use_class"]=="initializer_wrapper_closure_producer" for x in refs),"recognizer_direct_call_reference_count":sum(x["use_class"]=="recognizer_direct_call" for x in refs),"recognizer_owner_count":len({x["owner_entry_rva"] for x in refs if x["use_class"]=="recognizer_direct_call"}),"schema_violations":0}


def _derive(initializer: Mapping[str, Any],facts: Mapping[str, Any],direct: Mapping[str, Any],literal: Mapping[str, Any]) -> dict[str, Any]:
    _validate_json_tree(initializer,"initializer"); _validate_json_tree(facts,"program facts"); _validate_json_tree(direct,"direct calls")
    identity=_mapping(facts.get("identity"),"program facts identity")
    if identity.get("executable_sha256")!=_EXE_SHA or initializer.get("build_identity")!=dict(identity) or direct.get("build_identity")!=dict(identity): raise NativeLuaPropertyOperatorDispatchChainError("operator prerequisites have different build identities")
    result={"schema_version":SCHEMA_VERSION,"analysis_kind":ANALYSIS_KIND,"build_identity":dict(identity),"initializer_chain":{"analysis_kind":INITIALIZER_ANALYSIS_KIND,"canonical_sha256":_canonical_sha256(initializer)},"initializer_wrapper_placement":_placement(initializer),"source_bodies":_body_records(facts,direct),"literal":dict(literal),"target_reference_scan":{"target_rvas":["0x002ea1a0","0x002ea3d0"],"scope":{"atlas_function_count":len(_atlas_functions(facts)),"atlas_body_range_count":25490,"decoded_bytes":3735718,"decoded_instructions":1153814,"all_declared_ranges_decoded":True,"operand_classes":["absolute_memory","immediate"]},"references":_references(facts)},"semantics":_semantics(),"method":copy.deepcopy(_METHOD)}
    if dict(literal)!=_literal_expected(): raise NativeLuaPropertyOperatorDispatchChainError("operator literal record changed")
    result["summary"]=_summary(result); _assert_publication_safe(result); return result


def _exact_function_checks(data: bytes,image: Any,facts: Mapping[str, Any],direct: Mapping[str, Any]) -> None:
    import capstone
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; functions=_atlas_functions(facts)
    imports={x.get("name"):_rva(x.get("iat_rva"),"Lua import IAT") for x in _array(direct.get("lua_imports"),"Lua imports") if isinstance(x,Mapping) and x.get("library")==_LUA_LIBRARY}
    for role,entry,size,body,cfg,nodes,edges,calls in _FUNCTIONS:
        f=functions[entry]; ranges=_array(f["ranges"],"ranges")
        if len(ranges)!=1: raise NativeLuaPropertyOperatorDispatchChainError("operator body has multiple ranges")
        span=_mapping(ranges[0],"range"); start=_rva(span["start_rva"],"range start")
        if start!=entry or span.get("size")!=size: raise NativeLuaPropertyOperatorDispatchChainError("operator atlas range changed")
        ins=_decode_range(data,image,start,size,decoder); graph=_enhanced_cfg(ins,image.image_base,(start,size),capstone,x86); graph["caller_entry_rva"]=_hex(entry); graph=_with_edi_writes(graph,ins,x86)
        if _canonical_sha256(graph)!=cfg or graph["node_count"]!=nodes or graph["edge_count"]!=edges: raise NativeLuaPropertyOperatorDispatchChainError("operator CFG identity changed")
        decoded={i.address-image.image_base:i for i in ins}
        for c in _direct_records(direct,entry,calls):
            i=decoded.get(_rva(c["rva"],"direct call"))
            if i is None or hashlib.sha256(bytes(i.bytes)).hexdigest()!=c["instruction_sha256"]: raise NativeLuaPropertyOperatorDispatchChainError("operator direct call bytes changed")
        actual=[]
        for i in ins:
            raw=bytes(i.bytes)
            if len(raw)==2 and raw[0]==0xff and 0xd0<=raw[1]<=0xd7: actual.append((_hex(i.address-image.image_base),raw.hex()))
        expected=[(r["call_rvas"],r["opcode_hex"]) for r in (_audit() if entry==0x002EA1A0 else _audit_empty())]
        if {op:sorted(rvas) for rvas,op in expected}!={f"ffd{x:x}":[r for r,b in actual if b==f"ffd{x:x}"] for x in range(8)}: raise NativeLuaPropertyOperatorDispatchChainError("operator call-r32 audit changed")
        if entry==0x002EA1A0:
            stages=_staged()
            register_ids={"EBX":x86.X86_REG_EBX,"EDI":x86.X86_REG_EDI}
            prefixes={"EBX":b"\x8b\x1d","EDI":b"\x8b\x3d"}
            for record in stages:
                api=record["api"]; reg=record["register"]; iat=imports.get(api)
                expected_stage=prefixes[reg]+(image.image_base+iat).to_bytes(4,"little") if iat is not None else b""
                for raw_stage in record["stages"]:
                    stage=_rva(raw_stage["rva"],"stage rva"); i=decoded.get(stage)
                    if i is None or bytes(i.bytes)!=expected_stage or hashlib.sha256(bytes(i.bytes)).hexdigest()!=raw_stage["instruction_sha256"]:
                        raise NativeLuaPropertyOperatorDispatchChainError("operator staged import changed")
                for raw_call in record["calls"]:
                    call=_rva(raw_call["rva"],"staged call rva"); target=decoded.get(call)
                    opcode=b"\xff\xd3" if reg=="EBX" else b"\xff\xd7"
                    wanted={_rva(value,"last-definition stage") for value in raw_call["last_definition_stage_rvas"]}
                    if target is None or bytes(target.bytes)!=opcode or _last_reaching_definitions(graph,decoded,entry=entry,call=call,register=register_ids[reg])!=wanted:
                        raise NativeLuaPropertyOperatorDispatchChainError("operator staged-register provenance changed")


def _exact_reference_scan(data: bytes,image: Any,facts: Mapping[str, Any]) -> None:
    import capstone.x86_const as x86
    decoder,_=_decoder(); decoder.detail=True; targets={image.image_base+0x002EA1A0:0x002EA1A0,image.image_base+0x002EA3D0:0x002EA3D0}; found=[]; ranges=total=ins_total=0; functions=_atlas_functions(facts)
    for owner,f in sorted(functions.items()):
        for raw in _array(f["ranges"],"ranges"):
            span=_mapping(raw,"range"); start=_rva(span["start_rva"],"range start"); size=span["size"]; ins=_decode_range(data,image,start,size,decoder); ranges+=1; total+=size; ins_total+=len(ins)
            for i in ins:
                for index,op in enumerate(i.operands):
                    if op.type==x86.X86_OP_IMM: value=int(op.imm)&0xffffffff; kind="immediate"
                    elif op.type==x86.X86_OP_MEM and op.mem.base==x86.X86_REG_INVALID and op.mem.index==x86.X86_REG_INVALID: value=int(op.mem.disp)&0xffffffff; kind="absolute_memory"
                    else: continue
                    if value in targets: found.append((i.address-image.image_base,owner,targets[value],kind,index,bytes(i.bytes)))
    expected=_references(facts); observed=[]
    for r,owner,target,kind,index,raw in found:
        observed.append({"instruction_rva":_hex(r),"instruction_size":len(raw),"instruction_sha256":hashlib.sha256(raw).hexdigest(),"owner_entry_rva":_hex(owner),"owner_atlas_record_sha256":atlas_record_sha256(functions[owner]),"target_rva":_hex(target),"operand_class":kind,"operand_index":index,"use_class":"initializer_wrapper_closure_producer" if r==0x002EA3A7 else "recognizer_direct_call"})
    if observed!=expected or (ranges,total,ins_total)!=(25490,3735718,1153814): raise NativeLuaPropertyOperatorDispatchChainError("operator target-reference scan changed")


def build_native_lua_property_operator_dispatch_chain(executable: Path,initializer: Mapping[str, Any],consumer: Mapping[str, Any],property_factory_chain: Mapping[str, Any],direct_calls: Mapping[str, Any],callback_census: Mapping[str, Any],setfield_publications: Mapping[str, Any],direct_table_setter_publications: Mapping[str, Any],indirect_settable_publications: Mapping[str, Any],table_key_provenance: Mapping[str, Any],terminal_dispositions: Mapping[str, Any],program_facts: Mapping[str, Any],*,inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        receipt=validate_native_lua_property_initializer_chain(executable,initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts,inventory=inventory)
        if receipt.get("analysis_kind")!=INITIALIZER_VERIFICATION_KIND or receipt.get("status")!="verified" or receipt.get("evidence_sha256")!=_INIT_SHA: raise NativeLuaPropertyOperatorDispatchChainError("initializer exact verifier returned another result")
        data,image,digest=_load_executable(executable)
        if digest!=_EXE_SHA: raise NativeLuaPropertyOperatorDispatchChainError("operator executable identity changed")
        _exact_function_checks(data,image,program_facts,direct_calls); _exact_reference_scan(data,image,program_facts)
        return _derive(initializer,program_facts,direct_calls,_literal_exact(data,image))
    except NativeLuaPropertyOperatorDispatchChainError: raise
    except (NativeLuaPropertyInitializerChainError,NativeLuaCClosurePublicationError,NativeLuaDirectCallError,PEAnchorError) as exc: raise NativeLuaPropertyOperatorDispatchChainError(f"operator prerequisite exact verification failed: {exc}") from exc


def validate_native_lua_property_operator_dispatch_chain_structure(evidence: Mapping[str, Any],initializer: Mapping[str, Any],consumer: Mapping[str, Any],property_factory_chain: Mapping[str, Any],direct_calls: Mapping[str, Any],callback_census: Mapping[str, Any],setfield_publications: Mapping[str, Any],direct_table_setter_publications: Mapping[str, Any],indirect_settable_publications: Mapping[str, Any],table_key_provenance: Mapping[str, Any],terminal_dispositions: Mapping[str, Any],program_facts: Mapping[str, Any]) -> dict[str, Any]:
    try: receipt=validate_native_lua_property_initializer_chain_structure(initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts)
    except (NativeLuaPropertyInitializerChainError,NativeLuaCClosurePublicationError) as exc: raise NativeLuaPropertyOperatorDispatchChainError(f"operator structural prerequisite failed: {exc}") from exc
    if receipt.get("analysis_kind")!=INITIALIZER_STRUCTURE_VERIFICATION_KIND or receipt.get("status")!="structurally_verified" or receipt.get("evidence_sha256")!=_INIT_SHA: raise NativeLuaPropertyOperatorDispatchChainError("initializer structural verifier returned another result")
    try:
        expected=_derive(initializer,program_facts,direct_calls,_literal_expected()); evidence=_mapping(evidence,"evidence"); _exact_keys(evidence,set(expected),"evidence")
        if _canonical_bytes(evidence)!=_canonical_bytes(expected): raise NativeLuaPropertyOperatorDispatchChainError("operator evidence differs from structural replay")
    except NativeLuaCClosurePublicationError as exc: raise NativeLuaPropertyOperatorDispatchChainError(f"operator structural replay failed: {exc}") from exc
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":STRUCTURE_VERIFICATION_KIND,"status":"structurally_verified","build_identity":dict(expected["build_identity"]),"evidence_sha256":_canonical_sha256(expected),"summary":dict(expected["summary"])}


def validate_native_lua_property_operator_dispatch_chain(executable: Path,evidence: Mapping[str, Any],initializer: Mapping[str, Any],consumer: Mapping[str, Any],property_factory_chain: Mapping[str, Any],direct_calls: Mapping[str, Any],callback_census: Mapping[str, Any],setfield_publications: Mapping[str, Any],direct_table_setter_publications: Mapping[str, Any],indirect_settable_publications: Mapping[str, Any],table_key_provenance: Mapping[str, Any],terminal_dispositions: Mapping[str, Any],program_facts: Mapping[str, Any],*,inventory: Mapping[str, Any]) -> dict[str, Any]:
    rebuilt=build_native_lua_property_operator_dispatch_chain(executable,initializer,consumer,property_factory_chain,direct_calls,callback_census,setfield_publications,direct_table_setter_publications,indirect_settable_publications,table_key_provenance,terminal_dispositions,program_facts,inventory=inventory)
    if _canonical_bytes(evidence)!=_canonical_bytes(rebuilt): raise NativeLuaPropertyOperatorDispatchChainError("operator evidence differs from exact rebuild")
    return {"schema_version":SCHEMA_VERSION,"analysis_kind":VERIFICATION_KIND,"status":"verified","build_identity":dict(rebuilt["build_identity"]),"evidence_sha256":_canonical_sha256(rebuilt),"summary":dict(rebuilt["summary"])}


def encode_native_lua_property_operator_dispatch_chain(value: Mapping[str, Any]) -> str:
    _validate_json_tree(value)
    return json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+"\n"
