# Guide: Utiliser les Scripts d'Investigation

**Documentation des scripts d'analyse des 11 cas d'échec**

---

## 📍 Localisation

```
src/analyzers/
├── 03_binary_comparison.py    # Comparaison binaire
├── 04_offset_analysis.py      # Analyse structurelle
├── 05_pattern_recognition.py  # Reconnaissance patterns
└── 09_failure_analysis_report.py # Rapport final
```

---

## 🚀 Utilisation Rapide

### Option 1: Via Makefile (RECOMMANDÉ)

```bash
# Lancer toute l'investigation
make investigate

# Cela exécute les 4 scripts dans l'ordre et produit:
# - Comparaison binaire
# - Analyse structurelle
# - Reconnaissance de patterns
# - Rapport final
```

### Option 2: Scripts Individuels

```bash
# Analyse binaire (byte-by-byte)
python3 src/analyzers/03_binary_comparison.py

# Analyse structurelle (longueurs, terminateurs)
python3 src/analyzers/04_offset_analysis.py

# Reconnaissance patterns (byte mappings)
python3 src/analyzers/05_pattern_recognition.py

# Rapport final
python3 src/analyzers/09_failure_analysis_report.py
```

---

## 📊 Ce Que Produit Chaque Script

### 03_binary_comparison.py

**Objectif:** Comparer les données binaires EN vs ES

**Sortie:**
```
Offset 0x00A44125
  Catégorie: overflow_7_10
  EN: ...a7 00 ea...
  ES: ...a7 00 ea...
  → 31 bytes différents / 116
  ✅ Terminateur: +1 bytes (SUBSTITUTION IN-PLACE)
```

**Interprétation:**
- Affiche l'hexadécimal autour de chaque offset
- Compte les différences
- Détecte substitution vs relocalisation

---

### 04_offset_analysis.py

**Objectif:** Classifier les 11 cas

**Sortie:**
```
RÉSULTATS:
   Substitutions directes (in-place): 8
   Relocalisations (déplacées): 3

SUBSTITUTIONS DIRECTES:
1. 0x00A44125 (1 bytes)
2. 0x00B1F842 (50 bytes)
...

RELOCALISATIONS:
1. 0x00B1E2CE
   EN length: 18 → ES length: 30
```

**Interprétation:**
- Groupe les cas par stratégie
- Montre les longueurs (identiques = substitution)
- Identifie les relocalisations probables

---

### 05_pattern_recognition.py

**Objectif:** Trouver les patterns d'encodage

**Sortie:**
```
Analysant 7 substitutions directes:

RÉSULTATS:
   Total mappings uniques: 11

Top 20 des byte-mappings les plus fréquents:
  ✅ 0x66 → 0x66  (19x)
  ✅ 0xBB → 0xBB  (12x)
  ✅ 0x33 → 0x33  (8x)
  ...

OCCURENCES DE BYTES CLÉS:
📈 0x66: EN=167,920, ES=168,214 (Δ = +294)
📈 0x17: EN=78,897, ES=82,860 (Δ = +3,963)  ← ANOMALIE!
```

**Interprétation:**
- Cherche les mappings byte-by-byte
- Détecte XOR constants ou patterns récurrents
- Byte 0x17 avec +3,963 = ROM espagnole ajoute du contenu

---

### 09_failure_analysis_report.py

**Objectif:** Rapport final consolidé

**Sortie:**
```
Rapport final d'investigation avec:
- Résumé des résultats (99.9% succès)
- Les 2 stratégies identifiées
- Découvertes clés (byte 0x17, etc.)
- Conclusions sur le reverse engineering
- Prochaines étapes possibles
```

---

## 🔍 Interprétation des Résultats

### Pattern 1: Bytes Identiques

```
✅ 0x66 → 0x66 (19x) - Identique
```

**Interprétation:**
- Ce byte ne change jamais
- Peut être un code/marqueur
- Ou simplement du padding identique

### Pattern 2: Bytes Différents

```
⚠️ 0x77 → 0x11 (1x) - CONVERTI
```

**Interprétation:**
- Transformation spéciale
- Peut indiquer une table de conversion
- Localisée/spécifique

### Pattern 3: Anomalie 0x17

```
📈 0x17: EN=78,897, ES=82,860 (Δ = +3,963)
```

**Interprétation:**
- ROM espagnole ajoute 3,963 bytes de 0x17
- Peut être du nouveau contenu ou padding structurel
- Indique une modification importante

---

## 💡 Cas d'Usage

### Situation 1: "Pourquoi ces 11 offsets échouent?"

```bash
make investigate
```

Lira les 4 scripts et donnera une réponse complète.

---

### Situation 2: "Je veux voir les données binaires exactes"

```bash
python3 src/analyzers/03_binary_comparison.py
```

Affichera l'hexadécimal pour chaque offset.

---

### Situation 3: "Y a-t-il un pattern d'encodage?"

```bash
python3 src/analyzers/05_pattern_recognition.py
```

Affichera les byte mappings et patterns.

---

### Situation 4: "Comment la ROM espagnole gère-t-elle ces cas?"

```bash
python3 src/analyzers/04_offset_analysis.py
```

Classifiera entre substitution et relocalisation.

---

## 📈 Métriques Clés à Retenir

| Métrique | Valeur |
|----------|--------|
| Taux de succès global | 99.9% |
| Substitutions directes | 8/11 |
| Relocalisations | 3/11 |
| Bytes-codes identiques | 66, BB, 33, AA, 70, 88 |
| Anomalie majeure | Byte 0x17 (+3,963) |
| Textes valides testés | 11,508 |

---

## 🚀 Extension Future

Ces scripts peuvent être étendus pour:

1. **Localiser les pointeurs** référençant ces offsets
2. **Analyser les tables de relocalisation** complètes
3. **Mapper les zones de débordement** dans la ROM
4. **Reproduire le système de substitution** de la ROM espagnole

---

## ✨ Conclusion

Ces 4 scripts automatisent l'investigation des 11 cas d'échec et permettent:
- ✅ Comprendre le fonctionnement de la ROM espagnole
- ✅ Valider notre système de détection
- ✅ Documenter les stratégies de traduction
- ✅ Préparer l'étape suivante du reverse engineering

**Utilisez `make investigate` pour une analyse complète!**
