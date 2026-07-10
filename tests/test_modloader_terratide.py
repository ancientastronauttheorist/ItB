from pathlib import Path


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def test_terratide_overrides_inherited_tides_before_class_detection():
    source = MODLOADER.read_text()

    start = source.index('if mission_id == "Mission_Terratide" then')
    end = source.index("\n        end", start)
    branch = source[start:end]

    assert 'env_type = "sandstorm"' in branch
    assert "env_kill_default = false" in branch
    assert "env_flying_immune_default = false" in branch
    assert "return" in branch
    assert start < source.index("local mt = getmetatable(le)")
    assert start < source.index("elseif le.Index ~= nil")
