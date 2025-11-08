import asyncio
from typing import TYPE_CHECKING

from .callbacks import ToolProgress, ToolSuccess, ToolError

if TYPE_CHECKING:
    from .callbacks import DriverCallbacks

ALL_TOOLS = []


def tool(f):
    ALL_TOOLS.append(f)
    return f


_driver_callbacks: "DriverCallbacks | None" = None


def set_driver_callbacks(callbacks: "DriverCallbacks") -> None:
    """Set the driver callbacks for tool execution."""
    global _driver_callbacks
    _driver_callbacks = callbacks


def get_driver_callbacks() -> "DriverCallbacks | None":
    """Get the current driver callbacks."""
    return _driver_callbacks


@tool
async def test_tool(duration_seconds: float, update_count: int, success: bool) -> str:
    """Test tool that runs for specified duration and sends progress updates.

    Args:
        duration_seconds: How long the tool should run
        update_count: Number of progress updates to send
        success: Whether to succeed or fail after the duration
    """
    callbacks = get_driver_callbacks()
    if not callbacks:
        return "Error: No driver callbacks configured"

    tool_id = f"test_tool_{id(asyncio.current_task())}"

    if update_count < 0:
        await callbacks.on_tool_error(
            ToolError(
                text="Invalid update_count",
                tool_id=tool_id,
                error_details=f"update_count must be >= 0, got {update_count}",
            )
        )
        return "Error: Invalid update_count"

    if duration_seconds < 0:
        await callbacks.on_tool_error(
            ToolError(
                text="Invalid duration",
                tool_id=tool_id,
                error_details=f"duration_seconds must be >= 0, got {duration_seconds}",
            )
        )
        return "Error: Invalid duration"

    start_time = asyncio.get_event_loop().time()
    interval = duration_seconds / max(update_count, 1) if update_count > 0 else 0

    for i in range(update_count):
        elapsed = asyncio.get_event_loop().time() - start_time
        completion_ratio = (i + 1) / update_count if update_count > 0 else 1.0
        remaining_time = duration_seconds - elapsed

        await callbacks.on_tool_progress(
            ToolProgress(
                text=f"Progress update {i + 1}/{update_count}",
                tool_id=tool_id,
                completion_ratio=completion_ratio,
                completion_eta_minutes=remaining_time / 60,
            )
        )

        if i < update_count - 1:
            await asyncio.sleep(interval)

    # Sleep for any remaining time
    elapsed = asyncio.get_event_loop().time() - start_time
    if elapsed < duration_seconds:
        await asyncio.sleep(duration_seconds - elapsed)

    if success:
        await callbacks.on_tool_success(
            ToolSuccess(
                text=f"Test tool completed successfully after {duration_seconds}s",
                tool_id=tool_id,
            )
        )
        return f"Successfully completed after {duration_seconds} seconds with {update_count} updates"
    else:
        await callbacks.on_tool_error(
            ToolError(
                text="Test tool failed as requested",
                tool_id=tool_id,
                error_details=f"Tool ran for {duration_seconds}s and was configured to fail",
            )
        )
        return "Failed as requested"
