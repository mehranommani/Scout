"""
Central configuration — ALL secrets loaded exclusively from .env
No hardcoded credentials anywhere in code.

Fields without defaults are required in production (.env must supply them).
Empty-string defaults are intentional — they allow test imports without a
real .env while still failing loudly at runtime if a required value is missing.
"""
from pathlib import Path
from pydantic_settings import BaseSettings

# Resolve .env relative to this file so it works regardless of cwd
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # App
    APP_NAME: str = "scout"
    DEBUG: bool = False

    # PostgreSQL (raw asyncpg — no SQLAlchemy)
    # Empty default so module can be imported in tests without a live .env
    DATABASE_URL: str = ""

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "company_reports"
    QDRANT_VECTOR_SIZE: int = 768  # nomic-embed-text dimension

    # Ollama / LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:14b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_TEMPERATURE: float = 0.1

    # Langfuse — loaded from .env at runtime; empty default allows test imports
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3001"

    # Validation thresholds
    VALIDATION_MIN_TEXT_LENGTH: int = 500
    VALIDATION_MIN_RELEVANCY: float = 0.65
    VALIDATION_MAX_RETRIES: int = 3

    # Pagination defaults
    REPORTS_PAGE_LIMIT: int = 500   # max reports returned by /api/reports
    EVAL_ROWS_LIMIT: int = 500      # max rows returned by /api/eval

    # Source API keys — from .env (empty string = skip that source)
    OPENCORPORATES_API_KEY: str = ""
    CRUNCHBASE_API_KEY: str = ""

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",   # .env may contain vars (e.g. POSTGRES_PASSWORD) not in this model
    }


settings = Settings()

# ---------------------------------------------------------------------------
# Data source registry
# use_api=True       → httpx REST call
# use_scrapling=True → Scrapling StealthyFetcher (browser-based, stealth)
# requires_key=True  → source is skipped when the API key env var is blank
# ---------------------------------------------------------------------------
DATA_SOURCES: dict = {
    "opencorporates": {
        "enabled": True,
        "use_api": True,
        "base_url": "https://api.opencorporates.com/v0.4",
        "requires_key": True,    # API key required (free tier no longer unauthenticated)
    },
    "wikidata": {
        "enabled": True,
        "use_api": True,
        "base_url": "https://query.wikidata.org/sparql",
        "requires_key": False,
    },
    "crunchbase": {
        "enabled": True,
        "use_api": True,
        "base_url": "https://api.crunchbase.com/api/v4",
        "requires_key": True,    # skipped automatically when CRUNCHBASE_API_KEY is blank
    },
    "linkedin": {
        "enabled": True,
        "use_scrapling": True,
        "stealth": True,
        "base_url": "https://www.linkedin.com/company",
        "requires_key": False,
    },
    # Fallback: DuckDuckGo web search when no primary source returns data
    "duckduckgo": {
        "enabled": True,
        "use_api": False,        # uses duckduckgo-search Python library
        "requires_key": False,
    },
}
