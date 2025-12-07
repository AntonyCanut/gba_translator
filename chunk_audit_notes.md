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
  - 0x1880F8 rééquilibrée avec `\\n` : «Mon copain m’a offert de\\ngrosses perles.»
  - 0x188F53 rééquilibrée avec `\\n` : «J’ai fait de mon mieux,\\ndonc aucun regret !»
- fr_chunks/chunk_02.txt (toutes les lignes lisibles >36c corrigées)
  - Ex : 0x19A7F1, 0x19EB59, 0x1A2B88, 0x1A6046, etc. Rebrisés avec `\\n` en conservant les codes.
- fr_chunks/chunk_03.txt (lignes lisibles >36c corrigées)
  - Ex : 0x1BCB81, 0x1BD390, 0x1BD706, 0x1BF053, 0x1C566A, 0x1C5AEB, etc.
  - Restent non traités car illisibles/garbage : 0x1BE564, 0x1C1367, 0x1F47AC, 0x2009AC, 0x209428, 0x210CC4, 0x220FDC.
- fr_chunks/chunk_04.txt : 0x24F3D8, 0x24F481, 0x24F534 rebrisés (segments ≤36c).
- fr_chunks/chunk_06.txt : 0x3D8E10 rebrisé ; restent entrées illisibles (0x3E0F9F, 0x3E120B, 0x3E1326, 0x3E1529).
- fr_chunks/chunk_10.txt : 0x3FB484 rebrisé ; reste garbage 0x3F9050.
- fr_chunks/chunk_11.txt : 0x3FD006 rebrisé.
- fr_chunks/chunk_12.txt : lignes lisibles corrigées (0x3FDBEF, 0x3FDDEB, 0x41665C, 0x4166A7, 0x416A98, 0x416AE2, 0x416B16, 0x416B3E). Reste garbage 0x407C3F.
- fr_chunks/chunk_13.txt : toutes lignes lisibles corrigées (0x416BFB, 0x416D17, 0x416D78, 0x4170DE, 0x417494). Plus de dépassements.
- fr_chunks/chunk_14.txt : toutes lignes lisibles corrigées (0x418642, 0x418690, 0x4186B0, 0x418937, 0x4189EE, 0x41971A, 0x4199AB, 0x4199F4, 0x419D89). Plus de dépassements.

## Prochaines priorités proposées
1) Poursuivre chunk par chunk à partir de `chunk_04` en rebrisant les segments lisibles >36c (en respectant les breaks d’origine).
2) Laisser de côté pour l’instant les entrées illisibles/garbage listées ci-dessus jusqu’à clarification.
