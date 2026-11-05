from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMPORIO_", env_file=".env", extra="ignore")

    provider: Literal["demo", "openai", "openrouter", "ollama"] = "demo"
    model: str | None = None
    data_dir: Path = Path("data")
    state_dir: Path = Path("var")
    openai_api_key: SecretStr | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openrouter_api_key: SecretStr | None = Field(
        default=None, validation_alias="OPENROUTER_API_KEY"
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "http://127.0.0.1:8000"
    openrouter_provider_order: list[str] = Field(default_factory=list, max_length=10)
    langfuse_enabled: bool = False
    langfuse_public_key: SecretStr | None = Field(
        default=None, validation_alias="LANGFUSE_PUBLIC_KEY"
    )
    langfuse_secret_key: SecretStr | None = Field(
        default=None, validation_alias="LANGFUSE_SECRET_KEY"
    )
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )
    langfuse_environment: str = "artefact-local"
    eval_model: str = "z-ai/glm-5.3"
    eval_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] = (
        "max"
    )
    eval_max_tokens: int = Field(default=8192, ge=256, le=32768)
    eval_timeout: float = Field(default=120, gt=0, le=300)
    ollama_url: str = "http://localhost:11434"
    max_tool_rounds: int = Field(default=4, ge=1, le=8)
    llm_timeout: float = Field(default=45, gt=0, le=120)
    attendant_reasoning_effort: Literal[
        "default", "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] = "none"
    history_turns: int = Field(default=10, ge=1, le=30)
    timezone: str = "America/Campo_Grande"

    @model_validator(mode="after")
    def validate_provider(self):
        if self.langfuse_enabled and any(
            key is None or not key.get_secret_value().strip()
            for key in (self.langfuse_public_key, self.langfuse_secret_key)
        ):
            raise ValueError("LANGFUSE_PUBLIC_KEY e LANGFUSE_SECRET_KEY são obrigatórias.")
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY é obrigatória quando EMPORIO_PROVIDER=openai.")
        if self.provider == "openrouter" and (
            not self.openrouter_api_key or not self.openrouter_api_key.get_secret_value().strip()
        ):
            raise ValueError("OPENROUTER_API_KEY é obrigatória quando EMPORIO_PROVIDER=openrouter.")
        if not self.model:
            self.model = {
                "demo": "deterministic-v1",
                "openai": "gpt-4.1-mini",
                "openrouter": "xiaomi/mimo-v2.6-pro",
                "ollama": "qwen3:8b",
            }[self.provider]
        if self.provider == "openrouter" and "/" not in self.model:
            raise ValueError("EMPORIO_MODEL deve usar o formato provedor/modelo no OpenRouter.")
        return self
