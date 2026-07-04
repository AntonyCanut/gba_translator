# Audit: baked-in French text in `input/roms/englishrom.gba`

**Status:** confirmed — the "English" source ROM is a French-contaminated base.
**Tool:** `scripts/audit_english_rom_french_leak.py` (extends the methodology of
`scripts/audit_it_table_offset_coverage.py`).
**Follow-up to:** the P-171 move-name investigation
(`languages/fr/patches/move_names.py`, `src/core/fixed_tables.py`).

## TL;DR

`input/roms/englishrom.gba` is **not a pristine English CFRU/Unbound compile**.
It ships official **French** text baked into every major content table — move
names, move descriptions, item names, item descriptions, Pokédex flavour text,
and species names. Because the leak lives in the *shared base ROM* that every
language builds from, any language that lacks a dedicated patch for a given
table silently ships **French**, not English fallback or its own translation.

Concretely, today:

- **Italian and German builds display French move names** (`Poing Karaté`,
  `Écras'Face`, …) — no pipeline wrote them; they are inherited from the base.
- **Italian and German builds display French move descriptions**
  (`L'ennemi est tranché violemment.`) — same cause.
- **German ships French item names** (`Eau Fraîche`) where Italian, which has a
  dedicated `item_names` patch, correctly shows `Acqua Fresca`.
- **French only "works" for these tables by coincidence** — the base already
  holds French, so FR needs no patch there.

This is **one-time historical base contamination**, not an ongoing build
artifact: no FR/IT/DE pipeline step writes to these offsets. The fix for other
languages is to author/patch each table (as IT already does for item names),
never to "clean" the base.

## How it was confirmed

The strongest evidence is the cross-ROM diff the audit script performs. For
every French cluster it decodes the same offset in an **independent** ROM:

| Offset | `englishrom.gba` | `spanishrom.gba` (independent community translation) |
|---|---|---|
| `0x1B2998` (move name) | `Poing Karaté` | *(re-encoded / Spanish table)* |
| `0x876673` (item name) | `Eau Fraîche` | `Agua Fresca` |
| `0x482874` (move desc) | `L'ennemi est tranché…` | `Da un golpe cortante…` |
| `0x444D12` (Pokédex) | `Lorsque le bourgeon sur son dos éclot…` | `Cuando el bulbo del lomo crece…` |
| `0x3D51B4` (item desc) | `Une Poké Ball un peu spéciale…` | `Poké Ball distinta que va mejorando…` |

The Spanish ROM — produced separately from a real English base — holds Spanish
(or English) at exactly the offsets where our "English" ROM holds French. A
genuinely-fresh English compile is not checked into this repo, so it cannot be
diffed directly, but the Spanish ROM is a sufficient independent reference: it
proves the French in `englishrom.gba` is anomalous. **34 of the 35** reported
clusters differ from the Spanish ROM (the 1 that matches is graphics padding,
not text).

Built-ROM confirmation (from `output/roms/`), showing the silent inheritance:

| Offset | EN | IT | DE | FR |
|---|---|---|---|---|
| `0x1B2998` move name | `Poing Karaté` | `Poing Karaté` | `Poing Karaté` | `Poing Karaté` |
| `0x876673` item name | `Eau Fraîche` | `Acqua Fresca` ✅ | `Eau Fraîche` ⚠️ | `Eau Fraîche` |
| `0x482874` move desc | `L'ennemi est tranché` | `L'ennemi est tranché` | `L'ennemi est tranché` | `L'ennemi est tranché` |

## Scope — the contaminated regions

Full run: `python3 scripts/audit_english_rom_french_leak.py --compare input/roms/spanishrom.gba`.
3,308 French-looking runs collapse into 35 proximity clusters. Grouped by the
content table they land in:

| Hits | Region |
|---:|---|
| 1,997 | move descriptions (free-space relocation pool, `0x0B2*`–`0x0C2*`) |
| 671 | Pokédex flavour text (free-space pool, `0x0440000`, `0x0950000`) |
| 187 | move descriptions / Spinda flavour (`0x0A37000`–`0x0A44000`) |
| 125 | Pokédex flavour text (`0x1650000`–`0x1668000`) |
| 69 | move descriptions (legacy/duplicate table, `0x0480000`) |
| 59 | move names (13B fixed table, `0x1B2980`) |
| 35 | item descriptions (general: Poké Ball/Berry/Spray, `0x03D0000`) |
| 9 | item names (`gItems`, 44B stride, `0x0876074`) |
| 6 | item descriptions (drinks/vitamins, `0x0EB0000`) |
| 5 | unclassified free-space pool (`0x07B3BE9`, real French item desc) |

The three **fixed-width tables** (move names, species names, species info) are
documented in `src/core/fixed_tables.py` as "already French in the source ROM"
and are left untouched by text reinsertion. The bulk of the leak, however, is
in the **Pokédex/move-description free-space relocation pool** — the region the
P-171 parent flagged as "the generic builder's Pokédex free-space relocation
pool" — where a prior French build's relocated text was baked into the base.

## What this means for each language

- **FR** — no action; the base French *is* the desired French for these tables.
- **IT** — move names are now patched (`languages/it/patches/move_names.py`);
  move **descriptions** and any un-patched item names/descriptions still ship
  French. These are the next candidates for dedicated patches.
- **DE** — same as IT, plus DE has no `move_names` wrapper yet, so it ships
  French move names *and* descriptions. A `languages/de/patches/move_names.py`
  wrapper (the FR patch already accepts any `--combined` file) is the quick win.
- **Any future language** — inherits French for every table it does not patch.
  Run this audit against its built ROM to see exactly which surfaces leak.

## Using the tool

```bash
# self-contained audit of the English source ROM
python3 scripts/audit_english_rom_french_leak.py

# confirm each cluster against independent references, emit JSON
python3 scripts/audit_english_rom_french_leak.py \
    --compare input/roms/spanishrom.gba \
    --compare output/roms/GenedRom-it.gba \
    --json /tmp/en_french_leak.json

# audit a *built* ROM to see which tables that language still leaks French on
python3 scripts/audit_english_rom_french_leak.py --rom output/roms/GenedRom-de.gba
```

## Detector notes & caveats (same spirit as the sibling audit script)

- French is detected structurally: a run must decode to word-like tokens, then
  carry a strong French marker — an accent inside a real word, an unambiguous
  elision (`qu'`, `c'est`, `-vous`, …), or ≥2 distinct French function words.
- The é in **Poké / Pokédex / Pokémon** is masked (legitimately English), and
  accented English loanwords/proper nouns (`Café`, `Véga`) are accent-folded
  against an allowlist, so they never register as French.
- Bare `l'` / `d'` / `s'` are **not** treated as French elisions — they collide
  with English (`Farfetch'd`, `ol' Mel`, `Borrius'`).
- Density + region classification is the verdict; a single isolated hit is not.
  Low-density `unclassified` clusters may include residual false positives from
  graphics data whose bytes decode to accent glyphs — cross-check with the
  `--compare` decode before trusting them.
- The `tests/unit/test_audit_english_rom_french_leak.py` guard asserts the
  known move-name / move-description / Pokédex leaks stay detected.
