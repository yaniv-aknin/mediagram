import asyncio
import contextvars
import functools
from typing import TYPE_CHECKING

from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage

if TYPE_CHECKING:
    from ..callbacks import DriverCallbacks
    from pathlib import Path

ALL_TOOLS = []

_driver_callbacks: contextvars.ContextVar["DriverCallbacks | None"] = (
    contextvars.ContextVar("driver_callbacks", default=None)
)

_tool_subdir: contextvars.ContextVar["Path | None"] = contextvars.ContextVar(
    "tool_subdir", default=None
)


def set_driver_callbacks(callbacks: "DriverCallbacks") -> None:
    """Set the driver callbacks for tool execution."""
    _driver_callbacks.set(callbacks)


def get_driver_callbacks() -> "DriverCallbacks | None":
    """Get the current driver callbacks."""
    return _driver_callbacks.get()


def set_tool_subdir(subdir: "Path") -> None:
    """Set the current tool subdir for filesystem operations."""
    _tool_subdir.set(subdir)


def get_tool_subdir() -> "Path | None":
    """Get the current tool subdir."""
    return _tool_subdir.get()


def tool(f):
    """Decorator that wraps a tool function to handle the iterator protocol.

    Tools should yield ProgressMessage, SuccessMessage, or ErrorMessage.
    - Exactly one SuccessMessage or ErrorMessage must be yielded
    - SuccessMessage contains the return string for the LLM
    - ErrorMessage indicates failure
    - If neither Success nor Error are yielded, it's translated to ErrorMessage
    - Uncaught exceptions become ErrorMessage(unexpected=True)
    """

    @functools.wraps(f)
    async def wrapper(*args, **kwargs) -> str:
        callbacks = get_driver_callbacks()
        tool_id = f"tool_{f.__name__}_{id(asyncio.current_task())}"
        final_message: SuccessMessage | ErrorMessage | None = None

        try:
            async for message in f(*args, **kwargs):
                if final_message is not None:
                    error = ErrorMessage(
                        text=f"Error: Tool {f.__name__} yielded past the final message",
                        unexpected=True,
                    )
                    if callbacks:
                        await callbacks.on_tool_error(error, tool_id)
                    return error.text
                await _process_message(message, callbacks, tool_id)
                if isinstance(message, (SuccessMessage, ErrorMessage)):
                    final_message = message
        except ErrorMessage as e:
            if callbacks:
                await callbacks.on_tool_error(e, tool_id)
            return e.text
        except Exception as e:
            error = ErrorMessage(
                text=f"Error: {e}",
                error=e,
                unexpected=True,
            )
            if callbacks:
                await callbacks.on_tool_error(error, tool_id)
            return error.text

        if final_message is None:
            error = ErrorMessage(
                text="Error: Tool did not yield a final result",
                unexpected=True,
            )
            if callbacks:
                await callbacks.on_tool_error(error, tool_id)
            return error.text

        return final_message.text

    ALL_TOOLS.append(wrapper)
    return wrapper


async def _process_message(
    message: ProgressMessage | SuccessMessage | ErrorMessage,
    callbacks: "DriverCallbacks | None",
    tool_id: str,
) -> None:
    """Process a message yielded by a tool."""
    if not callbacks:
        return

    if isinstance(message, ProgressMessage):
        await callbacks.on_tool_progress(message, tool_id)
    elif isinstance(message, SuccessMessage):
        await callbacks.on_tool_success(message, tool_id)
    elif isinstance(message, ErrorMessage):
        await callbacks.on_tool_error(message, tool_id)
    else:
        raise TypeError(f"Unexpected message type: {type(message)}")


# Import tools to trigger @tool decorator registration
from .sleep import sleep  # noqa: F401, E402
from .filesystem import listdir, grep, rename  # noqa: F401, E402
from .respond import respond  # noqa: F401, E402
