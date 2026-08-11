#!/usr/bin/env bash
# armlens · run-everything script
# --------------------------------
# Paste-and-go on a fresh Arm64 VM (Oracle Ampere A1 or AWS Graviton). It will:
#   1. install deps + build llama.cpp with KleidiAI
#   2. fetch a model and create quant variants (Q4_0 / Q8_0 / F16)
#   3. run the full benchmark sweep and generate results/report.html
#   4. (optional) commit + push the REAL results back to your GitHub repo
#
# Usage on the VM:
#   git clone https://github.com/favour187/Armlens.git armlens && cd armlens
#   ./scripts/run_all.sh                 # build + benchmark only
#   PUSH=1 ./scripts/run_all.sh          # also commit + push results (asks for a fresh token)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN="\033[1;32m"; BLUE="\033[1;36m"; YEL="\033[1;33m"; NC="\033[0m"
say(){ echo -e "${BLUE}==>${NC} $*"; }
ok(){ echo -e "${GREEN}✓${NC} $*"; }

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  echo -e "${YEL}This is '$ARCH', not Arm64. Run this on an Arm server (Oracle Ampere / AWS Graviton).${NC}"
  echo "See docs/PROVISION_ARM.md. Aborting so results stay honest."
  exit 1
fi

# 1. build + install
say "Step 1/4 — setup (build llama.cpp + KleidiAI, install armlens, fetch model)"
./scripts/setup_arm.sh
# shellcheck disable=SC1091
source .venv/bin/activate

say "Detected platform:"
armlens info

# 2. quant variants (best-effort; sweep still works with whatever models exist)
say "Step 2/4 — creating quant variants for the sweep"
./scripts/make_quant_variants.sh || echo -e "${YEL}quant variants skipped — sweep will use available models${NC}"

# 3. benchmark + report
say "Step 3/4 — benchmarking + generating report"
armlens bench --preset quant-sweep --report
ok "Report ready: results/report.html  (and report.md, results.json)"

# 4. optional push of real results
if [[ "${PUSH:-0}" == "1" ]]; then
  say "Step 4/4 — committing real results back to the repo"
  read -r -p "GitHub username [favour187]: " GH_USER; GH_USER="${GH_USER:-favour187}"
  read -r -s -p "Fresh GitHub token (input hidden): " GH_TOKEN; echo
  REPO="${REPO:-https://github.com/favour187/Armlens.git}"
  # allow committing the generated results this one time
  git add -f results/report.md results/results.json results/report.html 2>/dev/null || true
  git config user.name  "$GH_USER" 2>/dev/null || true
  git config user.email "${GH_USER}@users.noreply.github.com" 2>/dev/null || true
  git commit -m "Add real Arm64 benchmark results ($(uname -m), $(nproc) cores)" || echo "nothing to commit"
  # push without persisting the token in git config
  PUSH_URL="https://${GH_USER}:${GH_TOKEN}@${REPO#https://}"
  git push "$PUSH_URL" HEAD:main 2>&1 | sed -E 's/ghp_[A-Za-z0-9_]+/***TOKEN***/g; s/github_pat_[A-Za-z0-9_]+/***TOKEN***/g'
  unset GH_TOKEN PUSH_URL
  ok "Pushed real results to $REPO"
  echo -e "${YEL}Reminder: revoke that token after if you won't reuse it.${NC}"
else
  echo
  ok "Done. To copy the report to your laptop:"
  echo "   scp <user>@<vm-ip>:$ROOT/results/report.html ."
  echo "Or re-run with:  PUSH=1 ./scripts/run_all.sh   to push results to GitHub."
fi
