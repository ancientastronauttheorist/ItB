/*
 * Build-keyed callback-campaign game-flow helper for the ITB Engine
 * Observatory.
 *
 * This DLL is not an input injector, memory editor, or general native bridge.
 * It exposes the two exact UI actions needed to run an unattended matched
 * callback trial: title-screen Continue and player End Turn.  A pair of exact
 * Breach.exe SDL frame-import slots provides a one-shot main-thread rendezvous
 * while the title object is being constructed.  Once the complete MainMenu and
 * its Button_MainContinue control are ready, the helper invokes the menu's own
 * reviewed key-action path to select and activate Continue.  Both frame slots
 * are restored before that action.  The DLL never synthesizes input or creates
 * a worker thread, and every action fails closed unless the pinned PE identity,
 * import slots, native routines, singleton chain, screen mode, control key, and
 * object vtables match the reviewed Windows build.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct lua_State lua_State;
typedef int (__cdecl *lua_CFunction)(lua_State *state);

typedef int (__cdecl *luaL_error_fn)(lua_State *, const char *, ...);
typedef void (__cdecl *lua_createtable_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_pushboolean_fn)(lua_State *, int);
typedef void (__cdecl *lua_pushcclosure_fn)(lua_State *, lua_CFunction, int);
typedef const char *(__cdecl *lua_pushstring_fn)(lua_State *, const char *);
typedef void (__cdecl *lua_setfield_fn)(lua_State *, int, const char *);

typedef void (__fastcall *title_key_action_fn)(
    void *menu,
    void *unused,
    int event_type,
    int event_code
);
typedef void (__fastcall *end_turn_action_fn)(void *battle_ui, void *unused);
typedef void (__cdecl *frame_present_fn)(void *object);

#define OBS_HELPER_VERSION "observatory-callback-gameflow-helper/6"
#define OBS_BUILD_ID "13725832"
#define OBS_EXECUTABLE_SHA256 \
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
#define OBS_ARCHITECTURE "x86"
#define OBS_HOST_GLOBAL_RVA_TEXT "0x004b9cf8"
#define OBS_GAME_APP_VTABLE_RVA_TEXT "0x00435014"
#define OBS_MENU_VTABLE_RVA_TEXT "0x0043597c"
#define OBS_MENU_BUTTON_VTABLE_RVA_TEXT "0x004358f4"
#define OBS_TITLE_KEY_ACTION_RVA_TEXT "0x0021c650"
#define OBS_TITLE_KEY_ACTION_REGION_SHA256 \
    "981a2a39bfcc7ae40d5aa7e4c049b3ad97877404807b979a938a0bf10bd0f481"
#define OBS_NEW_GAME_ACTION_RVA_TEXT "0x00217900"
#define OBS_NEW_GAME_ACTION_REGION_SHA256 \
    "4ae664238c4b6678a7c0c769c72d5850014e4cd5b8fdb2c6d034a16d2ee3eceb"
#define OBS_SCREEN_ROOT_VTABLE_RVA_TEXT "0x0043544c"
#define OBS_BATTLE_UI_VTABLE_RVA_TEXT "0x00430148"
#define OBS_END_TURN_ACTION_RVA_TEXT "0x00186b40"
#define OBS_END_TURN_ACTION_REGION_SHA256 \
    "3eff056cdd650e48c1c508f48da151d39bcd987afc1043257acc4d33bf1ea756"
#define OBS_SDL2_SHA256 \
    "cb7161fff576ab9a0288c14029bc98d138c3f660e764860dbd37640f06cb7f10"
#define OBS_RENDER_PRESENT_IAT_RVA_TEXT "0x003d6384"
#define OBS_GL_SWAP_IAT_RVA_TEXT "0x003d63b4"

#define OBS_PE_TIMESTAMP 0x65f16972u
#define OBS_PE_SIZE_OF_IMAGE 0x0056f000u
#define OBS_HOST_GLOBAL_RVA 0x004b9cf8u
#define OBS_GAME_APP_VTABLE_RVA 0x00435014u
#define OBS_MENU_OFFSET 0x0000002cu
#define OBS_MENU_VTABLE_RVA 0x0043597cu
#define OBS_MENU_SIZE 0x00012858u
#define OBS_MENU_BUTTON_VTABLE_RVA 0x004358f4u
#define OBS_MENU_KEY_ACTION_SLOT 0x0000002cu
#define OBS_TITLE_KEY_ACTION_RVA 0x0021c650u
#define OBS_TITLE_KEY_ACTION_SIZE 0x00000402u
#define OBS_CONTINUE_BUTTON_OFFSET 0x00000020u
#define OBS_CONTINUE_BUTTON_SIZE 0x00000144u
#define OBS_BUTTON_KEY_OFFSET 0x00000044u
#define OBS_BUTTON_ENABLED_OFFSET 0x00000080u
#define OBS_BUTTON_FADE_PROGRESS_OFFSET 0x00000100u
#define OBS_BUTTON_FADE_DURATION_OFFSET 0x00000108u
#define OBS_MENU_SELECTION_OFFSET 0x000013d4u
#define OBS_MENU_TRANSITION_FLAG_OFFSET 0x0000116cu
#define OBS_KEY_EVENT_TYPE 1
#define OBS_KEY_DOWN 0x14
#define OBS_KEY_ACTIVATE 0
#define OBS_NEW_GAME_ACTION_RVA 0x00217900u
#define OBS_NEW_GAME_ACTION_SIZE 0x0000011bu
#define OBS_GAME_APP_MINIMUM_SIZE 0x00000080u
#define OBS_SCREEN_ROOT_POINTER_OFFSET 0x00000010u
#define OBS_SCREEN_ROOT_VTABLE_RVA 0x0043544cu
#define OBS_SCREEN_ROOT_SIZE 0x0000c208u
#define OBS_ACTIVE_SCREEN_POINTER_OFFSET 0x0000c204u
#define OBS_BATTLE_UI_VTABLE_RVA 0x00430148u
#define OBS_BATTLE_UI_SIZE 0x000045ccu
#define OBS_END_TURN_BUTTON_OFFSET 0x0000015cu
#define OBS_END_TURN_BUTTON_VTABLE_RVA 0x00421ab0u
#define OBS_END_TURN_ACTION_RVA 0x00186b40u
#define OBS_END_TURN_ACTION_SIZE 0x000000deu
#define OBS_RENDER_PRESENT_IAT_RVA 0x003d6384u
#define OBS_GL_SWAP_IAT_RVA 0x003d63b4u
#define OBS_SDL2_PE_TIMESTAMP 0x5ddbfee9u
#define OBS_SDL2_SIZE_OF_IMAGE 0x000df000u
#define OBS_SDL2_RENDER_PRESENT_RVA 0x000118c0u
#define OBS_SDL2_RENDER_PRESENT_TARGET_RVA 0x000cf66cu
#define OBS_SDL2_GL_SWAP_RVA 0x0000fff0u
#define OBS_SDL2_GL_SWAP_TARGET_RVA 0x000cf9d0u
#define OBS_FRAME_HOOK_TIMEOUT_MS 30000u

static const unsigned char OBS_NEW_GAME_ACTION_BYTES[] = {
    0x55, 0x8b, 0xec, 0x6a, 0xff, 0x68, 0x78, 0x41, 0x7a, 0x00, 0x64, 0xa1,
    0x00, 0x00, 0x00, 0x00, 0x50, 0x83, 0xec, 0x0c, 0x56, 0xa1, 0x28, 0x3f,
    0x89, 0x00, 0x33, 0xc5, 0x50, 0x8d, 0x45, 0xf4, 0x64, 0xa3, 0x00, 0x00,
    0x00, 0x00, 0x8b, 0xf1, 0xe8, 0x23, 0x06, 0xec, 0xff, 0x83, 0xec, 0x18,
    0x8b, 0xcc, 0x89, 0x65, 0xf0, 0xc7, 0x41, 0x14, 0x0f, 0x00, 0x00, 0x00,
    0xc7, 0x41, 0x10, 0x00, 0x00, 0x00, 0x00, 0x83, 0x79, 0x14, 0x10, 0x72,
    0x04, 0x8b, 0x01, 0xeb, 0x02, 0x8b, 0xc1, 0x6a, 0x00, 0x68, 0xdc, 0xdf,
    0x80, 0x00, 0xc6, 0x00, 0x00, 0xe8, 0x72, 0x06, 0xdf, 0xff, 0x83, 0xec,
    0x18, 0xc7, 0x45, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x8b, 0xcc, 0xc7, 0x41,
    0x14, 0x0f, 0x00, 0x00, 0x00, 0xc7, 0x41, 0x10, 0x00, 0x00, 0x00, 0x00,
    0x83, 0x79, 0x14, 0x10, 0x72, 0x04, 0x8b, 0x01, 0xeb, 0x02, 0x8b, 0xc1,
    0x6a, 0x1a, 0x68, 0x60, 0x1a, 0x82, 0x00, 0xc6, 0x00, 0x00, 0xe8, 0x3d,
    0x06, 0xdf, 0xff, 0x83, 0xc9, 0xff, 0xc7, 0x45, 0xfc, 0xff, 0xff, 0xff,
    0xff, 0xe8, 0xce, 0x36, 0xec, 0xff, 0xc7, 0x86, 0x74, 0x11, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x8d, 0x96, 0x74, 0x11, 0x00, 0x00, 0x66, 0xc7,
    0x86, 0x79, 0x11, 0x00, 0x00, 0x00, 0x00, 0x8d, 0x4d, 0xf0, 0xc6, 0x86,
    0x78, 0x11, 0x00, 0x00, 0x01, 0x8d, 0x86, 0x7c, 0x11, 0x00, 0x00, 0xf3,
    0x0f, 0x10, 0x02, 0x83, 0xc4, 0x30, 0x0f, 0x57, 0xc9, 0xc7, 0x45, 0xf0,
    0x00, 0x00, 0x00, 0x00, 0x0f, 0x2f, 0xc1, 0xf3, 0x0f, 0x10, 0x00, 0x0f,
    0x47, 0xca, 0x0f, 0x2f, 0x01, 0x0f, 0x47, 0xc1, 0x8b, 0x00, 0x89, 0x02,
    0xc7, 0x86, 0x04, 0x0d, 0x00, 0x00, 0xcd, 0xcc, 0x4c, 0x3d, 0xc6, 0x86,
    0x6c, 0x11, 0x00, 0x00, 0x01, 0xc7, 0x86, 0xf4, 0x0c, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x8b, 0x4d, 0xf4, 0x64, 0x89, 0x0d, 0x00, 0x00, 0x00,
    0x00, 0x59, 0x5e, 0x8b, 0xe5, 0x5d, 0xc3,
};

typedef char observatory_new_game_action_size_must_match[
    sizeof(OBS_NEW_GAME_ACTION_BYTES) == OBS_NEW_GAME_ACTION_SIZE ? 1 : -1
];

typedef struct relocation_expectation {
    size_t offset;
    uint32_t target_rva;
} relocation_expectation;

static const relocation_expectation OBS_NEW_GAME_RELOCATIONS[] = {
    {6u, 0x003a4178u},
    {22u, 0x00493f28u},
    {82u, 0x0040dfdcu},
    {135u, 0x00421a60u},
};

/*
 * Pin the MainMenu key handler's entry and the complete navigation/activation
 * tail used below.  The build script separately attests the full 0x402-byte
 * function.  Runtime checks retain the two focused regions so an ASLR-loaded
 * process is rejected if either the calling convention or the exact
 * -1 -> 0 -> activate dispatch path differs.
 */
static const unsigned char OBS_TITLE_KEY_ENTRY_BYTES[] = {
    0x55, 0x8b, 0xec, 0x6a, 0xff, 0x68, 0x40, 0x55, 0x7c, 0x00, 0x64, 0xa1,
    0x00, 0x00, 0x00, 0x00, 0x50, 0x83, 0xec, 0x08, 0x53, 0x56, 0x57, 0xa1,
    0x28, 0x3f, 0x89, 0x00, 0x33, 0xc5, 0x50, 0x8d, 0x45, 0xf4, 0x64, 0xa3,
    0x00, 0x00, 0x00, 0x00,
};

static const relocation_expectation OBS_TITLE_KEY_ENTRY_RELOCATIONS[] = {
    {6u, 0x003c5540u},
    {24u, 0x00493f28u},
};

#define OBS_TITLE_KEY_TAIL_RVA 0x0021c985u
static const unsigned char OBS_TITLE_KEY_TAIL_BYTES[] = {
    0x8b, 0x5d, 0x0c, 0x85, 0xdb, 0x75, 0x07, 0x8b, 0xcf, 0xe8, 0x7d, 0xf8,
    0xff, 0xff, 0x8b, 0x87, 0xd4, 0x13, 0x00, 0x00, 0x8d, 0xb7, 0xd4, 0x13,
    0x00, 0x00, 0x89, 0x45, 0xec, 0xc7, 0x45, 0x08, 0x07, 0x00, 0x00, 0x00,
    0x0f, 0x1f, 0x80, 0x00, 0x00, 0x00, 0x00, 0x83, 0xfb, 0x14, 0x75, 0x04,
    0xff, 0x06, 0xeb, 0x07, 0x83, 0xfb, 0x13, 0x75, 0x02, 0xff, 0x0e, 0x8b,
    0x47, 0x20, 0x8d, 0x4f, 0x20, 0x8b, 0x40, 0x28, 0xff, 0xd0, 0x33, 0xc9,
    0x8d, 0x55, 0x0c, 0x84, 0xc0, 0x8d, 0x45, 0x08, 0x0f, 0x94, 0xc1, 0x3b,
    0x0e, 0x89, 0x4d, 0x0c, 0x0f, 0x4c, 0xd6, 0x83, 0x3a, 0x07, 0x0f, 0x4c,
    0xc2, 0x8b, 0x00, 0x89, 0x06, 0x85, 0xc0, 0x75, 0x0f, 0x8b, 0x47, 0x20,
    0x8d, 0x4f, 0x20, 0x8b, 0x40, 0x28, 0xff, 0xd0, 0x84, 0xc0, 0x74, 0xb3,
    0x8b, 0x45, 0xec, 0x3b, 0x06, 0x74, 0x3a, 0x83, 0xec, 0x18, 0x8b, 0xcc,
    0x89, 0x65, 0x0c, 0x68, 0xdc, 0xdf, 0x80, 0x00, 0xe8, 0xfa, 0xb3, 0xde,
    0xff, 0x83, 0xec, 0x18, 0xc7, 0x45, 0xfc, 0x01, 0x00, 0x00, 0x00, 0x8b,
    0xcc, 0x68, 0x1c, 0x19, 0x82, 0x00, 0xe8, 0xe4, 0xb3, 0xde, 0xff, 0x83,
    0xc9, 0xff, 0xc7, 0x45, 0xfc, 0xff, 0xff, 0xff, 0xff, 0xe8, 0x35, 0xe6,
    0xeb, 0xff, 0x83, 0xc4, 0x30, 0x8b, 0x4d, 0xf4, 0x64, 0x89, 0x0d, 0x00,
    0x00, 0x00, 0x00, 0x59, 0x5f, 0x5e, 0x5b, 0x8b, 0xe5, 0x5d, 0xc2, 0x08,
    0x00,
};

static const relocation_expectation OBS_TITLE_KEY_TAIL_RELOCATIONS[] = {
    {136u, 0x0040dfdcu},
    {158u, 0x0042191cu},
};

static const unsigned char OBS_END_TURN_ACTION_BYTES[] = {
    0x55, 0x8b, 0xec, 0x6a, 0xff, 0x68, 0x78, 0x41, 0x7a, 0x00, 0x64, 0xa1,
    0x00, 0x00, 0x00, 0x00, 0x50, 0x83, 0xec, 0x0c, 0x56, 0xa1, 0x28, 0x3f,
    0x89, 0x00, 0x33, 0xc5, 0x50, 0x8d, 0x45, 0xf4, 0x64, 0xa3, 0x00, 0x00,
    0x00, 0x00, 0x8b, 0xf1, 0xe8, 0x13, 0x85, 0x00, 0x00, 0x84, 0xc0, 0x0f,
    0x84, 0x82, 0x00, 0x00, 0x00, 0x83, 0xec, 0x18, 0x8b, 0xcc, 0x68, 0x90,
    0x1e, 0x82, 0x00, 0xe8, 0x8c, 0x12, 0xe8, 0xff, 0x33, 0xc9, 0xe8, 0xa5,
    0xd2, 0xf4, 0xff, 0x83, 0xc4, 0x18, 0x83, 0xf8, 0x01, 0x74, 0x64, 0x83,
    0xec, 0x18, 0x8b, 0xcc, 0x68, 0x7c, 0xf5, 0x82, 0x00, 0xe8, 0x6e, 0x12,
    0xe8, 0xff, 0x6a, 0x01, 0x6a, 0x01, 0x8d, 0x8e, 0x08, 0x10, 0x00, 0x00,
    0xe8, 0x6f, 0xd2, 0x02, 0x00, 0x83, 0xec, 0x18, 0xc7, 0x86, 0x58, 0x45,
    0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x8b, 0xcc, 0x89, 0x65, 0xf0, 0x68,
    0xdc, 0xdf, 0x80, 0x00, 0xe8, 0x43, 0x12, 0xe8, 0xff, 0x83, 0xec, 0x18,
    0xc7, 0x45, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x8b, 0xcc, 0x68, 0xb4, 0xf5,
    0x82, 0x00, 0xe8, 0x2d, 0x12, 0xe8, 0xff, 0x83, 0xc9, 0xff, 0xc7, 0x45,
    0xfc, 0xff, 0xff, 0xff, 0xff, 0xe8, 0x7e, 0x44, 0xf5, 0xff, 0x83, 0xc4,
    0x30, 0xeb, 0x10, 0x8b, 0xce, 0xe8, 0xa2, 0x87, 0x00, 0x00, 0x6a, 0x01,
    0x8b, 0xce, 0xe8, 0xb9, 0x36, 0x00, 0x00, 0x8b, 0xce, 0xe8, 0xb2, 0xe8,
    0x00, 0x00, 0x8b, 0x4d, 0xf4, 0x64, 0x89, 0x0d, 0x00, 0x00, 0x00, 0x00,
    0x59, 0x5e, 0x8b, 0xe5, 0x5d, 0xc3,
};

typedef char observatory_end_turn_action_size_must_match[
    sizeof(OBS_END_TURN_ACTION_BYTES) == OBS_END_TURN_ACTION_SIZE ? 1 : -1
];

static const relocation_expectation OBS_END_TURN_RELOCATIONS[] = {
    {6u, 0x003a4178u},
    {22u, 0x00493f28u},
    {59u, 0x00421e90u},
    {89u, 0x0042f57cu},
    {132u, 0x0040dfdcu},
    {154u, 0x0042f5b4u},
};

static luaL_error_fn g_luaL_error;
static lua_createtable_fn g_lua_createtable;
static lua_pushboolean_fn g_lua_pushboolean;
static lua_pushcclosure_fn g_lua_pushcclosure;
static lua_pushstring_fn g_lua_pushstring;
static lua_setfield_fn g_lua_setfield;
static volatile LONG g_continue_state;
static volatile LONG g_end_turn_invoked;
static DWORD g_continue_deadline;
static unsigned char *g_executable_base;
static frame_present_fn g_render_present_original;
static frame_present_fn g_gl_swap_original;

static int readable_range(const void *pointer, size_t size) {
    const unsigned char *cursor = (const unsigned char *)pointer;
    size_t remaining = size;

    if (pointer == NULL || size == 0u) {
        return 0;
    }
    while (remaining > 0u) {
        MEMORY_BASIC_INFORMATION info;
        SIZE_T queried = VirtualQuery(cursor, &info, sizeof(info));
        uintptr_t region_end;
        size_t available;

        if (queried != sizeof(info) || info.State != MEM_COMMIT ||
            (info.Protect & (PAGE_GUARD | PAGE_NOACCESS)) != 0u) {
            return 0;
        }
        region_end = (uintptr_t)info.BaseAddress + info.RegionSize;
        if (region_end <= (uintptr_t)cursor) {
            return 0;
        }
        available = (size_t)(region_end - (uintptr_t)cursor);
        if (available >= remaining) {
            return 1;
        }
        cursor += available;
        remaining -= available;
    }
    return 1;
}

static int validate_region_bytes(
    const unsigned char *base,
    uint32_t rva,
    const unsigned char *expected_bytes,
    size_t expected_size,
    const relocation_expectation *relocations,
    size_t relocation_count
) {
    const unsigned char *live = base + rva;
    size_t index = 0u;
    size_t relocation_index = 0u;

    while (index < expected_size) {
        if (relocation_index < relocation_count &&
            index == relocations[relocation_index].offset) {
            uint32_t observed = 0u;
            uint32_t expected = (uint32_t)(uintptr_t)base +
                relocations[relocation_index].target_rva;
            memcpy(&observed, live + index, sizeof(observed));
            if (observed != expected) {
                return 0;
            }
            index += sizeof(uint32_t);
            relocation_index += 1u;
        } else {
            if (live[index] != expected_bytes[index]) {
                return 0;
            }
            index += 1u;
        }
    }
    return relocation_index == relocation_count;
}

static int validate_new_game_bytes(const unsigned char *base) {
    return validate_region_bytes(
        base,
        OBS_NEW_GAME_ACTION_RVA,
        OBS_NEW_GAME_ACTION_BYTES,
        sizeof(OBS_NEW_GAME_ACTION_BYTES),
        OBS_NEW_GAME_RELOCATIONS,
        sizeof(OBS_NEW_GAME_RELOCATIONS) /
            sizeof(OBS_NEW_GAME_RELOCATIONS[0])
    );
}

static int validate_title_key_bytes(const unsigned char *base) {
    return validate_region_bytes(
        base,
        OBS_TITLE_KEY_ACTION_RVA,
        OBS_TITLE_KEY_ENTRY_BYTES,
        sizeof(OBS_TITLE_KEY_ENTRY_BYTES),
        OBS_TITLE_KEY_ENTRY_RELOCATIONS,
        sizeof(OBS_TITLE_KEY_ENTRY_RELOCATIONS) /
            sizeof(OBS_TITLE_KEY_ENTRY_RELOCATIONS[0])
    ) && validate_region_bytes(
        base,
        OBS_TITLE_KEY_TAIL_RVA,
        OBS_TITLE_KEY_TAIL_BYTES,
        sizeof(OBS_TITLE_KEY_TAIL_BYTES),
        OBS_TITLE_KEY_TAIL_RELOCATIONS,
        sizeof(OBS_TITLE_KEY_TAIL_RELOCATIONS) /
            sizeof(OBS_TITLE_KEY_TAIL_RELOCATIONS[0])
    );
}

static int validate_end_turn_bytes(const unsigned char *base) {
    return validate_region_bytes(
        base,
        OBS_END_TURN_ACTION_RVA,
        OBS_END_TURN_ACTION_BYTES,
        sizeof(OBS_END_TURN_ACTION_BYTES),
        OBS_END_TURN_RELOCATIONS,
        sizeof(OBS_END_TURN_RELOCATIONS) /
            sizeof(OBS_END_TURN_RELOCATIONS[0])
    );
}

static int validate_pinned_build(unsigned char **base_out) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;

    if (base == NULL) {
        return 0;
    }
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        (uint32_t)dos->e_lfanew > 0x00100000u) {
        return 0;
    }
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->FileHeader.TimeDateStamp != OBS_PE_TIMESTAMP ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage != OBS_PE_SIZE_OF_IMAGE ||
        OBS_TITLE_KEY_ACTION_RVA + OBS_TITLE_KEY_ACTION_SIZE >
            nt->OptionalHeader.SizeOfImage ||
        OBS_NEW_GAME_ACTION_RVA + OBS_NEW_GAME_ACTION_SIZE >
            nt->OptionalHeader.SizeOfImage ||
        OBS_END_TURN_ACTION_RVA + OBS_END_TURN_ACTION_SIZE >
            nt->OptionalHeader.SizeOfImage ||
        !validate_title_key_bytes(base) ||
        !validate_new_game_bytes(base) ||
        !validate_end_turn_bytes(base)) {
        return 0;
    }
    *base_out = base;
    return 1;
}

static int pinned_string_equals(
    unsigned char *owner,
    size_t offset,
    const char *expected
) {
    unsigned char *field = owner + offset;
    uint32_t size = 0u;
    uint32_t capacity = 0u;
    char *data;
    size_t expected_size = strlen(expected);

    if (!readable_range(field, 24u)) {
        return 0;
    }
    memcpy(&size, field + 16u, sizeof(size));
    memcpy(&capacity, field + 20u, sizeof(capacity));
    if (size != expected_size || capacity < size || capacity > 0x00001000u) {
        return 0;
    }
    if (capacity < 16u) {
        data = (char *)field;
    } else {
        memcpy(&data, field, sizeof(data));
    }
    return readable_range(data, expected_size + 1u) &&
        memcmp(data, expected, expected_size) == 0 &&
        data[expected_size] == '\0';
}

static int find_ready_title_menu(
    unsigned char *base,
    unsigned char **menu_out
) {
    static const size_t blocked_flag_offsets[] = {
        0x0000bd68u,
        0x000106dcu,
        0x000011c5u,
        0x000017c4u,
        0x0000bdf8u,
        0x0000de80u,
        0x00006748u,
        0x0000aae8u,
        0x000011c4u,
        OBS_MENU_TRANSITION_FLAG_OFFSET,
    };
    void *host;
    unsigned char *game_app;
    unsigned char *menu;
    unsigned char *continue_button;
    uintptr_t menu_vtable;
    uintptr_t key_action;
    int32_t selection;
    int32_t width;
    int32_t height;
    float fade_progress;
    float fade_duration;
    size_t index;

    memcpy(&host, base + OBS_HOST_GLOBAL_RVA, sizeof(host));
    if (!readable_range(host, 0x1cu)) {
        return 0;
    }
    memcpy(&game_app, (unsigned char *)host + 0x18u, sizeof(game_app));
    if (!readable_range(game_app, OBS_MENU_OFFSET + OBS_MENU_SIZE) ||
        *(uintptr_t *)game_app !=
            (uintptr_t)(base + OBS_GAME_APP_VTABLE_RVA)) {
        return 0;
    }
    menu = game_app + OBS_MENU_OFFSET;
    memcpy(&menu_vtable, menu, sizeof(menu_vtable));
    if (menu_vtable != (uintptr_t)(base + OBS_MENU_VTABLE_RVA) ||
        !readable_range((const void *)menu_vtable, OBS_MENU_KEY_ACTION_SLOT + 4u)) {
        return 0;
    }
    memcpy(
        &key_action,
        (const void *)(menu_vtable + OBS_MENU_KEY_ACTION_SLOT),
        sizeof(key_action)
    );
    if (key_action != (uintptr_t)(base + OBS_TITLE_KEY_ACTION_RVA)) {
        return 0;
    }
    continue_button = menu + OBS_CONTINUE_BUTTON_OFFSET;
    if (!readable_range(continue_button, OBS_CONTINUE_BUTTON_SIZE) ||
        *(uintptr_t *)continue_button !=
            (uintptr_t)(base + OBS_MENU_BUTTON_VTABLE_RVA) ||
        *(unsigned char *)(continue_button + OBS_BUTTON_ENABLED_OFFSET) != 1u ||
        !pinned_string_equals(
            continue_button,
            OBS_BUTTON_KEY_OFFSET,
            "Button_MainContinue"
        )) {
        return 0;
    }
    memcpy(&width, continue_button + 0x3cu, sizeof(width));
    memcpy(&height, continue_button + 0x40u, sizeof(height));
    memcpy(
        &fade_progress,
        continue_button + OBS_BUTTON_FADE_PROGRESS_OFFSET,
        sizeof(fade_progress)
    );
    memcpy(
        &fade_duration,
        continue_button + OBS_BUTTON_FADE_DURATION_OFFSET,
        sizeof(fade_duration)
    );
    memcpy(&selection, menu + OBS_MENU_SELECTION_OFFSET, sizeof(selection));
    if (width <= 0 || height <= 0 || selection != -1 ||
        !(fade_duration > 0.0f) || !(fade_progress >= fade_duration)) {
        return 0;
    }
    for (index = 0u;
         index < sizeof(blocked_flag_offsets) / sizeof(blocked_flag_offsets[0]);
         index += 1u) {
        if (*(unsigned char *)(menu + blocked_flag_offsets[index]) != 0u) {
            return 0;
        }
    }
    if (*(uintptr_t *)continue_button !=
            (uintptr_t)(base + OBS_MENU_BUTTON_VTABLE_RVA)) {
        return 0;
    }
    *menu_out = menu;
    return 1;
}

static int invoke_title_continue(unsigned char *base, unsigned char *menu) {
    uintptr_t menu_vtable;
    uintptr_t key_action_pointer;
    title_key_action_fn key_action;
    int32_t selection;

    memcpy(&menu_vtable, menu, sizeof(menu_vtable));
    memcpy(
        &key_action_pointer,
        (const void *)(menu_vtable + OBS_MENU_KEY_ACTION_SLOT),
        sizeof(key_action_pointer)
    );
    if (key_action_pointer != (uintptr_t)(base + OBS_TITLE_KEY_ACTION_RVA)) {
        return 0;
    }
    key_action = (title_key_action_fn)key_action_pointer;
    key_action(menu, NULL, OBS_KEY_EVENT_TYPE, OBS_KEY_DOWN);
    memcpy(&selection, menu + OBS_MENU_SELECTION_OFFSET, sizeof(selection));
    if (selection != 0) {
        return 0;
    }
    key_action(menu, NULL, OBS_KEY_EVENT_TYPE, OBS_KEY_ACTIVATE);
    return 1;
}

static int validate_sdl_stub(
    const unsigned char *base,
    uint32_t export_rva,
    uint32_t target_rva
) {
    const unsigned char *stub = base + export_rva;
    uint32_t relocated_target = 0u;
    size_t index;

    if (!readable_range(stub, 16u) || stub[0] != 0xffu ||
        stub[1] != 0x25u) {
        return 0;
    }
    memcpy(&relocated_target, stub + 2u, sizeof(relocated_target));
    if (relocated_target != (uint32_t)(uintptr_t)(base + target_rva)) {
        return 0;
    }
    for (index = 6u; index < 16u; index += 1u) {
        if (stub[index] != 0xccu) {
            return 0;
        }
    }
    return 1;
}

static int validate_pinned_sdl2(
    unsigned char **base_out,
    frame_present_fn *render_present_out,
    frame_present_fn *gl_swap_out
) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(L"SDL2.dll");
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    FARPROC render_present;
    FARPROC gl_swap;

    if (base == NULL || !readable_range(base, sizeof(IMAGE_DOS_HEADER))) {
        return 0;
    }
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        (uint32_t)dos->e_lfanew > 0x00100000u) {
        return 0;
    }
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    if (!readable_range(nt, sizeof(IMAGE_NT_HEADERS32)) ||
        nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->FileHeader.TimeDateStamp != OBS_SDL2_PE_TIMESTAMP ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage != OBS_SDL2_SIZE_OF_IMAGE ||
        !validate_sdl_stub(
            base,
            OBS_SDL2_RENDER_PRESENT_RVA,
            OBS_SDL2_RENDER_PRESENT_TARGET_RVA
        ) ||
        !validate_sdl_stub(
            base,
            OBS_SDL2_GL_SWAP_RVA,
            OBS_SDL2_GL_SWAP_TARGET_RVA
        )) {
        return 0;
    }
    render_present = GetProcAddress((HMODULE)base, "SDL_RenderPresent");
    gl_swap = GetProcAddress((HMODULE)base, "SDL_GL_SwapWindow");
    if (render_present != (FARPROC)(base + OBS_SDL2_RENDER_PRESENT_RVA) ||
        gl_swap != (FARPROC)(base + OBS_SDL2_GL_SWAP_RVA)) {
        return 0;
    }
    *base_out = base;
    *render_present_out = (frame_present_fn)render_present;
    *gl_swap_out = (frame_present_fn)gl_swap;
    return 1;
}

static PVOID read_iat_pointer(PVOID volatile *slot) {
    PVOID value = NULL;

    /* The pinned IAT page is read-only until exchange_iat_pointer opens it. */
    memcpy(&value, (const void *)slot, sizeof(value));
    return value;
}

static int exchange_iat_pointer(
    PVOID volatile *slot,
    PVOID expected,
    PVOID replacement
) {
    DWORD old_protection = 0u;
    DWORD discarded_protection = 0u;
    PVOID observed;
    BOOL protection_restored;

    if (!readable_range((const void *)slot, sizeof(PVOID)) ||
        read_iat_pointer(slot) != expected ||
        !VirtualProtect(
            (LPVOID)slot,
            sizeof(PVOID),
            PAGE_READWRITE,
            &old_protection
        )) {
        return 0;
    }
    observed = InterlockedCompareExchangePointer(slot, replacement, expected);
    protection_restored = VirtualProtect(
        (LPVOID)slot,
        sizeof(PVOID),
        old_protection,
        &discarded_protection
    );
    return observed == expected && protection_restored;
}

static void __cdecl observatory_render_present(void *renderer);
static void __cdecl observatory_gl_swap(void *window);

static int restore_one_frame_hook(
    PVOID volatile *slot,
    PVOID hook,
    PVOID original
) {
    PVOID current = read_iat_pointer(slot);

    if (current == original) {
        return 1;
    }
    if (current != hook) {
        return 0;
    }
    return exchange_iat_pointer(slot, hook, original);
}

static int restore_frame_hooks(void) {
    PVOID volatile *render_slot;
    PVOID volatile *gl_slot;
    int render_ok;
    int gl_ok;

    if (g_executable_base == NULL || g_render_present_original == NULL ||
        g_gl_swap_original == NULL) {
        return 0;
    }
    render_slot = (PVOID volatile *)(
        g_executable_base + OBS_RENDER_PRESENT_IAT_RVA
    );
    gl_slot = (PVOID volatile *)(
        g_executable_base + OBS_GL_SWAP_IAT_RVA
    );
    render_ok = restore_one_frame_hook(
        render_slot,
        (PVOID)observatory_render_present,
        (PVOID)g_render_present_original
    );
    gl_ok = restore_one_frame_hook(
        gl_slot,
        (PVOID)observatory_gl_swap,
        (PVOID)g_gl_swap_original
    );
    return render_ok && gl_ok;
}

static int install_frame_hooks(
    unsigned char *executable_base,
    frame_present_fn render_present,
    frame_present_fn gl_swap
) {
    PVOID volatile *render_slot = (PVOID volatile *)(
        executable_base + OBS_RENDER_PRESENT_IAT_RVA
    );
    PVOID volatile *gl_slot = (PVOID volatile *)(
        executable_base + OBS_GL_SWAP_IAT_RVA
    );

    if (read_iat_pointer(render_slot) != (PVOID)render_present ||
        read_iat_pointer(gl_slot) != (PVOID)gl_swap) {
        return 0;
    }
    g_executable_base = executable_base;
    g_render_present_original = render_present;
    g_gl_swap_original = gl_swap;
    g_continue_deadline = GetTickCount() + OBS_FRAME_HOOK_TIMEOUT_MS;
    if (!exchange_iat_pointer(
            render_slot,
            (PVOID)render_present,
            (PVOID)observatory_render_present
        )) {
        return 0;
    }
    if (!exchange_iat_pointer(
            gl_slot,
            (PVOID)gl_swap,
            (PVOID)observatory_gl_swap
        )) {
        restore_one_frame_hook(
            render_slot,
            (PVOID)observatory_render_present,
            (PVOID)render_present
        );
        return 0;
    }
    return 1;
}

static void try_continue_on_frame(void) {
    LONG state_value = InterlockedCompareExchange(&g_continue_state, 0, 0);
    unsigned char *menu = NULL;

    if (state_value == 3) {
        restore_frame_hooks();
        return;
    }
    if (state_value != 1) {
        return;
    }
    if ((LONG)(GetTickCount() - g_continue_deadline) >= 0) {
        if (InterlockedCompareExchange(&g_continue_state, 3, 1) == 1) {
            restore_frame_hooks();
        }
        return;
    }
    if (!find_ready_title_menu(g_executable_base, &menu) ||
        InterlockedCompareExchange(&g_continue_state, 4, 1) != 1) {
        return;
    }
    if (!restore_frame_hooks()) {
        InterlockedExchange(&g_continue_state, 3);
        return;
    }
    if (!invoke_title_continue(g_executable_base, menu)) {
        InterlockedExchange(&g_continue_state, 3);
        return;
    }
    InterlockedExchange(&g_continue_state, 2);
}

static void __cdecl observatory_render_present(void *renderer) {
    try_continue_on_frame();
    g_render_present_original(renderer);
}

static void __cdecl observatory_gl_swap(void *window) {
    try_continue_on_frame();
    g_gl_swap_original(window);
}

static int continue_saved_timeline(lua_State *state) {
    unsigned char *base = NULL;
    unsigned char *sdl_base = NULL;
    frame_present_fn render_present = NULL;
    frame_present_fn gl_swap = NULL;

    if (!validate_pinned_build(&base) ||
        !validate_pinned_sdl2(&sdl_base, &render_present, &gl_swap)) {
        return g_luaL_error(state, "pinned Breach.exe Continue identity mismatch");
    }
    (void)sdl_base;
    if (InterlockedCompareExchange(&g_continue_state, 4, 0) != 0) {
        return g_luaL_error(state, "title Continue bootstrap is already consumed");
    }
    if (!install_frame_hooks(base, render_present, gl_swap)) {
        restore_frame_hooks();
        InterlockedExchange(&g_continue_state, 3);
        return g_luaL_error(state, "title Continue frame hook installation failed");
    }
    InterlockedExchange(&g_continue_state, 1);
    g_lua_pushboolean(state, 1);
    return 1;
}

static int continue_status(lua_State *state) {
    LONG value = InterlockedCompareExchange(&g_continue_state, 0, 0);
    const char *status = "not_started";

    if (value == 1) {
        status = "pending";
    } else if (value == 2) {
        status = "invoked";
    } else if (value == 3) {
        status = "failed";
    } else if (value == 4) {
        status = "invoking";
    }
    g_lua_pushstring(state, status);
    return 1;
}

static int end_player_turn(lua_State *state) {
    unsigned char *base = NULL;
    void *host;
    unsigned char *game_app;
    unsigned char *screen_root;
    unsigned char *battle_ui;
    end_turn_action_fn action;

    if (!validate_pinned_build(&base)) {
        return g_luaL_error(state, "pinned Breach.exe game-flow identity mismatch");
    }
    memcpy(&host, base + OBS_HOST_GLOBAL_RVA, sizeof(host));
    if (!readable_range(host, 0x1cu)) {
        return g_luaL_error(state, "battle host singleton is unavailable");
    }
    memcpy(&game_app, (unsigned char *)host + 0x18u, sizeof(game_app));
    if (!readable_range(game_app, OBS_GAME_APP_MINIMUM_SIZE) ||
        *(uintptr_t *)game_app !=
            (uintptr_t)(base + OBS_GAME_APP_VTABLE_RVA)) {
        return g_luaL_error(state, "battle game object identity mismatch");
    }
    memcpy(
        &screen_root,
        game_app + OBS_SCREEN_ROOT_POINTER_OFFSET,
        sizeof(screen_root)
    );
    if (!readable_range(screen_root, OBS_SCREEN_ROOT_SIZE) ||
        *(uintptr_t *)screen_root !=
            (uintptr_t)(base + OBS_SCREEN_ROOT_VTABLE_RVA)) {
        return g_luaL_error(state, "battle screen registry identity mismatch");
    }
    memcpy(
        &battle_ui,
        screen_root + OBS_ACTIVE_SCREEN_POINTER_OFFSET,
        sizeof(battle_ui)
    );
    if (!readable_range(battle_ui, OBS_BATTLE_UI_SIZE) ||
        *(uintptr_t *)battle_ui !=
            (uintptr_t)(base + OBS_BATTLE_UI_VTABLE_RVA) ||
        *(uintptr_t *)(battle_ui + OBS_END_TURN_BUTTON_OFFSET) !=
            (uintptr_t)(base + OBS_END_TURN_BUTTON_VTABLE_RVA)) {
        return g_luaL_error(state, "battle UI identity mismatch");
    }
    if (*(int32_t *)(battle_ui + 0x0fc8u) != 0 ||
        *(unsigned char *)(battle_ui + 0x170cu) != 0) {
        return g_luaL_error(state, "player End Turn is blocked by battle UI state");
    }
    if (InterlockedCompareExchange(&g_end_turn_invoked, 1, 0) != 0) {
        return g_luaL_error(state, "player End Turn helper is already consumed");
    }
    action = (end_turn_action_fn)(base + OBS_END_TURN_ACTION_RVA);
    action(battle_ui, NULL);
    g_lua_pushboolean(state, 1);
    return 1;
}

static FARPROC require_lua(HMODULE module, const char *name) {
    return module == NULL ? NULL : GetProcAddress(module, name);
}

static int resolve_lua_api(void) {
    HMODULE lua = GetModuleHandleA("lua5.1.dll");
    g_luaL_error = (luaL_error_fn)require_lua(lua, "luaL_error");
    g_lua_createtable =
        (lua_createtable_fn)require_lua(lua, "lua_createtable");
    g_lua_pushboolean =
        (lua_pushboolean_fn)require_lua(lua, "lua_pushboolean");
    g_lua_pushcclosure =
        (lua_pushcclosure_fn)require_lua(lua, "lua_pushcclosure");
    g_lua_pushstring =
        (lua_pushstring_fn)require_lua(lua, "lua_pushstring");
    g_lua_setfield = (lua_setfield_fn)require_lua(lua, "lua_setfield");
    return g_luaL_error != NULL && g_lua_createtable != NULL &&
        g_lua_pushboolean != NULL && g_lua_pushcclosure != NULL &&
        g_lua_pushstring != NULL && g_lua_setfield != NULL;
}

static void set_string(lua_State *state, const char *key, const char *value) {
    g_lua_pushstring(state, value);
    g_lua_setfield(state, -2, key);
}

__declspec(dllexport) int __cdecl luaopen_itb_observatory_continue(
    lua_State *state) {
    unsigned char *base = NULL;
    unsigned char *sdl_base = NULL;
    frame_present_fn render_present = NULL;
    frame_present_fn gl_swap = NULL;

    if (!resolve_lua_api()) {
        return 0;
    }
    if (!validate_pinned_build(&base) ||
        !validate_pinned_sdl2(&sdl_base, &render_present, &gl_swap)) {
        return g_luaL_error(state, "pinned Breach.exe game-flow identity mismatch");
    }
    (void)sdl_base;
    (void)render_present;
    (void)gl_swap;
    g_lua_createtable(state, 0, 21);
    set_string(state, "VERSION", OBS_HELPER_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", OBS_ARCHITECTURE);
    set_string(state, "HOST_GLOBAL_RVA", OBS_HOST_GLOBAL_RVA_TEXT);
    set_string(state, "GAME_APP_VTABLE_RVA", OBS_GAME_APP_VTABLE_RVA_TEXT);
    set_string(state, "MENU_VTABLE_RVA", OBS_MENU_VTABLE_RVA_TEXT);
    set_string(
        state,
        "MENU_BUTTON_VTABLE_RVA",
        OBS_MENU_BUTTON_VTABLE_RVA_TEXT
    );
    set_string(state, "TITLE_KEY_ACTION_RVA", OBS_TITLE_KEY_ACTION_RVA_TEXT);
    set_string(
        state,
        "TITLE_KEY_ACTION_REGION_SHA256",
        OBS_TITLE_KEY_ACTION_REGION_SHA256
    );
    set_string(state, "NEW_GAME_ACTION_RVA", OBS_NEW_GAME_ACTION_RVA_TEXT);
    set_string(
        state,
        "NEW_GAME_ACTION_REGION_SHA256",
        OBS_NEW_GAME_ACTION_REGION_SHA256
    );
    set_string(
        state,
        "SCREEN_ROOT_VTABLE_RVA",
        OBS_SCREEN_ROOT_VTABLE_RVA_TEXT
    );
    set_string(state, "BATTLE_UI_VTABLE_RVA", OBS_BATTLE_UI_VTABLE_RVA_TEXT);
    set_string(state, "END_TURN_ACTION_RVA", OBS_END_TURN_ACTION_RVA_TEXT);
    set_string(
        state,
        "END_TURN_ACTION_REGION_SHA256",
        OBS_END_TURN_ACTION_REGION_SHA256
    );
    set_string(state, "SDL2_SHA256", OBS_SDL2_SHA256);
    set_string(
        state,
        "RENDER_PRESENT_IAT_RVA",
        OBS_RENDER_PRESENT_IAT_RVA_TEXT
    );
    set_string(state, "GL_SWAP_IAT_RVA", OBS_GL_SWAP_IAT_RVA_TEXT);
    g_lua_pushcclosure(state, continue_saved_timeline, 0);
    g_lua_setfield(state, -2, "continue_saved_timeline");
    g_lua_pushcclosure(state, continue_status, 0);
    g_lua_setfield(state, -2, "continue_status");
    g_lua_pushcclosure(state, end_player_turn, 0);
    g_lua_setfield(state, -2, "end_player_turn");
    return 1;
}
