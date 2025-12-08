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
- fr_chunks/chunk_15.txt : blocs MEC POKé rebrisés (0x41A2E1, 0x41A7B0, 0x41B554, 0x41B5B6, 0x41B69E, 0x41B83D, 0x41B8BF, 0x41BA41, 0x41BB40, 0x41BD10, 0x41BE76, 0x41C0AF, 0x41C23B, 0x41C384, 0x41C459, 0x41C587, 0x41C693, 0x41C7B4, 0x41C82A, 0x41C994, 0x41CE3B, 0x41CEA7, 0x41CFD1). Plus de dépassements lisibles.
- fr_chunks/chunk_16.txt : pas de segments >36 détectés.
- fr_chunks/chunk_19.txt : phrases de salon/échange rebrisées (0x458019, 0x4582C0, 0x458314, 0x458369, 0x458479, 0x4584C0, 0x458596, 0x458915, 0x45897B, 0x4589E3, 0x458AB7, 0x458E6E, 0x458F2A, 0x458F5F, 0x458F94, 0x459250, 0x459541). Restent garbage non traités : 0x45CEFA, 0x46A6F5, 0x4717C7 et assimilés.
- fr_chunks/chunk_21.txt : descriptions capacité rebrisées (0x71C950, 0x71C98C, 0x71C9AC, 0x71C9D4, 0x71CA30, 0x720F03, 0x720F27). Restent chaînes illisibles/garbage : 0x48903A, 0x4892B9, 0x489862, 0x4A8727, 0x4EDC07, 0x4F3A6C, 0x4FDAC2, 0x507C5B, 0x5081E8, 0x5082B3, 0x6C09CF, 0x719A0B.
- fr_chunks/chunk_20.txt : descriptions de capacités rebrisées (0x482C4F, 0x482CD3, 0x482E08, 0x483203, 0x483397, 0x4834ED, 0x48382A, 0x48386D, 0x483927, 0x4839F8, 0x483A3A, 0x48400F, 0x48422E, 0x484353, 0x484398, 0x4843E5, 0x48453C, 0x484689, 0x48475E, 0x484A15, 0x484BA1, 0x484DCD, 0x48515E, 0x4855E9, 0x48562F, 0x485679, 0x485752, 0x485798, 0x485857, 0x4858E2, 0x4859AE, 0x485A30, 0x485A7A, 0x485C66, 0x485CF0, 0x485E55, 0x485F6C, 0x48602B, 0x486265). Plus de dépassements détectés.
- fr_chunks/chunk_18.txt : entrées Pokédex rebrisées (0x44C0B3–0x44E7E6) + messages de lien (0x4571B7, 0x457264). Plus de dépassements détectés.
- fr_chunks/chunk_22.txt : quelques dialogues rebrisés (0x7213FC, 0x721FAE, 0x724962, 0x741625, 0x740195, 0x74B310, 0x74BF85, 0x74C058, 0x74BB69, 0x74BB9B, 0x74BBE2). Restent de nombreuses lignes avec préfixes corrompus/garbage (ex. 0x721340, 0x7248C3, 0x745132, 0x745194…) encore à traiter ou ignorer si sensibles.
- fr_chunks/chunk_23.txt : premiers ajustements (0x75CA45, 0x762A86, 0x762CD5, 0x763050, 0x763130, 0x763209, 0x763266, 0x7632FE, 0x7634F8, 0x76454F, 0x7645AD, 0x75DB9E, 0x765196). Restent nombreuses lignes longues ou corrompues (ex. 0x75D8D2, 0x762E5A, 0x7637DB, 0x764E54, 0x76501D, 0x7655A1, 0x7657D1…).

## Prochaines priorités proposées
1) Poursuivre chunk par chunk à partir de `chunk_17` (nombreuses entrées Pokédex) puis `chunk_18`, en rebrisant les segments lisibles >36c (en respectant les breaks d’origine).
2) Laisser de côté pour l’instant les entrées illisibles/garbage listées ci-dessus jusqu’à clarification.
