---
name: unbound-mission-menu-labels-live-pointer-false-negative
description: "Menu Missions labels (#46) — run précédent a cru \"All\" non traduit en lisant l'offset original périmé au lieu du pointeur vivant"
metadata:
  node_type: memory
  type: project
  originSessionId: de936285-973e-41b3-a3a5-5cb52724edc6
---

Issue #46 "Menu Missions" : 4 onglets = filtres du menu Missions, table de chaînes inline
à `0x1F5605C` (Active), `0x1F56063` (Inactive), `0x1F5609F` (All), `0x1F560A3` (Completed).
Traductions finales (féminin pluriel, accord avec « Missions ») : **Toutes / Actives /
Inactives / Terminées**, dans le bloc minuscule de `combined_fr.txt` (dernière entrée gagne).

**Faux négatif du run précédent** : il a décodé `0x1F5609F` et vu encore « All », donc conclu
« intraduisible, 3/4 seulement » et n'a jamais complété le ticket. En réalité l'entrée était
`too_long` → le build l'a **relogée en free-space et repointée** (`0x1EBE978` → 0xD10C1D
= « Tous »). L'offset original garde les octets EN périmés ; seul le **pointeur vivant** dit
la vérité. Cf. [[unbound-trace-live-pointer-not-original-offset]].

Pointeurs vivants à décoder pour vérifier : All←`0x1EBE978` ; Active←`0x1EBFFC8` **et**
`0x1FB40B8` (deux sites, les deux repointés) ; Inactive←`0x1FB40B4` ; Completed←`0x1FB40C0`.

Autre piège rencontré : la chaîne de build listée dans le skill (`apply_combined_fr --extend`
puis `09_csv_to_json_v2.py`) a produit un JSON **vide** (source_csv = template périmé) qui
aurait empoisonné `make build-fr` (il prend le `*_translation_ready.json` le plus récent).
Le bon générateur = `make prepare-fr` (JSON direct depuis combined_fr.txt), cf.
[[unbound-prepare-fr-bypasses-csv-step]]. Supprimer le JSON vide avant de rebuild.
