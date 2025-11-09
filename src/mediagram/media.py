import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MediaManager:
    """Manages media directories and conversation logging."""

    media_dir: Path
    current_subdir: Path | None = field(default=None, init=False)
    _temp_dir: tempfile.TemporaryDirectory | None = field(default=None, init=False)

    @classmethod
    def create(cls, media_dir_override: str | None = None) -> "MediaManager":
        """
        Create a MediaManager with the appropriate media directory.

        Selection order:
        1. media_dir_override (from --media-dir flag)
        2. /media if it exists and is writable
        3. ~/.mediagram.d/media if it exists (may be a symlink)
        4. ephemeral tmpdir (with warning)
        """
        if media_dir_override:
            media_dir = Path(media_dir_override)
            media_dir.mkdir(parents=True, exist_ok=True)
            return cls(media_dir=media_dir)

        media_path = Path("/media")
        if media_path.exists():
            try:
                test_subdir = media_path / "test_write"
                test_subdir.mkdir(exist_ok=True)
                test_subdir.rmdir()
                return cls(media_dir=media_path)
            except (PermissionError, OSError):
                pass

        home_media = Path.home() / ".mediagram.d" / "media"
        if home_media.exists():
            return cls(media_dir=home_media)

        temp_dir = tempfile.TemporaryDirectory()
        print(f"⚠️  Using ephemeral tmpdir: {temp_dir.name}")
        manager = cls(media_dir=Path(temp_dir.name))
        manager._temp_dir = temp_dir
        return manager

    def create_subdir(self) -> Path:
        """Create a new anonymous media subdirectory with leading dot."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        counter = 0
        while True:
            subdir_name = f".{timestamp}.{counter}"
            subdir = self.media_dir / subdir_name
            if not subdir.exists():
                subdir.mkdir(parents=True, exist_ok=False)
                break
            counter += 1

        self.current_subdir = subdir
        return subdir

    def reset_subdir(self) -> Path:
        """Reset the current subdirectory (used when /clear is called)."""
        return self.create_subdir()

    def rename_subdir(self, name: str | None = None) -> Path:
        """
        Rename current subdirectory from anonymous to named.
        If name is None, just removes the leading dot.
        If name is provided, converts '.20251114-070913.0' to '20251114-slugified-name'.
        """
        if not self.current_subdir:
            raise ValueError("No current subdirectory to rename")

        current_name = self.current_subdir.name

        if current_name.startswith("."):
            timestamp_part = current_name[1:16]
        else:
            timestamp_part = current_name[:15]

        if name:
            slugified = self._slugify(name)
            new_name = f"{timestamp_part}-{slugified}"
        else:
            new_name = timestamp_part

        new_subdir = self.media_dir / new_name

        if new_subdir.exists():
            raise ValueError(f"Directory {new_name} already exists")

        self.current_subdir.rename(new_subdir)
        self.current_subdir = new_subdir
        return new_subdir

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-safe slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text

    def get_messages_file(self) -> Path:
        """Get the path to the messages.jsonl file in the current subdir."""
        if not self.current_subdir:
            self.create_subdir()
        return self.current_subdir / "messages.jsonl"

    def log_message(self, role: str, content: str | dict, **metadata) -> None:
        """
        Log a message to messages.jsonl.

        Args:
            role: The role (user, assistant, system, etc.)
            content: The message content (string or dict for tool calls)
            **metadata: Additional metadata to log (name, username, timestamp, etc.)
        """
        if not self.current_subdir:
            self.create_subdir()

        message_entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            **metadata,
        }

        messages_file = self.get_messages_file()
        with messages_file.open("a") as f:
            json.dump(message_entry, f, ensure_ascii=False)
            f.write("\n")

    def cleanup(self) -> None:
        """Clean up temporary resources if needed."""
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None
