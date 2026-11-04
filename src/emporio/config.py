from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMPORIO_", env_file=".env", extra="ignore")

    provider: Literal["demo", "openai", "ollama"] = "demo"
    model: str | None = None
    data_dir: Path = Path("data")
    state_dir: Path = Path("var")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    ollama_url: str = "http://localhost:11434"
    max_tool_rounds: int = Field(default=4, ge=1, le=8)
    llm_timeout: float = Field(default=45, gt=0, le=120)
    history_turns: int = Field(default=10, ge=1, le=30)
    timezone: str = "America/Campo_Grande"

    @model_validator(mode="after")
    def validate_provider(self):
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY é obrigatória quando EMPORIO_PROVIDER=openai.")
        if not self.model:
            self.model = {
                "demo": "deterministic-v1",
                "openai": "gpt-4.1-mini",
                "ollama": "qwen3:8b",
            }[self.provider]
        return self
