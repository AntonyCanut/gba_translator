#!/bin/bash
# Script de restructuration du projet

echo "🏗️  Restructuration du projet selon les règles d'architecture..."

# Créer la nouvelle structure
mkdir -p input/roms
mkdir -p output/{roms,extracted,analysis,differences,reports}
mkdir -p src/{core,extractors,analyzers,translators,utils}
mkdir -p tests/{test_core,test_extractors,fixtures}

# Déplacer les ROMs
echo "📦 Déplacement des ROMs..."
mv englishrom.gba input/roms/ 2>/dev/null || echo "  englishrom.gba déjà déplacé"
mv spanishrom.gba input/roms/ 2>/dev/null || echo "  spanishrom.gba déjà déplacé"

# Déplacer les résultats existants
echo "📊 Déplacement des résultats..."
mv extracted_texts output/extracted/ 2>/dev/null || echo "  extracted_texts déjà déplacé"
mv differences output/ 2>/dev/null || echo "  differences déjà déplacé"
mv analysis_results output/analysis/ 2>/dev/null || echo "  analysis_results déjà déplacé"

# Créer __init__.py files
echo "🐍 Création des fichiers __init__.py..."
touch src/__init__.py
touch src/core/__init__.py
touch src/extractors/__init__.py
touch src/analyzers/__init__.py
touch src/translators/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py

# Renommer et déplacer la documentation
echo "📚 Réorganisation de la documentation..."
cd docs
mv README.md 00_README.md 2>/dev/null || true
mv SOLUTION.md 01_SOLUTION.md 2>/dev/null || true
mv TECHNICAL.md 02_TECHNICAL.md 2>/dev/null || true
mv TASKS.md 04_TASKS.md 2>/dev/null || true
mv TASKS_TECHNICAL.md 05_TASKS_TECHNICAL.md 2>/dev/null || true
mv STRATEGY.md 06_STRATEGY.md 2>/dev/null || true
cd ..

echo "✅ Structure créée!"
echo ""
echo "📁 Nouvelle structure:"
tree -L 2 -I '__pycache__|*.pyc' input output src docs 2>/dev/null || find input output src docs -maxdepth 2 -type d | sort

