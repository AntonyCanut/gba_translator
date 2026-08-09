# Nickname Prompt Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Afficher `Surnom de <Pokémon> ?` sur l’écran de saisie du surnom.

**Architecture:** Un patch FR post-build remplace la seule routine Thumb qui concatène le nom d’espèce et le titre. La traduction canonique fournit le préfixe, tandis que la routine ajoute le nom dynamique et le suffixe français.

**Tech Stack:** Python 3.11+, pytest, Unicorn ARM/Thumb, pipeline ROM Gen III.

## Global Constraints

- Modifier seulement la dernière entrée active de `languages/fr/combined_fr.txt`.
- Exécuter `apply_combined_fr.py --extend`, la conversion JSON, puis `make build-fr`.
- Vérifier les octets décodés de `output/roms/GenedRom-fr.gba`.
- Ne jamais publier avec `git push`.

---

### Task 1: Garde rouge de composition

**Files:**
- Create: `tests/test_patch_nickname_prompt_fr.py`
- Modify: `languages/fr/protected_entries.yaml`

**Interfaces:**
- Consumes: routine anglaise `DrawMonTextEntryBox` à `0x9F4F0`.
- Produces: assertions sur `Surnom de Wattouat ?` et le terminateur `0xFF`.

- [ ] **Step 1: Write the failing test** — exécuter la routine attendue sous Unicorn et protéger l’entrée `0x418E5C`.
- [ ] **Step 2: Run test to verify it fails** — `python3 -m pytest tests/test_patch_nickname_prompt_fr.py tests/unit/test_translation_integrity.py -q` doit échouer car le patch et le préfixe n’existent pas.

### Task 2: Correctif minimal

**Files:**
- Create: `languages/fr/patches/nickname_prompt.py`
- Modify: `languages/fr/combined_fr.txt`
- Modify: `languages/fr/lang.yaml`
- Modify: `Makefile`

**Interfaces:**
- Consumes: `StringCopy` (`0x08008D84`), table d’espèces (`0x0966A98C`) et structure de l’écran.
- Produces: une routine Thumb byte-exacte et idempotente appliquée au build FR.

- [ ] **Step 1: Write minimal implementation** — composer préfixe, espèce, espace, point d’interrogation et `0xFF`, puis conserver les appels de rendu originaux.
- [ ] **Step 2: Run test to verify it passes** — relancer les tests ciblés.
- [ ] **Step 3: Commit source before build** — commit `fix(fr): reformuler le titre du surnom` après contrôle du diff.

### Task 3: Livraison et preuve ROM

**Files:**
- Modify generated artifacts only under `output/` (gitignored).

**Interfaces:**
- Consumes: source FR et patch post-build commités.
- Produces: ROM jouable dont le titre décodé respecte l’ordre demandé.

- [ ] **Step 1: Build** — exécuter la chaîne FR complète avec `--extend`.
- [ ] **Step 2: Verify ROM** — exécuter la routine patchée sur la ROM construite et décoder le tampon final.
- [ ] **Step 3: Verify regression suite** — exécuter les tests ciblés puis `make test`.
- [ ] **Step 4: Document review** — compléter `tasks/todo.md`, relire le diff et intégrer localement.
