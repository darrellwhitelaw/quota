from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    @model_validator(mode="after")
    def _patch_empty_env_overrides(self) -> "Settings":
        """Fix for env vars set to empty string overriding .env values."""
        if not self.anthropic_api_key:
            from dotenv import dotenv_values
            env_vals = dotenv_values(".env")
            if env_vals.get("ANTHROPIC_API_KEY"):
                object.__setattr__(self, "anthropic_api_key", env_vals["ANTHROPIC_API_KEY"])
        return self

    # Apollo.io (contact sourcing)
    apollo_api_key: str = ""
    apollo_credits_per_heartbeat: int = 30

    # FullEnrich (email enrichment fallback)
    fullenrich_api_key: str = ""

    # Email delivery (Gmail REST API via OAuth2)
    gmail_from_email: str = ""
    gmail_from_name: str = ""
    google_client_id: str = ""       # OAuth2 client ID from Google Cloud Console
    google_client_secret: str = ""   # OAuth2 client secret from Google Cloud Console
    gmail_refresh_token: str = ""    # Generated via oauth_setup.py
    gmail_app_password: str = ""     # Gmail App Password — for IMAP inbox monitoring only
    email_daily_send_limit: int = 10

    # Slack (approval flow)
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_approval_channel_id: str = ""

    # Attio CRM
    attio_api_token: str = ""
    attio_api_base_url: str = "https://api.attio.com/v2"

    # Service
    agent_service_host: str = "0.0.0.0"
    agent_service_port: int = 8000

    # Agent behavior
    scout_batch_size: int = 5
    outreach_batch_size: int = 5
    enablement_batch_size: int = 5
    channels_batch_size: int = 10
    cro_batch_size: int = 50
    tier1_requires_approval: bool = True

    # Claude models
    scout_model: str = "claude-sonnet-4-20250514"
    outreach_model: str = "claude-sonnet-4-20250514"
    enablement_model: str = "claude-sonnet-4-20250514"
    channels_model: str = "claude-haiku-4-5-20251001"
    cro_model: str = "claude-sonnet-4-20250514"
    cro_conversational_max_turns: int = 10
    inbox_sentiment_model: str = "claude-haiku-4-5-20251001"
    max_tool_turns: int = 15
    max_tokens: int = 4096

    # Gmail IMAP (inbox monitoring)
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993

    # Dashboard / DB
    database_url: str = ""
    dashboard_password: str = "changeme"
    jwt_secret: str = "change-me-in-production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
