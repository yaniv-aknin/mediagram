# mediagram

A conversational AI assistant that works via Telegram or command-line interface, powered by Claude via the llm library.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   # For Telegram: add TELEGRAM_BOT_TOKEN
   ```

## Usage

### Telegram Bot (default)

Run the Telegram bot:
```bash
uv run mediagram
# or explicitly:
uv run mediagram --driver=telegram
```

With a specific model:
```bash
uv run mediagram --model=sonnet
```

### CLI Mode

Chat directly in your terminal:
```bash
uv run mediagram --driver=cli
```

With a specific model:
```bash
uv run mediagram --driver=cli --model=sonnet
```

## Commands

Both drivers support the same commands:

- `/help` - Show all available commands
- `/clear` - Clear chat history and start a new conversation
- `/model [name]` - Change model or show current model
  - Available models: `haiku` (Claude Haiku 4.5), `sonnet` (Claude Sonnet 4.5)
- `/quit` or `/exit` - Exit (CLI only)

## Features

- Persistent conversation history per user
- Async message handling using llm's async API
- Support for multiple Claude models
- Dynamic model switching
- Two interaction modes: Telegram and CLI
- Markdown rendering in Telegram (with fallback to plain text)
- Context-aware system prompts with user information and current time
