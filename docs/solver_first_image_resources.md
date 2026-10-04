# Bounded original image-resource acquisition

Original EXE code now decodes the stock grass Dust image and missing-image fallback,
copies their pixels, uploads them through an isolated real host OpenGL context,
and constructs and destroys its resource object. This removes an image-object
dependency of Ground N2 H8-to-G8 movement. Cache population, Lua image-location
metadata, emitter completion and the original movement action remain unacquired.

The [frozen report](../data/solver_first/s1_image_resource_20261003.json) records
**two attempted, two admitted, two matched, zero failed and zero excluded**
development cases. Seven original calls return per case; all guest allocations
close. Native decode, CPU copy and GPU readback equal independent expected RGBA.

| Asset | Native dimensions | RGBA bytes | Traced instructions |
| --- | --- | --- | --- |
| `img/combat/tiles_grass/dust.png` | 15 × 13 | 780 | 76,985 |
| `img/nullResource.png` | 25 × 22 | 2,200 | 58,472 |

Grass is RGBA PNG input; fallback is indexed input with an opaque palette. Native
source-component outputs are 4/3 respectively, with requested RGBA8 output.
Independent expectations use CRC-checked original chunks, exact zlib exhaustion,
filter reconstruction and re-filtering back to encoded scanlines. These assets
exercise filters 0,1,2, not general PNG correctness. Proprietary assets, pixels
and full traces stay private; hashes and archive offsets are public.

## Source and supplied boundaries

Original entries are PNG dispatcher `0x3f330`, CPU constructor `0x99ea0`, texture
upload `0x9a2c0`, resource constructor `0xc4410`, resource destructor `0xc4500`,
CPU shared-owner destructor `0x9a1b0`, and pixel free `0x36fb17`. The report pins
complete original bodies, tools and runtime. Traced instructions use the existing
strict source-byte/owner admission. Normal successful heap APIs and eight checked
OpenGL import calls are supplied per case; no resource-return callback replaces
these bodies.

Original encoded bytes enter a supplied decoder context following memory-input
setup in `0xc0ac0`. That loader is not executed. Ordinary Dust classification
selects `0xbee20`; its file-loading/cache path remains unacquired. Output fields
start poisoned. Scratch objects and successful heap responses are supplied;
allocation failure and full process bootstrap remain excluded.

Checked x86 upload IAT calls dispatch real Windows x64 OpenGL APIs in a hidden
utility window owned by the probe. Actual generated texture names, level dimensions
and physical RGBA readback are checked. This external API bridge does not execute
the game's x86 OpenGL DLL, SDL startup or driver instructions. A supplied global
selects ordinary 2D textures. Host DLL filenames/sizes/hashes and GL vendor,
renderer/version pin the observed service; other drivers/platforms are unvalidated.
Context ownership follows the [Windows WGL API](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-wglcreatecontext);
upload/readback use [glTexImage2D](https://wikis.khronos.org/opengl/GLAPI/glTexImage2D)
and [glGetTexImage](https://wikis.khronos.org/opengl/GLAPI/glGetTexImage).

`0xc4410` takes **GLuint, width, height**, not a pixel pointer. Its 32-byte resource
stores the handle, dimensions, zero flag byte, two zero words and two float1 words.
Bytes `+0xd..+0xf` are ungraded supplied-storage padding. The destructor releases
this allocation; CPU shared-owner destruction and decoder pixel free also execute.
Real texture deletion, context detachment/deletion, DC release and window destruction
succeed separately from guest ownership. Tracked texture names after a cleanup
validation failure do not assert physical live textures after context deletion.

## Accounting and solver-facing exit

The [attempt manifest](../data/solver_first/s1_image_resource_attempts_20261003.json)
retains one PNG-only prototype, one context-only prototype, three two-asset pipeline
runs and two deliberately rejected host-boundary controls: ten mixed worlds, not
aggregated gameplay fidelity passes. Review corrected the first pipeline's overbroad
zero-DWORD projection to a flag-byte check with ungraded padding. A superseded frozen
run changed only the tracked texture-name cleanup label; its receipt is retained.
Cleanup attempts all applicable host teardown steps before reporting errors and
preserves the original acquisition failure.

Independent reviews checked ABIs, GLuint flow, import seams, expected pixels and
ownership. Two synthetic controls confirm source-admission rejection after context
creation closes host objects, and injected texture-deletion validation failure
does not skip later teardown. These are host-tool sensitivity checks, not original
negative gameplay cases or gate 6 completion.

Lookup `0xbe8f0` still needs cache registration. `0xc8660` inserts the wrapper;
`0xc2a90` obtains Lua `GetImageLoc`. Exact stock `scripts/images.lua` defaults
unknown images to `Point(INT_MAX, INT_MAX)`; guessed zero coordinates would replace
behavior. Genuine Point bindings/metadata, biome substitution and loaded Move/effect
dispatch must join route installation and arrival settlement. `0x99800`/`0x99620`
construct CPU vertex geometry, not images or completed GL rendering.

Build 13725832 remains pinned to EXE SHA256
`31fe352655982398fb3ee8b0bbe80efd5d65e3a9aa11e3dc39d0364354493fe9`
and archive SHA256
`fd933aa7d13fe02a9ea577eb100c779f053734816e6c87abae863ae1c9efa4d5`.
All 2,854 archive entries match the installed owner inventory; its Mod Loader
overlay is retained, not a pristine-depot claim. Baseline solver is
`84c186ae440163056c5c39b9aea9c20e6f49983e`; simulator 413 is unchanged.

Information mode is supplied offline original-byte oracle; objective is native
pixel/copy/resource ownership closure with real external texture provenance.
Original action/full-turn comparisons, fair-input/held-out admissions, search
certificates and ledger/gate promotions remain **zero**. Acquisition timing is
not planner latency; no baseline/candidate practical outcome or memory improvement
is measured. Full S1 and all seven acceptance gates remain open.

Continue because decoding, texture provenance and resource ownership uncertainties
were removed. Next exit remains a completed original H8-to-G8 action and
enemy/environment/spawn next state compared with the existing solver under the
frozen information contract. Further rendering work is deferred unless reached
by that action.

```text
python scripts/solver_first_image_resource.py --executable <pinned-Breach.exe> --runtime-path <pinned-emulator-package> --output <new-report.json> --private-output-dir <new-private-directory>
```

Outputs are create-only; run serially in a fresh Windows x64 process. Calls retain
the two-million-instruction/ten-second budget. Private inputs/receipts stay outside
public Git. This tranche changes offline tools, not simulator rules.
