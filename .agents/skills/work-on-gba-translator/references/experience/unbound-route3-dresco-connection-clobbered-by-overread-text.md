---
name: ""
metadata:
  node_type: memory
  originSessionId: b9112589-61be-450b-9333-a633b3b2dbb1
---

Dresco Town "invisible wall" (couldn't return from Route 3 south back to Dresco): NOT a text
freeze and NOT map collision — it was the FR build **overwriting Route 3's `MapConnections`
struct** with translated text.

Root cause chain:
- Route 3 map header (ROM `0x777C00`) `connections` field → `0x8721344`. The 2-entry array sits
  just before at `0x72132C`; entry1 = dir=1 (SOUTH) → Dresco Town (group 3, num 71) = the return path.
- The string extractor **over-read**: it began a "string" at `0x721340` (12 bytes *inside* the
  connection data, whose bytes `03 47 00 00 02 00 00 00 2c 13 72 08` happen to decode as CFRU
  glyphs) instead of at the real ability-description text start `0x72134C`
  ("Parent and child attack together."). `combined_en.txt` shows the garbage prefix.
- `combined_fr.txt` carried the French translation keyed to `0x721340`, so `build-fr` wrote the
  French bytes over Route 3's SOUTH connection + the `MapConnections` header → connection destroyed →
  going north to Route 3 works (Dresco's north connection is fine) but returning south = invisible wall.

Fix (commit on `unbound`): re-key the `combined_fr.txt` entry `0x721340` → `0x72134C` (the true text
start). The `0x72134C` key has no matching EN extract entry so it's skipped (desc stays EN — likely an
unreferenced dup), and nothing writes into `0x72132C-0x72134B` anymore. Verified by rebuild: those
bytes are byte-identical to `input/roms/patchedfrenchrom.gba` and Route 3 `MapConnections` parses
`count=2`, entry1 SOUTH→(3,71). Guard: `tests/unit/fr/test_route3_dresco_connection_guard.py`.

Reusable technique for "invisible wall / can't return" map bugs (see [[diagnosing-unbound-freezes-skill]] — this is a *different* class from the freeze skill):
1. Reproduce location from the user's `.sav` (they boot to a shop in Dresco). Use closed-loop tile
   movement (press dir, re-read `playerX/Y`, retry the turn-then-step) — fixed key sequences are
   non-deterministic. Bridge: `emulator-web/src/mgba-bridge.ts` (`pressKeyAndAdvance`, `getState`,
   `readMemory`, `saveState`/`loadState`). `pkill -9 mgba` + wait for port 55234 between runs.
2. Read the current map from RAM: `gMapHeader` @ `0x02036DFC` (FireRed): mapLayout*@0, events*@4,
   scripts*@8, connections*@0xC, mapLayoutId@0x12. MapLayout: w@0,h@4,border*@8,mapdata*@0xC,
   primTS*@0x10,secTS*@0x14. Current group/num = SaveBlock1 (ptr @ `0x03005008`) +4/+5.
3. Find a neighbour map's header from the group array: search ROM for the current header's pointer
   signature, the array is indexed by map num. Dresco=3.71, its north neighbour Route 3=3.70.
4. **Decisive test without full navigation:** diff the map's block data + `MapConnections` between the
   built ROM and the build source `patchedfrenchrom.gba`. Identical ⇒ base-game; differs ⇒ the build
   clobbered it. Here Dresco's data was identical but Route 3's connection region differed.

Commit policy: `output/roms/GenedRom-fr.gba` is committed but usually **stale** (fixes accumulate in
`combined_fr.txt`, ROM rebuilt in periodic `build(fr):` commits). Only commit a rebuilt ROM when a
concurrent rebuild just landed so your rebuild diff is localized to your fix — otherwise it bundles
~1% unvalidated drift you can't e2e-gate locally. Here a concurrent rebuild made the diff exactly 34
bytes (my fix), so committing the ROM was clean. See [[unbound-combined-fr-fixed-but-rom-never-rebuilt]].
