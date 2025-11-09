import typer

from mediagram.config import (
    ModelChoice,
    ModelOption,
    MediaDirOption,
    TurnsOption,
    ToolOutputLimitOption,
    load_environment,
)
from mediagram.driver import telegram


app = typer.Typer()


@app.command()
def main(
    model: ModelOption = ModelChoice.haiku,
    media_dir: MediaDirOption = None,
    turns: TurnsOption = 5,
    tool_output_limit: ToolOutputLimitOption = 16384,
) -> None:
    """Mediagram Telegram - Chat with Claude via Telegram"""
    load_environment()
    telegram.run(
        model.value,
        media_dir_override=media_dir,
        max_turns=turns,
        tool_output_limit=tool_output_limit,
    )


if __name__ == "__main__":
    app()
