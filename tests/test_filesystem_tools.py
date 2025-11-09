import tempfile
from pathlib import Path

import pytest

from mediagram.agent.tools import set_tool_subdir
from mediagram.agent.tools.filesystem import listdir, grep, rename


@pytest.fixture
def test_subdir():
    """Create a temporary subdir with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir)

        (subdir / "file1.txt").write_text("hello world\ntest line\n")
        (subdir / "file2.txt").write_text("another file\n")
        (subdir / "subdir").mkdir()
        (subdir / "subdir" / "nested.txt").write_text("nested content\n")

        set_tool_subdir(subdir)

        yield subdir


@pytest.mark.asyncio
async def test_listdir_basic(test_subdir):
    """Test basic listdir functionality."""
    result = await listdir()
    assert "file1.txt" in result
    assert "file2.txt" in result
    assert "subdir" in result
    assert "dir" in result


@pytest.mark.asyncio
async def test_listdir_recursive(test_subdir):
    """Test recursive listdir."""
    result = await listdir(recursive=True)
    assert "nested.txt" in result or "subdir/nested.txt" in result


@pytest.mark.asyncio
async def test_grep_literal(test_subdir):
    """Test grep with literal pattern."""
    result = await grep("hello")
    assert "file1.txt" in result
    assert "hello world" in result


@pytest.mark.asyncio
async def test_grep_regex(test_subdir):
    """Test grep with regex pattern."""
    result = await grep(r"hello.*world", is_regex=True)
    assert "file1.txt" in result


@pytest.mark.asyncio
async def test_grep_context(test_subdir):
    """Test grep with context lines."""
    result = await grep("world", pre=1, post=1)
    assert "hello world" in result
    assert "test line" in result


@pytest.mark.asyncio
async def test_rename_basic(test_subdir):
    """Test basic rename functionality."""
    result = await rename(["file1.txt"], ["renamed.txt"])
    assert "renamed.txt" in result
    assert (test_subdir / "renamed.txt").exists()
    assert not (test_subdir / "file1.txt").exists()


@pytest.mark.asyncio
async def test_rename_multiple(test_subdir):
    """Test renaming multiple files."""
    await rename(["file1.txt", "file2.txt"], ["new1.txt", "new2.txt"])
    assert (test_subdir / "new1.txt").exists()
    assert (test_subdir / "new2.txt").exists()


@pytest.mark.asyncio
async def test_rename_containment(test_subdir):
    """Test rename prevents escaping subdir."""
    result = await rename(["file1.txt"], ["../escaped.txt"])
    assert "Error" in result or "escapes" in result
