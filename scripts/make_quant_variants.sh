#!/usr/bin/env bash







set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUANT="$ROOT/llama.cpp/build/bin/llama-quantize"
MODELS="$ROOT/models"
[[ -x "$QUANT" ]] || { echo "llama-quantize not found — run scripts/setup_arm.sh first."; exit 1; }


BASE="${1:-}"
if [[ -z "$BASE" ]]; then
  BASE="$MODELS/tinyllama-1.1b-chat-f16.gguf"
  if [[ ! -f "$BASE" ]]; then
    echo "==> Downloading TinyLlama F16 base (~2.2 GB) for quantization…"
    curl -L --fail -o "$BASE" \
      "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.fp16.gguf" \
      || { echo "Download failed. Pass a base .gguf explicitly."; exit 1; }
  fi
fi
echo "==> Base model: $BASE"

make_variant () {
  local qtype="$1" out="$2"
  if [[ -f "$out" ]]; then echo "  (exists) $(basename "$out")"; return; fi
  echo "==> Quantizing -> $qtype"
  "$QUANT" "$BASE" "$out" "$qtype"
}

make_variant Q4_0 "$MODELS/tinyllama-1.1b-chat-q4_0.gguf"
make_variant Q8_0 "$MODELS/tinyllama-1.1b-chat-q8_0.gguf"


echo
echo "✓ Quant variants ready in $MODELS:"
ls -lh "$MODELS"/*.gguf
echo
echo "Now run:  armlens bench --preset quant-sweep --report"
