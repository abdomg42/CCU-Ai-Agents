"""Configuration commune pour pytest."""
import os
import shutil

# Mode mock LLM pour garantir l'exécution sans Ollama installé en test.
os.environ.setdefault("MOCK_LLM", "true")

# Répertoire ChromaDB temporaire pour les tests
CHROMA_TEST_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "test_chroma")


def pytest_configure(config):
    os.environ["MOCK_LLM"] = "true"


def pytest_sessionstart(session):
    if os.path.isdir(CHROMA_TEST_DIR):
        shutil.rmtree(CHROMA_TEST_DIR, ignore_errors=True)
