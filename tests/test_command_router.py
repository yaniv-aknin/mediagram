"""Tests for command routing mechanism."""

from mediagram.agent.commands import CommandRouter, AgentResponse


def test_command_router_register_and_handle():
    router = CommandRouter(lambda **kwargs: None)

    def mock_handler(agent, args_string):
        return AgentResponse(text=f"Handler called with {args_string}")

    CommandRouter.register("test", mock_handler)
    result = router.handle("/test arg1 arg2", None)

    assert result.text == "Handler called with arg1 arg2"


def test_command_router_help():
    router = CommandRouter(lambda **kwargs: None)

    def cmd1(agent, args):
        """First command"""
        pass

    def cmd2(agent, args):
        """Second command"""
        pass

    CommandRouter.register("cmd1", cmd1)
    CommandRouter.register("cmd2", cmd2)

    result = router.handle("/help", None)
    assert "Available commands:" in result.text
    assert "/cmd1 - First command" in result.text
    assert "/cmd2 - Second command" in result.text


def test_command_router_unknown_command():
    router = CommandRouter(lambda **kwargs: None)
    result = router.handle("/nonexistent_unique_test", None)

    assert "Unknown command: /nonexistent_unique_test" in result.text
    assert "Available commands:" in result.text


def test_command_router_handles_empty_args():
    router = CommandRouter(lambda **kwargs: None)
    result = router.handle("/help", None)
    assert "Available commands:" in result.text
