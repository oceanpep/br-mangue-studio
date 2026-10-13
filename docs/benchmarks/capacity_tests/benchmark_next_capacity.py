#!/usr/bin/env python3
"""Run one large continuous-engine capacity test with RAM and swap guards."""
from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
from benchmark import generate_inputs, sha256

ROOT = Path(__file__).resolve().parent
OUT_ROOT = ROOT / "execucoes_limite_salto" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MIN_AVAILABLE_BYTES = int(1.5 * 1024**3)
MIN_SWAP_FREE_BYTES = int(1.0 * 1024**3)
SAMPLE_SECONDS = 1.0


def run(height: int, width: int, engine: str = "continuous") -> dict:
    cells = height * width
    OUT_ROOT.mkdir(parents=True, exist_ok=False)
    block_size = 100_000 if engine == "blocks" else 0
    engine_dir = f"blocks_{block_size}" if block_size else "continuous"
    out = OUT_ROOT / f"{cells}_cells" / engine_dir
    out.mkdir(parents=True)

    report_path = OUT_ROOT / "capacity_test.json"
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "os": "Ubuntu 26.04.1 LTS",
            "kernel": platform.release(),
            "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.lower().startswith("model name")), platform.processor()),
            "logical_cpus": os.cpu_count(),
            "ram_total_bytes": psutil.virtual_memory().total,
            "ram_available_at_start_bytes": psutil.virtual_memory().available,
            "swap_total_bytes": psutil.swap_memory().total,
            "swap_free_at_start_bytes": psutil.swap_memory().free,
        },
        "method": {
            "source_tag": "v1.1.0",
            "source_commit": "61630971869a5b9747d1b0dcf638e464446bc1b3",
            "grid_shape": [height, width],
            "cells": cells,
            "years": 5,
            "annual_state_exports": False,
            "engine": engine,
            "block_size_cells": block_size or None,
            "safety_stop_if_ram_available_below_bytes": MIN_AVAILABLE_BYTES,
            "safety_stop_if_swap_free_below_bytes": MIN_SWAP_FREE_BYTES,
            "sampling_interval_seconds": SAMPLE_SECONDS,
            "inputs": "fully valid synthetic land-cover and DEM rasters; arbitrary EPSG:3857 grid; classes 5,11,33,15; no ecological interpretation",
        },
        "status": "generating_inputs",
        "result": None,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lc, dem = generate_inputs(height, width)
    report["inputs"] = {"land_cover_sha256": sha256(lc), "dem_sha256": sha256(dem)}
    report["status"] = "running"
    report["started_available_after_input_generation_bytes"] = psutil.virtual_memory().available
    report["started_swap_free_after_input_generation_bytes"] = psutil.swap_memory().free

    cmd = [sys.executable, str(ROOT / "run_one.py"), str(lc), str(dem), str(out), str(cells), engine, str(block_size)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    monitored = psutil.Process(proc.pid)
    peak_rss = peak_process_swap = 0
    min_ram_available = psutil.virtual_memory().available
    min_swap_free = psutil.swap_memory().free
    samples = []
    stop_reason = None
    started = time.perf_counter()

    while proc.poll() is None:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        try:
            info = monitored.memory_info()
            peak_rss = max(peak_rss, info.rss)
            status_lines = Path(f"/proc/{proc.pid}/status").read_text().splitlines()
            process_swap = int(next((line.split()[1] for line in status_lines if line.startswith("VmSwap:")), "0")) * 1024
            peak_process_swap = max(peak_process_swap, process_swap)
        except (psutil.Error, OSError, StopIteration):
            process_swap = 0
        min_ram_available = min(min_ram_available, memory.available)
        min_swap_free = min(min_swap_free, swap.free)
        samples.append({
            "elapsed_seconds": round(time.perf_counter() - started, 2),
            "rss_bytes": info.rss if "info" in locals() else None,
            "process_swap_bytes": process_swap,
            "ram_available_bytes": memory.available,
            "swap_free_bytes": swap.free,
        })
        if memory.available < MIN_AVAILABLE_BYTES:
            stop_reason = "stopped_low_available_ram"
        elif swap.free < MIN_SWAP_FREE_BYTES:
            stop_reason = "stopped_low_free_swap"
        if stop_reason:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            break
        time.sleep(SAMPLE_SECONDS)

    stdout, stderr = proc.communicate()
    (out / "guard_stdout.json").write_text(stdout, encoding="utf-8")
    (out / "guard_stderr.log").write_text(stderr, encoding="utf-8")
    with (out / "resource_guard_samples.csv").open("w", encoding="utf-8") as f:
        f.write("elapsed_seconds,rss_bytes,process_swap_bytes,ram_available_bytes,swap_free_bytes\n")
        for sample in samples:
            f.write(",".join(str(sample[k] if sample[k] is not None else "") for k in (
                "elapsed_seconds", "rss_bytes", "process_swap_bytes", "ram_available_bytes", "swap_free_bytes")) + "\n")

    report.update({
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "status": stop_reason or ("completed" if proc.returncode == 0 else "failed"),
        "return_code": proc.returncode,
        "stop_reason": stop_reason,
        "wall_seconds_until_exit": round(time.perf_counter() - started, 3),
        "externally_sampled_peak_rss_bytes_including_load": peak_rss,
        "externally_sampled_peak_process_swap_bytes": peak_process_swap,
        "minimum_system_ram_available_bytes": min_ram_available,
        "minimum_system_swap_free_bytes": min_swap_free,
        "samples": len(samples),
        "stdout_tail": stdout[-5000:],
        "stderr_tail": stderr[-5000:],
    })
    if not stop_reason and proc.returncode == 0:
        parsed = json.loads(stdout)
        report["result"] = {
            "performance": parsed["performance"],
            "final_state_pixel_sha256": parsed["final_state_pixel_sha256"],
            "trajectory_final_row": parsed["trajectory_final_row"],
        }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Capacity result: {report_path}", flush=True)
    return report


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: benchmark_next_capacity.py HEIGHT WIDTH [continuous|blocks]")
    run(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3] if len(sys.argv) == 4 else "continuous")
