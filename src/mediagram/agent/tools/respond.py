from ..callbacks import SuccessMessage
from . import tool


@tool
async def respond(message: str, success: bool = True):
    """Yield control back to the user with a response message.

    Use this tool when you have completed the user's instruction and want to
    return control to them. This indicates you are done with your autonomous
    turn and are ready for the next user instruction.

    Args:
        message: The message to send to the user
        success: Whether you successfully completed the instruction (default: True)
    """
    status = "✓" if success else "⚠"
    yield SuccessMessage(f"{status} {message}")
