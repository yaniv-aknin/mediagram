import typer
from enum import Enum
from typing_extensions import Annotated

from mediagram import driver
from mediagram.config import (
    ModelChoice,
    ModelOption,
    MediaDirOption,
    TurnsOption,
    ToolOutputLimitOption,
    load_environment,
)


class DriverChoice(str, Enum):
    telegram = "telegram"
    cli = "cli"


app = typer.Typer()


@app.command()
def main(
    driver_name: Annotated[
        DriverChoice, typer.Option("--driver", help="Driver to use")
    ] = DriverChoice.telegram,
    model: ModelOption = ModelChoice.haiku,
    media_dir: MediaDirOption = None,
    turns: TurnsOption = 5,
    tool_output_limit: ToolOutputLimitOption = 16384,
) -> None:
    """Mediagram - Chat with Claude via Telegram or CLI"""
    load_environment()

    if driver_name == DriverChoice.telegram:
        driver.telegram.run(
            model=model.value,
            media_dir_override=media_dir,
            max_turns=turns,
            tool_output_limit=tool_output_limit,
        )
    elif driver_name == DriverChoice.cli:
        driver.cli.run(
            model=model.value,
            media_dir_override=media_dir,
            max_turns=turns,
            tool_output_limit=tool_output_limit,
        )


if __name__ == "__main__":
    app()
