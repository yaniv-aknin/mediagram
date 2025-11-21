#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run mediagram container")
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Drop into interactive shell"
    )
    args = parser.parse_args()

    cmd = ["docker", "run", "--rm"]

    if args.interactive:
        cmd.append("-it")

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

    if args.interactive:
        cmd.append("/bin/bash")
    else:
        cmd.extend(["mediagram", "run", "telegram"])

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
