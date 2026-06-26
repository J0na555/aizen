from aizen.plugins.hooks import HookPoint, HookRegistry, get_hook_registry
from aizen.plugins.installer import install_from_git, list_installed, uninstall
from aizen.plugins.loader import discover_plugins
from aizen.plugins.registry import PluginInfo, discover_all, get_plugin_info, load_plugin_meta, save_plugin_meta

__all__ = [
    "HookPoint",
    "HookRegistry",
    "get_hook_registry",
    "install_from_git",
    "list_installed",
    "uninstall",
    "discover_plugins",
    "PluginInfo",
    "discover_all",
    "get_plugin_info",
    "load_plugin_meta",
    "save_plugin_meta",
]
