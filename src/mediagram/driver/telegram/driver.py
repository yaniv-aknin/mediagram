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
from mediagram.agent.callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from mediagram.media import MediaManager
from .html import convert_to_telegram_html


class TelegramDriver:
    """Thin adapter layer for Telegram - handles message routing and formatting."""

    def __init__(
        self, default_model: str = "haiku", media_dir_override: str | None = None
    ):
        self.default_model = default_model
        self.media_dir_override = media_dir_override
        self.user_agents: dict[int, Agent] = {}
        self.user_media_managers: dict[int, MediaManager] = {}
        self.current_update: Update | None = None
        self.current_context: ContextTypes.DEFAULT_TYPE | None = None
        self.progress_messages: dict[str, int] = {}

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        """Handle tool progress updates."""
        if not self.current_update or not self.current_context:
            return

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
        message = f"🔄 {progress.text}{percentage}{eta}"

        try:
            if tool_id in self.progress_messages:
                await self.current_context.bot.edit_message_text(
                    chat_id=self.current_update.effective_chat.id,
                    message_id=self.progress_messages[tool_id],
                    text=message,
                )
            else:
                sent = await self.current_context.bot.send_message(
                    chat_id=self.current_update.effective_chat.id, text=message
                )
                self.progress_messages[tool_id] = sent.message_id
        except TelegramError:
            pass

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        """Handle tool success."""
        if not self.current_update or not self.current_context:
            return

        try:
            if tool_id in self.progress_messages:
                await self.current_context.bot.delete_message(
                    chat_id=self.current_update.effective_chat.id,
                    message_id=self.progress_messages[tool_id],
                )
                del self.progress_messages[tool_id]
            await self.current_context.bot.send_message(
                chat_id=self.current_update.effective_chat.id,
                text=f"✅ {success.text}",
            )
        except TelegramError:
            pass

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        """Handle tool errors."""
        if not self.current_update or not self.current_context:
            return

        details = f" - {error.error}" if error.error else ""
        try:
            if tool_id in self.progress_messages:
                await self.current_context.bot.delete_message(
                    chat_id=self.current_update.effective_chat.id,
                    message_id=self.progress_messages[tool_id],
                )
                del self.progress_messages[tool_id]
            await self.current_context.bot.send_message(
                chat_id=self.current_update.effective_chat.id,
                text=f"❌ {error.text}{details}",
            )
        except TelegramError:
            pass

    def _get_or_create_agent(self, user_id: int) -> Agent:
        if user_id not in self.user_agents:
            media_manager = MediaManager.create(self.media_dir_override)
            self.user_media_managers[user_id] = media_manager
            self.user_agents[user_id] = Agent(
                self.default_model, driver_callbacks=self, media_manager=media_manager
            )
        return self.user_agents[user_id]

    async def message_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Route message to agent and send response back to Telegram."""
        self.current_update = update
        self.current_context = context

        user_id = update.effective_user.id
        user_message = update.message.text
        user = update.effective_user

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

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


def run(model: str = "haiku", media_dir_override: str | None = None) -> None:
    driver = TelegramDriver(default_model=model, media_dir_override=media_dir_override)
    driver.run()
