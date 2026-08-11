"""Detect the host CPU / platform and the Arm features that matter for LLM inference.

The whole point of armlens is *Arm-specific* optimization, so we surface the exact
ISA features llama.cpp / KleidiAI use to accelerate quantized matmuls:

  * asimddp  (dotprod)   -> INT8 dot-product, big win for Q4_0/Q8_0
  * i8mm                 -> INT8 matrix multiply, powers KleidiAI Q4_0 repacking
  * sve / sve2           -> scalable vectors (Graviton3+, some Ampere)
  * bf16                 -> bfloat16 matmul

These map directly to the numbers you see in the benchmark report.
"""
from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass, asdict, field
from typing import Optional


# aarch64 HWCAP feature flags we care about, as they appear in /proc/cpuinfo "Features".
ARM_FEATURE_MEANING = {
    "asimd": "Advanced SIMD (NEON)",
    "asimddp": "INT8 dot product (dotprod) - accelerates Q4_0/Q8_0",
    "i8mm": "INT8 matrix multiply - powers KleidiAI Q4_0 kernels",
    "bf16": "bfloat16 matrix multiply",
    "sve": "Scalable Vector Extension",
    "sve2": "Scalable Vector Extension 2",
    "fphp": "half-precision floating point",
}

# Features that, when present, mean KleidiAI's fast INT8 kernels can kick in.
KLEIDI_RELEVANT = ["asimddp", "i8mm", "sve", "sve2", "bf16"]


@dataclass
class SysInfo:
    arch: str
    is_arm64: bool
    cpu_model: str
    physical_cores: int
    logical_cpus: int
    total_ram_gb: float
    os: str
    kernel: str
    arm_features: list = field(default_factory=list)
    kleidi_relevant_features: list = field(default_factory=list)
    likely_cloud: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _detect_cloud(cpu_model: str) -> str:
    """Best-effort guess of the Arm cloud platform for nicer reports."""
    text = cpu_model.lower()
    dmi = (_read("/sys/class/dmi/id/sys_vendor") + _read("/sys/class/dmi/id/product_name")).lower()
    if "graviton" in text or "amazon" in dmi or "aws" in dmi:
        return "AWS Graviton"
    if "ampere" in text or "ampere" in dmi:
        return "Ampere (Oracle/GCP/Azure)"
    if "cobalt" in text or "microsoft" in dmi:
        return "Azure Cobalt"
    if "axion" in text or "google" in dmi:
        return "Google Axion"
    if "neoverse" in text:
        return "Arm Neoverse"
    return "unknown"


def _cpu_model() -> str:
    cpuinfo = _read("/proc/cpuinfo")
    # x86 exposes "model name"; aarch64 usually exposes "CPU part" codes only.
    m = re.search(r"model name\s*:\s*(.+)", cpuinfo)
    if m:
        return m.group(1).strip()
    # Map common aarch64 CPU part IDs to Neoverse names.
    part = re.search(r"CPU part\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    part_map = {
        "0xd0c": "Arm Neoverse-N1",
        "0xd40": "Arm Neoverse-V1",
        "0xd49": "Arm Neoverse-N2",
        "0xd4f": "Arm Neoverse-V2",
        "0xd8e": "Arm Neoverse-N3",
    }
    if part and part.group(1).lower() in part_map:
        return part_map[part.group(1).lower()]
    impl = re.search(r"CPU implementer\s*:\s*(0x[0-9a-fA-F]+)", cpuinfo)
    if impl:
        return f"aarch64 (implementer {impl.group(1)})"
    return platform.processor() or "unknown"


def _arm_features() -> list:
    cpuinfo = _read("/proc/cpuinfo")
    m = re.search(r"Features\s*:\s*(.+)", cpuinfo)
    if not m:
        return []
    return m.group(1).split()


def _physical_cores() -> int:
    # Prefer lscpu; fall back to os.cpu_count.
    try:
        out = subprocess.check_output(["lscpu"], text=True, stderr=subprocess.DEVNULL)
        sockets = cores = None
        for line in out.splitlines():
            if line.startswith("Socket(s):"):
                sockets = int(line.split(":")[1])
            elif line.startswith("Core(s) per socket:"):
                cores = int(line.split(":")[1])
        if sockets and cores:
            return sockets * cores
    except Exception:
        pass
    return os.cpu_count() or 1


def _total_ram_gb() -> float:
    meminfo = _read("/proc/meminfo")
    m = re.search(r"MemTotal:\s*(\d+)\s*kB", meminfo)
    if m:
        return round(int(m.group(1)) / (1024 * 1024), 1)
    return 0.0


def collect() -> SysInfo:
    arch = platform.machine()
    is_arm64 = arch in ("aarch64", "arm64")
    features = _arm_features() if is_arm64 else []
    model = _cpu_model()
    return SysInfo(
        arch=arch,
        is_arm64=is_arm64,
        cpu_model=model,
        physical_cores=_physical_cores(),
        logical_cpus=os.cpu_count() or 1,
        total_ram_gb=_total_ram_gb(),
        os=f"{platform.system()} {platform.release()}",
        kernel=platform.release(),
        arm_features=features,
        kleidi_relevant_features=[f for f in KLEIDI_RELEVANT if f in features],
        likely_cloud=_detect_cloud(model),
    )


if __name__ == "__main__":
    print(json.dumps(collect().to_dict(), indent=2))
