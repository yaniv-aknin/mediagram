import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from mediagram.cli import app

runner = CliRunner()


def test_cli_help_command():
    """End-to-end test with media dir, conversation, and jsonl verification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        media_dir = Path(tmpdir)

        result = runner.invoke(
            app, ["--media-dir", str(media_dir), "/help", "Hello there"]
        )

        assert result.exit_code == 0
        assert "Available commands:" in result.stdout
        assert "/clear" in result.stdout

        subdirs = list(media_dir.glob(".*"))
        assert len(subdirs) == 1
        subdir = subdirs[0]
        assert subdir.name.startswith(".")
        assert subdir.name.endswith(".0")

        messages_file = subdir / ".messages.jsonl"
        assert messages_file.exists()

        with messages_file.open() as f:
            lines = f.readlines()
            assert len(lines) >= 2

            msg1 = json.loads(lines[0])
            assert msg1["role"] == "user"
            assert msg1["content"] == "/help"

            msg2 = json.loads(lines[1])
            assert msg2["role"] == "command"
            assert msg2["command"] == "help"
            assert "Available commands:" in msg2["content"]
