"""Main CLI entry point for mediagram."""

import typer
from typing_extensions import Annotated

from mediagram import cli, telegram, tool as tool_module
from mediagram import plugins as plugin_commands
from mediagram.config import load_environment

app = typer.Typer()


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    ctx: typer.Context,
    mode: Annotated[
        str,
        typer.Argument(help="Run mode: 'cli' or 'telegram'"),
    ],
):
    """Run mediagram in CLI or Telegram mode.

    Examples:
        mediagram run cli
        mediagram run telegram
    """
    load_environment()

    if mode == "cli":
        cli.app(ctx.args)
    elif mode == "telegram":
        telegram.app(ctx.args)
    else:
        typer.echo(f"Error: Unknown mode '{mode}'. Use 'cli' or 'telegram'.", err=True)
        raise typer.Exit(1)


# Add tool command
app.add_typer(
    tool_module.app, name="tool", help="Run mediagram tools from the command line"
)

# Add plugin commands
app.add_typer(plugin_commands.app, name="plugin", help="Manage mediagram plugins")


if __name__ == "__main__":
    app()
