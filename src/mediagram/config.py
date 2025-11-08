from pathlib import Path
from dotenv import load_dotenv
from enum import Enum


class ModelChoice(str, Enum):
    haiku = "haiku"
    sonnet = "sonnet"


def load_environment() -> None:
    """Load environment variables from .env or fallback location."""
    if not load_dotenv():
        fallback_env = Path.home() / ".mediagram.d" / "dotenv"
        if fallback_env.exists():
            load_dotenv(fallback_env)
