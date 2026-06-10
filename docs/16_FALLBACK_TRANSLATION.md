# Algorithme de repli pour les chaînes non traduites (shrink-to-fit)

## Problème

Lors d'un `make build-fr`, le réinséreur écrit chaque traduction française à
l'emplacement (offset) de la chaîne anglaise d'origine. L'espace disponible est
limité : `longueur d'origine + padding adjacent`. Quand le français encodé
dépasse ce budget, l'entrée était auparavant **ignorée** (`skipped_too_long`)
et **l'anglais restait en place**.

Sur un build complet, cela laissait des milliers de chaînes (≈ 7 468 sur le
build de référence) en anglais alors qu'une traduction française existait.

## Objectif

Transformer « on laisse l'anglais » en « on fait tenir le français ». À partir
du texte français complet et du budget en octets, on synthétise la plus longue
variante fidèle qui tient encore.

Module : [`src/core/fallback_translator.py`](../src/core/fallback_translator.py)
(`FallbackSynthesizer`). Intégré au `SmartReinserter` via le drapeau
`allow_fallback` (option CLI `--allow-fallback`, activée dans la cible
`build-fr`).

## Hypothèses sur les données d'entrée (contrat)

1. Le texte français complet est disponible (les codes de contrôle sont écrits
   littéralement sous la forme `<0xNN>` et les retours à la ligne `\n`, tels que
   le réinséreur les consomme).
2. `max_length` est le budget **terminateur inclus** (cohérent avec
   `SmartReinserter`, qui compare `len(encoded)`, terminateur compris).
3. Les codes de contrôle (`<0xNN>`, `\n` → `0xFE`) sont atomiques et
   significatifs : jamais coupés en plein milieu, jamais supprimés
   silencieusement. Seuls des caractères *littéraux* sont retirés.
4. La longueur en octets est mesurée en **encodant réellement** les candidats
   (via `TextEncoder`), donc les expansions d'alias (`œ`→`oe`, `…`→`...`) sont
   comptées exactement.
5. Les accents (é/è/à/ç…) s'encodent sur un seul octet comme leur lettre de
   base : les retirer ne gagne rien et dégraderait la qualité — non utilisé.

## Cascade de stratégies

On applique du *sans perte* vers le *avec perte*, et on s'arrête dès que ça
tient. `strategy` indique l'étape gagnante.

1. **`none`** — le texte tient déjà, renvoyé tel quel.
2. **`whitespace`** *(sans perte)* — espaces répétés réduits, espaces avant
   ponctuation fermante supprimés, bords nettoyés.
3. **`abbreviate`** — remplacement de mots entiers par des abréviations
   françaises standard (`s'il te plaît`→`stp`, `numéro`→`n°`, `Monsieur`→`M.`…).
   Dictionnaire volontairement restreint : une abréviation ambiguë est pire
   qu'une troncature propre.
4. **`truncate`** — troncature consciente des tokens : on garde le plus long
   préfixe d'unités atomiques qui tient, en coupant de préférence sur une
   frontière de mot et sans jamais scinder un token `<0xNN>`. Dernier recours :
   le sens est écourté mais la chaîne reste un français valide plutôt que de
   revenir à l'anglais.

Le résultat est par construction valide pour la charmap CFRU et toujours
≤ budget, donc le réinséreur peut l'écrire en place sans corrompre la chaîne
voisine.

## Ordre dans le réinséreur

Pour une chaîne trop longue, `SmartReinserter.reinsert_text` essaie, dans
l'ordre :

1. **Relocation** (`allow_relocate`, si les pointeurs sont connus) — sans perte.
2. **Repli shrink-to-fit** (`allow_fallback`) — en place, perte minimale.
3. **Troncature brute** (`allow_truncate`) — coupe au plus court.
4. Sinon `skipped_too_long`.

La statistique `fallback_used` (rapport de build et `reinserter_reports`)
compte les chaînes sauvées, et chaque warning consigne le texte d'origine, le
texte synthétisé et la stratégie employée.

## Tests

[`tests/test_fallback_translator.py`](../tests/test_fallback_translator.py) :
chaîne qui tient déjà, normalisation d'espaces, abréviation, troncature sur
frontière de mot, garantie de budget, non-scission des tokens de contrôle, et
le câblage `SmartReinserter` (sauvée avec `allow_fallback`, ignorée sans).
