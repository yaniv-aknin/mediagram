import typer
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv
from typing_extensions import Annotated

from mediagram import driver


class DriverChoice(str, Enum):
    telegram = "telegram"
    cli = "cli"


class ModelChoice(str, Enum):
    haiku = "haiku"
    sonnet = "sonnet"


app = typer.Typer()


@app.command()
def main(
    driver_name: Annotated[
        DriverChoice, typer.Option("--driver", help="Driver to use")
    ] = DriverChoice.telegram,
    model: Annotated[
        ModelChoice, typer.Option("--model", help="Model to use")
    ] = ModelChoice.haiku,
) -> None:
    """Mediagram - Chat with Claude via Telegram or CLI"""
    if not load_dotenv():
        fallback_env = Path.home() / ".mediagram.d" / "dotenv"
        if fallback_env.exists():
            load_dotenv(fallback_env)

    if driver_name == DriverChoice.telegram:
        driver.telegram.run(model.value)
    elif driver_name == DriverChoice.cli:
        driver.cli.run(model.value)


if __name__ == "__main__":
    app()
