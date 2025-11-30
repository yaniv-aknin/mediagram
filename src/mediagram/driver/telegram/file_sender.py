import time
from pathlib import Path
from pyrogram import Client
from pyrogram.enums import ChatAction
from pyrogram.errors import RPCError


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f}GB"


async def send_file_with_progress(
    app: Client,
    chat_id: int,
    file_path: Path,
    last_action_time: dict[int, float],
) -> str:
    file_size_bytes = file_path.stat().st_size
    size_str = format_file_size(file_size_bytes)

    await app.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
    last_action_time[chat_id] = time.time()

    if file_size_bytes > 10 * 1024 * 1024:
        progress_msg = await app.send_message(
            chat_id, f"Sending {file_path.name} ({size_str})"
        )

        last_progress = {"percent": 0, "time": 0}

        async def progress_callback(current, total):
            percent = current * 100 / total
            current_time = time.time()

            if (
                chat_id not in last_action_time
                or (current_time - last_action_time[chat_id]) >= 4
            ):
                try:
                    await app.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
                    last_action_time[chat_id] = current_time
                except RPCError:
                    pass

            if (
                percent - last_progress["percent"] >= 5
                or current_time - last_progress["time"] >= 5
            ):
                try:
                    await app.edit_message_text(
                        chat_id=chat_id,
                        message_id=progress_msg.id,
                        text=f"Sending {file_path.name} ({size_str}) - {percent:.1f}%",
                    )
                    last_progress["percent"] = percent
                    last_progress["time"] = current_time
                except RPCError:
                    pass

        await app.send_document(
            chat_id=chat_id,
            document=str(file_path),
            file_name=file_path.name,
            progress=progress_callback,
        )

        try:
            await app.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.id,
                text=f"Sent {file_path.name} ({size_str})",
            )
        except RPCError:
            pass
    else:
        await app.send_document(
            chat_id=chat_id,
            document=str(file_path),
            file_name=file_path.name,
        )

    return f"Sent {file_path.name} ({size_str})"
