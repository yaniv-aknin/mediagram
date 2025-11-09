import re
from pathlib import Path

from ..callbacks import SuccessMessage, ErrorMessage
from . import tool, get_tool_subdir


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
    cwd: str | None = None, recursive: bool = False, hidden: bool = False
):
    """List directory contents with size and type information.

    Args:
        cwd: Relative directory to list (None for root)
        recursive: Whether to list recursively
        hidden: Whether to include hidden files (starting with .)
    """
    try:
        root = get_subdir_root()
        if cwd:
            target = ensure_contained(Path(cwd))
        else:
            target = root

        if not target.exists():
            yield ErrorMessage(f"Directory does not exist: {cwd or '.'}")
            return

        if not target.is_dir():
            yield ErrorMessage(f"Not a directory: {cwd or '.'}")
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
async def grep(pattern: str, is_regex: bool = False, pre: int = 0, post: int = 0):
    """Search for pattern in all files with optional context lines.

    Args:
        pattern: Pattern to search for
        is_regex: Whether pattern is a regex (default: literal string)
        pre: Number of context lines before match
        post: Number of context lines after match
    """
    try:
        root = get_subdir_root()

        if is_regex:
            try:
                regex = re.compile(pattern)
            except re.error as e:
                yield ErrorMessage(f"Invalid regex: {e}")
                return
        else:
            regex = re.compile(re.escape(pattern))

        matches = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except Exception:
                continue

            rel_path = file_path.relative_to(root)
            file_matches = _find_matches(lines, regex, rel_path, pre, post)
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
