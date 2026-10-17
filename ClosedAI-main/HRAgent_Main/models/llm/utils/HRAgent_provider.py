from __future__ import annotations

from typing import Any, Final, TypedDict
from urllib.parse import urlsplit, urlunsplit

from models.llm.utils.verified_models import VERIFIED_MODELS


HRAgentS_PROVIDER_PREFIX: Final[str] = "HRAgent/"
LITELLM_PROXY_PREFIX: Final[str] = "litellm_proxy/"
HRAgentS_LLM_PROXY_BASE_URL: Final[str] = "https://llm-proxy.app.all-hands.dev"


class LiteLLMCallKwargs(TypedDict):
    model: str
    api_base: str | None


_HRAgentS_PROXY_BASE_URLS: Final[frozenset[str]] = frozenset(
    {
        "https://llm-proxy.app.all-hands.dev",
        "https://llm-proxy.app.all-hands.dev/v1",
    }
)


def is_HRAgent_provider_model(model: str | None) -> bool:
    return bool(model and model.startswith(HRAgentS_PROVIDER_PREFIX))


def is_litellm_proxy_model(model: str | None) -> bool:
    return bool(model and model.startswith(LITELLM_PROXY_PREFIX))


def _normalize_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def is_HRAgent_proxy_base_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    return _normalize_base_url(base_url) in _HRAgentS_PROXY_BASE_URLS


def _is_verified_HRAgent_model_name(model_name: str) -> bool:
    return model_name in VERIFIED_MODELS["HRAgent"]


def _has_litellm_provider_prefix(model: str) -> bool:
    """Whether ``model`` already names a litellm provider (e.g. ``openai/...``)."""
    if "/" not in model:
        return False
    prefix = model.split("/", 1)[0]
    try:
        # Lazy import: this module is also imported by configuration.settings.model,
        # where a heavy litellm import at module scope is undesirable.
        import litellm

        provider_list = getattr(litellm, "provider_list", None)
        if provider_list is not None:
            return prefix in provider_list
    except Exception:
        pass
    return False


def litellm_call_kwargs(model: str, base_url: str | None) -> LiteLLMCallKwargs:
    if is_HRAgent_provider_model(model):
        model_name = model.removeprefix(HRAgentS_PROVIDER_PREFIX)
        return {
            "model": f"{LITELLM_PROXY_PREFIX}{model_name}",
            "api_base": base_url or HRAgentS_LLM_PROXY_BASE_URL,
        }
    if base_url and model and not _has_litellm_provider_prefix(model):
        # Custom OpenAI-compatible endpoint with an arbitrary model name (e.g.
        # ``moonshotai/kimi-k3-free``). litellm cannot infer a provider from the
        # name alone, so pin the OpenAI client against the supplied api_base.
        return {"model": f"openai/{model}", "api_base": base_url}
    return {"model": model, "api_base": base_url}


def canonicalize_HRAgent_llm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    model = payload.get("model")
    if not isinstance(model, str):
        return payload

    migrated = dict(payload)
    base_url = migrated.get("base_url")
    normalized_base_url = base_url if isinstance(base_url, str) else None

    if is_HRAgent_provider_model(model):
        if is_HRAgent_proxy_base_url(normalized_base_url):
            migrated.pop("base_url", None)
        return migrated

    if not (
        is_litellm_proxy_model(model)
        and is_HRAgent_proxy_base_url(normalized_base_url)
    ):
        return migrated

    model_name = model.removeprefix(LITELLM_PROXY_PREFIX)
    if not _is_verified_HRAgent_model_name(model_name):
        return migrated

    migrated["model"] = f"{HRAgentS_PROVIDER_PREFIX}{model_name}"
    migrated.pop("base_url", None)
    return migrated
