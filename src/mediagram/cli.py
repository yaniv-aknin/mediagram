import typer
from typing_extensions import Annotated

from mediagram.config import (
    ModelChoice,
    ModelOption,
    MediaDirOption,
    TurnsOption,
    ToolOutputLimitOption,
    ToolDetailsOption,
    DEFAULT_MAX_TURNS,
    DEFAULT_TOOL_OUTPUT_LIMIT,
    DEFAULT_TOOL_DETAILS,
    load_environment,
)
from mediagram.driver import cli
from mediagram.driver.cli import PreDefinedInputSource


app = typer.Typer()


@app.command()
def main(
    model: ModelOption = ModelChoice.haiku,
    media_dir: MediaDirOption = None,
    turns: TurnsOption = DEFAULT_MAX_TURNS,
    tool_output_limit: ToolOutputLimitOption = DEFAULT_TOOL_OUTPUT_LIMIT,
    tool_details: ToolDetailsOption = DEFAULT_TOOL_DETAILS,
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
            tool_output_limit=tool_output_limit,
            tool_details=tool_details,
        )
    else:
        cli.run(
            model.value,
            media_dir_override=media_dir,
            max_turns=turns,
            tool_output_limit=tool_output_limit,
            tool_details=tool_details,
        )


if __name__ == "__main__":
    app()
