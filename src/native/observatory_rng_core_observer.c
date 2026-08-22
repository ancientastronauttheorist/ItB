/*
 * Build-keyed, one-shot native RNG-core observer for the ITB Observatory.
 *
 * The generated observatory_rng_core_build.inc binds this source to one exact
 * 32-bit Breach.exe, one reviewed five-byte entry patch, one caller-ID map,
 * one hook plan, and one restore manifest. Loading the DLL is inert. The only
 * exported Lua opener returns arm(), finish(), and status(); there is no
 * arbitrary address, memory, file-output, injection, or remote-control API.
 *
 * The hot hook performs no allocation, Lua/game calls, file I/O, locks,
 * clocks, serialization, or pointer publication. A fixed ring records only a
 * sequence, bounded thread slot, bounded caller ID, and the native RNG result.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <bcrypt.h>
#include <intrin.h>

#include <stddef.h>
#include <stdint.h>

#include "observatory_rng_core_build.inc"

#pragma comment(lib, "bcrypt.lib")
#pragma intrinsic(__readfsdword)
#pragma intrinsic(_InterlockedCompareExchange)
#pragma intrinsic(_InterlockedExchange)
#pragma intrinsic(_InterlockedIncrement)
#pragma intrinsic(_InterlockedDecrement)

typedef struct lua_State lua_State;
typedef int (__cdecl *lua_CFunction)(lua_State *state);
typedef ptrdiff_t lua_Integer;

typedef int (__cdecl *lua_gettop_fn)(lua_State *);
typedef const char *(__cdecl *luaL_checklstring_fn)(
    lua_State *, int, size_t *);
typedef int (__cdecl *luaL_error_fn)(lua_State *, const char *, ...);
typedef void (__cdecl *lua_createtable_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_pushboolean_fn)(lua_State *, int);
typedef void (__cdecl *lua_pushcclosure_fn)(lua_State *, lua_CFunction, int);
typedef void (__cdecl *lua_pushinteger_fn)(lua_State *, lua_Integer);
typedef void (__cdecl *lua_pushnil_fn)(lua_State *);
typedef const char *(__cdecl *lua_pushstring_fn)(lua_State *, const char *);
typedef void (__cdecl *lua_rawseti_fn)(lua_State *, int, int);
typedef void (__cdecl *lua_setfield_fn)(lua_State *, int, const char *);
typedef LONG (NTAPI *ldr_lock_loader_lock_fn)(
    ULONG, ULONG *, ULONG_PTR *);
typedef LONG (NTAPI *ldr_unlock_loader_lock_fn)(ULONG, ULONG_PTR);

#define OBS_VERSION "observatory-rng-core-observer/1"
#define OBS_RECORD_CAP 4096
#define OBS_THREAD_CAP 32
#define OBS_NESTING_CAP 8
#define OBS_THREAD_HANDLE_CAP 192
#define OBS_CAPTURE_ID_CAP 96
#define OBS_FILE_CHUNK_BYTES (64u * 1024u)
#define OBS_GATEWAY_BYTES 10
#define OBS_PATCH_BYTES 5
#define OBS_QUIESCE_ATTEMPTS 64

enum obs_state {
    OBS_STATE_DORMANT = 0,
    OBS_STATE_VERIFIED = 1,
    OBS_STATE_CAPTURING = 2,
    OBS_STATE_DRAINING = 3,
    OBS_STATE_RESTORED = 4,
    OBS_STATE_FAILED_CLEAN = 5,
    OBS_STATE_FAILED_PATCHED = 6
};

enum obs_stop_reason {
    OBS_STOP_NONE = 0,
    OBS_STOP_OVERFLOW = 1,
    OBS_STOP_UNKNOWN_CALLER = 2,
    OBS_STOP_THREAD_CAP = 3,
    OBS_STOP_NESTING_CAP = 4,
    OBS_STOP_INVALID_RESULT = 5,
    OBS_STOP_TORN_RECORD = 6,
    OBS_STOP_RESTORE_CONFLICT = 7,
    OBS_STOP_THREAD_CONTROL = 8,
    OBS_STOP_IDENTITY_MISMATCH = 9,
    OBS_STOP_EXECUTABLE_PIN = 10
};

typedef struct obs_record {
    volatile LONG committed;
    uint32_t sequence;
    uint8_t thread_slot;
    uint8_t caller_id;
    uint16_t result;
    uint32_t reserved;
} obs_record;

typedef struct obs_frame {
    uintptr_t caller_return;
    uint8_t caller_id;
    uint8_t reserved[3];
} obs_frame;

typedef struct obs_thread_context {
    volatile LONG thread_id;
    volatile LONG depth;
    obs_frame frames[OBS_NESTING_CAP];
} obs_thread_context;

typedef struct obs_suspended_threads {
    HANDLE handles[OBS_THREAD_HANDLE_CAP];
    DWORD thread_ids[OBS_THREAD_HANDLE_CAP];
    DWORD previous_counts[OBS_THREAD_HANDLE_CAP];
    size_t open_count;
    size_t suspended_count;
    int core_entry_busy;
    int observer_code_busy;
    ULONG_PTR loader_cookie;
    int loader_locked;
} obs_suspended_threads;

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
static ldr_lock_loader_lock_fn g_ldr_lock_loader_lock;
static ldr_unlock_loader_lock_fn g_ldr_unlock_loader_lock;

__declspec(align(64)) static obs_record g_records[OBS_RECORD_CAP];
__declspec(align(64)) static obs_thread_context g_threads[OBS_THREAD_CAP];
static unsigned char g_file_chunk[OBS_FILE_CHUNK_BYTES];
static unsigned char *g_executable_base;
static unsigned char *g_gateway;
static unsigned char g_patch[OBS_PATCH_BYTES];
static char g_capture_id[OBS_CAPTURE_ID_CAP + 1];
static volatile LONG g_state = OBS_STATE_DORMANT;
static volatile LONG g_consumed;
static volatile LONG g_capture_started;
static volatile LONG g_record_count;
static volatile LONG g_active_frames;
static volatile LONG g_stop_reason;
static volatile LONG g_overflow_count;
static volatile LONG g_thread_cap_count;
static volatile LONG g_nesting_cap_count;
static volatile LONG g_restore_conflict;
static volatile LONG g_patch_installed;
static volatile LONG g_core_bytes_restored;
static volatile LONG g_hook_bytes_restored;
static volatile LONG g_page_protection_restored;
static volatile LONG g_instruction_cache_flushed;
static volatile LONG g_executable_file_released;
static HANDLE g_recovery_handles[OBS_THREAD_HANDLE_CAP];
static DWORD g_recovery_previous_counts[OBS_THREAD_HANDLE_CAP];
static volatile LONG g_recovery_count;
static ULONG_PTR g_loader_recovery_cookie;
static DWORD g_loader_recovery_thread_id;
static volatile LONG g_loader_recovery_pending;
static DWORD g_original_page_protection;
static HANDLE g_executable_file = INVALID_HANDLE_VALUE;
static int g_module_anchor;

static const char *stop_reason_text(LONG reason) {
    switch (reason) {
    case OBS_STOP_OVERFLOW: return "overflow";
    case OBS_STOP_UNKNOWN_CALLER: return "unknown_caller";
    case OBS_STOP_THREAD_CAP: return "thread_cap";
    case OBS_STOP_NESTING_CAP: return "nesting_cap";
    case OBS_STOP_INVALID_RESULT: return "invalid_result";
    case OBS_STOP_TORN_RECORD: return "torn_record";
    case OBS_STOP_RESTORE_CONFLICT: return "restore_conflict";
    case OBS_STOP_THREAD_CONTROL: return "thread_control";
    case OBS_STOP_IDENTITY_MISMATCH: return "identity_mismatch";
    case OBS_STOP_EXECUTABLE_PIN: return "executable_pin";
    default: return NULL;
    }
}

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

static int bytes_equal(
    const void *left_value,
    const void *right_value,
    size_t length) {
    const volatile unsigned char *left =
        (const volatile unsigned char *)left_value;
    const volatile unsigned char *right =
        (const volatile unsigned char *)right_value;
    unsigned char difference = 0;
    size_t index;
    for (index = 0; index < length; ++index) {
        difference |= (unsigned char)(left[index] ^ right[index]);
    }
    return difference == 0;
}

static __forceinline LONG atomic_read(volatile LONG *value) {
    return _InterlockedCompareExchange(value, 0, 0);
}

static __forceinline void request_stop(LONG reason) {
    _InterlockedCompareExchange(&g_stop_reason, reason, OBS_STOP_NONE);
    _InterlockedCompareExchange(
        &g_state, OBS_STATE_DRAINING, OBS_STATE_CAPTURING);
}

static __forceinline uint8_t caller_id_for(uintptr_t caller_return) {
    uint32_t rva;
    size_t low = 0;
    size_t high = OBS_RETURN_RVA_COUNT;
    if (caller_return < (uintptr_t)g_executable_base ||
        caller_return - (uintptr_t)g_executable_base > 0xffffffffu) {
        return 0;
    }
    rva = (uint32_t)(caller_return - (uintptr_t)g_executable_base);
    while (low < high) {
        size_t middle = low + (high - low) / 2;
        uint32_t candidate = OBS_RETURN_RVAS[middle];
        if (candidate < rva) {
            low = middle + 1;
        } else {
            high = middle;
        }
    }
    if (low >= OBS_RETURN_RVA_COUNT || OBS_RETURN_RVAS[low] != rva) {
        return 0;
    }
    return (uint8_t)(low + 1);
}

static __forceinline int thread_slot_for(DWORD thread_id) {
    int index;
    for (index = 0; index < OBS_THREAD_CAP; ++index) {
        if ((DWORD)atomic_read(&g_threads[index].thread_id) == thread_id) {
            return index;
        }
    }
    for (index = 0; index < OBS_THREAD_CAP; ++index) {
        LONG previous = _InterlockedCompareExchange(
            &g_threads[index].thread_id, (LONG)thread_id, 0);
        if (previous == 0 || (DWORD)previous == thread_id) {
            return index;
        }
    }
    _InterlockedIncrement(&g_thread_cap_count);
    request_stop(OBS_STOP_THREAD_CAP);
    return -1;
}

/* OBS_HOT_PATH_BEGIN
 * Called only from the naked entry stub while all incoming registers and flags
 * are saved. It uses fixed memory and integer/interlocked operations only.
 */
static __declspec(noinline) int __cdecl observer_enter(
    uintptr_t caller_return) {
    DWORD thread_id;
    int slot;
    LONG depth;

    if (atomic_read(&g_state) != OBS_STATE_CAPTURING) {
        return 0;
    }
    _InterlockedIncrement(&g_active_frames);
    if (atomic_read(&g_state) != OBS_STATE_CAPTURING) {
        _InterlockedDecrement(&g_active_frames);
        return 0;
    }

    thread_id = (DWORD)__readfsdword(0x24);
    slot = thread_slot_for(thread_id);
    if (slot < 0) {
        _InterlockedDecrement(&g_active_frames);
        return 0;
    }
    for (;;) {
        depth = atomic_read(&g_threads[slot].depth);
        if (depth < 0 || depth >= OBS_NESTING_CAP) {
            _InterlockedIncrement(&g_nesting_cap_count);
            request_stop(OBS_STOP_NESTING_CAP);
            _InterlockedDecrement(&g_active_frames);
            return 0;
        }
        if (_InterlockedCompareExchange(
                &g_threads[slot].depth, depth + 1, depth) == depth) {
            break;
        }
    }
    g_threads[slot].frames[depth].caller_return = caller_return;
    g_threads[slot].frames[depth].caller_id = caller_id_for(caller_return);
    return 1;
}

static __forceinline LONG reserve_record(void) {
    LONG current;
    for (;;) {
        current = atomic_read(&g_record_count);
        if (current < 0 || current >= OBS_RECORD_CAP) {
            _InterlockedIncrement(&g_overflow_count);
            request_stop(OBS_STOP_OVERFLOW);
            return -1;
        }
        if (_InterlockedCompareExchange(
                &g_record_count, current + 1, current) == current) {
            return current;
        }
    }
}

static __declspec(noinline) uintptr_t __cdecl observer_exit(uint32_t result) {
    DWORD thread_id = (DWORD)__readfsdword(0x24);
    int slot = -1;
    LONG depth;
    LONG sequence;
    uintptr_t caller_return = 0;
    uint8_t caller_id = 0;
    int index;

    for (index = 0; index < OBS_THREAD_CAP; ++index) {
        if ((DWORD)atomic_read(&g_threads[index].thread_id) == thread_id) {
            slot = index;
            break;
        }
    }
    if (slot < 0) {
        request_stop(OBS_STOP_THREAD_CAP);
        return 0;
    }
    depth = atomic_read(&g_threads[slot].depth);
    if (depth <= 0 || depth > OBS_NESTING_CAP ||
        _InterlockedCompareExchange(
            &g_threads[slot].depth, depth - 1, depth) != depth) {
        request_stop(OBS_STOP_NESTING_CAP);
        return 0;
    }
    caller_return = g_threads[slot].frames[depth - 1].caller_return;
    caller_id = g_threads[slot].frames[depth - 1].caller_id;

    if (result > 32767u) {
        request_stop(OBS_STOP_INVALID_RESULT);
    } else {
        sequence = reserve_record();
        if (sequence >= 0) {
            obs_record *record = &g_records[sequence];
            record->sequence = (uint32_t)sequence;
            record->thread_slot = (uint8_t)slot;
            record->caller_id = caller_id;
            record->result = (uint16_t)result;
            record->reserved = 0;
            _InterlockedExchange(&record->committed, sequence + 1);
            if (caller_id == 0) {
                request_stop(OBS_STOP_UNKNOWN_CALLER);
            }
        }
    }
    return caller_return;
}
/* OBS_HOT_PATH_END */

static __declspec(naked) void observer_post_core(void) {
    __asm {
        pushfd
        pushad
        mov eax, dword ptr [esp + 28]
        push eax
        call observer_exit
        add esp, 4
        mov dword ptr [esp - 4], eax
        lock dec dword ptr [g_active_frames]
        popad
        popfd
        push dword ptr [esp - 40]
        ret
    }
}

static __declspec(naked) void observer_rng_core_entry(void) {
    __asm {
        pushfd
        pushad
        mov eax, dword ptr [esp + 36]
        push eax
        call observer_enter
        add esp, 4
        test eax, eax
        jz bypass_observer
        mov eax, offset observer_post_core
        mov dword ptr [esp + 36], eax
    bypass_observer:
        popad
        popfd
        jmp dword ptr [g_gateway]
    }
}

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
    if (path_length == 0 || path_length >= ARRAYSIZE(path)) {
        goto cleanup;
    }
    file = CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ,
        NULL,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN,
        NULL);
    if (file == INVALID_HANDLE_VALUE || !GetFileSizeEx(file, &size) ||
        size.QuadPart != OBS_EXECUTABLE_SIZE) {
        goto cleanup;
    }
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(
            &algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0)) ||
        !BCRYPT_SUCCESS(BCryptGetProperty(
            algorithm,
            BCRYPT_OBJECT_LENGTH,
            (PUCHAR)&object_length,
            sizeof(object_length),
            &result_length,
            0)) ||
        object_length == 0 || object_length > (1024u * 1024u)) {
        goto cleanup;
    }
    hash_object = (unsigned char *)HeapAlloc(
        GetProcessHeap(), 0, object_length);
    if (hash_object == NULL ||
        !BCRYPT_SUCCESS(BCryptCreateHash(
            algorithm, &hash, hash_object, object_length, NULL, 0, 0))) {
        goto cleanup;
    }
    for (;;) {
        if (!ReadFile(
                file,
                g_file_chunk,
                (DWORD)sizeof(g_file_chunk),
                &read_count,
                NULL)) {
            goto cleanup;
        }
        if (read_count == 0) {
            break;
        }
        if (!BCRYPT_SUCCESS(BCryptHashData(
                hash, g_file_chunk, read_count, 0))) {
            goto cleanup;
        }
    }
    if (!BCRYPT_SUCCESS(BCryptFinishHash(
            hash, digest, (ULONG)sizeof(digest), 0))) {
        goto cleanup;
    }
    ok = bytes_equal(
        digest, OBS_EXECUTABLE_SHA256_BYTES, sizeof(digest));
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

static int release_executable_file(void) {
    HANDLE file = g_executable_file;
    if (file == INVALID_HANDLE_VALUE) {
        return atomic_read(&g_executable_file_released) != 0;
    }
    if (!CloseHandle(file)) {
        request_stop(OBS_STOP_EXECUTABLE_PIN);
        return 0;
    }
    g_executable_file = INVALID_HANDLE_VALUE;
    _InterlockedExchange(&g_executable_file_released, 1);
    return 1;
}

static int validate_live_identity(void) {
    unsigned char *base = (unsigned char *)GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos;
    IMAGE_NT_HEADERS32 *nt;
    size_t index;

    if (base == NULL) return 0;
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
        OBS_RNG_CORE_RVA + OBS_RNG_CORE_SIZE >
            nt->OptionalHeader.SizeOfImage ||
        !bytes_equal(
            base + OBS_RNG_CORE_RVA,
            OBS_RNG_CORE_BYTES,
            OBS_RNG_CORE_SIZE)) {
        return 0;
    }
    for (index = 0; index < OBS_RETURN_RVA_COUNT; ++index) {
        uint32_t return_rva = OBS_RETURN_RVAS[index];
        uint32_t call_rva;
        int32_t relative;
        if (return_rva < 5 || return_rva >= nt->OptionalHeader.SizeOfImage) {
            return 0;
        }
        call_rva = return_rva - 5;
        if (base[call_rva] != 0xe8) return 0;
        byte_copy(&relative, base + call_rva + 1, sizeof(relative));
        if ((uint32_t)(return_rva + relative) != OBS_RNG_CORE_RVA) {
            return 0;
        }
    }
    if (!verify_executable_file_sha256()) return 0;
    g_executable_base = base;
    return 1;
}

static int build_gateway(void) {
    unsigned char *gateway;
    DWORD old_protection = 0;
    int32_t call_relative;
    int32_t jump_relative;
    uintptr_t state_owner = (uintptr_t)g_executable_base +
        OBS_RNG_STATE_OWNER_RVA;
    uintptr_t continuation = (uintptr_t)g_executable_base +
        OBS_RNG_CORE_RVA + OBS_PATCH_BYTES;

    if (g_gateway != NULL) return 1;
    gateway = (unsigned char *)VirtualAlloc(
        NULL,
        OBS_GATEWAY_BYTES,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE);
    if (gateway == NULL) return 0;
    call_relative = (int32_t)(state_owner - ((uintptr_t)gateway + 5));
    jump_relative = (int32_t)(continuation - ((uintptr_t)gateway + 10));
    gateway[0] = 0xe8;
    byte_copy(gateway + 1, &call_relative, sizeof(call_relative));
    gateway[5] = 0xe9;
    byte_copy(gateway + 6, &jump_relative, sizeof(jump_relative));
    if (!VirtualProtect(
            gateway, OBS_GATEWAY_BYTES, PAGE_EXECUTE_READ, &old_protection) ||
        !FlushInstructionCache(
            GetCurrentProcess(), gateway, OBS_GATEWAY_BYTES)) {
        VirtualFree(gateway, 0, MEM_RELEASE);
        return 0;
    }
    g_gateway = gateway;
    return 1;
}

static int capture_thread_ids(DWORD *ids, size_t *count_out) {
    HANDLE snapshot;
    THREADENTRY32 entry;
    DWORD process_id = GetCurrentProcessId();
    DWORD current_id = GetCurrentThreadId();
    size_t count = 0;

    snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return 0;
    byte_zero(&entry, sizeof(entry));
    entry.dwSize = sizeof(entry);
    if (!Thread32First(snapshot, &entry)) {
        CloseHandle(snapshot);
        return 0;
    }
    do {
        if (entry.th32OwnerProcessID == process_id &&
            entry.th32ThreadID != current_id) {
            if (count >= OBS_THREAD_HANDLE_CAP) {
                CloseHandle(snapshot);
                return 0;
            }
            ids[count++] = entry.th32ThreadID;
        }
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    *count_out = count;
    return 1;
}

static void sort_thread_ids(DWORD *ids, size_t count) {
    size_t index;
    for (index = 1; index < count; ++index) {
        DWORD value = ids[index];
        size_t cursor = index;
        while (cursor > 0 && ids[cursor - 1] > value) {
            ids[cursor] = ids[cursor - 1];
            --cursor;
        }
        ids[cursor] = value;
    }
}

static int stable_thread_ids(DWORD *ids, size_t *count_out) {
    DWORD second[OBS_THREAD_HANDLE_CAP];
    size_t first_count = 0;
    size_t second_count = 0;
    if (!capture_thread_ids(ids, &first_count) ||
        !capture_thread_ids(second, &second_count)) {
        return 0;
    }
    sort_thread_ids(ids, first_count);
    sort_thread_ids(second, second_count);
    if (first_count != second_count ||
        !bytes_equal(ids, second, first_count * sizeof(DWORD))) {
        return 0;
    }
    *count_out = first_count;
    return 1;
}

static int thread_has_exited(HANDLE thread) {
    DWORD exit_code = STILL_ACTIVE;
    return GetExitCodeThread(thread, &exit_code) && exit_code != STILL_ACTIVE;
}

static int retry_recovery_threads(void) {
    LONG count = atomic_read(&g_recovery_count);
    LONG retained = 0;
    LONG index;
    int clean = 1;
    for (index = 0; index < count; ++index) {
        HANDLE thread = g_recovery_handles[index];
        DWORD previous = ResumeThread(thread);
        if (previous != (DWORD)-1) {
            if (previous != g_recovery_previous_counts[index] + 1) clean = 0;
            CloseHandle(thread);
        } else if (thread_has_exited(thread)) {
            clean = 0;
            CloseHandle(thread);
        } else {
            g_recovery_handles[retained] = thread;
            g_recovery_previous_counts[retained] =
                g_recovery_previous_counts[index];
            ++retained;
        }
    }
    for (index = retained; index < count; ++index) {
        g_recovery_handles[index] = NULL;
        g_recovery_previous_counts[index] = 0;
    }
    _InterlockedExchange(&g_recovery_count, retained);
    if (!clean || retained != 0) request_stop(OBS_STOP_THREAD_CONTROL);
    return retained == 0;
}

static int retain_recovery_handle(
    HANDLE thread,
    DWORD previous_count) {
    LONG count = atomic_read(&g_recovery_count);
    if (count < 0 || count >= OBS_THREAD_HANDLE_CAP) return 0;
    g_recovery_handles[count] = thread;
    g_recovery_previous_counts[count] = previous_count;
    _InterlockedExchange(&g_recovery_count, count + 1);
    return 1;
}

static int retry_loader_unlock(void) {
    LONG status;
    if (atomic_read(&g_loader_recovery_pending) == 0) return 1;
    if (g_loader_recovery_thread_id != GetCurrentThreadId() ||
        g_loader_recovery_cookie == 0) {
        request_stop(OBS_STOP_THREAD_CONTROL);
        return 0;
    }
    status = g_ldr_unlock_loader_lock(0, g_loader_recovery_cookie);
    if (status < 0) {
        request_stop(OBS_STOP_THREAD_CONTROL);
        return 0;
    }
    g_loader_recovery_cookie = 0;
    g_loader_recovery_thread_id = 0;
    _InterlockedExchange(&g_loader_recovery_pending, 0);
    return 1;
}

static void retain_loader_unlock(ULONG_PTR cookie) {
    g_loader_recovery_cookie = cookie;
    g_loader_recovery_thread_id = GetCurrentThreadId();
    _InterlockedExchange(&g_loader_recovery_pending, 1);
    request_stop(OBS_STOP_THREAD_CONTROL);
}

static int close_and_resume_threads(obs_suspended_threads *threads) {
    int ok = 1;
    size_t index = threads->suspended_count;
    while (index > 0) {
        DWORD previous;
        int attempt;
        --index;
        previous = (DWORD)-1;
        for (attempt = 0; attempt < 3 && previous == (DWORD)-1; ++attempt) {
            previous = ResumeThread(threads->handles[index]);
        }
        if (previous == (DWORD)-1) {
            ok = 0;
            if (thread_has_exited(threads->handles[index])) {
                CloseHandle(threads->handles[index]);
                threads->handles[index] = NULL;
            } else if (retain_recovery_handle(
                           threads->handles[index],
                           threads->previous_counts[index])) {
                threads->handles[index] = NULL;
            } else {
                /* The recovery store begins empty and is as large as the
                 * suspended set, so this is reachable only after corruption.
                 * Never discard the sole recovery handle even then. */
                do {
                    previous = ResumeThread(threads->handles[index]);
                    if (previous == (DWORD)-1 &&
                        !thread_has_exited(threads->handles[index])) {
                        SwitchToThread();
                    }
                } while (previous == (DWORD)-1 &&
                         !thread_has_exited(threads->handles[index]));
                CloseHandle(threads->handles[index]);
                threads->handles[index] = NULL;
            }
        } else if (previous != threads->previous_counts[index] + 1) {
            /* ResumeThread succeeded and removed one suspend, but another
             * owner changed the count during the transaction. */
            ok = 0;
        }
    }
    for (index = 0; index < threads->open_count; ++index) {
        if (threads->handles[index] != NULL) {
            if (!CloseHandle(threads->handles[index])) ok = 0;
            threads->handles[index] = NULL;
        }
    }
    if (threads->loader_locked) {
        LONG status = -1;
        int attempt;
        for (attempt = 0; attempt < 3 && status < 0; ++attempt) {
            status = g_ldr_unlock_loader_lock(0, threads->loader_cookie);
        }
        if (status < 0) {
            retain_loader_unlock(threads->loader_cookie);
            ok = 0;
        }
        threads->loader_locked = 0;
        threads->loader_cookie = 0;
    }
    threads->open_count = 0;
    threads->suspended_count = 0;
    if (!ok) request_stop(OBS_STOP_THREAD_CONTROL);
    return ok;
}

static int suspend_other_threads(obs_suspended_threads *result) {
    DWORD ids[OBS_THREAD_HANDLE_CAP];
    DWORD verified_ids[OBS_THREAD_HANDLE_CAP];
    size_t id_count = 0;
    size_t verified_count = 0;
    size_t index;
    ULONG disposition = 0;
    LONG loader_status;
    uintptr_t core_start = (uintptr_t)g_executable_base + OBS_RNG_CORE_RVA;
    uintptr_t core_end = core_start + OBS_PATCH_BYTES;
    uintptr_t observer_start = (uintptr_t)&observer_post_core;
    uintptr_t observer_end = observer_start + 64;

    byte_zero(result, sizeof(*result));
    if (!retry_loader_unlock() ||
        !retry_recovery_threads() ||
        g_ldr_lock_loader_lock == NULL ||
        g_ldr_unlock_loader_lock == NULL) {
        return 0;
    }
    loader_status = g_ldr_lock_loader_lock(
        0, &disposition, &result->loader_cookie);
    if (loader_status < 0 || disposition != 1 ||
        result->loader_cookie == 0) {
        if (loader_status >= 0 && result->loader_cookie != 0) {
            LONG unlock_status = -1;
            int attempt;
            for (attempt = 0;
                 attempt < 3 && unlock_status < 0;
                 ++attempt) {
                unlock_status = g_ldr_unlock_loader_lock(
                    0, result->loader_cookie);
            }
            if (unlock_status < 0) {
                retain_loader_unlock(result->loader_cookie);
            }
        }
        result->loader_cookie = 0;
        return 0;
    }
    result->loader_locked = 1;
    if (!stable_thread_ids(ids, &id_count)) {
        close_and_resume_threads(result);
        return 0;
    }
    for (index = 0; index < id_count; ++index) {
        HANDLE thread = OpenThread(
            THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT |
                THREAD_QUERY_INFORMATION,
            FALSE,
            ids[index]);
        if (thread == NULL) {
            close_and_resume_threads(result);
            return 0;
        }
        result->handles[result->open_count] = thread;
        result->thread_ids[result->open_count] = ids[index];
        result->previous_counts[result->open_count] = 0;
        ++result->open_count;
    }
    if (!capture_thread_ids(verified_ids, &verified_count)) {
        close_and_resume_threads(result);
        return 0;
    }
    sort_thread_ids(verified_ids, verified_count);
    if (verified_count != id_count ||
        !bytes_equal(ids, verified_ids, id_count * sizeof(DWORD))) {
        close_and_resume_threads(result);
        return 0;
    }
    for (index = 0; index < result->open_count; ++index) {
        DWORD previous = SuspendThread(result->handles[index]);
        CONTEXT context;
        if (previous == (DWORD)-1) {
            close_and_resume_threads(result);
            return 0;
        }
        result->previous_counts[index] = previous;
        ++result->suspended_count;
        byte_zero(&context, sizeof(context));
        context.ContextFlags = CONTEXT_CONTROL;
        if (!GetThreadContext(result->handles[index], &context)) {
            close_and_resume_threads(result);
            return 0;
        }
        if ((uintptr_t)context.Eip >= core_start &&
            (uintptr_t)context.Eip < core_end) {
            result->core_entry_busy = 1;
        }
        if ((uintptr_t)context.Eip >= observer_start &&
            (uintptr_t)context.Eip < observer_end) {
            result->observer_code_busy = 1;
        }
    }
    return 1;
}

static int prepare_patch(void) {
    int32_t relative = (int32_t)(
        (uintptr_t)&observer_rng_core_entry -
        ((uintptr_t)g_executable_base + OBS_RNG_CORE_RVA + OBS_PATCH_BYTES));
    g_patch[0] = 0xe9;
    byte_copy(g_patch + 1, &relative, sizeof(relative));
    return 1;
}

static int page_protection_is_original(void) {
    unsigned char *entry = g_executable_base + OBS_RNG_CORE_RVA;
    MEMORY_BASIC_INFORMATION memory;
    if (g_original_page_protection == 0 ||
        VirtualQuery(entry, &memory, sizeof(memory)) != sizeof(memory)) {
        return 0;
    }
    return memory.State == MEM_COMMIT &&
        memory.Protect == g_original_page_protection;
}

static int write_exact_entry(
    const unsigned char *expected,
    const unsigned char *replacement,
    int preserve_current_protection) {
    unsigned char *entry = g_executable_base + OBS_RNG_CORE_RVA;
    DWORD old_protection = 0;
    DWORD ignored = 0;
    DWORD final_protection;
    int cache_ok;
    int protection_ok = 0;
    int attempt;

    if (!bytes_equal(entry, expected, OBS_PATCH_BYTES) ||
        !VirtualProtect(
            entry, OBS_PATCH_BYTES, PAGE_EXECUTE_READWRITE, &old_protection)) {
        return 0;
    }
    if (preserve_current_protection) {
        g_original_page_protection = old_protection;
    }
    final_protection = preserve_current_protection
        ? old_protection
        : g_original_page_protection;
    byte_copy(entry, replacement, OBS_PATCH_BYTES);
    for (attempt = 0; attempt < 3 && !protection_ok; ++attempt) {
        protection_ok = VirtualProtect(
            entry, OBS_PATCH_BYTES, final_protection, &ignored) != 0;
    }
    cache_ok = FlushInstructionCache(
        GetCurrentProcess(), entry, OBS_PATCH_BYTES) != 0;
    return cache_ok && protection_ok &&
        bytes_equal(entry, replacement, OBS_PATCH_BYTES);
}

static int restore_entry_while_suspended(void) {
    unsigned char *entry = g_executable_base + OBS_RNG_CORE_RVA;
    DWORD ignored = 0;
    int entry_known = 0;
    int cache_ok;
    int core_ok;
    int protection_ok;
    int attempt;

    if (bytes_equal(entry, g_patch, OBS_PATCH_BYTES)) {
        (void)write_exact_entry(g_patch, OBS_RNG_CORE_BYTES, 0);
    }
    if (bytes_equal(entry, OBS_RNG_CORE_BYTES, OBS_PATCH_BYTES)) {
        entry_known = 1;
    }
    for (attempt = 0;
         attempt < 3 && !page_protection_is_original();
         ++attempt) {
        (void)VirtualProtect(
            entry,
            OBS_PATCH_BYTES,
            g_original_page_protection,
            &ignored);
    }
    cache_ok = FlushInstructionCache(
        GetCurrentProcess(), entry, OBS_RNG_CORE_SIZE) != 0;
    core_ok = entry_known &&
        bytes_equal(entry, OBS_RNG_CORE_BYTES, OBS_RNG_CORE_SIZE);
    protection_ok = page_protection_is_original();
    _InterlockedExchange(&g_instruction_cache_flushed, cache_ok != 0);
    _InterlockedExchange(&g_core_bytes_restored, core_ok != 0);
    _InterlockedExchange(&g_hook_bytes_restored, core_ok != 0);
    _InterlockedExchange(&g_page_protection_restored, protection_ok != 0);
    if (core_ok) _InterlockedExchange(&g_patch_installed, 0);
    return core_ok && protection_ok && cache_ok;
}

static int arm_entry_patch(void) {
    int attempt;
    prepare_patch();
    for (attempt = 0; attempt < OBS_QUIESCE_ATTEMPTS; ++attempt) {
        obs_suspended_threads threads;
        int wrote;
        int resumed;
        if (atomic_read(&g_stop_reason) != OBS_STOP_NONE) return 0;
        if (!suspend_other_threads(&threads)) {
            SwitchToThread();
            continue;
        }
        if (threads.core_entry_busy || threads.observer_code_busy) {
            if (!close_and_resume_threads(&threads)) return 0;
            SwitchToThread();
            continue;
        }
        if (!bytes_equal(
                g_executable_base + OBS_RNG_CORE_RVA,
                OBS_RNG_CORE_BYTES,
                OBS_RNG_CORE_SIZE)) {
            close_and_resume_threads(&threads);
            request_stop(OBS_STOP_IDENTITY_MISMATCH);
            return 0;
        }
        wrote = write_exact_entry(OBS_RNG_CORE_BYTES, g_patch, 1);
        if (wrote) {
            _InterlockedExchange(&g_patch_installed, 1);
            _InterlockedExchange(&g_state, OBS_STATE_CAPTURING);
        } else if (bytes_equal(
                       g_executable_base + OBS_RNG_CORE_RVA,
                       g_patch,
                       OBS_PATCH_BYTES)) {
            _InterlockedExchange(&g_patch_installed, 1);
            _InterlockedExchange(&g_state, OBS_STATE_DRAINING);
            if (restore_entry_while_suspended()) {
                _InterlockedExchange(&g_state, OBS_STATE_FAILED_CLEAN);
            } else {
                _InterlockedExchange(&g_state, OBS_STATE_FAILED_PATCHED);
            }
        } else if (bytes_equal(
                       g_executable_base + OBS_RNG_CORE_RVA,
                       OBS_RNG_CORE_BYTES,
                       OBS_PATCH_BYTES)) {
            _InterlockedExchange(&g_state, OBS_STATE_FAILED_CLEAN);
        } else {
            _InterlockedExchange(&g_restore_conflict, 1);
            _InterlockedExchange(&g_state, OBS_STATE_FAILED_PATCHED);
        }
        resumed = close_and_resume_threads(&threads);
        if (!wrote || !resumed) {
            request_stop(OBS_STOP_THREAD_CONTROL);
            return 0;
        }
        return 1;
    }
    request_stop(OBS_STOP_THREAD_CONTROL);
    return 0;
}

static int restore_entry_patch(void) {
    int attempt;
    _InterlockedExchange(&g_state, OBS_STATE_DRAINING);
    for (attempt = 0; attempt < OBS_QUIESCE_ATTEMPTS; ++attempt) {
        obs_suspended_threads threads;
        int restored;
        int resumed;
        if (!suspend_other_threads(&threads)) {
            SwitchToThread();
            continue;
        }
        if (threads.core_entry_busy || threads.observer_code_busy ||
            atomic_read(&g_active_frames) != 0) {
            close_and_resume_threads(&threads);
            SwitchToThread();
            continue;
        }
        if (!bytes_equal(
                g_executable_base + OBS_RNG_CORE_RVA,
                g_patch,
                OBS_PATCH_BYTES) &&
            !bytes_equal(
                g_executable_base + OBS_RNG_CORE_RVA,
                OBS_RNG_CORE_BYTES,
                OBS_PATCH_BYTES)) {
            _InterlockedExchange(&g_restore_conflict, 1);
            request_stop(OBS_STOP_RESTORE_CONFLICT);
            close_and_resume_threads(&threads);
            _InterlockedExchange(&g_state, OBS_STATE_FAILED_PATCHED);
            return 0;
        }
        g_instruction_cache_flushed = 0;
        g_core_bytes_restored = 0;
        g_hook_bytes_restored = 0;
        g_page_protection_restored = 0;
        restored = restore_entry_while_suspended();
        resumed = close_and_resume_threads(&threads);
        if (!restored || !resumed) {
            request_stop(OBS_STOP_THREAD_CONTROL);
            _InterlockedExchange(
                &g_state,
                atomic_read(&g_patch_installed)
                    ? OBS_STATE_FAILED_PATCHED
                    : OBS_STATE_FAILED_CLEAN);
            return 0;
        }
        _InterlockedExchange(&g_state, OBS_STATE_RESTORED);
        return 1;
    }
    request_stop(OBS_STOP_THREAD_CONTROL);
    _InterlockedExchange(
        &g_state,
        atomic_read(&g_patch_installed)
            ? OBS_STATE_FAILED_PATCHED
            : OBS_STATE_FAILED_CLEAN);
    return 0;
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
    g_lua_pushstring = (lua_pushstring_fn)require_lua(
        lua, "lua_pushstring");
    g_lua_rawseti = (lua_rawseti_fn)require_lua(lua, "lua_rawseti");
    g_lua_setfield = (lua_setfield_fn)require_lua(lua, "lua_setfield");
    return g_lua_gettop != NULL && g_luaL_checklstring != NULL &&
        g_luaL_error != NULL && g_lua_createtable != NULL &&
        g_lua_pushboolean != NULL && g_lua_pushcclosure != NULL &&
        g_lua_pushinteger != NULL && g_lua_pushnil != NULL &&
        g_lua_pushstring != NULL && g_lua_rawseti != NULL &&
        g_lua_setfield != NULL;
}

static int resolve_loader_api(void) {
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    g_ldr_lock_loader_lock = (ldr_lock_loader_lock_fn)require_lua(
        ntdll, "LdrLockLoaderLock");
    g_ldr_unlock_loader_lock = (ldr_unlock_loader_lock_fn)require_lua(
        ntdll, "LdrUnlockLoaderLock");
    return g_ldr_lock_loader_lock != NULL &&
        g_ldr_unlock_loader_lock != NULL;
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
    if (text == NULL) {
        g_lua_pushnil(state);
    } else {
        g_lua_pushstring(state, text);
    }
    g_lua_setfield(state, -2, "stopped_reason");
}

static const char *state_text(LONG state) {
    switch (state) {
    case OBS_STATE_DORMANT: return "dormant";
    case OBS_STATE_VERIFIED: return "verified";
    case OBS_STATE_CAPTURING: return "capturing";
    case OBS_STATE_DRAINING: return "draining";
    case OBS_STATE_RESTORED: return "restored";
    case OBS_STATE_FAILED_CLEAN: return "failed_clean";
    default: return "failed_patched";
    }
}

static int valid_capture_id(const char *value, size_t length) {
    size_t index;
    if (length == 0 || length > OBS_CAPTURE_ID_CAP ||
        value[0] < 'a' || value[0] > 'z') {
        return 0;
    }
    for (index = 1; index < length; ++index) {
        unsigned char byte = (unsigned char)value[index];
        if (!((byte >= 'a' && byte <= 'z') ||
              (byte >= '0' && byte <= '9') ||
              byte == '_' || byte == '.' || byte == '-')) {
            return 0;
        }
    }
    return 1;
}

static void reset_capture_state(void) {
    byte_zero(g_records, sizeof(g_records));
    byte_zero(g_threads, sizeof(g_threads));
    g_record_count = 0;
    g_capture_started = 0;
    g_active_frames = 0;
    g_stop_reason = OBS_STOP_NONE;
    g_overflow_count = 0;
    g_thread_cap_count = 0;
    g_nesting_cap_count = 0;
    g_restore_conflict = 0;
    g_patch_installed = 0;
    g_core_bytes_restored = 0;
    g_hook_bytes_restored = 0;
    g_page_protection_restored = 0;
    g_instruction_cache_flushed = 0;
    g_executable_file_released = 0;
    g_original_page_protection = 0;
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
    if (_InterlockedCompareExchange(&g_consumed, 1, 0) != 0) {
        return g_luaL_error(state, "native observer is one-shot per process");
    }
    reset_capture_state();
    byte_copy(g_capture_id, capture_id, capture_length);
    g_capture_id[capture_length] = '\0';
    if (!validate_live_identity() || !build_gateway()) {
        request_stop(OBS_STOP_IDENTITY_MISMATCH);
        (void)release_executable_file();
        _InterlockedExchange(&g_state, OBS_STATE_FAILED_CLEAN);
        return g_luaL_error(state, "pinned native observer identity mismatch");
    }
    _InterlockedExchange(&g_state, OBS_STATE_VERIFIED);
    if (!arm_entry_patch()) {
        if (atomic_read(&g_patch_installed) != 0) {
            (void)restore_entry_patch();
        }
        if (atomic_read(&g_patch_installed) == 0) {
            (void)release_executable_file();
        }
        _InterlockedExchange(
            &g_state,
            atomic_read(&g_patch_installed)
                ? OBS_STATE_FAILED_PATCHED
                : OBS_STATE_FAILED_CLEAN);
        return g_luaL_error(state, "native observer arm transaction failed");
    }
    _InterlockedExchange(&g_capture_started, 1);
    g_lua_pushboolean(state, 1);
    return 1;
}

static LONG torn_record_count(void) {
    LONG count = atomic_read(&g_record_count);
    LONG torn = 0;
    LONG index;
    if (count < 0) return 1;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    for (index = 0; index < count; ++index) {
        if (atomic_read(&g_records[index].committed) != index + 1 ||
            g_records[index].sequence != (uint32_t)index) {
            ++torn;
        }
    }
    return torn;
}

static LONG unknown_caller_count(void) {
    LONG count = atomic_read(&g_record_count);
    LONG unknown = 0;
    LONG index;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    for (index = 0; index < count; ++index) {
        if (atomic_read(&g_records[index].committed) == index + 1 &&
            g_records[index].caller_id == 0) {
            ++unknown;
        }
    }
    return unknown;
}

static LONG observed_thread_count(void) {
    LONG count = 0;
    int index;
    for (index = 0; index < OBS_THREAD_CAP; ++index) {
        if (atomic_read(&g_threads[index].thread_id) != 0) ++count;
    }
    return count;
}

static void push_snapshot(lua_State *state) {
    LONG count = atomic_read(&g_record_count);
    LONG torn = torn_record_count();
    LONG unknown = unknown_caller_count();
    LONG reason = atomic_read(&g_stop_reason);
    LONG current = atomic_read(&g_state);
    LONG active = atomic_read(&g_active_frames);
    int complete;
    LONG index;

    if (count < 0) count = 0;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    if (torn > 0 && reason == OBS_STOP_NONE) {
        reason = OBS_STOP_TORN_RECORD;
        _InterlockedCompareExchange(
            &g_stop_reason, reason, OBS_STOP_NONE);
    }
    complete = current == OBS_STATE_RESTORED && reason == OBS_STOP_NONE &&
        atomic_read(&g_overflow_count) == 0 && unknown == 0 && torn == 0 &&
        atomic_read(&g_thread_cap_count) == 0 &&
        atomic_read(&g_nesting_cap_count) == 0 &&
        atomic_read(&g_restore_conflict) == 0 &&
        atomic_read(&g_patch_installed) == 0 && active == 0 &&
        atomic_read(&g_core_bytes_restored) != 0 &&
        atomic_read(&g_hook_bytes_restored) != 0 &&
        atomic_read(&g_page_protection_restored) != 0 &&
        atomic_read(&g_instruction_cache_flushed) != 0 &&
        atomic_read(&g_executable_file_released) != 0 &&
        atomic_read(&g_recovery_count) == 0 &&
        atomic_read(&g_loader_recovery_pending) == 0;
    g_lua_createtable(state, 0, 8);
    set_integer(state, "schema_version", 1);
    set_string(state, "kind", "native_rng_core_observer_snapshot");
    set_string(state, "observer_version", OBS_VERSION);
    set_string(state, "capture_id", g_capture_id);

    g_lua_createtable(state, 0, 8);
    set_string(state, "platform", "windows");
    set_string(state, "architecture", "x86");
    set_string(state, "executable_sha256", OBS_EXECUTABLE_SHA256);
    set_integer(state, "executable_size", OBS_EXECUTABLE_SIZE);
    set_string(state, "build_id", OBS_BUILD_ID);
    set_string(state, "inventory_sha256", OBS_INVENTORY_SHA256);
    set_string(state, "boundary_map_sha256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "rng_return_map_sha256", OBS_RNG_RETURN_MAP_SHA256);
    set_string(state, "hook_plan_sha256", OBS_HOOK_PLAN_SHA256);
    set_string(
        state, "restore_manifest_sha256", OBS_RESTORE_MANIFEST_SHA256);
    g_lua_setfield(state, -2, "identity");

    g_lua_createtable(state, 0, 19);
    set_string(state, "state", state_text(current));
    set_integer(state, "overflow_count", atomic_read(&g_overflow_count));
    set_integer(state, "unknown_caller_count", unknown);
    set_integer(state, "torn_record_count", torn);
    set_integer(state, "thread_cap_count", atomic_read(&g_thread_cap_count));
    set_integer(state, "nesting_cap_count", atomic_read(&g_nesting_cap_count));
    set_integer(state, "thread_recovery_count", atomic_read(&g_recovery_count));
    set_boolean(
        state,
        "loader_lock_recovery_pending",
        atomic_read(&g_loader_recovery_pending));
    set_boolean(state, "restore_conflict", atomic_read(&g_restore_conflict));
    set_boolean(state, "patch_installed", atomic_read(&g_patch_installed));
    set_integer(state, "active_frames", active);
    set_boolean(
        state, "core_bytes_restored", atomic_read(&g_core_bytes_restored));
    set_boolean(
        state, "hook_bytes_restored", atomic_read(&g_hook_bytes_restored));
    set_boolean(
        state,
        "page_protection_restored",
        atomic_read(&g_page_protection_restored));
    set_boolean(
        state,
        "instruction_cache_flushed",
        atomic_read(&g_instruction_cache_flushed));
    set_boolean(
        state,
        "executable_file_released",
        atomic_read(&g_executable_file_released));
    g_lua_createtable(state, 0, 1);
    if (atomic_read(&g_core_bytes_restored) != 0) {
        set_string(state, "rng_core", OBS_RNG_CORE_SHA256);
    }
    g_lua_setfield(state, -2, "post_restore_hashes");
    set_nullable_reason(state, reason);
    set_boolean(state, "complete", complete);
    g_lua_setfield(state, -2, "integrity");

    g_lua_createtable(state, count, 0);
    for (index = 0; index < count; ++index) {
        obs_record *record = &g_records[index];
        g_lua_createtable(state, 0, 5);
        set_string(state, "kind", "rng_core");
        set_integer(state, "seq", (LONG)record->sequence);
        set_integer(state, "thread_slot", (LONG)record->thread_slot);
        set_integer(state, "caller_id", (LONG)record->caller_id);
        set_integer(state, "result", (LONG)record->result);
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, "records");

    g_lua_createtable(state, 0, 3);
    set_integer(state, "record_count", count);
    set_integer(state, "thread_count", observed_thread_count());
    set_integer(state, "last_sequence", count - 1);
    g_lua_setfield(state, -2, "summary");
}

static int finish_observer(lua_State *state) {
    LONG current;
    int attempt;
    int restored = 0;
    int recovered = 0;
    int loader_recovered = 0;
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "observer finish takes no arguments");
    }
    if (atomic_read(&g_consumed) == 0) {
        return g_luaL_error(state, "native observer is not active");
    }
    current = atomic_read(&g_state);
    if (current != OBS_STATE_CAPTURING &&
        current != OBS_STATE_DRAINING &&
        current != OBS_STATE_FAILED_CLEAN &&
        current != OBS_STATE_FAILED_PATCHED &&
        !(current == OBS_STATE_RESTORED &&
          (atomic_read(&g_executable_file_released) == 0 ||
           atomic_read(&g_recovery_count) != 0 ||
           atomic_read(&g_loader_recovery_pending) != 0))) {
        return g_luaL_error(state, "native observer cannot be finished");
    }
    for (attempt = 0;
         attempt < 3 && (!restored || !recovered || !loader_recovered);
         ++attempt) {
        restored = atomic_read(&g_patch_installed) == 0 &&
            (atomic_read(&g_capture_started) == 0 ||
             atomic_read(&g_state) == OBS_STATE_RESTORED);
        if (!restored) restored = restore_entry_patch();
        recovered = retry_recovery_threads();
        loader_recovered = retry_loader_unlock();
    }
    if (atomic_read(&g_patch_installed) == 0) {
        (void)release_executable_file();
    }
    if (atomic_read(&g_capture_started) == 0) {
        return g_luaL_error(
            state,
            atomic_read(&g_patch_installed) == 0 &&
                    atomic_read(&g_recovery_count) == 0 &&
                    atomic_read(&g_loader_recovery_pending) == 0 &&
                    restored && recovered && loader_recovered
                ? "native observer arm failed cleanly; no checkpoint exists"
                : "native observer arm cleanup remains incomplete");
    }
    if (!restored || !recovered || !loader_recovered ||
        atomic_read(&g_state) != OBS_STATE_RESTORED ||
        atomic_read(&g_patch_installed) != 0 ||
        atomic_read(&g_loader_recovery_pending) != 0 ||
        !release_executable_file()) {
        return g_luaL_error(
            state,
            "native observer restoration failed; no checkpoint published");
    }
    push_snapshot(state);
    return 1;
}

static int status_observer(lua_State *state) {
    LONG current;
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "observer status takes no arguments");
    }
    current = atomic_read(&g_state);
    g_lua_createtable(state, 0, 8);
    set_string(state, "state", state_text(current));
    set_boolean(state, "consumed", atomic_read(&g_consumed));
    set_boolean(state, "capture_started", atomic_read(&g_capture_started));
    set_integer(state, "record_count", atomic_read(&g_record_count));
    set_integer(state, "active_frames", atomic_read(&g_active_frames));
    set_integer(state, "overflow_count", atomic_read(&g_overflow_count));
    set_nullable_reason(state, atomic_read(&g_stop_reason));
    set_boolean(
        state, "hook_bytes_restored", atomic_read(&g_hook_bytes_restored));
    set_boolean(state, "patch_installed", atomic_read(&g_patch_installed));
    set_integer(
        state, "thread_recovery_count", atomic_read(&g_recovery_count));
    set_boolean(
        state,
        "loader_lock_recovery_pending",
        atomic_read(&g_loader_recovery_pending));
    set_boolean(
        state,
        "executable_file_released",
        atomic_read(&g_executable_file_released));
    return 1;
}

static int pin_this_module(void) {
    HMODULE module = NULL;
    return GetModuleHandleExW(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
            GET_MODULE_HANDLE_EX_FLAG_PIN,
        (LPCWSTR)(const void *)&g_module_anchor,
        &module) != 0;
}

__declspec(dllexport) int __cdecl luaopen_itb_observatory_rng_core_observer(
    lua_State *state) {
    if (!resolve_lua_api() || !resolve_loader_api()) return 0;
    if (!pin_this_module()) {
        return g_luaL_error(state, "native observer module pin failed");
    }
    g_lua_createtable(state, 0, 12);
    set_string(state, "VERSION", OBS_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", "x86");
    set_string(state, "RNG_CORE_RVA", OBS_RNG_CORE_RVA_TEXT);
    set_string(state, "RNG_CORE_REGION_SHA256", OBS_RNG_CORE_SHA256);
    set_string(state, "RNG_RETURN_MAP_SHA256", OBS_RNG_RETURN_MAP_SHA256);
    set_string(state, "HOOK_PLAN_SHA256", OBS_HOOK_PLAN_SHA256);
    set_string(
        state, "RESTORE_MANIFEST_SHA256", OBS_RESTORE_MANIFEST_SHA256);
    g_lua_pushcclosure(state, arm_observer, 0);
    g_lua_setfield(state, -2, "arm");
    g_lua_pushcclosure(state, finish_observer, 0);
    g_lua_setfield(state, -2, "finish");
    g_lua_pushcclosure(state, status_observer, 0);
    g_lua_setfield(state, -2, "status");
    return 1;
}
