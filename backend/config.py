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
    # Auth                                                                 #
    # ------------------------------------------------------------------ #

    @property
    def jwt_secret(self) -> str:
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise RuntimeError(
                "JWT_SECRET is not set. "
                "Generate a long random string and add it to your .env file."
            )
        return secret

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

    @property
    def spotcrime_api_key(self) -> str | None:
        return os.getenv("SPOTCRIME_API_KEY") or None

    @property
    def rentcast_api_key(self) -> str | None:
        return os.getenv("RENTCAST_API_KEY") or None

    # ------------------------------------------------------------------ #
    # Feature flags                                                        #
    # ------------------------------------------------------------------ #

    @property
    def rate_limit_enabled(self) -> bool:
        return os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("true", "1", "yes")

    @property
    def rate_limit_analyses_per_day(self) -> int:
        return int(os.getenv("RATE_LIMIT_ANALYSES_PER_DAY", "5"))

    @property
    def rate_limit_authenticated_per_day(self) -> int:
        return int(os.getenv("RATE_LIMIT_AUTHENTICATED_PER_DAY", "20"))

    @property
    def enable_description_llm(self) -> bool:
        return os.getenv("ENABLE_DESCRIPTION_LLM", "").strip() == "1"

    @property
    def description_llm_model(self) -> str:
        return os.getenv("DESCRIPTION_LLM_MODEL", "claude-sonnet-4-6")

    @property
    def enable_rentcast_avm(self) -> bool:
        """True only when ENABLE_RENTCAST_AVM=1 AND RENTCAST_API_KEY is set."""
        return os.getenv("ENABLE_RENTCAST_AVM", "").strip() == "1" and bool(os.getenv("RENTCAST_API_KEY"))

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
    # OAuth providers (optional — features disabled when empty)           #
    # ------------------------------------------------------------------ #

    @property
    def google_client_id(self) -> str:
        return os.getenv("GOOGLE_CLIENT_ID", "")

    @property
    def google_client_secret(self) -> str:
        return os.getenv("GOOGLE_CLIENT_SECRET", "")

    @property
    def google_redirect_url(self) -> str:
        return os.getenv("GOOGLE_REDIRECT_URL", "http://localhost:3000/auth/callback/google")

    # Apple Sign In
    @property
    def apple_client_id(self) -> str:
        return os.getenv("APPLE_CLIENT_ID", "")

    @property
    def apple_team_id(self) -> str:
        return os.getenv("APPLE_TEAM_ID", "")

    @property
    def apple_key_id(self) -> str:
        return os.getenv("APPLE_KEY_ID", "")

    @property
    def apple_private_key(self) -> str:
        # .env files store newlines as literal \n — convert to real newlines for PEM parsing.
        return os.getenv("APPLE_PRIVATE_KEY", "").replace("\\n", "\n")

    @property
    def apple_redirect_url(self) -> str:
        return os.getenv("APPLE_REDIRECT_URL", "http://localhost:8000/api/auth/apple/callback")

    @property
    def frontend_url(self) -> str:
        return os.getenv("FRONTEND_URL", "http://localhost:3000")

    # ------------------------------------------------------------------ #
    # Admin portal                                                         #
    # ------------------------------------------------------------------ #

    @property
    def admin_username(self) -> str:
        return os.getenv("ADMIN_USERNAME", "admin")

    @property
    def admin_password(self) -> str | None:
        """Returns None when ADMIN_PASSWORD is not set (admin portal disabled)."""
        return os.getenv("ADMIN_PASSWORD") or None

    # ------------------------------------------------------------------ #
    # Stripe (optional — features disabled when keys are absent)          #
    # ------------------------------------------------------------------ #

    @property
    def stripe_secret_key(self) -> str | None:
        return os.getenv("STRIPE_SECRET_KEY") or None

    @property
    def stripe_publishable_key(self) -> str | None:
        return os.getenv("STRIPE_PUBLISHABLE_KEY") or None

    @property
    def stripe_webhook_secret(self) -> str | None:
        return os.getenv("STRIPE_WEBHOOK_SECRET") or None

    @property
    def stripe_investor_price_id(self) -> str | None:
        """Stripe Price ID for the Investor tier subscription."""
        return os.getenv("STRIPE_INVESTOR_PRICE_ID") or None

    @property
    def stripe_agent_price_id(self) -> str | None:
        """Stripe Price ID for the Agent tier subscription."""
        return os.getenv("STRIPE_AGENT_PRICE_ID") or None

    # ------------------------------------------------------------------ #
    # Subscription tier monthly analysis limits                           #
    # ------------------------------------------------------------------ #

    @property
    def rate_limit_anonymous_per_month(self) -> int:
        return int(os.getenv("RATE_LIMIT_ANONYMOUS_PER_MONTH", "3"))

    @property
    def rate_limit_buyer_per_month(self) -> int:
        return int(os.getenv("RATE_LIMIT_BUYER_PER_MONTH", "5"))

    @property
    def rate_limit_investor_per_month(self) -> int:
        return int(os.getenv("RATE_LIMIT_INVESTOR_PER_MONTH", "30"))

    @property
    def rate_limit_agent_per_month(self) -> int:
        return int(os.getenv("RATE_LIMIT_AGENT_PER_MONTH", "100"))

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
