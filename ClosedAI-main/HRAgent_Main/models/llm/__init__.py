import importlib
from typing import Final

from models.llm.auth import (
    OPENAI_CODEX_MODELS,
    CredentialStore,
    OAuthCredentials,
    OpenAISubscriptionAuth,
)
from models.llm.fallback_strategy import FallbackStrategy
from models.llm.llm import LLM, LLM_PROFILE_SCHEMA_VERSION
from models.llm.llm_profile_store import (
    LLMProfileLoader,
    LLMProfileMutator,
    LLMProfileStore,
)
from models.llm.llm_registry import LLMRegistry, RegistryEvent
from models.llm.llm_response import LLMResponse
from models.llm.message import (
    ImageContent,
    Message,
    MessageToolCall,
    ReasoningItemModel,
    RedactedThinkingBlock,
    TextContent,
    ThinkingBlock,
    content_to_str,
)
from models.llm.streaming import (
    AsyncTokenCallbackType,
    LLMStreamChunk,
    TokenCallbackType,
)
from models.llm.utils.metrics import Metrics, MetricsSnapshot, TokenUsage
from models.llm.utils.unverified_models import (
    UNVERIFIED_MODELS_EXCLUDING_BEDROCK,
    get_unverified_models,
)
from models.llm.utils.verified_models import VERIFIED_MODELS


#: Symbols re-exported from heavy submodules. ``RouterLLM`` pulls in the whole
#: ``tools`` graph (via ``models.llm.router.base`` importing ``tools.tool``,
#: which triggers ``tools.builtins`` → skills → plugins → core.execution.hooks
#: → core.conversation). Low-level modules that only need the message types
#: (e.g. ``core.execution.event.base`` importing ``ImageContent``/``Message``/
#: ``TextContent``) must not drag that graph in while ``core.execution.event``
#: is still mid-initialization. Resolved on first attribute access instead.
_LAZY_SYMBOLS: Final[dict[str, str]] = {
    "RouterLLM": "models.llm.router",
}


def __getattr__(name: str):
    module_name = _LAZY_SYMBOLS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    # Auth
    "CredentialStore",
    "OAuthCredentials",
    "OpenAISubscriptionAuth",
    "OPENAI_CODEX_MODELS",
    # Core
    "FallbackStrategy",
    "LLMResponse",
    "LLM",
    "LLM_PROFILE_SCHEMA_VERSION",
    "LLMRegistry",
    "LLMProfileLoader",
    "LLMProfileMutator",
    "LLMProfileStore",
    "RouterLLM",
    "RegistryEvent",
    # Messages
    "Message",
    "MessageToolCall",
    "TextContent",
    "ImageContent",
    "ThinkingBlock",
    "RedactedThinkingBlock",
    "ReasoningItemModel",
    "content_to_str",
    # Streaming
    "AsyncTokenCallbackType",
    "LLMStreamChunk",
    "TokenCallbackType",
    # Metrics
    "Metrics",
    "MetricsSnapshot",
    "TokenUsage",
    # Models
    "VERIFIED_MODELS",
    "UNVERIFIED_MODELS_EXCLUDING_BEDROCK",
    "get_unverified_models",
]
