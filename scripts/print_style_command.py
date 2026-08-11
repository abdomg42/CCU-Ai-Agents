"""Affiche la commande :style single-line prête à coller dans Neo4j Browser/Desktop."""
import json
from pathlib import Path

from config.settings import get_settings


def main() -> None:
    settings = get_settings()
    style_path = settings.PROJECT_ROOT / "graph" / "neo4j_style.grass"
    with open(style_path, encoding="utf-8") as f:
        style = json.load(f)
    # Commande single-line pour éviter les problèmes de parsing multi-lignes.
    print(":style " + json.dumps(style, separators=(",", ":")))


if __name__ == "__main__":
    main()
