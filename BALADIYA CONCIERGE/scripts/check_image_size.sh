#!/usr/bin/env bash
# T-042: Assert modelserver Docker image is < 500 MB.
# Usage: ./scripts/check_image_size.sh [image_tag]
# CI runs: docker build modelserver/ -t baladiya-modelserver:ci && ./scripts/check_image_size.sh baladiya-modelserver:ci

set -euo pipefail

IMAGE="${1:-baladiya-modelserver:ci}"
MAX_BYTES=524288000  # 500 MB in bytes

echo "Checking image size for: $IMAGE"

SIZE=$(docker image inspect "$IMAGE" --format '{{.Size}}' 2>/dev/null || echo "")

if [[ -z "$SIZE" ]]; then
  echo "ERROR: Image '$IMAGE' not found. Build it first with:"
  echo "  docker build modelserver/ -t $IMAGE"
  exit 1
fi

SIZE_MB=$(echo "scale=1; $SIZE / 1048576" | bc)
echo "Image size: ${SIZE_MB} MB (${SIZE} bytes)"
echo "Max allowed: 500 MB (${MAX_BYTES} bytes)"

if [[ "$SIZE" -gt "$MAX_BYTES" ]]; then
  echo "FAIL: Image exceeds 500 MB limit."
  exit 1
else
  echo "PASS: Image is within the 500 MB limit."
fi
