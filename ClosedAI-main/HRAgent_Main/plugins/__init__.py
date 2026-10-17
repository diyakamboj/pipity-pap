"""Plugin module for HRAgents SDK.

This module provides support for loading and managing plugins that bundle
skills, hooks, MCP configurations, agents, and commands together.

It also provides support for plugin marketplaces - directories that list
available plugins with their metadata and source locations.

Additionally, it provides utilities for managing installed plugins in the
user's home directory (~/.HRAgent/plugins/installed/).

Note: Marketplace classes live in ``plugins.marketplace``.
"""

import importlib
from typing import Final

from plugins.fetch import (
    PluginFetchError,
    fetch_plugin_with_resolution,
)
from plugins.source import (
    GitHubURLComponents,
    is_local_path,
    parse_github_url,
    resolve_source_path,
    validate_source_path,
)
from plugins.types import (
    CommandDefinition,
    PluginAuthor,
    PluginManifest,
    PluginSource,
    ResolvedPluginSource,
)


#: Symbols re-exported from the heavier ``plugins`` subpackages. ``plugins.plugin``
#: imports ``core.execution.hooks`` at module level (and, transitively, plugins
#: discovery → installed → skills), which re-enters ``core.conversation`` and
#: ``core.agent.base`` while low-level modules (e.g. ``context.agent_context``
#: importing ``plugins.marketplace``) are still mid-initialization. Resolved on
#: first attribute access instead; the loading machinery only runs once its
#: surrounding graph is ready.
_LAZY_SYMBOLS: Final[dict[str, str]] = {
    # plugins.discovery
    "load_available_plugins": "plugins.discovery",
    "load_project_plugins": "plugins.discovery",
    "load_user_plugins": "plugins.discovery",
    # plugins.installed
    "InstalledPluginInfo": "plugins.installed",
    "disable_plugin": "plugins.installed",
    "enable_plugin": "plugins.installed",
    "get_installed_plugin": "plugins.installed",
    "get_installed_plugins_dir": "plugins.installed",
    "install_plugin": "plugins.installed",
    "list_installed_plugins": "plugins.installed",
    "load_installed_plugins": "plugins.installed",
    "uninstall_plugin": "plugins.installed",
    "update_plugin": "plugins.installed",
    # plugins.loader
    "load_plugins": "plugins.loader",
    # plugins.plugin
    "Plugin": "plugins.plugin",
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
    # Plugin classes
    "Plugin",
    "PluginFetchError",
    "PluginManifest",
    "PluginAuthor",
    "PluginSource",
    "ResolvedPluginSource",
    "CommandDefinition",
    # Plugin loading
    "load_plugins",
    "fetch_plugin_with_resolution",
    # Local plugin discovery (ambient auto-load)
    "load_user_plugins",
    "load_project_plugins",
    "load_available_plugins",
    # Source path utilities
    "GitHubURLComponents",
    "parse_github_url",
    "is_local_path",
    "validate_source_path",
    "resolve_source_path",
    # Installed plugins management
    "InstalledPluginInfo",
    "install_plugin",
    "uninstall_plugin",
    "list_installed_plugins",
    "load_installed_plugins",
    "get_installed_plugins_dir",
    "get_installed_plugin",
    "enable_plugin",
    "disable_plugin",
    "update_plugin",
]
