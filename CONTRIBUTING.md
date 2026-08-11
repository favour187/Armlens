# Contributing to armlens

Thanks for your interest! armlens aims to stay small, honest, and Arm‑focused.

## Dev setup

```bash
git clone https://github.com/<you>/armlens.git && cd armlens
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[plots]" pytest
python -m pytest tests/ -q
```

Unit tests are architecture‑independent and run on any machine. Benchmark‑path changes should
also be validated on a real Arm64 host (see `docs/PROVISION_ARM.md`).

## Ground rules

1. **Never fabricate benchmark numbers.** All timings must come from the underlying engine.
2. **Keep the core dependency‑light** (`rich` only). Heavy libs go behind optional extras.
3. **Reports must stay self‑contained** (inline SVG/CSS) — the HTML must open offline.
4. Add/keep tests green: `python -m pytest tests/ -q`.

## Ideas we'd love PRs for

- Additional backends (`vLLM`, `ONNX Runtime`) behind a `--backend` flag.
- `armlens compare` to diff two `results.json` files across Arm SKUs.
- Energy/perf‑per‑watt reporting where the platform exposes it.

## License

By contributing you agree your contributions are licensed under the MIT License.
