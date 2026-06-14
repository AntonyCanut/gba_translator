# Save fixtures

## `post-zeph-pre-cs.srm`

Battery save supplied with the ticket **"Problème pas de gain d'objet"**.
It sits in the Frozen Forest right after the player beats the boss **Zeph**,
at the spot where the kidnapping scene triggers.

### The reported crash
The player walks the path, gets kidnapped by Team Shadow (Zeph / Ivory),
escapes through a magic portal and a hillbilly NPC hands over the CS **Coupe
(Cut)** — the game was reported to crash at the **object-gain** step
("pas de gain d'objet").

### How to reproduce manually
1. Copy this file next to the ROM and rename it to match, e.g.
   `output/roms/GenedRom-fr.gba` → `output/roms/GenedRom-fr.sav`
   (do **not** overwrite the committed Playwright fixture save — use a copy of
   the ROM in a scratch directory).
2. Boot in mGBA, press START → Continue.
3. Walk **down** to trigger the kidnapping cut-scene.
4. Win the Ivory battle, then the Zeph (Houndoom) battle.
5. After the portal escape, talk to the hillbilly → he gives the CS Coupe.

### Why the e2e for this sequence is byte-level, not a full playthrough
Step 4 is an RNG trainer battle (and an underleveled team), so a scripted
button-mash playthrough is not deterministic enough for CI. Instead the crash
*class* (a malformed string in the give-CS script) is guarded deterministically:

* `tests/e2e/test_object_gain_sequence.py` — reads the built ROM and asserts
  every string the give-CS script renders is 0xFF-terminated, has no truncated
  control code, and keeps the same `FD` buffer references as the English source.
* `tests/e2e-playwright/specs/object-gain-forget-sequence.spec.ts` — reads the
  same strings from the ROM and checks they decode to the expected French.

As of the current build all of these pass: the give-CS sequence strings are
byte-clean, so the text-corruption crash class is not present.

### Reproduced end-to-end in mGBA (no crash on the current build)
The full sequence *was* driven from this save to the exact reported screen and
it does **not** crash on `output/roms/GenedRom-fr.gba`:

1. Continue from this `.srm` (spawns at **Bourg Cratère**, the screenshot-1 spot)
   and walk **down** — the kidnapping cut-scene triggers (map `6.12`).
2. The Ivory/Zeph battles are the only RNG step. They are made deterministic by
   driving mGBA over the Lua bridge with two cheats: pin the active party mon's
   HP to max each turn (`gBattleMons[0].hp`, `0x02023C0C`) so it never faints,
   and select the **super-effective** move (Carmache's *Morsure* / Dark beats the
   Ghost foes — the default top-left *Double Baffe* is Normal and **immune**).
3. After the portal escape the player lands in the corridor (map `46.0`) and the
   hillbilly runs his give-CS script: the dialogue **"Alors, prends cette CS pour
   aller le voir."** (screenshot 2) prints, then `giveitem` runs — item **0x01B5**
   ends up in the bag and the game stays alive (`gSaveBlock1Ptr` valid throughout).

The non-text crash class (a build pass corrupting the `giveitem` script bytecode
or a relocated msgbox pointer) is now also guarded deterministically by
`tests/e2e/test_object_gain_sequence.py::test_give_cs_giveitem_command_intact`
and the two sibling `test_give_cs_script_*` checks.
