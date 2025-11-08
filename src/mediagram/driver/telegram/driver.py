import os
import mistune
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

from mediagram.agent import Agent
from .html import convert_to_telegram_html


class TelegramDriver:
    """Thin adapter layer for Telegram - handles message routing and formatting."""

    def __init__(self, default_model: str = "haiku"):
        self.default_model = default_model
        self.user_agents: dict[int, Agent] = {}

    def _get_or_create_agent(self, user_id: int) -> Agent:
        if user_id not in self.user_agents:
            self.user_agents[user_id] = Agent(self.default_model)
        return self.user_agents[user_id]

    async def message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Route message to agent and send response back to Telegram."""
        user_id = update.effective_user.id
        user_message = update.message.text
        user = update.effective_user

        agent = self._get_or_create_agent(user_id)

        # Let agent handle the message (commands or regular messages)
        response = await agent.handle_message(
            user_message,
            name=user.full_name,
            username=user.username,
            language=user.language_code,
        )

        # Handle errors
        if response.error:
            await update.message.reply_text(f"Error: {response.error}")
            return

        # Convert Markdown to HTML for Telegram
        try:
            # mistune.html with default settings escapes HTML, preventing arbitrary HTML injection
            html_text = mistune.html(response.text)
            # Convert to Telegram-compatible HTML using proper HTML parsing
            html_text = convert_to_telegram_html(html_text)
            await update.message.reply_text(html_text, parse_mode=ParseMode.HTML)
        except TelegramError as e:
            # If HTML rendering fails, show a proper error message
            await update.message.reply_text(
                f"⚠️ There was an error processing your request: {e}"
            )

    def run(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

        app = ApplicationBuilder().token(token).build()

        # All text messages (including commands) go through the agent
        app.add_handler(MessageHandler(filters.TEXT, self.message_handler))

        print(f"Starting Telegram bot with model: {self.default_model}")
        app.run_polling()


def run(model: str = "haiku") -> None:
    driver = TelegramDriver(default_model=model)
    driver.run()
