#!/usr/bin/env bash
set -euo pipefail

# Seeding Neo4j : schéma + ingestion complète des mocks.
# Utilisable en local comme dans le conteneur Docker.

cd "$(dirname "$0")/.."

echo "=== Seeding Neo4j GraphRAG ==="
python -m graph.ingestion.run_all

echo "=== Done ==="
