from pathlib import Path
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass
from typing_extensions import Annotated
import typer


class ModelChoice(str, Enum):
    haiku = "haiku"
    sonnet = "sonnet"


@dataclass
class CommonOptions:
    """Common options shared across all entry points."""

    model: str = "haiku"
    media_dir: str | None = None
    max_turns: int = 5


# Shared option type annotations for consistency
ModelOption = Annotated[ModelChoice, typer.Option("--model", help="Model to use")]
MediaDirOption = Annotated[
    str | None, typer.Option("--media-dir", help="Directory for media storage")
]
TurnsOption = Annotated[
    int, typer.Option("--turns", help="Maximum autonomous turns per instruction")
]


def load_environment() -> None:
    """Load environment variables from .env or fallback location."""
    if not load_dotenv():
        fallback_env = Path.home() / ".mediagram.d" / "dotenv"
        if fallback_env.exists():
            load_dotenv(fallback_env)
