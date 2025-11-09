import typer
from typing_extensions import Annotated

from mediagram.config import (
    ModelChoice,
    ModelOption,
    MediaDirOption,
    TurnsOption,
    load_environment,
)
from mediagram.driver import cli
from mediagram.driver.cli import PreDefinedInputSource


app = typer.Typer()


@app.command()
def main(
    model: ModelOption = ModelChoice.haiku,
    media_dir: MediaDirOption = None,
    turns: TurnsOption = 5,
    messages: Annotated[
        list[str] | None, typer.Argument(help="Optional messages to send")
    ] = None,
) -> None:
    """Mediagram CLI - Chat with Claude via command line"""
    load_environment()

    if messages:
        input_source = PreDefinedInputSource(messages)
        cli.run(
            model.value,
            media_dir_override=media_dir,
            input_source=input_source,
            max_turns=turns,
        )
    else:
        cli.run(model.value, media_dir_override=media_dir, max_turns=turns)


if __name__ == "__main__":
    app()
