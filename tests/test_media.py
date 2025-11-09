import json
import re
import tempfile
from pathlib import Path

from mediagram.media import MediaManager


def test_media_manager_subdir_and_logging():
    """Test subdirectory creation and message logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)

        subdir1 = manager.create_subdir()
        assert subdir1.exists()
        assert re.match(r"^\.\d{8}-\d{6}\.\d+$", subdir1.name)
        assert subdir1.name.startswith(".")
        assert subdir1.name.endswith(".0")

        manager.log_message(role="user", content="Hello")
        messages_file = manager.get_messages_file()
        assert messages_file.exists()

        with messages_file.open() as f:
            msg = json.loads(f.readline())
            assert msg["role"] == "user"
            assert msg["content"] == "Hello"

        subdir2 = manager.reset_subdir()
        assert subdir2.name.endswith(".1")
        assert subdir1 != subdir2


def test_media_manager_rename_subdir():
    """Test renaming anonymous subdirectory to named."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)

        anon_subdir = manager.create_subdir()
        assert anon_subdir.name.startswith(".")
        assert anon_subdir.name.endswith(".0")

        named_subdir = manager.rename_subdir("My Cool Project")
        assert not named_subdir.name.startswith(".")
        assert "my-cool-project" in named_subdir.name
        assert named_subdir.name.startswith("20")
        assert not anon_subdir.exists()
        assert named_subdir.exists()


def test_media_manager_rename_subdir_no_name():
    """Test renaming anonymous subdirectory without a custom name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)

        anon_subdir = manager.create_subdir()
        assert anon_subdir.name.startswith(".")
        original_name = anon_subdir.name

        permanent_subdir = manager.rename_subdir()
        assert not permanent_subdir.name.startswith(".")
        assert permanent_subdir.name == original_name[1:16]
        assert re.match(r"^\d{8}-\d{6}$", permanent_subdir.name)
        assert not anon_subdir.exists()
        assert permanent_subdir.exists()


def test_media_manager_ephemeral_tmpdir(capsys):
    """Test ephemeral tmpdir fallback with cleanup."""
    manager = MediaManager.create()
    tmpdir = manager.media_dir

    assert tmpdir.exists()
    assert manager._temp_dir is not None

    captured = capsys.readouterr()
    assert "⚠️" in captured.out

    manager.cleanup()
    assert not tmpdir.exists()
