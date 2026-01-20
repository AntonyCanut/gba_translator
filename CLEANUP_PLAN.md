# Plan de Nettoyage - Scripts Obsolètes

## Scripts à Supprimer (Doublons)

Ces scripts ont été remplacés par `src/commands/build_rom.py`:

### À Supprimer
- [ ] `src/translators/15_build_spanish_rom.py` → Remplacé par `build_rom.py --reference`
- [ ] `src/translators/16_build_french_rom.py` → Remplacé par `build_rom.py --translations`
- [ ] `src/translators/17_build_spanish_rom_correct.py` → Obsolète
- [ ] `src/translators/18_build_spanish_rom_simple.py` → Obsolète
- [ ] `src/translators/19_build_translated_rom_generic.py` → Remplacé par `build_rom.py`

### À Conserver (Pour l'instant)
- [x] `src/translators/11_reproduce_spanish_rom.py` → Utile pour tests
- [x] `src/translators/12_validate_reproduced_rom.py` → Utile pour validation
- [x] `src/translators/13_test_spanish_simulation.py` → Tests critiques (100% validation)
- [x] `src/translators/06_detect_padding.py` → Analyse de padding

### Scripts d'Analyse (À Migrer vers src/analyzers/)
- [ ] `src/translators/20_prepare_translation_template.py`
- [ ] `src/translators/21_diagnose_translation_issues.py`
- [ ] `src/translators/22_deep_dive_rom_structure.py`
- [ ] Etc.

## Prochaines Étapes

1. **Créer scripts commands/**
   - [ ] `extract_texts.py` (extraction)
   - [ ] `compare_roms.py` (comparaison)
   - [ ] `validate_rom.py` (validation 100%)

2. **Nettoyer translators/**
   - [ ] Supprimer scripts obsolètes
   - [ ] Déplacer scripts d'analyse vers `analyzers/`

3. **Documentation**
   - [x] `docs/ROM_BUILDING.md`
   - [ ] `docs/TEXT_EXTRACTION.md`
   - [ ] `docs/ROM_VALIDATION.md`

## Commande de Nettoyage (À Exécuter Plus Tard)

```bash
# Supprimer scripts obsolètes
rm src/translators/15_build_spanish_rom.py
rm src/translators/16_build_french_rom.py
rm src/translators/17_build_spanish_rom_correct.py
rm src/translators/18_build_spanish_rom_simple.py
rm src/translators/19_build_translated_rom_generic.py
```

**Note**: Ne pas exécuter maintenant, attendre validation complète du système.
