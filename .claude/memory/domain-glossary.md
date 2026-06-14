---
name: domain-glossary
description: Domain vocabulary for gba_translator — charmap, pointers, ROM structure, opcodes
metadata:
  type: reference
---

| Term | Meaning |
|---|---|
| **GBA** | Game Boy Advance |
| **BPRE01** | Pokemon FireRed ROM identifier |
| **CFRU** | Custom FireRed engine used by Pokemon Unbound |
| **charmap** | Table mapping Unicode chars → ROM byte values (`src/core/text_codec.py`) |
| **POKEMON_TABLE** | The main charmap dict; space=`0x00`, A=`0xBB`, a=`0xD5` |
| **POKEMON_TERMINATOR** | `0xFF` — marks end of a string |
| **POKEMON_NEWLINE** | `0xFE` — line break within text |
| **control code** | Multi-byte sequences: `FC nn`, `FD nn`, `F8 nn`, `F9 nn`, `F7 nn nn` |
| **{COLOR}X** | Color control → encodes as `FC 01 NN` |
| **{LV}** | Level token → byte `0x34` |
| **pointer** | 32-bit LE value in ROM; file offset = `value − 0x08000000` |
| **GBA_ROM_BASE** | `0x08000000` |
| **offset** | Byte position in the ROM file |
| **combined_fr.txt** | Master translation file: `<hex_offset> <FR_text>` entries (last wins on dup) |
| **translation_ready.json** | Structured JSON consumed by `19_build_translated_rom_generic.py` |
| **offset map** | JSON mapping EN pointer offsets → ES offsets (from `11_pointer_text_diff.py`) |
| **relocation** | Moving a text block to free space when FR is longer than original |
| **repoint** | Updating all pointers that referenced old address to new address |
| **fixed table** | ROM region (species/move names, etc.) whose address must not change |
| **LZ77** | GBA compression for graphics; must be preserved/repaired after injection |
| **IPS** | ROM patch file format (records: offset + replacement bytes) |
| **trilingual CSV** | EN/ES/FR text export with CRLF endings + LF inside field values |
| **mGBA** | GBA emulator used for Playwright/cooker scenario tests |
| **savestate** | mGBA snapshot file used as Playwright test fixtures |
| **cooker** | `src/cooker/` — emulator automation layer (checkpoint + emulator modules) |
| **GenedRom-fr.gba** | Output path: `output/roms/GenedRom-fr.gba` |
| **GenedRom-es.gba** | Output path: `output/roms/GenedRom-es.gba` |

**Links:** [[project-overview]] [[gotchas]]
