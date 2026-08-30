//! Compile stdin with an explicitly supplied 32-bit Lua 5.1 DLL and dump the
//! resulting chunk to stdout without executing it.

#![cfg(target_os = "windows")]

use std::env;
use std::ffi::{c_char, c_int, c_void, CStr, CString, OsStr};
use std::io::{self, Read, Write};
use std::mem;
use std::os::windows::ffi::OsStrExt;
use std::slice;

type LuaState = c_void;
type LuaLNewState = unsafe extern "C" fn() -> *mut LuaState;
type LuaClose = unsafe extern "C" fn(*mut LuaState);
type LuaLLoadBuffer = unsafe extern "C" fn(
    *mut LuaState,
    *const c_char,
    usize,
    *const c_char,
) -> c_int;
type LuaWriter = unsafe extern "C" fn(
    *mut LuaState,
    *const c_void,
    usize,
    *mut c_void,
) -> c_int;
type LuaDump = unsafe extern "C" fn(*mut LuaState, LuaWriter, *mut c_void) -> c_int;
type LuaToLString =
    unsafe extern "C" fn(*mut LuaState, c_int, *mut usize) -> *const c_char;

const MAX_SOURCE_BYTES: usize = 64 * 1024 * 1024;
const MAX_BYTECODE_BYTES: usize = 512 * 1024 * 1024;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn LoadLibraryW(name: *const u16) -> *mut c_void;
    fn GetProcAddress(module: *mut c_void, name: *const c_char) -> *mut c_void;
    fn FreeLibrary(module: *mut c_void) -> c_int;
}

struct Api {
    module: *mut c_void,
    new_state: LuaLNewState,
    close: LuaClose,
    load_buffer: LuaLLoadBuffer,
    dump: LuaDump,
    to_lstring: LuaToLString,
}

impl Drop for Api {
    fn drop(&mut self) {
        unsafe {
            FreeLibrary(self.module);
        }
    }
}

unsafe fn symbol<T: Copy>(module: *mut c_void, name: &CStr) -> Result<T, String> {
    let address = unsafe { GetProcAddress(module, name.as_ptr()) };
    if address.is_null() {
        return Err(format!(
            "Lua DLL does not export {}",
            name.to_string_lossy()
        ));
    }
    if mem::size_of::<T>() != mem::size_of::<*mut c_void>() {
        return Err("unexpected function-pointer size".to_string());
    }
    Ok(unsafe { mem::transmute_copy(&address) })
}

fn load_api(path: &OsStr) -> Result<Api, String> {
    let mut wide: Vec<u16> = path.encode_wide().collect();
    wide.push(0);
    let module = unsafe { LoadLibraryW(wide.as_ptr()) };
    if module.is_null() {
        return Err("could not load the supplied Lua DLL".to_string());
    }
    let loaded = unsafe {
        (|| {
            Ok(Api {
                module,
                new_state: symbol(module, c"luaL_newstate")?,
                close: symbol(module, c"lua_close")?,
                load_buffer: symbol(module, c"luaL_loadbuffer")?,
                dump: symbol(module, c"lua_dump")?,
                to_lstring: symbol(module, c"lua_tolstring")?,
            })
        })()
    };
    if loaded.is_err() {
        unsafe {
            FreeLibrary(module);
        }
    }
    loaded
}

unsafe extern "C" fn writer(
    _state: *mut LuaState,
    bytes: *const c_void,
    size: usize,
    user_data: *mut c_void,
) -> c_int {
    if user_data.is_null() || (bytes.is_null() && size != 0) {
        return 1;
    }
    let output = unsafe { &mut *(user_data as *mut Vec<u8>) };
    match output.len().checked_add(size) {
        Some(total) if total <= MAX_BYTECODE_BYTES => {}
        _ => return 1,
    }
    if output.try_reserve(size).is_err() {
        return 1;
    }
    if size != 0 {
        output.extend_from_slice(unsafe { slice::from_raw_parts(bytes as *const u8, size) });
    }
    0
}

fn lua_error(api: &Api, state: *mut LuaState) -> String {
    let mut size = 0usize;
    let message = unsafe { (api.to_lstring)(state, -1, &mut size) };
    if message.is_null() {
        return "Lua compiler returned an unknown error".to_string();
    }
    let bytes = unsafe { slice::from_raw_parts(message as *const u8, size) };
    String::from_utf8_lossy(bytes).into_owned()
}

fn parse_args() -> Result<(String, String), String> {
    let mut dll = None;
    let mut chunk_name = None;
    let mut args = env::args().skip(1);
    while let Some(argument) = args.next() {
        let value = args
            .next()
            .ok_or_else(|| format!("missing value for {argument}"))?;
        match argument.as_str() {
            "--dll" if dll.is_none() => dll = Some(value),
            "--chunk-name" if chunk_name.is_none() => chunk_name = Some(value),
            _ => return Err(format!("unexpected argument: {argument}")),
        }
    }
    Ok((
        dll.ok_or_else(|| "missing --dll".to_string())?,
        chunk_name.ok_or_else(|| "missing --chunk-name".to_string())?,
    ))
}

fn run() -> Result<(), String> {
    let (dll, chunk_name) = parse_args()?;
    let name = CString::new(chunk_name).map_err(|_| "chunk name contains NUL")?;
    let mut source = Vec::new();
    io::stdin()
        .take((MAX_SOURCE_BYTES + 1) as u64)
        .read_to_end(&mut source)
        .map_err(|error| format!("could not read source from stdin: {error}"))?;
    if source.len() > MAX_SOURCE_BYTES {
        return Err("source exceeds the 64 MiB protocol limit".to_string());
    }
    let api = load_api(OsStr::new(&dll))?;
    let state = unsafe { (api.new_state)() };
    if state.is_null() {
        return Err("luaL_newstate failed".to_string());
    }
    let status = unsafe {
        (api.load_buffer)(
            state,
            source.as_ptr() as *const c_char,
            source.len(),
            name.as_ptr(),
        )
    };
    if status != 0 {
        let message = lua_error(&api, state);
        unsafe {
            (api.close)(state);
        }
        return Err(format!("Lua compilation failed: {message}"));
    }
    let mut output = Vec::new();
    let dump_status = unsafe {
        (api.dump)(
            state,
            writer,
            &mut output as *mut Vec<u8> as *mut c_void,
        )
    };
    unsafe {
        (api.close)(state);
    }
    if dump_status != 0 {
        return Err("lua_dump failed".to_string());
    }
    io::stdout()
        .write_all(&output)
        .map_err(|error| format!("could not write bytecode to stdout: {error}"))?;
    io::stdout()
        .flush()
        .map_err(|error| format!("could not flush stdout: {error}"))?;
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        let _ = writeln!(io::stderr(), "error: {error}");
        std::process::exit(2);
    }
}
