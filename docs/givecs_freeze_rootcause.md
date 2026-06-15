# Give-CS freeze — root cause and fix

Ticket: **« Problème pas de gain d'objet »** (T-23). After beating Zeph the
player is handed a field-move CS by a hillbilly NPC; on the French build the
game **freezes** on the box « Alors, prends cette CS pour aller le voir. » and
ignores all input. English never freezes.

## How it was found

The user supplied a **savestate taken on the frozen box**
(`tests/fixtures/saves/givecs_freeze.ss1`, mGBA PNG savestate of the playable
build `output/roms/GenedRom-fr.gba`, CRC `0x55fd4d49`). Loading it in mGBA and
sampling the CPU showed the game is **hung**, not crashed:

- All `gMain` callbacks are NULL and the game state never changes; pressing A
  does nothing — the screen stays on the box forever.
- The PC spins permanently in `0x08005Exx–0x08006120`. Disassembly identifies
  this as the engine's **`GetStringWidth`** routine: it walks a string one byte
  at a time and stops only when it reads the `0xFF` terminator
  (`0x08006100 cmp r0,#0xFF`).
- The stack return address `0x089F3632` is inside a CFRU **word-wrap** routine
  (`0x089F35F8`) that copies a source string into a stack buffer and repeatedly
  calls `GetStringWidth` to break it into lines that fit a 195 px window.

The buffer being wrapped had **no `0xFF` terminator within 160+ bytes** and
decoded to French **move descriptions** — including *« Une attaque de base.
Elle peut être utilisée pour abattre des arbres… »*, the field description of
the CS (Cut/Coupe) being received. With no terminator in range the wrap scan
never ends → infinite loop → freeze.

Injecting a single `0xFF` into that buffer live (via the bridge `WRITE`
command) makes the PC leave the wrap region — confirming termination is what
releases the loop.

## The defect (pure translation data)

Unbound keeps **two** move-description pointer tables:

| Table | Used by | State |
|-------|---------|-------|
| `0x0899F190` | « Capacités connues » summary | re-wrapped/relocated by `patch_move_descriptions_fr.py` (clean) |
| `0x08488708` | move-info / **give-CS** path | **duplicate, never repointed** |

The generic builder writes the longer French descriptions over the original
English slots referenced by the **duplicate** table. A French description
overruns its slot and overwrites the **next entry's `0xFF` terminator**, fusing
a long run of descriptions with no terminator at all (≈720 bytes at
`0x0848_2ACD`). Measured on the three artifacts:

- English duplicate table: **0** unterminated entries → no freeze.
- French build: **57–72** unterminated/overflowing entries (idx 6 =
  `0x0848_2BD5` = the give-CS Cut description) → freeze.

The give-CS event bytecode, the box `0x1F3316D` and the item struct are all
byte-identical to English (verified by `test_object_gain_sequence.py`); the
freeze is **only** the duplicate description table. This corrects the earlier
conclusion that the freeze was not a translation-data problem.

## The fix

`scripts/patch_dup_move_descriptions_fr.py` (run last in `make build-fr`):

1. For every entry of table `0x08488708` whose stored string is unterminated
   (no `0xFF` within 160 bytes),
2. takes the authoritative French text keyed by the entry's original ROM offset
   in `combined_fr.txt` (the source of truth),
3. re-encodes it (the encoder always appends `0xFF`), relocates it into ROM free
   space, and repoints the table cell.

Termination alone removes the infinite loop; a relocated, terminated string can
never run into its neighbour again. This is the same duplicate-pointer-table
class as the summary-screen labels fix — both copies of a pointer table must be
repointed.

### Verification

- `scripts/patch_dup_move_descriptions_fr.py` relocates all 68 overflowing
  entries into genuine `0xFF` free space; content byte-matches the authoritative
  source; no relocations overlap; table `0x0899F190` and all other bytes are
  untouched.
- After patching: **0** unterminated entries in `0x08488708`; the give-CS Cut
  description decodes to the full, terminated French text.
- The patched ROM boots and runs (frames advance, no crash).
- `tests/e2e/test_givecs_move_desc_freeze.py` is the deterministic CI guard:
  it fails on the pre-patch ROM (57 overflow) and passes on the fixed build.

The savestate is pre-fix RAM, so it can only ever *reproduce* the historical
freeze; reaching give-CS on the rebuilt ROM is gated by the random Zeph double
battle and was not replayed headlessly. The root cause (missing `0xFF`) is
provably eliminated for every entry.
