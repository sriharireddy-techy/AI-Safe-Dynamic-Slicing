"""
Dashboard Data Loader and Telemetry Sanitization Module
=======================================================
Phase 11: Web Dashboard for AI-Safe Dynamic Network Slicing

Responsibilities:
1. Safely load and validate telemetry logs from data/telemetry.csv.
2. Defensively separate genuine network measurements from sentinel/unavailable
   measurements (e.g., latency == -1.0 or NaN).
3. Ingest Module 9 benchmark results (static, dynamic, proposed CSVs and summary table).
4. Detect live vs. simulated environment status non-intrusively without executing
   unauthorized privileged network modifications.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import pandas as pd


# Default workspace paths
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TELEMETRY_PATH = WORKSPACE_ROOT / "data" / "telemetry.csv"
DEFAULT_RESULTS_DIR = WORKSPACE_ROOT / "results"


def load_telemetry(
    file_path: Optional[str] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Loads and sanitizes telemetry records from CSV.

    Args:
        file_path: Optional custom path to telemetry CSV.

    Returns:
        Tuple of:
            - valid_df: DataFrame containing only genuine, reachable measurements (latency > 0).
            - invalid_df: DataFrame containing unreachable/sentinel records (latency <= 0 or NaN).
            - summary: Dictionary of telemetry metrics and health statistics.
    """
    path = Path(file_path) if file_path else DEFAULT_TELEMETRY_PATH

    empty_summary = {
        "exists": False,
        "total_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "mean_latency_ms": None,
        "p99_latency_ms": None,
        "min_latency_ms": None,
        "max_latency_ms": None,
        "mean_throughput_mbps": None,
        "mean_loss_pct": None,
        "max_queue_pkts": None,
        "file_path": str(path),
    }

    if not path.is_file():
        return pd.DataFrame(), pd.DataFrame(), empty_summary

    try:
        df = pd.read_csv(path)
    except Exception as e:
        empty_summary["error"] = str(e)
        return pd.DataFrame(), pd.DataFrame(), empty_summary

    if df.empty or "urllc_latency_ms" not in df.columns:
        empty_summary["exists"] = True
        return pd.DataFrame(), pd.DataFrame(), empty_summary

    # Ensure numeric conversion
    for col in ["urllc_latency_ms", "urllc_packet_loss", "throughput_mbps", "queue_occupancy"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Partition into genuine measurements vs unreachable / sentinel records
    # Ping unreachability is logged as -1.0 in Module 2 monitor
    is_valid_latency = (df["urllc_latency_ms"].notna()) & (df["urllc_latency_ms"] > 0.0)
    valid_df = df[is_valid_latency].copy()
    invalid_df = df[~is_valid_latency].copy()

    total_records = len(df)
    valid_count = len(valid_df)
    invalid_count = len(invalid_df)

    summary = {
        "exists": True,
        "total_records": total_records,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "mean_latency_ms": float(valid_df["urllc_latency_ms"].mean()) if valid_count > 0 else None,
        "p99_latency_ms": float(valid_df["urllc_latency_ms"].quantile(0.99)) if valid_count > 0 else None,
        "min_latency_ms": float(valid_df["urllc_latency_ms"].min()) if valid_count > 0 else None,
        "max_latency_ms": float(valid_df["urllc_latency_ms"].max()) if valid_count > 0 else None,
        "mean_throughput_mbps": float(valid_df["throughput_mbps"].mean()) if (valid_count > 0 and "throughput_mbps" in valid_df.columns) else None,
        "mean_loss_pct": float(valid_df["urllc_packet_loss"].mean()) if (valid_count > 0 and "urllc_packet_loss" in valid_df.columns) else None,
        "max_queue_pkts": float(valid_df["queue_occupancy"].max()) if (valid_count > 0 and "queue_occupancy" in valid_df.columns) else None,
        "file_path": str(path),
    }

    return valid_df, invalid_df, summary


def load_benchmark_csvs(
    results_dir: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """Loads Module 9 simulation benchmark CSVs (Static, Dynamic Unsafe, Proposed AI-Safe).

    Returns:
        Dictionary mapping system name to DataFrame.
    """
    res_dir = Path(results_dir) if results_dir else DEFAULT_RESULTS_DIR
    datasets = {}

    csv_mapping = {
        "static": res_dir / "static_results.csv",
        "dynamic": res_dir / "dynamic_results.csv",
        "proposed": res_dir / "proposed_results.csv",
    }

    for key, path in csv_mapping.items():
        if path.is_file():
            try:
                datasets[key] = pd.read_csv(path)
            except Exception:
                datasets[key] = pd.DataFrame()
        else:
            datasets[key] = pd.DataFrame()

    return datasets


def load_summary_table_markdown(
    results_dir: Optional[str] = None
) -> Optional[str]:
    """Loads existing summary table markdown generated from Module 9 benchmarks."""
    res_dir = Path(results_dir) if results_dir else DEFAULT_RESULTS_DIR
    summary_path = res_dir / "summary_table.md"
    if summary_path.is_file():
        try:
            return summary_path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None


def get_available_plots(
    results_dir: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """Checks and returns absolute paths to existing evaluation plot PNGs."""
    res_dir = Path(results_dir) if results_dir else DEFAULT_RESULTS_DIR
    plots = {
        "comparison": res_dir / "comparison.png",
        "latency": res_dir / "latency.png",
        "throughput": res_dir / "throughput.png",
    }
    return {
        key: str(p) if p.is_file() else None
        for key, p in plots.items()
    }


def _default_command_runner(cmd: list) -> tuple:
    """Default non-privileged command runner using subprocess."""
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1.5,
            check=False,
        )
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)


REQUIRED_SLICE_CLASSES = {
    "URLLC": "1:10",
    "eMBB": "1:20",
    "BE": "1:30",
}


def check_live_data_plane_status(
    interface: str = "s1-eth4",
    command_runner: Optional[Any] = None,
    verified_applied_allocation: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Non-intrusively inspects the data plane environment status.

    Distinguishes three distinct verification stages:
    1. Interface exists (e.g. s1-eth4 detected by tc/ip).
    2. Expected per-slice HTB classes are present (1:10 URLLC, 1:20 eMBB, 1:30 BE).
    3. Requested dynamic rates have been applied and confirmed via read-back.

    Never equates simple interface existence with verified dynamic bandwidth enforcement.
    """
    runner = command_runner or _default_command_runner

    # Stage 1: Check interface existence
    rc_qdisc, out_qdisc, err_qdisc = runner(["tc", "qdisc", "show", "dev", interface])
    interface_exists = (rc_qdisc == 0 and bool(out_qdisc.strip()))

    if not interface_exists:
        return {
            "status": "OFFLINE_SIMULATION",
            "is_live": False,
            "is_verified_live": False,
            "interface_exists": False,
            "classes_present": False,
            "enforcement_verified": False,
            "mode": "Simulation / Benchmark Mode (Mininet Offline)",
            "interface": interface,
            "classes_found": {},
            "details": f"Interface '{interface}' was not detected. Operating safely in offline simulation/benchmark mode.",
            "raw_output": "",
        }

    # Stage 2: Check for per-slice HTB classes
    rc_class, out_class, err_class = runner(["tc", "-s", "class", "show", "dev", interface])
    classes_found = {}
    if rc_class == 0 and out_class.strip():
        for s_name, cid in REQUIRED_SLICE_CLASSES.items():
            if re.search(rf'class\s+htb\s+{re.escape(cid)}', out_class):
                classes_found[s_name] = cid

    classes_present = len(classes_found) == len(REQUIRED_SLICE_CLASSES)

    if not classes_present:
        missing = [f"{s} ({c})" for s, c in REQUIRED_SLICE_CLASSES.items() if s not in classes_found]
        return {
            "status": "INTERFACE_ONLY_UNCONFIGURED",
            "is_live": False,
            "is_verified_live": False,
            "interface_exists": True,
            "classes_present": False,
            "enforcement_verified": False,
            "mode": "Unverified (Interface Detected, HTB Slices Missing)",
            "interface": interface,
            "classes_found": classes_found,
            "details": f"Interface '{interface}' detected, but required per-slice HTB classes are missing: {', '.join(missing)}. Dynamic slicing is unverified.",
            "raw_output": out_class,
        }

    # Stage 3: Check verified rate enforcement
    enforcement_verified = False
    if verified_applied_allocation and isinstance(verified_applied_allocation, dict):
        enforcement_verified = True

    if not enforcement_verified:
        return {
            "status": "CLASSES_PRESENT_UNVERIFIED_RATES",
            "is_live": False,
            "is_verified_live": False,
            "interface_exists": True,
            "classes_present": True,
            "enforcement_verified": False,
            "mode": "Unverified (HTB Classes Present, Rates Not Actuated)",
            "interface": interface,
            "classes_found": classes_found,
            "details": f"Per-slice HTB classes {classes_found} are present on '{interface}', but dynamic rate enforcement has not been applied and read-back verified in this session.",
            "raw_output": out_class,
        }

    return {
        "status": "LIVE_VERIFIED",
        "is_live": True,
        "is_verified_live": True,
        "interface_exists": True,
        "classes_present": True,
        "enforcement_verified": True,
        "mode": "Live Mininet Data-Plane Active & Verified",
        "interface": interface,
        "classes_found": classes_found,
        "details": f"Interface '{interface}', HTB classes {classes_found}, and dynamic rate enforcement verified on active data plane.",
        "raw_output": out_class,
    }
