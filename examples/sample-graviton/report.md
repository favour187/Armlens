# armlens benchmark report

_Generated 2026-08-11 13:40 UTC by armlens v0.1.0._

## Platform

- **CPU:** Arm Neoverse-V1  (AWS Graviton)
- **Architecture:** `aarch64`  ✅ Arm64
- **Cores:** 4 physical / 4 logical
- **RAM:** 8.0 GB
- **Arm accel features (KleidiAI-relevant):** asimddp, i8mm, bf16, sve

## Headline result

> **TinyLlama-1.1B Q4_0** decodes at **58.9 tok/s** vs **TinyLlama-1.1B F16** at **19.6 tok/s** — a **3.01× speedup** with a **3.46× smaller** model on disk.

## Full results

| Model | Quant | Size (MB) | Threads | Test | Tokens/s | ±stddev |
|---|---|---|---|---|---|---|
| TinyLlama-1.1B F16 | F16 | 2200.0 | 4 | prefill (TTFT) | **88** | 1.2 |
| TinyLlama-1.1B F16 | F16 | 2200.0 | 4 | decode | **19.6** | 0.4 |
| TinyLlama-1.1B Q4_0 | Q4_0 | 636.0 | 1 | prefill (TTFT) | **48.2** | 0.6 |
| TinyLlama-1.1B Q4_0 | Q4_0 | 636.0 | 4 | prefill (TTFT) | **171.4** | 2.1 |
| TinyLlama-1.1B Q4_0 | Q4_0 | 636.0 | 1 | decode | **22.7** | 0.3 |
| TinyLlama-1.1B Q4_0 | Q4_0 | 636.0 | 4 | decode | **58.9** | 0.8 |
| TinyLlama-1.1B Q8_0 | Q8_0 | 1170.0 | 4 | prefill (TTFT) | **142** | 1.9 |
| TinyLlama-1.1B Q8_0 | Q8_0 | 1170.0 | 4 | decode | **39.5** | 0.5 |


## Reproduce

```bash
git clone <this-repo> && cd armlens
./scripts/setup_arm.sh          # builds llama.cpp w/ KleidiAI + fetches a model
armlens bench --preset quant-sweep --report
```
