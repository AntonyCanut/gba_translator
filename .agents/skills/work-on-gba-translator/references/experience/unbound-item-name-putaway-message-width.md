---
name: unbound-item-name-putaway-message-width
description: "Un nom d'objet FR peut tenir dans sa cellule mais déborder le message « a rangé … » (ligne 1, 192px, sans retour auto)"
metadata:
  node_type: memory
  type: project
  originSessionId: e9f64224-353a-4466-a8d3-c4470a8a2a90
---

Le message de rangement en poche (template 0x1A5218 : « {PLAYER} a rangé {OBJET}\ndans la {POCHE}. ») pose le nom de l'objet sur la **ligne 1 sans retour à la ligne automatique**. La largeur utile de la fenêtre FRLG est **192px** (`DEFAULT_MAX_LINE_WIDTH` dans `src/core/dialogue_linewrap.py`). Un nom trop large déborde et se corrompt visuellement (ex. « Convertisseur Braille » → « …BraillZon » à l'écran) — c'est le bug affiché, PAS une chaîne corrompue en ROM (la string est bien terminée à 0xFF).

Donc un nom d'objet a DEUX contraintes de largeur, pas une :
1. tenir dans sa cellule/relocalisation (voir [[unbound-item-name-cells-class2]]) ;
2. tenir sur `line_width("WWWWWWW a rangé " + nom) <= 192px` (nom joueur ≤ 7 glyphes larges).

Mesurer avec `from src.core.dialogue_linewrap import line_width`. Fix = raccourcir le nom FR. Ex : « Braille Converter » (EN, 17o) traduit « Lecteur Braille » (15o, colle à la desc « Appareil lisant… ») ; garde-fous : `tests/e2e/test_item_name_widths_fr.py` (niveau ROM) + `tests/test_item_name_braille_converter_fr.py` (niveau source combined_fr).

PIÈGE : si le nom apparaît aussi dans des dialogues/missions (prose), le raccourcir crée une incohérence → passe de renommage multi-chaînes (cf. ticket B-132 : « Feuilles de Mystherbe » 0xEB92C0, « Catalogue des Dresseurs » 0xEB930E débordent encore mais sont référencés en prose). Braille était sûr car son nom n'apparaît nulle part ailleurs.

Build FR déterministe : rebuild byte-identique → un rebuild sur base fusionnée qui ne change aucun octet prouve que la ROM committée est déjà canonique (cf. [[unbound-build-determinism-relocation-order]]). Build local via venv 3.14 (`/Users/akc/Projects/Test/Unbound/.venv/bin/python`, pyyaml présent) car `python3` système = 3.9 < requires-python 3.11 ; `make PYTHON=$VP prepare-fr && make PYTHON=$VP build-fr` (prepare-fr séparé : FR_TRANSLATION résolu au parse du Makefile).
