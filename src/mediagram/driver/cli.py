import asyncio
import os
from typing import Protocol
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from mediagram.agent import Agent
from mediagram.agent.callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from mediagram.media import MediaManager
from mediagram.config import DEFAULT_MAX_TURNS, DEFAULT_TOOL_OUTPUT_LIMIT


class InputSource(Protocol):
    """Protocol for input sources that provide user messages."""

    async def get_input(self, prompt: str) -> str | None:
        """Get next input. Returns None to signal EOF."""
        ...


class InteractiveInputSource:
    """Interactive input source using prompt_toolkit."""

    def __init__(self) -> None:
        self.session = PromptSession(history=InMemoryHistory())

    async def get_input(self, prompt: str) -> str | None:
        try:
            return await self.session.prompt_async(prompt)
        except (KeyboardInterrupt, EOFError):
            return None


class PreDefinedInputSource:
    """Pre-defined input source from a list of messages."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        self.index = 0

    async def get_input(self, prompt: str) -> str | None:
        if self.index >= len(self.messages):
            return None
        message = self.messages[self.index]
        self.index += 1
        print(f"{prompt}{message}")
        return message


class CLIDriver:
    """Thin adapter layer for CLI - handles terminal I/O."""

    def __init__(
        self,
        default_model: str = "haiku",
        input_source: InputSource | None = None,
        media_dir_override: str | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
    ):
        self.media_manager = MediaManager.create(media_dir_override)
        self.media_manager.create_subdir()
        self.agent = Agent(
            media_manager=self.media_manager,
            model_name=default_model,
            driver_callbacks=self,
            max_turns=max_turns,
            tool_output_limit=tool_output_limit,
        )
        self.input_source = input_source or InteractiveInputSource()
        self.username = os.getenv("USER", "user")
        self.name = self.username

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        """Handle tool progress updates."""
        percentage = (
            f" ({progress.completion_ratio * 100:.0f}%)"
            if progress.completion_ratio is not None
            else ""
        )
        eta = (
            f" - ETA: {progress.completion_eta_minutes:.1f}m"
            if progress.completion_eta_minutes is not None
            else ""
        )
        print(f"🔄 {progress.text}{percentage}{eta}")

    def _format_message(self, text: str, is_success: bool) -> str:
        emoji = "✅" if is_success else "❌"
        if "\n" in text:
            indented = "\n".join(f"   {line}" for line in text.split("\n"))
            return f"{emoji}\n{indented}"
        else:
            return f"{emoji} {text}"

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        """Handle tool success."""
        print(self._format_message(success.text, is_success=True))

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        """Handle tool errors."""
        details = f" - {error.error}" if error.error else ""
        full_text = f"{error.text}{details}"
        print(self._format_message(full_text, is_success=False))

    def _print_welcome(self) -> None:
        print(f"Mediagram CLI - Using model: {self.agent.model_name}")
        print("Type your messages or use commands:")
        print("  /help - Show all available commands")
        print("  /quit or /exit - Exit the program")
        print()

    async def run_async(self) -> None:
        self._print_welcome()

        try:
            while True:
                try:
                    user_input = await self.input_source.get_input("You: ")

                    if user_input is None:
                        print("Goodbye!")
                        break

                    if not user_input.strip():
                        continue

                    # Handle CLI-specific exit commands
                    if user_input.strip() in ["/quit", "/exit"]:
                        print("Goodbye!")
                        break

                    # Let agent handle the message (commands or regular messages)
                    response = await self.agent.handle_message(
                        user_input, name=self.name, username=self.username
                    )

                    # Handle errors
                    if response.error:
                        print(f"Error: {response.error}")
                        continue

                    # Display response
                    print(f"Bot: {response.text}\n")

                except Exception as e:
                    print(f"Unexpected error: {e}")
                    break
        finally:
            self.media_manager.cleanup()

    def run(self) -> None:
        asyncio.run(self.run_async())


def run(
    model: str = "haiku",
    input_source: InputSource | None = None,
    media_dir_override: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
) -> None:
    driver = CLIDriver(
        default_model=model,
        input_source=input_source,
        media_dir_override=media_dir_override,
        max_turns=max_turns,
        tool_output_limit=tool_output_limit,
    )
    driver.run()
