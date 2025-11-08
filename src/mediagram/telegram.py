import typer
from typing_extensions import Annotated

from mediagram.config import ModelChoice, load_environment
from mediagram.driver import telegram


app = typer.Typer()


@app.command()
def main(
    model: Annotated[
        ModelChoice, typer.Option("--model", help="Model to use")
    ] = ModelChoice.haiku,
) -> None:
    """Mediagram Telegram - Chat with Claude via Telegram"""
    load_environment()
    telegram.run(model.value)


if __name__ == "__main__":
    app()
