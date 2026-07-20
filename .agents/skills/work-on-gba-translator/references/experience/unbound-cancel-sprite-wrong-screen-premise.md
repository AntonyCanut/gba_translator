---
name: unbound-cancel-sprite-wrong-screen-premise
description: "RESOLU — Cancel/ANNUL (F-108→F-111) n'etait pas un sprite du tout, voir [[unbound-cancel-button-was-text-not-sprite]] pour la resolution finale"
metadata:
  node_type: memory
  type: project
  originSessionId: 374802a1-d0b5-4e4d-905b-8fa62767fbee
---

**RÉSOLU dans F-110** — voir [[unbound-cancel-button-was-text-not-sprite]] pour le détail complet. Résumé : "CANCEL" n'était pas un sprite, c'était du texte CFRU normal (`"DEL. ALL<FC:1357>CANCEL<FC:13A4>OK"` à 0x41ee2b) déjà traduit dans `combined_fr.txt` mais jamais rebuild dans la ROM. Trouvé en encodant "CANCEL" via `src.text.encoder.encode_string` et un `rom.find` direct — pas besoin de connaître l'écran ni de sonder mGBA. `make prepare-fr && make build-fr` (gba_translator) a suffi. Tout est mergé sur `unbound`.

---

Historique conservé ci-dessous (contexte de l'investigation, plus périmé sur "que faire ensuite") :

Les tickets F-108/F-109/F-110 ont tous buté sur la MÊME fausse prémisse : que Cancel
vivait sur le clavier de nommage / l'écran de surnom Pokémon, d'où plusieurs sessions
de navigation mGBA à l'aveugle (coincé dans l'entrepôt map 4.10).

F-111 avait déjà écarté cette hypothèse par analyse statique : les trois BMP de F-108
sont TROIS écrans sans rapport (`Selection`=clavier de nommage, trouvé F-109
@0x00E985D8 ; `Afflictions`=status_badges de combat ; `Cancel`=écran inconnu à
l'époque). Rendre la planche complète de 65 tuiles `selection` montre tout son pool
de labels (SELECT/BACK/B BUTTON/OK/START/UPPER/lower/others) — aucun CANCEL dedans.
Les scans statiques (non compressé + tous les blocs LZ77 de 0x800000–0xF00000)
n'avaient rien trouvé non plus — normal, ce n'était pas un sprite à chercher par forme.

Related: [[unbound-mgba-tap-vs-move-and-warehouse-deadend]] [[unbound-type-icons-are-graphics]] [[unbound-cancel-button-was-text-not-sprite]]
