from pathlib import Path


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def _repair_command_source() -> str:
    source = MODLOADER.read_text()
    start = source.index('elseif cmd == "REPAIR"')
    end = source.index('elseif cmd == "DEPLOY"', start)
    return source[start:end]


def test_direct_repair_helper_clears_every_modeled_repair_status():
    source = MODLOADER.read_text()
    start = source.index("local function direct_repair_pawn")
    end = source.index("local function execute_command", start)
    helper = source[start:end]

    assert "get_pawn_max_health(target, target_uid, save_data)" in helper
    assert "target.SetHealth" in helper
    assert "sd.iFire = effect_remove" in helper
    assert "sd.iAcid = effect_remove" in helper
    assert "sd.iFrozen = effect_remove" in helper
    assert "sd.iInjure = effect_remove" in helper
    assert "target.SetInfected" in helper


def test_bridge_repair_field_reuses_direct_repair_for_other_mechs():
    repair = _repair_command_source()

    assert 'fn("Mass_Repair")' in repair
    assert '_G["TEAM_MECH"] or TEAM_PLAYER' in repair
    assert "extract_table(Board:GetPawns(mech_team))" in repair
    assert "if mid ~= uid then" in repair
    assert repair.count("direct_repair_pawn(") == 2
    assert 'method = method .. "_mass"' in repair
    assert "target:SetActive(false)" not in repair
