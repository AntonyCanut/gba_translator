# DE menu and world graphics design

## Scope

Port the French out-of-battle graphics group to German without routing French
or Italian through the generic builder. The deliverable covers the five named
menu sprites, fixed World Map labels/actions, junction panels, localized LZ77
ordering, and the already-existing German DexNav headers.

## Design

German owns an indexed-image registry at `languages/de/sprites.py` and editable
PNG sources under `languages/de/sprites/`. The registry reuses the proven ROM
geometry from the French registry but never reuses a French bitmap. A dedicated
`menu_sprites` patch invokes the existing safe sprite inserter for each declared
image and every active Mart copy. Reapplying the patch writes the same pixels.

The DE descriptor schedules `menu_sprites` only after `repair_lz77` and
`repair_localized_lz77`. German-only World Map patches then restore the live
action cells and the two in-place location labels. Proper names stay identical
to the English source, per the parent ticket. The existing junction wrapper
continues to source all ten arrow panels from `combined_de.txt`; DexNav keeps
its strict 1,176-byte budget and ghost-tail clearing. The fixed map cells run
before the two allocator-backed mission/junction passes, which remain the final
relocation steps required by the DE pipeline.

## Asset copy

- Cube footer: `START Sort.`
- PC sheet: `PKMN DATEN`, `TEAM PKMN`, `ZURUECK`, `BOX ZU`.
- Mart sign: `SHOP` on all three live copies.
- Naming keyboard: `SELECT`, `ZUR.`, `B TASTE`, `OK`, `START`, `GROSS`,
  `klein`, `andere`.
- START menu hint: `SELECT Bew.`.
- World Map action strip: `Bew.`, `OK`, `Zurück`.

ASCII digraphs are used only inside tile art where the fixed pixel height or
width cannot draw an umlaut cleanly. Runtime text uses the real `ü` glyph.

## Safety and verification

Tests exercise the real indexed assets and inserter against a disposable ROM,
including a second idempotency pass. Compression must remain within each
original block or declared capacity. A ROM test extracts every sprite from
`GenedRom-de.gba` and compares its indexed pixels with the versioned source.
The map tests decode the finished ROM and assert the original proper names.
Existing DexNav tests remain the pixel-ghost and compression authority.
