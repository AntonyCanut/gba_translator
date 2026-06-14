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
