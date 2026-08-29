"""Benchmark engine.

armlens drives the official `llama-bench` tool that ships with llama.cpp. That tool
is the community-standard way to measure LLM CPU inference and already reports:

  * pp (prompt processing)  -> tokens/sec for the prefill  == time-to-first-token proxy
  * tg (text generation)    -> tokens/sec for decode       == steady-state throughput

We run it with JSON output (`-o json`) so parsing is robust, sweep over thread counts
and any number of GGUF model files (e.g. the same model at Q4_0 vs Q8_0 vs F16), and
normalise everything into flat rows the reporter can chart.

Nothing here fabricates numbers: if `llama-bench` is not present or a model is missing,
the run is recorded as an explicit error. All timings come from llama.cpp itself.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class BenchRow:
    model_label: str
    model_path: str
    model_size_mb: float
    quant: str
    n_threads: int
    test: str
    n_tokens: int
    tokens_per_sec: float
    stddev: float = 0.0
    backend: str = "CPU"
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchConfig:
    llama_bench: str
    models: list = field(default_factory=list)
    threads: list = field(default_factory=list)
    n_prompt: int = 128
    n_gen: int = 128
    repetitions: int = 3


def find_llama_bench(hint: Optional[str] = None) -> Optional[str]:
    """Locate the llama-bench binary from a hint, PATH, or common build dirs."""
    candidates = []
    if hint:
        candidates.append(hint)
    candidates += [
        shutil.which("llama-bench") or "",
        "./llama.cpp/build/bin/llama-bench",
        os.path.expanduser("~/llama.cpp/build/bin/llama-bench"),
        "/usr/local/bin/llama-bench",
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _quant_from_name(path: str) -> str:
    name = os.path.basename(path).lower()
    for q in ("q4_0", "q4_k_m", "q4_k_s", "q4_k", "q5_k_m", "q5_k", "q6_k",
              "q8_0", "iq4_xs", "f16", "bf16", "f32"):
        if q in name:
            return q.upper()
    return "unknown"


def _size_mb(path: str) -> float:
    try:
        return round(os.path.getsize(path) / (1024 * 1024), 1)
    except OSError:
        return 0.0


def _run_llama_bench(cfg: BenchConfig, label: str, path: str) -> list:
    """Run llama-bench for one model over the configured thread sweep. Returns rows."""
    rows: list = []
    quant = _quant_from_name(path)
    size = _size_mb(path)

    if not os.path.isfile(path):
        rows.append(BenchRow(label, path, size, quant, 0, "pp", cfg.n_prompt, 0.0,
                             error="model file not found"))
        return rows

    threads_arg = ",".join(str(t) for t in cfg.threads)
    cmd = [
        cfg.llama_bench,
        "-m", path,
        "-t", threads_arg,
        "-p", str(cfg.n_prompt),
        "-n", str(cfg.n_gen),
        "-r", str(cfg.repetitions),
        "-o", "json",
    ]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT,
                                      timeout=60 * 30)
    except subprocess.CalledProcessError as e:
        rows.append(BenchRow(label, path, size, quant, 0, "pp", cfg.n_prompt, 0.0,
                             error=f"llama-bench failed: {e.output[-400:] if e.output else e}"))
        return rows
    except FileNotFoundError:
        rows.append(BenchRow(label, path, size, quant, 0, "pp", cfg.n_prompt, 0.0,
                             error="llama-bench binary not found"))
        return rows
    except subprocess.TimeoutExpired:
        rows.append(BenchRow(label, path, size, quant, 0, "pp", cfg.n_prompt, 0.0,
                             error="llama-bench timed out"))
        return rows


    try:
        data = json.loads(out)
    except json.JSONDecodeError:

        start = out.find("[")
        end = out.rfind("]")
        if start != -1 and end != -1:
            data = json.loads(out[start:end + 1])
        else:
            rows.append(BenchRow(label, path, size, quant, 0, "pp", cfg.n_prompt, 0.0,
                                 error="could not parse llama-bench JSON"))
            return rows

    for entry in data:
        n_threads = int(entry.get("n_threads", 0))
        avg_ts = float(entry.get("avg_ts", 0.0))
        stddev = float(entry.get("stddev_ts", 0.0))
        n_prompt = int(entry.get("n_prompt", 0))
        n_gen = int(entry.get("n_gen", 0))
        backend = entry.get("backend_name") or entry.get("backend") or "CPU"
        if n_prompt and not n_gen:
            test, ntok = "pp", n_prompt
        elif n_gen and not n_prompt:
            test, ntok = "tg", n_gen
        else:
            test, ntok = entry.get("test", "?"), max(n_prompt, n_gen)
        rows.append(BenchRow(
            model_label=label, model_path=path, model_size_mb=size, quant=quant,
            n_threads=n_threads, test=test, n_tokens=ntok,
            tokens_per_sec=round(avg_ts, 2), stddev=round(stddev, 2), backend=backend,
        ))
    return rows


def run(cfg: BenchConfig, progress=None) -> list:
    """Run the full sweep. `progress` is an optional callable(msg)."""
    all_rows: list = []
    for label, path in cfg.models:
        if progress:
            progress(f"Benchmarking {label} ({os.path.basename(path)}) ...")
        t0 = time.time()
        all_rows.extend(_run_llama_bench(cfg, label, path))
        if progress:
            progress(f"  done in {time.time() - t0:.1f}s")
    return all_rows
