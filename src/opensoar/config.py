from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    playbook_dirs: str = "playbooks"
    integration_dirs: str = ""
    local_login_enabled: bool = True
    local_registration_enabled: bool = False
    api_key_secret: str = ""
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if not self.jwt_secret:
            raise ValueError(
                "JWT_SECRET must be set to a non-empty value. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        if not self.api_key_secret:
            raise ValueError(
                "API_KEY_SECRET must be set to a non-empty value."
            )
        return self
    vt_api_key: str | None = None
    abuseipdb_api_key: str | None = None
    shodan_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_url: str | None = None
    llm_model: str | None = None
    # Semantic alert deduplication (issue #81).
    ai_embedding_provider: str | None = None
    ai_embedding_model: str | None = None
    ai_dedup_threshold: float = 0.85
    ai_embedding_cache_ttl: int = 7 * 24 * 3600  # 7 days
    debug: bool = False

    # Enrichment cache TTLs (seconds). See opensoar.integrations.cache.
    enrichment_cache_ttl_default: int = 3600
    enrichment_cache_ttl_virustotal: int = 24 * 3600
    enrichment_cache_ttl_abuseipdb: int = 12 * 3600
    enrichment_cache_ttl_greynoise: int = 6 * 3600
    enrichment_cache_ttl_shodan: int = 24 * 3600

    @property
    def playbook_directories(self) -> list[str]:
        return [d.strip() for d in self.playbook_dirs.split(",") if d.strip()]

    @property
    def integration_directories(self) -> list[str]:
        return [d.strip() for d in self.integration_dirs.split(",") if d.strip()]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql+psycopg2", "postgresql"
        )

    @property
    def effective_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
