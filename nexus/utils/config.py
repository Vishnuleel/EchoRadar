"""Central configuration. Everything is optional and read from the environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:  # python-dotenv is a convenience, not a requirement
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
# Audited Blue Science Park seed (second source, reconciled against the live directory on every sync).
# NEXUS_SEED_PATH overrides it; an empty value switches seed reconciliation off.
_seed_env = os.getenv("NEXUS_SEED_PATH")
SEED_PATH = (Path(_seed_env) if _seed_env else None) if _seed_env is not None else \
    DATA_DIR / "sources" / "bsp_audited_seed_2026-11-13" / "blue_science_park_audited_directory.json"


@dataclass(frozen=True)
class Settings:
    database_url: str
    embeddings: str
    embedding_model: str
    openalex_api_key: str
    contact_email: str
    openai_api_key: str
    openai_model: str
    offline: bool
    cache_dir: Path
    model_dir: Path

    # Ranking weights (initial hypotheses, see docs/innovation_methodology.md)
    w_complementarity: float = 0.35
    w_opportunity: float = 0.25
    w_research: float = 0.20
    w_evidence: float = 0.20
    # A source older than this many days is flagged as stale
    stale_after_days: int = 120


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("NEXUS_DATABASE_URL", f"sqlite:///{DATA_DIR / 'nexus.db'}"),
        embeddings=os.getenv("NEXUS_EMBEDDINGS", "auto").lower(),
        embedding_model=os.getenv(
            "NEXUS_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        openalex_api_key=os.getenv("OPENALEX_API_KEY", ""),
        contact_email=os.getenv("NEXUS_CONTACT_EMAIL", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        offline=os.getenv("NEXUS_OFFLINE", "0") == "1",
        cache_dir=Path(os.getenv("NEXUS_CACHE_DIR", DATA_DIR / "cache")),
        model_dir=Path(os.getenv("NEXUS_MODEL_DIR", DATA_DIR / "models")),
    )
