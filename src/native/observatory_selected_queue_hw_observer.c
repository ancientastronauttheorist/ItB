/*
 * Build-keyed, one-shot selected-record/queued-action observer for ITB.
 *
 * Loading this x86 DLL is inert. arm() verifies one exact Breach.exe and then
 * uses a private RaiseException/VEH transition to place current-thread execute
 * breakpoints in DR0 and DR1. No executable byte is ever modified. The VEH
 * writes only fixed-width records into a bounded static ring and performs no
 * allocation, I/O, Lua/game calls, locks, clocks, or Windows API calls.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <intrin.h>

#include <stddef.h>
#include <stdint.h>

#include "observatory_selected_queue_hw_build.inc"

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
typedef void (__cdecl *lua_rawseti_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_setfield_fn)(lua_State *, int, const char *);

#define OBS_VERSION "observatory-selected-queue-hw-observer/1"
#define OBS_RECORD_CAP 256
#define OBS_READABLE_RANGE_CAP 4096
#define OBS_CAPTURE_ID_CAP 96
#define OBS_FILE_CHUNK_BYTES (64u * 1024u)
#define OBS_TRANSITION_EXCEPTION ((DWORD)0xe0425351u)
#define OBS_TRANSITION_MAGIC ((ULONG_PTR)0x5148534fu)
#define OBS_TRANSITION_ARM 1
#define OBS_TRANSITION_CLEAR 2
#define OBS_DR7_EXACT 0x00000005u
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
    OBS_STOP_UNEXPECTED_ORDER = 6,
    OBS_STOP_POINTER_FAULT = 7,
    OBS_STOP_OVERFLOW = 8,
    OBS_STOP_CLEAR_MISMATCH = 9,
    OBS_STOP_VEH_REMOVE = 10,
    OBS_STOP_EXECUTABLE_PIN = 11,
    OBS_STOP_EMPTY_CAPTURE = 12,
    OBS_STOP_TORN_RECORD = 13,
    OBS_STOP_READABLE_MAP = 14
};

enum obs_record_kind {
    OBS_RECORD_SELECTED = 1,
    OBS_RECORD_QUEUE = 2
};

typedef struct obs_record {
    volatile LONG committed;
    uint32_t sequence;
    uint16_t pair_index;
    uint8_t kind;
    uint8_t reserved;
    int32_t pawn_id;
    int32_t current_weapon;
    int32_t base_current_weapon;
    int32_t value0;
    int32_t value1;
    int32_t value2;
    int32_t value3;
    int32_t value4;
    int32_t value5;
    int32_t value6;
} obs_record;

typedef struct obs_readable_range {
    uintptr_t start;
    uintptr_t end;
} obs_readable_range;

static lua_gettop_fn g_lua_gettop;
static luaL_checklstring_fn g_luaL_checklstring;
static luaL_error_fn g_luaL_error;
static lua_createtable_fn g_lua_createtable;
static lua_pushboolean_fn g_lua_pushboolean;
static lua_pushcclosure_fn g_lua_pushcclosure;
static lua_pushinteger_fn g_lua_pushinteger;
static lua_pushnil_fn g_lua_pushnil;
static lua_pushstring_fn g_lua_pushstring;
static lua_rawseti_fn g_lua_rawseti;
static lua_setfield_fn g_lua_setfield;

__declspec(align(64)) static obs_record g_records[OBS_RECORD_CAP];
__declspec(align(64)) static obs_readable_range
    g_readable_ranges[OBS_READABLE_RANGE_CAP];
static unsigned char g_file_chunk[OBS_FILE_CHUNK_BYTES];
static unsigned char *g_executable_base;
static char g_capture_id[OBS_CAPTURE_ID_CAP + 1];
static volatile LONG g_state = OBS_STATE_DORMANT;
static volatile LONG g_consumed;
static volatile LONG g_capture_started;
static volatile LONG g_record_count;
static volatile LONG g_selected_count;
static volatile LONG g_queue_count;
static volatile LONG g_pair_count;
static volatile LONG g_overflow_count;
static volatile LONG g_ordering_error_count;
static volatile LONG g_pointer_fault_count;
static volatile LONG g_transition_mismatch_count;
static volatile LONG g_wrong_thread_count;
static volatile LONG g_unexpected_breakpoint_count;
static volatile LONG g_torn_record_count;
static volatile LONG g_stop_reason;
static volatile LONG g_transition_requested;
static volatile LONG g_transition_seen;
static volatile LONG g_handler_depth;
static volatile LONG g_debug_armed;
static volatile LONG g_debug_cleared;
static volatile LONG g_veh_installed;
static volatile LONG g_veh_removed;
static volatile LONG g_executable_file_released;
static volatile LONG g_seam_bytes_unchanged;
static volatile LONG g_readable_range_count;
static DWORD g_owner_thread_id;
static uintptr_t g_selected_address;
static uintptr_t g_queue_address;
static uintptr_t g_pending_pawn;
static int32_t g_pending_pawn_id;
static uint16_t g_pending_pair_index;
static PVOID g_veh_handle;
static HANDLE g_executable_file = INVALID_HANDLE_VALUE;
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
    const unsigned char *left = (const unsigned char *)left_value;
    const unsigned char *right = (const unsigned char *)right_value;
    unsigned char difference = 0;
    size_t index;
    for (index = 0; index < length; ++index) {
        difference |= (unsigned char)(left[index] ^ right[index]);
    }
    return difference == 0;
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
    case OBS_STOP_IDENTITY_MISMATCH: return "identity_mismatch";
    case OBS_STOP_PREEXISTING_DEBUG_STATE: return "preexisting_debug_state";
    case OBS_STOP_TRANSITION_MISMATCH: return "transition_mismatch";
    case OBS_STOP_WRONG_THREAD: return "wrong_thread";
    case OBS_STOP_UNEXPECTED_BREAKPOINT: return "unexpected_breakpoint";
    case OBS_STOP_UNEXPECTED_ORDER: return "unexpected_order";
    case OBS_STOP_POINTER_FAULT: return "pointer_fault";
    case OBS_STOP_OVERFLOW: return "overflow";
    case OBS_STOP_CLEAR_MISMATCH: return "clear_mismatch";
    case OBS_STOP_VEH_REMOVE: return "veh_remove_failed";
    case OBS_STOP_EXECUTABLE_PIN: return "executable_pin_failed";
    case OBS_STOP_EMPTY_CAPTURE: return "empty_capture";
    case OBS_STOP_TORN_RECORD: return "torn_record";
    case OBS_STOP_READABLE_MAP: return "readable_map_failed";
    default: return NULL;
    }
}

static void request_stop_cold(LONG reason) {
    if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = reason;
    if (g_state == OBS_STATE_CAPTURING) g_state = OBS_STATE_DRAINING;
}

/* OBS_HOT_PATH_BEGIN
 * This entire dedicated executable section is the VEH. It calls no function,
 * uses only fixed static memory, and publishes no address or pointer.
 */
#pragma code_seg(push, ".obshot")
static __forceinline int hot_range_readable(uintptr_t address, size_t length) {
    LONG index;
    uintptr_t end;
    if (length == 0 || address < 0x00010000u ||
        address > 0x7ff00000u || length > 0x7ff00000u - address) return 0;
    end = address + length;
    for (index = 0; index < g_readable_range_count; ++index) {
        if (address >= g_readable_ranges[index].start &&
            end <= g_readable_ranges[index].end) return 1;
        if (address < g_readable_ranges[index].start) return 0;
    }
    return 0;
}

LONG CALLBACK observer_selected_queue_veh(PEXCEPTION_POINTERS pointers) {
    PEXCEPTION_RECORD exception_record;
    PCONTEXT context;
    DWORD thread_id;
    DWORD code;
    DWORD ours;
    uintptr_t eip;
    LONG index;
    obs_record *record;
    uintptr_t pawn;
    int capture_ok;

    if (pointers == NULL || pointers->ExceptionRecord == NULL ||
        pointers->ContextRecord == NULL) {
        return EXCEPTION_CONTINUE_SEARCH;
    }
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
            context->Dr0 = (DWORD)g_selected_address;
            context->Dr1 = (DWORD)g_queue_address;
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
                context->Dr0 != (DWORD)g_selected_address ||
                context->Dr1 != (DWORD)g_queue_address ||
                context->Dr2 != 0 || context->Dr3 != 0 ||
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

    if (code != EXCEPTION_SINGLE_STEP) return EXCEPTION_CONTINUE_SEARCH;
    ours = (DWORD)context->Dr6 & 3u;
    if (ours == 0) return EXCEPTION_CONTINUE_SEARCH;
    if (thread_id != g_owner_thread_id) {
        ++g_wrong_thread_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_WRONG_THREAD;
        if (g_state == OBS_STATE_CAPTURING) g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_SEARCH;
    }
    context->Dr6 &= ~3u;
    context->EFlags |= OBS_EFLAGS_RF;
    if (g_state != OBS_STATE_CAPTURING) return EXCEPTION_CONTINUE_EXECUTION;
    eip = (uintptr_t)context->Eip;
    if ((ours != 1u && ours != 2u) ||
        (ours == 1u && eip != g_selected_address) ||
        (ours == 2u && eip != g_queue_address)) {
        ++g_unexpected_breakpoint_count;
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = OBS_STOP_UNEXPECTED_BREAKPOINT;
        }
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (g_handler_depth != 0) {
        ++g_pointer_fault_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_POINTER_FAULT;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (g_record_count < 0 || g_record_count >= OBS_RECORD_CAP) {
        ++g_overflow_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_OVERFLOW;
        g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_EXECUTION;
    }

    g_handler_depth = 1;
    capture_ok = 0;
    if (ours == 1u) {
        uintptr_t ai = (uintptr_t)context->Ebx;
        if (g_pending_pawn != 0 || (ai & 3u) != 0) {
            ++g_ordering_error_count;
        } else if (!hot_range_readable(ai + 4u, sizeof(uintptr_t)) ||
            !hot_range_readable(ai + 0x50u, 24u)) {
            ++g_pointer_fault_count;
        } else {
            pawn = *(const uintptr_t *)(ai + 4u);
            if ((pawn & 3u) != 0 ||
                !hot_range_readable(pawn + 0x10u, 0x34u) ||
                !hot_range_readable(pawn + 0x948u, 0x60u)) {
                ++g_pointer_fault_count;
            } else {
                index = g_record_count;
                record = &g_records[index];
                record->sequence = (uint32_t)index;
                record->pair_index = (uint16_t)g_pair_count;
                record->kind = OBS_RECORD_SELECTED;
                record->reserved = 0;
                record->pawn_id = *(const int32_t *)(pawn + 0x9a4u);
                record->current_weapon = *(const int32_t *)(pawn + 0x948u);
                record->base_current_weapon = *(const int32_t *)(pawn + 0x40u);
                record->value0 = *(const int32_t *)(ai + 0x50u);
                record->value1 = *(const int32_t *)(ai + 0x54u);
                record->value2 = *(const int32_t *)(ai + 0x58u);
                record->value3 = *(const int32_t *)(ai + 0x5cu);
                record->value4 = *(const int32_t *)(ai + 0x60u);
                record->value5 = *(const int32_t *)(ai + 0x64u);
                record->value6 = 0;
                _ReadWriteBarrier();
                record->committed = index + 1;
                g_record_count = index + 1;
                ++g_selected_count;
                g_pending_pawn = pawn;
                g_pending_pawn_id = record->pawn_id;
                g_pending_pair_index = record->pair_index;
                capture_ok = 1;
            }
        }
    } else {
        pawn = (uintptr_t)context->Esi;
        if (g_pending_pawn == 0 || pawn != g_pending_pawn ||
            (pawn & 3u) != 0) {
            ++g_ordering_error_count;
        } else if (!hot_range_readable(pawn + 0x10u, 0x34u) ||
            !hot_range_readable(pawn + 0x948u, 0x60u)) {
            ++g_pointer_fault_count;
        } else {
            index = g_record_count;
            record = &g_records[index];
            record->sequence = (uint32_t)index;
            record->pair_index = g_pending_pair_index;
            record->kind = OBS_RECORD_QUEUE;
            record->reserved = 0;
            record->pawn_id = *(const int32_t *)(pawn + 0x9a4u);
            record->current_weapon = *(const int32_t *)(pawn + 0x948u);
            record->base_current_weapon = *(const int32_t *)(pawn + 0x40u);
            record->value0 = *(const int32_t *)(pawn + 0x10u);
            record->value1 = *(const int32_t *)(pawn + 0x14u);
            record->value2 = *(const int32_t *)(pawn + 0x18u);
            record->value3 = *(const int32_t *)(pawn + 0x1cu);
            record->value4 = *(const int32_t *)(pawn + 0x20u);
            record->value5 = *(const int32_t *)(pawn + 0x24u);
            record->value6 = *(const int32_t *)(pawn + 0x28u);
            if (record->pawn_id != g_pending_pawn_id) {
                ++g_ordering_error_count;
            } else {
                _ReadWriteBarrier();
                record->committed = index + 1;
                g_record_count = index + 1;
                ++g_queue_count;
                ++g_pair_count;
                g_pending_pawn = 0;
                g_pending_pawn_id = 0;
                g_pending_pair_index = 0;
                capture_ok = 1;
            }
        }
    }
    g_handler_depth = 0;
    if (!capture_ok) {
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = g_pointer_fault_count != 0
                ? OBS_STOP_POINTER_FAULT : OBS_STOP_UNEXPECTED_ORDER;
        }
        g_state = OBS_STATE_DRAINING;
    }
    return EXCEPTION_CONTINUE_EXECUTION;
}
#pragma code_seg(pop)
/* OBS_HOT_PATH_END */

static int verify_executable_file_sha256(void) {
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

    path_length = GetModuleFileNameW(NULL, path, ARRAYSIZE(path));
    if (path_length == 0 || path_length >= ARRAYSIZE(path)) goto cleanup;
    file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (file == INVALID_HANDLE_VALUE || !GetFileSizeEx(file, &size) ||
        size.QuadPart != OBS_EXECUTABLE_SIZE) goto cleanup;
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
    ok = bytes_equal(digest, OBS_EXECUTABLE_SHA256_BYTES, sizeof(digest));
    if (ok) {
        g_executable_file = file;
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

static int verify_live_identity(void) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    if (base == NULL) return 0;
    dos = (IMAGE_DOS_HEADER *)base;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0 ||
        (uint32_t)dos->e_lfanew > 0x00100000u) return 0;
    nt = (IMAGE_NT_HEADERS32 *)(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->FileHeader.TimeDateStamp != OBS_PE_TIMESTAMP ||
        nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR32_MAGIC ||
        nt->OptionalHeader.SizeOfImage != OBS_PE_SIZE_OF_IMAGE ||
        OBS_SELECTED_RVA + OBS_SELECTED_PREBYTE_SIZE > nt->OptionalHeader.SizeOfImage ||
        OBS_QUEUE_RVA + OBS_QUEUE_PREBYTE_SIZE > nt->OptionalHeader.SizeOfImage ||
        !bytes_equal(base + OBS_SELECTED_RVA, OBS_SELECTED_PREBYTES,
            OBS_SELECTED_PREBYTE_SIZE) ||
        !bytes_equal(base + OBS_QUEUE_RVA, OBS_QUEUE_PREBYTES,
            OBS_QUEUE_PREBYTE_SIZE) || !verify_executable_file_sha256()) return 0;
    g_executable_base = base;
    g_selected_address = (uintptr_t)(base + OBS_SELECTED_RVA);
    g_queue_address = (uintptr_t)(base + OBS_QUEUE_RVA);
    return 1;
}

static int seams_unchanged(void) {
    return g_executable_base != NULL &&
        bytes_equal(g_executable_base + OBS_SELECTED_RVA, OBS_SELECTED_PREBYTES,
            OBS_SELECTED_PREBYTE_SIZE) &&
        bytes_equal(g_executable_base + OBS_QUEUE_RVA, OBS_QUEUE_PREBYTES,
            OBS_QUEUE_PREBYTE_SIZE);
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
        if (information.RegionSize > 0x7ff00000u - start) {
            end = 0x7ff00000u;
        } else {
            end = start + information.RegionSize;
        }
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

static int release_executable_file(void) {
    HANDLE file = g_executable_file;
    if (file == INVALID_HANDLE_VALUE) return g_executable_file_released != 0;
    if (!CloseHandle(file)) {
        request_stop_cold(OBS_STOP_EXECUTABLE_PIN);
        return 0;
    }
    g_executable_file = INVALID_HANDLE_VALUE;
    g_executable_file_released = 1;
    return 1;
}

static FARPROC require_lua(HMODULE module, const char *name) {
    return module == NULL ? NULL : GetProcAddress(module, name);
}

static int resolve_lua_api(void) {
    HMODULE lua = GetModuleHandleA("lua5.1.dll");
    g_lua_gettop = (lua_gettop_fn)require_lua(lua, "lua_gettop");
    g_luaL_checklstring = (luaL_checklstring_fn)require_lua(lua, "luaL_checklstring");
    g_luaL_error = (luaL_error_fn)require_lua(lua, "luaL_error");
    g_lua_createtable = (lua_createtable_fn)require_lua(lua, "lua_createtable");
    g_lua_pushboolean = (lua_pushboolean_fn)require_lua(lua, "lua_pushboolean");
    g_lua_pushcclosure = (lua_pushcclosure_fn)require_lua(lua, "lua_pushcclosure");
    g_lua_pushinteger = (lua_pushinteger_fn)require_lua(lua, "lua_pushinteger");
    g_lua_pushnil = (lua_pushnil_fn)require_lua(lua, "lua_pushnil");
    g_lua_pushstring = (lua_pushstring_fn)require_lua(lua, "lua_pushstring");
    g_lua_rawseti = (lua_rawseti_fn)require_lua(lua, "lua_rawseti");
    g_lua_setfield = (lua_setfield_fn)require_lua(lua, "lua_setfield");
    return g_lua_gettop != NULL && g_luaL_checklstring != NULL &&
        g_luaL_error != NULL && g_lua_createtable != NULL &&
        g_lua_pushboolean != NULL && g_lua_pushcclosure != NULL &&
        g_lua_pushinteger != NULL && g_lua_pushnil != NULL &&
        g_lua_pushstring != NULL && g_lua_rawseti != NULL &&
        g_lua_setfield != NULL;
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
    byte_zero(g_records, sizeof(g_records));
    g_record_count = 0;
    g_selected_count = 0;
    g_queue_count = 0;
    g_pair_count = 0;
    g_overflow_count = 0;
    g_ordering_error_count = 0;
    g_pointer_fault_count = 0;
    g_transition_mismatch_count = 0;
    g_wrong_thread_count = 0;
    g_unexpected_breakpoint_count = 0;
    g_torn_record_count = 0;
    g_stop_reason = OBS_STOP_NONE;
    g_transition_requested = 0;
    g_transition_seen = 0;
    g_handler_depth = 0;
    g_capture_started = 0;
    g_debug_armed = 0;
    g_debug_cleared = 0;
    g_veh_installed = 0;
    g_veh_removed = 0;
    g_executable_file_released = 0;
    g_seam_bytes_unchanged = 0;
    g_readable_range_count = 0;
    g_pending_pawn = 0;
    g_pending_pawn_id = 0;
    g_pending_pair_index = 0;
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
        return g_luaL_error(state, "observer arm requires one capture ID");
    }
    capture_id = g_luaL_checklstring(state, 1, &capture_length);
    if (!valid_capture_id(capture_id, capture_length)) {
        return g_luaL_error(state, "observer capture ID is invalid");
    }
    if (g_consumed != 0) {
        return g_luaL_error(state, "native observer is one-shot per process");
    }
    g_consumed = 1;
    reset_capture_state();
    byte_copy(g_capture_id, capture_id, capture_length);
    g_capture_id[capture_length] = '\0';
    g_owner_thread_id = (DWORD)__readfsdword(0x24);
    if (!verify_live_identity()) {
        request_stop_cold(OBS_STOP_IDENTITY_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "pinned selected/queue observer identity mismatch");
    }
    if (!build_readable_range_map()) {
        request_stop_cold(OBS_STOP_READABLE_MAP);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "selected/queue readable-range map failed");
    }
    g_state = OBS_STATE_VERIFIED;
    g_veh_handle = AddVectoredExceptionHandler(1, observer_selected_queue_veh);
    if (g_veh_handle == NULL) {
        request_stop_cold(OBS_STOP_TRANSITION_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "selected/queue VEH installation failed");
    }
    g_veh_installed = 1;
    if (!run_transition(OBS_TRANSITION_ARM) || g_debug_armed == 0 ||
        g_state != OBS_STATE_CAPTURING) {
        if (g_debug_armed != 0) {
            g_state = OBS_STATE_DRAINING;
            (void)run_transition(OBS_TRANSITION_CLEAR);
        }
        if (g_debug_armed == 0 && RemoveVectoredExceptionHandler(g_veh_handle) != 0) {
            g_veh_handle = NULL;
            g_veh_removed = 1;
            g_veh_installed = 0;
        }
        if (g_debug_armed == 0) (void)release_executable_file();
        g_state = g_debug_armed != 0 ? OBS_STATE_FAILED_ARMED : OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "selected/queue debug-register arm failed");
    }
    g_lua_pushboolean(state, 1);
    return 1;
}

static LONG count_torn_records(void) {
    LONG count = g_record_count;
    LONG torn = 0;
    LONG index;
    if (count < 0) return 1;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    for (index = 0; index < count; ++index) {
        if (g_records[index].committed != index + 1 ||
            g_records[index].sequence != (uint32_t)index) ++torn;
    }
    return torn;
}

static void push_snapshot(lua_State *state) {
    LONG count = g_record_count;
    LONG index;
    LONG reason = g_stop_reason;
    LONG torn = count_torn_records();
    int complete;
    if (count < 0) count = 0;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    if (torn != 0 && reason == OBS_STOP_NONE) reason = OBS_STOP_TORN_RECORD;
    g_torn_record_count = torn;
    complete = g_state == OBS_STATE_RESTORED && reason == OBS_STOP_NONE &&
        count > 0 && g_selected_count == g_queue_count &&
        g_selected_count == g_pair_count && g_pending_pawn == 0 && torn == 0 &&
        g_overflow_count == 0 && g_ordering_error_count == 0 &&
        g_pointer_fault_count == 0 && g_transition_mismatch_count == 0 &&
        g_wrong_thread_count == 0 && g_unexpected_breakpoint_count == 0 &&
        g_debug_armed == 0 && g_debug_cleared != 0 &&
        g_veh_installed == 0 && g_veh_removed != 0 &&
        g_executable_file_released != 0 && g_seam_bytes_unchanged != 0;

    g_lua_createtable(state, 0, 7);
    set_integer(state, "schema_version", 1);
    set_string(state, "kind", "native_selected_queue_hw_observer_snapshot");
    set_string(state, "observer_version", OBS_VERSION);
    set_string(state, "capture_id", g_capture_id);

    g_lua_createtable(state, 0, 10);
    set_string(state, "platform", "windows");
    set_string(state, "architecture", "x86");
    set_string(state, "build_id", OBS_BUILD_ID);
    set_string(state, "executable_sha256", OBS_EXECUTABLE_SHA256);
    set_integer(state, "executable_size", OBS_EXECUTABLE_SIZE);
    set_string(state, "inventory_sha256", OBS_INVENTORY_SHA256);
    set_string(state, "boundary_map_sha256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "hardware_breakpoint_plan_sha256", OBS_HW_PLAN_SHA256);
    set_string(state, "selected_prebytes_sha256", OBS_SELECTED_PREBYTES_SHA256);
    set_string(state, "queue_prebytes_sha256", OBS_QUEUE_PREBYTES_SHA256);
    g_lua_setfield(state, -2, "identity");

    g_lua_createtable(state, 0, 18);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "complete", complete);
    set_nullable_reason(state, reason);
    set_integer(state, "overflow_count", g_overflow_count);
    set_integer(state, "ordering_error_count", g_ordering_error_count);
    set_integer(state, "pointer_fault_count", g_pointer_fault_count);
    set_integer(state, "transition_mismatch_count", g_transition_mismatch_count);
    set_integer(state, "wrong_thread_count", g_wrong_thread_count);
    set_integer(state, "unexpected_breakpoint_count", g_unexpected_breakpoint_count);
    set_integer(state, "torn_record_count", torn);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_boolean(state, "veh_removed", g_veh_removed);
    set_boolean(state, "executable_file_released", g_executable_file_released);
    set_boolean(state, "executable_bytes_modified", 0);
    set_boolean(state, "seam_bytes_unchanged", g_seam_bytes_unchanged);
    g_lua_setfield(state, -2, "integrity");

    g_lua_createtable(state, count, 0);
    for (index = 0; index < count; ++index) {
        obs_record *record = &g_records[index];
        g_lua_createtable(state, 0, 13);
        set_string(state, "kind", record->kind == OBS_RECORD_SELECTED
            ? "selected_record" : "queued_action");
        set_integer(state, "seq", (LONG)record->sequence);
        set_integer(state, "pair_index", (LONG)record->pair_index);
        set_integer(state, "pawn_id", record->pawn_id);
        set_integer(state, "current_weapon_raw", record->current_weapon);
        set_integer(state, "base_current_weapon_raw", record->base_current_weapon);
        if (record->kind == OBS_RECORD_SELECTED) {
            set_integer(state, "ai_dest_x", record->value0);
            set_integer(state, "ai_dest_y", record->value1);
            set_integer(state, "ai_target_x", record->value2);
            set_integer(state, "ai_target_y", record->value3);
            set_integer(state, "selected_field_4_raw", record->value4);
            set_integer(state, "selected_field_5_raw", record->value5);
        } else {
            set_integer(state, "target_x", record->value0);
            set_integer(state, "target_y", record->value1);
            set_integer(state, "origin_x", record->value2);
            set_integer(state, "origin_y", record->value3);
            set_integer(state, "queued_shot_x", record->value4);
            set_integer(state, "queued_shot_y", record->value5);
            set_integer(state, "queued_skill_raw", record->value6);
        }
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, "records");

    g_lua_createtable(state, 0, 7);
    set_integer(state, "record_count", count);
    set_integer(state, "selected_count", g_selected_count);
    set_integer(state, "queue_count", g_queue_count);
    set_integer(state, "pair_count", g_pair_count);
    set_integer(state, "thread_count", g_capture_started != 0 ? 1 : 0);
    set_integer(state, "last_sequence", count - 1);
    set_boolean(state, "pending_selection", g_pending_pawn != 0);
    g_lua_setfield(state, -2, "summary");
}

static int finish_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "observer finish takes no arguments");
    }
    if (g_consumed == 0 || g_capture_started == 0) {
        return g_luaL_error(state, "native observer is not active");
    }
    if ((DWORD)__readfsdword(0x24) != g_owner_thread_id) {
        ++g_wrong_thread_count;
        request_stop_cold(OBS_STOP_WRONG_THREAD);
        return g_luaL_error(state, "observer must finish on its arm thread");
    }
    if (g_state != OBS_STATE_CAPTURING && g_state != OBS_STATE_DRAINING &&
        g_state != OBS_STATE_FAILED_ARMED) {
        return g_luaL_error(state, "native observer cannot be finished");
    }
    if (g_pending_pawn != 0) {
        ++g_ordering_error_count;
        request_stop_cold(OBS_STOP_UNEXPECTED_ORDER);
    }
    if (g_record_count == 0) request_stop_cold(OBS_STOP_EMPTY_CAPTURE);
    g_state = OBS_STATE_DRAINING;
    if (!run_transition(OBS_TRANSITION_CLEAR) || g_debug_cleared == 0 ||
        g_debug_armed != 0) {
        g_state = OBS_STATE_FAILED_ARMED;
        return g_luaL_error(state,
            "debug-register clearing failed; no checkpoint published");
    }
    if (g_veh_handle == NULL ||
        RemoveVectoredExceptionHandler(g_veh_handle) == 0) {
        request_stop_cold(OBS_STOP_VEH_REMOVE);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "VEH removal failed; no checkpoint published");
    }
    g_veh_handle = NULL;
    g_veh_installed = 0;
    g_veh_removed = 1;
    g_seam_bytes_unchanged = seams_unchanged();
    if (!g_seam_bytes_unchanged || !release_executable_file()) {
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state,
            "selected/queue observer integrity finalization failed");
    }
    g_state = OBS_STATE_RESTORED;
    push_snapshot(state);
    return 1;
}

static int status_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "observer status takes no arguments");
    }
    g_lua_createtable(state, 0, 14);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "consumed", g_consumed);
    set_boolean(state, "capture_started", g_capture_started);
    set_integer(state, "record_count", g_record_count);
    set_integer(state, "selected_count", g_selected_count);
    set_integer(state, "queue_count", g_queue_count);
    set_integer(state, "pair_count", g_pair_count);
    set_boolean(state, "pending_selection", g_pending_pawn != 0);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_integer(state, "overflow_count", g_overflow_count);
    set_integer(state, "ordering_error_count", g_ordering_error_count);
    set_nullable_reason(state, g_stop_reason);
    return 1;
}

static int pin_this_module(void) {
    HMODULE module = NULL;
    return GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_PIN,
        (LPCWSTR)(const void *)&g_module_anchor, &module) != 0;
}

__declspec(dllexport) int __cdecl luaopen_itb_observatory_selected_queue_hw_observer(
    lua_State *state) {
    if (!resolve_lua_api()) return 0;
    if (!pin_this_module()) {
        return g_luaL_error(state, "native observer module pin failed");
    }
    g_lua_createtable(state, 0, 11);
    set_string(state, "VERSION", OBS_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", "x86");
    set_string(state, "SELECTED_RVA", OBS_SELECTED_RVA_TEXT);
    set_string(state, "QUEUE_RVA", OBS_QUEUE_RVA_TEXT);
    set_string(state, "HARDWARE_BREAKPOINT_PLAN_SHA256", OBS_HW_PLAN_SHA256);
    g_lua_pushcclosure(state, arm_observer, 0);
    g_lua_setfield(state, -2, "arm");
    g_lua_pushcclosure(state, finish_observer, 0);
    g_lua_setfield(state, -2, "finish");
    g_lua_pushcclosure(state, status_observer, 0);
    g_lua_setfield(state, -2, "status");
    return 1;
}
