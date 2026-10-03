"""Original SetActive body in explicitly supplied receiver storage.

This is a setter microproof, not original Pawn construction, IsActive, Wait UI,
or a completed gameplay action. No native helper/import result is substituted.
"""
from __future__ import annotations

from pathlib import Path

from src.observatory.solver_first_path_oracle import (
    BOARD, ROOT, STACK, EXE_SHA, Machine, OriginalSource, canonical,
    require, runtime_identity, sha,
)

ENTRY = 0x2375F0
BODY_SHA = "247eccc6d4587cf6101b169dfd98bc1ea9d20582a8fb27330ae9c6be3f336554"
RECEIVER = BOARD + 0x80000
RECEIVER_SIZE = 0x1200
ACTIVE, GATE, MECH = 0x91C, 0x10C0, 0x9E4


def recipes():
    # Expected storage laws come from independent original static review.
    return [dict(id=name, initial=initial, requested=requested, gate=gate,
                 expected=expected) for name, initial, requested, gate, expected in [
        ("disable_mech_storage", 1, 0, 1, 0),
        ("enable_mech_storage", 0, 1, 1, 1),
        ("already_disabled", 0, 0, 1, 0),
        ("already_enabled", 1, 1, 1, 1),
        ("gate_zero_disable", 1, 0, 0, 1),
        ("gate_zero_enable", 0, 1, 0, 0),
    ]]


def run(executable, *, private_dir=None):
    source = OriginalSource(executable)
    source.verify(ENTRY)
    identity = source.verified[ENTRY]
    require(identity["body_size"] == 83 and identity["body_sha256"] == BODY_SHA,
            "setter body identity differs")
    report = dict(
        schema_version=1, corpus_version="s1-readiness-setter-storage-development-v1",
        baseline_commit="96e497206def812904e6a4370a672c1c43c695e9",
        evidence_class="bounded_original_body_execution_with_supplied_receiver_storage",
        executable_sha256=EXE_SHA, atlas_canonical_sha256=source.atlas_sha,
        original_body=identity, runtime=runtime_identity() | dict(instruction_limit=100),
        source_sha256={p: sha((ROOT / p).read_bytes()) for p in (
            "src/observatory/solver_first_readiness_leaf.py",
            "src/observatory/solver_first_path_oracle.py",
            "src/observatory/pe_anchor_map.py", "scripts/solver_first_readiness_leaf.py")},
        solver_facing_question="Does the original SetActive(false) mech-storage branch change only the stored active byte?",
        supplied_boundaries=dict(
            receiver_size=RECEIVER_SIZE,
            active_offset="0x91c", gate_offset="0x10c0", mech_offset="0x9e4",
            mech_byte=1, other_receiver_bytes="deterministic sentinel pattern; no complete constructor claim",
            argument="one zero-extended 32-bit word, interpreted as a byte",
            external_responses="none reached; no helper return substitution",
            source_runtime="original executable body; emulator memory/register initialization supplied"),
        information_mode="offline_validation_oracle_only_no_planner_input",
        objective="stored_active_byte_and_unchanged_receiver_projection",
        source_review_packet_sha256="5356d082377c89271a046f3b56b38fa69bea3b7474922e2942ee5029b12e51ac",
        original_game_observations=0, original_completed_action_transitions=0,
        full_turn_original_comparisons=0, ledger_promotions=0,
        legal_action_admissions=0, transition_gate_admissions=0,
        search_quality="not_evaluated", held_out_evaluation="not_evaluated",
        scope_exclusions=["complete Pawn/Board construction", "original IsActive getter",
            "nonmech helper branch", "original Wait UI and callbacks", "movement/weapon consumption",
            "turn reset", "enemy/environment resolution", "full tactical continuity",
            "gameplay content/overlay provenance", "held-out original transitions"],
        cases=[], failures=[], mismatches=[])
    for recipe in recipes():
        row = dict(recipe=recipe, admitted=False, passed=False)
        m = None
        try:
            m = Machine(source)
            blob = bytearray((i * 37 + 17) & 255 for i in range(RECEIVER_SIZE))
            blob[ACTIVE], blob[GATE], blob[MECH] = recipe["initial"], recipe["gate"], 1
            m.uc.mem_write(RECEIVER, bytes(blob))
            before = bytes(m.uc.mem_read(BOARD, 0x200000))
            accesses = []

            def audit_memory(uc, kind, address, width, value, _):
                try:
                    if STACK <= address and address + width <= STACK + 0x10000:
                        return
                    require(RECEIVER <= address and address + width <= RECEIVER + RECEIVER_SIZE,
                            "access outside supplied receiver/stack")
                    offset = address - RECEIVER
                    is_write = kind == m.u.UC_MEM_WRITE
                    require(width == 1 and offset in (ACTIVE, GATE, MECH),
                            "unreviewed receiver field access")
                    require(not is_write or offset == ACTIVE, "write outside stored active byte")
                    accesses.append(dict(kind="write" if is_write else "read",
                                         offset=f"0x{offset:x}", width=width,
                                         value=value if is_write else int(uc.mem_read(address, width)[0])))
                except Exception as exc:
                    m.fail(exc)

            m.uc.hook_add(m.u.UC_HOOK_MEM_READ | m.u.UC_HOOK_MEM_WRITE, audit_memory)
            preserved = {m.x.UC_X86_REG_EBX: 0x11223344,
                         m.x.UC_X86_REG_ESI: 0x55667788,
                         m.x.UC_X86_REG_EBP: 0x12345678}
            for register, value in preserved.items():
                m.uc.reg_write(register, value)
            receipt = m.call(ENTRY, [recipe["requested"]], receiver=RECEIVER, limit=100)
            require(not m.imports, "unexpected native import response")
            require(all(ENTRY <= rva < ENTRY + 83 for rva, _ in m.trace),
                    "unexpected helper body execution")
            require(all(m.uc.reg_read(register) == value for register, value in preserved.items()),
                    "callee-saved register differs")
            after = bytes(m.uc.mem_read(BOARD, 0x200000))
            changed = [i - (RECEIVER - BOARD) for i, (a, b) in enumerate(zip(before, after)) if a != b]
            expected_changes = [ACTIVE] if recipe["initial"] != recipe["expected"] else []
            expected_blob = bytearray(blob)
            expected_blob[ACTIVE] = recipe["expected"]
            actual_blob = bytes(m.uc.mem_read(RECEIVER, RECEIVER_SIZE))
            row.update(admitted=True, original_return=receipt | dict(
                receiver="supplied receiver storage", stack_cleanup_bytes=4,
                callee_saved_registers_preserved=True, helper_calls=0,
                return_value="void; EAX/AL not interpreted as success"),
                before_receiver_sha256=sha(blob), after_receiver_sha256=sha(actual_blob),
                before_world_storage_sha256=sha(before), after_world_storage_sha256=sha(after),
                changed_receiver_offsets=[f"0x{i:x}" for i in changed],
                accesses=accesses, stored_active_after=actual_blob[ACTIVE])
            require(changed == expected_changes and actual_blob == bytes(expected_blob),
                    "stored-byte projection mismatch")
            if private_dir:
                with (private_dir / (recipe["id"] + ".json")).open("x", encoding="utf-8", newline="\n") as out:
                    out.write(canonical(dict(trace=m.trace, imports=m.imports, accesses=accesses,
                                             recipe=recipe, original_return=receipt)).decode())
            row["passed"] = True
        except Exception as exc:
            failure = dict(id=recipe["id"], reason=str(exc))
            if m:
                failure["partial_execution"] = m.diagnostic()
            report["failures"].append(failure)
            if row["admitted"]:
                report["mismatches"].append(failure)
            row["failure"] = str(exc)
        report["cases"].append(row)
    require(sha(Path(executable).read_bytes()) == EXE_SHA, "executable changed during evaluation")
    report.update(attempted=len(report["cases"]), admitted=sum(r["admitted"] for r in report["cases"]),
                  passed=sum(r["passed"] for r in report["cases"]), failed=len(report["failures"]), excluded=0)
    return report
