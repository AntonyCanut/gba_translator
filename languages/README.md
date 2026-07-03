# `languages/` — translation files organized by language

Every language-specific translation file lives under `languages/<code>/`, so that
a language's data is self-contained and any **missing** piece is visible at a glance
(and can be turned into a patch ticket).

## Per-language layout

```
languages/<code>/
  combined_<code>.txt   Master EN→<lang> translation source (offset_hex + text)
  lang.yaml             Build registry entry (charmap, patches, metadata)
  data/                 Curated per-language override / guard files (optional)
```

- `combined_<code>.txt` — the authoritative translation source consumed by the
  build chain (`build_language.py` / `make build-<code>`).
- `lang.yaml` — declares how the language is built (see `scripts/build_language.py`).
- `data/` — language-specific curation data referenced by that language's
  post-build patch scripts. Only present when a language has such data. For FR:
  - `critical_strings_fr.txt` — guard file pinning fragile entries into the ROM.
  - `move_descriptions_fr_overrides.json` — hand-reviewed short move descriptions.
  - `pokedex_categories_fr.json` — EN→FR Pokédex category map.
  - `pokedex_fr_overrides.json` — hand-reviewed short Pokédex entries.
  - `pokemon_names_en_fr.json` — EN→FR species-name map for dialogue localisation.

## Coverage matrix

Snapshot of what each language currently ships. An empty cell is a **gap** —
a candidate for a dedicated patch ticket.

| Code | `combined_<code>.txt` | `lang.yaml` | `data/` overrides |
|------|:---:|:---:|:---:|
| `en` (source) | ✅ | ✅ | — |
| `es` | ✅ | ✅ | ❌ |
| `fr` | ✅ | ✅ | ✅ |
| `de` | ✅ | ✅ | ❌ |
| `it` | ✅ | ✅ | ❌ |
| `indie` | ✅ | ✅ | ❌ |

### Reading the gaps

FR is the reference build and is the only language with curated `data/` overrides.
The other translated languages (ES, DE, IT, Indie) inherit English break positions
and have no per-language override data yet — so Pokédex categories/entries, move
descriptions, species-name localisation and critical-string guards are FR-only.
Porting those to DE and IT is tracked by the sibling tickets **F-84** (German) and
**F-85** (Italian); ES/Indie remain uncovered and are natural follow-up tickets.

> Post-build **patch scripts** now live alongside each language's data in
> `languages/<code>/patches/<name>.py` (generic names, no `_<code>` suffix), so a
> missing patch reads as a gap to fill for that language. They feed the byte-perfect
> `make build-fr` recipe and the generic `scripts/build_language.py` driver; this
> folder holds both the translation *data* and its per-language *patch code*.
