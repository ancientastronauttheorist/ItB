"""Finite shared synthetic Lua dispatch layout for native helper composition."""

from __future__ import annotations

BASE, IMPORT = 0x00400000, 0x05000000
HEAP_SLOT, HEAP_TARGET = 0x003D6220, IMPORT
SLOTS = {
    "lua_equal": 0x3D64C4,
    "lua_getmetatable": 0x3D6534,
    "lua_gettable": 0x3D64BC,
    "lua_insert": 0x3D6514,
    "lua_next": 0x3D64B4,
    "lua_pushnil": 0x3D64B8,
    "lua_pushstring": 0x3D6494,
    "lua_pushvalue": 0x3D64E4,
    "lua_rawgeti": 0x3D64C0,
    "lua_settable": 0x3D6550,
    "lua_settop": 0x3D6510,
    "lua_toboolean": 0x3D64F8,
    "lua_touserdata": 0x3D649C,
}
TARGETS = {name: IMPORT + 0x100 * (i + 1) for i, name in enumerate(sorted(SLOTS))}
LITERALS = {
    BASE + 0x420F68: b"__init\0",
    BASE + 0x43C50C: b"__finalize\0",
    BASE + 0x43C738: b"__luabind_classrep\0",
}
IAT_PAGE = (BASE + HEAP_SLOT) & ~0xFFF
SHARED_PAGES = frozenset({IAT_PAGE, *{a & ~0xFFF for a in LITERALS}})


class LayoutError(RuntimeError):
    """The supplied synthetic dispatch contract is stale or malformed."""


def _require(ok, message):
    if not ok:
        raise LayoutError(message)


def validate_targets_and_pages(targets, pages):
    _require(
        type(targets) is dict
        and set(targets) == set(TARGETS)
        and all(type(v) is int and 0 <= v < 2**32 for v in targets.values())
        and targets == TARGETS,
        "shared Lua target mapping differs",
    )
    _require(
        type(pages) is dict
        and SHARED_PAGES.issubset(pages)
        and all(
            type(pages[p]) is bytes and len(pages[p]) == 4096 for p in SHARED_PAGES
        ),
        "shared Lua pages differ",
    )

    def raw(address, width=4):
        return bytes(
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] for i in range(width)
        )

    _require(
        all(
            int.from_bytes(raw(BASE + slot), "little") == targets[name]
            for name, slot in SLOTS.items()
        ),
        "shared Lua IAT binding differs",
    )
    _require(
        int.from_bytes(raw(BASE + HEAP_SLOT), "little") == HEAP_TARGET,
        "shared HeapAlloc binding differs",
    )
    _require(
        all(raw(address, len(value)) == value for address, value in LITERALS.items()),
        "shared Lua literal differs",
    )
    return dict(targets)


def validate_layout(layout):
    _require(
        type(layout) is dict and set(layout) == {"targets", "pages"},
        "invalid shared Lua layout fields",
    )
    _require(
        type(layout["pages"]) is dict and set(layout["pages"]) == SHARED_PAGES,
        "shared Lua page partition differs",
    )
    validate_targets_and_pages(layout["targets"], layout["pages"])
    return {"targets": dict(layout["targets"]), "pages": dict(layout["pages"])}


def make_layout():
    pages = {
        page: bytearray((i * 17 + (page >> 12) + 0xA3) % 256 for i in range(4096))
        for page in sorted(SHARED_PAGES)
    }

    def put(address, value):
        for i, byte in enumerate(value):
            pages[(address + i) & ~0xFFF][(address + i) & 0xFFF] = byte

    for name, slot in SLOTS.items():
        put(BASE + slot, TARGETS[name].to_bytes(4, "little"))
    put(BASE + HEAP_SLOT, HEAP_TARGET.to_bytes(4, "little"))
    for address, value in LITERALS.items():
        put(address, value)
    return validate_layout(
        {"targets": dict(TARGETS), "pages": {p: bytes(v) for p, v in pages.items()}}
    )


def install_layout(fixture, layout):
    checked = validate_layout(layout)
    return dict(
        fixture,
        pages={**fixture["pages"], **checked["pages"]},
        api_targets=checked["targets"],
    )
