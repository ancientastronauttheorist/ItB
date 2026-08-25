/*
 * Build-keyed, one-shot enemy-tournament observer for ITB.
 *
 * This source deliberately reuses the already published selected/queue
 * observer runtime as an immutable compile-time dependency.  Its old Lua
 * opener is renamed and made non-exported; no old artifact is rewritten.
 * The new VEH adds one selector-entry breakpoint, captures the complete
 * ordered 24-byte record vector plus the pre-selector CRT state, then binds
 * the selected record to the immediate queue commit.  It changes no image
 * bytes and performs no calls, allocation, I/O, locks, or clocks while hot.
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <intrin.h>
#include <stddef.h>
#include <stdint.h>
#undef WIN32_LEAN_AND_MEAN

/* Keep the included historical opener out of this DLL's export table. */
#define dllexport noinline
#define luaopen_itb_observatory_selected_queue_hw_observer \
    observatory_selected_queue_base_opener_unexported
#include "observatory_selected_queue_hw_observer.c"
#undef luaopen_itb_observatory_selected_queue_hw_observer
#undef dllexport

#define TOURNAMENT_VERSION "observatory-enemy-tournament-hw-observer/1"
#define TOURNAMENT_STAGE_WAIT_SELECTOR 0
#define TOURNAMENT_STAGE_WAIT_SELECTED 1
#define TOURNAMENT_STAGE_WAIT_QUEUE 2
#define TOURNAMENT_STAGE_COMPLETE 3
#define TOURNAMENT_DR7_ARM 0x00000015u
#define TOURNAMENT_DR7_AFTER_SELECTOR 0x00000014u
#define TOURNAMENT_DR7_QUEUE_ONLY 0x00000010u
#define TOURNAMENT_RNG_STATE_OFFSET 0x18u

typedef unsigned char *(__cdecl *tournament_rng_state_owner_fn)(void);

typedef struct tournament_candidate_record {
    volatile LONG committed;
    uint32_t sequence;
    int32_t destination_x;
    int32_t destination_y;
    int32_t target_x;
    int32_t target_y;
    int32_t target_score;
    int32_t positioning_score;
} tournament_candidate_record;

__declspec(align(64)) static tournament_candidate_record
    g_tournament_candidates[OBS_RECORD_CAP];
static volatile LONG g_tournament_stage;
static volatile LONG g_tournament_selector_count;
static volatile LONG g_tournament_candidate_count;
static volatile LONG g_tournament_torn_candidate_count;
static uintptr_t g_tournament_selector_address;
static uintptr_t g_tournament_rng_state_address;
static uintptr_t g_tournament_pending_context;
static uintptr_t g_tournament_pending_ai;
static uint32_t g_tournament_rng_before;
static uint32_t g_tournament_rng_after;
static int32_t g_tournament_pawn_id;
static int32_t g_tournament_current_weapon;
static int32_t g_tournament_base_current_weapon;
static int32_t g_tournament_board_width;
static int32_t g_tournament_board_height;
static int32_t g_tournament_interior_favorable;

/* TOURNAMENT_HOT_PATH_BEGIN
 * The complete dedicated section calls no function and publishes no pointer.
 */
#pragma code_seg(push, ".obshot")
static __forceinline int tournament_debug_state_matches(PCONTEXT context) {
    LONG stage = g_tournament_stage;
    if (stage == TOURNAMENT_STAGE_WAIT_SELECTOR) {
        return context->Dr0 == (DWORD)g_tournament_selector_address &&
            context->Dr1 == (DWORD)g_selected_address &&
            context->Dr2 == (DWORD)g_queue_address &&
            context->Dr3 == 0 && context->Dr7 == TOURNAMENT_DR7_ARM;
    }
    if (stage == TOURNAMENT_STAGE_WAIT_SELECTED) {
        return context->Dr0 == 0 &&
            context->Dr1 == (DWORD)g_selected_address &&
            context->Dr2 == (DWORD)g_queue_address &&
            context->Dr3 == 0 &&
            context->Dr7 == TOURNAMENT_DR7_AFTER_SELECTOR;
    }
    if (stage == TOURNAMENT_STAGE_WAIT_QUEUE) {
        return context->Dr0 == 0 && context->Dr1 == 0 &&
            context->Dr2 == (DWORD)g_queue_address &&
            context->Dr3 == 0 &&
            context->Dr7 == TOURNAMENT_DR7_QUEUE_ONLY;
    }
    return context->Dr0 == 0 && context->Dr1 == 0 &&
        context->Dr2 == 0 && context->Dr3 == 0 && context->Dr7 == 0;
}

LONG CALLBACK observer_enemy_tournament_veh(PEXCEPTION_POINTERS pointers) {
    PEXCEPTION_RECORD exception_record;
    PCONTEXT context;
    DWORD thread_id;
    DWORD code;
    DWORD ours;
    uintptr_t eip;
    uintptr_t context_pointer;
    uintptr_t ai;
    uintptr_t pawn;
    uintptr_t board;
    uintptr_t begin;
    uintptr_t end;
    uintptr_t capacity;
    uintptr_t bytes;
    LONG count;
    LONG index;
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
                context->Dr1 != 0 || context->Dr2 != 0 ||
                context->Dr3 != 0 || context->Dr7 != 0) {
                ++g_transition_mismatch_count;
                if (g_stop_reason == OBS_STOP_NONE) {
                    g_stop_reason = OBS_STOP_PREEXISTING_DEBUG_STATE;
                }
                g_transition_seen = -requested;
                return EXCEPTION_CONTINUE_EXECUTION;
            }
            context->Dr0 = (DWORD)g_tournament_selector_address;
            context->Dr1 = (DWORD)g_selected_address;
            context->Dr2 = (DWORD)g_queue_address;
            context->Dr3 = 0;
            context->Dr6 = 0;
            context->Dr7 = TOURNAMENT_DR7_ARM;
            g_debug_armed = 1;
            g_capture_started = 1;
            g_state = OBS_STATE_CAPTURING;
            g_transition_seen = requested;
            return EXCEPTION_CONTINUE_EXECUTION;
        }
        if (requested == OBS_TRANSITION_CLEAR) {
            if ((g_state != OBS_STATE_DRAINING &&
                 g_state != OBS_STATE_CAPTURING &&
                 g_state != OBS_STATE_FAILED_ARMED) ||
                !tournament_debug_state_matches(context)) {
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
    ours = (DWORD)context->Dr6 & 7u;
    if (ours == 0) return EXCEPTION_CONTINUE_SEARCH;
    if (thread_id != g_owner_thread_id) {
        ++g_wrong_thread_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_WRONG_THREAD;
        if (g_state == OBS_STATE_CAPTURING) g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_SEARCH;
    }
    context->Dr6 &= ~7u;
    context->EFlags |= OBS_EFLAGS_RF;
    if (g_state != OBS_STATE_CAPTURING) return EXCEPTION_CONTINUE_EXECUTION;
    eip = (uintptr_t)context->Eip;
    if ((ours != 1u && ours != 2u && ours != 4u) ||
        (ours == 1u && eip != g_tournament_selector_address) ||
        (ours == 2u && eip != g_selected_address) ||
        (ours == 4u && eip != g_queue_address)) {
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

    g_handler_depth = 1;
    capture_ok = 0;
    if (ours == 1u) {
        context_pointer = (uintptr_t)context->Ecx;
        if (g_tournament_stage != TOURNAMENT_STAGE_WAIT_SELECTOR ||
            g_tournament_selector_count != 0 || context_pointer < 0x14u ||
            (context_pointer & 3u) != 0) {
            ++g_ordering_error_count;
        } else {
            ai = context_pointer - 0x14u;
            if (!hot_range_readable(ai + 4u, sizeof(uintptr_t)) ||
                !hot_range_readable(context_pointer + 8u, 0x20u) ||
                !hot_range_readable(
                    g_tournament_rng_state_address, sizeof(uint32_t))) {
                ++g_pointer_fault_count;
            } else {
                pawn = *(const uintptr_t *)(ai + 4u);
                begin = *(const uintptr_t *)(context_pointer + 8u);
                end = *(const uintptr_t *)(context_pointer + 0x0cu);
                capacity = *(const uintptr_t *)(context_pointer + 0x10u);
                board = *(const uintptr_t *)(context_pointer + 0x24u);
                if ((pawn & 3u) != 0 || (board & 3u) != 0 ||
                    begin == 0 || end < begin || capacity < end ||
                    ((end - begin) % 24u) != 0 ||
                    ((capacity - begin) % 24u) != 0 ||
                    !hot_range_readable(pawn + 0x40u, sizeof(int32_t)) ||
                    !hot_range_readable(pawn + 0x948u, 0x60u) ||
                    !hot_range_readable(board + 0x48u, 8u)) {
                    ++g_pointer_fault_count;
                } else {
                    bytes = end - begin;
                    count = (LONG)(bytes / 24u);
                    if (count <= 0 || count > OBS_RECORD_CAP ||
                        !hot_range_readable(begin, bytes)) {
                        ++g_overflow_count;
                    } else {
                        for (index = 0; index < count; ++index) {
                            const int32_t *source =
                                (const int32_t *)(begin + (uintptr_t)index * 24u);
                            tournament_candidate_record *record =
                                &g_tournament_candidates[index];
                            record->sequence = (uint32_t)index;
                            record->destination_x = source[0];
                            record->destination_y = source[1];
                            record->target_x = source[2];
                            record->target_y = source[3];
                            record->target_score = source[4];
                            record->positioning_score = source[5];
                            _ReadWriteBarrier();
                            record->committed = index + 1;
                        }
                        g_tournament_candidate_count = count;
                        g_tournament_selector_count = 1;
                        g_tournament_rng_before =
                            *(const uint32_t *)g_tournament_rng_state_address;
                        g_tournament_pending_context = context_pointer;
                        g_tournament_pending_ai = ai;
                        g_pending_pawn = pawn;
                        g_pending_pawn_id =
                            *(const int32_t *)(pawn + 0x9a4u);
                        g_tournament_pawn_id = g_pending_pawn_id;
                        g_tournament_current_weapon =
                            *(const int32_t *)(pawn + 0x948u);
                        g_tournament_base_current_weapon =
                            *(const int32_t *)(pawn + 0x40u);
                        g_tournament_board_width =
                            *(const int32_t *)(board + 0x48u);
                        g_tournament_board_height =
                            *(const int32_t *)(board + 0x4cu);
                        g_tournament_interior_favorable =
                            *(const unsigned char *)(context_pointer + 0x14u) != 0;
                        g_tournament_stage = TOURNAMENT_STAGE_WAIT_SELECTED;
                        context->ContextFlags |= CONTEXT_DEBUG_REGISTERS;
                        context->Dr0 = 0;
                        context->Dr7 = TOURNAMENT_DR7_AFTER_SELECTOR;
                        capture_ok = 1;
                    }
                }
            }
        }
    } else if (ours == 2u) {
        ai = (uintptr_t)context->Ebx;
        if (g_tournament_stage != TOURNAMENT_STAGE_WAIT_SELECTED ||
            ai != g_tournament_pending_ai || (ai & 3u) != 0 ||
            !hot_range_readable(ai + 4u, sizeof(uintptr_t)) ||
            !hot_range_readable(ai + 0x50u, 24u)) {
            ++g_ordering_error_count;
        } else {
            pawn = *(const uintptr_t *)(ai + 4u);
            if (pawn != g_pending_pawn || (pawn & 3u) != 0 ||
                !hot_range_readable(pawn + 0x40u, sizeof(int32_t)) ||
                !hot_range_readable(pawn + 0x948u, 0x60u) ||
                !hot_range_readable(
                    g_tournament_rng_state_address, sizeof(uint32_t))) {
                ++g_pointer_fault_count;
            } else {
                obs_record *record = &g_records[0];
                record->sequence = 0;
                record->pair_index = 0;
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
                if (record->pawn_id != g_pending_pawn_id) {
                    ++g_ordering_error_count;
                } else {
                    _ReadWriteBarrier();
                    record->committed = 1;
                    g_record_count = 1;
                    g_selected_count = 1;
                    g_tournament_rng_after =
                        *(const uint32_t *)g_tournament_rng_state_address;
                    g_tournament_stage = TOURNAMENT_STAGE_WAIT_QUEUE;
                    context->ContextFlags |= CONTEXT_DEBUG_REGISTERS;
                    context->Dr1 = 0;
                    context->Dr7 = TOURNAMENT_DR7_QUEUE_ONLY;
                    capture_ok = 1;
                }
            }
        }
    } else {
        pawn = (uintptr_t)context->Esi;
        if (g_tournament_stage != TOURNAMENT_STAGE_WAIT_QUEUE ||
            pawn != g_pending_pawn || (pawn & 3u) != 0 ||
            !hot_range_readable(pawn + 0x10u, 0x34u) ||
            !hot_range_readable(pawn + 0x948u, 0x60u)) {
            ++g_ordering_error_count;
        } else {
            obs_record *record = &g_records[1];
            record->sequence = 1;
            record->pair_index = 0;
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
                record->committed = 2;
                g_record_count = 2;
                g_queue_count = 1;
                g_pair_count = 1;
                g_pending_pawn = 0;
                g_pending_pawn_id = 0;
                g_pending_pair_index = 0;
                g_tournament_pending_context = 0;
                g_tournament_pending_ai = 0;
                g_tournament_stage = TOURNAMENT_STAGE_COMPLETE;
                context->ContextFlags |= CONTEXT_DEBUG_REGISTERS;
                context->Dr0 = 0;
                context->Dr1 = 0;
                context->Dr2 = 0;
                context->Dr3 = 0;
                context->Dr6 = 0;
                context->Dr7 = 0;
                g_debug_armed = 0;
                g_debug_cleared = 1;
                g_state = OBS_STATE_DRAINING;
                capture_ok = 1;
            }
        }
    }
    g_handler_depth = 0;
    if (!capture_ok) {
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = g_pointer_fault_count != 0
                ? OBS_STOP_POINTER_FAULT
                : (g_overflow_count != 0
                    ? OBS_STOP_OVERFLOW : OBS_STOP_UNEXPECTED_ORDER);
        }
        g_state = OBS_STATE_DRAINING;
    }
    return EXCEPTION_CONTINUE_EXECUTION;
}
#pragma code_seg(pop)
/* TOURNAMENT_HOT_PATH_END */

static int tournament_relocated_region_equal(
    const unsigned char *actual,
    const unsigned char *expected,
    size_t size) {
    uint32_t delta;
    size_t cursor = 0;
    size_t index;
    if (actual == NULL || expected == NULL || g_executable_base == NULL ||
        (uintptr_t)g_executable_base < OBS_PREFERRED_IMAGE_BASE) {
        return 0;
    }
    delta = (uint32_t)((uintptr_t)g_executable_base - OBS_PREFERRED_IMAGE_BASE);
    for (index = 0; index < OBS_RNG_STATE_OWNER_RELOCATION_COUNT; ++index) {
        size_t offset = OBS_RNG_STATE_OWNER_RELOCATION_OFFSETS[index];
        uint32_t expected_value = 0;
        uint32_t actual_value = 0;
        if (offset < cursor || offset + sizeof(uint32_t) > size ||
            !bytes_equal(actual + cursor, expected + cursor, offset - cursor)) {
            return 0;
        }
        byte_copy(&expected_value, expected + offset, sizeof(expected_value));
        byte_copy(&actual_value, actual + offset, sizeof(actual_value));
        if (actual_value != expected_value + delta) return 0;
        cursor = offset + sizeof(uint32_t);
    }
    return cursor <= size &&
        bytes_equal(actual + cursor, expected + cursor, size - cursor);
}

static int tournament_live_identity(void) {
    tournament_rng_state_owner_fn owner;
    unsigned char *owner_result;
    if (!verify_live_identity() || g_executable_base == NULL ||
        !bytes_equal(
            g_executable_base + OBS_TOURNAMENT_SELECTOR_RVA,
            OBS_TOURNAMENT_SELECTOR_PREBYTES,
            OBS_TOURNAMENT_SELECTOR_PREBYTE_SIZE) ||
        !tournament_relocated_region_equal(
            g_executable_base + OBS_RNG_STATE_OWNER_RVA,
            OBS_RNG_STATE_OWNER_BYTES,
            OBS_RNG_STATE_OWNER_SIZE)) {
        return 0;
    }
    g_tournament_selector_address =
        (uintptr_t)(g_executable_base + OBS_TOURNAMENT_SELECTOR_RVA);
    owner = (tournament_rng_state_owner_fn)(
        g_executable_base + OBS_RNG_STATE_OWNER_RVA);
    owner_result = owner();
    if (owner_result == NULL) return 0;
    g_tournament_rng_state_address =
        (uintptr_t)(owner_result + TOURNAMENT_RNG_STATE_OFFSET);
    return g_tournament_rng_state_address >= 0x00010000u &&
        g_tournament_rng_state_address <= 0x7ff00000u - sizeof(uint32_t);
}

static int tournament_seams_unchanged(void) {
    return seams_unchanged() && g_executable_base != NULL &&
        bytes_equal(
            g_executable_base + OBS_TOURNAMENT_SELECTOR_RVA,
            OBS_TOURNAMENT_SELECTOR_PREBYTES,
            OBS_TOURNAMENT_SELECTOR_PREBYTE_SIZE) &&
        tournament_relocated_region_equal(
            g_executable_base + OBS_RNG_STATE_OWNER_RVA,
            OBS_RNG_STATE_OWNER_BYTES,
            OBS_RNG_STATE_OWNER_SIZE);
}

static void tournament_reset_capture_state(void) {
    reset_capture_state();
    byte_zero(g_tournament_candidates, sizeof(g_tournament_candidates));
    g_tournament_stage = TOURNAMENT_STAGE_WAIT_SELECTOR;
    g_tournament_selector_count = 0;
    g_tournament_candidate_count = 0;
    g_tournament_torn_candidate_count = 0;
    g_tournament_selector_address = 0;
    g_tournament_rng_state_address = 0;
    g_tournament_pending_context = 0;
    g_tournament_pending_ai = 0;
    g_tournament_rng_before = 0;
    g_tournament_rng_after = 0;
    g_tournament_pawn_id = 0;
    g_tournament_current_weapon = 0;
    g_tournament_base_current_weapon = 0;
    g_tournament_board_width = 0;
    g_tournament_board_height = 0;
    g_tournament_interior_favorable = 0;
}

static int tournament_arm(lua_State *state) {
    const char *capture_id;
    size_t capture_length = 0;
    if (g_lua_gettop(state) != 1) {
        return g_luaL_error(state, "tournament arm requires one capture ID");
    }
    capture_id = g_luaL_checklstring(state, 1, &capture_length);
    if (!valid_capture_id(capture_id, capture_length)) {
        return g_luaL_error(state, "tournament capture ID is invalid");
    }
    if (g_consumed != 0) {
        return g_luaL_error(state, "native tournament observer is one-shot per process");
    }
    g_consumed = 1;
    tournament_reset_capture_state();
    byte_copy(g_capture_id, capture_id, capture_length);
    g_capture_id[capture_length] = '\0';
    g_owner_thread_id = (DWORD)__readfsdword(0x24);
    if (!tournament_live_identity()) {
        request_stop_cold(OBS_STOP_IDENTITY_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "pinned tournament observer identity mismatch");
    }
    if (!build_readable_range_map() || !hot_range_readable(
            g_tournament_rng_state_address, sizeof(uint32_t))) {
        request_stop_cold(OBS_STOP_READABLE_MAP);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "tournament readable-range map failed");
    }
    g_state = OBS_STATE_VERIFIED;
    g_veh_handle = AddVectoredExceptionHandler(1, observer_enemy_tournament_veh);
    if (g_veh_handle == NULL) {
        request_stop_cold(OBS_STOP_TRANSITION_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "tournament VEH installation failed");
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
        if (g_debug_armed == 0) (void)release_executable_file();
        g_state = g_debug_armed != 0
            ? OBS_STATE_FAILED_ARMED : OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "tournament debug-register arm failed");
    }
    g_lua_pushboolean(state, 1);
    return 1;
}

static LONG tournament_count_torn_candidates(void) {
    LONG count = g_tournament_candidate_count;
    LONG torn = 0;
    LONG index;
    if (count < 0) return 1;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    for (index = 0; index < count; ++index) {
        if (g_tournament_candidates[index].committed != index + 1 ||
            g_tournament_candidates[index].sequence != (uint32_t)index) {
            ++torn;
        }
    }
    return torn;
}

static void tournament_set_u32_hex(
    lua_State *state, const char *key, uint32_t value) {
    static const char digits[] = "0123456789abcdef";
    char text[11];
    int index;
    text[0] = '0';
    text[1] = 'x';
    for (index = 0; index < 8; ++index) {
        unsigned int shift = (unsigned int)(7 - index) * 4u;
        text[index + 2] = digits[(value >> shift) & 0x0fu];
    }
    text[10] = '\0';
    set_string(state, key, text);
}

static void tournament_push_selected(lua_State *state) {
    obs_record *record = &g_records[0];
    g_lua_createtable(state, 0, 13);
    set_string(state, "kind", "selected_record");
    set_integer(state, "seq", (LONG)record->sequence);
    set_integer(state, "pawn_id", record->pawn_id);
    set_integer(state, "current_weapon_raw", record->current_weapon);
    set_integer(state, "base_current_weapon_raw", record->base_current_weapon);
    set_integer(state, "ai_dest_x", record->value0);
    set_integer(state, "ai_dest_y", record->value1);
    set_integer(state, "ai_target_x", record->value2);
    set_integer(state, "ai_target_y", record->value3);
    set_integer(state, "selected_field_4_raw", record->value4);
    set_integer(state, "selected_field_5_raw", record->value5);
}

static void tournament_push_queue(lua_State *state) {
    obs_record *record = &g_records[1];
    g_lua_createtable(state, 0, 14);
    set_string(state, "kind", "queued_action");
    set_integer(state, "seq", (LONG)record->sequence);
    set_integer(state, "pawn_id", record->pawn_id);
    set_integer(state, "current_weapon_raw", record->current_weapon);
    set_integer(state, "base_current_weapon_raw", record->base_current_weapon);
    set_integer(state, "target_x", record->value0);
    set_integer(state, "target_y", record->value1);
    set_integer(state, "origin_x", record->value2);
    set_integer(state, "origin_y", record->value3);
    set_integer(state, "queued_shot_x", record->value4);
    set_integer(state, "queued_shot_y", record->value5);
    set_integer(state, "queued_skill_raw", record->value6);
}

static void tournament_push_snapshot(lua_State *state) {
    LONG candidate_count = g_tournament_candidate_count;
    LONG record_count = g_record_count;
    LONG candidate_torn = tournament_count_torn_candidates();
    LONG record_torn = count_torn_records();
    LONG reason = g_stop_reason;
    LONG index;
    int complete;
    if (candidate_count < 0) candidate_count = 0;
    if (candidate_count > OBS_RECORD_CAP) candidate_count = OBS_RECORD_CAP;
    if (record_count < 0) record_count = 0;
    if (record_count > OBS_RECORD_CAP) record_count = OBS_RECORD_CAP;
    if ((candidate_torn != 0 || record_torn != 0) &&
        reason == OBS_STOP_NONE) reason = OBS_STOP_TORN_RECORD;
    g_tournament_torn_candidate_count = candidate_torn;
    g_torn_record_count = record_torn;
    complete = g_state == OBS_STATE_RESTORED && reason == OBS_STOP_NONE &&
        g_tournament_stage == TOURNAMENT_STAGE_COMPLETE &&
        g_tournament_selector_count == 1 && candidate_count > 0 &&
        record_count == 2 && g_selected_count == 1 && g_queue_count == 1 &&
        g_pair_count == 1 && g_pending_pawn == 0 &&
        candidate_torn == 0 && record_torn == 0 &&
        g_overflow_count == 0 && g_ordering_error_count == 0 &&
        g_pointer_fault_count == 0 && g_transition_mismatch_count == 0 &&
        g_wrong_thread_count == 0 && g_unexpected_breakpoint_count == 0 &&
        g_debug_armed == 0 && g_debug_cleared != 0 &&
        g_veh_installed == 0 && g_veh_removed != 0 &&
        g_executable_file_released != 0 && g_seam_bytes_unchanged != 0;

    g_lua_createtable(state, 0, 8);
    set_integer(state, "schema_version", 1);
    set_string(state, "kind", "native_enemy_tournament_hw_snapshot");
    set_string(state, "observer_version", TOURNAMENT_VERSION);
    set_string(state, "capture_id", g_capture_id);

    g_lua_createtable(state, 0, 15);
    set_string(state, "platform", "windows");
    set_string(state, "architecture", "x86");
    set_string(state, "build_id", OBS_BUILD_ID);
    set_string(state, "executable_sha256", OBS_EXECUTABLE_SHA256);
    set_integer(state, "executable_size", OBS_EXECUTABLE_SIZE);
    set_string(state, "inventory_sha256", OBS_INVENTORY_SHA256);
    set_string(state, "boundary_map_sha256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "rng_return_map_sha256", OBS_RNG_RETURN_MAP_SHA256);
    set_string(state, "record_selector_boundary_sha256",
        OBS_RECORD_SELECTOR_BOUNDARY_SHA256);
    set_string(state, "selected_queue_source_sha256",
        OBS_SELECTED_QUEUE_SOURCE_SHA256);
    set_string(state, "hardware_breakpoint_plan_sha256", OBS_HW_PLAN_SHA256);
    set_string(state, "selector_prebytes_sha256",
        OBS_TOURNAMENT_SELECTOR_PREBYTES_SHA256);
    set_string(state, "selected_prebytes_sha256", OBS_SELECTED_PREBYTES_SHA256);
    set_string(state, "queue_prebytes_sha256", OBS_QUEUE_PREBYTES_SHA256);
    set_string(state, "rng_state_owner_sha256", OBS_RNG_STATE_OWNER_SHA256);
    g_lua_setfield(state, -2, "identity");

    g_lua_createtable(state, 0, 20);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "complete", complete);
    set_nullable_reason(state, reason);
    set_integer(state, "overflow_count", g_overflow_count);
    set_integer(state, "ordering_error_count", g_ordering_error_count);
    set_integer(state, "pointer_fault_count", g_pointer_fault_count);
    set_integer(state, "transition_mismatch_count", g_transition_mismatch_count);
    set_integer(state, "wrong_thread_count", g_wrong_thread_count);
    set_integer(state, "unexpected_breakpoint_count",
        g_unexpected_breakpoint_count);
    set_integer(state, "torn_candidate_count", candidate_torn);
    set_integer(state, "torn_record_count", record_torn);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_boolean(state, "veh_removed", g_veh_removed);
    set_boolean(state, "executable_file_released", g_executable_file_released);
    set_boolean(state, "executable_bytes_modified", 0);
    set_boolean(state, "seam_bytes_unchanged", g_seam_bytes_unchanged);
    set_boolean(state, "addresses_or_pointers_published", 0);
    g_lua_setfield(state, -2, "integrity");

    g_lua_createtable(state, 0, 9);
    set_integer(state, "pawn_id", g_tournament_pawn_id);
    set_integer(state, "current_weapon_raw", g_tournament_current_weapon);
    set_integer(state, "base_current_weapon_raw",
        g_tournament_base_current_weapon);
    set_integer(state, "board_width", g_tournament_board_width);
    set_integer(state, "board_height", g_tournament_board_height);
    set_boolean(state, "interior_favorable",
        g_tournament_interior_favorable);
    tournament_set_u32_hex(
        state, "selector_rng_state_before", g_tournament_rng_before);
    tournament_set_u32_hex(
        state, "selector_rng_state_after", g_tournament_rng_after);
    g_lua_setfield(state, -2, "selector_context");

    g_lua_createtable(state, candidate_count, 0);
    for (index = 0; index < candidate_count; ++index) {
        tournament_candidate_record *record = &g_tournament_candidates[index];
        g_lua_createtable(state, 0, 7);
        set_integer(state, "seq", (LONG)record->sequence);
        set_integer(state, "destination_x", record->destination_x);
        set_integer(state, "destination_y", record->destination_y);
        set_integer(state, "target_x", record->target_x);
        set_integer(state, "target_y", record->target_y);
        set_integer(state, "target_score", record->target_score);
        set_integer(state, "positioning_score", record->positioning_score);
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, "candidate_records");
    tournament_push_selected(state);
    g_lua_setfield(state, -2, "selected_record");
    tournament_push_queue(state);
    g_lua_setfield(state, -2, "queued_action");

    g_lua_createtable(state, 0, 8);
    set_integer(state, "selector_count", g_tournament_selector_count);
    set_integer(state, "candidate_count", candidate_count);
    set_integer(state, "selected_count", g_selected_count);
    set_integer(state, "queue_count", g_queue_count);
    set_integer(state, "pair_count", g_pair_count);
    set_integer(state, "thread_count", g_capture_started != 0 ? 1 : 0);
    set_integer(state, "stage", g_tournament_stage);
    set_boolean(state, "pending_selection", g_pending_pawn != 0);
    g_lua_setfield(state, -2, "summary");
}

static int tournament_finish(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "tournament finish takes no arguments");
    }
    if (g_consumed == 0 || g_capture_started == 0) {
        return g_luaL_error(state, "native tournament observer is not active");
    }
    if ((DWORD)__readfsdword(0x24) != g_owner_thread_id) {
        ++g_wrong_thread_count;
        request_stop_cold(OBS_STOP_WRONG_THREAD);
        return g_luaL_error(state, "tournament must finish on its arm thread");
    }
    if (g_state != OBS_STATE_CAPTURING && g_state != OBS_STATE_DRAINING &&
        g_state != OBS_STATE_FAILED_ARMED) {
        return g_luaL_error(state, "native tournament observer cannot be finished");
    }
    if (g_tournament_stage != TOURNAMENT_STAGE_COMPLETE ||
        g_pending_pawn != 0 || g_record_count != 2 ||
        g_tournament_candidate_count <= 0) {
        ++g_ordering_error_count;
        request_stop_cold(OBS_STOP_UNEXPECTED_ORDER);
    }
    g_state = OBS_STATE_DRAINING;
    if (g_debug_armed != 0 &&
        (!run_transition(OBS_TRANSITION_CLEAR) || g_debug_cleared == 0 ||
         g_debug_armed != 0)) {
        g_state = OBS_STATE_FAILED_ARMED;
        return g_luaL_error(state,
            "tournament debug-register clearing failed; no snapshot published");
    }
    if (g_debug_armed == 0 && g_debug_cleared == 0) {
        g_state = OBS_STATE_FAILED_ARMED;
        return g_luaL_error(state,
            "tournament debug registers were not proven clear");
    }
    if (g_veh_handle == NULL ||
        RemoveVectoredExceptionHandler(g_veh_handle) == 0) {
        request_stop_cold(OBS_STOP_VEH_REMOVE);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state,
            "tournament VEH removal failed; no snapshot published");
    }
    g_veh_handle = NULL;
    g_veh_installed = 0;
    g_veh_removed = 1;
    g_seam_bytes_unchanged = tournament_seams_unchanged();
    if (!g_seam_bytes_unchanged || !release_executable_file()) {
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state,
            "tournament observer integrity finalization failed");
    }
    g_state = OBS_STATE_RESTORED;
    tournament_push_snapshot(state);
    return 1;
}

static int tournament_status(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "tournament status takes no arguments");
    }
    g_lua_createtable(state, 0, 16);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "consumed", g_consumed);
    set_boolean(state, "capture_started", g_capture_started);
    set_integer(state, "stage", g_tournament_stage);
    set_integer(state, "selector_count", g_tournament_selector_count);
    set_integer(state, "candidate_count", g_tournament_candidate_count);
    set_integer(state, "record_count", g_record_count);
    set_integer(state, "selected_count", g_selected_count);
    set_integer(state, "queue_count", g_queue_count);
    set_boolean(state, "pending_selection", g_pending_pawn != 0);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_integer(state, "overflow_count", g_overflow_count);
    set_integer(state, "ordering_error_count", g_ordering_error_count);
    set_nullable_reason(state, g_stop_reason);
    return 1;
}

__declspec(dllexport) int __cdecl
luaopen_itb_observatory_enemy_tournament_hw_observer(lua_State *state) {
    if (!resolve_lua_api()) return 0;
    if (!pin_this_module()) {
        return g_luaL_error(state, "native tournament observer module pin failed");
    }
    g_lua_createtable(state, 0, 14);
    set_string(state, "VERSION", TOURNAMENT_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", "x86");
    set_string(state, "SELECTOR_RVA", OBS_TOURNAMENT_SELECTOR_RVA_TEXT);
    set_string(state, "SELECTED_RVA", OBS_SELECTED_RVA_TEXT);
    set_string(state, "QUEUE_RVA", OBS_QUEUE_RVA_TEXT);
    set_string(state, "RNG_STATE_OWNER_RVA", OBS_RNG_STATE_OWNER_RVA_TEXT);
    set_string(state, "HARDWARE_BREAKPOINT_PLAN_SHA256", OBS_HW_PLAN_SHA256);
    set_string(state, "RECORD_SELECTOR_BOUNDARY_SHA256",
        OBS_RECORD_SELECTOR_BOUNDARY_SHA256);
    set_string(state, "SELECTED_QUEUE_SOURCE_SHA256",
        OBS_SELECTED_QUEUE_SOURCE_SHA256);
    g_lua_pushcclosure(state, tournament_arm, 0);
    g_lua_setfield(state, -2, "arm");
    g_lua_pushcclosure(state, tournament_finish, 0);
    g_lua_setfield(state, -2, "finish");
    g_lua_pushcclosure(state, tournament_status, 0);
    g_lua_setfield(state, -2, "status");
    return 1;
}
