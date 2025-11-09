import asyncio
import inspect
import os
from pathlib import Path

import typer
from typing_extensions import Annotated

from mediagram.agent.tools import ALL_TOOLS

app = typer.Typer()

_global_cwd = "."


@app.callback()
def main(
    cwd: Annotated[
        str, typer.Option("--cwd", help="Working directory (default: current dir)")
    ] = ".",
) -> None:
    """Run mediagram tools from the command line."""
    global _global_cwd
    _global_cwd = cwd


def create_tool_command(tool_func):
    """Create a command wrapper for a tool."""

    def wrapper(**kwargs):
        os.environ["MEDIAGRAM_TOOL_SUBDIR"] = str(Path(_global_cwd).resolve())

        # Special handling for rename tool
        if tool_func.__name__ == "rename" and "rename" in kwargs:
            rename_arg = kwargs["rename"]
            if rename_arg and isinstance(rename_arg[0], str):
                # Convert from flat list to list of tuples
                kwargs["rename"] = [
                    (rename_arg[i], rename_arg[i + 1])
                    for i in range(0, len(rename_arg), 2)
                ]

        async def run():
            result = await tool_func(**kwargs)
            print(result)

        asyncio.run(run())

    wrapper.__name__ = tool_func.__name__
    wrapper.__doc__ = tool_func.__doc__

    sig = inspect.signature(tool_func)
    new_params = []

    for param_name, param in sig.parameters.items():
        # Special annotation for rename's list parameter
        if tool_func.__name__ == "rename" and param_name == "rename":
            new_param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=param.default
                if param.default != inspect.Parameter.empty
                else ...,
                annotation=Annotated[
                    list[str],
                    typer.Option(
                        "--rename",
                        help="Old and new paths (repeat for multiple renames)",
                    ),
                ],
            )
        else:
            new_param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=param.default
                if param.default != inspect.Parameter.empty
                else ...,
                annotation=param.annotation,
            )
        new_params.append(new_param)

    wrapper.__signature__ = inspect.Signature(parameters=new_params)

    return wrapper


for tool in ALL_TOOLS:
    app.command(name=tool.__name__)(create_tool_command(tool))


if __name__ == "__main__":
    app()
