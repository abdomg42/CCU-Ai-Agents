import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    """Configuration centralisée du projet diagnostic-technique."""

    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

    # LLM configuration
    # Ollama est le moteur local par défaut. Décommenter/adapter la section
    # Anthropic ci-dessous pour switcher vers Claude (nécessite ANTHROPIC_API_KEY).
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")

    # Pour tests et démo sans Ollama disponible
    MOCK_LLM: bool = os.getenv("MOCK_LLM", "false").lower() in {"1", "true", "yes"}

    # Anthropic (utilisé pour la génération de tickets synthétiques CCU)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

    # Neo4j GraphRAG
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "abdo1234")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # Embeddings (abstraction : ollama par défaut, sentence-transformers/openai/voyage possible)
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "ollama")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "mxbai-embed-large:latest"
    )
    VECTOR_INDEX_DIM: int = int(os.getenv("VECTOR_INDEX_DIM", "1024"))
    VECTOR_SIMILARITY_THRESHOLD: float = float(
        os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.75")
    )
    TICKETS_VECTOR_INDEX: str = os.getenv("TICKETS_VECTOR_INDEX", "ticket_embeddings")

    # Vector store (ChromaDB embarqué) -- deprecated, remplacé par Neo4j
    CHROMA_PERSIST_DIR: Path = PROJECT_ROOT / "data" / "chroma"
    TICKETS_COLLECTION: str = os.getenv("TICKETS_COLLECTION", "ccu_tickets")

    # Mocks
    MOCKS_DIR: Path = PROJECT_ROOT / "mocks"
    MOCK_LOGS: Path = MOCKS_DIR / "mock_logs.json"
    MOCK_CRM: Path = MOCKS_DIR / "mock_crm.json"
    MOCK_ORDERS: Path = MOCKS_DIR / "mock_orders_tmf622.json"
    MOCK_TICKETS_DIR: Path = MOCKS_DIR / "mock_tickets"

    # Postgres / CRM
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "inetum")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "inetum")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "inetum")

    # Ticketing backend abstraction
    TICKETING_BACKEND: str = os.getenv("TICKETING_BACKEND", "zammad")

    # Zammad
    ZAMMAD_URL: str = os.getenv("ZAMMAD_URL", "http://localhost:8080")
    ZAMMAD_TOKEN: str = os.getenv("ZAMMAD_TOKEN", "UOIt7O8Ez4FJ3-SFaCBM6QrIwOmEJSnVVFozTJEH1U4Q9PdbaodIRumm0zEEKeuU")
    ZAMMAD_DEFAULT_GROUP: str = os.getenv("ZAMMAD_DEFAULT_GROUP", "Users")

    # SMTP configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "kmg59674@gmail.com")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "nrvbupgsrsvrqpvga")
    SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "kmg59674@gmail.com"))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}
    REPORT_RECIPIENTS: str = os.getenv("REPORT_RECIPIENTS", "abdellah.moghandez@gmail.com")

    # Reports
    REPORTS_DIR: Path = PROJECT_ROOT / "reports"

    # Guardrail
    WHITELIST_PATH: Path = (
        PROJECT_ROOT
        / "sub_agents"
        / "guardrail_validator"
        / "action_whitelist.yaml"
    )

    # Audit
    AUDIT_LOG_PATH: Path = PROJECT_ROOT / "data" / "audit.log"

    # Ticket mapping
    TICKET_MAPPING_SIMILARITY_THRESHOLD: float = float(
        os.getenv("TICKET_MAPPING_SIMILARITY_THRESHOLD", "0.85")
    )


def get_settings() -> Settings:
    return Settings()
