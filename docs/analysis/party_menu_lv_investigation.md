# Party-menu « Lv » → « N. » — investigation (issue #48 / B-234 / F-113)

**Statut : RÉSOLU (nature du « Lv » établie par trace d'exécution mGBA).**
Le « Lv » de la liste d'équipe **n'est PAS du texte** rendu par une police : c'est
un **graphique** cuit dans le template de la boîte Pokémon, exactement comme le
label « PV » (déjà traité par `languages/fr/patches/hp_labels.py`). L'hypothèse
« police FRLG non-compressée » de F-113 est **réfutée** ; la prémisse d'origine de
B-234 (label graphique comme HP/PV) est **confirmée**. Voir la section
« RÉSOLUTION » (bas du fichier) pour la preuve par watchpoint et le pipeline exact.

> Note historique : la section immédiatement ci-dessous (« source NON localisée »)
> date de la première passe B-234, avant que l'infra watchpoint mGBA n'existe.
> Conservée pour la trace des pistes statiques éliminées ; conclusion corrigée par
> la RÉSOLUTION.

---

**(historique) Statut : source NON localisée.** Toutes les pistes statiques testables ont été
éliminées empiriquement (voir ci-dessous). La correction finale demande de
localiser la police FRLG *non-compressée* utilisée par l'écran d'équipe, ce qui
nécessite un trace d'exécution (watchpoint mGBA) ou la table `gFonts` désassemblée.

## Le symptôme

Menu START → Pokémon (liste équipe) : le niveau s'affiche « Lv10 » (ex.
« Lv18 »/« Lv15 » dans les captures de l'issue). Le « Lv » est collé au nombre,
même police blanche/ombre grise que les chiffres du niveau et des PV. Objectif :
« N.10 » (abréviation française de « Niveau »).

Décomposition pixel à l'écran (dump VRAM BG, savestate `output/roms/GenedRom-fr.ss2`,
Pokémon Embrylex Lv10) : « L » majuscule 7px de haut + « v » minuscule 4px, puis
les chiffres « 10 » — c.-à-d. du **texte** rendu glyphe par glyphe, composité au
runtime dans les tuiles-fenêtre du BG0 (screenblock 31, tuiles ~0x8d/0x9b/0x9c).
Le fond de carte (barre PV, label PV) est un tileset LZ77 séparé (bloc 0x8001D0,
déjà géré par `languages/fr/patches/hp_labels.py`).

## Ce que « Lv » n'est PAS (résultats négatifs vérifiés)

1. **Pas une chaîne CFRU pointée.** Scan inverse de tous les pointeurs alignés du
   ROM FR vers une cible commençant par `C6 EA` (« Lv ») : seulement **3** chaînes
   « Lv* » dans tout le ROM — `0x4160F4` « Lv. » (en-tête Panthéon/Résumé, 2
   pointeurs) et `0x10C182D` « Lv »+code. **Aucune ne touche le code de l'écran
   d'équipe** (patch de la chaîne 0x4160F4 → « N. » : aucun effet sur la liste,
   vérifié en jeu).
2. **Pas le glyphe-ligature `{LV}` (0x34) des polices principales.** Blanchi dans
   les 7 blocs `find_font_blocks` + tous les blocs LZ77 taille-police (0x2000) :
   aucun effet. Le glyphe 0x34 ne rend d'ailleurs pas « Lv » dans ces polices.
3. **Pas les glyphes texte `L`(0xC6)/`v`(0xEA) ni les chiffres `0`(0xA1)/`1`(0xA2)
   des polices détectées.** Blanchis dans les 7 polices principales ET dans les
   ~49 blocs LZ77 de 0x2000 octets : « Lv10 » **et** « 30/ 30 » **et** le nom
   « Embrylex » restent inchangés. ⇒ l'écran d'équipe rend son texte depuis une
   police que `find_font_blocks` ne détecte pas.
4. **Pas une tuile LZ77 ni brute alignée.** Recherche exhaustive de la forme
   « Lv » (et du glyphe `0`) dans chaque tuile de chaque bloc LZ77 décompressé et
   dans le ROM brut 4bpp aligné : 0 correspondance.
5. **Pas construit dans un `gStringVar` au runtime.** Scan EWRAM (0x02000000,
   256 Ko) + IWRAM au moment de l'écran d'équipe : aucune chaîne « Lv » (`C6 EA`).
6. **Pas les 4 polices non-compressées adjacentes aux tables de largeur**
   (`0x1FB100/0x207300/0x217618/0x227930`, cf. `font.py:WIDTH_TABLE_OFFSETS`) :
   blanchi 0x4000 octets de données-glyphes avant chaque table → aucun effet.

## Ce qui est PROUVÉ

- L'écran d'équipe **re-rend** à chaque ouverture (fermer→rouvrir repart de
  l'overworld puis redessine), donc une édition de la *vraie* source apparaîtrait
  dans le probe.
- Le probe **reflète bien** les éditions ROM des graphiques chargés à l'ouverture :
  patcher le tileset de carte 0x8001D0 change visiblement la carte, « Lv10 »
  restant dessiné par-dessus (⇒ le texte vient d'un chemin séparé).
- Conclusion : le texte de l'écran d'équipe (Lv, chiffres, nom) provient d'une
  **police FRLG stockée non-compressée** (tableaux `sFontXxxLatinGlyphs`, lus
  directement par le moteur de texte), à un emplacement non encore identifié dans
  ce ROM Unbound. Aucune des polices LZ77 connues n'est utilisée par cet écran.

## Méthode de reproduction (harnais validé)

Boucle « modifier le ROM → vérifier en jeu » qui fonctionne :

```bash
npm i -D tsx   # requis pour lancer les probes .mts
# 1. patcher une copie du ROM (ex. /tmp/x.gba)
# 2. IMPORTANT : copier la savestate sous le MÊME basename que le ROM
cp output/roms/GenedRom-fr.ss2 /tmp/x.ss2
# 3. probe (slot 2 = overworld avec Pokémon, navigue START→Pokémon)
MGBA_PATH=/opt/homebrew/bin/mgba npx tsx scripts/probe_party_menu.mts /tmp/x.gba /tmp/out.png
```

Piège majeur : `loadStateSlot(2)` cherche `<basename-du-rom>.ss2`. Sans la
savestate copiée à côté du ROM modifié, le jeu démarre à froid → écran blanc
(faux négatif). C'est la cause des « écrans blancs » lors des premières tentatives.

## Prochaine étape recommandée

Localiser la police non-compressée via l'une de :

1. **Trace d'exécution mGBA** : poser un watchpoint d'écriture sur la tuile-fenêtre
   BG0 qui reçoit « Lv » (VRAM 0x06000000 + tile*0x20) pendant l'ouverture du menu,
   remonter au `ldr` de la police source. Demande d'étendre `emulator-web/src/lua/bridge.lua`
   avec le support debugger/watchpoint de mGBA 0.11.
2. **Table `gFonts`** : retrouver la structure `struct Font`/`sFontXxxLatinGlyphs`
   dans ce ROM (désassemblage), en déduire l'adresse des glyphes de la police
   « narrow » de l'écran d'équipe.

Une fois la police trouvée : vérifier si « Lv » y est un glyphe-ligature unique
(⇒ éditer ce seul glyphe en « N. », correction propre couvrant tous les écrans) ou
deux glyphes `L`+`v` (⇒ pas d'édition de police possible sans casser tout `L`/`v` ;
il faudra alors intercepter/repointer la chaîne de niveau côté code).

---

# RÉSOLUTION (F-113) — le « Lv » est un GRAPHIQUE, pas une police

Le trace d'exécution mGBA (piste 1 ci-dessus) a été implémenté et exécuté. Il
tranche : **aucune police ne rend « Lv »**. Le niveau affiché « Lv10 » est en fait
**un graphique « Lv » (template de la boîte) + un nombre « 10 » en texte**.

## Infra ajoutée

`emulator-web/src/lua/bridge.lua` gagne le support debugger de mGBA ≥ 0.11 :
commandes `WATCHPOINT` (write/read/change, simple + range), `BREAKPOINT`,
`CLEARBP`, `WATCHHITS`, `CLEARHITS`, `CAP`. Chaque hit capture tout le fichier de
registres ARM (r0-r15, cpsr) + l'accès (addr/old/new/type). Côté client
(`emulator-web/src/mgba-bridge.ts`) : `setWatchpoint/setRangeWatchpoint/`
`setBreakpoint/clearBreakpoint/drainWatchHits/clearWatchHits/capabilities`.
Sondes : `scripts/probe_party_lv_trace.mts` (read-watch des tables de largeur),
`probe_party_vram_dump.mts`, `probe_party_lv_source.mts` (write-watch VRAM→EWRAM),
`probe_party_lv_blit.mts` (breakpoint du blit de fenêtre).

## Preuve

1. **Trace read-watch sur les 11 tables de largeur de polices** (font.py
   `WIDTH_TABLE_OFFSETS` + la famille « small » découverte par scan des literal
   pools : glyph_base + 0x8000 = width_table, stride 0x40/glyphe). Pendant
   l'ouverture START→Pokémon, chaque glyphe dessiné lit sa table de largeur. On
   décode la séquence de glyphes par police (charmap) :
   - `font@1FB100` → `Pokémon` (menu START) + horloge
   - `font@207300` → `Choisis Pokémon ou Annuler.` (invite bas d'écran)
   - **`font@1EEF00` → `Embrylex` `10` `♀` ` 30/` `/ 30` `Annuler`**
   La police `1EEF00` rend donc **le nombre de niveau « 10 »**, les PV « 30/ 30 »,
   le surnom et le bouton. **Aucune** police ne lit les codepoints `L`(0xC6)/
   `v`(0xEA) : **« Lv » (et « PV ») ne sont dessinés par aucune police.**
2. **Write-watch VRAM** sur les tuiles BG0 qui portent « Lv » (charbase 0, tuiles
   0x8D/0x8E/0x9B/0x9C) : les pixels arrivent par copie depuis le tampon-fenêtre
   EWRAM `0x2001c00`. Le fond dégradé de la boîte y est décompressé (SVC 0x11
   LZ77) depuis `0x08B1BCE8` — ce bloc ne contient QUE le dégradé (motif de bandes
   uniforme, pas de lettres). Le texte (« 10 »/« Embrylex »/…) est ensuite tracé
   par-dessus par le plotter de fenêtre `0x08004c5e` (via `0x08004aa4`), et le
   template de boîte est blit par `0x08004aa4` call #0 depuis une source ROM
   (`r4=0x083D0070`). **« Lv » fait partie de ce template graphique, pas d'un
   glyphe de police.**

Conclusion : « Lv » se comporte **exactement** comme « PV » (label graphique cuit
dans le template de boîte, cf. `hp_labels.py` qui a converti HP→PV dans le bloc
`0x008001D0`). « PV » n'était pas dans `0x008001D0` avec des tuiles `L`/`v`
séparables → « Lv » vit dans le template de boîte Unbound custom (blit `0x8004aa4`
call #0, source ROM ≈ `0x083D0070`), et non dans une police.

## Correction recommandée (nouveau ticket)

Traiter « Lv »→« N. » **comme un graphique**, sur le modèle de `hp_labels.py` :
localiser précisément les tuiles « L »+« v » dans le template de boîte Pokémon
(blit `0x8004aa4` call #0 ; commencer par la source ROM `0x083D0070` et le bloc
voisin de `0x008001D0`/`0x08B1BCE8`), les redessiner en « N. » (validation stricte
des octets connus + recompression in-place), l'ajouter à la chaîne `build-fr`
après `repair_*`, puis vérifier en jeu avec `probe_party_menu.mts`.
**Ne PAS** chercher/éditer une police : la piste police est close.
