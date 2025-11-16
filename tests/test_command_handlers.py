"""Tests for individual command handlers with edge cases and validation."""

import tempfile
from typing import List, Optional

import pytest

from mediagram.agent import Agent
from mediagram.agent.commands import (
    cmd_model,
    cmd_turns,
    cmd_tool_output_limit,
    cmd_tool_details,
    cmd_tools,
    cmd_name,
    cmd_read,
    _ensure_contained,
    _format_annotation,
)
from mediagram.config import MIN_TOOL_OUTPUT_LIMIT
from mediagram.media import MediaManager


@pytest.fixture
def media_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)
        manager.create_subdir()
        yield manager


@pytest.fixture
def agent(media_manager):
    return Agent(media_manager=media_manager, model_name="haiku")


def test_cmd_model(agent):
    result = cmd_model(agent, "")
    assert "haiku" in result.text
    assert "Available models:" in result.text

    result = cmd_model(agent, "sonnet")
    assert "Model changed to: sonnet" in result.text
    assert agent.model_name == "sonnet"

    result = cmd_model(agent, "invalid_model_xyz")
    assert "Unknown model: invalid_model_xyz" in result.text
    assert agent.model_name == "sonnet"


def test_cmd_turns(agent):
    agent.max_turns = 10
    result = cmd_turns(agent, "")
    assert "Current max turns: 10" in result.text

    agent.max_turns = 0
    result = cmd_turns(agent, "")
    assert "infinite" in result.text.lower()
    assert agent.max_turns == 0

    result = cmd_turns(agent, "20")
    assert "Max turns set to: 20" in result.text
    assert agent.max_turns == 20

    agent.max_turns = 42
    result = cmd_turns(agent, "-5")
    assert "positive" in result.text or "0" in result.text
    result = cmd_turns(agent, "abc")
    assert "number" in result.text
    assert agent.max_turns == 42


def test_cmd_tlimit_show_current(agent):
    agent.tool_output_limit = 16384
    result = cmd_tool_output_limit(agent, "")
    assert "16384" in result.text
    result = cmd_tool_output_limit(agent, "8192")
    assert agent.tool_output_limit == 8192
    result = cmd_tool_output_limit(agent, "64")
    assert "Error" in result.text
    assert str(MIN_TOOL_OUTPUT_LIMIT) in result.text
    result = cmd_tool_output_limit(agent, "large")
    assert "Error" in result.text
    assert "number" in result.text


def test_cmd_tdetails_show_current(agent):
    agent.tool_details = True
    result = cmd_tool_details(agent, "")
    assert "on" in result.text

    agent.tool_details = False
    result = cmd_tool_details(agent, "on")
    assert "enabled" in result.text
    assert agent.tool_details is True

    agent.tool_details = True
    result = cmd_tool_details(agent, "off")
    assert "disabled" in result.text
    assert agent.tool_details is False

    result = cmd_tool_details(agent, "maybe")
    assert "Error" in result.text
    assert "on" in result.text and "off" in result.text


def test_cmd_tools_lists_tools(agent):
    result = cmd_tools(agent, "")
    assert "Available tools:" in result.text
    assert len(agent.tools) > 0


def test_cmd_name_with_custom_name(media_manager, agent):
    result = cmd_name(agent, "Test Project")
    assert "test-project" in result.text.lower()
    assert media_manager.current_subdir.name.endswith("test-project")


def test_cmd_name_without_name(media_manager, agent):
    original_name = media_manager.current_subdir.name
    assert original_name.startswith(".")

    result = cmd_name(agent, "")
    assert "permanent" in result.text.lower()
    assert not media_manager.current_subdir.name.startswith(".")


def test_ensure_contained_valid_path(agent):
    test_file = agent.media_manager.current_subdir / "test.txt"
    test_file.write_text("test")

    resolved = _ensure_contained(agent, "test.txt")
    assert resolved.exists()
    assert resolved.name == "test.txt"


def test_ensure_contained_prevents_escape(agent):
    with pytest.raises(ValueError, match="escapes"):
        _ensure_contained(agent, "../escape.txt")


def test_ensure_contained_prevents_absolute_escape(agent):
    with pytest.raises(ValueError, match="escapes"):
        _ensure_contained(agent, "/etc/passwd")


def test_ensure_contained_no_active_subdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)
        agent = Agent(media_manager=manager, model_name="haiku")

        with pytest.raises(ValueError, match="No active"):
            _ensure_contained(agent, "file.txt")


def test_cmd_read_missing_file(agent):
    result = cmd_read(agent, "nonexistent.txt")
    assert "Error" in result.text or "not found" in result.text.lower()


def test_cmd_read_escape_attempt(agent):
    result = cmd_read(agent, "../escape.txt")
    assert "Error" in result.text or "escapes" in result.text


def test_cmd_read_valid_file(agent):
    test_file = agent.media_manager.current_subdir / "test.txt"
    test_file.write_text("Hello World")

    result = cmd_read(agent, "test.txt")
    assert "Hello World" in result.text


def test_cmd_read_with_size_limit(agent):
    test_file = agent.media_manager.current_subdir / "large.txt"
    test_file.write_text("x" * 10000)

    result = cmd_read(agent, "large.txt 1")
    assert len(result.text) < 10000


def test_format_annotation_simple_type():
    assert _format_annotation(int) == "int"
    assert _format_annotation(str) == "str"
    assert _format_annotation(bool) == "bool"


def test_format_annotation_complex_type():
    result = _format_annotation(List[str])
    assert "list" in result.lower() or "List" in result

    result = _format_annotation(Optional[int])
    assert "optional" in result.lower() or "Optional" in result or "int" in result
