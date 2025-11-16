from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
import inspect

from mediagram.config import AVAILABLE_MODELS, MIN_TOOL_OUTPUT_LIMIT

if TYPE_CHECKING:
    from . import Agent


@dataclass
class AgentResponse:
    text: str
    error: str | None = None


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
        args = parts[1].split() if len(parts) > 1 else []

        if command == "help":
            response = AgentResponse(text=self.get_help())
        elif command not in self.commands:
            response = AgentResponse(
                text=f"Unknown command: /{command}\n\n{self.get_help()}"
            )
        else:
            handler = self.commands[command]
            response = handler(agent, args)

        self.log_message(
            role="command",
            content=response.text,
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
def cmd_clear(agent: "Agent", args: list[str]) -> AgentResponse:
    """Clear conversation history and start fresh"""
    agent.conversation = agent.model.conversation(
        tools=agent.tools,
        before_call=agent._before_tool_call,
        after_call=agent._after_tool_call,
    )
    agent.media_manager.reset_subdir()
    return AgentResponse(text="Chat history cleared. Starting a new conversation.")


@command("model")
def cmd_model(agent: "Agent", args: list[str]) -> AgentResponse:
    """Change or show current model (usage: /model [haiku|sonnet])"""
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
def cmd_tools(agent: "Agent", args: list[str]) -> AgentResponse:
    """List all available tools"""
    if not agent.tools:
        return AgentResponse(text="No tools available.")

    lines = ["Available tools:"]
    for tool in agent.tools:
        tool_name = tool.__name__
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
        lines.append(f"\n  {tool_name}({params_str})")
        lines.append(f"    {tool_doc_clean}")

    return AgentResponse(text="\n".join(lines))


def _format_annotation(annotation) -> str:
    """Format a type annotation for display."""
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation).replace("typing.", "")


@command("name")
def cmd_name(agent: "Agent", args: list[str]) -> AgentResponse:
    """Name the current conversation (usage: /name [name])"""
    name = " ".join(args) if args else None

    try:
        new_subdir = agent.media_manager.rename_subdir(name)
        if name:
            return AgentResponse(text=f"Conversation named: {new_subdir.name}")
        else:
            return AgentResponse(text=f"Conversation made permanent: {new_subdir.name}")
    except ValueError as e:
        return AgentResponse(text=f"Error: {e}", error=str(e))


@command("turns")
def cmd_turns(agent: "Agent", args: list[str]) -> AgentResponse:
    """Get or set maximum autonomous turns (usage: /turns [number], 0 = infinite)"""
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
def cmd_tool_output_limit(agent: "Agent", args: list[str]) -> AgentResponse:
    """Get or set tool output limit (usage: /tlimit [chars], min 128)"""
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
def cmd_tool_details(agent: "Agent", args: list[str]) -> AgentResponse:
    """Get or set tool details display (usage: /tdetails [on|off])"""
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
