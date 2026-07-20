---
name: unbound-link-lost-live-offset-4577bc
description: "Message « link was lost » : la cellule VIVANTE est 0x4577BC/0x4577F8 (pointeurs 0x1185A4/0x117C08), PAS 0x4577B9/0x4577F5 (0 référence, dead space). Écrire à l'offset mort déborde de 3 o sur la chaîne vivante → string mid-mot (« Le » perdu)."
metadata:
  node_type: memory
  type: project
  originSessionId: 5cab6a83-dc14-4e43-80c1-f89a3e8c57eb
---

B-113 (branche test/pr, gba_translator multilang registry).

**Le bug :** `tests/e2e/test_ellipsis_pauses_fr.py::test_link_lost_message_pause`
échouait — la pause ellipse 0xB0 manquait sur le message « The WIRELESS
COMMUNICATION SYSTEM link has been dropped<0xB0> ».

**La cause racine (PIÈGE offset mort) :** `languages/fr/combined_fr.txt` avait
DEUX entrées par message, à 3 octets d'écart :
- `0x4577B9` / `0x4577F5` (bloc MAJUSCULE, « …interrompu… ») = **dead space, 0
  référence pointeur**. En EN ce sont juste les 3 espaces de tête `000000`.
- `0x4577BC` / `0x4577F8` (bloc minuscule, « …perdu<0xB0> ») = **les vraies
  cellules** : les pointeurs jeu 0x1185A4→0x4577BC et 0x117C08→0x4577F8 pointent
  ICI (vérifié `en.count(struct.pack("<I", off+0x08000000))`).

L'entrée morte 0x4577B9 « Le lien WIRELESS… » écrite en place déborde sur
0x4577BC et **clobbe** la chaîne vivante → le pointeur lit à partir du 4ᵉ octet
→ « lien WIRELESS… » (le « Le » sauté, mid-mot). En jeu : message tronqué.

**Le fix :** SUPPRIMER les entrées mortes 0x4577B9/0x4577F5 de combined_fr.txt.
Les cellules vivantes 0x4577BC/0x4577F8 (« …perdu<0xB0> ») gagnent alors, byte-
faithful à l'EN (`<0xB0>`, 1 o — voir [[unbound-ellipsis-pause-b0-glyph]]).
Vérifier TOUJOURS via le pointeur vivant, pas l'offset combined
([[unbound-patch-repoint-via-live-cell-not-original-offset]],
[[unbound-pipeline-unreachable-name-cells]]).

**Collision parallèle :** un ticket frère avait « corrigé » en ajoutant `<0xB0>`
à l'offset MORT 0x4577B9 (+ changé le test pour chercher « interrompu »). C'est
faux (clobbe la cellule vivante). À la résolution de rebase : garder ma
suppression + remettre le test sur « perdu » (la vraie chaîne).
[[unbound-e2e-tests-gate-committed-rom]] (rebuild + commit la ROM).
