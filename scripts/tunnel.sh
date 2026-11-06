#!/usr/bin/env bash
# Forward the bench from the GPU box to this laptop.
# The server on the box must already be listening on 127.0.0.1:8787.
set -euo pipefail
: "${AWS_HOST:?Set AWS_HOST}"
: "${AWS_USER:?Set AWS_USER}"
: "${AWS_PEM_PATH:?Set AWS_PEM_PATH}"
PORT="${AWS_PORT:-22}"
LOCAL="${LOCAL_PORT:-8787}"
REMOTE="${REMOTE_PORT:-8787}"
exec ssh \
  -i "$AWS_PEM_PATH" \
  -p "$PORT" \
  -o StrictHostKeyChecking=accept-new \
  -o IdentitiesOnly=yes \
  -N \
  -L "${LOCAL}:127.0.0.1:${REMOTE}" \
  "${AWS_USER}@${AWS_HOST}"
