# Mediagram

An media processing agent based on Claude. Works via Telegram or CLI.

## Installation

- Run with `uv run mediagram` or `uv tool install <mediagram>`.
- Copy `.env.example` to `.env` and populate

## Plugins

Use `mediagram plugin install <url>` to install plugins, adding tools to `mediagram`.

## Invocation

- `mediagram run cli` to try things out in the terminal
- `mediagram run telegram` to run a Telegram bot

## Tools

- `mediagram tool` to experiment with tools; `--help` to get a list.

## Commands

Both drivers support some builtin commands. Try `/help` in the chat.

## Media dir

Tools are invoked in a "media subdir", under the media directory (`~/.mediagram.d/media` or `--media-dir`).

Isolation is pretty basic; run in a container for better isolation.

## Containerization

The `build-container.py` script helps create a container with `mediagram` and plugins installed.

The `run-container.py` script runs a container, passing bits of `~/.mediagram.d` into the container (environment, mounts, etc).

## Example

The power of `mediagram` comes from agentic use of tools to accomplish interesting tasks.

With the `yt-dlp`, `ffmpeg`, and `assemblyai` plugins, you could try something like "Download https://www.youtube.com/watch?v=oADU2PIzhD0, extract audio, identify a few surprising statements and cut a short clip of the most surprising facts".
