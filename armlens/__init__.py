"""armlens - reproducible LLM inference optimization & benchmarking for Arm64.

A small, dependency-light toolkit that:
  * detects Arm64 CPU capabilities relevant to LLM inference (dotprod, i8mm, SVE, bf16),
  * benchmarks llama.cpp across quantization levels and thread counts,
  * quantifies the Arm-specific (KleidiAI) speedup, and
  * emits a shareable Markdown + HTML report with charts.
"""

__version__ = "0.1.0"
