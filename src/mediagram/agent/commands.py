from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
import inspect
import shlex
from pathlib import Path

from mediagram.config import AVAILABLE_MODELS, MIN_TOOL_OUTPUT_LIMIT

if TYPE_CHECKING:
    from . import Agent


@dataclass
class AgentResponse:
    text: str
    error: str | None = None
    log_summary: str | None = None


class CommandRouter:
    _commands: dict[str, Callable] = {}

    def __init__(self, log_message: Callable):
        self.log_message = log_message

    @classmethod
    def register(cls, name: str, handler: Callable) -> None:
        cls._commands[name] = handler

    @property
    def commands(self) -> dict[str, Callable]:
        return self._commands

    def get_help(self) -> str:
        lines = ["Available commands:"]
        for name in sorted(self.commands.keys()):
            handler = self.commands[name]
            doc = handler.__doc__ or "No description"
            lines.append(f"  /{name} - {doc.strip()}")
        return "\n".join(lines)

    def handle(self, message: str, agent: "Agent") -> AgentResponse:
        if not message.startswith("/"):
            raise ValueError("Not a command")

        parts = message[1:].split(maxsplit=1)
        command = parts[0]
        args_string = parts[1] if len(parts) > 1 else ""

        if command == "help":
            response = AgentResponse(text=self.get_help())
        elif command not in self.commands:
            response = AgentResponse(
                text=f"Unknown command: /{command}\n\n{self.get_help()}"
            )
        else:
            handler = self.commands[command]
            response = handler(agent, args_string)

        log_content = response.log_summary if response.log_summary else response.text
        self.log_message(
            role="command",
            content=log_content,
            command=command,
            error=response.error,
        )
        return response


def command(name: str):
    def decorator(func: Callable) -> Callable:
        CommandRouter.register(name, func)
        return func

    return decorator


@command("clear")
def cmd_clear(agent: "Agent", args_string: str) -> AgentResponse:
    """Clear conversation history and start fresh"""
    agent.conversation = agent.model.conversation(
        tools=agent.tools,
        before_call=agent._before_tool_call,
        after_call=agent._after_tool_call,
    )
    agent.media_manager.reset_subdir()
    return AgentResponse(text="Chat history cleared. Starting a new conversation.")


@command("model")
def cmd_model(agent: "Agent", args_string: str) -> AgentResponse:
    """Change or show current model (usage: /model [haiku|sonnet])"""
    args = args_string.split()
    if not args:
        return AgentResponse(
            text=f"Current model: {agent.model_name}\nAvailable models: {', '.join(AVAILABLE_MODELS.keys())}"
        )

    model_name = args[0]
    if model_name not in AVAILABLE_MODELS:
        return AgentResponse(
            text=f"Unknown model: {model_name}\nAvailable models: {', '.join(AVAILABLE_MODELS.keys())}"
        )

    agent.model_name = model_name
    agent.model_id = AVAILABLE_MODELS[model_name]
    agent.model = agent._get_async_model(agent.model_id)
    agent.conversation.model = agent.model

    return AgentResponse(text=f"Model changed to: {model_name}")


@command("tools")
def cmd_tools(agent: "Agent", args_string: str) -> AgentResponse:
    """List all available tools, or show details for a specific tool (usage: /tools [name])"""
    if not agent.tools:
        return AgentResponse(text="No tools available.")

    tool_name = args_string.strip() if args_string else None

    if tool_name:
        tool = next((t for t in agent.tools if t.__name__ == tool_name), None)
        if not tool:
            return AgentResponse(text=f"Tool '{tool_name}' not found.")

        tool_doc = tool.__doc__ or "No description"
        tool_doc_clean = " ".join(line.strip() for line in tool_doc.split("\n"))

        sig = inspect.signature(tool)
        params = []
        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                params.append(f"{param_name}: {_format_annotation(param.annotation)}")
            else:
                params.append(param_name)

        params_str = ", ".join(params)
        return AgentResponse(text=f"{tool_name}({params_str})\n\n{tool_doc_clean}")

    lines = ["Available tools:"]
    for tool in agent.tools:
        sig = inspect.signature(tool)
        params = []
        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                params.append(f"{param_name}: {_format_annotation(param.annotation)}")
            else:
                params.append(param_name)

        params_str = ", ".join(params)
        lines.append(f"  {tool.__name__}({params_str})")

    return AgentResponse(text="\n".join(lines))


def _format_annotation(annotation) -> str:
    """Format a type annotation for display."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


@command("name")
def cmd_name(agent: "Agent", args_string: str) -> AgentResponse:
    """Name the current conversation (usage: /name [name])"""
    name = args_string.strip() if args_string else None

    try:
        new_subdir = agent.media_manager.rename_subdir(name)
        if name:
            return AgentResponse(text=f"Conversation named: {new_subdir.name}")
        else:
            return AgentResponse(text=f"Conversation made permanent: {new_subdir.name}")
    except ValueError as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))


@command("turns")
def cmd_turns(agent: "Agent", args_string: str) -> AgentResponse:
    """Get or set maximum autonomous turns (usage: /turns [number], 0 = infinite)"""
    args = args_string.split()
    if not args:
        if agent.max_turns == 0:
            return AgentResponse(text="Current max turns: infinite (0)")
        return AgentResponse(text=f"Current max turns: {agent.max_turns}")

    try:
        new_turns = int(args[0])
        if new_turns < 0:
            return AgentResponse(
                text="Error: turns must be 0 (infinite) or a positive number"
            )

        agent.max_turns = new_turns
        if new_turns == 0:
            return AgentResponse(text="Max turns set to: infinite (0)")
        return AgentResponse(text=f"Max turns set to: {new_turns}")
    except ValueError:
        return AgentResponse(text="Error: turns must be a number (0 for infinite)")


@command("tlimit")
def cmd_tool_output_limit(agent: "Agent", args_string: str) -> AgentResponse:
    """Get or set tool output limit (usage: /tlimit [chars], min 128)"""
    args = args_string.split()
    if not args:
        return AgentResponse(
            text=f"Current tool output limit: {agent.tool_output_limit} characters"
        )

    try:
        new_limit = int(args[0])
        if new_limit < MIN_TOOL_OUTPUT_LIMIT:
            return AgentResponse(
                text=f"Error: tool output limit must be at least {MIN_TOOL_OUTPUT_LIMIT} characters"
            )

        agent.tool_output_limit = new_limit
        return AgentResponse(text=f"Tool output limit set to: {new_limit} characters")
    except ValueError:
        return AgentResponse(
            text=f"Error: limit must be a number (minimum {MIN_TOOL_OUTPUT_LIMIT})"
        )


@command("tdetails")
def cmd_tool_details(agent: "Agent", args_string: str) -> AgentResponse:
    """Get or set tool details display (usage: /tdetails [on|off])"""
    args = args_string.split()
    if not args:
        status = "on" if agent.tool_details else "off"
        return AgentResponse(text=f"Tool details: {status}")

    arg = args[0].lower()
    if arg == "on":
        agent.tool_details = True
        return AgentResponse(text="Tool details enabled")
    elif arg == "off":
        agent.tool_details = False
        return AgentResponse(text="Tool details disabled")
    else:
        return AgentResponse(text="Error: argument must be 'on' or 'off'")


def _ensure_contained(agent: "Agent", path: str) -> Path:
    """Ensure path is contained within the media subdir."""
    subdir = agent.media_manager.current_subdir
    if not subdir:
        raise ValueError("No active media subdirectory")

    resolved = (subdir / path).resolve()
    subdir_resolved = subdir.resolve()
    if not str(resolved).startswith(str(subdir_resolved)):
        raise ValueError(f"Path {path} escapes subdir containment")

    return resolved


@command("read")
def cmd_read(agent: "Agent", args_string: str) -> AgentResponse:
    """Read a file from the media subdir (usage: /read <filename> [max_kb])"""
    try:
        args = shlex.split(args_string)
    except ValueError as e:
        return AgentResponse(text=f"Error parsing arguments: {e}", error=str(e))

    if not args:
        return AgentResponse(
            text="Error: filename required\nUsage: /read <filename> [max_kb]",
            error="Missing filename",
        )

    filename = args[0]
    max_kb = 8

    if len(args) > 1:
        try:
            max_kb = int(args[1])
        except ValueError:
            return AgentResponse(
                text=f"Error: max_kb must be a number, got '{args[1]}'",
                error="Invalid max_kb",
            )

    try:
        file_path = _ensure_contained(agent, filename)
    except ValueError as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))

    if not file_path.exists():
        return AgentResponse(
            text=f"Error: file does not exist: {filename}", error="File not found"
        )

    if not file_path.is_file():
        return AgentResponse(text=f"Error: not a file: {filename}", error="Not a file")

    file_size_bytes = file_path.stat().st_size
    file_size_kb = file_size_bytes / 1024

    if max_kb > 0 and file_size_kb > max_kb:
        return AgentResponse(
            text=f"Error: {filename} is {file_size_kb:.1f}KB, larger than {max_kb}KB limit",
            error="File too large",
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return AgentResponse(
            text=f"Error: {filename} is not a text file", error="Not a text file"
        )
    except Exception as e:
        return AgentResponse(text=f"Error reading file: {e}", error=str(e))

    log_summary = f"Read {filename} ({file_size_kb:.1f}KB)"
    return AgentResponse(text=content, log_summary=log_summary)


@command("send")
def cmd_send(agent: "Agent", args_string: str) -> AgentResponse:
    """Send a file to the user's driver (usage: /send <filename> [max_kb])"""
    try:
        args = shlex.split(args_string)
    except ValueError as e:
        return AgentResponse(text=f"Error parsing arguments: {e}", error=str(e))

    if not args:
        return AgentResponse(
            text="Error: filename required\nUsage: /send <filename> [max_kb]",
            error="Missing filename",
        )

    filename = args[0]
    max_kb = 2 * 1024 * 1024

    if len(args) > 1:
        try:
            max_kb = int(args[1])
        except ValueError:
            return AgentResponse(
                text=f"Error: max_kb must be a number, got '{args[1]}'",
                error="Invalid max_kb",
            )

    try:
        file_path = _ensure_contained(agent, filename)
    except ValueError as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))

    if not file_path.exists():
        return AgentResponse(
            text=f"Error: file does not exist: {filename}", error="File not found"
        )

    if not file_path.is_file():
        return AgentResponse(text=f"Error: not a file: {filename}", error="Not a file")

    file_size_bytes = file_path.stat().st_size
    file_size_kb = file_size_bytes / 1024

    if max_kb > 0 and file_size_kb > max_kb:
        return AgentResponse(
            text=f"Error: {filename} is {file_size_kb:.1f}KB, larger than {max_kb}KB limit",
            error="File too large",
        )

    if not hasattr(agent.driver_callbacks, "send_file"):
        return AgentResponse(
            text="Error: file sending not supported by current driver",
            error="Driver doesn't support send_file",
        )

    try:
        result_message = agent.driver_callbacks.send_file(file_path)
        log_summary = f"Sent {filename} ({file_size_kb:.1f}KB)"
        return AgentResponse(text=result_message, log_summary=log_summary)
    except Exception as e:
        return AgentResponse(text=f"Error sending file: {e}", error=str(e))


@command("ls")
def cmd_ls(agent: "Agent", args_string: str) -> AgentResponse:
    """List directory contents in the media subdir (usage: /ls [path])"""
    args = args_string.split()
    path_arg = args[0] if args else None

    try:
        subdir = agent.media_manager.current_subdir
        if not subdir:
            return AgentResponse(
                text="Error: no active media subdirectory", error="No subdir"
            )

        if path_arg:
            target = _ensure_contained(agent, path_arg)
        else:
            target = subdir

        if not target.exists():
            return AgentResponse(
                text=f"Error: directory does not exist: {path_arg or '.'}",
                error="Directory not found",
            )

        if not target.is_dir():
            return AgentResponse(
                text=f"Error: not a directory: {path_arg or '.'}",
                error="Not a directory",
            )

        lines = []
        for item in sorted(target.iterdir()):
            rel_path = item.relative_to(subdir)
            if item.name.startswith("."):
                continue

            if item.is_symlink():
                type_str = "symlink"
                size = 0
            elif item.is_dir():
                type_str = "dir"
                size = 0
            elif item.is_file():
                type_str = "file"
                size = item.stat().st_size
            else:
                type_str = "other"
                size = 0

            lines.append(f"{rel_path}  {size:>10}  {type_str}")

        if lines:
            return AgentResponse(text="\n".join(lines))
        else:
            return AgentResponse(text="(empty directory)")

    except ValueError as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))
    except Exception as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))
