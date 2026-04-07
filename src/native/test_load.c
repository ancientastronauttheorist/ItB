/*
 * Feasibility test: Can Into the Breach's Lua load a native dylib?
 * Zero Lua symbol dependencies — treats lua_State as opaque void*.
 * Writes a marker file to prove the function was called.
 */
#include <stdio.h>

int luaopen_itb_test(void *L) {
    (void)L;  /* unused — we can't call any Lua C API */
    FILE *f = fopen("/tmp/itb_native_test.txt", "w");
    if (f) {
        fprintf(f, "NATIVE_OK\n");
        fclose(f);
    }
    return 0;  /* Lua interprets this as 0 return values pushed */
}
