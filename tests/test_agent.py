from datetime import datetime
from unittest.mock import patch
import pytest

from mediagram.agent import (
    get_user_info_text,
    render_system_prompt,
    CommandRouter,
    AgentResponse,
)


def test_get_user_info_text_full():
    """Test user info formatting with all fields."""
    result = get_user_info_text("John Doe", "johndoe", "en")
    assert result == "Name: John Doe\nUsername: johndoe\nLanguage: en"


def test_get_user_info_text_no_optional_fields():
    """Test user info formatting with only required fields."""
    result = get_user_info_text("John Doe", None, None)
    assert result == "Name: John Doe"


def test_render_system_prompt():
    """Test system prompt rendering with user info and datetime."""
    template = "User: {{ user_information }}\nTime: {{ datetime }}"

    with patch("mediagram.agent.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2024-01-15 10:30:00"
        result = render_system_prompt(template, "Alice", "alice123", "fr")

    assert "Name: Alice" in result
    assert "Username: alice123" in result
    assert "Language: fr" in result
    assert "2024-01-15 10:30:00" in result


def test_command_router_register_and_route():
    """Test command registration and routing."""
    router = CommandRouter()

    def mock_handler(args):
        return AgentResponse(text=f"Handler called with {args}")

    router.register("test", mock_handler)
    result = router.route("test", ["arg1", "arg2"], None)

    assert result.text == "Handler called with ['arg1', 'arg2']"


def test_command_router_help():
    """Test help generation from registered commands."""
    router = CommandRouter()

    def cmd1(args):
        """First command"""
        pass

    def cmd2(args):
        """Second command"""
        pass

    router.register("cmd1", cmd1)
    router.register("cmd2", cmd2)

    result = router.route("help", [], None)
    assert "Available commands:" in result.text
    assert "/cmd1 - First command" in result.text
    assert "/cmd2 - Second command" in result.text


def test_command_router_unknown_command():
    """Test handling of unknown commands."""
    router = CommandRouter()
    result = router.route("nonexistent", [], None)

    assert "Unknown command: /nonexistent" in result.text
    assert "Available commands:" in result.text
