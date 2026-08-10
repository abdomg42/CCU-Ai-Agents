"""Configuration commune pour pytest."""
import os

# Mode mock LLM pour garantir l'exécution sans Ollama installé en test.
os.environ.setdefault("MOCK_LLM", "true")


def pytest_configure(config):
    os.environ["MOCK_LLM"] = "true"
