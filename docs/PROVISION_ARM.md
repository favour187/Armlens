# Getting a free (or cheap) Arm64 machine

`armlens` must run on **Arm64 (aarch64)** to produce meaningful results. You do **not** need
to own Arm hardware — here are three ways to get one, cheapest first.

---

## Option A — Oracle Cloud "Always Free" Ampere A1 (recommended, $0)

Oracle's Always Free tier includes **Ampere Altra Arm cores** — up to **4 vCPU / 24 GB RAM**,
free forever. That's plenty for a 1–3B model quant sweep.

1. Create an account at <https://www.oracle.com/cloud/free/> (needs a card for verification; the
   A1 shape used here is in the Always‑Free allowance).
2. **Create a VM instance:**
   - *Image:* **Ubuntu 22.04 or 24.04 (aarch64)**.
   - *Shape:* **VM.Standard.A1.Flex** → set **4 OCPUs / 24 GB** (or less).
   - Add your SSH public key.
3. **Open the demo port (optional):** in the instance's subnet Security List, add an ingress
   rule for TCP **8080** (only if you want to show the web chat demo remotely).
4. SSH in:
   ```bash
   ssh ubuntu@<public-ip>
   ```
5. Run armlens:
   ```bash
   sudo apt-get update -y && sudo apt-get install -y git
   git clone https://github.com/<you>/armlens.git && cd armlens
   ./scripts/setup_arm.sh
   source .venv/bin/activate
   armlens info                       # should say ✅ Arm64, cloud: Ampere
   ./scripts/make_quant_variants.sh   # optional
   armlens bench --preset quant-sweep --report
   ```
6. Copy the report back to your laptop:
   ```bash
   scp ubuntu@<public-ip>:~/armlens/results/report.html .
   ```

> Tip: If A1 capacity is unavailable in your home region, try creating the instance in a
> different availability domain or region — Always‑Free A1 capacity rotates.

---

## Option B — AWS Graviton (fast, ~$0.15–0.70/hr)

1. Launch an EC2 instance:
   - *AMI:* Ubuntu 24.04 **(64‑bit Arm)**.
   - *Type:* **c7g.xlarge** (Graviton3, 4 vCPU) or **c8g.xlarge** (Graviton4).
   - Security group: allow SSH (22); add 8080 for the demo if desired.
2. SSH in and run the same commands as Option A step 5.
3. **Terminate the instance when done** to stop billing.

Graviton3/4 expose `i8mm`, `bf16`, and SVE — `armlens info` will list them, and KleidiAI Q4_0
kernels will engage.

---

## Option C — GitHub Actions Arm runner (for CI, not for headline numbers)

`.github/workflows/ci.yml` already uses `runs-on: ubuntu-24.04-arm`, a GitHub‑hosted Arm64
runner, to prove the toolkit installs and detects Arm on every push. Shared CI runners aren't
ideal for stable throughput numbers, but they're perfect for validating the code path on Arm.

---

## Sizing guidance

| Instance RAM | Comfortable model size (GGUF) |
|---|---|
| 4–8 GB | 1–3B (TinyLlama 1.1B, Qwen2.5‑1.5B, Phi‑3‑mini Q4) |
| 16–24 GB | up to ~7–8B at Q4_0 (Llama‑3.1‑8B, Mistral‑7B) |
| 32 GB+ | 7–8B at Q8_0, or 13B at Q4 |

The bundled demo uses **TinyLlama‑1.1B‑Chat Q4_0 (~636 MB)** so it runs even on the smallest
free tier. Point `--model` / `models/` at anything larger when you have the RAM.
