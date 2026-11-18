from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.market.settings import ROOT


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )
    openai_api_key: SecretStr = SecretStr("")
    news_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    swan_ai_daily_token_budget: int = Field(default=0, ge=0)
    swan_ai_max_output_tokens: int = Field(default=2000, ge=256, le=8000)
    swan_ai_timeout_seconds: int = Field(default=25, ge=5, le=45)
    swan_news_config: str = str(ROOT / "config" / "news-sources.json")

    def model_post_init(self, context) -> None:
        from services.core.setup import CONFIG_FILES, AgentPolicy

        path = CONFIG_FILES["agents"]
        if path.exists():
            policy = AgentPolicy.model_validate_json(path.read_text(encoding="utf-8"))
            self.openai_model = policy.model
            self.swan_ai_daily_token_budget = policy.daily_token_budget
            self.swan_ai_max_output_tokens = policy.max_output_tokens
            self.swan_ai_timeout_seconds = policy.timeout_seconds

    def ready(self) -> bool:
        return bool(
            self.openai_api_key.get_secret_value()
            and self.openai_model
            and self.swan_ai_daily_token_budget
        )
