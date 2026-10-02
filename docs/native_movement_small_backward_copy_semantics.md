# Small backward overlapping copy semantics

`src/observatory/native_movement_small_backward_copy_semantics.py` predicts the
backward scalar arm at CRT entry RVA3703E0. Count is2..31 and pointers satisfy
`source < destination < source + count`. The mapped nonwrapping overlapping
union is disjoint from the complete protected caller stack. No imports, CPU
feature reads or direction-setting instructions execute in this bounded arm.

The five-input API returns a complete eleven-field packet. For `q,r=divmod(N,4)`,
DWORD offsets descend as `N-4*(i+1)`, then byte offsets descend as `r-i-1`.
Actual evolving reads and writes are recorded. Final destination equals the
original source snapshot; the overlapping source region legitimately changes.
Separate direct final pages bind stack saves and exact original-source blit.

Final EAX is destination, ECX zero, EDX remains the original count, and ESP
advances four. All nonvolatile registers and eight XMM values preserve. Final
defined flags are44, mask8C5 for no byte tail or8D5 after a byte tail; DF is
zero. Instructions number `24+7*q+6*r`, accesses `9+2*q+2*r`. Sparse body
identity, all selected literal instruction points, ABI and caller bytes are
pinned.

Independent source review is GO. All8,216 independent checks pass without
skips in56.13seconds. The suite covers all465 valid count/shift pairs at sixteen
alignments,128 ordinary flags at four recipes, full packets, direct overlap
bytes versus independent descending replay, strict typed schemas, prewrite
rejection ledgers and detachment. All1,860 complete native cases agree across
every overlap pair and four alignments, including flags, DF and endpoints.

Counts32 and above, larger/SIMD branches, ownership, gameplay and broader
native receipt sealing remain separate gates. Whole-program accounting is
unchanged.
