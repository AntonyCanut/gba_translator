# French translation — launch → first-battle gameplay verification

**ROM under test:** `output/roms/GenedRom-fr.gba` (built FR ROM)
**Emulator:** real mGBA 0.11 via the Lua bridge (`emulator-web/src/mgba-bridge.ts`)
**Probe:** `scripts/verify_fr_gameplay.mts` (boots the ROM, walks the launch
sequence, harvests the live text buffers `gStringVar1..4` + battle buffers,
flags encoding/English issues, saves screenshots to
`output/proofs/fr-gameplay/`).

Run it with:

```bash
npx tsx scripts/verify_fr_gameplay.mts          # default FR ROM
npx tsx scripts/verify_fr_gameplay.mts <rom>    # any ROM
```

## What was exercised

Title screen → character creation (skin / hair / jacket / outline colour) →
"Est-ce ton personnage ?" confirmation → professor / language prompts → the full
Borrius legend intro cinematic → entry into the overworld. **147 distinct live
strings** were captured and decoded straight from emulator RAM.

The first *scripted* battle is reached only after a long story segment that the
automated A-spam/skip cannot fast-forward deterministically within the frame
budget, so wild-battle text was **not** harvested live here. Battle-message
rendering is instead covered by the deterministic `battle-flow` Playwright
project (10/10 green), which seeds the battle buffers and asserts French / no
residual English.

## Result summary

| Check | Verdict |
|-------|---------|
| French text displays correctly | ✅ Pass — proper grammar & vocabulary throughout |
| Accents render (é è à â ç î ù) | ✅ Pass — all direct-mapped accents render |
| UI formatting intact (line breaks, prompts, windows) | ✅ Pass — no overflow / garbled layout observed |
| No unexpected English text | ⚠️ One residual-English case (see Issue 2) |
| No encoding degradation | ⚠️ Circumflex/diaeresis vowels degraded (see Issue 1) |

Representative harvested French (all correct):

```
"Choisis un personnage."
"Choisis une couleur de peau."
"Est-ce ton personnage ?"
"C'est ta première partie sur Pokémon Unbound ?"
"Les Pokémon du roi le quittèrent, et le champ de bataille…"
"Incapable de pardonner au monde qui avait blessé son cher Pokémon…"
```

## Issues found

### Issue 1 — Circumflex / diaeresis vowels are silently degraded to ASCII (encoding degradation)

**Symptom (in-game):** `aussitôt → aussitot`, `même → meme`, `arrête → arrete`,
`entrepôt → entrepot`, `gênes → genes`, `fenêtre → fenetre`, etc.

**Root cause — confirmed, not a probe artifact:**
- The translation *source* is correct: `combined_fr.txt` contains `aussitôt`
  (with `ô`) 11×, `ê` ~2147×, `ô` ~386×, `û` ~500×, `ï` 76×, `ü` 29×, `œ` 180×.
- `src/core/text_codec.py` → `ENCODE_ALIASES` deliberately rewrites
  `ê→e, ë→e, ô→o, û→u, ü→u, ï→i, œ→oe` (and uppercase variants) **before**
  encoding, because the Unbound font has **no glyphs** for those characters.
- `src/text/charmap_data.py` confirms it: only `é è à â ç ù î` are mapped;
  `sync_charmap.py` reports `FR accents MISSING: ê ë û ü ï ô œ`, and
  `tests/unit/test_sync_charmap.py` already classifies them as `ALIAS_ACCENTS`.
- `scripts/patch_font_fr.py` only synthesizes glyphs for `à` and `ç` — it never
  builds circumflex/diaeresis glyphs.

So the loss happens at **injection time**, not in the source and not in the
emulator. It affects thousands of strings game-wide.

**Severity:** Medium — text stays readable, but it is not orthographically
correct French.

**Fix (belongs to parent P-02, out of this test ticket's scope):** extend
`patch_font_fr.py` to synthesize `ê ô û ë ï ü` glyphs (same approach as the
existing `build_grave_a` / `build_cedilla`), assign them CFRU byte codes in
`charmap_data.py` + `text_codec.POKEMON_TABLE`, drop the corresponding
`ENCODE_ALIASES` entries, then `make build-fr`. Requires authoritative Unbound
font byte codes, so it was **not** attempted blindly here (guessing codes would
corrupt text).

### Issue 2 — Untranslated gender pronoun `him` / `her` via `STR_VAR_1` substitution

**Symptom (in-game, harvested live):**

```
"Assomme him et enferme him dans l'entrepôt !"   (expected: "Assomme-le et enferme-le …")
"Attrape him !"
```

**Root cause:** the warehouse dialogue is translated correctly as a literal
string (`offset 0x7EF966`: *"Assomme-le et enferme-le dans l'entrepôt !"*), **but
the variant actually played** (`offset 0x1F2CC17`, English `0x...` =
`"Now knock <STR_VAR_1> out and lock <STR_VAR_1> up …"`) keeps the
`{STR_VAR_1}` / `<0xFD><0x02>` buffer reference. That buffer is filled at runtime
by a separate gender-pronoun helper string that is **still English (`him`/`her`)**.
French should not buffer a pronoun this way — the line should hardcode `-le`/`-la`
or the pronoun source must be translated.

**Severity:** Medium — visible residual English in a story scene.

**Fix (parent P-02):** translate the pronoun-buffer source string (or rewrite the
`{STR_VAR_1}` lines to inline `-le`/`-la`), then rebuild.

## Test-infrastructure fix shipped with this ticket

The shared charmap decoder (`src/text/charmap_data.py`, regenerated into
`emulator-web/src/charmap.ts` and `tests/e2e-playwright/helpers/charmap.ts` by
`scripts/sync_charmap.py`) did not handle the **single-byte prompt control
codes `0xFA` (scroll) and `0xFB` (clear-window)**. They decoded to a spurious
`?` wedged mid-sentence (`obscure?pour`), producing **45 false "encoding
degradation" hits** in the gameplay probe and noise in the e2e text assertions.

They now decode as a paragraph break (`\n`), preserving word boundaries. After
the fix the probe reports drop from **45 → 4** issues, and those 4 are all the
genuine `him` residual-English of Issue 2.

Verification: `sync_charmap.py --check` green · `test_sync_charmap.py` 13/13 ·
python fast suite 154 passed · Playwright `translation` + `battle-flow` 10/10.
