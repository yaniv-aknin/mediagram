#!/usr/bin/env python3
import argparse
import shutil
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description="Build mediagram container with plugins")
parser.add_argument("-t", "--tag", default="mediagram", help="Image name/tag")
parser.add_argument(
    "plugins", nargs="*", help="Plugins (PyPI, git URLs, or local paths)"
)
args = parser.parse_args()

print("Building Python package...")
subprocess.run(["uv", "build"], check=True)

local_plugins = [p for p in args.plugins if Path(p).exists()]
remote_plugins = [p for p in args.plugins if p not in local_plugins]

plugin_dist = Path("dist-plugins")
if local_plugins:
    print("Building local plugins...")
    shutil.rmtree(plugin_dist, ignore_errors=True)
    plugin_dist.mkdir()
    for plugin in local_plugins:
        print(f"  Building: {plugin}")
        subprocess.run(
            ["uv", "build", "--out-dir", str(plugin_dist.absolute())],
            cwd=plugin,
            check=True,
        )
    print(
        f"Built local plugin wheels:\n{subprocess.run(['ls', '-lh', plugin_dist], capture_output=True, text=True).stdout}"
    )

docker_cmd = ["docker", "build", "-t", args.tag]
if remote_plugins:
    print(f"Remote plugins to install: {' '.join(remote_plugins)}")
    docker_cmd.extend(["--build-arg", f"REMOTE_PLUGINS={' '.join(remote_plugins)}"])
docker_cmd.append(".")

print(f"Building Docker image: {args.tag}...")
subprocess.run(docker_cmd, check=True)

shutil.rmtree(plugin_dist, ignore_errors=True)

print(f"Successfully built image: {args.tag}")
if remote_plugins:
    print(f"Installed remote plugins: {' '.join(remote_plugins)}")
if local_plugins:
    print(f"Installed local plugins: {' '.join(local_plugins)}")
