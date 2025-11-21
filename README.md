# Mediagram

A conversational AI assistant powered by Claude that helps with media processing tasks. Works via Telegram or CLI.

Mediagram uses a plugin architecture to extend functionality. The core package provides the agent system and built-in tools, while additional tools can be installed as separate plugins.

## Installation

### Using pip

```bash
pip install mediagram
```

### Using uv (recommended for development)

```bash
git clone https://github.com/yourusername/mediagram.git
cd mediagram
uv sync
```

### Configuration

Configure environment variables:
```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
# For Telegram: add TELEGRAM_BOT_TOKEN
```

### Installing Plugins

Mediagram has a plugin system for additional tools. Install plugins as needed:

```bash
# From PyPI (when published)
mediagram plugin install mediagram-http
mediagram plugin install mediagram-ffmpeg
mediagram plugin install mediagram-yt-dlp

# From GitHub
mediagram plugin install git+https://github.com/user/mediagram-plugin.git

# Development mode
mediagram plugin install -e /path/to/plugin
```

## Usage

### Run Mediagram

```bash
# Interactive CLI mode
mediagram run cli

# Telegram bot
mediagram run telegram
```

### Run Tools Directly

```bash
# List available tools
mediagram tool --help

# Run a specific tool
mediagram tool listdir --path .
mediagram tool grep --pattern "TODO" --path .
```

### Manage Plugins

```bash
# List installed plugins
mediagram plugin plugins

# Install a plugin
mediagram plugin install mediagram-http

# Uninstall a plugin
mediagram plugin uninstall mediagram-http -y
```

## Commands

Both drivers support the same commands:

- `/help` - Show all available commands
- `/clear` - Clear chat history and start a new conversation
- `/model [name]` - Change model or show current model
  - Available models: `haiku` (Claude Haiku 4.5), `sonnet` (Claude Sonnet 4.5)
- `/tools` - List all available tools with their signatures and descriptions
- `/quit` or `/exit` - Exit (CLI only)

## Plugin Management

Mediagram provides commands to manage plugins (similar to `llm` CLI):

### List Installed Plugins

```bash
# List plugin packages (excludes built-in tools)
mediagram plugin plugins

# List all plugins including built-in
mediagram plugin plugins --all

# Filter by hook
mediagram plugin plugins --hook register_tools
```

### Install Plugins

```bash
# From PyPI
mediagram plugin install mediagram-http

# From GitHub
mediagram plugin install git+https://github.com/user/mediagram-plugin.git

# From local directory
mediagram plugin install /path/to/plugin

# Editable/development mode
mediagram plugin install -e /path/to/plugin

# Multiple packages
mediagram plugin install mediagram-http mediagram-ffmpeg mediagram-llm
```

### Uninstall Plugins

```bash
# With confirmation prompt
mediagram plugin uninstall mediagram-http

# Skip confirmation
mediagram plugin uninstall mediagram-http -y

# Multiple packages
mediagram plugin uninstall mediagram-http mediagram-ffmpeg -y
```

### Emergency Plugin Disable

If a broken plugin prevents mediagram from running:

```bash
# Disable all plugins temporarily
MEDIAGRAM_LOAD_PLUGINS='' mediagram plugin uninstall mediagram-broken-plugin
```

## Plugin Architecture

Mediagram uses a plugin system based on [Pluggy](https://pluggy.readthedocs.io/). Tools are registered via the `mediagram` entry point group in `pyproject.toml`.

### Plugin Packages

Plugin packages are distributed separately from the core. Each plugin is self-contained and can be:
- Published to its own repository
- Distributed via PyPI
- Installed from any source (PyPI, GitHub, local path)

**Available plugins:**
- [mediagram-yt-dlp](https://github.com/user/mediagram-yt-dlp) - YouTube download tool
- [mediagram-ffmpeg](https://github.com/user/mediagram-ffmpeg) - FFmpeg media processing
- [mediagram-llm](https://github.com/user/mediagram-llm) - LLM file processing
- [mediagram-http](https://github.com/user/mediagram-http) - HTTP fetch tool
- [mediagram-assemblyai](https://github.com/user/mediagram-assemblyai) - Audio transcription

**Plugin requirements:**
1. Depend on `mediagram>=0.1.0`
2. Define entry point: `[project.entry-points.mediagram]`

### Creating a Plugin

1. Create a package with this structure:

```python
# my_plugin/__init__.py
from mediagram import hookimpl
from mediagram.agent.tools import tool
from mediagram.agent.callbacks import SuccessMessage

@tool
async def my_tool(arg: str):
    """My custom tool."""
    # Tool logic here
    yield SuccessMessage(f"Processed: {arg}")

@hookimpl
def register_tools(register):
    """Register tools with mediagram."""
    register(my_tool)
```

2. Add entry point in `pyproject.toml`:

```toml
[project.entry-points.mediagram]
my_plugin = "my_plugin"
```

3. Install and the tool will be available automatically.

## Features

- Persistent conversation history per user
- Async message handling using llm's async API
- Support for multiple Claude models
- Dynamic model switching
- Two interaction modes: Telegram and CLI
- Markdown rendering in Telegram (with fallback to plain text)
- Context-aware system prompts with user information and current time
- Plugin-based tool system with progress reporting
