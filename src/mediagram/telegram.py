import typer

from mediagram.config import (
    ModelChoice,
    ModelOption,
    MediaDirOption,
    TurnsOption,
    load_environment,
)
from mediagram.driver import telegram


app = typer.Typer()


@app.command()
def main(
    model: ModelOption = ModelChoice.haiku,
    media_dir: MediaDirOption = None,
    turns: TurnsOption = 5,
) -> None:
    """Mediagram Telegram - Chat with Claude via Telegram"""
    load_environment()
    telegram.run(model.value, media_dir_override=media_dir, max_turns=turns)


if __name__ == "__main__":
    app()
