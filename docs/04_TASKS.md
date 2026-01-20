# Plan de Traduction ROM GBA - Liste des Tâches

## 📋 Vue d'ensemble du projet

**Objectif** : Créer une version française de Pokemon FireRed en partant de la ROM anglaise

**Contraintes** :
- 339,821 textes totaux dans la ROM
- 14,436 textes différents entre versions anglaise/espagnole à traduire
- Limitation d'espace : textes dans des arrays séquentiels
- 576 KB d'espace libre disponible pour relocalisation

---

## Phase 1 : Préparation et Analyse (COMPLÉTÉ ✅)

### 1.1 Extraction des textes ✅
**Temps estimé** : 1 heure
**Outils** : `extract_text.py`

**Détails** :
- [x] Extraire tous les textes de `englishrom.gba`
- [x] Extraire tous les textes de `spanishrom.gba`
- [x] Vérifier l'intégrité des extractions
- [x] Générer fichiers JSON et TXT lisibles

**Résultats** :
- ✅ 339,821 textes anglais extraits
- ✅ 339,716 textes espagnols extraits
- ✅ Fichiers dans `extracted_texts/`

**Commande** :
```bash
make extract
```

---

### 1.2 Comparaison et analyse des différences ✅
**Temps estimé** : 30 minutes
**Outils** : `compare_texts.py`, `extract_english_diff.py`

**Détails** :
- [x] Comparer les deux versions
- [x] Identifier les 25,183 différences
- [x] Filtrer pour obtenir uniquement les textes à traduire
- [x] Réduction de 95.8% du volume

**Résultats** :
- ✅ 3,584 textes modifiés identifiés
- ✅ 14,436 textes anglais aux offsets différents
- ✅ Fichiers dans `differences/`

**Commandes** :
```bash
make compare
make extract-diff
```

---

### 1.3 Analyse de la structure ROM ✅
**Temps estimé** : 2 heures
**Outils** : `analyze_rom_structure.py`

**Détails** :
- [x] Identifier l'espace libre (576 KB trouvés)
- [x] Détecter les tables de pointeurs (500+ tables)
- [x] Comprendre l'organisation des textes
- [x] Analyser comment la version espagnole a géré les textes longs

**Découvertes importantes** :
- ✅ 336 KB d'espace libre continu à 0x015FBC90
- ✅ La version espagnole a relocalisé 792 textes (22% des modifications)
- ✅ Les textes sont majoritairement dans des arrays séquentiels
- ⚠️ Limitation : notre script actuel ne gère que les pointeurs directs

**Commande** :
```bash
make analyze
python3 analyze_rom_structure.py englishrom.gba 0x0018D42A
```

---

## Phase 2 : Stratégie de Traduction (EN COURS 🔄)

### 2.1 Définir la méthodologie de traduction
**Temps estimé** : 1 journée
**Responsable** : Chef de projet traduction

**Décisions à prendre** :

#### A. Approche conservative (RECOMMANDÉ) ⭐
**Avantages** :
- ✅ Fonctionne à 100% avec nos outils actuels
- ✅ Pas de risque de corruption de ROM
- ✅ Workflow simple et rapide

**Contraintes** :
- ❌ Textes français ≤ longueur anglaise
- ❌ Nécessite traductions concises

**Workflow** :
```bash
1. Éditer extracted_texts/englishrom_texts.json
2. Garder textes ≤ longueur originale
3. make reinsert-en
4. Tester sur émulateur
```

**Tâches** :
- [ ] Établir glossaire de termes courts
- [ ] Définir règles d'abréviation
- [ ] Former traducteurs aux contraintes d'espace

---

#### B. Approche avancée (NÉCESSITE DÉVELOPPEMENT)
**Avantages** :
- ✅ Textes français sans limite de longueur
- ✅ Traduction naturelle et fluide

**Contraintes** :
- ⚠️ Nécessite développement supplémentaire
- ⚠️ Plus complexe à tester
- ⚠️ Risque de bugs

**Développements requis** :
- [ ] Implémenter détection de tables de textes
- [ ] Implémenter relocalisation de tables entières
- [ ] Implémenter mise à jour de pointeurs de tables
- [ ] Tests approfondis

**Temps estimé développement** : 3-5 jours

---

### 2.2 Organisation de l'équipe de traduction
**Temps estimé** : 1-2 jours

**Tâches** :
- [ ] Recruter traducteurs français (2-5 personnes)
- [ ] Diviser les 14,436 textes en sections
- [ ] Assigner responsabilités par catégorie :
  - [ ] Dialogues (estimé : 6,000 textes)
  - [ ] Descriptions objets (estimé : 3,000 textes)
  - [ ] Noms de lieux (estimé : 500 textes)
  - [ ] Messages système (estimé : 2,000 textes)
  - [ ] Descriptions Pokémon (estimé : 2,936 textes)

**Outils à fournir** :
- [ ] Guide de style de traduction
- [ ] Glossaire Pokemon FR officiel
- [ ] Fichier `differences/englishrom_diff_only.json`
- [ ] Validation automatique avec `validate_translation.py`

---

### 2.3 Créer les outils de gestion de traduction
**Temps estimé** : 2-3 jours
**Développeur** : Requis

**Outils à créer** :

#### A. Convertisseur JSON ↔ CSV
```python
# json_to_csv.py
# Convertir JSON en CSV pour édition dans Excel/Google Sheets
```

**Tâches** :
- [ ] Script de conversion JSON → CSV
- [ ] Script de conversion CSV → JSON
- [ ] Validation de l'intégrité des données
- [ ] Gestion de l'encodage UTF-8

**Format CSV** :
```csv
Offset,English,French,Length,Encoding,Category
0x0018D42A,Take care now!,[À TRADUIRE],14,pokemon,dialogue
```

---

#### B. Interface web de traduction (OPTIONNEL)
**Temps estimé** : 1 semaine

**Fonctionnalités** :
- [ ] Affichage texte par texte
- [ ] Indicateur de longueur restante
- [ ] Recherche et filtres par catégorie
- [ ] Progression % par traducteur
- [ ] Export JSON final

**Technologies suggérées** :
- Frontend : HTML + JavaScript simple
- Backend : Python Flask
- Base de données : SQLite

---

## Phase 3 : Traduction (DURÉE VARIABLE)

### 3.1 Traduction initiale
**Temps estimé** : Variable selon équipe
**Volume** : 14,436 textes

**Estimation par vitesse** :
- Traducteur rapide : 100 textes/heure → 144 heures (18 jours à 8h/jour)
- Équipe de 3 : ~6 jours intensifs
- Équipe de 5 : ~4 jours intensifs

**Organisation** :

#### Semaine 1-2 : Textes prioritaires
- [ ] Dialogues principaux (2,000 textes)
- [ ] Messages système critiques (500 textes)
- [ ] Noms de lieux et menus (500 textes)

#### Semaine 3-4 : Textes secondaires
- [ ] Dialogues PNJ (4,000 textes)
- [ ] Descriptions objets (3,000 textes)

#### Semaine 5-6 : Textes complémentaires
- [ ] Descriptions Pokémon (2,936 textes)
- [ ] Textes rares/cachés (2,500 textes)

**Contrôle qualité continu** :
- [ ] Validation quotidienne avec `validate_translation.py`
- [ ] Tests émulateur hebdomadaires
- [ ] Relecture croisée entre traducteurs

---

### 3.2 Gestion des contraintes de longueur
**Responsable** : Chef de projet + traducteurs

**Processus** :

#### Étape 1 : Première passe (traduction naturelle)
- [ ] Traduire sans contrainte de longueur
- [ ] Marquer les textes dépassant la limite

#### Étape 2 : Identification des textes problématiques
```bash
python3 validate_translation.py differences/englishrom_diff_only.json
```

**Résultat attendu** :
- Liste des X textes trop longs
- Catégorisation par dépassement :
  - 1-5 caractères : Facile à ajuster
  - 6-10 caractères : Nécessite réécriture
  - 11+ caractères : Nécessite relocalisation OU abréviation forte

#### Étape 3 : Stratégies d'ajustement

**Pour dépassement 1-5 caractères** :
- [ ] Abréviations standards (Pokémon → PKM)
- [ ] Suppression articles (Le/La → Ø)
- [ ] Synonymes courts

**Pour dépassement 6-10 caractères** :
- [ ] Réécriture complète
- [ ] Changement de formulation
- [ ] Consultation glossaire abrégé

**Pour dépassement 11+ caractères** :
- [ ] Décision : Accepter ROM avec bugs OU développer relocalisation avancée
- [ ] Alternative : Diviser en deux textes si possible

---

### 3.3 Glossaire et cohérence
**Temps estimé** : Continu pendant traduction

**Tâches** :
- [ ] Créer glossaire principal (200-300 termes)
- [ ] Définir traductions Pokemon officielles FR
- [ ] Lister abréviations acceptées
- [ ] Documenter noms propres (villes, personnages)

**Fichier** : `GLOSSARY.md`

**Exemples de décisions** :
```markdown
# Glossaire

## Termes Pokemon
- Pokémon Center → Centre Pokémon (pas "CPM")
- Poké Ball → Poké Ball (pas traduit)
- Hit Points → Points de Vie (abrégé : PV)

## Noms de lieux
- Pallet Town → Bourg Palette
- Viridian City → Jadielle

## Objets
- Potion → Potion
- Super Potion → Super Potion

## Abréviations acceptées (si contrainte d'espace)
- ATTAQUE → ATQ
- DÉFENSE → DÉF
- Expérience → EXP
```

---

## Phase 4 : Implémentation Technique (2 OPTIONS)

### Option A : Réinsertion basique (SIMPLE) ⭐
**Temps estimé** : 1 journée
**Prérequis** : Toutes traductions ≤ longueur originale

**Processus** :

#### 4.1 Préparation finale
- [ ] Validation complète avec `validate_translation.py`
- [ ] Vérification : 0 erreur, 0 texte trop long
- [ ] Backup de la ROM originale

#### 4.2 Génération de la ROM traduite
```bash
# Copier le fichier de traduction finalisé
cp french_translation_final.json extracted_texts/englishrom_texts.json

# Générer la ROM
make reinsert-en

# Résultat : englishrom_modified.gba
```

#### 4.3 Tests
- [ ] Test boot ROM sur émulateur
- [ ] Test écran titre
- [ ] Test 20 premiers dialogues
- [ ] Test menu principal
- [ ] Test combat
- [ ] Test Pokédex
- [ ] Test sauvegarde/chargement

---

### Option B : Relocalisation avancée (COMPLEXE)
**Temps estimé** : 1-2 semaines développement + tests
**Prérequis** : Développement supplémentaire

**Développements nécessaires** :

#### 4.1 Améliorer `translate_rom.py`
**Fichier** : `translate_rom_advanced.py`

**Nouvelles fonctionnalités** :
- [ ] Détection automatique des tables de textes
- [ ] Analyse des structures de données Pokemon
- [ ] Relocalisation de tables entières
- [ ] Mise à jour des pointeurs de tables

**Algorithme** :
```python
def relocate_text_table(table_offset, table_size):
    """
    1. Identifier tous les textes de la table
    2. Calculer l'espace total nécessaire
    3. Allouer bloc dans espace libre
    4. Copier tous les textes dans le nouveau bloc
    5. Reconstruire la table de pointeurs
    6. Mettre à jour le pointeur vers la table
    7. Effacer l'ancien bloc
    """
```

**Tâches de développement** :
- [ ] Étudier la structure des tables Pokemon (3 jours)
- [ ] Implémenter détection de tables (2 jours)
- [ ] Implémenter relocalisation (3 jours)
- [ ] Tests unitaires (2 jours)

#### 4.2 Créer script de validation ROM
**Fichier** : `validate_rom.py`

**Fonctionnalités** :
- [ ] Vérifier intégrité checksum ROM
- [ ] Tester chargement dans émulateur
- [ ] Valider textes affichés correctement
- [ ] Détecter corruptions mémoire

#### 4.3 Tests approfondis
- [ ] Tests automatisés sur émulateur
- [ ] Capture d'écran comparaison EN vs FR
- [ ] Tests de toutes les fonctionnalités du jeu
- [ ] Tests de régression

---

## Phase 5 : Tests et Validation (CRITIQUE)

### 5.1 Tests fonctionnels (Version Alpha)
**Temps estimé** : 1 semaine
**Équipe** : 3-5 testeurs

**Plan de test** :

#### Jour 1 : Tests de base
- [ ] Démarrage du jeu
- [ ] Création nouveau personnage
- [ ] 3 premières routes
- [ ] Premier combat
- [ ] Capture d'un Pokémon
- [ ] Menu Pokémon

#### Jour 2 : Tests système
- [ ] Sauvegarde/Chargement
- [ ] Menu principal complet
- [ ] Pokédex (20 entrées)
- [ ] Sac à dos (tous objets)
- [ ] Centre Pokémon
- [ ] Boutique

#### Jour 3-4 : Tests avancés
- [ ] Histoire principale (10 premières heures)
- [ ] Arène 1
- [ ] Arène 2
- [ ] Échanges Pokémon
- [ ] PC Storage

#### Jour 5-7 : Tests exhaustifs
- [ ] Tous les dialogues PNJ (échantillon 200)
- [ ] Toutes descriptions objets
- [ ] Toutes attaques Pokémon
- [ ] Fin du jeu
- [ ] Post-game

**Fichier de suivi** : `TESTS.md`

**Format rapport de bug** :
```markdown
## Bug #42
- Catégorie : Texte tronqué
- Emplacement : Route 3, PNJ3
- Texte attendu : "Bienvenue sur la Route 3"
- Texte affiché : "Bienvenue sur la Rou"
- Offset : 0x001234AB
- Priorité : Haute
- Status : À corriger
```

---

### 5.2 Corrections de bugs
**Temps estimé** : Variable (1-3 semaines)

**Processus** :

#### Triage des bugs
- [ ] Catégoriser par priorité (Critique/Haute/Moyenne/Basse)
- [ ] Catégoriser par type (Longueur/Encodage/Localisation/Autre)

#### Correction
- [ ] Bugs critiques : Textes manquants, crashs
- [ ] Bugs hauts : Textes tronqués, affichage incorrect
- [ ] Bugs moyens : Fautes de frappe, formulations
- [ ] Bugs bas : Cosmétique

#### Workflow correction
```bash
1. Identifier le texte dans englishrom_texts.json
2. Corriger la traduction
3. Re-générer la ROM : make reinsert-en
4. Re-tester
5. Valider correction
6. Passer au bug suivant
```

---

### 5.3 Tests béta publics (OPTIONNEL)
**Temps estimé** : 2-4 semaines
**Communauté** : 50-200 testeurs

**Processus** :
- [ ] Créer version béta avec watermark
- [ ] Distribuer à testeurs sélectionnés
- [ ] Créer formulaire de feedback
- [ ] Analyser retours communauté
- [ ] Intégrer corrections prioritaires

**Plateforme** : Discord, Reddit r/PokemonROMhacks

---

## Phase 6 : Release et Distribution

### 6.1 Préparation de la release finale
**Temps estimé** : 3-5 jours

**Tâches** :

#### A. Finalisation technique
- [ ] Validation finale complète
- [ ] Génération ROM finale
- [ ] Tests sur vraie console (flashcart)
- [ ] Calcul checksum et hashes (MD5, SHA256)

#### B. Documentation utilisateur
**Fichier** : `README_FR.md`

**Contenu** :
- [ ] Instructions d'installation
- [ ] Liste des changements vs version anglaise
- [ ] Crédits équipe de traduction
- [ ] FAQ
- [ ] Compatibilité émulateurs

#### C. Package de distribution
**Contenu du package** :
```
pokemon_firered_french_v1.0/
├── pokemon_firered_fr.gba      # ROM traduite
├── README_FR.md                 # Documentation
├── CHANGELOG.md                 # Historique versions
├── CREDITS.md                   # Crédits complets
├── patch/
│   └── firered_french.ips      # Patch IPS (optionnel)
└── tools/
    └── validate_checksum.py    # Outil de validation
```

---

### 6.2 Création du patch IPS (RECOMMANDÉ)
**Temps estimé** : 1 jour

**Pourquoi un patch ?** :
- ✅ Légal : Ne distribue pas la ROM complète
- ✅ Petit : ~2-5 MB vs 32 MB
- ✅ Standard : Compatible tous outils de patch

**Outils** :
- Lunar IPS (Windows)
- MultiPatch (Mac)
- Python script custom

**Tâches** :
- [ ] Générer patch IPS : ROM anglaise → ROM française
- [ ] Tester patch sur ROM clean
- [ ] Créer instructions d'application du patch
- [ ] Vérifier checksum ROM patchée

**Script** : `create_patch.py`

---

### 6.3 Release publique
**Plateforme** : ROMhacking.net, GitHub, Archive.org

**Tâches** :

#### A. Préparation page de projet
- [ ] Créer page ROMhacking.net
- [ ] Uploader patch IPS
- [ ] Écrire description complète
- [ ] Screenshots (10-15 images)
- [ ] Vidéo trailer (optionnel)

#### B. Annonce communauté
- [ ] Post Reddit r/PokemonROMhacks
- [ ] Post Twitter/X
- [ ] Discord servers Pokemon
- [ ] Forums français

#### C. Support post-release
- [ ] Créer système de bug report (GitHub Issues)
- [ ] Répondre questions utilisateurs
- [ ] Planifier patches correctifs si nécessaire

---

## Phase 7 : Maintenance (LONG TERME)

### 7.1 Patches correctifs
**Fréquence** : Au besoin

**Versions** :
- v1.0 : Release initiale
- v1.1 : Corrections bugs critiques (1 mois)
- v1.2 : Corrections bugs mineurs (3 mois)
- v1.3+ : Améliorations communauté (6+ mois)

**Process** :
```bash
1. Collecter bugs rapportés
2. Prioriser corrections
3. Modifier translation JSON
4. Re-générer ROM
5. Créer nouveau patch IPS
6. Release v1.x
```

---

### 7.2 Amélioration continue (OPTIONNEL)
**Suggestions communauté** :

**Possibilités** :
- [ ] Traduction noms Pokémon (si non officiel FR)
- [ ] Ajout accents français manquants
- [ ] Amélioration fluidité dialogues
- [ ] Easter eggs français
- [ ] Support ROM hacks populaires (Unbound, etc.)

---

## Annexes

### A. Estimation totale du projet

#### Approche Conservative (RECOMMANDÉ)
**Durée totale** : 8-12 semaines

| Phase | Durée |
|-------|-------|
| Préparation | Complété |
| Organisation | 1 semaine |
| Traduction | 4-6 semaines |
| Tests | 2-3 semaines |
| Release | 1 semaine |

**Équipe minimale** :
- 1 Chef de projet
- 3-5 Traducteurs
- 2-3 Testeurs
- 1 Développeur (support technique)

---

#### Approche Avancée (Avec relocalisation)
**Durée totale** : 12-16 semaines

| Phase | Durée |
|-------|-------|
| Préparation | Complété |
| Développement avancé | 2-3 semaines |
| Organisation | 1 semaine |
| Traduction | 4-6 semaines |
| Tests approfondis | 3-4 semaines |
| Release | 1 semaine |

**Équipe requise** :
- 1 Chef de projet
- 2 Développeurs (ROM hacking)
- 5-8 Traducteurs
- 3-5 Testeurs
- 1 Community manager

---

### B. Checklist de validation finale

#### Avant release
- [ ] ROM boot sans erreur
- [ ] Tous textes affichés correctement
- [ ] Aucun crash sur story principale
- [ ] Sauvegarde fonctionne
- [ ] Checksum calculé et documenté
- [ ] Patch IPS testé sur ROM clean
- [ ] README complet
- [ ] Crédits à jour
- [ ] Tests sur 3+ émulateurs différents
- [ ] Tests sur vraie console (si possible)

#### Post-release
- [ ] Monitoring des premiers retours (48h)
- [ ] Patch correctif rapide si bug critique
- [ ] Réponse aux questions fréquentes
- [ ] Mise à jour documentation si nécessaire

---

### C. Contacts et ressources

#### Communautés ROM hacking
- ROMhacking.net
- Reddit r/PokemonROMhacks
- Discord "The PokéCommunity"
- Discord "ROM Hacking Hideout"

#### Outils utiles
- mGBA (émulateur)
- Lunar IPS (patcher)
- HxD (hex editor)
- Tilemap Studio (graphics)

#### Documentation Pokemon
- Bulbapedia (noms officiels FR)
- Pokémon Database
- Serebii.net

---

## 🎯 Prochaines étapes immédiates

### Cette semaine
1. [ ] **DÉCISION** : Choisir approche (Conservative vs Avancée)
2. [ ] Créer `json_to_csv.py` pour faciliter traduction
3. [ ] Recruter 2-3 traducteurs pour test
4. [ ] Traduire 100 premiers textes (test pilote)
5. [ ] Générer ROM test et valider fonctionnement

### Ce mois-ci
1. [ ] Finaliser équipe de traduction
2. [ ] Établir glossaire complet
3. [ ] Traduire 3,000 premiers textes (dialogues prioritaires)
4. [ ] Tests alpha réguliers
5. [ ] Ajuster workflow selon retours

---

**Dernière mise à jour** : 2026-01-13
**Status projet** : Phase 2 - Stratégie en définition
**Prochain milestone** : Décision approche technique (J+7)
