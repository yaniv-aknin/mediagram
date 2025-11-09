import typer
from typing_extensions import Annotated

from mediagram.config import ModelChoice, load_environment
from mediagram.driver import cli
from mediagram.driver.cli import PreDefinedInputSource


app = typer.Typer()


@app.command()
def main(
    model: Annotated[
        ModelChoice, typer.Option("--model", help="Model to use")
    ] = ModelChoice.haiku,
    media_dir: Annotated[
        str | None, typer.Option("--media-dir", help="Directory for media storage")
    ] = None,
    messages: Annotated[
        list[str] | None, typer.Argument(help="Optional messages to send")
    ] = None,
) -> None:
    """Mediagram CLI - Chat with Claude via command line"""
    load_environment()

    if messages:
        input_source = PreDefinedInputSource(messages)
        cli.run(model.value, media_dir_override=media_dir, input_source=input_source)
    else:
        cli.run(model.value, media_dir_override=media_dir)


if __name__ == "__main__":
    app()
