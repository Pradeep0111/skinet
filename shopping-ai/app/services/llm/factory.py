from app.config import Settings
from app.services.llm import LLMProvider, MockLLMProvider
from app.services.llm.anthropic_provider import ClaudeProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()

    api_key = settings.anthropic_api_key
    model = settings.anthropic_model
    if api_key is None or model is None:  # Defensive; Settings validates this configuration.
        raise ValueError("Anthropic provider settings are incomplete")
    return ClaudeProvider(
        api_key=api_key.get_secret_value(),
        model=model,
        max_tokens=settings.anthropic_max_tokens,
        timeout_seconds=settings.request_timeout_seconds,
    )

