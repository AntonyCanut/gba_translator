# Audit de couverture des traductions (multi-langue)

> Généré par `scripts/audit_translation_coverage.py`. Relancer pour rafraîchir :
> ```bash
> python3 scripts/audit_translation_coverage.py            # toutes les langues sauf en/de
> python3 scripts/audit_translation_coverage.py --languages it   # une seule cible
> python3 scripts/audit_translation_coverage.py --include-de      # inclure l'allemand
> ```
> L'allemand (`de`) est volontairement **exclu** de cet audit (demande du ticket).

## Comment lire l'audit

L'**anglais** (`languages/en/combined_en.txt`) est la **référence** : c'est
l'extraction du texte de la ROM source à *tous* les offsets présents dans le
fichier maître français. Son jeu de clés = l'univers des chaînes traduisibles.
Chaque autre langue est comparée à lui, offset par offset :

| Statut | Signification |
| --- | --- |
| `translated` | Offset présent **et** texte différent de l'anglais → vraie traduction |
| `untranslated` | Offset présent mais texte **identique** à l'anglais (recopié, pas traduit) |
| `missing` | Offset présent en EN mais **absent** du fichier de la langue → reste anglais en jeu |
| `orphan` | Offset présent dans la langue mais **inconnu** de la référence EN/FR |

`coverage%` = `translated / offsets_référence` (la vraie progression utile).

## Résultats — 23 873 offsets de référence (EN)

| Langue | Statut projet | Présents | Traduits | Non traduits (=EN) | Manquants | Orphelins | Couverture |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| **fr** | complete | 23 873 | 21 423 | 2 450 | **0** | 1 | **89.7 %** |
| **it** | in_progress | 12 439 | 12 056 | 383 | **11 434** | 1 710 | **50.5 %** |
| **es** | reference | 23 873 | 14 186 | 9 687 | 0 | 0 | 59.4 % |

### Lecture

- **FR** — 0 offset manquant : toutes les chaînes ont une entrée. Les 2 450
  « non traduits » sont en quasi-totalité des chaînes volontairement identiques
  à l'anglais (noms propres, codes, mono-glyphes). FR reste la référence
  byte-perfect.
- **IT** — c'est là que sont les trous : **11 434 offsets manquants** (restent
  anglais en jeu) + 383 entrées recopiées de l'anglais. Couverture réelle
  **50.5 %**. C'est la cible prioritaire pour combler les trous.
- **ES** — ROM communautaire de référence (non maintenue ici). Ses 9 687
  « non traduits » montrent simplement que la traduction espagnole d'origine
  laisse beaucoup de chaînes en anglais : utile comme second filet quand l'IT
  cherche une référence, mais l'ES n'est pas fiable à 100 %.

### Point d'attention — 1 710 offsets « orphelins » en italien

L'IT contient 1 710 offsets **absents de la référence EN/FR**. Échantillon :
mélange de vraies chaînes (`Muk`, `Mew`, `Uovo`=Œuf) et de lignes corrompues
issues des dumps JSON (`??????`, mojibake type `NORUYceffec…`). 362 tombent
dans la région texte principale `0x1F00000–0x1F80000`. À trier : certains sont
peut-être des pointeurs valides que le FR n'a jamais couverts, d'autres du bruit
à purger. Liste complète : `output/audit/translation_orphans_it.csv`.

## Fichiers produits (`output/audit/`, régénérables — non versionnés)

| Fichier | Contenu |
| --- | --- |
| `translation_coverage.csv` | **Tableau large** : une ligne par offset, colonnes `en, fr, it, es` + `status_*`. C'est le « en anglais ça, en français ça, en italien ça » demandé. |
| `translation_gaps_it.csv` | Uniquement les offsets IT à faire (`missing` + `untranslated`) avec le texte anglais à côté → prêt pour un traducteur. |
| `translation_gaps_es.csv` | Idem pour l'espagnol (diagnostic). |
| `translation_gaps_fr.csv` | Idem FR (devrait ne contenir que des `untranslated` volontaires). |
| `translation_orphans_it.csv` | Offsets IT inconnus de la référence (à trier/purger). |

### Workflow pour combler les trous en italien

1. Régénérer : `python3 scripts/audit_translation_coverage.py`
2. Ouvrir `output/audit/translation_gaps_it.csv` (11 434 lignes `missing`).
3. Traduire la colonne `english` → ajouter `0x<offset>: <texte_it>` dans
   `languages/it/combined_it.txt` (même format, dernière entrée gagnante).
4. Rebuild IT via `scripts/build_language.py it`, puis relancer l'audit pour
   vérifier que `missing` diminue.
