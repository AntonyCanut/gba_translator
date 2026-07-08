# Save fixtures

## Missing: `pre-multi-battle-daherapolis.srm` (issue #75 follow-up)

No fixture exists yet for a genuine BATTLE_TYPE_MULTI fight (player + AI
partner vs two trainers at once), needed to test whether Unbound's "ENEMY
TEAM"/"YOUR TEAM" graphic (GitHub issue #75) renders in place of CFRU's
dynamic `gText_TeamPreviewMultiText` two-trainer-name overlay. Unbound's only
Multi Battles live in Daherapolis' postgame facilities — Tour de Combat
("Salle Multi", `combined_fr.txt` offsets `0x1F8F690`-`0x1F9419A`) and Cirque
de Combat (`0x1F8A917`-`0x1F8ADD8`) — both requiring the player to talk to the
facility guide, then pick/link a partner in a "Salon de Combat" before the
fight starts. This is reached only after substantial story progress; no
existing save/savestate in this repo is anywhere close (all are early/mid-game
— see below), and this codebase has no debug menu, warp tool, or safe
save/flag editor (the only `writeMemory()` cheat, an HP-pin auto-win in
`scripts/repro_give_cs.mts`, is documented below as unsafe and must not be
repurposed to fake progress flags).

**To unblock**: obtain a save/savestate positioned right before entering the
Salle Multi (partner already chosen), drop it in here as
`pre-multi-battle-daherapolis.srm`, then run
`scripts/probe_enemy_team_multi_battle.mts`. The probe is now runnable-on-arrival:
its only truly fixture-specific step — the button path from where the save
drops the player up to the first Multi Battle turn — is supplied at runtime as
DATA, not code, via either `$MULTI_WALK` or a `pre-multi-battle-daherapolis.walk.txt`
sidecar next to the save (syntax: `KEY [repeat] [holdFrames] [advanceFrames]`
per line, `#` comments, `;`/newline separators — see the probe's file header).
If the save is already parked on the first Multi Battle turn, no walk data is
needed. Everything else (Team Preview option setup, L-before-A overlay sweep,
VRAM/palette dump) is proven working by `probe_enemy_team_preview.mts`. See
memory `unbound-enemy-team-not-cfru-teampreview.md` for the full investigation
history.

## `post-zeph-pre-cs.srm`

Battery save supplied with the ticket **"Problème pas de gain d'objet"**
(byte-identical to the `.srm` the user attached on the reopen). The filename is
a **misnomer kept for back-compat**: measured in mGBA, this save actually sits
**before** the Zeph battle, not after it (see *Where this save really is* below).

### The reported problem
After beating the boss **Zeph** the player is kidnapped by Team Shadow, escapes
through a portal, and a hillbilly NPC hands over a **CS (HM)**. The player
reports a **FREEZE** (not a reset): the box **"Alors, prends cette CS pour aller
le voir."** (dialogue `0x1F3316D`) stays on screen and the dialogue window never
closes. Screenshot on the ticket.

### Where this save really is (measured in mGBA, no cheats)
Booting this `.srm` on `output/roms/GenedRom-fr.gba` and pressing Continue spawns
the player at map `0.0` in the Frozen Forest. Walking **down** ("suis le chemin
vers la forêt"):

1. triggers the kidnapping cut-scene (map `6.12`),
2. then a **double battle** vs Zeph — lead-select shows the player's
   Carmache / Hélionceau / Nodulithe (Lv25) against Grelaçon / Fantominus /
   Hariyama (Lv23-25).

The give-CS NPC is reachable **only by winning that RNG double battle**. That is
the blocker that has kept this ticket open across many runs — the gift cannot be
driven headlessly to completion, and a scripted blind playthrough is not
deterministic enough for CI. It is **not** evidence the build is broken.

> ⚠️ A freeze never invalidates `gSaveBlock1Ptr`, and this Unbound build's RAM
> state flags are unreliable (`textActive` @`0x020375c0` reads false on an open
> box; **writing** `gBattleMons[0].hp` corrupts RAM into a black screen). So
> "game stays alive" from a reset-detector is **not** proof a box advanced, and
> the old HP-pin / move-select cheat recipe is unsafe — do not use it.

### Why the give-CS data is provably not the cause
Static analysis (re-verified independently this run, on all three FR artifacts)
shows that **every byte the engine touches on the gift path is byte-identical to
the English ROM** apart from the intentionally translated dialogue strings:

* the event-script bytecode `loadword 0x1F3316D → callstd MSGBOX →
  setorcopyvar 0x8000=0x01B5 → setorcopyvar 0x8001=1 → callstd 0` — the only
  FR/EN diffs in the whole script are 3 relocated msgbox pointer operands;
* the granted item `0x01B5`'s whole 44-byte struct (static name "TM112", no
  runtime move-table lookup);
* the box `0x1F3316D` itself (in place, 460 of 484 bytes, `0xFF`-terminated,
  control codes well-formed) and the 3 build-relocated boxes (`0x73F75F`,
  `0x73FB20`, `0x73FDC6` — all terminated, well-formed).

English does not freeze here, so a byte-identical FR build cannot either.
**Crucially, the user's own screenshot shows the box rendering the full, cleanly
accented French text ending exactly at "…le voir."** — a corrupt/runaway box
would paint garbage *past* that point. So the user's ROM's give-CS box is itself
intact; the freeze is not corrupt give-CS text.

### What to actually do
Run, on the ROM file you are **playing** (the `.gba` itself, not this save):

```
python3 scripts/verify_user_rom_givecs.py <your_rom.gba>
```

It prints the SHA-256 **and decodes/shows the give-CS box exactly as your ROM
stores it**, then reports CLEAN vs DIVERGENT.
* CLEAN → your ROM's gift path matches the known-good build; a persisting freeze
  is then an emulator/input issue (try a fresh copy of the current ROM or a
  different emulator such as desktop mGBA), not the translation.
* DIVERGENT → it points at the exact corrupt byte; rebuild with `make build-fr`
  or re-download the current patch.

### CI guards (deterministic, hold)
* `tests/e2e/fr/test_object_gain_sequence.py` — 42 assertions pinning the whole
  gift path (strings, giveitem bytecode, msgbox pointers incl. relocated, item
  struct) byte-identical to English. Verified red on each injected corruption.
* `tests/e2e-playwright/specs/object-gain-forget-sequence.spec.ts` — reads the
  same strings from the ROM and checks the expected French decode.
