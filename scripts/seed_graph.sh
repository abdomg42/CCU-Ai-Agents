#!/usr/bin/env bash
set -euo pipefail

# Seeding Neo4j : schéma + ingestion complète des mocks.
# Utilisable en local comme dans le conteneur Docker.

cd "$(dirname "$0")/.."

# Détecte automatiquement le Python du venv s'il existe,
# sinon utilise le python disponible dans le PATH.
if [ -f ".venv/Scripts/python.exe" ]; then
    PYTHON=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python"
fi

echo "=== Seeding Neo4j GraphRAG (using $PYTHON) ==="
"$PYTHON" -m graph.ingestion.run_all

echo "=== Done ==="
