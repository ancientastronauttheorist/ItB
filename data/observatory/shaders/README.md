# OpenGL shader interface census

This directory is the publication boundary for build-keyed, metadata-only
analysis of the installed `shadersOGL/` corpus. Eligible artifacts contain
exact file identities, extension-based stage hints, duplicate-content groups,
line-ending metadata, bounded interface and preprocessor identifiers, and
lexical operation counts. They must not contain raw shader source,
preprocessor expressions, literal payloads, function bodies, compiler output,
or absolute installation paths.

The current Windows artifact is
`windows_build_13725832_31fe35265598_shader_census.json`. It accounts for the
complete flat directory:

- 12 regular UTF-8, no-BOM files totaling 4,087 bytes: five `.vs`, five `.ps`,
  and two `.h` files;
- eight `void main()` entry points and two byte-identical file pairs;
- 48 interface declarations covering ten uniform, three attribute, and two
  varying identifiers;
- seven observed preprocessor symbols, including four files that read
  `_ALPHA_TEST` and two that read `_PALETTE`;
- nine `texture2D` calls and four `discard` tokens; and
- four mixed-line-ending files, with original bytes preserved by every source
  identity hash.

The shader-directory manifest revision is
`08e26d15a68401577facb8d75c619bc2fc2d4827256ede7a35a389ed997de5e2`.
The artifact's pretty-printed file SHA-256 is
`a30da34fbf367f6f1f4699c7468c8a146acfa1b279ef1fad8c960eb32d3008f5`;
the verifier's canonical JSON SHA-256 is
`82404626ceba5d70110ffbd567cfda00957026ff715015e905e38c743d8d0f76`.

## Method

The builder first regenerates and exact-matches the complete sealed owner
installation inventory. That baseline intentionally inventories only the
existing scripts, maps, native libraries, executable, and opaque resource
archive, so the shader tool additionally builds and seals its own exact
`shadersOGL/` manifest without changing the baseline identity used by earlier
artifacts.

Every direct shader-directory entry must be a regular non-symlink file with a
bounded identifier-shaped basename and a recognized lowercase extension. The
parser requires bounded UTF-8 without a BOM or unsupported controls, masks
comments, balances the supported preprocessor conditional subset and braces,
accepts only strict top-level interface declarations, and recognizes at most
one top-level `void main()` block. It records bounded identifiers and counts;
it neither executes source nor invokes a shader compiler.

## Build

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
$inventory = "data/observatory/inventories/" +
  "windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json"
$evidence = "data/observatory/shaders/" +
  "windows_build_13725832_31fe35265598_shader_census.json"
python -X utf8 scripts/itb_shader_census.py build `
  --install-dir $itbInstall `
  --inventory $inventory `
  --output $evidence
```

Repository output is restricted to a direct child of this directory and is
written atomically. An existing artifact of another kind is never replaced.

## Verify

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
$inventory = "data/observatory/inventories/" +
  "windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json"
$evidence = "data/observatory/shaders/" +
  "windows_build_13725832_31fe35265598_shader_census.json"
python -X utf8 scripts/itb_shader_census.py verify `
  --install-dir $itbInstall `
  --inventory $inventory `
  --evidence $evidence
```

Verification repeats baseline installation attestation, rebuilds the complete
shader manifest, reparses and renormalizes every file, and requires exact
artifact equality.

## Claim boundary

This is a complete file and supported lexical-interface census for the sealed
owner-build shader corpus, not proof of OpenGL runtime semantics. `.vs`, `.ps`,
and `.h` classifications are filename hints. Source alone does not establish
header prepending, macro configurations, pipeline pairing, OpenGL or GLSL
version, driver acceptance, uniform locations or values, runtime loading,
reachability, or rendered results. No pristine-depot or cross-build equality
is claimed.
