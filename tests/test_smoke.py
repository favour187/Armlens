"""Architecture-independent smoke tests.

These verify parsing/reporting logic without needing an Arm host or llama.cpp,
so they run in CI on any runner. Real Arm numbers come from `armlens bench`.
"""
import json
import os
import tempfile

from armlens import sysinfo, report, benchmark


def test_sysinfo_collects():
    si = sysinfo.collect()
    d = si.to_dict()
    assert "arch" in d and "is_arm64" in d
    assert isinstance(d["physical_cores"], int) and d["physical_cores"] >= 1


def test_quant_detection():
    assert benchmark._quant_from_name("foo.Q4_0.gguf") == "Q4_0"
    assert benchmark._quant_from_name("bar-q8_0.gguf") == "Q8_0"
    assert benchmark._quant_from_name("baz.f16.gguf") == "F16"


def test_report_generation_and_headline():
    sysinfo_d = {
        "arch": "aarch64", "is_arm64": True, "cpu_model": "Arm Neoverse-V1",
        "physical_cores": 4, "logical_cpus": 4, "total_ram_gb": 8.0,
        "os": "Linux", "kernel": "6", "arm_features": ["i8mm", "asimddp"],
        "kleidi_relevant_features": ["i8mm", "asimddp"], "likely_cloud": "AWS Graviton",
    }
    rows = [
        {"model_label": "M Q4_0", "model_path": "a", "model_size_mb": 600.0, "quant": "Q4_0",
         "n_threads": 4, "test": "tg", "n_tokens": 128, "tokens_per_sec": 60.0,
         "stddev": 0.5, "backend": "CPU", "error": ""},
        {"model_label": "M F16", "model_path": "b", "model_size_mb": 2200.0, "quant": "F16",
         "n_threads": 4, "test": "tg", "n_tokens": 128, "tokens_per_sec": 20.0,
         "stddev": 0.5, "backend": "CPU", "error": ""},
    ]
    meta = {"version": "0.1.0", "timestamp": "now", "preset": "test"}
    with tempfile.TemporaryDirectory() as d:
        summary = report.generate(d, sysinfo_d, rows, meta)
        assert os.path.exists(os.path.join(d, "report.html"))
        assert os.path.exists(os.path.join(d, "report.md"))
        assert os.path.exists(os.path.join(d, "results.json"))
        h = summary["headline"]
        assert h["fastest_model"] == "M Q4_0"
        assert h["decode_speedup_x"] == 3.0
        assert h["size_reduction_x"] > 3.0


        with open(os.path.join(d, "report.html")) as f:
            doc = f.read()
        assert 'src="http' not in doc
        assert 'href="http' not in doc
        assert "<link" not in doc


def test_find_llama_bench_missing_is_none(monkeypatch):
    monkeypatch.setattr(benchmark.shutil, "which", lambda *_: None)

    assert benchmark.find_llama_bench("/nonexistent/llama-bench") is None
