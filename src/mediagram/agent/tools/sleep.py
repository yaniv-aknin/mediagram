import asyncio

from ..callbacks import ProgressMessage, SuccessMessage, ErrorMessage
from . import tool


@tool
async def sleep(duration_seconds: float, update_count: int, success: bool):
    """Example tool that runs for specified duration and sends progress updates.

    Args:
        duration_seconds: How long the tool should run
        update_count: Number of progress updates to send
        success: Whether to succeed or fail after the duration
    """
    if update_count < 0:
        raise ValueError(f"update_count must be >= 0, got {update_count}")

    if duration_seconds < 0:
        raise ValueError(f"duration_seconds must be >= 0, got {duration_seconds}")

    start_time = asyncio.get_event_loop().time()
    interval = duration_seconds / max(update_count, 1) if update_count > 0 else 0

    for i in range(update_count):
        elapsed = asyncio.get_event_loop().time() - start_time
        completion_ratio = (i + 1) / update_count if update_count > 0 else 1.0
        remaining_time = duration_seconds - elapsed

        yield ProgressMessage(
            text=f"Progress update {i + 1}/{update_count}",
            completion_ratio=completion_ratio,
            completion_eta_minutes=remaining_time / 60,
        )

        if i < update_count - 1:
            await asyncio.sleep(interval)

    elapsed = asyncio.get_event_loop().time() - start_time
    if elapsed < duration_seconds:
        await asyncio.sleep(duration_seconds - elapsed)

    if success:
        yield SuccessMessage(
            f"Successfully completed after {duration_seconds} seconds with {update_count} updates"
        )
    else:
        yield ErrorMessage("Test tool failed as requested")
