"""Turn benchmark rows + system info into a shareable report.

Outputs three artifacts into the results directory:
  * results.json  -- raw rows + sysinfo (machine readable, for CI / regression)
  * report.md     -- Markdown summary (renders on GitHub)
  * report.html   -- self-contained HTML with inline SVG charts (no external assets,
                     so it previews in any sandbox / offline)

Charts are hand-rendered SVG bar charts -> zero heavy dependencies required on the
Arm VM. (matplotlib is an optional extra for PNGs if you want them.)
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone


def _summarize(rows: list) -> dict:
    """Compute best decode/prefill per model and the Arm speedup vs a baseline quant."""
    ok = [r for r in rows if not r.get("error")]
    by_model = {}
    for r in ok:
        by_model.setdefault(r["model_label"], []).append(r)

    summary = {"models": {}, "headline": {}}
    for label, rs in by_model.items():
        tg = [r for r in rs if r["test"] == "tg"]
        pp = [r for r in rs if r["test"] == "pp"]
        best_tg = max(tg, key=lambda r: r["tokens_per_sec"], default=None)
        best_pp = max(pp, key=lambda r: r["tokens_per_sec"], default=None)
        summary["models"][label] = {
            "quant": rs[0]["quant"],
            "size_mb": rs[0]["model_size_mb"],
            "best_decode_tps": best_tg["tokens_per_sec"] if best_tg else 0.0,
            "best_decode_threads": best_tg["n_threads"] if best_tg else 0,
            "best_prefill_tps": best_pp["tokens_per_sec"] if best_pp else 0.0,
            "best_prefill_threads": best_pp["n_threads"] if best_pp else 0,
        }


    m = summary["models"]
    if len(m) >= 2:
        fastest = max(m.items(), key=lambda kv: kv[1]["best_decode_tps"])
        slowest = min(m.items(), key=lambda kv: kv[1]["best_decode_tps"])
        if slowest[1]["best_decode_tps"] > 0:
            speedup = fastest[1]["best_decode_tps"] / slowest[1]["best_decode_tps"]
            size_ratio = (slowest[1]["size_mb"] / fastest[1]["size_mb"]
                          if fastest[1]["size_mb"] else 0)
            summary["headline"] = {
                "fastest_model": fastest[0],
                "slowest_model": slowest[0],
                "decode_speedup_x": round(speedup, 2),
                "size_reduction_x": round(size_ratio, 2),
                "fastest_tps": fastest[1]["best_decode_tps"],
                "slowest_tps": slowest[1]["best_decode_tps"],
            }
    return summary




def _svg_bar_chart(title: str, labels: list, values: list, unit: str,
                   width: int = 640, bar_h: int = 34, color: str = "#00A3E0") -> str:
    if not values:
        return ""
    pad_left, pad_top, pad_right = 180, 46, 90
    vmax = max(values) or 1.0
    plot_w = width - pad_left - pad_right
    height = pad_top + len(values) * (bar_h + 12) + 20
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="system-ui,Segoe UI,Roboto,sans-serif" width="100%">',
        f'<text x="16" y="26" font-size="17" font-weight="700" fill="#0b2233">{html.escape(title)}</text>',
    ]
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = pad_top + i * (bar_h + 12)
        w = max(2, int(plot_w * (val / vmax)))
        parts.append(
            f'<text x="{pad_left - 12}" y="{y + bar_h*0.66:.0f}" font-size="13" '
            f'text-anchor="end" fill="#33475b">{html.escape(str(lab))}</text>'
        )
        parts.append(
            f'<rect x="{pad_left}" y="{y}" width="{w}" height="{bar_h}" rx="5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{pad_left + w + 8}" y="{y + bar_h*0.66:.0f}" font-size="13" '
            f'fill="#0b2233" font-weight="600">{val:g} {html.escape(unit)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)




def write_json(path: str, sysinfo: dict, rows: list, summary: dict, meta: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "sysinfo": sysinfo, "summary": summary, "rows": rows},
                  f, indent=2)


def _md_table(rows: list) -> str:
    header = "| Model | Quant | Size (MB) | Threads | Test | Tokens/s | ±stddev |\n"
    header += "|---|---|---|---|---|---|---|\n"
    lines = []
    for r in sorted(rows, key=lambda r: (r["model_label"], r["test"], r["n_threads"])):
        if r.get("error"):
            lines.append(f"| {r['model_label']} | {r['quant']} | {r['model_size_mb']} | "
                         f"- | - | ERROR | {r['error']} |")
        else:
            test = "prefill (TTFT)" if r["test"] == "pp" else "decode"
            lines.append(f"| {r['model_label']} | {r['quant']} | {r['model_size_mb']} | "
                         f"{r['n_threads']} | {test} | **{r['tokens_per_sec']:g}** | "
                         f"{r['stddev']:g} |")
    return header + "\n".join(lines) + "\n"


def write_markdown(path: str, sysinfo: dict, rows: list, summary: dict, meta: dict) -> None:
    h = summary.get("headline", {})
    s = sysinfo
    feats = ", ".join(s.get("kleidi_relevant_features", [])) or "none detected"
    lines = [
        "# armlens benchmark report",
        "",
        f"_Generated {meta.get('timestamp','')} by armlens v{meta.get('version','')}._",
        "",
        "## Platform",
        "",
        f"- **CPU:** {s.get('cpu_model','?')}  ({s.get('likely_cloud','unknown')})",
        f"- **Architecture:** `{s.get('arch','?')}`  "
        f"{'✅ Arm64' if s.get('is_arm64') else '⚠️ not Arm64 — run this on an Arm server'}",
        f"- **Cores:** {s.get('physical_cores','?')} physical / {s.get('logical_cpus','?')} logical",
        f"- **RAM:** {s.get('total_ram_gb','?')} GB",
        f"- **Arm accel features (KleidiAI-relevant):** {feats}",
        "",
    ]
    if h:
        lines += [
            "## Headline result",
            "",
            f"> **{h['fastest_model']}** decodes at **{h['fastest_tps']:g} tok/s** vs "
            f"**{h['slowest_model']}** at **{h['slowest_tps']:g} tok/s** — "
            f"a **{h['decode_speedup_x']}× speedup**"
            + (f" with a **{h['size_reduction_x']}× smaller** model on disk."
               if h.get('size_reduction_x') else "."),
            "",
        ]
    lines += ["## Full results", "", _md_table(rows), "",
              "## Reproduce", "",
              "```bash",
              "git clone <this-repo> && cd armlens",
              "./scripts/setup_arm.sh          # builds llama.cpp w/ KleidiAI + fetches a model",
              "armlens bench --preset quant-sweep --report",
              "```", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_html(path: str, sysinfo: dict, rows: list, summary: dict, meta: dict) -> None:
    ok = [r for r in rows if not r.get("error")]

    m = summary.get("models", {})
    dec_labels = list(m.keys())
    dec_vals = [round(m[k]["best_decode_tps"], 1) for k in dec_labels]

    size_labels = dec_labels
    size_vals = [m[k]["size_mb"] for k in dec_labels]

    h = summary.get("headline", {})
    scale_model = h.get("fastest_model") or (dec_labels[0] if dec_labels else None)
    scale_rows = sorted([r for r in ok if r["model_label"] == scale_model and r["test"] == "tg"],
                        key=lambda r: r["n_threads"])
    scale_labels = [f"{r['n_threads']} thr" for r in scale_rows]
    scale_vals = [r["tokens_per_sec"] for r in scale_rows]

    chart1 = _svg_bar_chart("Decode throughput (higher = better)", dec_labels, dec_vals, "tok/s")
    chart2 = _svg_bar_chart("Model size on disk (lower = better)", size_labels, size_vals, "MB",
                            color="#7b61ff")
    chart3 = _svg_bar_chart(f"Thread scaling — {scale_model or ''} (decode)",
                            scale_labels, scale_vals, "tok/s", color="#16b981")

    s = sysinfo
    feats = ", ".join(s.get("kleidi_relevant_features", [])) or "none detected"
    arch_badge = ("Arm64 ✅" if s.get("is_arm64")
                  else "NOT Arm64 ⚠️ run on an Arm server")
    headline_html = ""
    if h:
        headline_html = f"""
        <div class="headline">
          <div class="big">{h['decode_speedup_x']}×</div>
          <div>faster decode: <b>{html.escape(h['fastest_model'])}</b>
          ({h['fastest_tps']:g} tok/s) vs <b>{html.escape(h['slowest_model'])}</b>
          ({h['slowest_tps']:g} tok/s)
          {f"&nbsp;·&nbsp; <b>{h['size_reduction_x']}×</b> smaller on disk" if h.get('size_reduction_x') else ''}
          </div>
        </div>"""

    rows_html = ""
    for r in sorted(ok, key=lambda r: (r["model_label"], r["test"], r["n_threads"])):
        test = "prefill (TTFT)" if r["test"] == "pp" else "decode"
        rows_html += (f"<tr><td>{html.escape(r['model_label'])}</td><td>{r['quant']}</td>"
                      f"<td>{r['model_size_mb']:g}</td><td>{r['n_threads']}</td>"
                      f"<td>{test}</td><td><b>{r['tokens_per_sec']:g}</b></td>"
                      f"<td>{r['stddev']:g}</td></tr>")

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>armlens report</title>
<style>
  :root {{ --arm:#00A3E0; --ink:#0b2233; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:system-ui,Segoe UI,Roboto,sans-serif; color:var(--ink);
         background:#f3f6f9; }}
  .wrap {{ max-width:900px; margin:0 auto; padding:28px 20px 60px; }}
  h1 {{ font-size:28px; margin:0 0 4px; }}
  .sub {{ color:#5b7083; margin-bottom:22px; font-size:14px; }}
  .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:20px 22px;
          margin:16px 0; box-shadow:0 1px 3px rgba(16,42,67,.06); }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px 24px; font-size:14px; }}
  .grid div b {{ color:#33475b; }}
  .badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px;
           font-weight:700; background:#e6f7ff; color:#0077aa; }}
  .headline {{ display:flex; align-items:center; gap:18px; background:linear-gradient(90deg,#e6f7ff,#f5f0ff);
              border:1px solid #cfe9f7; border-radius:14px; padding:18px 22px; margin:16px 0; }}
  .headline .big {{ font-size:46px; font-weight:800; color:var(--arm); line-height:1; }}
  table {{ width:100%; border-collapse:collapse; font-size:13.5px; }}
  th,td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #eef2f6; }}
  th {{ color:#5b7083; font-weight:600; }}
  .foot {{ color:#8aa0b2; font-size:12px; margin-top:24px; text-align:center; }}
</style></head><body><div class="wrap">
  <h1>armlens benchmark report</h1>
  <div class="sub">Generated {html.escape(meta.get('timestamp',''))} · armlens v{html.escape(meta.get('version',''))}</div>
  {headline_html}
  <div class="card">
    <h3 style="margin-top:0">Platform &nbsp;<span class="badge">{html.escape(arch_badge)}</span></h3>
    <div class="grid">
      <div><b>CPU:</b> {html.escape(s.get('cpu_model','?'))}</div>
      <div><b>Cloud:</b> {html.escape(s.get('likely_cloud','unknown'))}</div>
      <div><b>Cores:</b> {s.get('physical_cores','?')} physical / {s.get('logical_cpus','?')} logical</div>
      <div><b>RAM:</b> {s.get('total_ram_gb','?')} GB</div>
      <div style="grid-column:1/3"><b>Arm accel features:</b> {html.escape(feats)}</div>
    </div>
  </div>
  <div class="card">{chart1}</div>
  <div class="card">{chart2}</div>
  <div class="card">{chart3}</div>
  <div class="card">
    <h3 style="margin-top:0">Full results</h3>
    <table><thead><tr><th>Model</th><th>Quant</th><th>Size (MB)</th><th>Threads</th>
    <th>Test</th><th>Tokens/s</th><th>±stddev</th></tr></thead>
    <tbody>{rows_html}</tbody></table>
  </div>
  <div class="foot">Built with armlens · llama.cpp + Arm KleidiAI · MIT licensed</div>
</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def generate(results_dir: str, sysinfo: dict, rows: list, meta: dict) -> dict:
    os.makedirs(results_dir, exist_ok=True)
    summary = _summarize(rows)
    write_json(os.path.join(results_dir, "results.json"), sysinfo, rows, summary, meta)
    write_markdown(os.path.join(results_dir, "report.md"), sysinfo, rows, summary, meta)
    write_html(os.path.join(results_dir, "report.html"), sysinfo, rows, summary, meta)
    return summary
