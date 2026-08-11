<div align="center">

# 🔎 armlens

### Reproducible LLM inference optimization & benchmarking for Arm64 servers

**Prove your Arm optimization with one command.** `armlens` builds `llama.cpp` with Arm's
**KleidiAI** kernels, benchmarks a model across quantization levels and thread counts on
**Arm64** (AWS Graviton · Oracle/GCP/Azure Ampere/Cobalt/Axion · Neoverse), and generates a
shareable **HTML + Markdown report** with charts — measuring exactly the metrics that matter:
**tokens/sec, time‑to‑first‑token, throughput, and model size.**

[![ci](https://img.shields.io/badge/CI-unit%20%2B%20arm64-brightgreen)](.github/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![arch](https://img.shields.io/badge/target-Arm64%20(aarch64)-00A3E0)](#)

*Arm Create: AI Optimization Challenge 2026 — Cloud AI track.*

</div>

---

## Why this exists

Everyone claims "we optimized for Arm." Almost nobody ships something a judge can **re‑run
in 5 minutes and see the numbers**. `armlens` is that missing piece: a tiny, dependency‑light
toolkit that turns a bare Arm64 VM into a rigorous, self‑documenting benchmark of Arm LLM
inference — and hands you a report you can drop straight into a blog post or a submission.

- ✅ **Real numbers, never faked.** Every timing comes from `llama.cpp`'s own `llama-bench`.
  On a non‑Arm host, `armlens` *refuses to run* rather than produce misleading results.
- ✅ **Arm‑specific.** Detects and reports the ISA features KleidiAI exploits
  (`i8mm`, `asimddp`/dotprod, `sve`, `bf16`) and builds llama.cpp with `GGML_CPU_KLEIDIAI=ON`.
- ✅ **Reusable artifact.** A CLI + report format any developer can point at their own model.
- ✅ **WOW demo.** A private, offline chat UI running a model on Arm CPU, showing live
  TTFT and tok/s in the browser.

---

## The result it produces

Running the quant sweep on an Arm64 box yields a headline like:

> **TinyLlama‑1.1B Q4_0** decodes at **58.9 tok/s** vs **F16** at **19.6 tok/s** —
> a **3.0× speedup** with a **3.5× smaller** model on disk.

…plus a full table (per quant × per thread count, prefill + decode) and three charts
(throughput, model size, thread scaling). See a rendered example:
[`examples/sample-graviton/report.html`](examples/sample-graviton/report.html)
([Markdown version](examples/sample-graviton/report.md)).

> ℹ️ The numbers in `examples/` are **illustrative sample data** to show the report format.
> Your `armlens bench` run overwrites them with the real numbers from *your* Arm machine.

---

## Quick start (on an Arm64 server)

**Don't have an Arm machine?** Get one free: **Oracle Cloud "Always Free" Ampere A1**
(up to 4 vCPU / 24 GB, no cost) — see [`docs/PROVISION_ARM.md`](docs/PROVISION_ARM.md).
Or launch an AWS Graviton `c7g.xlarge` for ~$0.15/hr.

```bash
# 1. Clone
git clone https://github.com/<you>/armlens.git && cd armlens

# 2. One-command setup: builds llama.cpp + KleidiAI, installs armlens, fetches a model
./scripts/setup_arm.sh
source .venv/bin/activate

# 3. Confirm you're on Arm and see the accel features
armlens info

# 4. (optional) create Q8_0 + F16 variants so the sweep can compare quant levels
./scripts/make_quant_variants.sh

# 5. Benchmark + generate the report
armlens bench --preset quant-sweep --report

# 6. Open results/report.html   (scp it back, or serve it)
```

That's it. `results/report.html`, `report.md`, and machine‑readable `results.json` appear
in `./results/`.

---

## Commands

| Command | What it does |
|---|---|
| `armlens info` | Detect Arm64 CPU, cores, RAM, and KleidiAI‑relevant ISA features. |
| `armlens bench --preset quant-sweep --report` | Sweep every `models/*.gguf` across a thread sweep; write reports. |
| `armlens bench --model q4=models/a.gguf --model f16=models/b.gguf --threads 1,2,4 --report` | Fully custom run. |
| `armlens report results/results.json` | Re‑render HTML/MD from a saved run (great for CI diffs). |

**Presets:** `quick` (fast sanity), `quant-sweep` (default, balanced), `thorough` (5 reps, long).

---

## Live demo: a private LLM on Arm CPU 🔒

```bash
./demo/serve_demo.sh          # starts llama-server (KleidiAI) + a tiny web UI
# open http://<server-ip>:8080
```

A clean chat interface where **every token is generated on the Arm64 CPU** — no GPU, no
cloud API, nothing leaves the box. Each reply shows live **TTFT** and **tok/s**, so the
optimization is visible to anyone, not just people who read benchmark tables.

---

## What "optimization" means here (mapped to the judging brief)

| Challenge optimization axis | How armlens addresses it |
|---|---|
| **Model size** | Quant sweep quantifies MB‑on‑disk per level; report shows the size‑reduction factor. |
| **Model speed** | Measures decode tok/s **and** prefill (TTFT proxy) via `llama-bench`. |
| **Inference server speed** | Thread‑scaling sweep finds the throughput‑optimal core count on your Arm SKU. |
| **Arm‑specific optimization** | Builds llama.cpp with `GGML_CPU_KLEIDIAI=ON`; detects/reports `i8mm`, dotprod, SVE, bf16. |
| **Developer experience** | One script from bare VM → report; self‑contained HTML; JSON for CI regression gates. |

---

## How it works

```
armlens info    ─► sysinfo.py   detect aarch64 + HWCAP features (i8mm, dotprod, sve, bf16)
armlens bench   ─► benchmark.py drive llama-bench (-o json), parse pp/tg tok/s per thread
                ─► report.py     summarize → results.json + report.md + self-contained report.html
setup_arm.sh    ─► build llama.cpp with -DGGML_CPU_KLEIDIAI=ON, fetch a GGUF model
serve_demo.sh   ─► llama-server (OpenAI API) + static chat UI, CPU-only on Arm
```

Design choices that matter for judging:
- **No fabricated data.** Timings are llama.cpp's; armlens only orchestrates + parses.
- **Honest guardrail.** `bench` exits on non‑Arm hosts unless you explicitly `--allow-non-arm`.
- **Zero heavy deps.** Core needs only `rich`; charts are hand‑rendered inline **SVG** so the
  HTML report opens offline anywhere (matplotlib is an optional extra).
- **CI on real Arm.** `.github/workflows/ci.yml` runs the suite on a GitHub `ubuntu-24.04-arm`
  runner and asserts Arm64 detection.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/PROVISION_ARM.md`](docs/PROVISION_ARM.md).

---

## Reproducibility & validation

- Unit tests (`pytest tests/`) validate parsing, headline math, and report self‑containment on
  any architecture.
- `results.json` fully captures the platform + every measurement, so runs are comparable
  across machines and over time.
- Re‑render any past run: `armlens report results/results.json`.

---

## Roadmap

- [ ] Optional `vLLM` + INT4 backend for larger Arm instances.
- [ ] `ONNX Runtime` backend for non‑LLM models (SqueezeNet/Whisper on Arm).
- [ ] `armlens compare a.json b.json` to diff two Arm SKUs (e.g. Graviton3 vs Graviton4).

---

## License

MIT — see [LICENSE](LICENSE). Built for the **Arm Create: AI Optimization Challenge 2026**.
Uses [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT) and Arm
[KleidiAI](https://gitlab.arm.com/kleidi/kleidiai) kernels.
