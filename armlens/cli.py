"""armlens command line interface.

Commands
--------
  armlens info                      Show the detected Arm64 platform + accel features.
  armlens bench [options]           Run the llama.cpp benchmark sweep and write reports.
  armlens report <results.json>     Re-render reports from an existing results.json.

The `bench` command has presets so judges can reproduce with a single line:

  armlens bench --preset quant-sweep --report
      Benchmarks every *.gguf in ./models across a sensible thread sweep, then writes
      results/report.html + report.md + results.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

from . import __version__
from . import sysinfo as sysinfo_mod
from . import benchmark as bench_mod
from . import report as report_mod

try:
    from rich.console import Console
    from rich.table import Table
    _console = Console()
except Exception:
    _console = None


def _print(msg: str) -> None:
    if _console:
        _console.print(msg)
    else:
        print(msg)


def _default_threads(cores: int) -> list:
    """A sensible thread sweep: 1, half, all physical cores (deduped)."""
    opts = sorted({1, max(1, cores // 2), cores})
    return opts


def cmd_info(args) -> int:
    si = sysinfo_mod.collect()
    if _console:
        t = Table(title="armlens · platform", show_header=False, expand=False)
        t.add_row("CPU model", si.cpu_model)
        t.add_row("Architecture", f"{si.arch}  " + ("[green]Arm64[/]" if si.is_arm64
                                                     else "[red]NOT Arm64[/]"))
        t.add_row("Likely cloud", si.likely_cloud)
        t.add_row("Physical cores", str(si.physical_cores))
        t.add_row("Logical CPUs", str(si.logical_cpus))
        t.add_row("RAM (GB)", str(si.total_ram_gb))
        t.add_row("KleidiAI-relevant", ", ".join(si.kleidi_relevant_features) or "-")
        _console.print(t)
        if not si.is_arm64:
            _console.print("[yellow]⚠ This is not an Arm64 host. Run armlens on an "
                           "Arm server (Oracle Ampere / AWS Graviton) for valid results.[/]")
    else:
        print(json.dumps(si.to_dict(), indent=2))
    return 0


def _collect_models(models_arg, models_dir) -> list:
    """Return list of (label, path). Explicit --model wins; else glob the dir."""
    out = []
    if models_arg:
        for spec in models_arg:
            if "=" in spec:
                label, path = spec.split("=", 1)
            else:
                label, path = os.path.splitext(os.path.basename(spec))[0], spec
            out.append((label, os.path.expanduser(path)))
        return out
    for path in sorted(glob.glob(os.path.join(models_dir, "*.gguf"))):
        label = os.path.splitext(os.path.basename(path))[0]
        out.append((label, path))
    return out


def cmd_bench(args) -> int:
    si = sysinfo_mod.collect()
    if not si.is_arm64 and not args.allow_non_arm:
        _print("[red]Refusing to benchmark on a non-Arm64 host.[/] "
               "armlens measures *Arm* optimization. Run on an Arm server, "
               "or pass --allow-non-arm to override (results won't reflect Arm).")
        return 2

    llama_bench = bench_mod.find_llama_bench(args.llama_bench)
    if not llama_bench:
        _print("[red]Could not find `llama-bench`.[/] Run ./scripts/setup_arm.sh first, "
               "or pass --llama-bench /path/to/llama-bench.")
        return 3

    models = _collect_models(args.model, args.models_dir)
    if not models:
        _print(f"[red]No models found[/] in {args.models_dir}. "
               "Add a .gguf there or pass --model label=path.")
        return 4

    threads = ([int(t) for t in args.threads.split(",")] if args.threads
               else _default_threads(si.physical_cores))


    if args.preset == "quick":
        n_prompt, n_gen, reps = 32, 32, 2
    elif args.preset == "quant-sweep":
        n_prompt, n_gen, reps = 128, 128, 3
    else:
        n_prompt, n_gen, reps = 256, 256, 5
    n_prompt = args.n_prompt or n_prompt
    n_gen = args.n_gen or n_gen
    reps = args.repetitions or reps

    cfg = bench_mod.BenchConfig(
        llama_bench=llama_bench, models=models, threads=threads,
        n_prompt=n_prompt, n_gen=n_gen, repetitions=reps,
    )

    _print(f"[cyan]armlens[/] benchmarking {len(models)} model(s) on "
           f"[bold]{si.cpu_model}[/] · threads={threads} · pp={n_prompt} tg={n_gen} r={reps}")
    rows = bench_mod.run(cfg, progress=_print)
    row_dicts = [r.to_dict() for r in rows]

    meta = {
        "version": __version__,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "llama_bench": llama_bench,
        "preset": args.preset,
    }

    if args.report or args.out:
        results_dir = args.out or "results"
        summary = report_mod.generate(results_dir, si.to_dict(), row_dicts, meta)
        _print(f"[green]✓ Wrote[/] {results_dir}/report.html, report.md, results.json")
        h = summary.get("headline")
        if h:
            _print(f"[bold green]Headline:[/] {h['fastest_model']} is "
                   f"{h['decode_speedup_x']}× faster to decode than {h['slowest_model']}.")
    else:
        print(json.dumps({"sysinfo": si.to_dict(), "rows": row_dicts}, indent=2))
    return 0


def cmd_report(args) -> int:
    with open(args.results, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = args.out or "results"
    report_mod.generate(out, data["sysinfo"], data["rows"], data.get("meta", {}))
    _print(f"[green]✓ Re-rendered[/] reports into {out}/")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="armlens",
                                description="Reproducible LLM inference optimization & "
                                            "benchmarking for Arm64 servers.")
    p.add_argument("--version", action="version", version=f"armlens {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="Show detected Arm64 platform + accel features")\
        .set_defaults(func=cmd_info)

    b = sub.add_parser("bench", help="Run llama.cpp benchmark sweep")
    b.add_argument("--preset", choices=["quick", "quant-sweep", "thorough"],
                   default="quant-sweep", help="benchmark intensity (default: quant-sweep)")
    b.add_argument("--models-dir", default="models", help="dir to scan for *.gguf")
    b.add_argument("--model", action="append",
                   help="explicit model as label=path (repeatable)")
    b.add_argument("--threads", help="comma list, e.g. 1,2,4 (default: 1,half,all cores)")
    b.add_argument("--n-prompt", type=int, help="override prefill tokens")
    b.add_argument("--n-gen", type=int, help="override decode tokens")
    b.add_argument("--repetitions", type=int, help="override repetitions")
    b.add_argument("--llama-bench", help="path to llama-bench binary")
    b.add_argument("--report", action="store_true", help="write report.html/md/json")
    b.add_argument("--out", help="output dir (implies --report)")
    b.add_argument("--allow-non-arm", action="store_true",
                   help="allow running on non-Arm hosts (for CI dry-runs only)")
    b.set_defaults(func=cmd_bench)

    r = sub.add_parser("report", help="Re-render reports from results.json")
    r.add_argument("results", help="path to results.json")
    r.add_argument("--out", help="output dir")
    r.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
