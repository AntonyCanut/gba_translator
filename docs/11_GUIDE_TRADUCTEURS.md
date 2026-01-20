# Guide des Traducteurs - Pokemon FireRed FR

## 🎯 Vue d'ensemble

Bienvenue dans le projet de traduction française de Pokemon FireRed ! Ce guide vous explique comment contribuer à la traduction de **14,436 textes**.

## 📊 Situation actuelle

### Statistiques de padding disponible

L'analyse de la ROM a révélé d'excellentes nouvelles :

- **99.2%** des textes ont du padding disponible
- **Padding moyen : 17.7 bytes** par texte
- **73.5%** des textes ont 1-3 bytes de padding

Cela signifie que vous aurez généralement de la flexibilité pour vos traductions !

### Distribution par catégorie

| Catégorie | Nombre | Pourcentage |
|-----------|--------|-------------|
| Autres | 6,797 | 47.1% |
| Dialogues | 4,853 | 33.6% |
| Descriptions | 1,758 | 12.2% |
| Lieux | 983 | 6.8% |
| Système | 45 | 0.3% |

## 📝 Comment traduire

### Étape 1 : Obtenir le fichier CSV

Le fichier de traduction se trouve dans :
```
output/translation/2026-01-13_translation_template.csv
```

Option pour un CSV trilingue (EN/ES/FR) avec contexte espagnol :
```
python src/translators/28_export_trilingual_csv.py
```
Cela génère un fichier du type `output/translation/YYYY-MM-DD_trilingual_translation.csv`.

### Étape 2 : Ouvrir dans votre éditeur préféré

Vous pouvez utiliser :
- **Microsoft Excel**
- **Google Sheets** (recommandé pour collaboration)
- **LibreOffice Calc**
- Tout éditeur CSV

### Étape 3 : Comprendre les colonnes

| Colonne | Description |
|---------|-------------|
| `offset` | Position dans la ROM (technique, ne pas modifier) |
| `original_text` | **Texte anglais à traduire** |
| `spanish_text` | Texte espagnol de référence (contexte) |
| `original_length` | Longueur du texte anglais |
| `padding_available` | Bytes de padding disponibles |
| `real_max_length` | **LONGUEUR MAX AUTORISÉE** (original + padding) |
| `encoding` | Type d'encodage (pokemon ou ascii) |
| `category` | Catégorie du texte |
| `translation` | **VOTRE TRADUCTION** ← Remplir ici ! |
| `notes` | Vos commentaires/questions |

### Étape 4 : Règles de traduction

#### ✅ À FAIRE

1. **Respecter la longueur maximale**
   - Votre traduction doit être ≤ `real_max_length`
   - Exemple : Si `real_max_length` = 19, votre traduction peut faire jusqu'à 19 caractères

2. **Utiliser les caractères français**
   - Vous pouvez utiliser : à, è, é, ù, ç
   - Attention : À, È, É sont disponibles mais moins courants

3. **Préserver le sens et le ton**
   - Dialogues : Ton naturel et fluide
   - Descriptions : Précis et informatif
   - Système : Court et clair

4. **Utiliser la colonne `notes`**
   - Pour poser des questions
   - Pour signaler des ambiguïtés
   - Pour suggérer des alternatives

#### ❌ À ÉVITER

1. **Ne pas dépasser `real_max_length`**
   - Le système refusera votre traduction si elle est trop longue
   - Mieux vaut une traduction concise qu'une traduction tronquée !

2. **Ne pas modifier les autres colonnes**
   - Seules `translation` et `notes` doivent être modifiées

3. **Ne pas laisser de lignes vides**
   - Si vous ne savez pas comment traduire, mettez "TODO" dans notes

### Étape 5 : Techniques d'abréviation

Si votre traduction est trop longue, voici des astuces :

#### Abréviations standards

| Anglais | Long | Court |
|---------|------|-------|
| Pokemon | Pokémon | PKM |
| Attack | Attaque | ATQ |
| Defense | Défense | DÉF |
| Experience | Expérience | EXP |
| Hit Points | Points de Vie | PV |

#### Suppressions possibles

- Articles : "Le Centre" → "Centre"
- Mots de liaison : "et puis" → "puis"
- Politesses : "S'il vous plaît" → "SVP"

#### Reformulations

Au lieu de traduire mot à mot, reformulez :
- "I better go, too." → "Je dois partir." (au lieu de "Je ferais mieux d'y aller aussi.")
- "Take care now!" → "Prends soin de toi!" (au lieu de "Fais attention maintenant!")

## 📖 Exemples de traductions

### Exemple 1 : Dialogue simple

```
Original: "Take care now!"
Length: 14
Padding: 5
Max: 19

✅ BON: "Prends soin de toi!" (19 caractères)
✅ BON: "À bientôt!" (11 caractères)
❌ MAUVAIS: "Prends bien soin de toi maintenant!" (35 caractères - trop long!)
```

### Exemple 2 : Nom de lieu

```
Original: "Valley Cave"
Length: 11
Padding: 124
Max: 135

✅ BON: "Grotte de la Vallée" (19 caractères)
✅ BON: "Grotte Vallée" (13 caractères)
```

### Exemple 3 : Question de dialogue

```
Original: "Which move should be forgotten?"
Length: 31
Padding: 1
Max: 32

✅ BON: "Quel talent oublier?" (19 caractères)
✅ BON: "Quelle capacité oublier?" (24 caractères)
❌ MAUVAIS: "Quelle capacité devrait être oubliée?" (38 caractères)
```

## 🎨 Glossaire Pokemon (noms officiels français)

### Lieux
- Pallet Town → Bourg Palette
- Viridian City → Jadielle
- Pewter City → Argenta
- Cerulean City → Azuria

### Objets
- Potion → Potion
- Super Potion → Super Potion
- Hyper Potion → Hyper Potion
- Poké Ball → Poké Ball
- Great Ball → Super Ball
- Ultra Ball → Hyper Ball

### Termes de jeu
- Pokemon Center → Centre Pokémon
- Poké Mart → Boutique Pokémon
- Gym Leader → Champion d'Arène
- Elite Four → Conseil 4
- Champion → Maître

### Stats
- HP (Hit Points) → PV (Points de Vie)
- Attack → Attaque
- Defense → Défense
- Sp. Atk → Atq. Spé
- Sp. Def → Déf. Spé
- Speed → Vitesse

## 🔄 Processus de validation

Une fois vos traductions terminées :

1. **Sauvegarder le CSV**
   - Format UTF-8 avec BOM
   - Conserver le nom du fichier

2. **Exécuter la validation**
   ```bash
   python src/translators/09_csv_to_json.py
   ```

3. **Corriger les erreurs**
   - Le système vous indiquera les traductions trop longues
   - Corrigez-les et relancez la validation

4. **Générer la ROM**
   ```bash
   python src/translators/10_reinsert_smart.py
   ```

## ⚠️ Messages d'erreur courants

### "Trop long: X > Y"

Votre traduction dépasse la longueur maximale.

**Solution** : Raccourcir la traduction ou utiliser des abréviations

### "Traduction manquante"

Vous avez laissé une cellule vide dans la colonne `translation`.

**Solution** : Remplir toutes les cellules ou mettre "TODO" dans notes

## 💡 Conseils pratiques

### Pour les débutants

1. Commencez par les **dialogues simples** (catégorie "dialogue")
2. Utilisez les **noms officiels français** pour les Pokemon et lieux
3. N'hésitez pas à poser des questions dans la colonne `notes`

### Pour les traducteurs avancés

1. Priorisez les **descriptions** (plus techniques)
2. Assurez-vous de la **cohérence terminologique**
3. Vérifiez les **contextes ambigus**

### Organisation du travail

Si vous travaillez en équipe :

1. **Diviser par catégorie**
   - Traducteur A : Dialogues
   - Traducteur B : Descriptions
   - Traducteur C : Lieux et système

2. **Utiliser Google Sheets**
   - Permet la collaboration en temps réel
   - Ajoutez des commentaires pour discussion

3. **Faire des revues croisées**
   - Relire les traductions des autres
   - Signaler les incohérences

## 📞 Besoin d'aide ?

- Consultez [GLOSSARY.md](GLOSSARY.md) pour la terminologie
- Consultez [17_TEXT_VARIABLES.md](17_TEXT_VARIABLES.md) pour les variables `<0x..>`
- Vérifiez [04_TASKS.md](04_TASKS.md) pour le planning global
- Posez vos questions dans la colonne `notes` du CSV

## 🎯 Objectif final

Créer une traduction française naturelle et fidèle de Pokemon FireRed qui respecte :
- Les **contraintes techniques** (longueur)
- Les **noms officiels** français
- L'**esprit du jeu** original

Bonne traduction ! 🎮🇫🇷
