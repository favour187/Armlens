# Architecture

`armlens` is deliberately small and orchestration‑only: it never invents numbers, it drives
the community‑standard `llama.cpp` benchmark tool and turns its output into decision‑ready
artifacts.

```
                 ┌─────────────────────────────────────────────────────────┐
                 │                         armlens CLI                       │
                 │                       (armlens/cli.py)                    │
                 └───────────┬───────────────────┬──────────────────────────┘
                             │                   │
                 ┌───────────▼──────────┐  ┌─────▼───────────────────────────┐
                 │      sysinfo.py       │  │          benchmark.py           │
                 │ detect aarch64 + HWCAP│  │  find + drive `llama-bench`     │
                 │ (i8mm, dotprod, sve,  │  │  -o json → parse pp/tg tok/s    │
                 │  bf16), cores, cloud  │  │  per (model × thread × test)    │
                 └───────────┬───────────┘  └─────┬───────────────────────────┘
                             │                    │  rows: BenchRow[]
                             └────────┬───────────┘
                                      ▼
                            ┌───────────────────────┐
                            │       report.py        │
                            │ summarize + render:    │
                            │  • results.json        │
                            │  • report.md           │
                            │  • report.html (SVG)   │
                            └───────────────────────┘
```

## Modules

### `sysinfo.py`
Reads `/proc/cpuinfo`, `/proc/meminfo`, `lscpu`, and DMI to produce a `SysInfo`:
- `is_arm64` gate for the honesty guardrail.
- `arm_features` from the `Features:` line; `kleidi_relevant_features` filters to the flags
  KleidiAI uses (`asimddp`, `i8mm`, `sve`, `sve2`, `bf16`).
- `cpu_model` maps aarch64 `CPU part` IDs → Neoverse names (N1/V1/N2/V2/N3).
- `likely_cloud` heuristically labels Graviton / Ampere / Cobalt / Axion for nicer reports.

### `benchmark.py`
- `find_llama_bench()` locates the binary (hint → PATH → common build dirs).
- `run()` invokes `llama-bench -m … -t <threads> -p <n_prompt> -n <n_gen> -r <reps> -o json`
  and parses each JSON entry into a `BenchRow` (`pp` = prefill/TTFT proxy, `tg` = decode).
- Errors (missing binary/model, parse failure, timeout) are recorded **as data**, never hidden.

### `report.py`
- `_summarize()` computes best decode/prefill per model and a headline speedup + size ratio
  between the fastest and slowest models (e.g. Q4_0 vs F16).
- Emits `results.json` (full capture), `report.md` (GitHub‑friendly), and a **self‑contained**
  `report.html` with **hand‑rendered inline SVG** bar charts — no external CSS/JS/images, so it
  opens offline and previews in any sandbox.

## Design principles

1. **Honesty over hype.** Non‑Arm hosts are refused by default; all timings are llama.cpp's.
2. **Zero‑friction reproduction.** One script from bare VM to report.
3. **Minimal dependencies.** Core = `rich` only. Charts are SVG, not matplotlib.
4. **Machine‑readable first.** `results.json` enables CI regression gates and SKU comparisons.

## Extending

- **New backend:** add a `run_*` function in `benchmark.py` that returns `BenchRow`s (e.g.
  vLLM, ONNX Runtime) and a `--backend` flag in `cli.py`. The reporter is backend‑agnostic.
- **New chart:** add an `_svg_*` helper in `report.py` and drop it into `write_html`.
