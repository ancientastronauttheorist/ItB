"""Original PNG decode, CPU copy, real texture upload and resource construction.

This supplied-byte development domain excludes cache population, Lua image
metadata, ordinary file loading, rendering and complete gameplay transitions.
"""
import bisect
import ctypes as c
import json
from pathlib import Path
import time

from src.observatory import solver_first_path_oracle as api
from src.observatory.resource_archive import scan_resource_archive
from src.observatory.solver_first_gl_texture import TextureContext

ARCHIVE_SHA = "fd933aa7d13fe02a9ea577eb100c779f053734816e6c87abae863ae1c9efa4d5"
ASSETS = (
    dict(id="grass", path="img/combat/tiles_grass/dust.png", width=15, height=13, components=4,
         encoded_sha256="8d9fa20148d784c9202477d2189f542e79ef9156f52d8de45d1c6c47c9eea6a8",
         rgba_sha256="50b6a690739309d004d6c13ca15de92c986bb62465a923d491130b7318ab6dbc"),
    dict(id="fallback", path="img/nullResource.png", width=25, height=22, components=3,
         encoded_sha256="602c1a88b281949a16b3957b599c75a41b1870e295c8d2e8bdcaf7a4fa8104bb",
         rgba_sha256="300d6d1d19d9801badffa1b320c9ab56c7750e49ef23a56bf6ef6c5d0ef30787"))
PINS = {
    0x3f330: "ef2efd6fc4da385a8f88664b1adb7f5f3c87f892dfc6c2d071904c85077b239a",
    0x99ea0: "ddd4ceba9c05cb83da6ec88ae4256f9ed2ceffdbff7ce29dc199901f5f4e95d4",
    0x9a2c0: "2b60a4be98dae5dedc031ed8b65910998dfa97c5d5acc315ce3b1013999c7ddd",
    0xc4410: "67447bd743c0969d3605ddcbf15f715f7d206a922168866dd04e07fcf2818050",
    0xc4500: "2ba8a43ca26180c3508acf900aebb927ecc4d6b0f9f1dc67970fb1811eac18d5",
    0x9a1b0: "f44408c771ce460c21aec1f7e2d7ba5e3301b03e7e6fb0e1aec9bb5897d7634e",
    0x36fb17: "fafd106d4b0ce80368b3e080fb3be3b06582d8145fce2063305541cab5f65ea3"}
GL_SEAMS = {
    "glGenTextures": (0x3d62a8, (0x9a2e0,), 2),
    "glBindTexture": (0x3d62c8, (0x9a2ef,), 2),
    "glTexParameteri": (0x3d62a4, (0x9a307, 0x9a319, 0x9a332, 0x9a344), 3),
    "glTexParameterfv": (0x3d624c, (0x9a364,), 3),
    "glTexImage2D": (0x3d62a0, (0x9a38b,), 9)}


class ImageMachine(api.Machine):
    def __init__(self, executable, context):
        super().__init__(api.OriginalSource(executable))
        self.context = context
        self.put(0, 0xffffffff)
        for entry, digest in PINS.items():
            self.source.verify(entry)
            api.require(self.source.verified[entry]["body_sha256"] == digest, "image dependency identity differs")

    def live_bytes(self, at, size):
        i = bisect.bisect_right(self.allocation_starts, at) - 1
        api.require(i >= 0, "GL input has no allocation")
        begin = self.allocation_starts[i]
        api.require(begin in self.live and begin <= at and at + size <= begin + self.allocations[begin],
                    "GL input outside live allocation")
        return bytes(self.uc.mem_read(at, size))

    def respond_import(self, at):
        row = self.stubs[at]
        if row["library"].lower() != "opengl32.dll":
            return super().respond_import(at)
        name = row["name"]
        api.require(name in GL_SEAMS, "unacquired GL API")
        slot, returns, count = GL_SEAMS[name]
        esp = self.uc.reg_read(self.x.UC_X86_REG_ESP)
        api.require(api.STACK <= esp < api.STACK + 0x10000 - 4 * (count + 1), "GL frame outside stack")
        ret = self.get(esp)
        api.require(ret - api.BASE in returns and int(row["iat_rva"], 16) == slot
                    and self.get(api.BASE + slot) == at, "GL import seam differs")
        api.require(self.trace and len(self.trace[-1]) == 2 and
                    sum(self.trace[-1]) == ret - api.BASE, "GL original call trace differs")
        call_rva, call_size = self.trace[-1]
        decoded = list(self.source.decoder.disasm(self.source.bytes_at(call_rva, call_size), api.BASE + call_rva))
        api.require(len(decoded) == 1 and decoded[0].mnemonic == "call", "GL seam is not original CALL")
        args = [self.get(esp + 4 + 4 * i) for i in range(count)]
        context, observations = self.context, {}
        context.check()
        if name == "glGenTextures":
            api.require(args[0] == 1 and api.STACK <= args[1] <= api.STACK + 0x10000 - 4, "generation arguments differ")
            texture = context.new_texture()
            self.put(args[1], texture)
            observations["generated_texture"] = texture
        elif name == "glBindTexture":
            api.require(args[0] == 0xde1 and args[1] in context.textures, "binding outside supplied 2D texture domain")
            context.bind_texture(*args)
        elif name == "glTexParameteri":
            api.require(args[0] == 0xde1 and (args[1], args[2]) in
                        ((0x2801, 0x2600), (0x2800, 0x2600), (0x2802, 0x8370), (0x2803, 0x8370)),
                        "texture integer parameters differ")
            context.parameter_i(*args)
        elif name == "glTexParameterfv":
            api.require(args[:2] == [0xde1, 0x1004] and api.STACK <= args[2] <= api.STACK + 0x10000 - 16,
                        "border parameters differ")
            values = (c.c_float * 4).from_buffer_copy(bytes(self.uc.mem_read(args[2], 16)))
            api.require(list(values) == [1.0, 1.0, 0.0, 1.0], "original border color differs")
            context.parameter_fv(args[0], args[1], values)
            observations["values"] = list(values)
        else:
            api.require(args[:3] == [0xde1, 0, 0x1908] and args[5:8] == [0, 0x1908, 0x1401]
                        and 0 < args[3] <= 4096 and 0 < args[4] <= 4096, "RGBA upload domain differs")
            raw = self.live_bytes(args[8], args[3] * args[4] * 4)
            buffer = (c.c_ubyte * len(raw)).from_buffer_copy(raw)
            context.upload(*args[:8], buffer)
            observations.update(pixel_bytes=len(raw), pixels_sha256=api.sha(raw))
        context.check()
        self.imports.append(dict(name=name, arguments=args, result=0, caller_return_rva=ret - api.BASE,
                                 provider="actual isolated host OpenGL API", observations=observations))
        # OpenGL functions here are void stdcall; EAX is a declared volatile
        # boundary value, not a game result. GenTextures writes its actual name.
        self.uc.reg_write(self.x.UC_X86_REG_EAX, 0)
        self.uc.reg_write(self.x.UC_X86_REG_ESP, esp + 4 + 4 * count)
        self.uc.reg_write(self.x.UC_X86_REG_EIP, ret)

    def execute(self, entry, args, receiver=0, edx=0, cleanup=0):
        self.trace, self.imports, self.failure = [], [], None
        esp = api.STACK + 0x8000
        self.put(esp, api.RETURN)
        for i, arg in enumerate(args):
            self.put(esp + 4 + 4 * i, arg)
        for reg, value in ((self.x.UC_X86_REG_ESP, esp), (self.x.UC_X86_REG_ECX, receiver),
                           (self.x.UC_X86_REG_EDX, edx), (self.x.UC_X86_REG_EFLAGS, 0x202)):
            self.uc.reg_write(reg, value)
        started = time.perf_counter()
        try:
            self.uc.emu_start(api.BASE + entry, api.RETURN + 1, count=api.LIMIT, timeout=10_000_000)
        except Exception as exc:
            self.fail(exc)
        returned = self.uc.reg_read(self.x.UC_X86_REG_EIP) == api.RETURN
        stack_ok = self.uc.reg_read(self.x.UC_X86_REG_ESP) == esp + 4 + cleanup
        return dict(entry_rva=entry, arguments=args, ecx=receiver, edx=edx, cleanup_bytes=cleanup,
            returned=returned, stack_ok=stack_ok, failure=self.failure, eax=self.uc.reg_read(self.x.UC_X86_REG_EAX),
            trace=list(self.trace), imports=list(self.imports), instructions=len(self.trace),
            wall_seconds=time.perf_counter() - started, summary=self.diagnostic())


def acquire(executable, asset, encoded):
    context = machine = None
    calls, observations, failure = [], {}, None
    status = "failed"
    def original(entry, args=(), receiver=0, edx=0, cleanup=0):
        row = machine.execute(entry, args, receiver, edx, cleanup)
        calls.append(row)
        api.require(row["returned"] and row["stack_ok"] and row["failure"] is None,
                    f"original image call {entry:#x} did not return: {row['failure']}")
        return row["eax"]
    try:
        context = TextureContext()
        machine = ImageMachine(executable, context)
        api.require(api.sha(encoded) == asset["encoded_sha256"], "asset input identity differs")
        ctx, data = api.BOARD + 0x1000, api.BOARD + 0x10000
        wout, hout, nout = api.BOARD + 0x2000, api.BOARD + 0x2004, api.BOARD + 0x2008
        bitmap, wrapper = api.BOARD + 0x3000, api.BOARD + 0x4000
        machine.uc.mem_write(data, encoded)
        for offset, value in ((0x10, 0), (0x20, 0), (0xa8, data), (0xac, data + len(encoded)), (0xb0, data)):
            machine.put(ctx + offset, value)
        for ptr in (wout, hout, nout):
            machine.put(ptr, 0xdeadbeef)
        pixels = original(0x3f330, [hout, nout, 4], ctx, wout)
        width, height, components = machine.get(wout), machine.get(hout), machine.get(nout)
        api.require((width, height, components) == (asset["width"], asset["height"], asset["components"]),
                    "original image dimensions/components differ")
        native_pixels = machine.live_bytes(pixels, width * height * 4)
        api.require(api.sha(native_pixels) == asset["rgba_sha256"], "independent RGBA expectation differs")
        api.require(original(0x99ea0, [pixels, width, height], bitmap, cleanup=12) == bitmap,
                    "CPU copy constructor differs")
        copied = machine.live_bytes(machine.get(bitmap), width * height * 4)
        api.require(copied == native_pixels, "original CPU copy changed pixels")
        machine.put(0x894b54, 0xde1)  # Explicit supplied ordinary 2D rendering mode.
        texture = original(0x9a2c0, receiver=bitmap)
        readback = context.readback(texture, width, height)
        api.require(readback == native_pixels, "actual texture readback differs")
        api.require(original(0xc4410, [texture, width, height], wrapper, cleanup=12) == wrapper,
                    "resource constructor receiver differs")
        resource = machine.get(wrapper)
        projection = [machine.get(resource + i * 4) for i in range(8)]
        flag = bytes(machine.uc.mem_read(resource + 12, 1))[0]
        padding = bytes(machine.uc.mem_read(resource + 13, 3))
        api.require(projection[:3] == [texture, width, height] and flag == 0
                    and projection[4:] == [0, 0, 0x3f800000, 0x3f800000],
                    "original resource fields differ")
        observations.update(width=width, height=height, source_components=components, pixel_bytes=len(native_pixels),
            decoded_rgba_sha256=api.sha(native_pixels), copied_rgba_sha256=api.sha(copied),
            texture=texture, actual_texture_rgba_sha256=api.sha(readback), raw_resource_words=projection,
            resource_flag_byte=flag, supplied_storage_padding_bytes=list(padding),
            wrapper_resource=resource)
        original(0xc4500, receiver=wrapper)
        original(0x9a1b0, receiver=bitmap)
        original(0x36fb17, [pixels])
        api.require(not machine.live, "original cleanup left live guest allocations")
        status = "complete"
    except Exception as exc:
        failure = str(exc)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception as exc:
                failure = f"{failure}; cleanup: {exc}" if failure else f"cleanup: {exc}"
                status = "failed"
    return dict(asset=asset, status=status, failure=failure, observations=observations, calls=calls,
        remaining_allocations=len(machine.live) if machine else None,
        allocations=machine.allocations if machine else {}, live_allocations=sorted(machine.live) if machine else [],
        context_identity=context.identity if context else {}, context_cleanup=context.cleanup if context else {},
        verified_original_bodies=list(machine.source.verified.values()) if machine else []), machine


def run(executable, private_dir):
    executable, private_dir = Path(executable), Path(private_dir)
    api.require(not private_dir.exists(), "private directory is create-only")
    private_dir.mkdir(parents=True)
    paths = ["src/observatory/solver_first_image_resource.py", "scripts/solver_first_image_resource.py",
        "src/observatory/solver_first_gl_texture.py", "src/observatory/solver_first_path_oracle.py",
        "src/observatory/resource_archive.py", "src/observatory/pe_anchor_map.py"]
    pins = {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in paths}
    runtime = api.runtime_identity()
    archive_path = executable.parent / "resources/resource.dat"
    archive = scan_resource_archive(archive_path)
    api.require(archive["sha256"] == ARCHIVE_SHA and archive["entry_count"] == 2854, "archive identity differs")
    records = {r["path"]: r for r in archive["records"]}
    cases = []
    for asset in ASSETS:
        record = records[asset["path"]]
        api.require(record["payload_sha256"] == asset["encoded_sha256"], "archive payload identity differs")
        with archive_path.open("rb") as handle:
            handle.seek(record["payload_offset"])
            encoded = handle.read(record["payload_size"])
        private, _ = acquire(executable, asset, encoded)
        path = private_dir / (asset["id"] + ".json")
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(private, handle, indent=2, sort_keys=True, allow_nan=False); handle.write("\n")
        cases.append(dict(asset=asset, archive_record=record, status=private["status"], failure=private["failure"],
            observations=private["observations"], call_count=len(private["calls"]),
            instruction_count=sum(c["instructions"] for c in private["calls"]),
            call_wall_seconds=[c["wall_seconds"] for c in private["calls"]],
            import_calls=[r for c in private["calls"] for r in c["imports"]],
            remaining_allocations=private["remaining_allocations"], context_identity=private["context_identity"],
            context_cleanup=private["context_cleanup"], private_receipt_sha256=api.sha(path.read_bytes())))
    api.require(pins == {p: api.sha((api.ROOT / p).read_bytes().replace(b"\r\n", b"\n")) for p in paths}, "tool sources changed")
    api.require(runtime == api.runtime_identity(), "runtime changed")
    api.require(api.sha(executable.read_bytes()) == api.EXE_SHA and
                api.sha(archive_path.read_bytes()) == ARCHIVE_SHA, "original inputs changed")
    return dict(schema_version=1, corpus_version="s1-original-image-resource-development-v1", game_build=13725832,
        baseline_solver_commit="84c186ae440163056c5c39b9aea9c20e6f49983e", executable_sha256=api.EXE_SHA,
        archive_sha256=ARCHIVE_SHA, source_lf_sha256=pins, runtime=runtime,
        information_mode="supplied offline original-byte oracle; no fair player admission",
        objective="native RGBA decoding/copy, real external texture upload and native resource field/ownership closure",
        attempted=len(cases), admitted=sum(c["status"] == "complete" for c in cases),
        matched=sum(c["status"] == "complete" for c in cases), failed=sum(c["status"] != "complete" for c in cases),
        excluded=0, cases=cases, original_body_pins={hex(k): v for k, v in PINS.items()},
        supplied_boundaries=["Encoded PNG bytes from exact resource archive; original decoder context fields follow normal c0ac0 memory-input setup.",
            "Mapped output/context/CPU/wrapper storage and normal successful Windows heap responses are supplied; original allocation, copy and destruction bodies execute.",
            "Actual isolated Windows x64 OpenGL API/context services bridge pinned x86 upload calls; original game/x86 OpenGL/SDL startup and driver instruction trace are unacquired.",
            "Ordinary 2D target is supplied. Real texture name, storage, dimensions and RGBA readback are checked; no fabricated texture or final dimensions.",
            "Native resource constructor/destructor and CPU/pixel cleanup execute; texture/context cleanup uses actual external API ownership.",
            "Resource +0xc is an original zero flag byte; +0xd..+0xf are ungraded supplied-storage padding, not constructor-written zero DWORD semantics.",
            "Ordinary bee20 loader, cache registration, GetImageLoc/Lua metadata, biome selection, draw geometry and complete movement remain unacquired."],
        original_completed_action_transitions=0, full_turn_original_comparisons=0, held_out_cases=0,
        fair_input_admissions=0, gate_promotions=0, ledger_promotions=0,
        next_blocker="Normal image-cache population and genuine Lua GetImageLoc metadata, then joined native emitter and Ground Move/dispatch settlement.")
