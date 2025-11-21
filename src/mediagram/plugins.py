"""Plugin management for mediagram."""

import importlib
import json
import os
import sys
from importlib import metadata
from runpy import run_module

import pluggy
import typer
from typing_extensions import Annotated

from . import hookspecs

# Environment variable to control plugin loading
# Set to empty string to disable all plugins
# Set to comma-separated list to load only specific plugins
MEDIAGRAM_LOAD_PLUGINS = os.environ.get("MEDIAGRAM_LOAD_PLUGINS")

# Create plugin manager
pm = pluggy.PluginManager("mediagram")
pm.add_hookspecs(hookspecs)

# Built-in plugins that are always loaded
BUILTIN_PLUGINS = [
    "mediagram.builtins.sleep_tool",
    "mediagram.builtins.filesystem_tools",
]

_loaded = False


def load_plugins():
    """Load all plugins (built-in and installed)."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    # Load plugins from setuptools entry points (normal operation)
    if not hasattr(sys, "_called_from_test") and MEDIAGRAM_LOAD_PLUGINS is None:
        pm.load_setuptools_entrypoints("mediagram")

    # Load specific plugins if MEDIAGRAM_LOAD_PLUGINS is set
    if MEDIAGRAM_LOAD_PLUGINS is not None:
        for package_name in [
            name for name in MEDIAGRAM_LOAD_PLUGINS.split(",") if name.strip()
        ]:
            try:
                distribution = metadata.distribution(package_name)
                mediagram_entry_points = [
                    ep for ep in distribution.entry_points if ep.group == "mediagram"
                ]
                for entry_point in mediagram_entry_points:
                    mod = entry_point.load()
                    pm.register(mod, name=entry_point.name)
                    pm._plugin_distinfo.append((mod, distribution))
            except metadata.PackageNotFoundError:
                sys.stderr.write(f"Plugin {package_name} could not be found\n")

    # Load built-in plugins
    for plugin in BUILTIN_PLUGINS:
        mod = importlib.import_module(plugin)
        pm.register(mod, plugin)


# CLI commands for plugin management

app = typer.Typer()


def get_plugins(all: bool = False):
    """Get list of installed plugins with metadata."""
    load_plugins()
    plugins = []
    plugin_to_distinfo = dict(pm.list_plugin_distinfo())

    for plugin in pm.get_plugins():
        # Skip built-in plugins unless --all is specified
        if not all and plugin.__name__.startswith("mediagram.builtins."):
            continue

        plugin_info = {
            "name": plugin.__name__,
            "hooks": [h.name for h in pm.get_hookcallers(plugin)],
        }

        distinfo = plugin_to_distinfo.get(plugin)
        if distinfo:
            plugin_info["version"] = distinfo.version
            plugin_info["name"] = (
                getattr(distinfo, "name", None) or distinfo.project_name
            )

        plugins.append(plugin_info)

    return plugins


@app.command()
def install(
    packages: Annotated[list[str], typer.Argument(help="Package names to install")],
    upgrade: Annotated[
        bool, typer.Option("--upgrade", "-U", help="Upgrade packages")
    ] = False,
    editable: Annotated[
        str | None, typer.Option("--editable", "-e", help="Install in editable mode")
    ] = None,
    force_reinstall: Annotated[
        bool, typer.Option("--force-reinstall", help="Force reinstall")
    ] = False,
    no_cache_dir: Annotated[
        bool, typer.Option("--no-cache-dir", help="Disable cache")
    ] = False,
    pre: Annotated[
        bool, typer.Option("--pre", help="Include pre-release versions")
    ] = False,
):
    """Install packages from PyPI into the same environment as mediagram.

    Examples:
        mediagram plugin install mediagram-http
        mediagram plugin install -e /path/to/plugin
        mediagram plugin install git+https://github.com/user/mediagram-plugin.git
    """
    args = ["pip", "install"]
    if upgrade:
        args += ["--upgrade"]
    if editable:
        args += ["--editable", editable]
    if force_reinstall:
        args += ["--force-reinstall"]
    if no_cache_dir:
        args += ["--no-cache-dir"]
    if pre:
        args += ["--pre"]
    args += list(packages)

    sys.argv = args
    run_module("pip", run_name="__main__")


@app.command()
def uninstall(
    packages: Annotated[list[str], typer.Argument(help="Package names to uninstall")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
):
    """Uninstall Python packages from the mediagram environment.

    Examples:
        mediagram plugin uninstall mediagram-http
        mediagram plugin uninstall mediagram-http mediagram-ffmpeg -y
    """
    sys.argv = ["pip", "uninstall"] + list(packages) + (["-y"] if yes else [])
    run_module("pip", run_name="__main__")


@app.command()
def plugins(
    all: Annotated[
        bool, typer.Option("--all", help="Include built-in plugins")
    ] = False,
    hooks: Annotated[
        list[str] | None, typer.Option("--hook", help="Filter by hook name")
    ] = None,
    dump: Annotated[
        bool, typer.Option("--dump", help="Show full plugin details as JSON")
    ] = False,
):
    """List installed plugins.

    Examples:
        mediagram plugin plugins
        mediagram plugin plugins --all
        mediagram plugin plugins --hook register_tools
        mediagram plugin plugins --dump
    """
    plugins_list = get_plugins(all)

    if hooks:
        hooks_set = set(hooks)
        plugins_list = [p for p in plugins_list if hooks_set.intersection(p["hooks"])]

    if dump:
        typer.echo(json.dumps(plugins_list, indent=2))
    else:
        for plugin in plugins_list:
            typer.echo(plugin["name"])


@app.command(name="list")
def list_command(
    all: Annotated[
        bool, typer.Option("--all", help="Include built-in plugins")
    ] = False,
    dump: Annotated[
        bool, typer.Option("--dump", help="Show full plugin details as JSON")
    ] = False,
):
    """List installed plugins (alias for 'plugins' command).

    Examples:
        mediagram plugin list
        mediagram plugin list --all
        mediagram plugin list --dump
    """
    plugins_list = get_plugins(all)
    if dump:
        typer.echo(json.dumps(plugins_list, indent=2))
    else:
        for plugin in plugins_list:
            typer.echo(plugin["name"])
