import asyncio
import contextvars
import functools
from typing import TYPE_CHECKING, Callable

from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage, StartMessage
from mediagram.config import DEFAULT_TOOL_OUTPUT_LIMIT

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

_tool_output_limit: contextvars.ContextVar[int] = contextvars.ContextVar(
    "tool_output_limit", default=DEFAULT_TOOL_OUTPUT_LIMIT
)

_log_message: contextvars.ContextVar["Callable | None"] = contextvars.ContextVar(
    "log_message", default=None
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


def set_tool_output_limit(limit: int) -> None:
    """Set the tool output limit for truncation."""
    _tool_output_limit.set(limit)


def get_tool_output_limit() -> int:
    """Get the current tool output limit."""
    return _tool_output_limit.get()


def set_log_message(log_message: "Callable") -> None:
    """Set the log_message function for tool execution."""
    _log_message.set(log_message)


def get_log_message() -> "Callable | None":
    """Get the current log_message function."""
    return _log_message.get()


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

        # Emit StartMessage before tool execution
        start_message = StartMessage(
            tool_name=f.__name__, invocation_details={"args": args, "kwargs": kwargs}
        )
        if callbacks:
            await callbacks.on_tool_start(start_message, tool_id)

        # Log start message to .messages.jsonl
        log_message = get_log_message()
        if log_message:
            log_message(
                role="tool_start",
                content={"tool_name": f.__name__, "args": args, "kwargs": kwargs},
                tool_id=tool_id,
            )

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

                if isinstance(message, SuccessMessage):
                    output_limit = get_tool_output_limit()
                    if len(message.text) > output_limit:
                        half_limit = output_limit // 2
                        first_part = message.text[:half_limit]
                        last_part = message.text[-half_limit:]
                        truncated_text = (
                            f"Tool emitted >{output_limit:,} characters of output.\n\n"
                            f"Here are the first {half_limit:,} characters:\n{first_part}\n\n"
                            f"And the last {half_limit:,} characters:\n{last_part}\n\n"
                            f"Consider invoking the tool with more specific parameters to produce less output."
                        )
                        message = SuccessMessage(text=truncated_text)

                await _process_message(message, callbacks, tool_id)
                if isinstance(message, (SuccessMessage, ErrorMessage)):
                    final_message = message
        except ErrorMessage as e:
            if callbacks:
                await callbacks.on_tool_error(e, tool_id)
            if log_message:
                log_message(
                    role="tool_result",
                    content={"result": e.text, "status": "error"},
                    tool_id=tool_id,
                )
            return e.text
        except Exception as e:
            error = ErrorMessage(
                text=f"Error: {e}",
                error=e,
                unexpected=True,
            )
            if callbacks:
                await callbacks.on_tool_error(error, tool_id)
            if log_message:
                log_message(
                    role="tool_result",
                    content={
                        "result": error.text,
                        "status": "error",
                        "unexpected": True,
                    },
                    tool_id=tool_id,
                )
            return error.text

        if final_message is None:
            error = ErrorMessage(
                text="Error: Tool did not yield a final result",
                unexpected=True,
            )
            if callbacks:
                await callbacks.on_tool_error(error, tool_id)
            if log_message:
                log_message(
                    role="tool_result",
                    content={"result": error.text, "status": "error"},
                    tool_id=tool_id,
                )
            return error.text

        # Log tool result to .messages.jsonl
        if log_message:
            log_message(
                role="tool_result",
                content={
                    "result": final_message.text,
                    "status": "success"
                    if isinstance(final_message, SuccessMessage)
                    else "error",
                },
                tool_id=tool_id,
            )

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


def load_tools():
    """Load all tools from plugins."""
    from mediagram.plugins import load_plugins, pm

    load_plugins()

    def register(tool_func):
        """Register a tool function."""
        if tool_func not in ALL_TOOLS:
            ALL_TOOLS.append(tool_func)

    pm.hook.register_tools(register=register)
