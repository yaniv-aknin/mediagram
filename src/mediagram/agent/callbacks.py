from typing import Protocol
from dataclasses import dataclass


@dataclass
class ProgressMessage:
    """Progress update from a tool."""

    text: str
    completion_ratio: float | None = None
    completion_eta_minutes: float | None = None


@dataclass
class SuccessMessage:
    """Success result from a tool."""

    text: str


@dataclass
class ErrorMessage(Exception):
    """Error result from a tool."""

    text: str
    error: Exception | None = None
    unexpected: bool = False


@dataclass
class StartMessage:
    """Start notification from a tool."""

    tool_name: str
    invocation_details: dict


class DriverCallbacks(Protocol):
    """Protocol that drivers must implement to receive tool callbacks."""

    async def on_tool_start(self, start: StartMessage, tool_id: str) -> None:
        """Called when a tool starts executing."""
        ...

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        """Called when a tool reports progress."""
        ...

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        """Called when a tool completes successfully."""
        ...

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        """Called when a tool encounters an error."""
        ...
