---
name: unbound-pokedex-entries
description: "Fiches Pokédex Unbound — table, fenêtre 3 lignes/232 px, patch post-build de re-wrap/raccourcissement"
metadata:
  node_type: memory
  type: project
  originSessionId: 6c893098-a37b-47e0-9389-ee825eeec0ea
---

Les descriptions du Pokédex Unbound sont une `PokedexEntry` de **36 octets** à partir de `0x1A35800` (file offset) ; le **pointeur de description est en tête de struct** (struct+0, LE, base 0x08000000). La catégorie « X Pokémon » (struct+0x12) est protégée par `src/core/fixed_tables.py` (0x1A35800–0x1A3ABB0) — NE PAS la réécrire. ~905 fiches valides ; au-delà de l'index ~905 la table déborde sur des données binaires (filtrer par `pokedex.is_description`).

**Fenêtre d'affichage = 3 lignes max, largeur ≤ 232 px** (≈40-43 car/ligne). Preuve : la ROM ES n'a AUCUNE fiche > 3 lignes (max 232 px) ; ES sert de référence de largeur. Le FR héritait des coupures EN → 188 fiches sur 4 lignes ; 164 traductions FR trop verbeuses (110-154 car, vs ~80 en ES) ne tiennent pas en 3×232 et doivent être **raccourcies**, pas seulement re-wrappées.

Correctif (juin 2026, commit gba_translator) : `src/core/pokedex.py` (table + re-wrap pixel via dialogue_linewrap) + `scripts/patch_pokedex_fr.py`, **dernière étape de `make build-fr`** (après patch_version_fr, donc immunisée). **CRITIQUE : le script était absent du Makefile lors d'un premier commit** — toujours vérifier que `PATCH_POKEDEX_FR_SCRIPT` figure dans la cible `build-fr` du Makefile. Sans cela : fiches sur 4+ lignes, et la pipeline de traduction peut écrire des noms de move (ex. « Téléport » à mid-description 0xa40f23) qui corrompent les fiches. La passe : re-wrappe chaque fiche ≤3 lignes ; écrit en place si ça rentre, sinon **relocalise en espace libre (FreeSpaceAllocator SANS reserved_rom — avec la ROM ES en reserved il reste 0 octet libre) + repointe struct+0**. `data/pokedex_fr_overrides.json` = 164 descriptions FR raccourcies (clé = offset EN).

Bugs builder révélés (corrigés par cette passe, pas à la source) : (1) **fusion** — ~13 fiches des blocs packés 0x44xxxx/0x165xxx/0x166xxx avec traduction JSON plus longue que le slot écrites au-delà du terminateur → 2 fiches collées ; (2) **collision** — 5 offsets (0xa40fc0…) où le JSON mappe un nom de talent (« Bouclier », « Récolte »…) alors que le struct dex pointe le même slot ; la vraie description est dans la ROM source (englishrom contaminée = déjà FR) → fallback sur `entry.text` source + relocation obligatoire pour ne pas écraser le talent partagé ; (3) le `°` doit être autorisé dans `is_description` (encodé en º). Voir [[unbound-fr-build-lives-in-gba-translator]] et [[unbound-special-text-rules]].
