"""Tests for the agentic tool-calling loop using mock models."""

import tempfile

import pytest

from mediagram.agent import Agent
from mediagram.media import MediaManager


class MockAsyncModel:
    """Mock async model for testing the agentic loop."""

    def __init__(self):
        self.conversation_history = []
        self._response_queue = []
        self._current_conversation = None

    def enqueue_response(self, text, tool_calls=None):
        """Enqueue a response for the mock model to return."""
        self._response_queue.append({"text": text, "tool_calls": tool_calls or []})

    def conversation(self, tools=None, before_call=None, after_call=None):
        """Create a mock conversation."""
        conv = MockConversation(
            self, tools=tools, before_call=before_call, after_call=after_call
        )
        self._current_conversation = conv
        return conv


class MockConversation:
    """Mock conversation for testing."""

    def __init__(self, model, tools=None, before_call=None, after_call=None):
        self.model = model
        self.tools = tools or []
        self.before_call = before_call
        self.after_call = after_call
        self.prompt_history = []

    def prompt(self, message, system=None, tools=None, tool_results=None):
        """Mock prompt that returns a mock response."""
        self.prompt_history.append(
            {
                "message": message,
                "system": system,
                "tools": tools,
                "tool_results": tool_results,
            }
        )

        if self.model._response_queue:
            response_data = self.model._response_queue.pop(0)
        else:
            raise RuntimeError("No response available")

        return MockResponse(
            response_data["text"],
            response_data["tool_calls"],
            self.before_call,
            self.after_call,
        )


class MockResponse:
    """Mock response object."""

    def __init__(self, text, tool_calls, before_call=None, after_call=None):
        self._text = text
        self._tool_calls = tool_calls
        self.before_call = before_call
        self.after_call = after_call

    async def text(self):
        """Return the text response."""
        return self._text

    async def tool_calls(self):
        """Return tool calls if any."""
        return self._tool_calls

    async def execute_tool_calls(self, before_call=None, after_call=None):
        """Execute tool calls and return results."""
        results = []
        for tool_call in self._tool_calls:
            if before_call:
                await before_call(None, tool_call)

            result = MockToolResult(tool_call["name"], "mock result")
            results.append(result)

            if after_call:
                await after_call(None, tool_call, result)
        return results


class MockToolResult:
    """Mock tool result."""

    def __init__(self, name, output):
        self.name = name
        self.output = output


@pytest.fixture
def media_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MediaManager.create(media_dir_override=tmpdir)
        manager.create_subdir()
        yield manager


@pytest.fixture
def mocked_agent(media_manager):
    agent = Agent(media_manager=media_manager, model_name="haiku")
    mock_model = MockAsyncModel()
    agent.model = mock_model
    agent.conversation = mock_model.conversation(
        tools=agent.tools,
        before_call=agent._before_tool_call,
        after_call=agent._after_tool_call,
    )
    agent.mock_model = mock_model
    return agent


@pytest.mark.asyncio
async def test_agent_simple_message_no_tools(mocked_agent):
    mocked_agent.mock_model.enqueue_response("Hello! I'm here to help.")
    response = await mocked_agent.handle_message("Hello", name="TestUser")
    assert response.text == "Hello! I'm here to help."
    assert response.error is None


@pytest.mark.asyncio
async def test_agent_command_shortcut(mocked_agent):
    response = await mocked_agent.handle_message(
        "prompt will fail, no responses", name="TestUser"
    )
    assert response.error is not None
    response = await mocked_agent.handle_message("/help", name="TestUser")
    assert "Available commands:" in response.text
    assert response.error is None


@pytest.mark.asyncio
async def test_agent_max_turns_exhaustion(mocked_agent):
    mocked_agent.max_turns = 2
    mocked_agent.model.enqueue_response(
        "Let me use a tool",
        tool_calls=[{"name": "test_tool", "args": {}}],
    )
    mocked_agent.model.enqueue_response(
        "Using another tool",
        tool_calls=[{"name": "test_tool", "args": {}}],
    )
    mocked_agent.model.enqueue_response("Final response after tools")

    response = await mocked_agent.handle_message(
        "Do something complex", name="TestUser"
    )

    assert "ran out of autonomous turns" in response.text.lower()
    assert response.error is None


@pytest.mark.asyncio
async def test_agent_max_turns_infinite(mocked_agent):
    mocked_agent.max_turns = 0
    for x in range(100):
        mocked_agent.model.enqueue_response(
            "Let me use a tool",
            tool_calls=[{"name": "test_tool", "args": {}}],
        )
    mocked_agent.model.enqueue_response("Final response after tools")

    response = await mocked_agent.handle_message("Test", name="TestUser")

    assert "Final response after tools" in response.text
    assert "ran out" not in response.text.lower()


@pytest.mark.asyncio
async def test_agent_tool_call_with_completion(mocked_agent):
    mocked_agent.max_turns = 5
    mocked_agent.model.enqueue_response(
        "Using tool",
        tool_calls=[{"name": "test_tool", "args": {}}],
    )
    mocked_agent.model.enqueue_response("Task completed successfully")

    response = await mocked_agent.handle_message("Do a task", name="TestUser")

    assert "Task completed successfully" in response.text
    assert "ran out" not in response.text.lower()


@pytest.mark.asyncio
async def test_agent_error_handling(mocked_agent):
    """Test agent error handling during message processing."""

    class FailingResponse:
        async def text(self):
            raise RuntimeError("Simulated error")

        async def tool_calls(self):
            return []

    def failing_prompt(*args, **kwargs):
        return FailingResponse()

    mocked_agent.conversation.prompt = failing_prompt

    response = await mocked_agent.handle_message("Test", name="TestUser")

    assert response.error is not None
    assert "Simulated error" in response.error


@pytest.mark.asyncio
async def test_agent_logs_messages(mocked_agent):
    """Test that agent logs messages to media manager."""
    mocked_agent.mock_model.enqueue_response("Response")

    await mocked_agent.handle_message("Test message", name="TestUser")

    messages_file = mocked_agent.media_manager.get_messages_file()
    assert messages_file.exists()

    content = messages_file.read_text()
    assert "Test message" in content
    assert "Response" in content
