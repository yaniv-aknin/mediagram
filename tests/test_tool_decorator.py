import pytest

from mediagram.agent.tools import tool, set_driver_callbacks
from mediagram.agent.callbacks import (
    ProgressMessage,
    SuccessMessage,
    ErrorMessage,
    StartMessage,
)


class MockCallbacks:
    def __init__(self):
        self.starts = []
        self.progress = []
        self.success = []
        self.errors = []

    async def on_tool_start(self, start: StartMessage, tool_id: str) -> None:
        self.starts.append(start)

    async def on_tool_progress(self, progress: ProgressMessage, tool_id: str) -> None:
        self.progress.append(progress)

    async def on_tool_success(self, success: SuccessMessage, tool_id: str) -> None:
        self.success.append(success)

    async def on_tool_error(self, error: ErrorMessage, tool_id: str) -> None:
        self.errors.append(error)


@pytest.mark.asyncio
async def test_tool_happy_path():
    @tool
    async def my_tool():
        yield ProgressMessage("Step 1")
        yield ProgressMessage("Step 2")
        yield SuccessMessage("Done!")

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert result == "Done!"
    assert len(callbacks.progress) == 2
    assert callbacks.progress[0].text == "Step 1"
    assert len(callbacks.success) == 1
    assert len(callbacks.errors) == 0


@pytest.mark.asyncio
async def test_tool_yields_error_message():
    @tool
    async def my_tool():
        yield ProgressMessage("Starting...")
        yield ErrorMessage("Failed!", error=ValueError("bad input"))

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert result == "Failed!"
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0].text == "Failed!"
    assert isinstance(callbacks.errors[0].error, ValueError)
    assert len(callbacks.success) == 0


@pytest.mark.asyncio
async def test_tool_raises_exception():
    @tool
    async def my_tool():
        yield ProgressMessage("Working...")
        raise RuntimeError("Something broke")

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert "Error: Something broke" in result
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0].unexpected is True
    assert isinstance(callbacks.errors[0].error, RuntimeError)


@pytest.mark.asyncio
async def test_tool_raises_error_message():
    @tool
    async def my_tool():
        yield ProgressMessage("Checking...")
        raise ErrorMessage("Invalid input", error=ValueError("x < 0"))

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert result == "Invalid input"
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0].unexpected is False


@pytest.mark.asyncio
async def test_tool_no_final_message():
    @tool
    async def my_tool():
        yield ProgressMessage("Working...")
        yield ProgressMessage("Still working...")

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert "Error: Tool did not yield a final result" in result
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0].unexpected is True


@pytest.mark.asyncio
async def test_tool_yields_after_final():
    @tool
    async def my_tool():
        yield SuccessMessage("Done!")
        yield ProgressMessage("Wait, more work...")

    callbacks = MockCallbacks()
    set_driver_callbacks(callbacks)

    result = await my_tool()

    assert "Error:" in result
    assert "yielded past the final message" in result
    assert len(callbacks.errors) == 1
    assert callbacks.errors[0].unexpected is True


@pytest.mark.asyncio
async def test_tool_without_callbacks():
    @tool
    async def my_tool():
        yield ProgressMessage("Working...")
        yield SuccessMessage("Done!")

    set_driver_callbacks(None)

    result = await my_tool()

    assert result == "Done!"
