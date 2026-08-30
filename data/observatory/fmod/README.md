# FMOD bank and native interface census

This directory is the publication boundary for build-keyed, metadata-only
analysis of the installed FMOD banks, the two shipped FMOD PE libraries, and
their exact executable import surface. Eligible artifacts contain whole-file
identities, bounded container/header facts, aggregate RIFF structure, library
version metadata, export/interface identities, and executable bank-basename
literals. They must not contain bank payload bytes, event/bus/VCA paths,
decoded string tables, sample records, codecs, recursive node topology,
absolute installation paths, or isolated payload fingerprints.

The current Windows artifact is
`windows_build_13725832_31fe35265598_fmod_census.json`. It accounts for the
complete supported surface:

- five exact regular bank files totaling 168,821,378 bytes;
- 25,979 validated RIFF nodes, 14 top-level chunks, 689 recursive `WAV `
  chunks, and four bounded `FSB5` signatures whose candidate spans reach EOF;
- 32-bit `fmod.dll` and `fmodstudio.dll`, both carrying version `1.10.2`
  build `92217` metadata;
- 1,429 named exports across the two libraries, with no aliases, empty slots,
  ordinal-only exports, or forwarders in this build;
- 22 named and zero ordinal imports from `Breach.exe`, each named import
  resolved in the corresponding sealed export set; and
- all five expected bank basenames present exactly once as executable byte
  literals.

The exact bank-manifest revision is
`d9d921aa3080be0e3b93951a70fbdc2c88fa79df9d03d45ea518c8e86daee949`.
The artifact's pretty-printed file SHA-256 is
`8f7d942fed2294032993ace4a6fbbb30cb0a13cb06f3bff602b3abf3a151bc0d`;
the verifier's canonical JSON SHA-256 is
`d845999a838e5f1a7a0b4af94607899bdab781358d0491882f3dd66a19917d11`.

## Method

The builder first regenerates and exact-matches the complete sealed owner
installation inventory. That baseline intentionally does not enumerate the
five bank files, so this tool also seals the exact flat `.bank` surface under
`resources/`, rejects nested directories and links/reparse points, and checks
the directory and every file before and after analysis.

The bank parser streams whole-file hashing while enforcing a bounded exact-EOF
RIFF/`FEV ` grammar, printable FourCCs, containment, zero odd-byte padding,
recursive `LIST` bounds, the observed top-level grammar, and the observed raw
`FMT `/`FSB5` header shapes. Only aggregate identifiers/counts and bounded raw
header words survive normalization. Raw words and FourCC names are not assigned
undocumented semantics.

The native parser independently validates every nonzero PE export slot,
distinguishes named aliases and ordinal-only slots, hashes the complete sorted
named-export set, and accepts only the supported version-resource hierarchy.
The existing PE image parser supplies exact executable imports; every named
FMOD import must occur in the matching sealed DLL export set. All binary reads
use contained regular-file and stable-identity checks.

## Build

```powershell
$itbInstall = "<path-to-Into-the-Breach-install>"
$inventory = "data/observatory/inventories/" +
  "windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json"
$evidence = "data/observatory/fmod/" +
  "windows_build_13725832_31fe35265598_fmod_census.json"
python -X utf8 scripts/itb_fmod_census.py build `
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
$evidence = "data/observatory/fmod/" +
  "windows_build_13725832_31fe35265598_fmod_census.json"
python -X utf8 scripts/itb_fmod_census.py verify `
  --install-dir $itbInstall `
  --inventory $inventory `
  --evidence $evidence
```

Verification repeats installation attestation, exact bank-surface sealing,
container parsing, DLL export/version parsing, executable import/literal
analysis, publication-policy validation, and canonical artifact comparison.

## Claim boundary

This is complete only for the supported metadata/interface surface of the
sealed owner build. It is not an FMOD bank decompiler and does not establish
event identities, decoded audio, codec/sample semantics, bank load order,
runtime reachability, successful library calls, playback behavior, or first-
party audio-engine control flow. Version resources are publisher metadata,
imports are availability facts, and bank-basename literals are byte facts.
Third-party FMOD internals remain outside the first-party semantic-coverage
denominator.
