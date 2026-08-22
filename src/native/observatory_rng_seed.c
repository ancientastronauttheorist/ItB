/*
 * Build-keyed, one-purpose RNG seed helper for the ITB Engine Observatory.
 *
 * This DLL is intentionally not a memory editor or a general native bridge.
 * It exposes one Lua function which calls the already-reviewed seed setter in
 * one exact 32-bit Breach.exe build.  Both module load and every seed request
 * fail closed unless the live PE header and the complete reviewed RNG-core and
 * seed-setter byte regions match the pinned build.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stddef.h>
#include <stdint.h>
#include <string.h>

typedef struct lua_State lua_State;
typedef int (__cdecl *lua_CFunction)(lua_State *state);
typedef ptrdiff_t lua_Integer;

typedef lua_Integer (__cdecl *luaL_checkinteger_fn)(lua_State *, int);
typedef int (__cdecl *luaL_error_fn)(lua_State *, const char *, ...);
typedef void (__cdecl *lua_createtable_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_pushboolean_fn)(lua_State *, int);
typedef void (__cdecl *lua_pushcclosure_fn)(lua_State *, lua_CFunction, int);
typedef void (__cdecl *lua_pushinteger_fn)(lua_State *, lua_Integer);
typedef const char *(__cdecl *lua_pushstring_fn)(lua_State *, const char *);
typedef void (__cdecl *lua_setfield_fn)(lua_State *, int, const char *);

typedef void (__cdecl *rng_seed_fn)(uint32_t seed);

#define OBS_HELPER_VERSION "observatory-rng-seed-helper/1"
#define OBS_BUILD_ID "13725832"
#define OBS_EXECUTABLE_SHA256 \
    "31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9"
#define OBS_ARCHITECTURE "x86"
#define OBS_RNG_SEED_RVA_TEXT "0x00387f37"
#define OBS_RNG_SEED_REGION_SHA256 \
    "67b19fe39627674ef04d07bd86e989a39ce744be2e93f9265c16e2aeb928cf9d"

#define OBS_PE_TIMESTAMP 0x65f16972u
#define OBS_PE_SIZE_OF_IMAGE 0x0056f000u
#define OBS_RNG_CORE_RVA 0x00387f16u
#define OBS_RNG_SEED_RVA 0x00387f37u

static const unsigned char OBS_RNG_CORE_BYTES[] = {
    0xe8, 0x17, 0x6e, 0x00, 0x00, 0x69, 0x48, 0x18, 0xfd, 0x43, 0x03,
    0x00, 0x81, 0xc1, 0xc3, 0x9e, 0x26, 0x00, 0x89, 0x48, 0x18, 0xc1,
    0xe9, 0x10, 0x81, 0xe1, 0xff, 0x7f, 0x00, 0x00, 0x8b, 0xc1, 0xc3,
};

static const unsigned char OBS_RNG_SEED_BYTES[] = {
    0x8b, 0xff, 0x55, 0x8b, 0xec, 0xe8, 0xf1, 0x6d, 0x00,
    0x00, 0x8b, 0x4d, 0x08, 0x89, 0x48, 0x18, 0x5d, 0xc3,
};

static luaL_checkinteger_fn g_luaL_checkinteger;
static luaL_error_fn g_luaL_error;
static lua_createtable_fn g_lua_createtable;
static lua_pushboolean_fn g_lua_pushboolean;
static lua_pushcclosure_fn g_lua_pushcclosure;
static lua_pushinteger_fn g_lua_pushinteger;
static lua_pushstring_fn g_lua_pushstring;
static lua_setfield_fn g_lua_setfield;

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
        nt->OptionalHeader.SizeOfImage != OBS_PE_SIZE_OF_IMAGE) {
        return 0;
    }
    if (OBS_RNG_CORE_RVA + sizeof(OBS_RNG_CORE_BYTES) >
            nt->OptionalHeader.SizeOfImage ||
        OBS_RNG_SEED_RVA + sizeof(OBS_RNG_SEED_BYTES) >
            nt->OptionalHeader.SizeOfImage ||
        memcmp(base + OBS_RNG_CORE_RVA, OBS_RNG_CORE_BYTES,
               sizeof(OBS_RNG_CORE_BYTES)) != 0 ||
        memcmp(base + OBS_RNG_SEED_RVA, OBS_RNG_SEED_BYTES,
               sizeof(OBS_RNG_SEED_BYTES)) != 0) {
        return 0;
    }
    *base_out = base;
    return 1;
}

static int seed_rng(lua_State *state) {
    unsigned char *base = NULL;
    lua_Integer requested = g_luaL_checkinteger(state, 1);
    rng_seed_fn seed;

    if (requested < 0 || (uint64_t)requested > 0x7fffffffu) {
        return g_luaL_error(state, "native RNG seed must be 0..2147483647");
    }
    if (!validate_pinned_build(&base)) {
        return g_luaL_error(state, "pinned Breach.exe RNG identity mismatch");
    }
    seed = (rng_seed_fn)(base + OBS_RNG_SEED_RVA);
    seed((uint32_t)requested);
    g_lua_pushboolean(state, 1);
    return 1;
}

static FARPROC require_lua(HMODULE module, const char *name) {
    return module == NULL ? NULL : GetProcAddress(module, name);
}

static int resolve_lua_api(void) {
    HMODULE lua = GetModuleHandleA("lua5.1.dll");
    g_luaL_checkinteger = (luaL_checkinteger_fn)require_lua(
        lua, "luaL_checkinteger");
    g_luaL_error = (luaL_error_fn)require_lua(lua, "luaL_error");
    g_lua_createtable = (lua_createtable_fn)require_lua(
        lua, "lua_createtable");
    g_lua_pushboolean = (lua_pushboolean_fn)require_lua(
        lua, "lua_pushboolean");
    g_lua_pushcclosure = (lua_pushcclosure_fn)require_lua(
        lua, "lua_pushcclosure");
    g_lua_pushinteger = (lua_pushinteger_fn)require_lua(
        lua, "lua_pushinteger");
    g_lua_pushstring = (lua_pushstring_fn)require_lua(
        lua, "lua_pushstring");
    g_lua_setfield = (lua_setfield_fn)require_lua(lua, "lua_setfield");
    return g_luaL_checkinteger != NULL && g_luaL_error != NULL &&
        g_lua_createtable != NULL && g_lua_pushboolean != NULL &&
        g_lua_pushcclosure != NULL && g_lua_pushinteger != NULL &&
        g_lua_pushstring != NULL && g_lua_setfield != NULL;
}

static void set_string(lua_State *state, const char *key, const char *value) {
    g_lua_pushstring(state, value);
    g_lua_setfield(state, -2, key);
}

__declspec(dllexport) int __cdecl luaopen_itb_observatory_rng_seed(
    lua_State *state) {
    unsigned char *base = NULL;

    if (!resolve_lua_api()) {
        return 0;
    }
    if (!validate_pinned_build(&base)) {
        return g_luaL_error(state, "pinned Breach.exe RNG identity mismatch");
    }

    g_lua_createtable(state, 0, 7);
    set_string(state, "VERSION", OBS_HELPER_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", OBS_ARCHITECTURE);
    set_string(state, "RNG_SEED_RVA", OBS_RNG_SEED_RVA_TEXT);
    set_string(state, "RNG_SEED_REGION_SHA256", OBS_RNG_SEED_REGION_SHA256);
    g_lua_pushcclosure(state, seed_rng, 0);
    g_lua_setfield(state, -2, "seed");
    return 1;
}
