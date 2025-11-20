import os
import mistune
from pathlib import Path
from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
)

from mediagram.agent import Agent
from mediagram.agent.callbacks import (
    ProgressMessage,
    SuccessMessage,
    ErrorMessage,
    StartMessage,
)
from mediagram.agent.commands import CommandRouter
from mediagram.media import MediaManager
from mediagram.config import (
    DEFAULT_MAX_TURNS,
    DEFAULT_TOOL_OUTPUT_LIMIT,
    DEFAULT_TOOL_DETAILS,
)
from .html import convert_to_telegram_html


class TelegramDriver:
    """Thin adapter layer for Telegram - handles message routing and formatting."""

    def __init__(
        self,
        default_model: str = "haiku",
        media_dir_override: str | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
        tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
        tool_details: bool = DEFAULT_TOOL_DETAILS,
    ):
        self.default_model = default_model
        self.media_dir_override = media_dir_override
        self.max_turns = max_turns
        self.tool_output_limit = tool_output_limit
        self.tool_details = tool_details
        self.user_agents: dict[int, Agent] = {}
        self.user_media_managers: dict[int, MediaManager] = {}
        self.current_update: Update | None = None
        self.current_context: ContextTypes.DEFAULT_TYPE | None = None
        self.progress_messages: dict[str, int] = {}

    async def on_tool_start(self, start: StartMessage, tool_id: str) -> None:
        """Handle tool start notification."""
        if not self.current_update or not self.current_context:
            return

        try:
            if self.tool_details:
                details = f" - args: {start.invocation_details['args']}, kwargs: {start.invocation_details['kwargs']}"
                message = f"🔧 Starting {start.tool_name}{details}"
            else:
                message = f"🔧 Starting {start.tool_name}"

            sent = await self.current_context.bot.send_message(
                chat_id=self.current_update.effective_chat.id, text=message
            )
            self.progress_messages[tool_id] = sent.message_id
        except TelegramError:
            pass

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

    async def send_file_async(self, file_path: Path) -> str:
        """Send file to user via Telegram (async version)."""
        if not self.current_update or not self.current_context:
            return "Error: cannot send file, no active Telegram context"

        try:
            file_size_kb = file_path.stat().st_size / 1024
            await self.current_context.bot.send_document(
                chat_id=self.current_update.effective_chat.id,
                document=file_path,
                filename=file_path.name,
            )
            return f"Sent {file_path.name} ({file_size_kb:.1f}KB)"
        except Exception as e:
            return f"Error sending file: {e}"

    def send_file(self, file_path: Path) -> str:
        """Send file to user via Telegram (sync wrapper for command handlers)."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.send_file_async(file_path))
                file_size_kb = file_path.stat().st_size / 1024
                return f"Sending {file_path.name} ({file_size_kb:.1f}KB)"
            else:
                return asyncio.run(self.send_file_async(file_path))
        except Exception as e:
            return f"Error sending file: {e}"

    def _get_or_create_agent(self, user_id: int) -> Agent:
        if user_id not in self.user_agents:
            media_manager = MediaManager.create(self.media_dir_override)
            media_manager.create_subdir()
            self.user_media_managers[user_id] = media_manager
            self.user_agents[user_id] = Agent(
                media_manager=media_manager,
                model_name=self.default_model,
                driver_callbacks=self,
                max_turns=self.max_turns,
                tool_output_limit=self.tool_output_limit,
                tool_details=self.tool_details,
            )
        return self.user_agents[user_id]

    def _get_telegram_commands(self) -> list[BotCommand]:
        """Build list of BotCommand objects from registered command handlers."""
        commands = []
        dummy_media_manager = MediaManager.create(self.media_dir_override)
        router = CommandRouter(dummy_media_manager.log_message)

        for name, handler in sorted(router.commands.items()):
            doc = handler.__doc__ or "No description"
            description = doc.strip().split("\n")[0]
            if len(description) > 256:
                description = description[:253] + "..."
            commands.append(BotCommand(command=name, description=description))

        commands.append(
            BotCommand(command="help", description="Show all available commands")
        )
        return commands

    async def file_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle file uploads by saving them to the current media subdir."""
        self.current_update = update
        self.current_context = context

        user_id = update.effective_user.id
        self._get_or_create_agent(user_id)
        media_manager = self.user_media_managers[user_id]

        if not media_manager.current_subdir:
            await update.message.reply_text("Error: No active media subdirectory")
            return

        document = update.message.document
        if not document:
            await update.message.reply_text("Error: No file found in message")
            return

        try:
            file = await context.bot.get_file(document.file_id)
            file_path = media_manager.current_subdir / document.file_name
            await file.download_to_drive(file_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Error saving file: {e}")

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

    async def post_init(self, application) -> None:
        """Register commands with Telegram after bot initialization."""
        commands = self._get_telegram_commands()
        try:
            await application.bot.set_my_commands(commands)
            print(f"Registered {len(commands)} commands with Telegram")
        except Exception as e:
            print(f"Warning: Failed to register commands with Telegram: {e}")

    def run(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

        app = ApplicationBuilder().token(token).post_init(self.post_init).build()

        # Handle file uploads
        app.add_handler(MessageHandler(filters.Document.ALL, self.file_handler))

        # All text messages (including commands) go through the agent
        app.add_handler(MessageHandler(filters.TEXT, self.message_handler))

        print(f"Starting Telegram bot with model: {self.default_model}")
        app.run_polling()


def run(
    model: str = "haiku",
    media_dir_override: str | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    tool_output_limit: int = DEFAULT_TOOL_OUTPUT_LIMIT,
    tool_details: bool = DEFAULT_TOOL_DETAILS,
) -> None:
    driver = TelegramDriver(
        default_model=model,
        media_dir_override=media_dir_override,
        max_turns=max_turns,
        tool_output_limit=tool_output_limit,
        tool_details=tool_details,
    )
    driver.run()
