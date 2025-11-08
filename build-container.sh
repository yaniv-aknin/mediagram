#!/bin/bash
set -e

IMAGE_NAME="${1:-mediagram}"

echo "Building Python package..."
uv build

echo "Building Docker image: ${IMAGE_NAME}..."
docker build -t "${IMAGE_NAME}" .

echo "Successfully built image: ${IMAGE_NAME}"
