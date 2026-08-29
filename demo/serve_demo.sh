#!/usr/bin/env bash





set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER="$ROOT/llama.cpp/build/bin/llama-server"
MODEL="${MODEL:-$ROOT/models/tinyllama-1.1b-chat-q4_0.gguf}"
PORT="${PORT:-8080}"
THREADS="${THREADS:-$(nproc)}"

[[ -x "$SERVER" ]] || { echo "llama-server not found — run scripts/setup_arm.sh first."; exit 1; }
[[ -f "$MODEL" ]]  || { echo "Model not found: $MODEL"; exit 1; }

echo "==> Starting llama-server on Arm64 CPU"
echo "    model:   $(basename "$MODEL")"
echo "    threads: $THREADS   port: $PORT"
echo "    UI:      http://0.0.0.0:$PORT   (serves demo/index.html)"

exec "$SERVER" \
  -m "$MODEL" \
  --host 0.0.0.0 --port "$PORT" \
  --threads "$THREADS" \
  --ctx-size 2048 \
  --path "$ROOT/demo/public"
