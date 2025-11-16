"""Tests for agent utility functions like system prompt rendering."""

from unittest.mock import patch

from mediagram.agent import (
    render_system_prompt,
    load_system_prompt_template,
)


def test_render_system_prompt_turns():
    template = "Max: {{ max_turns }}, Remaining: {{ remaining_turns }}"

    result = render_system_prompt(template, "Alice", max_turns=0)
    assert "Max: unlimited" in result
    assert "Remaining: unlimited" in result

    result = render_system_prompt(template, "Alice", max_turns=10, remaining_turns=3)
    assert "Max: 10" in result
    assert "Remaining: 3" in result

    result = render_system_prompt(template, "Alice", max_turns=15, remaining_turns=None)
    assert "Max: 15" in result
    assert "Remaining: 15" in result


def test_render_system_prompt_user():
    template = "User: {{ user_information }}"

    result = render_system_prompt(template, "Bob", username=None, language=None)
    assert "User: Name: Bob" in result
    assert "Username:" not in result
    assert "Language:" not in result

    result = render_system_prompt(template, "Alice", username="alice99", language="en")
    assert "Name: Alice" in result
    assert "Username: alice99" in result
    assert "Language: en" in result


def test_render_system_prompt_datetime_replacement():
    template = "Time: {{ datetime }}"

    with patch("mediagram.agent.datetime") as mock_datetime:
        mock_datetime.now.return_value.strftime.return_value = "2024-12-25 14:30:00 UTC"
        result = render_system_prompt(template, "User")

    assert "Time: 2024-12-25 14:30:00 UTC" in result


def test_load_system_prompt_template():
    template = load_system_prompt_template()
    assert isinstance(template, str)
    assert len(template) > 0


def test_render_system_prompt_handles_missing_placeholders():
    template = "Hello {{ user_information }}"
    result = render_system_prompt(template, "Alice")
    assert "Hello Name: Alice" in result
    assert "{{ user_information }}" not in result
