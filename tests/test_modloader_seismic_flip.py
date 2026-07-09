from pathlib import Path


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def test_seismic_bridge_fallback_is_guarded_by_unchanged_live_queued_shot():
    source = MODLOADER.read_text()

    snapshot = 'if string.find(wname, "^Science_KO_Crack") ~= nil then'
    fire = "pawn:FireWeapon(Point(tx, ty), slot)"
    unchanged = "queued.x == seismic_flip_before.x"
    flip = "flip.iPush = DIR_FLIP"

    assert source.count(snapshot) == 1
    assert source.count(unchanged) == 1
    assert source.count(flip) == 1
    assert source.index(snapshot) < source.index(fire)
    assert source.index(fire) < source.index(unchanged) < source.index(flip)


def test_seismic_bridge_fallback_requires_same_surviving_enemy_target():
    source = MODLOADER.read_text()

    fallback = source[source.index("if seismic_flip_before ~= nil then"):]
    assert "not target:IsDead()" in fallback
    assert "target:GetTeam() == TEAM_ENEMY" in fallback
    assert "target_id == seismic_flip_before.id" in fallback
    assert "if unchanged then" in fallback
