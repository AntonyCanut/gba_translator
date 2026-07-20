---
name: unbound-de-font-patch-order-lz77-repair-revert
description: "Umlauts allemands ä ö ü encodés correctement mais glyphes invisibles en jeu — le patch font tournait avant repair_lz77, qui l'effaçait à chaque build"
metadata:
  node_type: memory
  type: project
  originSessionId: 7bb32408-2705-4759-b672-3b742b54fc70
---

Ticket B-211 « German letters » — après un premier « fix » (commit `a331cb8` dans
gba_translator, charmap 0x60-0x65→0xF1-0xF6) déclaré réussi et complété, l'utilisateur
rouvre le ticket : « au lancement du jeu sans save, l'intro n'affiche toujours pas les
caractères ». Le premier fix avait bien corrigé l'encodage mais pas le rendu visuel.

**Cause racine :** `languages/de/lang.yaml` (et aussi `it/lang.yaml`, `indie/lang.yaml`
— même bug latent, non signalé) déclarait l'étape `font` **avant**
`repair_lz77`/`repair_localized_lz77` dans la liste `patches:`. Ces deux étapes
(`scripts/repair_stable_lz77_blocks.py`) restaurent depuis la ROM anglaise tout bloc
LZ77 identique octet-à-octet entre EN et ES (anti-corruption pour les graphismes UI
partagés). Un bloc de police **non patché** est justement EN=ES (ni l'un ni l'autre
n'a de glyphe allemand) → à chaque `make build-de`, le patch `font.py` dessinait les
glyphes ä/ö/ü, puis `repair_lz77` désormais classait ce bloc comme « corrompu » et le
restaurait depuis l'anglais, effaçant silencieusement le patch. L'encodage (byte
0xF4 en mémoire) restait correct, seuls les pixels du glyphe disparaissaient — d'où
« encodage juste, rendu blanc » dans TOUS les écrans concernés, intro comprise (pas
un bug spécifique à l'intro : juste le premier écran texte qu'on voit sans save).

**Piège de diagnostic :** comparer les blocs de police par leur offset dans la ROM
anglaise (comme le fait `find_font_blocks(en_rom)`) après un build donne un faux
« identique à l'anglais » si le patch a été relocalisé en free-space (taille
compressée plus grande) — le VRAI bloc vivant est ailleurs. Toujours appeler
`find_font_blocks()` **sur la ROM buildée elle-même**, pas sur des offsets calculés
depuis l'EN, pour trouver le bloc réellement utilisé par le jeu.

**Fix :** déplacer `font` après `repair_lz77`/`repair_localized_lz77`, regroupé avec
les autres patchs graphiques LZ77 (`status_badges`/`type_icons`/`hp_labels`/
`dexnav_headers`) qui étaient déjà correctement ordonnés — c'était la seule étape
graphique mal placée. Même correction appliquée à IT et Indie (bug identique
présent mais jamais signalé, `font.py` y est un fallback vers `languages/fr/patches/
font.py`).

**Garde-fou ajouté :** `tests/test_language_registry.py::
test_font_patch_runs_after_lz77_repair_steps` vérifie l'ordre déclaratif sans
builder de ROM. `tests/e2e/de/test_accent_glyphs.py` existait déjà et documentait
ce pattern exact dans son docstring (« as documented in the FR equivalent of this
test ») mais personne ne l'avait relancé depuis l'introduction du bug — sa présence
seule ne suffit pas si le pipeline CI/build ne le déclenche pas après un rebuild.
Nouveau test Playwright `tests/e2e-playwright/german-translation.spec.ts` (lancer
avec `ROM_PATH=$(pwd)/output/roms/GenedRom-de.gba npm run test:e2e:german` ou
`--project=german`), qui rejoue exactement le scénario du bug (boot sans save,
avance dans l'intro).

Voir aussi [[unbound-font-patch-freespace-cascade]] (même famille de fragilité :
modifier `patch_font_*` a des effets de bord non locaux sur le reste du pipeline
de build) et [[unbound-fr-build-lives-in-gba_translator]] pour où corriger.
