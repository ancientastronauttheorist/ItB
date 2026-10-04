"""Real host OpenGL texture service for a bounded original x86 upload probe.

An isolated hidden utility window owns the context; no game process is touched.
This is an external API bridge, not execution of the game's x86 OpenGL DLL.
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path

from src.observatory import solver_first_path_oracle as api


class PixelFormat(c.Structure):
    _fields_ = [("nSize", w.WORD), ("nVersion", w.WORD), ("dwFlags", w.DWORD)] + [
        (name, c.c_ubyte) for name in (
            "iPixelType", "cColorBits", "cRedBits", "cRedShift", "cGreenBits", "cGreenShift",
            "cBlueBits", "cBlueShift", "cAlphaBits", "cAlphaShift", "cAccumBits", "cAccumRedBits",
            "cAccumGreenBits", "cAccumBlueBits", "cAccumAlphaBits", "cDepthBits", "cStencilBits",
            "cAuxBuffers", "iLayerType", "bReserved")
    ] + [(name, w.DWORD) for name in ("dwLayerMask", "dwVisibleMask", "dwDamageMask")]


def bind(library, name, result, args):
    function = getattr(library, name)
    function.restype, function.argtypes = result, args
    return function


class TextureContext:
    def __init__(self):
        api.require(os.name == "nt" and c.sizeof(c.c_void_p) == 8, "requires isolated Windows x64 host")
        api.require(c.sizeof(PixelFormat) == 40, "pixel-format ABI differs")
        self.window = self.dc = self.context = None
        self.textures, self.cleanup, self.identity = set(), {}, {}
        self.user = c.WinDLL("user32", use_last_error=True)
        self.gdi = c.WinDLL("gdi32", use_last_error=True)
        self.gl = c.WinDLL("opengl32", use_last_error=True)
        self.create_window = bind(self.user, "CreateWindowExW", w.HWND,
            [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.c_int, c.c_int, c.c_int, c.c_int,
             w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p])
        self.destroy_window = bind(self.user, "DestroyWindow", w.BOOL, [w.HWND])
        self.get_dc = bind(self.user, "GetDC", w.HDC, [w.HWND])
        self.release_dc = bind(self.user, "ReleaseDC", c.c_int, [w.HWND, w.HDC])
        choose = bind(self.gdi, "ChoosePixelFormat", c.c_int, [w.HDC, c.POINTER(PixelFormat)])
        set_format = bind(self.gdi, "SetPixelFormat", w.BOOL, [w.HDC, c.c_int, c.POINTER(PixelFormat)])
        create_context = bind(self.gl, "wglCreateContext", w.HANDLE, [w.HDC])
        self.make_current = bind(self.gl, "wglMakeCurrent", w.BOOL, [w.HDC, w.HANDLE])
        self.delete_context = bind(self.gl, "wglDeleteContext", w.BOOL, [w.HANDLE])
        self.get_current = bind(self.gl, "wglGetCurrentContext", w.HANDLE, [])
        self.get_error = bind(self.gl, "glGetError", c.c_uint, [])
        get_string = bind(self.gl, "glGetString", c.c_char_p, [c.c_uint])
        self.generate = bind(self.gl, "glGenTextures", None, [c.c_int, c.POINTER(c.c_uint)])
        self.bind_texture = bind(self.gl, "glBindTexture", None, [c.c_uint, c.c_uint])
        self.parameter_i = bind(self.gl, "glTexParameteri", None, [c.c_uint, c.c_uint, c.c_int])
        self.parameter_fv = bind(self.gl, "glTexParameterfv", None,
            [c.c_uint, c.c_uint, c.POINTER(c.c_float)])
        self.upload = bind(self.gl, "glTexImage2D", None,
            [c.c_uint, c.c_int, c.c_int, c.c_int, c.c_int, c.c_int, c.c_uint, c.c_uint, c.c_void_p])
        self.is_texture = bind(self.gl, "glIsTexture", c.c_ubyte, [c.c_uint])
        self.level = bind(self.gl, "glGetTexLevelParameteriv", None,
            [c.c_uint, c.c_int, c.c_uint, c.POINTER(c.c_int)])
        self.download = bind(self.gl, "glGetTexImage", None,
            [c.c_uint, c.c_int, c.c_uint, c.c_uint, c.c_void_p])
        self.delete_textures = bind(self.gl, "glDeleteTextures", None, [c.c_int, c.POINTER(c.c_uint)])
        kernel = c.WinDLL("kernel32", use_last_error=True)
        module_path = bind(kernel, "GetModuleFileNameW", w.DWORD, [w.HMODULE, w.LPWSTR, w.DWORD])
        self.module_identity = {}
        for library in (self.user, self.gdi, self.gl):
            buffer = c.create_unicode_buffer(32768)
            count = module_path(library._handle, buffer, len(buffer))
            api.require(0 < count < len(buffer), "host module path unavailable")
            raw = Path(buffer.value).read_bytes()
            self.module_identity[Path(buffer.value).name] = dict(size=len(raw), sha256=api.sha(raw))
        try:
            api.require(not self.get_current(), "unexpected existing host context")
            self.window = self.create_window(0, "STATIC", "Offline texture acquisition", 0,
                                            0, 0, 32, 32, None, None, None, None)
            api.require(bool(self.window), "hidden utility window creation failed")
            self.dc = self.get_dc(self.window)
            api.require(bool(self.dc), "device-context acquisition failed")
            descriptor = PixelFormat(nSize=40, nVersion=1, dwFlags=0x25, iPixelType=0,
                                     cColorBits=32, cAlphaBits=8, cDepthBits=24, cStencilBits=8)
            self.pixel_format = choose(self.dc, c.byref(descriptor))
            api.require(self.pixel_format > 0 and set_format(self.dc, self.pixel_format, c.byref(descriptor)),
                        "pixel-format setup failed")
            self.context = create_context(self.dc)
            api.require(bool(self.context) and self.make_current(self.dc, self.context), "context setup failed")
            self.identity = dict(vendor=get_string(0x1f00).decode("ascii"),
                renderer=get_string(0x1f01).decode("ascii"), version=get_string(0x1f02).decode("ascii"),
                pixel_format=self.pixel_format, host_modules=self.module_identity)
            self.check()
        except Exception as exc:
            try:
                self.close()
            except Exception as cleanup_exc:
                raise RuntimeError(f"{exc}; cleanup: {cleanup_exc}") from exc
            raise

    def check(self):
        api.require(self.get_current() == self.context, "host context changed")
        error = self.get_error()
        api.require(error == 0, f"real OpenGL error {error:#x}")

    def new_texture(self):
        self.check()
        value = c.c_uint()
        self.generate(1, c.byref(value))
        self.check()
        api.require(value.value > 0 and value.value not in self.textures, "texture name ownership differs")
        self.textures.add(value.value)
        return value.value

    def readback(self, texture, width, height):
        api.require(texture in self.textures, "unowned texture")
        self.bind_texture(0xde1, texture)
        self.check()
        api.require(self.is_texture(texture) == 1, "driver did not create actual texture")
        actual_width, actual_height = c.c_int(), c.c_int()
        self.level(0xde1, 0, 0x1000, c.byref(actual_width))
        self.level(0xde1, 0, 0x1001, c.byref(actual_height))
        self.check()
        api.require((actual_width.value, actual_height.value) == (width, height), "real texture dimensions differ")
        buffer = (c.c_ubyte * (width * height * 4))()
        self.download(0xde1, 0, 0x1908, 0x1401, buffer)
        self.check()
        return bytes(buffer)

    def close(self):
        errors = []
        def attempt(label, operation):
            try:
                return operation()
            except Exception as exc:
                errors.append(f"{label}: {exc}")
                return None
        if self.context:
            current = attempt("current context query", self.get_current)
            if current != self.context and self.textures:
                if not attempt("restore owned context", lambda: self.make_current(self.dc, self.context)):
                    errors.append("owned context unavailable for texture deletion")
            if attempt("current context query", self.get_current) == self.context:
                for texture in sorted(self.textures):
                    def delete(texture=texture):
                        value = c.c_uint(texture)
                        self.delete_textures(1, c.byref(value))
                        self.check()
                        api.require(self.is_texture(texture) == 0, "texture deletion failed")
                        self.textures.remove(texture)
                    attempt(f"texture {texture} deletion", delete)
                self.cleanup["made_not_current"] = bool(attempt("detach context", lambda: self.make_current(None, None)))
                if not self.cleanup["made_not_current"]:
                    errors.append("owned context detach failed")
            self.cleanup["tracked_texture_names_remaining"] = len(self.textures)
            self.cleanup["context_deleted"] = bool(attempt("delete context", lambda: self.delete_context(self.context)))
            if self.cleanup["context_deleted"]:
                self.context = None
            else:
                errors.append("context deletion failed")
        if self.dc:
            self.cleanup["dc_released"] = attempt("release DC", lambda: self.release_dc(self.window, self.dc))
            if self.cleanup["dc_released"]:
                self.dc = None
            else:
                errors.append("DC release failed")
        if self.window:
            self.cleanup["window_destroyed"] = bool(attempt("destroy window", lambda: self.destroy_window(self.window)))
            if self.cleanup["window_destroyed"]:
                self.window = None
            else:
                errors.append("window destruction failed")
        self.cleanup["errors"] = errors
        api.require(not errors, "; ".join(errors))
