from pathlib import Path
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass
from typing_extensions import Annotated
import typer
import functools


AVAILABLE_MODELS = {
    "haiku": "claude-haiku-4.5",
    "sonnet": "claude-sonnet-4.5",
}


def patch_docstring(func):
    """Decorator that patches {available_models} in docstrings with current model list."""
    if func.__doc__:
        model_list = ", ".join(f'"{k}"' for k in AVAILABLE_MODELS.keys())
        func.__doc__ = func.__doc__.replace("{available_models}", model_list)
    return func


class ModelChoice(str, Enum):
    haiku = "haiku"
    sonnet = "sonnet"


@dataclass
class CommonOptions:
    """Common options shared across all entry points."""

    model: str = "haiku"
    media_dir: str | None = None
    max_turns: int = 5
    tool_output_limit: int = 16384  # 16K characters


# Shared option type annotations for consistency
ModelOption = Annotated[ModelChoice, typer.Option("--model", help="Model to use")]
MediaDirOption = Annotated[
    str | None, typer.Option("--media-dir", help="Directory for media storage")
]
TurnsOption = Annotated[
    int, typer.Option("--turns", help="Maximum autonomous turns per instruction")
]
ToolOutputLimitOption = Annotated[
    int,
    typer.Option(
        "--tool-limit", help="Maximum tool output size in characters (min 128)"
    ),
]


def load_environment() -> None:
    """Load environment variables from .env or fallback location."""
    if not load_dotenv():
        fallback_env = Path.home() / ".mediagram.d" / "dotenv"
        if fallback_env.exists():
            load_dotenv(fallback_env)
