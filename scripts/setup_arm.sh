#!/usr/bin/env bash
# armlens · one-command Arm64 setup
# -----------------------------------
# Builds llama.cpp with Arm KleidiAI INT8/INT4 kernels enabled, installs armlens,
# and fetches a small demo model so you can benchmark immediately.
#
# Tested on: Oracle Cloud Ampere A1 (Ubuntu 22.04/24.04), AWS Graviton (c7g), any
# aarch64 Linux with apt. Safe to re-run (idempotent-ish).
#
# Usage:   ./scripts/setup_arm.sh
set -euo pipefail

BLUE="\033[1;36m"; GREEN="\033[1;32m"; RED="\033[1;31m"; YEL="\033[1;33m"; NC="\033[0m"
say()  { echo -e "${BLUE}==>${NC} $*"; }
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YEL}!${NC} $*"; }
die()  { echo -e "${RED}✗ $*${NC}"; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ---- 0. Sanity: must be Arm64 -------------------------------------------------
ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  warn "This host is '$ARCH', not Arm64."
  warn "armlens measures *Arm* optimization — run this on an Arm server."
  warn "Free option: Oracle Cloud 'Always Free' Ampere A1 (4 vCPU / 24 GB)."
  read -r -p "Continue anyway (build will still work but results won't reflect Arm)? [y/N] " a
  [[ "${a:-N}" =~ ^[Yy]$ ]] || die "Aborting. Provision an Arm64 VM and re-run."
fi
ok "Architecture: $ARCH"

# ---- 1. System dependencies ---------------------------------------------------
say "Installing build dependencies (needs sudo)…"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y build-essential cmake git curl libcurl4-openssl-dev \
                          python3 python3-pip python3-venv
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y gcc gcc-c++ make cmake git curl libcurl-devel python3 python3-pip
else
  warn "No apt/dnf found — install cmake, git, a C++ toolchain and libcurl manually."
fi
ok "Dependencies installed"

# ---- 2. Python venv + armlens -------------------------------------------------
say "Setting up Python environment…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[plots]" -q || pip install -e . -q
ok "armlens installed (run 'source .venv/bin/activate' in new shells)"

# ---- 3. Build llama.cpp WITH KleidiAI ----------------------------------------
# KleidiAI provides Arm's optimized micro-kernels for INT4/INT8 matmul. Modern
# llama.cpp auto-detects and enables them on Arm via GGML_CPU_KLEIDIAI.
LLAMA_DIR="$ROOT/llama.cpp"
if [[ ! -d "$LLAMA_DIR/.git" ]]; then
  say "Cloning llama.cpp…"
  git clone --depth 1 https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
else
  say "Updating llama.cpp…"
  git -C "$LLAMA_DIR" pull --ff-only || warn "pull skipped"
fi

say "Building llama.cpp with Arm KleidiAI kernels…"
cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" \
      -DCMAKE_BUILD_TYPE=Release \
      -DGGML_NATIVE=ON \
      -DGGML_CPU_KLEIDIAI=ON \
      -DLLAMA_CURL=ON
cmake --build "$LLAMA_DIR/build" --config Release -j"$(nproc)" \
      --target llama-bench llama-cli llama-server llama-quantize
ok "Built: llama-bench, llama-cli, llama-server, llama-quantize"

# Verify KleidiAI actually compiled in (best effort).
if strings "$LLAMA_DIR/build/bin/llama-bench" 2>/dev/null | grep -qi kleidi; then
  ok "KleidiAI symbols present in binary"
else
  warn "Could not confirm KleidiAI symbols (older llama.cpp?). Q4_0 will still use Arm dotprod/i8mm."
fi

# ---- 4. Fetch a small demo model ---------------------------------------------
mkdir -p "$ROOT/models"
MODEL_Q4="$ROOT/models/tinyllama-1.1b-chat-q4_0.gguf"
if [[ ! -f "$MODEL_Q4" ]]; then
  say "Downloading TinyLlama-1.1B-Chat (Q4_0, ~636 MB)…"
  curl -L --fail -o "$MODEL_Q4" \
    "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_0.gguf" \
    || warn "Model download failed — add a .gguf to ./models manually."
fi
[[ -f "$MODEL_Q4" ]] && ok "Model ready: $(basename "$MODEL_Q4")"

echo
ok "Setup complete."
echo -e "${GREEN}Next steps:${NC}"
echo "  source .venv/bin/activate"
echo "  armlens info                              # confirm Arm features"
echo "  ./scripts/make_quant_variants.sh          # (optional) create Q8_0 + F16 for a quant sweep"
echo "  armlens bench --preset quant-sweep --report"
echo "  # open results/report.html"
