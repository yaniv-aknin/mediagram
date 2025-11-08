from typing import Protocol
from dataclasses import dataclass


@dataclass
class ToolProgress:
    """Progress update from a tool."""

    text: str
    tool_id: str
    completion_ratio: float | None = None
    completion_eta_minutes: float | None = None


@dataclass
class ToolSuccess:
    """Success result from a tool."""

    text: str
    tool_id: str


@dataclass
class ToolError:
    """Error result from a tool."""

    text: str
    tool_id: str
    error_details: str | None = None


class DriverCallbacks(Protocol):
    """Protocol that drivers must implement to receive tool callbacks."""

    async def on_tool_progress(self, progress: ToolProgress) -> None:
        """Called when a tool reports progress."""
        ...

    async def on_tool_success(self, success: ToolSuccess) -> None:
        """Called when a tool completes successfully."""
        ...

    async def on_tool_error(self, error: ToolError) -> None:
        """Called when a tool encounters an error."""
        ...
