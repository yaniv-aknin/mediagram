import os
import time
import asyncio
import mistune
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, BotCommand
from pyrogram.enums import ChatAction, ParseMode
from pyrogram.errors import RPCError
from pyrogram.handlers import MessageHandler

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
from .file_sender import send_file_with_progress


class TelegramDriver:
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
        self.current_chat_id: int | None = None
        self.current_message_id: int | None = None
        self.progress_messages: dict[str, int] = {}
        self.last_action_time: dict[int, float] = {}

        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

        if not self.api_id or not self.api_hash:
            raise ValueError(
                "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set. "
                "Get them from https://my.telegram.org"
            )
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN must be set")

        session_dir = Path(
            os.getenv("PYROGRAM_SESSION", str(Path.home() / ".mediagram.d"))
        )
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = str(session_dir / "mediagram_bot")

        self.app = Client(
            session_path,
            api_id=int(self.api_id),
            api_hash=self.api_hash,
            bot_token=self.bot_token,
        )

    def _register_handlers(self):
        self.app.add_handler(
            MessageHandler(self.file_handler, filters.document & filters.private)
        )
        self.app.add_handler(
            MessageHandler(self.message_handler, filters.text & filters.private)
        )

    async def _refresh_chat_action(self, chat_id: int, action: ChatAction):
        current_time = time.time()
        if (
            chat_id not in self.last_action_time
            or (current_time - self.last_action_time[chat_id]) >= 4
        ):
            try:
                await self.app.send_chat_action(chat_id, action)
                self.last_action_time[chat_id] = current_time
            except RPCError:
                pass

    async def on_tool_start(self, start: StartMessage, tool_id: str) -> None:
        if not self.current_chat_id:
            return

        await self._refresh_chat_action(self.current_chat_id, ChatAction.TYPING)

        try:
            if self.tool_details:
                details = f" - args: {start.invocation_details['args']}, kwargs: {start.invocation_details['kwargs']}"
                message = f"Starting {start.tool_name}{details}"
            else:
                message = f"Starting {start.tool_name}"

            sent = await self.app.send_message(
                chat_id=self.current_chat_id, text=message
            )
            self.progress_messages[tool_id] = sent.id
        except RPCError:
            pass

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        if not self.current_chat_id:
            return

        await self._refresh_chat_action(self.current_chat_id, ChatAction.TYPING)

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
        message = f"{progress.text}{percentage}{eta}"

        try:
            if tool_id in self.progress_messages:
                await self.app.edit_message_text(
                    chat_id=self.current_chat_id,
                    message_id=self.progress_messages[tool_id],
                    text=message,
                )
            else:
                sent = await self.app.send_message(
                    chat_id=self.current_chat_id, text=message
                )
                self.progress_messages[tool_id] = sent.id
        except RPCError:
            pass

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        if not self.current_chat_id:
            return

        try:
            if tool_id in self.progress_messages:
                await self.app.delete_messages(
                    chat_id=self.current_chat_id,
                    message_ids=self.progress_messages[tool_id],
                )
                del self.progress_messages[tool_id]
            await self.app.send_message(
                chat_id=self.current_chat_id,
                text=success.text,
            )
        except RPCError:
            pass

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        if not self.current_chat_id:
            return

        details = f" - {error.error}" if error.error else ""
        try:
            if tool_id in self.progress_messages:
                await self.app.delete_messages(
                    chat_id=self.current_chat_id,
                    message_ids=self.progress_messages[tool_id],
                )
                del self.progress_messages[tool_id]
            await self.app.send_message(
                chat_id=self.current_chat_id,
                text=f"{error.text}{details}",
            )
        except RPCError:
            pass

    async def send_file_async(self, file_path: Path) -> str:
        if not self.current_chat_id:
            return "Error: cannot send file, no active Telegram context"

        try:
            return await send_file_with_progress(
                self.app, self.current_chat_id, file_path, self.last_action_time
            )
        except Exception as e:
            return f"Error sending file: {e}"

    def send_file(self, file_path: Path) -> str:
        try:
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self.send_file_async(file_path))
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                return f"Sending {file_path.name} ({file_size_mb:.1f}MB)"
            except RuntimeError:
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

    async def _register_bot_commands(self):
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

        try:
            await self.app.set_bot_commands(commands)
            print(f"Registered {len(commands)} commands with Telegram")
        except Exception as e:
            print(f"Warning: Failed to register commands with Telegram: {e}")

    async def file_handler(self, client: Client, message: Message) -> None:
        self.current_chat_id = message.chat.id
        self.current_message_id = message.id

        user_id = message.from_user.id
        self._get_or_create_agent(user_id)
        media_manager = self.user_media_managers[user_id]

        if not media_manager.current_subdir:
            await message.reply_text("Error: No active media subdirectory")
            return

        document = message.document
        if not document:
            await message.reply_text("Error: No file found in message")
            return

        try:
            file_path = media_manager.current_subdir / document.file_name
            await client.download_media(message, file_name=str(file_path))
        except Exception as e:
            await message.reply_text(f"Error saving file: {e}")

    def _split_message(self, text: str, max_length: int) -> list[str]:
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        for line in text.split("\n"):
            if not current_chunk:
                if len(line) <= max_length:
                    current_chunk = line
                else:
                    chunks.append(line[:max_length])
                    current_chunk = line[max_length:]
            elif len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += "\n" + line
            else:
                chunks.append(current_chunk)
                current_chunk = line

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def message_handler(self, client: Client, message: Message) -> None:
        self.current_chat_id = message.chat.id
        self.current_message_id = message.id

        user_id = message.from_user.id
        user_message = message.text
        user = message.from_user

        await client.send_chat_action(message.chat.id, ChatAction.TYPING)
        self.last_action_time[message.chat.id] = time.time()

        agent = self._get_or_create_agent(user_id)

        full_name = user.first_name
        if user.last_name:
            full_name += f" {user.last_name}"

        response = await agent.handle_message(
            user_message,
            name=full_name,
            username=user.username,
            language=user.language_code,
        )

        if response.error:
            await message.reply_text(f"Error: {response.error}")
            return

        try:
            html_text = mistune.html(response.text)
            html_text = convert_to_telegram_html(html_text)

            max_length = 4096
            if len(html_text) <= max_length:
                await message.reply_text(html_text, parse_mode=ParseMode.HTML)
            else:
                chunks = self._split_message(html_text, max_length)
                for chunk in chunks:
                    await message.reply_text(chunk, parse_mode=ParseMode.HTML)
        except RPCError as e:
            await message.reply_text(f"Error processing your request: {e}")

    def run(self) -> None:
        self._register_handlers()

        print(f"Starting Telegram bot with model: {self.default_model}")
        print(f"Session file: {self.app.name}.session")

        @self.app.on_message(filters.me, group=-1)
        async def on_startup(client: Client, _):
            await self._register_bot_commands()
            self.app.remove_handler(on_startup, -1)

        self.app.run()


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
