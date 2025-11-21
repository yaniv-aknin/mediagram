"""Built-in filesystem tools plugin."""

import re
from pathlib import Path

from mediagram.agent.callbacks import SuccessMessage, ErrorMessage
from mediagram.agent.tools import tool, get_tool_subdir
from mediagram import hookimpl


def get_subdir_root() -> Path:
    """Get the root directory for tool operations (current media subdir)."""
    subdir = get_tool_subdir()
    if not subdir:
        raise ValueError("Tool subdir not set in context")
    return subdir.resolve()


def ensure_contained(path: Path) -> Path:
    """Ensure path is contained within the subdir root."""
    root = get_subdir_root()
    resolved = (root / path).resolve()

    if not str(resolved).startswith(str(root)):
        raise ValueError(f"Path {path} escapes subdir containment")

    return resolved


@tool
async def listdir(
    path: str | None = None, recursive: bool = False, hidden: bool = False
):
    """List directory contents with size and type information.

    Args:
        path: Relative path to list (None for root)
        recursive: Whether to list recursively
        hidden: Whether to include hidden files (starting with .)
    """
    try:
        root = get_subdir_root()
        if path:
            target = ensure_contained(Path(path))
        else:
            target = root

        if not target.exists():
            yield ErrorMessage(f"Directory does not exist: {path or '.'}")
            return

        if not target.is_dir():
            yield ErrorMessage(f"Not a directory: {path or '.'}")
            return

        lines = []
        if recursive:
            for item in sorted(target.rglob("*")):
                rel_path = item.relative_to(root)
                if not hidden and rel_path.name.startswith("."):
                    continue
                lines.append(_format_item(item, rel_path))
        else:
            for item in sorted(target.iterdir()):
                rel_path = item.relative_to(root)
                if not hidden and rel_path.name.startswith("."):
                    continue
                lines.append(_format_item(item, rel_path))

        if lines:
            yield SuccessMessage("\n".join(lines))
        else:
            yield SuccessMessage("(empty directory)")

    except ValueError as e:
        yield ErrorMessage(str(e))


def _format_item(path: Path, rel_path: Path) -> str:
    """Format a directory entry with size and type."""
    if path.is_symlink():
        type_str = "symlink"
        size = 0
    elif path.is_dir():
        type_str = "dir"
        size = 0
    elif path.is_file():
        type_str = "file"
        size = path.stat().st_size
    else:
        type_str = "other"
        size = 0

    return f"{rel_path}  {size:>10}  {type_str}"


@tool
async def grep(
    pattern: str,
    regex: bool = False,
    pre: int = 0,
    post: int = 0,
    glob: str | None = None,
):
    """Search for pattern in all files with optional context lines.

    Args:
        pattern: Pattern to search for
        regex: Whether pattern is a regex (default: literal string)
        pre: Number of context lines before match
        post: Number of context lines after match
        glob: Optional glob pattern to filter files (e.g., '*.py')
    """
    try:
        root = get_subdir_root()

        if regex:
            try:
                regex_pattern = re.compile(pattern)
            except re.error as e:
                yield ErrorMessage(f"Invalid regex: {e}")
                return
        else:
            regex_pattern = re.compile(re.escape(pattern))

        matches = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            # Apply glob filter if provided
            if glob:
                from fnmatch import fnmatch

                rel_path_for_glob = file_path.relative_to(root)
                if not fnmatch(str(rel_path_for_glob), glob):
                    continue

            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            rel_path = file_path.relative_to(root)
            file_matches = _find_matches(lines, regex_pattern, rel_path, pre, post)
            if file_matches:
                matches.append(file_matches)

        if matches:
            yield SuccessMessage("\n\n".join(matches))
        else:
            yield SuccessMessage("No matches found")

    except ValueError as e:
        yield ErrorMessage(str(e))


def _find_matches(
    lines: list[str], regex: re.Pattern, rel_path: Path, pre: int, post: int
) -> str:
    """Find all matches in a file with context."""
    matching_lines = []

    for i, line in enumerate(lines):
        if regex.search(line):
            matching_lines.append(i)

    if not matching_lines:
        return ""

    result_lines = [f"--- {rel_path} ---"]
    added_lines = set()

    for match_idx in matching_lines:
        start = max(0, match_idx - pre)
        end = min(len(lines), match_idx + post + 1)

        if (
            result_lines[-1] != "..."
            and added_lines
            and min(range(start, end)) > max(added_lines)
        ):
            result_lines.append("...")

        for i in range(start, end):
            if i not in added_lines:
                prefix = ">" if i == match_idx else " "
                result_lines.append(f"{prefix} {i + 1:>4} {lines[i].rstrip()}")
                added_lines.add(i)

    return "\n".join(result_lines)


@tool
async def read(path: str, lines: int | None = None, chars: int | None = None):
    """Read file contents with optional slicing.

    Args:
        path: Relative path to file
        lines: Number of lines to read (positive=from start, negative=from end, None=all)
        chars: Number of characters to read (positive=from start, negative=from end, None=all)
    """
    try:
        file_path = ensure_contained(Path(path))

        if not file_path.exists():
            yield ErrorMessage(f"File does not exist: {path}")
            return

        if not file_path.is_file():
            yield ErrorMessage(f"Not a file: {path}")
            return

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            yield ErrorMessage(f"File is not a text file: {path}")
            return
        except Exception as e:
            yield ErrorMessage(f"Error reading file: {e}")
            return

        if chars is not None:
            if chars > 0:
                content = content[:chars]
            elif chars < 0:
                content = content[chars:]

        if lines is not None:
            content_lines = content.splitlines(keepends=True)
            if lines > 0:
                content_lines = content_lines[:lines]
            elif lines < 0:
                content_lines = content_lines[lines:]
            content = "".join(content_lines)

        yield SuccessMessage(content)

    except ValueError as e:
        yield ErrorMessage(str(e))


@tool
async def rename(old: list[str], new: list[str]):
    """Rename files or directories.

    Args:
        old: List of old paths (relative to subdir)
        new: List of new paths (relative to subdir)
    """
    try:
        if len(old) != len(new):
            yield ErrorMessage("old and new must have same length")
            return

        renames = []

        for old_path, new_path in zip(old, new):
            old_resolved = ensure_contained(Path(old_path))
            new_resolved = ensure_contained(Path(new_path))

            if not old_resolved.exists():
                yield ErrorMessage(f"Source does not exist: {old_path}")
                return

            if new_resolved.exists():
                yield ErrorMessage(f"Destination already exists: {new_path}")
                return

            renames.append((old_resolved, new_resolved))

        for old_resolved, new_resolved in renames:
            new_resolved.parent.mkdir(parents=True, exist_ok=True)
            old_resolved.rename(new_resolved)

        renamed_list = ", ".join(f"{o} → {n}" for o, n in zip(old, new))
        yield SuccessMessage(f"Renamed: {renamed_list}")

    except ValueError as e:
        yield ErrorMessage(str(e))


@hookimpl
def register_tools(register):
    """Register filesystem tools."""
    register(listdir)
    register(grep)
    register(read)
    register(rename)
