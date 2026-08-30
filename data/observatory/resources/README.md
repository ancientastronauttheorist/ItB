# Resource archive inventories

This directory contains metadata-only inventories of Into the Breach resource
archives. Artifacts may record archive identity, resource paths, record and
payload offsets, sizes, extensions, and SHA-256 values. They must not contain
asset payloads, extracted images, font glyphs, or bulk decoded resources.

Build an inventory from the owner's exact archive:

```powershell
python -X utf8 scripts/itb_resource_inventory.py build `
  --install-dir "B:\SteamLibrary\steamapps\common\Into the Breach" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --output data/observatory/resources/windows_build_13725832_fd933aa7d13f_resource_inventory.json
```

Verify every span, path, payload hash, archive hash, and build identity:

```powershell
python -X utf8 scripts/itb_resource_inventory.py verify `
  --install-dir "B:\SteamLibrary\steamapps\common\Into the Breach" `
  --inventory data/observatory/inventories/windows_build_13725832_31fe35265598_full_decompile_baseline_20260830.json `
  --evidence data/observatory/resources/windows_build_13725832_fd933aa7d13f_resource_inventory.json
```

Before parsing the archive, the validator independently rebuilds the complete
installation inventory and requires an exact match with the supplied sealed
inventory, including the recorded `resources/resource.dat` path, size, and
SHA-256. It then recognizes the archive container, PNG signatures,
TrueType/OpenType signatures, and custom `.font` records as an opaque resource
class. It does not claim the custom font payload grammar, rendering semantics,
or reachability from native/Lua code; those are later decompilation workstreams.
