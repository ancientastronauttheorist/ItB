/*
 * Build-keyed, one-shot selector-entry Board/RNG capsule observer for ITB.
 *
 * This source deliberately reuses the published spawn-coordinate observer as
 * an immutable compile-time dependency.  Its historical Lua opener and VEH
 * are renamed and left unexported; no v1 source or artifact is rewritten.
 * The v2 VEH adds the previously unused DR3 selector-entry breakpoint, copies
 * pointer-free Board facts plus the shared CRT state, and pairs each capsule
 * with the existing post-IDIV candidate/draw record.  The hot path performs no
 * calls, allocation, I/O, locks, clocks, Lua/game calls, or Windows API calls.
 */

/* Keep the included historical opener out of this DLL's export table. */
#define dllexport noinline
#define observer_spawn_coordinate_veh \
    observer_spawn_coordinate_base_veh_unreferenced
#define luaopen_itb_observatory_spawn_coordinate_hw_observer \
    observatory_spawn_coordinate_base_opener_unexported
#include "observatory_spawn_coordinate_hw_observer.c"
#undef luaopen_itb_observatory_spawn_coordinate_hw_observer
#undef observer_spawn_coordinate_veh
#undef dllexport

#include "observatory_spawn_coordinate_capsule_hw_build.inc"

#define CAPSULE_VERSION "observatory-spawn-coordinate-capsule-hw-observer/2"
#define CAPSULE_RECORD_CAP 64
#define CAPSULE_TILE_CAP 64
#define CAPSULE_POINT_CAP 64
#define CAPSULE_OCCUPANT_CAP 8
#define CAPSULE_TREE_STACK_CAP 65
#define CAPSULE_DR7_EXACT 0x00000055u
#define CAPSULE_BLOCK_UNSET ((int32_t)(-2147483647 - 1))
#define CAPSULE_STOP_CONTRACT 17
#define CAPSULE_STOP_RNG 18
#define CAPSULE_STOP_PAIRING 19

#define CAPSULE_BOARD_WIDTH_OFFSET 0x48u
#define CAPSULE_BOARD_HEIGHT_OFFSET 0x4cu
#define CAPSULE_BOARD_TILE_COLUMNS_OFFSET 0x50u
#define CAPSULE_BOARD_TURN_OFFSET 0x2ca8u
#define CAPSULE_BOARD_SPAWN_BEGIN_OFFSET 0x2d50u
#define CAPSULE_BOARD_SPAWN_END_OFFSET 0x2d54u
#define CAPSULE_BOARD_SPAWN_CAPACITY_OFFSET 0x2d58u
#define CAPSULE_BOARD_BLOCK_MAP_OFFSET 0x7458u
#define CAPSULE_BOARD_DANGER_A_BEGIN_OFFSET 0x7460u
#define CAPSULE_BOARD_DANGER_A_END_OFFSET 0x7464u
#define CAPSULE_BOARD_DANGER_A_CAPACITY_OFFSET 0x7468u
#define CAPSULE_BOARD_DANGER_B_BEGIN_OFFSET 0x7470u
#define CAPSULE_BOARD_DANGER_B_END_OFFSET 0x7474u
#define CAPSULE_BOARD_DANGER_B_CAPACITY_OFFSET 0x7478u
#define CAPSULE_TILE_COLUMN_STRIDE 12u
#define CAPSULE_TILE_Y_STRIDE 0x2bbcu
#define CAPSULE_TILE_OCCUPANCY_BEGIN_OFFSET 0xa0u
#define CAPSULE_TILE_OCCUPANCY_END_OFFSET 0xa4u
#define CAPSULE_TILE_OCCUPANCY_CAPACITY_OFFSET 0xa8u
#define CAPSULE_TILE_TERRAIN_OFFSET 0x2ae0u
#define CAPSULE_TILE_POD_OFFSET 0x2ae4u
#define CAPSULE_TILE_DANGER_OFFSET 0x2af0u
#define CAPSULE_TILE_ACID_OFFSET 0x2af1u
#define CAPSULE_TILE_ITEM_OFFSET 0x2b04u
#define CAPSULE_PAWN_TEAM_OFFSET 0xb0u
#define CAPSULE_PAWN_ID_OFFSET 0x9a4u
#define CAPSULE_RNG_STATE_OFFSET 0x18u

typedef unsigned char *(__cdecl *capsule_rng_state_owner_fn)(void);

typedef struct capsule_tile_record {
    int32_t terrain;
    int32_t pod_state;
    int32_t item_present;
    int32_t acid;
    int32_t dangerous_flag;
    int32_t occupancy_count;
    int32_t occupant_ids[CAPSULE_OCCUPANT_CAP];
} capsule_tile_record;

typedef struct capsule_record {
    volatile LONG committed;
    uint32_t sequence;
    int32_t draw_sequence;
    uint8_t selector_kind;
    uint8_t reserved0;
    uint16_t reserved1;
    uint32_t rng_state_before;
    uint32_t rng_state_after;
    int32_t raw_rng;
    int32_t selected_index;
    int32_t selected_x;
    int32_t selected_y;
    int32_t board_width;
    int32_t board_height;
    int32_t board_turn;
    int32_t pawn_id;
    int32_t pawn_team;
    uint16_t tile_count;
    uint16_t block_spawn_count;
    uint16_t spawn_marker_count;
    uint16_t dangerous_a_count;
    uint16_t dangerous_b_count;
    uint16_t reserved2;
    int32_t block_spawn_values[CAPSULE_TILE_CAP];
    int32_t spawn_marker_x[CAPSULE_POINT_CAP];
    int32_t spawn_marker_y[CAPSULE_POINT_CAP];
    int32_t dangerous_a_x[CAPSULE_POINT_CAP];
    int32_t dangerous_a_y[CAPSULE_POINT_CAP];
    int32_t dangerous_b_x[CAPSULE_POINT_CAP];
    int32_t dangerous_b_y[CAPSULE_POINT_CAP];
    capsule_tile_record tiles[CAPSULE_TILE_CAP];
} capsule_record;

__declspec(align(64)) static capsule_record
    g_capsules[CAPSULE_RECORD_CAP];
static volatile LONG g_capsule_entry_count;
static volatile LONG g_capsule_count;
static volatile LONG g_capsule_error_count;
static volatile LONG g_rng_error_count;
static volatile LONG g_pairing_error_count;
static volatile LONG g_torn_capsule_count;
static volatile LONG g_pending_capsule_index = -1;
static uintptr_t g_selector_entry_address;
static uintptr_t g_rng_state_address;

static const char *capsule_stop_reason_text(LONG reason) {
    if (reason == CAPSULE_STOP_CONTRACT) return "capsule_contract";
    if (reason == CAPSULE_STOP_RNG) return "rng_transition";
    if (reason == CAPSULE_STOP_PAIRING) return "selector_pairing";
    return stop_reason_text(reason);
}

static void capsule_set_nullable_reason(lua_State *state, LONG reason) {
    const char *text = capsule_stop_reason_text(reason);
    if (text == NULL) g_lua_pushnil(state); else g_lua_pushstring(state, text);
    g_lua_setfield(state, -2, "stopped_reason");
}

static void capsule_set_u32_hex(
    lua_State *state,
    const char *key,
    uint32_t value) {
    static const char digits[] = "0123456789abcdef";
    char text[11];
    int index;
    text[0] = '0';
    text[1] = 'x';
    for (index = 0; index < 8; ++index) {
        text[2 + index] = digits[(value >> (28 - index * 4)) & 0x0fu];
    }
    text[10] = '\0';
    set_string(state, key, text);
}

/* CAPSULE_HOT_PATH_BEGIN
 * The complete dedicated section calls no function and publishes no pointer.
 */
#pragma code_seg(push, ".obshot")
LONG CALLBACK observer_spawn_coordinate_capsule_veh(
    PEXCEPTION_POINTERS pointers) {
    PEXCEPTION_RECORD exception_record;
    PCONTEXT context;
    DWORD thread_id;
    DWORD code;
    DWORD ours;
    uintptr_t eip;
    uintptr_t frame;
    uintptr_t begin;
    uintptr_t end;
    uintptr_t capacity;
    uintptr_t board;
    uintptr_t pawn;
    uintptr_t columns;
    uintptr_t tile;
    uintptr_t node;
    uintptr_t head;
    uintptr_t tree_stack[CAPSULE_TREE_STACK_CAP];
    uintptr_t visited[CAPSULE_TILE_CAP];
    LONG tree_top;
    LONG visited_count;
    LONG count;
    LONG selected_index;
    LONG quotient;
    LONG index;
    LONG x;
    LONG y;
    LONG point_index;
    LONG record_index;
    LONG capsule_index;
    int32_t *coordinates;
    obs_record *record;
    capsule_record *capsule;
    uint32_t expected_rng_state;
    uint32_t observed_rng_state;
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
            context->Dr0 = (DWORD)g_scheduler_address;
            context->Dr1 = (DWORD)g_selector_fallback_address;
            context->Dr2 = (DWORD)g_selector_standard_address;
            context->Dr3 = (DWORD)g_selector_entry_address;
            context->Dr6 = 0;
            context->Dr7 = CAPSULE_DR7_EXACT;
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
                context->Dr0 != (DWORD)g_scheduler_address ||
                context->Dr1 != (DWORD)g_selector_fallback_address ||
                context->Dr2 != (DWORD)g_selector_standard_address ||
                context->Dr3 != (DWORD)g_selector_entry_address ||
                context->Dr7 != CAPSULE_DR7_EXACT) {
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
    ours = (DWORD)context->Dr6 & 15u;
    if (ours == 0) return EXCEPTION_CONTINUE_SEARCH;
    if (thread_id != g_owner_thread_id) {
        ++g_wrong_thread_count;
        if (g_stop_reason == OBS_STOP_NONE) g_stop_reason = OBS_STOP_WRONG_THREAD;
        if (g_state == OBS_STATE_CAPTURING) g_state = OBS_STATE_DRAINING;
        return EXCEPTION_CONTINUE_SEARCH;
    }
    context->Dr6 &= ~15u;
    context->EFlags |= OBS_EFLAGS_RF;
    if (g_state != OBS_STATE_CAPTURING) return EXCEPTION_CONTINUE_EXECUTION;
    eip = (uintptr_t)context->Eip;
    if ((ours != 1u && ours != 2u && ours != 4u && ours != 8u) ||
        (ours == 1u && eip != g_scheduler_address) ||
        (ours == 2u && eip != g_selector_fallback_address) ||
        (ours == 4u && eip != g_selector_standard_address) ||
        (ours == 8u && eip != g_selector_entry_address)) {
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
    if (ours == 8u) {
        uintptr_t stack_pointer = (uintptr_t)context->Esp;
        if (g_pending_capsule_index != -1 || g_capsule_entry_count < 0 ||
            g_capsule_entry_count >= CAPSULE_RECORD_CAP ||
            !hot_range_readable(stack_pointer + 4u, 8u)) {
            ++g_pairing_error_count;
        } else {
            board = (uintptr_t)context->Ecx;
            pawn = *(const uintptr_t *)(stack_pointer + 8u);
            if ((board & 3u) != 0 || (pawn & 3u) != 0 ||
                !hot_range_readable(board, 0x747cu) ||
                !hot_range_readable(pawn + CAPSULE_PAWN_TEAM_OFFSET, 4u) ||
                !hot_range_readable(pawn + CAPSULE_PAWN_ID_OFFSET, 4u) ||
                !hot_range_readable(g_rng_state_address, sizeof(uint32_t)) ||
                *(const uintptr_t *)board !=
                    (uintptr_t)(g_executable_base + OBS_BOARD_PRIMARY_VTABLE_RVA) ||
                *(const uintptr_t *)(board + 0x0cu) !=
                    (uintptr_t)(g_executable_base + OBS_BOARD_SECONDARY_VTABLE_RVA)) {
                ++g_pointer_fault_count;
            } else {
                capsule_index = g_capsule_entry_count;
                capsule = &g_capsules[capsule_index];
                capsule->sequence = (uint32_t)capsule_index;
                capsule->draw_sequence = -1;
                capsule->selector_kind = 0;
                capsule->rng_state_before =
                    *(const uint32_t *)g_rng_state_address;
                capsule->board_width =
                    *(const int32_t *)(board + CAPSULE_BOARD_WIDTH_OFFSET);
                capsule->board_height =
                    *(const int32_t *)(board + CAPSULE_BOARD_HEIGHT_OFFSET);
                capsule->board_turn =
                    *(const int32_t *)(board + CAPSULE_BOARD_TURN_OFFSET);
                capsule->pawn_id =
                    *(const int32_t *)(pawn + CAPSULE_PAWN_ID_OFFSET);
                capsule->pawn_team =
                    *(const int32_t *)(pawn + CAPSULE_PAWN_TEAM_OFFSET);
                if (capsule->board_width != 8 ||
                    capsule->board_height != 8 ||
                    capsule->board_turn < 0 || capsule->board_turn > 20 ||
                    capsule->pawn_team < 0 || capsule->pawn_team > 8) {
                    ++g_capsule_error_count;
                }

                for (index = 0; index < CAPSULE_TILE_CAP; ++index) {
                    capsule->block_spawn_values[index] = CAPSULE_BLOCK_UNSET;
                }
                capsule->tile_count = 0;
                columns = *(const uintptr_t *)(
                    board + CAPSULE_BOARD_TILE_COLUMNS_OFFSET);
                if (g_capsule_error_count == 0 &&
                    !hot_range_readable(
                        columns,
                        CAPSULE_TILE_COLUMN_STRIDE * 8u)) {
                    ++g_pointer_fault_count;
                }
                if (g_capsule_error_count == 0 &&
                    g_pointer_fault_count == 0) {
                    for (x = 0; x < 8; ++x) {
                        uintptr_t column = *(const uintptr_t *)(
                            columns + (uintptr_t)x * CAPSULE_TILE_COLUMN_STRIDE);
                        if ((column & 3u) != 0) {
                            ++g_pointer_fault_count;
                            break;
                        }
                        for (y = 0; y < 8; ++y) {
                            LONG tile_index = x * 8 + y;
                            LONG occupant_count = 0;
                            capsule_tile_record *tile_record =
                                &capsule->tiles[tile_index];
                            tile = column +
                                (uintptr_t)y * CAPSULE_TILE_Y_STRIDE;
                            if (!hot_range_readable(
                                    tile + CAPSULE_TILE_OCCUPANCY_BEGIN_OFFSET,
                                    12u) ||
                                !hot_range_readable(
                                    tile + CAPSULE_TILE_TERRAIN_OFFSET,
                                    CAPSULE_TILE_ITEM_OFFSET -
                                        CAPSULE_TILE_TERRAIN_OFFSET + 4u)) {
                                ++g_pointer_fault_count;
                                break;
                            }
                            tile_record->terrain = *(const int32_t *)(
                                tile + CAPSULE_TILE_TERRAIN_OFFSET);
                            tile_record->pod_state = *(const int32_t *)(
                                tile + CAPSULE_TILE_POD_OFFSET);
                            tile_record->item_present =
                                *(const int32_t *)(
                                    tile + CAPSULE_TILE_ITEM_OFFSET) != 0;
                            tile_record->acid = *(const unsigned char *)(
                                tile + CAPSULE_TILE_ACID_OFFSET) != 0;
                            tile_record->dangerous_flag =
                                *(const unsigned char *)(
                                    tile + CAPSULE_TILE_DANGER_OFFSET) != 0;
                            begin = *(const uintptr_t *)(
                                tile + CAPSULE_TILE_OCCUPANCY_BEGIN_OFFSET);
                            end = *(const uintptr_t *)(
                                tile + CAPSULE_TILE_OCCUPANCY_END_OFFSET);
                            capacity = *(const uintptr_t *)(
                                tile + CAPSULE_TILE_OCCUPANCY_CAPACITY_OFFSET);
                            if (begin == end) {
                                if ((begin == 0 && capacity != 0) ||
                                    (begin != 0 &&
                                     (!hot_range_readable(begin, 1u) ||
                                      capacity < end ||
                                      (capacity - begin) % 4u != 0))) {
                                    ++g_capsule_error_count;
                                    break;
                                }
                            } else if ((begin & 3u) != 0 || end < begin ||
                                capacity < end || (end - begin) % 4u != 0 ||
                                (capacity - begin) % 4u != 0 ||
                                !hot_range_readable(begin, end - begin)) {
                                ++g_capsule_error_count;
                                break;
                            } else {
                                occupant_count = (LONG)((end - begin) / 4u);
                            }
                            if (occupant_count < 0 ||
                                occupant_count > CAPSULE_OCCUPANT_CAP) {
                                ++g_capsule_error_count;
                                break;
                            }
                            tile_record->occupancy_count = occupant_count;
                            for (index = 0;
                                 index < CAPSULE_OCCUPANT_CAP;
                                 ++index) {
                                tile_record->occupant_ids[index] = -1;
                            }
                            for (index = 0; index < occupant_count; ++index) {
                                uintptr_t occupant = *(const uintptr_t *)(
                                    begin + (uintptr_t)index * 4u);
                                if ((occupant & 3u) != 0 ||
                                    !hot_range_readable(
                                        occupant + CAPSULE_PAWN_ID_OFFSET,
                                        4u)) {
                                    ++g_pointer_fault_count;
                                    break;
                                }
                                tile_record->occupant_ids[index] =
                                    *(const int32_t *)(
                                        occupant + CAPSULE_PAWN_ID_OFFSET);
                            }
                            if (g_pointer_fault_count != 0) break;
                            capsule->tile_count =
                                (uint16_t)(tile_index + 1);
                        }
                        if (g_pointer_fault_count != 0 ||
                            g_capsule_error_count != 0) break;
                    }
                }

                capsule->block_spawn_count = 0;
                if (g_pointer_fault_count == 0 &&
                    g_capsule_error_count == 0) {
                    head = *(const uintptr_t *)(
                        board + CAPSULE_BOARD_BLOCK_MAP_OFFSET);
                    if ((head & 3u) != 0 ||
                        !hot_range_readable(head, 0x1cu) ||
                        *(const unsigned char *)(head + 0x0du) == 0) {
                        ++g_pointer_fault_count;
                    } else {
                        node = *(const uintptr_t *)(head + 4u);
                        tree_top = 0;
                        visited_count = 0;
                        tree_stack[tree_top++] = node;
                        while (tree_top > 0 &&
                               g_pointer_fault_count == 0 &&
                               g_capsule_error_count == 0) {
                            LONG duplicate = 0;
                            node = tree_stack[--tree_top];
                            if (node == head) continue;
                            if ((node & 3u) != 0 ||
                                visited_count >= CAPSULE_TILE_CAP ||
                                !hot_range_readable(node, 0x1cu) ||
                                *(const unsigned char *)(node + 0x0du) != 0) {
                                ++g_pointer_fault_count;
                                break;
                            }
                            for (index = 0; index < visited_count; ++index) {
                                if (visited[index] == node) duplicate = 1;
                            }
                            if (duplicate) {
                                ++g_capsule_error_count;
                                break;
                            }
                            visited[visited_count++] = node;
                            x = *(const int32_t *)(node + 0x10u);
                            y = *(const int32_t *)(node + 0x14u);
                            if (x < 0 || x >= 8 || y < 0 || y >= 8 ||
                                capsule->block_spawn_values[x * 8 + y] !=
                                    CAPSULE_BLOCK_UNSET) {
                                ++g_capsule_error_count;
                                break;
                            }
                            capsule->block_spawn_values[x * 8 + y] =
                                *(const int32_t *)(node + 0x18u);
                            capsule->block_spawn_count =
                                (uint16_t)(capsule->block_spawn_count + 1);
                            if (tree_top + 2 > CAPSULE_TREE_STACK_CAP) {
                                ++g_capsule_error_count;
                                break;
                            }
                            tree_stack[tree_top++] =
                                *(const uintptr_t *)(node + 8u);
                            tree_stack[tree_top++] =
                                *(const uintptr_t *)(node + 0u);
                        }
                        if (visited_count != CAPSULE_TILE_CAP ||
                            capsule->block_spawn_count != CAPSULE_TILE_CAP) {
                            ++g_capsule_error_count;
                        }
                    }
                }

#define CAPSULE_COPY_POINT_VECTOR(begin_offset, end_offset, capacity_offset, \
        count_field, x_field, y_field) \
                do { \
                    LONG vector_count = 0; \
                    begin = *(const uintptr_t *)(board + (begin_offset)); \
                    end = *(const uintptr_t *)(board + (end_offset)); \
                    capacity = *(const uintptr_t *)(board + (capacity_offset)); \
                    if (begin == end) { \
                        if ((begin == 0 && capacity != 0) || \
                            (begin != 0 && \
                             (!hot_range_readable(begin, 1u) || \
                              capacity < end || \
                              (capacity - begin) % 8u != 0))) { \
                            ++g_capsule_error_count; \
                        } \
                    } else if ((begin & 3u) != 0 || end < begin || \
                        capacity < end || (end - begin) % 8u != 0 || \
                        (capacity - begin) % 8u != 0 || \
                        !hot_range_readable(begin, end - begin)) { \
                        ++g_capsule_error_count; \
                    } else { \
                        vector_count = (LONG)((end - begin) / 8u); \
                    } \
                    if (vector_count < 0 || \
                        vector_count > CAPSULE_POINT_CAP) { \
                        ++g_capsule_error_count; \
                    } else { \
                        capsule->count_field = (uint16_t)vector_count; \
                        for (point_index = 0; \
                             point_index < vector_count; \
                             ++point_index) { \
                            LONG px = *(const int32_t *)( \
                                begin + (uintptr_t)point_index * 8u); \
                            LONG py = *(const int32_t *)( \
                                begin + (uintptr_t)point_index * 8u + 4u); \
                            if (px < 0 || px >= 8 || py < 0 || py >= 8) { \
                                ++g_capsule_error_count; \
                                break; \
                            } \
                            for (index = 0; index < point_index; ++index) { \
                                if (capsule->x_field[index] == px && \
                                    capsule->y_field[index] == py) { \
                                    ++g_capsule_error_count; \
                                } \
                            } \
                            capsule->x_field[point_index] = px; \
                            capsule->y_field[point_index] = py; \
                        } \
                    } \
                } while (0)

                if (g_pointer_fault_count == 0 &&
                    g_capsule_error_count == 0) {
                    CAPSULE_COPY_POINT_VECTOR(
                        CAPSULE_BOARD_SPAWN_BEGIN_OFFSET,
                        CAPSULE_BOARD_SPAWN_END_OFFSET,
                        CAPSULE_BOARD_SPAWN_CAPACITY_OFFSET,
                        spawn_marker_count,
                        spawn_marker_x,
                        spawn_marker_y);
                    CAPSULE_COPY_POINT_VECTOR(
                        CAPSULE_BOARD_DANGER_A_BEGIN_OFFSET,
                        CAPSULE_BOARD_DANGER_A_END_OFFSET,
                        CAPSULE_BOARD_DANGER_A_CAPACITY_OFFSET,
                        dangerous_a_count,
                        dangerous_a_x,
                        dangerous_a_y);
                    CAPSULE_COPY_POINT_VECTOR(
                        CAPSULE_BOARD_DANGER_B_BEGIN_OFFSET,
                        CAPSULE_BOARD_DANGER_B_END_OFFSET,
                        CAPSULE_BOARD_DANGER_B_CAPACITY_OFFSET,
                        dangerous_b_count,
                        dangerous_b_x,
                        dangerous_b_y);
                }
#undef CAPSULE_COPY_POINT_VECTOR

                if (g_pointer_fault_count == 0 &&
                    g_capsule_error_count == 0) {
                    g_pending_capsule_index = capsule_index;
                    g_capsule_entry_count = capsule_index + 1;
                    capture_ok = 1;
                }
            }
        }
    } else {
        if (g_record_count < 0 || g_record_count >= OBS_RECORD_CAP) {
            ++g_overflow_count;
        } else {
            frame = (uintptr_t)context->Ebp;
            begin = 0;
            end = 0;
            count = (LONG)context->Esi;
            selected_index = (LONG)context->Edx;
            quotient = (LONG)context->Eax;
            if (frame < 0x00010050u || frame > 0x7fefff00u) {
                ++g_pointer_fault_count;
            } else if (ours == 1u) {
                if (g_pending_capsule_index != -1 ||
                    !hot_range_readable(frame + 8u, 8u)) {
                    ++g_pairing_error_count;
                } else {
                    begin = *(const uintptr_t *)(frame + 8u);
                    end = *(const uintptr_t *)(frame + 12u);
                }
            } else if (ours == 2u) {
                if (!hot_range_readable(frame - 0x44u, 8u)) {
                    ++g_pointer_fault_count;
                } else {
                    begin = (uintptr_t)context->Edi;
                    end = *(const uintptr_t *)(frame - 0x40u);
                    if (*(const uintptr_t *)(frame - 0x44u) != begin) {
                        ++g_candidate_error_count;
                    }
                }
            } else {
                if (!hot_range_readable(frame - 0x38u, 8u)) {
                    ++g_pointer_fault_count;
                } else {
                    begin = (uintptr_t)context->Ecx;
                    end = *(const uintptr_t *)(frame - 0x34u);
                    if (*(const uintptr_t *)(frame - 0x38u) != begin) {
                        ++g_candidate_error_count;
                    }
                }
            }
            if (g_pointer_fault_count == 0 &&
                g_candidate_error_count == 0 &&
                g_pairing_error_count == 0) {
                if ((begin & 3u) != 0 || end < begin || count < 1 ||
                    count > OBS_CANDIDATE_CAP ||
                    end - begin != (uintptr_t)count * 8u ||
                    selected_index < 0 || selected_index >= count ||
                    quotient < 0 || quotient > 32767 ||
                    !hot_range_readable(begin, (size_t)count * 8u)) {
                    ++g_candidate_error_count;
                }
            }
            if (g_pointer_fault_count == 0 &&
                g_candidate_error_count == 0 &&
                g_pairing_error_count == 0) {
                coordinates = (int32_t *)begin;
                record_index = g_record_count;
                record = &g_records[record_index];
                record->sequence = (uint32_t)record_index;
                record->candidate_count = (uint16_t)count;
                record->kind = ours == 1u ? OBS_RECORD_SCHEDULER :
                    (ours == 2u ? OBS_RECORD_SELECTOR_FALLBACK :
                        OBS_RECORD_SELECTOR_STANDARD);
                record->reserved = 0;
                record->selected_index = selected_index;
                record->rng_quotient = quotient;
                record->raw_rng = quotient * count + selected_index;
                record->selected_x = coordinates[selected_index * 2];
                record->selected_y = coordinates[selected_index * 2 + 1];
                for (index = 0; index < count; ++index) {
                    record->candidate_x[index] = coordinates[index * 2];
                    record->candidate_y[index] = coordinates[index * 2 + 1];
                }
                if (ours == 2u || ours == 4u) {
                    capsule_index = g_pending_capsule_index;
                    if (capsule_index < 0 ||
                        capsule_index >= g_capsule_entry_count ||
                        capsule_index != g_capsule_count ||
                        !hot_range_readable(
                            g_rng_state_address, sizeof(uint32_t))) {
                        ++g_pairing_error_count;
                    } else {
                        capsule = &g_capsules[capsule_index];
                        observed_rng_state =
                            *(const uint32_t *)g_rng_state_address;
                        expected_rng_state =
                            capsule->rng_state_before * 214013u + 2531011u;
                        if (observed_rng_state != expected_rng_state ||
                            record->raw_rng !=
                                (LONG)((expected_rng_state >> 16) & 0x7fffu)) {
                            ++g_rng_error_count;
                        } else {
                            capsule->draw_sequence = record_index;
                            capsule->selector_kind = (uint8_t)record->kind;
                            capsule->rng_state_after = observed_rng_state;
                            capsule->raw_rng = record->raw_rng;
                            capsule->selected_index = selected_index;
                            capsule->selected_x = record->selected_x;
                            capsule->selected_y = record->selected_y;
                            _ReadWriteBarrier();
                            capsule->committed = capsule_index + 1;
                            g_capsule_count = capsule_index + 1;
                            g_pending_capsule_index = -1;
                        }
                    }
                }
                if (g_pairing_error_count == 0 && g_rng_error_count == 0) {
                    _ReadWriteBarrier();
                    record->committed = record_index + 1;
                    g_record_count = record_index + 1;
                    if (ours == 1u) ++g_scheduler_count;
                    else if (ours == 2u) ++g_selector_fallback_count;
                    else ++g_selector_standard_count;
                    capture_ok = 1;
                }
            }
        }
    }

    g_handler_depth = 0;
    if (!capture_ok) {
        if (g_stop_reason == OBS_STOP_NONE) {
            g_stop_reason = g_pointer_fault_count != 0
                ? OBS_STOP_POINTER_FAULT
                : (g_overflow_count != 0
                    ? OBS_STOP_OVERFLOW
                    : (g_rng_error_count != 0
                        ? CAPSULE_STOP_RNG
                        : (g_pairing_error_count != 0
                            ? CAPSULE_STOP_PAIRING
                            : CAPSULE_STOP_CONTRACT)));
        }
        g_state = OBS_STATE_DRAINING;
    }
    return EXCEPTION_CONTINUE_EXECUTION;
}
#pragma code_seg(pop)
/* CAPSULE_HOT_PATH_END */

static int capsule_relocated_region_equal(
    const unsigned char *actual,
    const unsigned char *expected,
    size_t size) {
    uint32_t delta;
    size_t cursor = 0;
    size_t index;
    if (actual == NULL || expected == NULL || g_executable_base == NULL ||
        (uintptr_t)g_executable_base < OBS_PREFERRED_IMAGE_BASE) return 0;
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

static int capsule_live_identity(void) {
    capsule_rng_state_owner_fn owner;
    unsigned char *owner_result;
    if (!verify_live_identity() || g_executable_base == NULL ||
        !bytes_equal(
            g_executable_base + OBS_SELECTOR_ENTRY_RVA,
            OBS_SELECTOR_ENTRY_PREBYTES,
            OBS_SELECTOR_ENTRY_PREBYTE_SIZE) ||
        !capsule_relocated_region_equal(
            g_executable_base + OBS_RNG_STATE_OWNER_RVA,
            OBS_RNG_STATE_OWNER_BYTES,
            OBS_RNG_STATE_OWNER_SIZE)) return 0;
    g_selector_entry_address =
        (uintptr_t)(g_executable_base + OBS_SELECTOR_ENTRY_RVA);
    owner = (capsule_rng_state_owner_fn)(
        g_executable_base + OBS_RNG_STATE_OWNER_RVA);
    owner_result = owner();
    if (owner_result == NULL) return 0;
    g_rng_state_address =
        (uintptr_t)(owner_result + CAPSULE_RNG_STATE_OFFSET);
    return g_rng_state_address >= 0x00010000u &&
        g_rng_state_address <= 0x7ff00000u - sizeof(uint32_t);
}

static int capsule_seams_unchanged(void) {
    return seams_unchanged() && g_executable_base != NULL &&
        bytes_equal(
            g_executable_base + OBS_SELECTOR_ENTRY_RVA,
            OBS_SELECTOR_ENTRY_PREBYTES,
            OBS_SELECTOR_ENTRY_PREBYTE_SIZE) &&
        capsule_relocated_region_equal(
            g_executable_base + OBS_RNG_STATE_OWNER_RVA,
            OBS_RNG_STATE_OWNER_BYTES,
            OBS_RNG_STATE_OWNER_SIZE);
}

static void capsule_reset_capture_state(void) {
    reset_capture_state();
    byte_zero(g_capsules, sizeof(g_capsules));
    g_capsule_entry_count = 0;
    g_capsule_count = 0;
    g_capsule_error_count = 0;
    g_rng_error_count = 0;
    g_pairing_error_count = 0;
    g_torn_capsule_count = 0;
    g_pending_capsule_index = -1;
    g_selector_entry_address = 0;
    g_rng_state_address = 0;
}

static int capsule_arm_observer(lua_State *state) {
    const char *capture_id;
    size_t capture_length = 0;
    if (g_lua_gettop(state) != 1) {
        return g_luaL_error(state, "capsule observer arm requires one capture ID");
    }
    capture_id = g_luaL_checklstring(state, 1, &capture_length);
    if (!valid_capture_id(capture_id, capture_length)) {
        return g_luaL_error(state, "capsule observer capture ID is invalid");
    }
    if (g_consumed != 0) {
        return g_luaL_error(state, "native observer is one-shot per process");
    }
    g_consumed = 1;
    capsule_reset_capture_state();
    byte_copy(g_capture_id, capture_id, capture_length);
    g_capture_id[capture_length] = '\0';
    g_owner_thread_id = (DWORD)__readfsdword(0x24);
    if (!capsule_live_identity()) {
        request_stop_cold(OBS_STOP_IDENTITY_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "pinned capsule observer identity mismatch");
    }
    if (!build_readable_range_map()) {
        request_stop_cold(OBS_STOP_READABLE_MAP);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "capsule readable-range map failed");
    }
    g_state = OBS_STATE_VERIFIED;
    g_veh_handle = AddVectoredExceptionHandler(
        1, observer_spawn_coordinate_capsule_veh);
    if (g_veh_handle == NULL) {
        request_stop_cold(OBS_STOP_TRANSITION_MISMATCH);
        (void)release_executable_file();
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state, "capsule VEH installation failed");
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
        return g_luaL_error(state, "capsule debug-register arm failed");
    }
    g_lua_pushboolean(state, 1);
    return 1;
}

static LONG capsule_count_torn(void) {
    LONG count = g_capsule_count;
    LONG torn = 0;
    LONG index;
    if (count < 0) return 1;
    if (count > CAPSULE_RECORD_CAP) count = CAPSULE_RECORD_CAP;
    for (index = 0; index < count; ++index) {
        if (g_capsules[index].committed != index + 1 ||
            g_capsules[index].sequence != (uint32_t)index) ++torn;
    }
    return torn;
}

static void capsule_push_points(
    lua_State *state,
    const int32_t *xs,
    const int32_t *ys,
    LONG count,
    const char *key) {
    LONG index;
    g_lua_createtable(state, count, 0);
    for (index = 0; index < count; ++index) {
        g_lua_createtable(state, 0, 2);
        set_integer(state, "x", xs[index]);
        set_integer(state, "y", ys[index]);
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, key);
}

static void capsule_push_snapshot(lua_State *state) {
    LONG count = g_record_count;
    LONG capsule_count = g_capsule_count;
    LONG selector_count = g_selector_fallback_count +
        g_selector_standard_count;
    LONG torn = count_torn_records();
    LONG capsule_torn = capsule_count_torn();
    LONG reason = g_stop_reason;
    LONG index;
    LONG candidate_index;
    LONG x;
    LONG y;
    int complete;
    if (count < 0) count = 0;
    if (count > OBS_RECORD_CAP) count = OBS_RECORD_CAP;
    if (capsule_count < 0) capsule_count = 0;
    if (capsule_count > CAPSULE_RECORD_CAP) {
        capsule_count = CAPSULE_RECORD_CAP;
    }
    if ((torn != 0 || capsule_torn != 0) && reason == OBS_STOP_NONE) {
        reason = OBS_STOP_TORN_RECORD;
    }
    if ((selector_count == 0 || capsule_count == 0) &&
        reason == OBS_STOP_NONE) reason = OBS_STOP_SELECTOR_MISSING;
    if ((capsule_count != selector_count ||
         g_capsule_entry_count != capsule_count ||
         g_pending_capsule_index != -1) && reason == OBS_STOP_NONE) {
        reason = CAPSULE_STOP_PAIRING;
    }
    g_torn_record_count = torn;
    g_torn_capsule_count = capsule_torn;
    complete = g_state == OBS_STATE_RESTORED && reason == OBS_STOP_NONE &&
        count > 0 && selector_count > 0 && capsule_count == selector_count &&
        g_capsule_entry_count == capsule_count &&
        g_pending_capsule_index == -1 && torn == 0 && capsule_torn == 0 &&
        g_overflow_count == 0 && g_candidate_error_count == 0 &&
        g_capsule_error_count == 0 && g_rng_error_count == 0 &&
        g_pairing_error_count == 0 && g_pointer_fault_count == 0 &&
        g_transition_mismatch_count == 0 && g_wrong_thread_count == 0 &&
        g_unexpected_breakpoint_count == 0 && g_debug_armed == 0 &&
        g_debug_cleared != 0 && g_veh_installed == 0 &&
        g_veh_removed != 0 && g_executable_file_released != 0 &&
        g_seam_bytes_unchanged != 0;

    g_lua_createtable(state, 0, 8);
    set_integer(state, "schema_version", 1);
    set_string(state, "kind",
        "native_spawn_coordinate_capsule_hw_observer_snapshot");
    set_string(state, "observer_version", CAPSULE_VERSION);
    set_string(state, "capture_id", g_capture_id);

    g_lua_createtable(state, 0, 19);
    set_string(state, "platform", "windows");
    set_string(state, "architecture", "x86");
    set_string(state, "build_id", OBS_BUILD_ID);
    set_string(state, "executable_sha256", OBS_EXECUTABLE_SHA256);
    set_integer(state, "executable_size", OBS_EXECUTABLE_SIZE);
    set_string(state, "inventory_sha256", OBS_INVENTORY_SHA256);
    set_string(state, "boundary_map_sha256", OBS_BOUNDARY_MAP_SHA256);
    set_string(state, "spawn_candidate_boundary_sha256",
        OBS_SPAWN_CANDIDATE_BOUNDARY_SHA256);
    set_string(state, "position_observations_boundary_sha256",
        OBS_POSITION_OBSERVATIONS_BOUNDARY_SHA256);
    set_string(state, "hardware_breakpoint_plan_sha256",
        OBS_CAPSULE_HW_PLAN_SHA256);
    set_string(state, "selector_region_sha256", OBS_SELECTOR_REGION_SHA256);
    set_string(state, "selector_entry_prebytes_sha256",
        OBS_SELECTOR_ENTRY_PREBYTES_SHA256);
    set_string(state, "scheduler_prebytes_sha256",
        OBS_SCHEDULER_PREBYTES_SHA256);
    set_string(state, "selector_fallback_prebytes_sha256",
        OBS_SELECTOR_FALLBACK_PREBYTES_SHA256);
    set_string(state, "selector_standard_prebytes_sha256",
        OBS_SELECTOR_STANDARD_PREBYTES_SHA256);
    set_string(state, "rng_state_owner_sha256",
        OBS_RNG_STATE_OWNER_SHA256);
    g_lua_setfield(state, -2, "identity");

    g_lua_createtable(state, 0, 24);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "complete", complete);
    capsule_set_nullable_reason(state, reason);
    set_integer(state, "overflow_count", g_overflow_count);
    set_integer(state, "candidate_error_count", g_candidate_error_count);
    set_integer(state, "capsule_error_count", g_capsule_error_count);
    set_integer(state, "rng_error_count", g_rng_error_count);
    set_integer(state, "pairing_error_count", g_pairing_error_count);
    set_integer(state, "pointer_fault_count", g_pointer_fault_count);
    set_integer(state, "transition_mismatch_count",
        g_transition_mismatch_count);
    set_integer(state, "wrong_thread_count", g_wrong_thread_count);
    set_integer(state, "unexpected_breakpoint_count",
        g_unexpected_breakpoint_count);
    set_integer(state, "torn_record_count", torn);
    set_integer(state, "torn_capsule_count", capsule_torn);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_boolean(state, "veh_removed", g_veh_removed);
    set_boolean(state, "executable_file_released",
        g_executable_file_released);
    set_boolean(state, "executable_bytes_modified", 0);
    set_boolean(state, "seam_bytes_unchanged", g_seam_bytes_unchanged);
    set_boolean(state, "addresses_or_pointers_published", 0);
    g_lua_setfield(state, -2, "integrity");

    g_lua_createtable(state, count, 0);
    for (index = 0; index < count; ++index) {
        obs_record *draw = &g_records[index];
        const char *kind = draw->kind == OBS_RECORD_SCHEDULER
            ? "scheduler_draw"
            : (draw->kind == OBS_RECORD_SELECTOR_FALLBACK
                ? "selector_fallback_draw" : "selector_standard_draw");
        g_lua_createtable(state, 0, 10);
        set_string(state, "kind", kind);
        set_integer(state, "seq", (LONG)draw->sequence);
        set_integer(state, "candidate_count", (LONG)draw->candidate_count);
        set_integer(state, "selected_index", draw->selected_index);
        set_integer(state, "rng_quotient", draw->rng_quotient);
        set_integer(state, "raw_rng", draw->raw_rng);
        set_integer(state, "selected_x", draw->selected_x);
        set_integer(state, "selected_y", draw->selected_y);
        g_lua_createtable(state, draw->candidate_count, 0);
        for (candidate_index = 0;
             candidate_index < (LONG)draw->candidate_count;
             ++candidate_index) {
            g_lua_createtable(state, 0, 2);
            set_integer(state, "x", draw->candidate_x[candidate_index]);
            set_integer(state, "y", draw->candidate_y[candidate_index]);
            g_lua_rawseti(state, -2, (int)candidate_index + 1);
        }
        g_lua_setfield(state, -2, "candidates");
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, "draw_records");

    g_lua_createtable(state, capsule_count, 0);
    for (index = 0; index < capsule_count; ++index) {
        capsule_record *item = &g_capsules[index];
        LONG tile_index;
        const char *kind = item->selector_kind == OBS_RECORD_SELECTOR_FALLBACK
            ? "selector_fallback_draw" : "selector_standard_draw";
        g_lua_createtable(state, 0, 18);
        set_integer(state, "seq", (LONG)item->sequence);
        set_integer(state, "draw_seq", item->draw_sequence);
        set_string(state, "selector_kind", kind);
        set_integer(state, "board_width", item->board_width);
        set_integer(state, "board_height", item->board_height);
        set_integer(state, "board_turn", item->board_turn);
        set_integer(state, "pawn_id", item->pawn_id);
        set_integer(state, "pawn_team", item->pawn_team);
        capsule_set_u32_hex(state, "rng_state_before",
            item->rng_state_before);
        capsule_set_u32_hex(state, "rng_state_after",
            item->rng_state_after);
        set_integer(state, "raw_rng", item->raw_rng);
        set_integer(state, "selected_index", item->selected_index);
        set_integer(state, "selected_x", item->selected_x);
        set_integer(state, "selected_y", item->selected_y);

        g_lua_createtable(state, item->block_spawn_count, 0);
        for (x = 0; x < 8; ++x) {
            for (y = 0; y < 8; ++y) {
                tile_index = x * 8 + y;
                g_lua_createtable(state, 0, 3);
                set_integer(state, "x", x);
                set_integer(state, "y", y);
                set_integer(state, "value",
                    item->block_spawn_values[tile_index]);
                g_lua_rawseti(state, -2, (int)tile_index + 1);
            }
        }
        g_lua_setfield(state, -2, "block_spawn_values");
        capsule_push_points(state, item->spawn_marker_x,
            item->spawn_marker_y, item->spawn_marker_count,
            "spawn_markers");
        capsule_push_points(state, item->dangerous_a_x,
            item->dangerous_a_y, item->dangerous_a_count,
            "dangerous_points_a");
        capsule_push_points(state, item->dangerous_b_x,
            item->dangerous_b_y, item->dangerous_b_count,
            "dangerous_points_b");

        g_lua_createtable(state, item->tile_count, 0);
        for (x = 0; x < 8; ++x) {
            for (y = 0; y < 8; ++y) {
                capsule_tile_record *tile_item;
                tile_index = x * 8 + y;
                tile_item = &item->tiles[tile_index];
                g_lua_createtable(state, 0, 9);
                set_integer(state, "x", x);
                set_integer(state, "y", y);
                set_integer(state, "terrain", tile_item->terrain);
                set_integer(state, "pod_state", tile_item->pod_state);
                set_boolean(state, "item_present", tile_item->item_present);
                set_boolean(state, "acid", tile_item->acid);
                set_boolean(state, "dangerous_flag",
                    tile_item->dangerous_flag);
                set_integer(state, "occupancy_count",
                    tile_item->occupancy_count);
                g_lua_createtable(state, tile_item->occupancy_count, 0);
                for (candidate_index = 0;
                     candidate_index < tile_item->occupancy_count;
                     ++candidate_index) {
                    g_lua_pushinteger(state, (lua_Integer)
                        tile_item->occupant_ids[candidate_index]);
                    g_lua_rawseti(state, -2, (int)candidate_index + 1);
                }
                g_lua_setfield(state, -2, "occupant_ids");
                g_lua_rawseti(state, -2, (int)tile_index + 1);
            }
        }
        g_lua_setfield(state, -2, "tiles");
        g_lua_rawseti(state, -2, (int)index + 1);
    }
    g_lua_setfield(state, -2, "capsules");

    g_lua_createtable(state, 0, 10);
    set_integer(state, "draw_record_count", count);
    set_integer(state, "scheduler_count", g_scheduler_count);
    set_integer(state, "selector_fallback_count",
        g_selector_fallback_count);
    set_integer(state, "selector_standard_count",
        g_selector_standard_count);
    set_integer(state, "selector_count", selector_count);
    set_integer(state, "capsule_entry_count", g_capsule_entry_count);
    set_integer(state, "capsule_count", capsule_count);
    set_integer(state, "thread_count", g_capture_started != 0 ? 1 : 0);
    set_integer(state, "last_draw_sequence", count - 1);
    set_integer(state, "last_capsule_sequence", capsule_count - 1);
    g_lua_setfield(state, -2, "summary");
}

static int capsule_finish_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "capsule observer finish takes no arguments");
    }
    if (g_consumed == 0 || g_capture_started == 0) {
        return g_luaL_error(state, "native observer is not active");
    }
    if ((DWORD)__readfsdword(0x24) != g_owner_thread_id) {
        ++g_wrong_thread_count;
        request_stop_cold(OBS_STOP_WRONG_THREAD);
        return g_luaL_error(state, "capsule observer must finish on its arm thread");
    }
    if (g_state != OBS_STATE_CAPTURING &&
        g_state != OBS_STATE_DRAINING &&
        g_state != OBS_STATE_FAILED_ARMED) {
        return g_luaL_error(state, "native observer cannot be finished");
    }
    if (g_record_count == 0) request_stop_cold(OBS_STOP_EMPTY_CAPTURE);
    if (g_capsule_count == 0) request_stop_cold(OBS_STOP_SELECTOR_MISSING);
    if (g_pending_capsule_index != -1 ||
        g_capsule_count != g_capsule_entry_count) {
        request_stop_cold(CAPSULE_STOP_PAIRING);
    }
    g_state = OBS_STATE_DRAINING;
    if (!run_transition(OBS_TRANSITION_CLEAR) || g_debug_cleared == 0 ||
        g_debug_armed != 0) {
        g_state = OBS_STATE_FAILED_ARMED;
        return g_luaL_error(state,
            "capsule debug-register clearing failed; no checkpoint published");
    }
    if (g_veh_handle == NULL ||
        RemoveVectoredExceptionHandler(g_veh_handle) == 0) {
        request_stop_cold(OBS_STOP_VEH_REMOVE);
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state,
            "capsule VEH removal failed; no checkpoint published");
    }
    g_veh_handle = NULL;
    g_veh_installed = 0;
    g_veh_removed = 1;
    g_seam_bytes_unchanged = capsule_seams_unchanged();
    if (!g_seam_bytes_unchanged || !release_executable_file()) {
        g_state = OBS_STATE_FAILED_CLEAN;
        return g_luaL_error(state,
            "capsule observer integrity finalization failed");
    }
    g_state = OBS_STATE_RESTORED;
    capsule_push_snapshot(state);
    return 1;
}

static int capsule_status_observer(lua_State *state) {
    if (g_lua_gettop(state) != 0) {
        return g_luaL_error(state, "capsule observer status takes no arguments");
    }
    g_lua_createtable(state, 0, 17);
    set_string(state, "state", state_text(g_state));
    set_boolean(state, "consumed", g_consumed);
    set_boolean(state, "capture_started", g_capture_started);
    set_integer(state, "draw_record_count", g_record_count);
    set_integer(state, "scheduler_count", g_scheduler_count);
    set_integer(state, "selector_fallback_count",
        g_selector_fallback_count);
    set_integer(state, "selector_standard_count",
        g_selector_standard_count);
    set_integer(state, "capsule_entry_count", g_capsule_entry_count);
    set_integer(state, "capsule_count", g_capsule_count);
    set_integer(state, "pending_capsule_index", g_pending_capsule_index);
    set_boolean(state, "debug_registers_armed", g_debug_armed);
    set_boolean(state, "debug_registers_cleared", g_debug_cleared);
    set_boolean(state, "veh_installed", g_veh_installed);
    set_integer(state, "capsule_error_count", g_capsule_error_count);
    set_integer(state, "rng_error_count", g_rng_error_count);
    set_integer(state, "pairing_error_count", g_pairing_error_count);
    capsule_set_nullable_reason(state, g_stop_reason);
    return 1;
}

__declspec(dllexport) int __cdecl
luaopen_itb_observatory_spawn_coordinate_capsule_hw_observer(
    lua_State *state) {
    if (!resolve_lua_api()) return 0;
    if (!pin_this_module()) {
        return g_luaL_error(state, "native capsule observer module pin failed");
    }
    g_lua_createtable(state, 0, 12);
    set_string(state, "VERSION", CAPSULE_VERSION);
    set_string(state, "BUILD_ID", OBS_BUILD_ID);
    set_string(state, "EXECUTABLE_SHA256", OBS_EXECUTABLE_SHA256);
    set_string(state, "ARCHITECTURE", "x86");
    set_string(state, "SELECTOR_ENTRY_RVA", OBS_SELECTOR_ENTRY_RVA_TEXT);
    set_string(state, "SCHEDULER_RVA", OBS_SCHEDULER_RVA_TEXT);
    set_string(state, "SELECTOR_FALLBACK_RVA",
        OBS_SELECTOR_FALLBACK_RVA_TEXT);
    set_string(state, "SELECTOR_STANDARD_RVA",
        OBS_SELECTOR_STANDARD_RVA_TEXT);
    set_string(state, "RNG_STATE_OWNER_RVA",
        OBS_RNG_STATE_OWNER_RVA_TEXT);
    set_string(state, "HARDWARE_BREAKPOINT_PLAN_SHA256",
        OBS_CAPSULE_HW_PLAN_SHA256);
    g_lua_pushcclosure(state, capsule_arm_observer, 0);
    g_lua_setfield(state, -2, "arm");
    g_lua_pushcclosure(state, capsule_finish_observer, 0);
    g_lua_setfield(state, -2, "finish");
    g_lua_pushcclosure(state, capsule_status_observer, 0);
    g_lua_setfield(state, -2, "status");
    return 1;
}
