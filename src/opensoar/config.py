from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://opensoar:opensoar@localhost:5432/opensoar"
    redis_url: str = "redis://localhost:6379/0"
    playbook_dirs: str = "playbooks"
    api_key_secret: str = ""
    jwt_secret: str = ""
    jwt_expire_minutes: int = 480
    vt_api_key: str | None = None
    abuseipdb_api_key: str | None = None
    debug: bool = False

    @property
    def playbook_directories(self) -> list[str]:
        return [d.strip() for d in self.playbook_dirs.split(",") if d.strip()]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "postgresql+psycopg2", "postgresql"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
