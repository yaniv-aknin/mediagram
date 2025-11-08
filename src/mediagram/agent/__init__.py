from datetime import datetime
from importlib.resources import files
from dataclasses import dataclass
from typing import Callable
import llm


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
        return handler(agent, args)


class Agent:
    def __init__(self, model_name: str = "haiku"):
        self.model_name = model_name
        self.model_id = AVAILABLE_MODELS[model_name]
        self.model = llm.get_async_model(self.model_id)
        self.conversation = self.model.conversation()
        self.system_prompt_template = load_system_prompt_template()
        self.router = CommandRouter()
        self._register_commands()

    def _register_commands(self) -> None:
        """Register all available commands."""
        self.router.register("clear", self._cmd_clear)
        self.router.register("model", self._cmd_model)

    def _cmd_clear(self, args: list[str]) -> AgentResponse:
        """Clear conversation history and start fresh"""
        self.conversation = self.model.conversation()
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
        self.conversation = self.model.conversation()

        return AgentResponse(
            text=f"Model changed to: {model_name}\nNote: Conversation history has been cleared."
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
            response = self.conversation.prompt(message, system=system_prompt)
            response_text = await response.text()
            return AgentResponse(text=response_text)
        except Exception as e:
            return AgentResponse(text="", error=str(e))
