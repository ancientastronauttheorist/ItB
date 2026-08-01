from pathlib import Path


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def test_control_shot_state_export_uses_live_predicates_separately():
    source = MODLOADER.read_text(encoding="utf-8")

    assert "pcall(function() return p:GetBaseMove() end)" in source
    assert "base_move = live_base_move" in source
    assert "pcall(function() return p:IsPowered() end)" in source
    assert "unit.powered = powered" in source
    assert "pcall(function() return p:IsBurrower() end)" in source
    assert "unit.burrower = burrower" in source
    assert "pcall(function() return p:IsJumper() end)" in source
    assert "unit.jumper = jumper" in source

    grapple_probe = '"IsGrappled", "IsWebbed", "IsWeb", "IsPinned",'
    assert grapple_probe in source
    assert "unit.web = web" in source
    assert "unit.grappled = web_probes.IsGrappled" in source
    assert source.index("unit.web = web") < source.index(
        "unit.grappled = web_probes.IsGrappled"
    )


def test_control_shot_execution_validates_native_target_areas_before_effect():
    source = MODLOADER.read_text(encoding="utf-8")
    start = source.index('if string.find(wname, "^Science_TC_Control") ~= nil then')
    end = source.index('if wname == "Ranged_DeployBomb_A" then', start)
    control = source[start:end]

    first_area = "skill:GetTargetArea(source)"
    first_membership = "point_list_contains(first_targets, first)"
    second_area = "skill:GetSecondTargetArea(source, first)"
    second_membership = "point_list_contains(second_targets, second)"
    final_effect = "Board:AddEffect(skill:GetFinalEffect(source, first, second))"

    assert all(
        snippet in control
        for snippet in (
            first_area,
            first_membership,
            second_area,
            second_membership,
            final_effect,
        )
    )
    assert (
        control.index(first_area)
        < control.index(first_membership)
        < control.index(second_area)
        < control.index(second_membership)
        < control.index(final_effect)
    )
