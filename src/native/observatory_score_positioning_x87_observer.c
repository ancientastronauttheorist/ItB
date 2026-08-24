/*
 * Build-keyed, one-shot x87 rounding observer for enemy ScorePositioning.
 *
 * Loading this x86 DLL is inert. arm() verifies the exact Breach.exe and
 * lua5.1.dll images, then uses a private RaiseException/VEH transition to put
 * one current-thread execute breakpoint on lua_tointeger's reviewed FISTP.
 * The VEH accepts only the exact ScorePositioning -> named invoker -> integer
 * helper -> lua_tointeger frame chain and copies the exception context's x87
 * control word into fixed static storage. No executable byte is modified.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <intrin.h>

#include <stddef.h>
#include <stdint.h>

#include "observatory_score_positioning_x87_build.inc"

#pragma comment(lib, "bcrypt.lib")
#pragma intrinsic(__readfsdword)
#pragma intrinsic(_ReadWriteBarrier)

typedef struct lua_State lua_State;
typedef int (__cdecl *lua_CFunction)(lua_State *state);
typedef ptrdiff_t lua_Integer;

typedef int (__cdecl *lua_gettop_fn)(lua_State *);
typedef const char *(__cdecl *luaL_checklstring_fn)(lua_State *, int, size_t *);
typedef int (__cdecl *luaL_error_fn)(lua_State *, const char *, ...);
typedef void (__cdecl *lua_createtable_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_pushboolean_fn)(lua_State *, int);
typedef void (__cdecl *lua_pushcclosure_fn)(lua_State *, lua_CFunction, int);
typedef void (__cdecl *lua_pushinteger_fn)(lua_State *, lua_Integer);
typedef void (__cdecl *lua_pushnil_fn)(lua_State *);
typedef const char *(__cdecl *lua_pushstring_fn)(lua_State *, const char *);
typedef void (__cdecl *lua_setfield_fn)(lua_State *, int, const char *);

#define OBS_VERSION "observatory-score-positioning-x87-observer/1"
#define OBS_CAPTURE_ID_CAP 96
#define OBS_READABLE_RANGE_CAP 4096
#define OBS_FILE_CHUNK_BYTES (64u * 1024u)
#define OBS_TRANSITION_EXCEPTION ((DWORD)0xe0425837u)
#define OBS_TRANSITION_MAGIC ((ULONG_PTR)0x37585053u)
#define OBS_TRANSITION_ARM 1
#define OBS_TRANSITION_CLEAR 2
#define OBS_DR7_EXACT 0x00000001u
#define OBS_EFLAGS_RF 0x00010000u

enum obs_state {
    OBS_STATE_DORMANT = 0,
    OBS_STATE_VERIFIED = 1,
    OBS_STATE_CAPTURING = 2,
    OBS_STATE_DRAINING = 3,
    OBS_STATE_RESTORED = 4,
    OBS_STATE_FAILED_CLEAN = 5,
    OBS_STATE_FAILED_ARMED = 6
};

enum obs_stop_reason {
    OBS_STOP_NONE = 0,
    OBS_STOP_IDENTITY_MISMATCH = 1,
    OBS_STOP_PREEXISTING_DEBUG_STATE = 2,
    OBS_STOP_TRANSITION_MISMATCH = 3,
    OBS_STOP_WRONG_THREAD = 4,
    OBS_STOP_UNEXPECTED_BREAKPOINT = 5,
    OBS_STOP_POINTER_FAULT = 6,
    OBS_STOP_CONTEXT_FLAGS = 7,
    OBS_STOP_CLEAR_MISMATCH = 8,
    OBS_STOP_VEH_REMOVE = 9,
    OBS_STOP_FILE_PIN = 10,
    OBS_STOP_EMPTY_CAPTURE = 11,
    OBS_STOP_READABLE_MAP = 12,
    OBS_STOP_TORN_RECORD = 13
};

typedef struct obs_readable_range {
    uintptr_t start;
    uintptr_t end;
} obs_readable_range;

typedef struct obs_record {
    volatile LONG committed;
    uint32_t sequence;
    uint32_t thread_id;
    uint32_t context_flags;
    uint16_t control_word;
    uint16_t rounding_control_bits;
    uint32_t lua_conversion_rva;
    uint32_t integer_helper_return_rva;
    uint32_t named_invoker_return_rva;
    uint32_t score_positioning_return_rva;
} obs_record;

static lua_gettop_fn g_lua_gettop;
static luaL_checklstring_fn g_luaL_checklstring;
static luaL_error_fn g_luaL_error;
static lua_createtable_fn g_lua_createtable;
static lua_pushboolean_fn g_lua_pushboolean;
static lua_pushcclosure_fn g_lua_pushcclosure;
static lua_pushinteger_fn g_lua_pushinteger;
static lua_pushnil_fn g_lua_pushnil;
static lua_pushstring_fn g_lua_pushstring;
static lua_setfield_fn g_lua_setfield;

__declspec(align(64)) static obs_record g_record;
__declspec(align(64)) static obs_readable_range
    g_readable_ranges[OBS_READABLE_RANGE_CAP];
static unsigned char g_file_chunk[OBS_FILE_CHUNK_BYTES];
static unsigned char *g_executable_base;
static unsigned char *g_lua_base;
static char g_capture_id[OBS_CAPTURE_ID_CAP + 1];
static volatile LONG g_state = OBS_STATE_DORMANT;
static volatile LONG g_consumed;
static volatile LONG g_capture_started;
static volatile LONG g_record_count;
static volatile LONG g_ignored_non_score_count;
static volatile LONG g_pointer_fault_count;
static volatile LONG g_context_flag_error_count;
static volatile LONG g_transition_mismatch_count;
static volatile LONG g_wrong_thread_count;
static volatile LONG g_unexpected_breakpoint_count;
static volatile LONG g_torn_record_count;
static volatile LONG g_stop_reason;
static volatile LONG g_transition_requested;
static volatile LONG g_transition_seen;
static volatile LONG g_debug_armed;
static volatile LONG g_debug_cleared;
static volatile LONG g_veh_installed;
static volatile LONG g_veh_removed;
static volatile LONG g_executable_file_released;
static volatile LONG g_lua_file_released;
static volatile LONG g_seams_unchanged;
static volatile LONG g_readable_range_count;
static DWORD g_owner_thread_id;
static uintptr_t g_lua_conversion_address;
static PVOID g_veh_handle;
static HANDLE g_executable_file = INVALID_HANDLE_VALUE;
static HANDLE g_lua_file = INVALID_HANDLE_VALUE;
static int g_module_anchor;

static void byte_copy(void *destination, const void *source, size_t length) {
    volatile unsigned char *target = (volatile unsigned char *)destination;
    const volatile unsigned char *origin =
        (const volatile unsigned char *)source;
    size_t index;
    for (index = 0; index < length; ++index) target[index] = origin[index];
}

static void byte_zero(void *destination, size_t length) {
    volatile unsigned char *target = (volatile unsigned char *)destination;
    size_t index;
    for (index = 0; index < length; ++index) target[index] = 0;
}

static int bytes_equal(const void *left_value, const void *right_value, size_t length) {
    const volatile unsigned char *left =
        (const volatile unsigned char *)left_value;
    const volatile unsigned char *right =
        (const volatile unsigned char *)right_value;
    size_t index;
    for (index = 0; index < length; ++index) {
        if (left[index] != right[index]) return 0;
    }
    return 1;
}

static const char *state_text(LONG state) {
    switch (state) {
    case OBS_STATE_DORMANT: return "dormant";
    case OBS_STATE_VERIFIED: return "verified";
    case OBS_STATE_CAPTURING: return "capturing";
    case OBS_STATE_DRAINING: return "draining";
    case OBS_STATE_RESTORED: return "restored";
    case OBS_STATE_FAILED_CLEAN: return "failed_clean";
    default: return "failed_armed";
    }
}

static const char *stop_reason_text(LONG reason) {
    switch (reason) {
    case OBS_STOP_NONE: return NULL;
    case OBS_STOP_IDENTITY_MISMATCH: return "identity_mismatch";
    case OBS_STOP_PREEXISTING_DEBUG_STATE: return "preexisting_debug_state";
    case OBS_STOP_TRANSITION_MISMATCH: return "transition_mismatch";
    case OBS_STOP_WRONG_THREAD: return "wrong_thread";
    case OBS_STOP_UNEXPECTED_BREAKPOINT: return "unexpected_breakpoint";
    case OBS_STOP_POINTER_FAULT: return "pointer_fault";
    case OBS_STOP_CONTEXT_FLAGS: return "context_flags";
    case OBS_STOP_CLEAR_MISMATCH: return "clear_mismatch";
    case OBS_STOP_VEH_REMOVE: return "veh_remove";
    case OBS_STOP_FILE_PIN: return "file_pin";
    case OBS_STOP_EMPTY_CAPTURE: return "empty_capture";
    case OBS_STOP_READABLE_MAP: return "readable_map";
    default: return "torn_record";
    }
}

static const char *rounding_mode_text(uint16_t bits) {
    switch (bits & 0x0c00u) {
    case 0x0000u: return "nearest_even";
    case 0x0400u: return "down";
    case 0x0800u: return "up";
    default: return "toward_zero";
    }
}

static void request_stop_cold(LONG reason) {
    if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = reason;
    if (g_state == OBS_STATE_CAPTURING || g_state == OBS_STATE_VERIFIED) {
        g_state = OBS_STATE_DRAINING;
    }
}

/* OBS_HOT_PATH_BEGIN: no calls, allocation, I/O, locks, clocks, Lua, or APIs. */
#pragma code_seg(push, ".obshot")
static __forceinline int hot_range_readable(uintptr_t address, size_t length) {
    uintptr_t end;
    LONG index;
    if (length == 0 || address > UINTPTR_MAX - length) return 0;
    end = address + length;
    for (index = 0; index < g_readable_range_count; ++index) {
        if (address >= g_readable_ranges[index].start &&
            end <= g_readable_ranges[index].end) return 1;
        if (address < g_readable_ranges[index].start) return 0;
    }
    return 0;
}

LONG CALLBACK observer_score_positioning_x87_veh(PEXCEPTION_POINTERS pointers) {
    PEXCEPTION_RECORD exception_record;
    PCONTEXT context;
    DWORD thread_id;
    DWORD code;
    uintptr_t frame;
    uintptr_t parent_frame;
    uintptr_t grandparent_frame;
    uintptr_t integer_return;
    uintptr_t named_return;
    uintptr_t score_return;

    if (pointers == NULL || pointers->ExceptionRecord == NULL ||
        pointers->ContextRecord == NULL) return EXCEPTION_CONTINUE_SEARCH;
    exception_record = pointers->ExceptionRecord;
    context = pointers->ContextRecord;
    code = exception_record->ExceptionCode;
    thread_id = (DWORD)__readfsdword(0x24);

    if (code == OBS_TRANSITION_EXCEPTION) {
        LONG requested = g_transition_requested;
        LONG valid = requested != 0 && thread_id == g_owner_thread_id &&
            exception_record->NumberParameters == 3 &&
            exception_record->ExceptionInformation[0] == OBS_TRANSITION_MAGIC &&
            exception_record->ExceptionInformation[1] == (ULONG_PTR)requested &&
            exception_record->ExceptionInformation[2] == (ULONG_PTR)thread_id;
        if (!valid) {
            if (requested == 0) return EXCEPTION_CONTINUE_SEARCH;
            ++g_transition_mismatch_count;
            if (g_stop_reason == OBS_STOP_NONE) {
                g_stop_reason = OBS_STOP_TRANSITION_MISMATCH;
            }
            g_transition_seen = -requested;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        context->ContextFlags |= CONTEXT_DEBUG_REGISTERS;
        if (requested == OBS_TRANSITION_ARM) {
            if (g_state != OBS_STATE_VERIFIED || context->Dr0 != 0 ||
                context->Dr1 != 0 || context->Dr2 != 0 || context->Dr3 != 0 ||
                context->Dr7 != 0) {
                ++g_transition_mismatch_count;
                if (g_stop_reason == OBS_STOP_NONE) {
                    g_stop_reason = OBS_STOP_PREEXISTING_DEBUG_STATE;
                }
                g_transition_seen = -requested;
                return EXCEPTION_CONTINUE_EXECUTION;
            }
            context->Dr0 = (DWORD)g_lua_conversion_address;
            context->Dr1 = 0;
            context->Dr2 = 0;
            context->Dr3 = 0;
            context->Dr6 = 0;
            context->Dr7 = OBS_DR7_EXACT;
            g_debug_armed = 1;
            g_capture_started = 1;
            g_state = OBS_STATE_CAPTURING;
            g_transition_seen = requested;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        if (requested == OBS_TRANSITION_CLEAR) {
            if ((g_state != OBS_STATE_DRAINING &&
                 g_state != OBS_STATE_CAPTURING) ||
                context->Dr0 != (DWORD)g_lua_conversion_address ||
                context->Dr1 != 0 || context->Dr2 != 0 || context->Dr3 != 0 ||
                context->Dr7 != OBS_DR7_EXACT) {
                ++g_transition_mismatch_count;
                if (g_stop_reason == OBS_STOP_NONE) {
                    g_stop_reason = OBS_STOP_CLEAR_MISMATCH;
                }
                g_transition_seen = -requested;
                return EXCEPTION_CONTINUE_EXECUTION;
            }
            context->Dr0 = 0;
            context->Dr1 = 0;
            context->Dr2 = 0;
            context->Dr3 = 0;
            context->Dr6 = 0;
            context->Dr7 = 0;
            g_debug_armed = 0;
            g_debug_cleared = 1;
            g_transition_seen = requested;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        ++g_transition_mismatch_count;
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = OBS_STOP_TRANSITION_MISMATCH;
        }
        g_transition_seen = -requested;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    if (code != EXCEPTION_SINGLE_STEP || ((DWORD)context->Dr6 & 1u) == 0u) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
    if (thread_id != g_owner_thread_id) {
        ++g_wrong_thread_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_WRONG_THREAD;
        if (g_state == OBS_STATE_CAPTURING) g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_SEARCH;
    }
    context->Dr6 &= ~1u;
    context->EFlags |= OBS_EFLAGS_RF;
    if (g_state != OBS_STATE_CAPTURING) return EXCEPTION_CONTINUE_EXECUTION;
    if ((uintptr_t)context->Eip != g_lua_conversion_address) {
        ++g_unexpected_breakpoint_count;
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = OBS_STOP_UNEXPECTED_BREAKPOINT;
        }
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    frame = (uintptr_t)context->Ebp;
    if ((frame & 3u) != 0 || !hot_range_readable(frame, 8u)) {
        ++g_pointer_fault_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_POINTER_FAULT;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    parent_frame = *(const uintptr_t *)frame;
    integer_return = *(const uintptr_t *)(frame + 4u);
    if ((parent_frame & 3u) != 0 || !hot_range_readable(parent_frame, 8u)) {
        ++g_pointer_fault_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_POINTER_FAULT;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    grandparent_frame = *(const uintptr_t *)parent_frame;
    named_return = *(const uintptr_t *)(parent_frame + 4u);
    if ((grandparent_frame & 3u) != 0 ||
        !hot_range_readable(grandparent_frame, 8u)) {
        ++g_pointer_fault_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_POINTER_FAULT;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    score_return = *(const uintptr_t *)(grandparent_frame + 4u);
    if (integer_return != (uintptr_t)(g_executable_base +
            OBS_INTEGER_HELPER_AFTER_LUA_RVA) ||
        named_return != (uintptr_t)(g_executable_base +
            OBS_NAMED_INVOKER_AFTER_HELPER_RVA) ||
        score_return != (uintptr_t)(g_executable_base +
            OBS_SCORE_POSITIONING_AFTER_NAMED_RVA)) {
        ++g_ignored_non_score_count;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if ((context->ContextFlags & CONTEXT_FLOATING_POINT) !=
        CONTEXT_FLOATING_POINT) {
        ++g_context_flag_error_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_CONTEXT_FLAGS;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    g_record.sequence = 1u;
    g_record.thread_id = thread_id;
    g_record.context_flags = context->ContextFlags;
    g_record.control_word = (uint16_t)context->FloatSave.ControlWord;
    g_record.rounding_control_bits =
        (uint16_t)(context->FloatSave.ControlWord & 0x0c00u);
    g_record.lua_conversion_rva = OBS_LUA_CONVERSION_RVA;
    g_record.integer_helper_return_rva = OBS_INTEGER_HELPER_AFTER_LUA_RVA;
    g_record.named_invoker_return_rva = OBS_NAMED_INVOKER_AFTER_HELPER_RVA;
    g_record.score_positioning_return_rva =
        OBS_SCORE_POSITIONING_AFTER_NAMED_RVA;
    _ReadWriteBarrier();
    g_record.committed = 1;
    g_record_count = 1;

    context->Dr0 = 0;
    context->Dr1 = 0;
    context->Dr2 = 0;
    context->Dr3 = 0;
    context->Dr6 = 0;
    context->Dr7 = 0;
    g_debug_armed = 0;
    g_debug_cleared = 1;
    g_state = OBS_STATE_DRAINING;
    return EXCEPTION_CONTINUE_EXECUTION;
}
#pragma code_seg(pop)
/* OBS_HOT_PATH_END */

static int verify_module_file_sha256(
    HMODULE module,
    LONGLONG expected_size,
    const unsigned char expected_digest[32],
    HANDLE *pinned_file
) {
    WCHAR path[1024];
    DWORD path_length;
    HANDLE file = INVALID_HANDLE_VALUE;
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    DWORD object_length = 0;
    DWORD result_length = 0;
    DWORD read_count = 0;
    LARGE_INTEGER size;
    unsigned char *hash_object = NULL;
    unsigned char digest[32];
    int ok = 0;

    path_length = GetModuleFileNameW(module, path, ARRAYSIZE(path));
    if (path_length == 0 || path_length >= ARRAYSIZE(path)) goto cleanup;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (file == INVALID_HANDLE_VALUE || !GetFileSizeEx(file, &size) ||
        size.QuadPart != expected_size) goto cleanup;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(
            &algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0)) ||
        !BCRYPT_SUCCESS(BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH,
            (PUCHAR)&object_length, sizeof(object_length), &result_length, 0)) ||
        object_length == 0 || object_length > (1024u * 1024u)) goto cleanup;
    hash_object = (unsigned char *)HeapAlloc(GetProcessHeap(), 0, object_length);
    if (hash_object == NULL || !BCRYPT_SUCCESS(BCryptCreateHash(
            algorithm, &hash, hash_object, object_length, NULL, 0, 0))) {
        goto cleanup;
    }
    for (;;) {
        if (!ReadFile(file, g_file_chunk, (DWORD)sizeof(g_file_chunk),
                &read_count, NULL)) goto cleanup;
        if (read_count == 0) break;
        if (!BCRYPT_SUCCESS(BCryptHashData(hash, g_file_chunk, read_count, 0))) {
            goto cleanup;
        }
    }
    if (!BCRYPT_SUCCESS(BCryptFinishHash(hash, digest, sizeof(digest), 0))) {
        goto cleanup;
    }
    ok = bytes_equal(digest, expected_digest, sizeof(digest));
    if (ok) {
        *pinned_file = file;
        file = INVALID_HANDLE_VALUE;
    }
cleanup:
    if (hash != NULL) BCryptDestroyHash(hash);
    if (hash_object != NULL) HeapFree(GetProcessHeap(), 0, hash_object);
    if (algorithm != NULL) BCryptCloseAlgorithmProvider(algorithm, 0);
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    byte_zero(digest, sizeof(digest));
    return ok;
}

static int live_pe_identity(
    unsigned char *base,
    DWORD timestamp,
    DWORD size_of_image
) {
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    if (base == NULL) return 0;
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        (uint32_t)dos->e_lfanew > 0x00100000u) return 0;
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    return nt->Signature == IMAGE_NT_SIGNATURE &&
        nt->FileHeader.Machine == IMAGE_FILE_MACHINE_I386 &&
        nt->FileHeader.TimeDateStamp == timestamp &&
        nt->OptionalHeader.Magic == IMAGE_NT_OPTIONAL_HDR32_MAGIC &&
        nt->OptionalHeader.SizeOfImage == size_of_image;
}

static int executable_seams_match(void) {
    uint32_t iat_operand = 0u;
    if (g_executable_base == NULL) return 0;
    byte_copy(&iat_operand,
        g_executable_base + OBS_INTEGER_CALL_RVA + 2u, sizeof(iat_operand));
    return bytes_equal(g_executable_base + OBS_INTEGER_CALL_RVA,
            OBS_INTEGER_CALL_PREFIX, OBS_INTEGER_CALL_PREFIX_SIZE) &&
        iat_operand == (uint32_t)(uintptr_t)(g_executable_base +
            OBS_LUA_TOINTEGER_IAT_RVA) &&
        bytes_equal(g_executable_base + OBS_SCORE_POSITIONING_CALL_RVA,
            OBS_SCORE_POSITIONING_CALL_BYTES, OBS_SCORE_POSITIONING_CALL_SIZE) &&
        bytes_equal(g_executable_base + OBS_NAMED_INVOKER_HELPER_CALL_RVA,
            OBS_NAMED_INVOKER_HELPER_CALL_BYTES,
            OBS_NAMED_INVOKER_HELPER_CALL_SIZE);
}

static int lua_seam_matches(void) {
    FARPROC exported;
    if (g_lua_base == NULL) return 0;
    exported = GetProcAddress((HMODULE)g_lua_base, "lua_tointeger");
    return exported == (FARPROC)(g_lua_base + OBS_LUA_TOINTEGER_RVA) &&
        bytes_equal(g_lua_base + OBS_LUA_CONVERSION_RVA,
            OBS_LUA_CONVERSION_BYTES, OBS_LUA_CONVERSION_SIZE);
}

static int verify_live_identity(void) {
    g_executable_base = (unsigned char *)GetModuleHandleW(NULL);
    g_lua_base = (unsigned char *)GetModuleHandleA("lua5.1.dll");
    if (!live_pe_identity(g_executable_base, OBS_PE_TIMESTAMP,
            OBS_PE_SIZE_OF_IMAGE) ||
        !live_pe_identity(g_lua_base, OBS_LUA_PE_TIMESTAMP,
            OBS_LUA_PE_SIZE_OF_IMAGE) ||
        !executable_seams_match() || !lua_seam_matches() ||
        !verify_module_file_sha256(NULL, OBS_EXECUTABLE_SIZE,
            OBS_EXECUTABLE_SHA256_BYTES, &g_executable_file) ||
        !verify_module_file_sha256((HMODULE)g_lua_base, OBS_LUA_SIZE,
            OBS_LUA_SHA256_BYTES, &g_lua_file)) return 0;
    g_lua_conversion_address =
        (uintptr_t)(g_lua_base + OBS_LUA_CONVERSION_RVA);
    return 1;
}

static int build_readable_range_map(void) {
    uintptr_t cursor = 0x00010000u;
    MEMORY_BASIC_INFORMATION information;
    LONG count = 0;
    while (cursor < 0x7ff00000u) {
        SIZE_T queried = VirtualQuery(
            (const void *)cursor, &information, sizeof(information));
        uintptr_t start;
        uintptr_t end;
        DWORD protection;
        int readable;
        if (queried != sizeof(information) || information.RegionSize == 0) {
            return 0;
        }
        start = (uintptr_t)information.BaseAddress;
        end = information.RegionSize > 0x7ff00000u - start
            ? 0x7ff00000u : start + information.RegionSize;
        if (end <= cursor) return 0;
        protection = information.Protect;
        readable = information.State == MEM_COMMIT &&
            (protection & (PAGE_GUARD | PAGE_NOACCESS)) == 0 &&
            ((protection & 0xffu) == PAGE_READONLY ||
             (protection & 0xffu) == PAGE_READWRITE ||
             (protection & 0xffu) == PAGE_WRITECOPY ||
             (protection & 0xffu) == PAGE_EXECUTE_READ ||
             (protection & 0xffu) == PAGE_EXECUTE_READWRITE ||
             (protection & 0xffu) == PAGE_EXECUTE_WRITECOPY);
        if (readable) {
            if (start < 0x00010000u) start = 0x00010000u;
            if (end > 0x7ff00000u) end = 0x7ff00000u;
            if (start < end) {
                if (count > 0 && g_readable_ranges[count - 1].end == start) {
                    g_readable_ranges[count - 1].end = end;
                } else {
                    if (count >= OBS_READABLE_RANGE_CAP) return 0;
                    g_readable_ranges[count].start = start;
                    g_readable_ranges[count].end = end;
                    ++count;
                }
            }
        }
        cursor = end;
    }
    g_readable_range_count = count;
    return count > 0;
}

static int close_pinned_file(HANDLE *file, volatile LONG *released) {
    HANDLE current = *file;
    if (current == INVALID_HANDLE_VALUE) return *released != 0;
    if (!CloseHandle(current)) return 0;
    *file = INVALID_HANDLE_VALUE;
    *released = 1;
    return 1;
}

static FARPROC require_lua(HMODULE module, const char *name) {
    return module == NULL ? NULL : GetProcAddress(module, name);
}

static int resolve_lua_api(void) {
    HMODULE lua = GetModuleHandleA("lua5.1.dll");
    g_lua_gettop = (lua_gettop_fn)require_lua(lua, "lua_gettop");
    g_luaL_checklstring = (luaL_checklstring_fn)require_lua(
        lua, "luaL_checklstring");
    g_luaL_error = (luaL_error_fn)require_lua(lua, "luaL_error");
    g_lua_createtable = (lua_createtable_fn)require_lua(
        lua, "lua_createtable");
    g_lua_pushboolean = (lua_pushboolean_fn)require_lua(
        lua, "lua_pushboolean");
    g_lua_pushcclosure = (lua_pushcclosure_fn)require_lua(
        lua, "lua_pushcclosure");
    g_lua_pushinteger = (lua_pushinteger_fn)require_lua(
        lua, "lua_pushinteger");
    g_lua_pushnil = (lua_pushnil_fn)require_lua(lua, "lua_pushnil");
    g_lua_pushstring = (lua_pushstring_fn)require_lua(lua, "lua_pushstring");
    g_lua_setfield = (lua_setfield_fn)require_lua(lua, "lua_setfield");
    return g_lua_gettop != NULL && g_luaL_checklstring != NULL &&
        g_luaL_error != NULL && g_lua_createtable != NULL &&
        g_lua_pushboolean != NULL && g_lua_pushcclosure != NULL &&
        g_lua_pushinteger != NULL && g_lua_pushnil != NULL &&
        g_lua_pushstring != NULL && g_lua_setfield != NULL;
}

static void set_string(lua_State *state, const char *key, const char *value) {
    g_lua_pushstring(state, value);
    g_lua_setfield(state, -2, key);
}

static void set_integer(lua_State *state, const char *key, LONG value) {
    g_lua_pushinteger(state, (lua_Integer)value);
    g_lua_setfield(state, -2, key);
}

static void set_boolean(lua_State *state, const char *key, int value) {
    g_lua_pushboolean(state, value != 0);
    g_lua_setfield(state, -2, key);
}

static void set_nullable_reason(lua_State *state, LONG reason) {
    const char *text = stop_reason_text(reason);
    if (text == NULL) g_lua_pushnil(state); else g_lua_pushstring(state, text);
    g_lua_setfield(state, -2, "stopped_reason");
}

static int valid_capture_id(const char *value, size_t length) {
    size_t index;
    if (length == 0 || length > OBS_CAPTURE_ID_CAP ||
        value[0] < 'a' || value[0] > 'z') return 0;
    for (index = 1; index < length; ++index) {
        unsigned char byte = (unsigned char)value[index];
        if (!((byte >= 'a' && byte <= 'z') ||
              (byte >= '0' && byte <= '9') || byte == '_' || byte == '.' ||
              byte == '-')) return 0;
    }
    return 1;
}

static void reset_capture_state(void) {
    byte_zero(&g_record, sizeof(g_record));
    g_record_count = 0;
    g_ignored_non_score_count = 0;
    g_pointer_fault_count = 0;
    g_context_flag_error_count = 0;
    g_transition_mismatch_count = 0;
    g_wrong_thread_count = 0;
    g_unexpected_breakpoint_count = 0;
    g_torn_record_count = 0;
    g_stop_reason = OBS_STOP_NONE;
    g_transition_requested = 0;
    g_transition_seen = 0;
    g_capture_started = 0;
    g_debug_armed = 0;
    g_debug_cleared = 0;
    g_veh_installed = 0;
    g_veh_removed = 0;
    g_executable_file_released = 0;
    g_lua_file_released = 0;
    g_seams_unchanged = 0;
    g_readable_range_count = 0;
}

static int run_transition(LONG mode) {
    ULONG_PTR arguments[3];
    g_transition_requested = mode;
    g_transition_seen = 0;
    arguments[0] = OBS_TRANSITION_MAGIC;
    arguments[1] = (ULONG_PTR)mode;
    arguments[2] = (ULONG_PTR)g_owner_thread_id;
    RaiseException(OBS_TRANSITION_EXCEPTION, 0, 3, arguments);
    g_transition_requested = 0;
    return g_transition_seen == mode;
}

static int arm_observer(lua_State *state) {
    const char *capture_id;
    size_t capture_length = 0;
    if (g_lua_gettop(state) != 1) {
        return g_luaL_error(state, "x87 observer arm requires one capture ID");
    }
    capture_id = g_luaL_checklstring(state, 1, &capture_length);
    if (!valid_capture_id(capture_id, capture_length)) {
        return g_luaL_error(state, "x87 observer capture ID is invalid");
    }
    if (g_consumed != 0) {
        return g_luaL_error(state, "x87 observer is one-shot per process");
    }
    g_consumed = 1;
    reset_capture_state();
    byte_copy(g_capture_id, capture_id, capture_length);
    g_capture_id[capture_length] = '\0';
    g_owner_thread_id = (DWORD)__readfsdword(0x24);
    if (!verify_live_identity()) {
        request_stop_cold(OBS_STOP_IDENTITY_MISMATCH);
        (void)close_pinned_file(&g_executable_file,
            &g_executable_file_released);
        (void)close_pinned_file(&g_lua_file, &g_lua_file_released);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "pinned x87 observer identity mismatch");
    }
    if (!build_readable_range_map()) {
        request_stop_cold(OBS_STOP_READABLE_MAP);
        (void)close_pinned_file(&g_executable_file,
            &g_executable_file_released);
        (void)close_pinned_file(&g_lua_file, &g_lua_file_released);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "x87 observer readable-range map failed");
    }
    g_state = OBS_STATE_VERIFIED;
    g_veh_handle = AddVectoredExceptionHandler(
        1, observer_score_positioning_x87_veh);
    if (g_veh_handle == NULL) {
        request_stop_cold(OBS_STOP_TRANSITION_MISMATCH);
        (void)close_pinned_file(&g_executable_file,
            &g_executable_file_released);
        (void)close_pinned_file(&g_lua_file, &g_lua_file_released);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "x87 observer VEH installation failed");
    }
    g_veh_installed = 1;
    if (!run_transition(OBS_TRANSITION_ARM) || g_debug_armed == 0 ||
        g_state != OBS_STATE_CAPTURING) {
        if (g_debug_armed != 0) {
            g_state = OBS_STATE_DRAINING;
            (void)run_transition(OBS_TRANSITION_CLEAR);
        }
        if (g_debug_armed == 0 &&
            RemoveVectoredExceptionHandler(g_veh_handle) != 0) {
            g_veh_handle = NULL;
            g_veh_removed = 1;
            g_veh_installed = 0;
        }
        if (g_debug_armed == 0) {
            (void)close_pinned_file(&g_executable_file,
                &g_executable_file_released);
            (void)close_pinned_file(&g_lua_file, &g_lua_file_released);
        }
        g_state = g_debug_armed != 0
            ? OBS_STATE_FAILED_ARMED : OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "x87 debug-register arm failed");
    }
    g_lua_pushboolean(state, 1);
    return 1;
}

static void push_snapshot(lua_State *state) {
    LONG reason = g_stop_reason;
    LONG torn = g_record_count == 1 && g_record.committed == 1 ? 0 : 1;
    int complete;
    if (torn != 0 && reason == OBS_STOP_NONE) reason = OBS_STOP_TORN_RECORD;
    g_torn_record_count = torn;
    complete = g_state == OBS_STATE_RESTORED && reason == OBS_STOP_NONE &&
        g_record_count == 1 && torn == 0 && g_pointer_fault_count == 0 &&
        g_context_flag_error_count == 0 &&
        g_transition_mismatch_count == 0 && g_wrong_thread_count == 0 &&
        g_unexpected_breakpoint_count == 0 && g_debug_armed == 0 &&
        g_debug_cleared != 0 && g_veh_installed == 0 &&
        g_veh_removed != 0 && g_executable_file_released != 0 &&
        g_lua_file_released != 0 && g_seams_unchanged != 0;

    g_lua_createtable(state, 0, 7);
    set_integer(state, "schema_version", 1);
    set_string(state, "kind", "native_score_positioning_x87_snapshot");
    set_string(state, "observer_version", OBS_VERSION);
    set_string(state, "capture_id", g_capture_id);

    g_lua_createtable(state, 0, 14);
    set_string(state, "platform", "windows");
    set_string(state, "architecture", "x86");
    set_string(state, "build_id", OBS_BUILD_ID);
    set_string(state, "executable_sha256", OBS_EXECUTABLE_SHA256);
    set_integer(state, "executable_size", (LONG)OBS_EXECUTABLE_SIZE);
    set_string(state, "lua_dll_sha256", OBS_LUA_SHA256);
    set_integer(state, "lua_dll_size", (LONG)OBS_LUA_SIZE);
    set_string(state, "inventory_sha256", OBS_INVENTORY_SHA256);
    set_string(state, "boundary_map_sha256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "hardware_breakpoint_plan_sha256", OBS_HW_PLAN_SHA256);
    set_string(state, "integer_call_rva", OBS_INTEGER_CALL_RVA_TEXT);
    set_string(state, "lua_tointeger_rva", OBS_LUA_TOINTEGER_RVA_TEXT);
    set_string(state, "lua_conversion_rva", OBS_LUA_CONVERSION_RVA_TEXT);
    g_lua_setfield(state, -2, "identity");

    g_lua_createtable(state, 0, 18);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "complete", complete);
    set_nullable_reason(state, reason);
    set_integer(state, "ignored_non_score_count", g_ignored_non_score_count);
    set_integer(state, "pointer_fault_count", g_pointer_fault_count);
    set_integer(state, "context_flag_error_count", g_context_flag_error_count);
    set_integer(state, "transition_mismatch_count", g_transition_mismatch_count);
    set_integer(state, "wrong_thread_count", g_wrong_thread_count);
    set_integer(state, "unexpected_breakpoint_count",
        g_unexpected_breakpoint_count);
    set_integer(state, "torn_record_count", torn);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_boolean(state, "veh_removed", g_veh_removed);
    set_boolean(state, "executable_file_released",
        g_executable_file_released);
    set_boolean(state, "lua_file_released", g_lua_file_released);
    set_boolean(state, "executable_bytes_modified", 0);
    set_boolean(state, "seams_unchanged", g_seams_unchanged);
    g_lua_setfield(state, -2, "integrity");

    g_lua_createtable(state, 0, 10);
    set_integer(state, "seq", (LONG)g_record.sequence);
    set_integer(state, "thread_id", (LONG)g_record.thread_id);
    set_integer(state, "context_flags", (LONG)g_record.context_flags);
    set_integer(state, "control_word", (LONG)g_record.control_word);
    set_integer(state, "rounding_control_bits",
        (LONG)g_record.rounding_control_bits);
    set_string(state, "rounding_mode",
        rounding_mode_text(g_record.rounding_control_bits));
    set_integer(state, "lua_conversion_rva", (LONG)g_record.lua_conversion_rva);
    set_integer(state, "integer_helper_return_rva",
        (LONG)g_record.integer_helper_return_rva);
    set_integer(state, "named_invoker_return_rva",
        (LONG)g_record.named_invoker_return_rva);
    set_integer(state, "score_positioning_return_rva",
        (LONG)g_record.score_positioning_return_rva);
    g_lua_setfield(state, -2, "observation");

    g_lua_createtable(state, 0, 3);
    set_integer(state, "record_count", g_record_count);
    set_integer(state, "thread_count", g_capture_started != 0 ? 1 : 0);
    set_string(state, "observed_rounding_mode",
        rounding_mode_text(g_record.rounding_control_bits));
    g_lua_setfield(state, -2, "summary");
}

static int finish_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "x87 observer finish takes no arguments");
    }
    if (g_consumed == 0 || g_capture_started == 0) {
        return g_luaL_error(state, "x87 observer is not active");
    }
    if ((DWORD)__readfsdword(0x24) != g_owner_thread_id) {
        ++g_wrong_thread_count;
        request_stop_cold(OBS_STOP_WRONG_THREAD);
        return g_luaL_error(state, "x87 observer must finish on its arm thread");
    }
    if (g_state != OBS_STATE_CAPTURING && g_state != OBS_STATE_DRAINING &&
        g_state != OBS_STATE_FAILED_ARMED) {
        return g_luaL_error(state, "x87 observer cannot be finished");
    }
    if (g_record_count == 0) request_stop_cold(OBS_STOP_EMPTY_CAPTURE);
    g_state = OBS_STATE_DRAINING;
    if (g_debug_armed != 0 &&
        (!run_transition(OBS_TRANSITION_CLEAR) || g_debug_cleared == 0 ||
         g_debug_armed != 0)) {
        g_state = OBS_STATE_FAILED_ARMED;
        return g_luaL_error(state,
            "x87 debug-register clearing failed; no checkpoint published");
    }
    if (g_veh_handle == NULL ||
        RemoveVectoredExceptionHandler(g_veh_handle) == 0) {
        request_stop_cold(OBS_STOP_VEH_REMOVE);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "x87 VEH removal failed; no checkpoint published");
    }
    g_veh_handle = NULL;
    g_veh_installed = 0;
    g_veh_removed = 1;
    g_seams_unchanged = executable_seams_match() && lua_seam_matches();
    if (!g_seams_unchanged ||
        !close_pinned_file(&g_executable_file,
            &g_executable_file_released) ||
        !close_pinned_file(&g_lua_file, &g_lua_file_released)) {
        request_stop_cold(OBS_STOP_FILE_PIN);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "x87 observer integrity finalization failed");
    }
    g_state = OBS_STATE_RESTORED;
    push_snapshot(state);
    return 1;
}

static int status_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "x87 observer status takes no arguments");
    }
    g_lua_createtable(state, 0, 12);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "consumed", g_consumed);
    set_boolean(state, "capture_started", g_capture_started);
    set_integer(state, "record_count", g_record_count);
    set_integer(state, "ignored_non_score_count", g_ignored_non_score_count);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_nullable_reason(state, g_stop_reason);
    if (g_record_count == 1) {
        set_string(state, "observed_rounding_mode",
            rounding_mode_text(g_record.rounding_control_bits));
    }
    return 1;
}

static int pin_this_module(void) {
    HMODULE module = NULL;
    return GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_PIN,
        (LPCWSTR)(const void *)&g_module_anchor, &module) != 0;
}

__declspec(dllexport) int __cdecl
luaopen_itb_observatory_score_positioning_x87_observer(lua_State *state) {
    if (!resolve_lua_api()) return 0;
    if (!pin_this_module()) {
        return g_luaL_error(state, "x87 observer module pin failed");
    }
    g_lua_createtable(state, 0, 14);
    set_string(state, "VERSION", OBS_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "LUA_DLL_SHA256", OBS_LUA_SHA256);
    set_string(state, "INVENTORY_SHA256", OBS_INVENTORY_SHA256);
    set_string(state, "BOUNDARY_MAP_SHA256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "ARCHITECTURE", "x86");
    set_string(state, "INTEGER_CALL_RVA", OBS_INTEGER_CALL_RVA_TEXT);
    set_string(state, "LUA_TOINTEGER_RVA", OBS_LUA_TOINTEGER_RVA_TEXT);
    set_string(state, "LUA_CONVERSION_RVA", OBS_LUA_CONVERSION_RVA_TEXT);
    set_string(state, "HARDWARE_BREAKPOINT_PLAN_SHA256", OBS_HW_PLAN_SHA256);
    g_lua_pushcclosure(state, arm_observer, 0);
    g_lua_setfield(state, -2, "arm");
    g_lua_pushcclosure(state, finish_observer, 0);
    g_lua_setfield(state, -2, "finish");
    g_lua_pushcclosure(state, status_observer, 0);
    g_lua_setfield(state, -2, "status");
    return 1;
}
