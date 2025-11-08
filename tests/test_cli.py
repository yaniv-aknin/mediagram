from typer.testing import CliRunner
from mediagram.cli import app

runner = CliRunner()


def test_cli_help_command():
    """Test that /help command works and lists available commands."""
    result = runner.invoke(app, ["/help"])

    assert result.exit_code == 0
    assert "Available commands:" in result.stdout
    assert "/clear" in result.stdout
    assert "/model" in result.stdout
    assert "/tools" in result.stdout
