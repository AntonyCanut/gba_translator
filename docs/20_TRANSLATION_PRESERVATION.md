# 20 — Préservation des traductions (règles anti-écrasement)

> **Pour Claude / Codex / tout agent IA.** Ce document est la référence unique sur
> *comment ne PAS détruire des traductions FR existantes*. Lis-le **avant** toute
> édition de `combined_fr.txt` ou de la chaîne de build FR.
>
> Origine : commit **`c7c1ede`** (2026-06-15) a silencieusement ramené **97 entrées**
> (dont 94 noms de lieux) à leur forme anglaise/périmée. Ticket de récupération :
> **B-52**. Ce document + la garde `scripts/check_translation_integrity.py` existent
> pour que ça ne se reproduise **jamais**.

---

## 1. Le modèle mental : la traduction FR est un empilement de couches

Le texte FR visible en jeu ne vient **pas d'une seule source**. La ROM finale est
construite en empilant **trois couches**, chacune pouvant écraser la précédente.
**Corriger dans la mauvaise couche = correction silencieusement écrasée au prochain build.**

| # | Couche | Source éditable | Appliquée par | Ce qu'elle possède |
|---|--------|-----------------|---------------|--------------------|
| 1 | **Texte par pointeurs** | `combined_fr.txt` → CSV trilingue → `*_translation_ready.json` | `19_build_translated_rom_generic.py` | La grande majorité des dialogues, descriptions, menus atteints par une table de pointeurs |
| 2 | **Overrides / tables fixes** | `combined_fr.txt` (offsets inline) + scripts dédiés | `patch_fixed_table_names.py`, `apply_inline_overrides_fr.py` | Noms en cellules à largeur fixe et chaînes hors-pointeur (noms de lieux carte, objets, NPC) |
| 3 | **Patches code/graphismes post-build** | code Python du script | `patch_font_fr.py`, `patch_time_format_fr.py`, `repair_*_lz77_blocks.py`, `repoint_stale_text_pointers.py` | Police, date/heure (Thumb), images LZ77, repointage |

> **Règle d'or.** Le **texte** (dialogues, noms, descriptions) se corrige **dans
> `combined_fr.txt`**. Jamais dans un JSON intermédiaire, le CSV, ou la ROM
> directement : ces artefacts sont **régénérés à chaque build** et ta correction
> disparaît. Les couches 2 et 3 ne se touchent que pour de la logique (code, glyphes,
> compression), pas pour traduire une phrase.

### Le piège « couche » qui a tué c7c1ede

Les **13 labels de la carte du monde** (offsets `0xB5xxxx` / `0x72xxxx` : Trou Glacé,
Volcan Cendreux, Île de la Lune…) sont **inline (couche 2)** : ils **n'existent PAS
dans le CSV trilingue**. Ils ne survivent que parce que `combined_fr.txt` les contient
et que `apply_combined_fr.py --extend` les réinjecte. Une réécriture en masse de
`combined_fr.txt` (sed, regex globale, `csv.writer`, working copy périmée) les efface
**sans aucune erreur** — c'est exactement ce qu'a fait `c7c1ede`.

---

## 2. `combined_fr.txt` — la source de vérité

Format d'une ligne : `0x<offset_hex>: <texte FR>` (offset, deux-points, espace, texte).

### Règle last-wins (CRITIQUE)

```python
# apply_combined_fr.py, _load_combined()
mapping[offset] = text   # dernière occurrence rencontrée → gagne
```

- **~971 offsets sont dupliqués** dans le fichier.
- Le **bloc en hexa minuscule, en bas du fichier**, est la **version vivante**.
- Toute correction se fait **dans ce bloc minuscule**, jamais dans les entrées du haut.
- Une entrée du haut (`0x720E74: Ville de Fallshore`) peut coexister avec l'entrée
  vivante (`0x720e74: Fallshore`) — seule la dernière compte. **Un `grep -c` ne dit
  donc RIEN sur la valeur réellement injectée.**

### Pourquoi un `grep -c` ne suffit pas

`c7c1ede` **n'a pas supprimé** de lignes : il a **réécrit leur valeur**
(`Fallshore` → `Ville de Fallshore`). Un comptage de lignes serait resté à 13 et
n'aurait **rien** détecté. La seule vérification fiable contrôle la **valeur résolue
par last-wins**, pas la présence d'une ligne. C'est ce que fait la garde du §4.

---

## 3. La chaîne d'injection (pipeline) — l'ordre exact

```
combined_fr.txt  (SOURCE DE VÉRITÉ — édition chirurgicale uniquement)
   │
   │  python3 scripts/apply_combined_fr.py --extend        ← OBLIGATOIRE
   │     (sans --extend, les offsets absents du CSV — dont les 13 labels carte —
   │      ne sont JAMAIS injectés)
   ▼
CSV trilingue  (CRLF + LF dans les champs ; jamais csv.writer)
   │
   │  python3 src/translators/09_csv_to_json_v2.py <csv.csv> --allow-too-long
   │     (l'argument CSV est OBLIGATOIRE ; sans lui le script lit un CSV vide)
   ▼
output/translation/<date>_translation_ready.json
   │
   │  make build-fr   (enchaîne les 8 étapes ci-dessous)
   ▼
output/roms/GenedRom-fr.gba
```

`make build-fr` exécute, dans l'ordre (cf. `CLAUDE.md` → « FR Build Pipeline ») :

1. `19_build_translated_rom_generic.py` — copie EN + injecte le texte (couche 1)
2. `patch_font_fr.py` — glyphes FR (couche 3)
3. `patch_fixed_table_names.py` — noms en tables fixes (couche 2)
4. `patch_time_format_fr.py` — date/heure Thumb (couche 3)
5. `apply_inline_overrides_fr.py` — overrides inline (couche 2)
6. `repair_stable_lz77_blocks.py` — images LZ77 (couche 3)
7. `repair_localized_lz77_blocks.py` — blocs LZ77 localisés (couche 3)
8. `repoint_stale_text_pointers.py` — repointage final (couche 3)

> **Ne jamais sauter une étape.** Sauter `apply_combined_fr.py --extend` perd les
> labels carte ; sauter `repair_*_lz77` corrompt les graphismes ; sauter
> `repoint_stale_text_pointers` laisse des pointeurs sur des octets périmés.

---

## 4. La garde exécutable — `scripts/check_translation_integrity.py`

Vérifie, **sur la valeur résolue last-wins**, que les 13 labels carte n'ont pas
régressé vers une forme anglaise/périmée. C'est le filet qui aurait stoppé `c7c1ede`.

```bash
# Doit afficher 13 [OK] et sortir avec le code 0
python3 scripts/check_translation_integrity.py

# Rapport machine (CI / hooks)
python3 scripts/check_translation_integrity.py --json
```

- Code de sortie **0** = conforme, **1** = au moins un label régressé.
- Testé par `tests/unit/test_translation_integrity.py` (rapide, sans ROM).
- **À lancer après TOUTE édition de `combined_fr.txt`**, avant de rebuild.

> Cette garde complète — sans le remplacer — `tests/test_location_names_fr.py`
> (ajouté par B-52) qui vérifie qu'aucune forme périmée ne redevient *atteignable par
> pointeur* dans la ROM **buildée**. Les deux ensemble couvrent la source (ce fichier)
> et le binaire (la ROM).

---

## 5. Règles de préservation (à respecter sans exception)

### ❌ INTERDIT

- **Réécrire `combined_fr.txt` en entier** — pas de `sed`/regex globale, pas de
  `csv.writer`, pas de re-sérialisation du fichier. Édition **chirurgicale** : une
  entrée à la fois, dans le bloc minuscule du bas.
- **Travailler sur une working copy périmée.** `c7c1ede` était un `git` désynchronisé :
  faire `git status` + `git log -1 combined_fr.txt` **avant** d'éditer ; ne jamais
  régénérer le fichier à partir d'une source plus ancienne que `HEAD`.
- **Corriger du texte ailleurs que dans `combined_fr.txt`** (JSON, CSV, ROM) — écrasé
  au prochain build.
- **Committer une ROM sans `make test-rom`** ni `check_translation_integrity.py` vert.
- **`apply_combined_fr.py` sans `--extend`** ; **`09_csv_to_json_v2.py` sans argument CSV**.

### ✅ OBLIGATOIRE — workflow d'une correction de texte

1. `git status` propre + identifier la **dernière** occurrence de l'offset
   (`grep -in "^0x0*<offset>:" combined_fr.txt | tail -1`).
2. Éditer **uniquement** cette dernière ligne (insertion chirurgicale).
3. `python3 scripts/check_translation_integrity.py` → 13 OK, exit 0.
4. Rejouer la chaîne complète : `apply_combined_fr.py --extend` → CSV → JSON → `make build-fr`.
5. Vérifier les **octets décodés dans la ROM buildée** (pas le fichier) — une entrée
   peut être ignorée silencieusement (trad vide, texte trop long sans pointeur libre).
6. `make test-rom` + `tests/test_location_names_fr.py` verts avant tout commit.

---

## 6. Cas d'étude — `c7c1ede` (2026-06-15)

| | |
|---|---|
| **Intitulé du commit** | « correct 'And' to 'Et' » (anodin en apparence) |
| **Cause racine** | Working copy **périmée** : le commit a re-sérialisé `combined_fr.txt` à partir d'un état antérieur, annulant 97 entrées sans le signaler |
| **Dégâts** | `Mont Foudre`→`Mont Thundercap` (14), `Île de la Lune`→`Fullmoon Island`, `Fallshore`→`Ville de Fallshore` (26), `Dehara`→`Ville de Dehara` (27)… |
| **Pourquoi non détecté** | Les lignes existaient toujours ; seules leurs **valeurs** avaient régressé. Aucun test ne contrôlait la valeur résolue |
| **Récupération** | B-52 : 54 substitutions chirurgicales + rebuild + guard de pointeur |
| **Prévention** | Ce document (couches + last-wins) + `check_translation_integrity.py` (valeur résolue) + `test_location_names_fr.py` (pointeur ROM) |

**Leçon.** Un commit au libellé inoffensif peut détruire des dizaines de traductions
si la working copy est périmée et le fichier réécrit en masse. La défense n'est pas
« faire attention » : c'est **édition chirurgicale + garde sur la valeur résolue +
test ROM**, à chaque fois.

---

## Voir aussi

- `CLAUDE.md` → « combined_fr.txt — SOURCE DE VÉRITÉ » et « FR Build Pipeline »
- `.claude/rules/patterns/forbidden.md` → section « Traductions »
- `scripts/check_translation_integrity.py` / `tests/unit/test_translation_integrity.py`
- `tests/test_location_names_fr.py` (garde de pointeur ROM, B-52)
