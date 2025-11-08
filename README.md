# mediagram

A Telegram bot that proxies conversations with Claude via the llm library.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY
   ```

3. Run the bot:
   ```bash
   uv run mediagram
   ```

## Usage

The bot maintains a conversation history for each user and forwards all messages to Claude.

### Commands

- `/clear` - Clear chat history and start a new conversation

### Features

- Persistent conversation history per user
- Async message handling using llm's async API
- Proxies all non-command messages to Claude Haiku 4.5
