from datetime import datetime
from importlib.resources import files
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING
import llm

from .tools import ALL_TOOLS

if TYPE_CHECKING:
    from .callbacks import DriverCallbacks


AVAILABLE_MODELS = {
    "haiku": "claude-haiku-4.5",
    "sonnet": "claude-sonnet-4.5",
}


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
    template: str, name: str, username: str | None = None, language: str | None = None
) -> str:
    user_info = get_user_info_text(name, username, language)
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    return template.replace("{{ user_information }}", user_info).replace(
        "{{ datetime }}", current_datetime
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
    ):
        self.model_name = model_name
        self.model_id = AVAILABLE_MODELS[model_name]
        self.model = llm.get_async_model(self.model_id)
        self.driver_callbacks = driver_callbacks
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

    async def _before_tool_call(self, tool, tool_call):
        """Hook called before a tool is executed."""
        from .tools import set_driver_callbacks

        if self.driver_callbacks:
            set_driver_callbacks(self.driver_callbacks)

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
                    params.append(f"{param_name}: {param.annotation.__name__}")
                else:
                    params.append(param_name)

            params_str = ", ".join(params)
            lines.append(f"\n  {tool_name}({params_str})")
            lines.append(f"    {tool_doc_clean}")

        return AgentResponse(text="\n".join(lines))

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

        # Route commands
        if message.startswith("/"):
            parts = message[1:].split(maxsplit=1)
            command = parts[0]
            args = parts[1].split() if len(parts) > 1 else []
            return self.router.route(command, args, self)

        # Regular message - get response from Claude
        try:
            system_prompt = render_system_prompt(
                self.system_prompt_template, name, username, language
            )
            chain_response = self.conversation.chain(message, system=system_prompt)
            response_text = await chain_response.text()
            return AgentResponse(text=response_text)
        except Exception as e:
            return AgentResponse(text="", error=str(e))
