import asyncio
import os
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from mediagram.agent import Agent


class CLIDriver:
    """Thin adapter layer for CLI - handles terminal I/O."""

    def __init__(self, default_model: str = "haiku"):
        self.agent = Agent(default_model)
        self.session = PromptSession(history=InMemoryHistory())
        self.username = os.getenv("USER", "user")
        self.name = self.username

    def _print_welcome(self) -> None:
        print(f"Mediagram CLI - Using model: {self.agent.model_name}")
        print("Type your messages or use commands:")
        print("  /help - Show all available commands")
        print("  /quit or /exit - Exit the program")
        print()

    async def run_async(self) -> None:
        self._print_welcome()

        while True:
            try:
                user_input = await self.session.prompt_async("You: ")

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

            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")

    def run(self) -> None:
        asyncio.run(self.run_async())


def run(model: str = "haiku") -> None:
    driver = CLIDriver(default_model=model)
    driver.run()
