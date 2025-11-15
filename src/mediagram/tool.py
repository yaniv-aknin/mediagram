import asyncio
import inspect
from pathlib import Path

import typer
from typing_extensions import Annotated

from mediagram.config import load_environment
from mediagram.agent.tools import ALL_TOOLS, set_driver_callbacks
from mediagram.agent.callbacks import ProgressMessage, SuccessMessage, ErrorMessage

load_environment()

app = typer.Typer()

_global_cwd = "."


class ToolCLICallbacks:
    """Simple callbacks for tool CLI that prints progress to stdout."""

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        """Handle tool progress updates."""
        percentage = (
            f" ({progress.completion_ratio * 100:.0f}%)"
            if progress.completion_ratio is not None
            else ""
        )
        eta = (
            f" - ETA: {progress.completion_eta_minutes:.1f}m"
            if progress.completion_eta_minutes is not None
            else ""
        )
        print(f"🔄 {progress.text}{percentage}{eta}")

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        """Handle tool success."""
        if "\n" in success.text:
            indented = "\n".join(f"   {line}" for line in success.text.split("\n"))
            print(f"✅\n{indented}")
        else:
            print(f"✅ {success.text}")

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        """Handle tool errors."""
        details = f" - {error.error}" if error.error else ""
        full_text = f"{error.text}{details}"
        if "\n" in full_text:
            indented = "\n".join(f"   {line}" for line in full_text.split("\n"))
            print(f"❌\n{indented}")
        else:
            print(f"❌ {full_text}")


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
        from mediagram.agent.tools import set_tool_subdir

        # Set the tool subdir context variable for filesystem operations
        resolved_cwd = Path(_global_cwd).resolve()
        set_tool_subdir(resolved_cwd)

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
            # Set up callbacks for progress reporting
            callbacks = ToolCLICallbacks()
            set_driver_callbacks(callbacks)

            # The result is already printed via callbacks
            await tool_func(**kwargs)

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
        # Special handling for boolean flags to show as --flag/--no-flag
        elif param.annotation is bool or (
            hasattr(param.annotation, "__origin__")
            and param.annotation.__origin__ is type(None) | type
            and bool in getattr(param.annotation, "__args__", ())
        ):
            # For boolean parameters, create proper flag annotations
            default_val = (
                param.default if param.default != inspect.Parameter.empty else False
            )
            new_param = inspect.Parameter(
                param_name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=default_val,
                annotation=Annotated[
                    bool, typer.Option(f"--{param_name.replace('_', '-')}")
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
