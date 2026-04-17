"""Probe the live game for deployment-zone APIs.

Sends LUA commands via the bridge to discover what actually returns
the current yellow Drop Zone. Run while the game is sitting on the
"Deploying <MechName>" prompt.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bridge.protocol import write_command, wait_for_ack, BridgeError


def run(lua: str) -> str:
    write_command("LUA " + lua)
    try:
        return wait_for_ack(timeout=5.0)
    except (TimeoutError, BridgeError) as e:
        return f"<err: {e}>"


def main() -> None:
    probes = [
        # Baseline: what Board:GetZone returns today.
        ("GetZone('deployment') exists?", "return tostring(Board and Board.GetZone ~= nil)"),
        ("GetZone('deployment') type", "local z = Board:GetZone('deployment'); return type(z)"),
        ("GetZone('deployment') size", "local z = Board:GetZone('deployment'); return z and z:size() or -1"),

        # Phase / team state
        ("team turn", "return Game and Game:GetTeamTurn() or 'nil'"),
        ("turn count", "return Game and Game:GetTurnCount() or 'nil'"),

        # Mission object fields
        ("current mission id", "return _ITB_CURRENT_MISSION and (_ITB_CURRENT_MISSION.ID or _ITB_CURRENT_MISSION.Name) or 'nil'"),
        ("mission MapTags", "local m=_ITB_CURRENT_MISSION; if not m or not m.MapTags then return 'nil' end; local s=''; for i,t in ipairs(m.MapTags) do s=s..t..',' end; return s"),
        ("mission fields with 'deploy'",
         "local m=_ITB_CURRENT_MISSION; if not m then return 'nil' end; "
         "local s=''; for k,v in pairs(m) do local lk=tostring(k):lower(); "
         "if lk:find('deploy') or lk:find('drop') then s=s..k..'='..tostring(v)..'|' end end; return s"),

        # Enumerate all Board methods that mention deploy/zone
        ("Board fns with 'deploy' or 'zone'",
         "local s=''; for k,v in pairs(getmetatable(Board) or {}) do if type(v)=='function' then "
         "local lk=tostring(k):lower(); if lk:find('deploy') or lk:find('zone') then s=s..k..',' end end end; return s"),

        # GetDeployLocScore for every tile (output lines of "x,y:score")
        ("GetDeployLocScore grid",
         "local out={}; for x=0,7 do for y=0,7 do "
         "local ok,sc=pcall(function() return Board:GetDeployLocScore(Point(x,y)) end); "
         "if ok then table.insert(out, string.format('%d,%d:%s',x,y,tostring(sc))) end end end; "
         "return table.concat(out,' ')"),

        # Any globals whose name hints at deployment
        ("globals with 'deploy'",
         "local s=''; for k,v in pairs(_G) do local lk=tostring(k):lower(); "
         "if lk:find('deploy') then s=s..k..',' end end; return s"),

        # Try other zone names that might mean drop zone
        ("GetZone('drop') size", "local z=Board:GetZone('drop'); return z and z:size() or 'nil'"),
        ("GetZone('drop_zone') size", "local z=Board:GetZone('drop_zone'); return z and z:size() or 'nil'"),
        ("GetZone('dropzone') size", "local z=Board:GetZone('dropzone'); return z and z:size() or 'nil'"),
        ("GetZone('mech_deploy') size", "local z=Board:GetZone('mech_deploy'); return z and z:size() or 'nil'"),
        ("GetZone('mechdrop') size", "local z=Board:GetZone('mechdrop'); return z and z:size() or 'nil'"),

        # Probe mission OBJECT members more broadly
        ("mission keys (all)",
         "local m=_ITB_CURRENT_MISSION; if not m then return 'nil' end; "
         "local s=''; for k,v in pairs(m) do s=s..k..'('..type(v)..'),' end; return s"),

        # Probe Board members
        ("Board keys (non-fn)",
         "local s=''; for k,v in pairs(Board) do if type(v)~='function' then s=s..k..'('..type(v)..'),' end end; return s"),

        # Look at mission metatable / class parents
        ("mission metatable",
         "local m=_ITB_CURRENT_MISSION; local mt=getmetatable(m); "
         "if not mt then return 'no mt' end; local s=''; for k,v in pairs(mt) do s=s..k..',' end; return s"),

        # Check Game for deployment state
        ("Game deployment-ish",
         "local s=''; local mt=getmetatable(Game) or {}; "
         "for k,v in pairs(mt) do local lk=tostring(k):lower(); "
         "if lk:find('deploy') or lk:find('drop') or lk:find('phase') or lk:find('state') then s=s..k..',' end end; return s"),

        # TileState/Highlight query
        ("Board tile highlighted? 0,0",
         "local ok,r=pcall(function() return Board:IsTileHighlighted(Point(0,0)) end); return ok and tostring(r) or 'no fn'"),

        # DropZone struct
        ("DropZone global", "return tostring(DropZone)"),
        ("g_DropZone", "return tostring(g_DropZone)"),
    ]

    for label, lua in probes:
        print(f"=== {label} ===")
        print(run(lua))
        print()


if __name__ == "__main__":
    main()
