#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def main():
    cmd = ["docker", "run", "--rm"]

    local_env = Path(".env")
    if local_env.exists():
        cmd.extend(["--env-file", str(local_env)])
        print(f"Using environment file: {local_env}")

    mediagram_d = Path.home() / ".mediagram.d"
    if mediagram_d.exists():
        cmd.extend(["-v", f"{mediagram_d}:/root/.mediagram.d:rw"])
        print(f"Mounting directory: {mediagram_d}")

    media_dir = Path.home() / ".mediagram.d" / "media"
    if media_dir.exists():
        resolved_media = media_dir.resolve()
        cmd.extend(["-v", f"{resolved_media}:/media:rw"])
        print(f"Mounting media directory: {resolved_media}")

    cmd.append("mediagram")

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)


if __name__ == "__main__":
    main()
