from datetime import datetime
from importlib.resources import files
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
import llm

from .tools import ALL_TOOLS
from mediagram.config import (
    AVAILABLE_MODELS,
    MIN_TOOL_OUTPUT_LIMIT,
    DEFAULT_MAX_TURNS,
    DEFAULT_TOOL_OUTPUT_LIMIT,
)

if TYPE_CHECKING:
    from .callbacks import DriverCallbacks
    from mediagram.media import MediaManager


def load_system_prompt_template() -> str:
    prompt_file = files("mediagram").joinpath("prompts/system.md")
    return prompt_file.read_text()


def get_user_info_text(name: str, username: str | None, language: str | None) -> str:
    parts = [f"Name: {name}"]
    if username:
        parts.append(f"Username: {username}")
    if language:
        parts.append(f"Language: {language}")
    return "\n".join(parts)


def render_system_prompt(
    template: str,
    name: str,
    username: str | None = None,
    language: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    remaining_turns: int | None = None,
) -> str:
    user_info = get_user_info_text(name, username, language)
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    if max_turns == 0:
        max_turns_text = "unlimited"
        remaining_turns_text = "unlimited"
    else:
        max_turns_text = str(max_turns)
        remaining_turns_text = str(
            remaining_turns if remaining_turns is not None else max_turns
        )

    return (
        template.replace("{{ user_information }}", user_info)
        .replace("{{ datetime }}", current_datetime)
        .replace("{{ max_turns }}", max_turns_text)
        .replace("{{ remaining_turns }}", remaining_turns_text)
    )


@dataclass
class AgentResponse:
    text: str
    error: str | None = None


class CommandRouter:
    """Routes commands to their handlers and provides help."""

    def __init__(self):
        self.commands: dict[str, Callable] = {}

    def register(self, name: str, handler: Callable) -> None:
        """Register a command handler."""
        self.commands[name] = handler

    def get_help(self) -> str:
        """Generate help text from all registered commands."""
        lines = ["Available commands:"]
        for name in sorted(self.commands.keys()):
            handler = self.commands[name]
            doc = handler.__doc__ or "No description"
            lines.append(f"  /{name} - {doc.strip()}")
        return "\n".join(lines)

    def route(self, command: str, args: list[str], agent: "Agent") -> AgentResponse:
        """Route a command to its handler."""
        if command == "help":
            return AgentResponse(text=self.get_help())

        if command not in self.commands:
            return AgentResponse(
                text=f"Unknown command: /{command}\n\n{self.get_help()}"
            )

        handler = self.commands[command]
        return handler(args)


class Agent:
    def __init__(
        self,
        model_name: str = "haiku",
        driver_callbacks: "DriverCallbacks | None" = None,
        media_manager: "MediaManager | None" = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
    ):
        self.model_name = model_name
        self.model_id = AVAILABLE_MODELS[model_name]
        self.model = llm.get_async_model(self.model_id)
        self.driver_callbacks = driver_callbacks
        self.media_manager = media_manager
        self.max_turns = max_turns
        self.tool_output_limit = tool_output_limit
        self.tools = list(ALL_TOOLS)
        self.conversation = self.model.conversation(
            tools=self.tools,
            before_call=self._before_tool_call,
            after_call=self._after_tool_call,
        )
        self.system_prompt_template = load_system_prompt_template()
        self.router = CommandRouter()
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        self.router.register("clear", self._cmd_clear)
        self.router.register("model", self._cmd_model)
        self.router.register("tools", self._cmd_tools)
        self.router.register("name", self._cmd_name)
        self.router.register("turns", self._cmd_turns)
        self.router.register("tlimit", self._cmd_tool_output_limit)

    async def _before_tool_call(self, tool, tool_call):
        """Hook called before a tool is executed."""
        from .tools import set_driver_callbacks, set_tool_subdir, set_tool_output_limit

        if self.driver_callbacks:
            set_driver_callbacks(self.driver_callbacks)

        if self.media_manager and self.media_manager.current_subdir:
            set_tool_subdir(self.media_manager.current_subdir)

        set_tool_output_limit(self.tool_output_limit)

    async def _after_tool_call(self, tool, tool_call, tool_result):
        """Hook called after a tool is executed."""
        pass

    def _cmd_clear(self, args: list[str]) -> AgentResponse:
        """Clear conversation history and start fresh"""
        self.conversation = self.model.conversation(
            tools=self.tools,
            before_call=self._before_tool_call,
            after_call=self._after_tool_call,
        )
        if self.media_manager:
            self.media_manager.reset_subdir()
        return AgentResponse(text="Chat history cleared. Starting a new conversation.")

    def _cmd_model(self, args: list[str]) -> AgentResponse:
        """Change or show current model (usage: /model [haiku|sonnet])"""
        if not args:
            return AgentResponse(
                text=f"Current model: {self.model_name}\nAvailable models: {', '.join(AVAILABLE_MODELS.keys())}"
            )

        model_name = args[0]
        if model_name not in AVAILABLE_MODELS:
            return AgentResponse(
                text=f"Unknown model: {model_name}\nAvailable models: {', '.join(AVAILABLE_MODELS.keys())}"
            )

        self.model_name = model_name
        self.model_id = AVAILABLE_MODELS[model_name]
        self.model = llm.get_async_model(self.model_id)
        self.conversation.model = self.model

        return AgentResponse(text=f"Model changed to: {model_name}")

    def _cmd_tools(self, args: list[str]) -> AgentResponse:
        """List all available tools"""
        if not self.tools:
            return AgentResponse(text="No tools available.")

        lines = ["Available tools:"]
        for tool in self.tools:
            tool_name = tool.__name__
            tool_doc = tool.__doc__ or "No description"
            tool_doc_clean = " ".join(line.strip() for line in tool_doc.split("\n"))

            import inspect

            sig = inspect.signature(tool)
            params = []
            for param_name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    params.append(
                        f"{param_name}: {self._format_annotation(param.annotation)}"
                    )
                else:
                    params.append(param_name)

            params_str = ", ".join(params)
            lines.append(f"\n  {tool_name}({params_str})")
            lines.append(f"    {tool_doc_clean}")

        return AgentResponse(text="\n".join(lines))

    def _format_annotation(self, annotation) -> str:
        """Format a type annotation for display."""
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")

    def _cmd_name(self, args: list[str]) -> AgentResponse:
        """Name the current conversation (usage: /name [name])"""
        if not self.media_manager:
            return AgentResponse(
                text="Media manager not available. Cannot name conversation."
            )

        name = " ".join(args) if args else None

        try:
            new_subdir = self.media_manager.rename_subdir(name)
            if name:
                return AgentResponse(text=f"Conversation named: {new_subdir.name}")
            else:
                return AgentResponse(
                    text=f"Conversation made permanent: {new_subdir.name}"
                )
        except ValueError as e:
            return AgentResponse(text=f"Error: {e}", error=str(e))

    def _cmd_turns(self, args: list[str]) -> AgentResponse:
        """Get or set maximum autonomous turns (usage: /turns [number], 0 = infinite)"""
        if not args:
            if self.max_turns == 0:
                return AgentResponse(text="Current max turns: infinite (0)")
            return AgentResponse(text=f"Current max turns: {self.max_turns}")

        try:
            new_turns = int(args[0])
            if new_turns < 0:
                return AgentResponse(
                    text="Error: turns must be 0 (infinite) or a positive number"
                )

            self.max_turns = new_turns
            if new_turns == 0:
                return AgentResponse(text="Max turns set to: infinite (0)")
            return AgentResponse(text=f"Max turns set to: {new_turns}")
        except ValueError:
            return AgentResponse(text="Error: turns must be a number (0 for infinite)")

    def _cmd_tool_output_limit(self, args: list[str]) -> AgentResponse:
        """Get or set tool output limit (usage: /tlimit [chars], min 128)"""
        if not args:
            return AgentResponse(
                text=f"Current tool output limit: {self.tool_output_limit} characters"
            )

        try:
            new_limit = int(args[0])
            if new_limit < MIN_TOOL_OUTPUT_LIMIT:
                return AgentResponse(
                    text=f"Error: tool output limit must be at least {MIN_TOOL_OUTPUT_LIMIT} characters"
                )

            self.tool_output_limit = new_limit
            return AgentResponse(
                text=f"Tool output limit set to: {new_limit} characters"
            )
        except ValueError:
            return AgentResponse(
                text=f"Error: limit must be a number (minimum {MIN_TOOL_OUTPUT_LIMIT})"
            )

    async def handle_message(
        self,
        message: str,
        name: str,
        username: str | None = None,
        language: str | None = None,
    ) -> AgentResponse:
        """
        Handle a message, which may be a command or a regular message.
        Returns an AgentResponse with the text to display to the user.
        """
        message = message.strip()

        # Log user message
        if self.media_manager:
            self.media_manager.log_message(
                role="user", content=message, name=name, username=username
            )

        # Route commands
        if message.startswith("/"):
            parts = message[1:].split(maxsplit=1)
            command = parts[0]
            args = parts[1].split() if len(parts) > 1 else []
            response = self.router.route(command, args, self)

            # Log command response
            if self.media_manager:
                self.media_manager.log_message(
                    role="command",
                    content=response.text,
                    command=command,
                    error=response.error,
                )
            return response

        # Regular message - run agentic loop
        try:
            # Initialize loop state
            remaining_turns = self.max_turns if self.max_turns > 0 else float("inf")
            current_message = message
            tool_results = None
            response_text = None
            had_tool_calls = False

            # Agent loop - continue while turns remain and tools are being called
            while remaining_turns > 0:
                # Update system prompt with current remaining_turns
                remaining_turns_int = (
                    int(remaining_turns) if remaining_turns != float("inf") else None
                )
                system_prompt = render_system_prompt(
                    self.system_prompt_template,
                    name,
                    username,
                    language,
                    self.max_turns,
                    remaining_turns_int,
                )

                # AsyncConversation.prompt() doesn't default tools like chain() does
                if tool_results is not None:
                    response = self.conversation.prompt(
                        current_message,
                        system=system_prompt,
                        tools=self.tools,
                        tool_results=tool_results,
                    )
                else:
                    response = self.conversation.prompt(
                        current_message, system=system_prompt, tools=self.tools
                    )

                # Get response text and tool calls
                response_text = await response.text()
                tool_calls = await response.tool_calls()

                # No tool calls means agent is done
                if not tool_calls:
                    break

                # Tools were called - execute them and continue
                had_tool_calls = True
                tool_results = await response.execute_tool_calls(
                    before_call=self._before_tool_call, after_call=self._after_tool_call
                )

                current_message = ""
                if self.max_turns > 0:
                    remaining_turns -= 1

            # Handle case where turns exhausted with pending work
            if self.max_turns > 0 and remaining_turns <= 0 and had_tool_calls:
                exhaustion_msg = "I ran out of autonomous turns before completing the task. Here's what I found:\n\n"
                response_text = exhaustion_msg + (response_text or "")

            if not response_text:
                response_text = "No response generated."

            if self.media_manager:
                self.media_manager.log_message(role="assistant", content=response_text)

            return AgentResponse(text=response_text)
        except Exception as e:
            error_response = AgentResponse(text="", error=str(e))
            if self.media_manager:
                self.media_manager.log_message(
                    role="error", content=str(e), error=str(e)
                )
            return error_response
