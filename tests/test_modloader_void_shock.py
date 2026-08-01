from pathlib import Path


MODLOADER = (
    Path(__file__).resolve().parents[1] / "src" / "bridge" / "modloader.lua"
)


def test_modloader_exports_source_defined_void_shock_immunity():
    source = MODLOADER.read_text(encoding="utf-8")

    assert (
        "void_shock_immune = pawn_def and pawn_def.VoidShockImmune or false"
        in source
    )
