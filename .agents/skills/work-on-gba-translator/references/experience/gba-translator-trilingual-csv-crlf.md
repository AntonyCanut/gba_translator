---
name: gba-translator-trilingual-csv-crlf
description: "Le CSV trilingue de gba_translator est en CRLF avec \\n LF dans les champs ; éditer chirurgicalement, jamais réécrire avec csv.writer"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f93af43f-f228-4353-a6eb-86e3bcd7f489
---

`output/translation/*_trilingual_translation.csv` (gba_translator) utilise des **fins de ligne CRLF** pour les enregistrements mais des **LF nus à l'intérieur des champs multi-lignes entre guillemets** (ex. `"Happy birthday!\nMay I heal..."`). Le fichier a un BOM UTF-8.

**Why:** Réécrire le CSV entier avec `csv.writer` **par défaut (LF)** reformate les ~30 000 lignes → diff énorme et illisible pour une correction d'une seule chaîne (constaté juin 2026 sur le ticket « infirmière non traduite »).

**Nuance (juin 2026, ticket noms de villes) :** `csv.reader → csv.writer(lineterminator='\r\n')` puis réécriture en `('﻿'+buf).encode('utf-8')` (BOM) **round-trip byte-identique** sur ce fichier (testé : `orig == out`). Donc réécrire via `csv.writer` est SÛR et donne un diff minimal (seuls les champs changés) À CONDITION de forcer le terminateur CRLF + BOM. Le piège n'est que le terminateur LF par défaut. Modifier uniquement la colonne 8 (`translation`), jamais EN/ES.

**How to apply:** Pour ajouter/modifier une ligne, faire une **insertion textuelle chirurgicale** : préserver le BOM, construire la ligne à la main (`offset,"original","spanish",len,pad,max,enc,cat,"trad",` + `\r\n`, LF réels dans les champs), l'insérer avant l'ancre, réécrire en bytes. La chaîne du Centre Pokémon vit dans **3 sources synchronisées** : `combined_fr.txt`, le CSV trilingue, et `*_translation_ready.json` (seul ce dernier est lu par `make build-fr` ; ajouter une entrée sans `pointer_offsets`/`raw_bytes` suffit, le builder les retrouve dans `englishrom_texts.json`). Voir [[unbound-fr-build-lives-in-gba-translator]].
