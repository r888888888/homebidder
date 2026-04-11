"""
Centralised application configuration.

All environment variables are declared here in one place. Import `settings`
from this module instead of calling os.getenv / os.environ directly in
individual tool or service files.
"""

from __future__ import annotations

import os


class _Settings:
    # ------------------------------------------------------------------ #
    # Required                                                             #
    # ------------------------------------------------------------------ #

    @property
    def anthropic_api_key(self) -> str:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Export it or add it to your .env file before starting the server."
            )
        return key

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./homebidder.db")

    # ------------------------------------------------------------------ #
    # External data APIs (all optional — features degrade gracefully)     #
    # ------------------------------------------------------------------ #

    @property
    def census_api_key(self) -> str | None:
        return os.getenv("CENSUS_API_KEY") or None

    @property
    def fred_api_key(self) -> str | None:
        return os.getenv("FRED_API_KEY") or None

    @property
    def bart_api_key(self) -> str:
        return os.getenv("BART_API_KEY", "")

    # ------------------------------------------------------------------ #
    # Feature flags                                                        #
    # ------------------------------------------------------------------ #

    @property
    def enable_description_llm(self) -> bool:
        return os.getenv("ENABLE_DESCRIPTION_LLM", "").strip() == "1"

    @property
    def description_llm_model(self) -> str:
        return os.getenv("DESCRIPTION_LLM_MODEL", "claude-sonnet-4-6")

    @property
    def enable_permit_llm(self) -> bool:
        return os.getenv("ENABLE_PERMIT_LLM", "").strip().lower() in ("1", "true", "yes")

    @property
    def permit_llm_model(self) -> str:
        return os.getenv("PERMIT_LLM_MODEL", "claude-sonnet-4-6")

    @property
    def renovation_llm_model(self) -> str:
        return os.getenv("RENOVATION_LLM_MODEL", "claude-sonnet-4-6")

    # ------------------------------------------------------------------ #
    # Server / logging                                                     #
    # ------------------------------------------------------------------ #

    @property
    def allowed_origins(self) -> list[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def log_file(self) -> str:
        return os.getenv("LOG_FILE", "homebidder.log")


settings = _Settings()
