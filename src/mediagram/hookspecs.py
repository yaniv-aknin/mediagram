"""Hook specifications for mediagram plugins."""

from pluggy import HookspecMarker, HookimplMarker

hookspec = HookspecMarker("mediagram")
hookimpl = HookimplMarker("mediagram")


@hookspec
def register_tools(register):
    """Register tool functions that can be called by the agent.

    Args:
        register: Callable that accepts a tool function decorated with @tool
    """
