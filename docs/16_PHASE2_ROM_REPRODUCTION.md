# 🎯 PHASE 2: ROM Reproduction & Validation

**Date:** 14 janvier 2026  
**Objectif:** Reproduire la ROM espagnole à partir de la ROM anglaise + textes espagnols extraits

---

## 📋 Architecture

### Étape 1: Reproduction de la ROM espagnole

**Script:** `src/translators/11_reproduce_spanish_rom.py`

**Process:**
1. Charger la ROM anglaise (`input/roms/englishrom.gba`)
2. Charger les textes espagnols extraits (`output/extracted/extracted_texts/spanishrom_texts.json`)
3. Charger les textes anglais extraits (`output/extracted/extracted_texts/englishrom_texts.json`)
4. Pour chaque texte espagnol:
   - Vérifier qu'il est valide (pas corrompu)
   - Si identique au texte anglais → ne pas modifier
   - Sinon → réinsérer à l'offset original
5. Sauvegarder la ROM modifiée

**Output:**
- `output/roms/YYYY-MM-DD_spanishrom_reproduction.gba` - ROM reproduite
- `output/reports/YYYY-MM-DD_spanish_reproduction_report.json` - Rapport détaillé

### Étape 2: Validation de l'intégrité

**Script:** `src/translators/12_validate_reproduced_rom.py`

**Vérifications:**
1. ✅ ROM existe et est accessible
2. ✅ Taille correcte (doit correspondre à la ROM de référence)
3. ✅ En-tête valide
4. ✅ Textes extraits et comparables
5. ✅ Taux de modification cohérent

**Output:**
- `output/reports/YYYY-MM-DD_validation_reproduced_rom.json` - Résultats validation

---

## 🚀 Utilisation

### Commande Rapide

```bash
# Reproduire + Valider (pipeline complet)
make test-reproduction

# Ou individuellement:
make reproduce-es         # Seulement reproduction
make validate-reproduced  # Seulement validation
```

### Détaillé

```bash
# Étape 1: Reproduire la ROM
python3 src/translators/11_reproduce_spanish_rom.py

# Étape 2: Valider la ROM reproduite
python3 src/translators/12_validate_reproduced_rom.py

# Optionnel: Valider une ROM spécifique
python3 src/translators/12_validate_reproduced_rom.py output/roms/2026-01-14_spanishrom_reproduction.gba
```

---

## 📊 Résultats Attendus

### ROM Reproduite
```json
{
  "timestamp": "2026-01-14T...",
  "statistics": {
    "total_texts_to_insert": 11508,
    "successfully_inserted": ~11497,
    "failed_insertions": ~11,
    "unchanged_texts": ~2000,
    "corrupted_spanish_texts": ~2928,
    "success_rate": "99.9%"
  }
}
```

### Validation
```json
{
  "rom_exists": true,
  "rom_size_valid": true,
  "texts_extracted": true,
  "text_comparison": {
    "total": 11508,
    "identical": ~2000,
    "different": ~9508,
    "mismatch_rate": 82.6%
  },
  "integrity_checks": {
    "header_valid": true,
    "size_matches_reference": true,
    "all_texts_readable": true
  }
}
```

---

## ✨ Ce Que Cela Prouve

### ✅ Système Fonctionnel

Si la ROM reproduite est valide, cela signifie:
1. **Extraction correcte** → Les textes ont été extraits fidèlement
2. **Réinsertion correcte** → On peut réinsérer correctement dans la ROM
3. **Structure préservée** → La ROM reste fonctionnelle

### ✅ Méthode Validée

Ce processus valide notre approche pour:
- **Traduction en français** → Remplacer textes anglais par textes français
- **Autres langues** → Utiliser la même méthode pour d'autres traductions
- **ROM modding** → Base solide pour d'autres modifications

---

## 🔄 Prochaine Étape: Traduction en Français

Une fois la ROM espagnole reproduite avec succès:

1. **Préparer les traductions:**
   ```bash
   make extract           # Extraire textes anglais
   make compare           # Voir les différences
   # Éditer les traductions en JSON/CSV
   ```

2. **Réinsérer traductions:**
   ```bash
   python3 src/translators/11_reproduce_spanish_rom.py  # Template
   # Adapter pour utiliser les traductions françaises
   ```

3. **Créer ROM française:**
   ```
   output/roms/YYYY-MM-DD_frenchrom.gba
   ```

---

## 🔍 Diagnostic

### Si Reproduction Échoue

**Vérifier:**
1. ROM anglaise présente: `input/roms/englishrom.gba` ✓
2. Textes extraits: `output/extracted/extracted_texts/spanishrom_texts.json` ✓
3. Taille ROM: ~16 MB ✓
4. Textes valides: Nombre > 0 ✓

**Commande de diagnostic:**
```bash
# Voir les logs détaillés
python3 src/translators/11_reproduce_spanish_rom.py 2>&1 | tee debug.log
```

### Si Validation Échoue

**Vérifier:**
1. ROM reproduite existe: `output/roms/*_spanishrom_reproduction.gba`
2. Taille correcte (≈16 MB)
3. En-tête valide

**Vérification manuelle:**
```bash
ls -lh output/roms/*_spanishrom_reproduction.gba
file output/roms/*_spanishrom_reproduction.gba
```

---

## 📈 Métriques de Succès

| Métrique | Seuil | Status |
|----------|-------|--------|
| **Texts inserted** | > 90% | ✅ |
| **ROM size valid** | ±1% | ✅ |
| **Header valid** | ✓ | ✅ |
| **Validation pass** | ✓ | ✅ |

---

## 🎓 Ce Qu'On Apprend

Si cette phase fonctionne:
- ✅ Notre code de réinsertion est **correct**
- ✅ La ROM anglaise est **modifiable**
- ✅ On peut créer des **ROM modifiées stables**
- ✅ La méthode est **reproductible** pour d'autres langues

---

## 📌 Notes Importantes

1. **Pas de modification de donnée**
   - On réinsère simplement les textes tels quels
   - Aucune traduction, aucune modification
   - But: Valider le système technique

2. **Textes inchangés**
   - Si texte espagnol = texte anglais → pas de modification
   - Réduit les risques d'erreur
   - Économise du temps traitement

3. **Corruption filtrée**
   - Les textes corrompus sont ignorés
   - Réduit les risques de ROM corrompue
   - Plus sûr pour la validation

---

## 🚀 Commencez!

```bash
# Tout d'un coup
make test-reproduction

# Ou pas à pas
make reproduce-es
make validate-reproduced
```

**Résultats dans:** `output/roms/` et `output/reports/`

---

**Bonne chance! 🎉**
