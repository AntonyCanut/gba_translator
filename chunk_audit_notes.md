# Audit chunks 00-70 (aperçu rapide)

- Règle vérifiée : segments visibles (sans codes `{COLOR}`, `{STR_VAR_*}`) doivent rester ≤36 caractères entre `\n/\p/\l`.
- Sensible/illisible : lignes manifestement corrompues ou remplissage binaire/garbage non prises en compte pour correction immédiate.

## Volumétrie globale (automatique)
- Nombre total de segments >36 caractères détectés sur chunks 00-70 : ~2 680 (trop volumineux pour une passe manuelle en une étape).
- Exemples de blocs très longs et lisibles (prioritaires) :
  - fr_chunks/chunk_01.txt:135 (`0x1880F8`) «Mon copain m’a offert des perles.» — réduit.
  - fr_chunks/chunk_01.txt:144 (`0x188F53`) «J’ai tout donné, aucun regret.» — réduit.
  - fr_chunks/chunk_02.txt:65 (`0x19A7F1`) phrase double-ligne très longue sur les objets en rab.
  - fr_chunks/chunk_02.txt:84 (`0x19EB59`) paragraphe Cherche-Objet (plusieurs segments >36, à re-couper proprement).
  - fr_chunks/chunk_03.txt:15 (`0x1BD390`) description des modes de combat (phrases >100 caractères à refendre selon les breaks d’origine).
- Nombreuses lignes illisibles/garbage (ex. chunk_03/chunk_05 blocs d’octets ou glyphes) laissées de côté pour l’instant.

## Corrections déjà appliquées
- fr_chunks/chunk_01.txt
  - 0x1880F8 raccourcie : «Mon copain m’a offert des perles.»
  - 0x188F53 raccourcie : «J’ai tout donné, aucun regret.»

## Prochaines priorités proposées
1) Traiter les lignes lisibles >36 caractères dans `chunk_02` (jetons/prix, messages Cherche-Objet, guides) en respectant les breaks de l’origin.
2) Traiter `chunk_03` entrées lisibles (modes de combat, obstacles plongée, etc.).
3) Continuer chunk par chunk en excluant les sections corrompues/garbage pour l’instant.

