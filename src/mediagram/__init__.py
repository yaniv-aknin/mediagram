import os
from datetime import datetime
from importlib.resources import files
from telegram import Update, User
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv
import llm


conversations = {}
system_prompt_template = None


def load_system_prompt_template() -> str:
    prompt_file = files("mediagram").joinpath("prompts/system.md")
    return prompt_file.read_text()


def get_user_info_text(user: User) -> str:
    parts = [f"Name: {user.full_name}"]
    if user.username:
        parts.append(f"Username: @{user.username}")
    if user.language_code:
        parts.append(f"Language: {user.language_code}")
    if user.is_premium:
        parts.append("Telegram Premium user")
    return "\n".join(parts)


def render_system_prompt(user: User) -> str:
    global system_prompt_template

    if system_prompt_template is None:
        system_prompt_template = load_system_prompt_template()

    user_info = get_user_info_text(user)
    current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z").strip()

    return system_prompt_template.replace("{{ user_information }}", user_info).replace(
        "{{ datetime }}", current_datetime
    )


async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in conversations:
        del conversations[user_id]
    await update.message.reply_text(
        "Chat history cleared. Starting a new conversation."
    )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_message = update.message.text
    user = update.effective_user

    if user_id not in conversations:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

        model = llm.get_async_model("claude-haiku-4.5")
        conversations[user_id] = model.conversation()

    conversation = conversations[user_id]
    system_prompt = render_system_prompt(user)

    try:
        response = conversation.prompt(user_message, system=system_prompt)
        reply_text = await response.text()

        try:
            await update.message.reply_text(
                reply_text, parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception:
            await update.message.reply_text(reply_text)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


def main() -> None:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()
