from datetime import datetime
from importlib.resources import files
from typing import TYPE_CHECKING
import llm

from .tools import ALL_TOOLS, load_tools
from .commands import CommandRouter, AgentResponse
from mediagram.config import (
    AVAILABLE_MODELS,
    DEFAULT_MAX_TURNS,
    DEFAULT_TOOL_OUTPUT_LIMIT,
    DEFAULT_TOOL_DETAILS,
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


class Agent:
    def __init__(
        self,
        media_manager: "MediaManager",
        model_name: str = "haiku",
        driver_callbacks: "DriverCallbacks | None" = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
        tool_details: bool = DEFAULT_TOOL_DETAILS,
    ):
        self.model_name = model_name
        self.model_id = AVAILABLE_MODELS[model_name]
        self.model = self._get_async_model(self.model_id)
        self.driver_callbacks = driver_callbacks
        self.media_manager = media_manager
        self.max_turns = max_turns
        self.tool_output_limit = tool_output_limit
        self.tool_details = tool_details
        load_tools()
        self.tools = list(ALL_TOOLS)
        self.conversation = self.model.conversation(
            tools=self.tools,
            before_call=self._before_tool_call,
            after_call=self._after_tool_call,
        )
        self.system_prompt_template = load_system_prompt_template()
        self.router = CommandRouter(media_manager.log_message)

    def _get_async_model(self, model_id: str):
        """Get an async model instance."""
        return llm.get_async_model(model_id)

    async def _before_tool_call(self, tool, tool_call):
        """Hook called before a tool is executed."""
        from .tools import (
            set_driver_callbacks,
            set_tool_subdir,
            set_tool_output_limit,
            set_log_message,
        )

        if self.driver_callbacks:
            set_driver_callbacks(self.driver_callbacks)

        if self.media_manager.current_subdir:
            set_tool_subdir(self.media_manager.current_subdir)

        set_tool_output_limit(self.tool_output_limit)
        set_log_message(self.media_manager.log_message)

    async def _after_tool_call(self, tool, tool_call, tool_result):
        """Hook called after a tool is executed."""
        pass

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

        self.media_manager.log_message(
            role="user", content=message, name=name, username=username
        )

        if message.startswith("/"):
            return self.router.handle(message, self)

        try:
            remaining_turns = self.max_turns if self.max_turns > 0 else float("inf")
            current_message = message
            tool_results = None
            response_text = None
            had_tool_calls = False

            while remaining_turns > 0:
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

                response_text = await response.text()
                tool_calls = await response.tool_calls()

                if not tool_calls:
                    break

                had_tool_calls = True
                tool_results = await response.execute_tool_calls(
                    before_call=self._before_tool_call, after_call=self._after_tool_call
                )

                current_message = ""
                if self.max_turns > 0:
                    remaining_turns -= 1

            if self.max_turns > 0 and remaining_turns <= 0 and had_tool_calls:
                exhaustion_msg = "I ran out of autonomous turns before completing the task. Here's what I found:\n\n"
                response_text = exhaustion_msg + (response_text or "")

            if not response_text:
                response_text = "No response generated."

            self.media_manager.log_message(role="assistant", content=response_text)

            return AgentResponse(text=response_text)
        except Exception as e:
            error_response = AgentResponse(text="", error=str(e))
            self.media_manager.log_message(role="error", content=str(e), error=str(e))
            return error_response
