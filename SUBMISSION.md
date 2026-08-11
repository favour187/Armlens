# Devpost submission — armlens (copy/paste ready)

**Track:** Cloud AI
**Repo:** https://github.com/<you>/armlens  (public, MIT license visible in About)

---

## Project Overview
`armlens` is a reproducible LLM inference optimization & benchmarking toolkit for Arm64
servers. It turns a bare Arm VM (AWS Graviton, Oracle/GCP/Azure Ampere/Cobalt/Axion, or any
Neoverse box) into a rigorous, self‑documenting benchmark of Arm LLM inference — building
`llama.cpp` with Arm's **KleidiAI** kernels, sweeping a model across quantization levels and
thread counts, and generating a shareable HTML + Markdown report with charts.

**What makes it interesting / why it should win:** most "Arm‑optimized" projects can't be
independently verified. armlens is built around *proof*: one command from a bare VM to a report,
every number sourced from `llama.cpp`'s own `llama-bench`, and an honesty guardrail that
*refuses to run on non‑Arm hosts*. It's a reusable artifact the whole Arm developer community
can point at their own models — exactly the kind of tooling the challenge asks for.

## Functionality / Output
- `armlens info` — detects the Arm64 CPU and the ISA features KleidiAI exploits (`i8mm`,
  dotprod/`asimddp`, SVE, bf16), cores, RAM, and cloud SKU.
- `armlens bench --preset quant-sweep --report` — benchmarks every model in `models/` across a
  thread sweep, measuring **decode tok/s**, **prefill/TTFT**, and **model size**.
- **Outputs:** `results/report.html` (self‑contained, inline‑SVG charts), `report.md` (renders on
  GitHub), and `results.json` (machine‑readable for CI regression / SKU comparison).
- **Live demo:** `./demo/serve_demo.sh` starts a private, offline chat UI where every token is
  generated on the Arm CPU, showing live TTFT and tok/s in the browser.

Representative headline (real runs overwrite it): *TinyLlama‑1.1B Q4_0 decodes ~3× faster than
F16 at ~3.5× smaller on disk on Arm.*

## Setup Instructions (Arm64)
```bash
# Get a free Arm box: Oracle Cloud Always-Free Ampere A1 (see docs/PROVISION_ARM.md)
git clone https://github.com/<you>/armlens.git && cd armlens
./scripts/setup_arm.sh          # builds llama.cpp + KleidiAI, installs armlens, fetches a model
source .venv/bin/activate
armlens info                    # confirms ✅ Arm64 + accel features
./scripts/make_quant_variants.sh   # optional: create Q8_0 + F16 for a quant sweep
armlens bench --preset quant-sweep --report
# open results/report.html
```
Validation: `python -m pytest tests/ -q` (architecture‑independent). CI runs the suite on a
GitHub `ubuntu-24.04-arm` runner and asserts Arm64 detection.

## Optimizations demonstrated (mapped to the brief)
- **Model size** — quant sweep reports MB/level + size‑reduction factor.
- **Model speed** — decode tok/s and prefill (TTFT proxy).
- **Inference‑server speed** — thread‑scaling sweep finds throughput‑optimal core count.
- **Arm‑specific** — builds llama.cpp `-DGGML_CPU_KLEIDIAI=ON`; detects/reports i8mm/dotprod/SVE/bf16.
- **Developer experience** — one script bare‑VM → report; offline HTML; JSON for CI gates.

---

## 3‑minute demo video script (optional but recommended)
1. **(0:00–0:20) Hook.** "Everyone says they optimized for Arm — here's how to *prove* it in
   one command." Show the repo + MIT license.
2. **(0:20–0:50) Provision.** Show an Oracle Ampere / Graviton instance; `git clone`; run
   `./scripts/setup_arm.sh` (fast‑forward the build).
3. **(0:50–1:20) Detect.** `armlens info` — highlight ✅ Arm64 and `i8mm`, dotprod, SVE, bf16.
4. **(1:20–2:10) Benchmark.** `armlens bench --preset quant-sweep --report`; open
   `results/report.html`; point at the headline speedup, the three charts, and the size win.
5. **(2:10–2:45) Live demo.** `./demo/serve_demo.sh`; chat in the browser; point at live
   TTFT + tok/s — "all on the Arm CPU, nothing leaves the box."
6. **(2:45–3:00) Close.** "Reusable, honest, reproducible — armlens. MIT licensed."
