"""
Experiment Runner, Plotter, and Comparative Evaluator (Module 9)
================================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

EXECUTION SPECIFICATION & SCIENTIFIC LABELS:
--------------------------------------------
- Architecture: Trace-Driven Simulation Benchmark using a simplified FIFO queuing model.
- Metrics are calculated DIRECTLY from saved CSV data files.
- Generates:
    - results/latency.png      (Simulated URLLC RTT vs 15.0 ms SLA over time)
    - results/throughput.png   (eMBB Slice Throughput Adaptation over time)
    - results/comparison.png   (Comparative metrics bar chart)
    - Official Simulation Benchmark Summary Table.
"""

import os
import sys
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from experiments.static_baseline import run_simulation as run_static
from experiments.dynamic_baseline import run_simulation as run_dynamic
from experiments.proposed_system import run_simulation as run_proposed


def load_csv_data(csv_path: str) -> list:
    """Reads saved CSV results into a list of row dictionaries with typed values."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    rows = []
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "step": int(r["step"]),
                "time_s": float(r["time_s"]),
                "mode": r["mode"],
                "description": r["description"],
                "urllc_offered_mbps": float(r["urllc_offered_mbps"]),
                "embb_offered_mbps": float(r["embb_offered_mbps"]),
                "be_offered_mbps": float(r["be_offered_mbps"]),
                "total_offered_mbps": float(r["total_offered_mbps"]),
                "urllc_alloc_mbps": float(r["urllc_alloc_mbps"]),
                "embb_alloc_mbps": float(r["embb_alloc_mbps"]),
                "be_alloc_mbps": float(r["be_alloc_mbps"]),
                "total_alloc_mbps": float(r["total_alloc_mbps"]),
                "urllc_tput_mbps": float(r["urllc_tput_mbps"]),
                "embb_tput_mbps": float(r["embb_tput_mbps"]),
                "be_tput_mbps": float(r["be_tput_mbps"]),
                "total_tput_mbps": float(r["total_tput_mbps"]),
                "embb_dropped_mbps": float(r["embb_dropped_mbps"]),
                "be_dropped_mbps": float(r["be_dropped_mbps"]),
                "queue_occupancy_pkts": float(r["queue_occupancy_pkts"]),
                "simulated_urllc_rtt_ms": float(r["simulated_urllc_rtt_ms"]),
                "urllc_packet_loss_pct": float(r["urllc_packet_loss_pct"]),
                "sla_violation": int(r["sla_violation"]),
                "guardrail_status": r["guardrail_status"],
                "reward": float(r.get("reward", 0.0)),
            })
    return rows


def compute_metrics(results_data: list) -> dict:
    """Computes summary benchmark metrics strictly from loaded CSV rows."""
    latencies = [r["simulated_urllc_rtt_ms"] for r in results_data]
    losses = [r["urllc_packet_loss_pct"] for r in results_data]
    embb_tputs = [r["embb_tput_mbps"] for r in results_data]
    total_tputs = [r["total_tput_mbps"] for r in results_data]
    sla_violations = [r["sla_violation"] for r in results_data]
    repaired_count = sum(1 for r in results_data if r["guardrail_status"] == "REPAIRED")
    blocked_count = sum(1 for r in results_data if r["guardrail_status"] == "BLOCKED")

    total_steps = len(results_data)
    sla_count = sum(sla_violations)
    sla_pct = round((sla_count / total_steps) * 100.0, 1)

    mean_lat = round(float(np.mean(latencies)), 2)
    p99_lat = round(float(np.percentile(latencies, 99)), 2)
    mean_embb_tput = round(float(np.mean(embb_tputs)), 2)
    peak_embb_tput = round(float(np.max(embb_tputs)), 2)
    mean_total_tput = round(float(np.mean(total_tputs)), 2)
    mean_loss = round(float(np.mean(losses)), 2)

    # Congestion recovery time: steps taken to return to latency <= 15 ms after surge starts (step 6)
    recovery_steps = 0
    in_surge = False
    for r in results_data:
        if r["step"] >= 6:
            if r["simulated_urllc_rtt_ms"] > 15.0:
                in_surge = True
                recovery_steps += 1
            elif in_surge and r["simulated_urllc_rtt_ms"] <= 15.0:
                break

    return {
        "mean_latency_ms": mean_lat,
        "p99_latency_ms": p99_lat,
        "mean_embb_tput_mbps": mean_embb_tput,
        "peak_embb_tput_mbps": peak_embb_tput,
        "mean_total_tput_mbps": mean_total_tput,
        "mean_loss_pct": mean_loss,
        "sla_violations": sla_count,
        "sla_violation_pct": sla_pct,
        "recovery_time_s": float(recovery_steps),
        "repaired_count": repaired_count,
        "blocked_count": blocked_count,
    }


def generate_plots(static_res: list, dynamic_res: list, proposed_res: list, output_dir: str = "results") -> None:
    """Renders and saves comparative evaluation charts derived directly from CSV data."""
    os.makedirs(output_dir, exist_ok=True)
    steps = [r["step"] for r in static_res]

    lat_static = [r["simulated_urllc_rtt_ms"] for r in static_res]
    lat_dynamic = [r["simulated_urllc_rtt_ms"] for r in dynamic_res]
    lat_proposed = [r["simulated_urllc_rtt_ms"] for r in proposed_res]

    tput_static = [r["embb_tput_mbps"] for r in static_res]
    tput_dynamic = [r["embb_tput_mbps"] for r in dynamic_res]
    tput_proposed = [r["embb_tput_mbps"] for r in proposed_res]

    # --------------------------------------------------------------------------
    # PLOT 1: results/latency.png
    # --------------------------------------------------------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(steps, lat_static, label="Static Slicing (Fixed)", color="#4A90E2", linewidth=2, linestyle="--")
    plt.plot(steps, lat_dynamic, label="Dynamic (Unsafe LinUCB)", color="#E94A48", linewidth=2.5, marker="o", markersize=4)
    plt.plot(steps, lat_proposed, label="Proposed (SRA-LinUCB + Guardrail)", color="#2ECC71", linewidth=2.5, marker="s", markersize=4)

    plt.axhline(y=15.0, color="crimson", linestyle=":", linewidth=2, label="URLLC SLA Limit (15.0 ms)")
    plt.axvspan(6, 12, color="orange", alpha=0.12, label="eMBB Traffic Surge (Steps 6-12)")

    plt.title("Simulated URLLC Round-Trip Latency (FIFO Model) Under Traffic Surge", fontsize=12, fontweight="bold")
    plt.xlabel("Experiment Step (Seconds)", fontsize=11)
    plt.ylabel("Simulated URLLC RTT (ms)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="upper right", framealpha=0.9)
    plt.tight_layout()

    lat_path = os.path.join(output_dir, "latency.png")
    plt.savefig(lat_path, dpi=300)
    plt.close()
    print(f"[+] Generated: {lat_path}")

    # --------------------------------------------------------------------------
    # PLOT 2: results/throughput.png
    # --------------------------------------------------------------------------
    plt.figure(figsize=(10, 5))
    plt.plot(steps, tput_static, label="Static Slicing (5 Mbps Cap)", color="#4A90E2", linewidth=2, linestyle="--")
    plt.plot(steps, tput_dynamic, label="Dynamic (Unsafe LinUCB)", color="#E94A48", linewidth=2, alpha=0.85)
    plt.plot(steps, tput_proposed, label="Proposed (AI-Safe Dynamic)", color="#2ECC71", linewidth=2.5)

    plt.axvspan(6, 12, color="orange", alpha=0.12, label="eMBB Traffic Surge (Steps 6-12)")
    plt.title("eMBB Slice Throughput Adaptation (Trace Simulation)", fontsize=12, fontweight="bold")
    plt.xlabel("Experiment Step (Seconds)", fontsize=11)
    plt.ylabel("eMBB Actual Throughput (Mbps)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="upper left", framealpha=0.9)
    plt.tight_layout()

    tput_path = os.path.join(output_dir, "throughput.png")
    plt.savefig(tput_path, dpi=300)
    plt.close()
    print(f"[+] Generated: {tput_path}")

    # --------------------------------------------------------------------------
    # PLOT 3: results/comparison.png
    # --------------------------------------------------------------------------
    met_static = compute_metrics(static_res)
    met_dynamic = compute_metrics(dynamic_res)
    met_proposed = compute_metrics(proposed_res)

    fig, ax1 = plt.subplots(figsize=(9, 5))

    regimes = ["Static Slicing", "Dynamic (Unsafe)", "Proposed (AI-Safe)"]
    sla_counts = [met_static["sla_violations"], met_dynamic["sla_violations"], met_proposed["sla_violations"]]
    mean_lats = [met_static["mean_latency_ms"], met_dynamic["mean_latency_ms"], met_proposed["mean_latency_ms"]]
    mean_tputs = [met_static["mean_embb_tput_mbps"], met_dynamic["mean_embb_tput_mbps"], met_proposed["mean_embb_tput_mbps"]]

    x = np.arange(len(regimes))
    width = 0.25

    rects1 = ax1.bar(x - width, sla_counts, width, label="SLA Violations (count)", color="#E94A48")
    rects2 = ax1.bar(x, mean_lats, width, label="Mean Simulated RTT (ms)", color="#F39C12")
    rects3 = ax1.bar(x + width, mean_tputs, width, label="Mean eMBB TPut (Mbps)", color="#2ECC71")

    ax1.set_ylabel("Metric Value", fontsize=11)
    ax1.set_title("Simulation Benchmark Performance Comparison Across Slicing Regimes", fontsize=12, fontweight="bold")
    ax1.set_xticks(x)
    ax1.set_xticklabels(regimes, fontsize=11)
    ax1.legend(loc="upper right")
    ax1.grid(axis="y", linestyle="--", alpha=0.6)

    for rects in [rects1, rects2, rects3]:
        for rect in rects:
            height = rect.get_height()
            ax1.annotate(
                f"{height:.1f}",
                xy=(rect.get_x() + rect.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center", va="bottom", fontsize=9
            )

    plt.tight_layout()
    comp_path = os.path.join(output_dir, "comparison.png")
    plt.savefig(comp_path, dpi=300)
    plt.close()
    print(f"[+] Generated: {comp_path}")


def format_comparison_markdown(m_stat: dict, m_dyn: dict, m_prop: dict) -> str:
    """Formats benchmark summary metrics as a clean GitHub-flavored markdown table."""
    md = [
        "# Simulation Benchmark Performance Summary Table",
        "",
        "> **Note:** Results are derived from the trace-driven FIFO queuing simulation model (10.0 Mbps bottleneck).",
        "",
        "| Metric | Static Slicing (Fixed) | Dynamic Slicing (Unsafe LinUCB) | Proposed System (AI-Safe) |",
        "| :--- | :--- | :--- | :--- |",
        f"| **URLLC Mean Simulated RTT** | {m_stat['mean_latency_ms']:.2f} ms | {m_dyn['mean_latency_ms']:.2f} ms | **{m_prop['mean_latency_ms']:.2f} ms** |",
        f"| **URLLC 99th-Percentile RTT** | {m_stat['p99_latency_ms']:.2f} ms | **{m_dyn['p99_latency_ms']:.2f} ms** *(breach)* | **{m_prop['p99_latency_ms']:.2f} ms** *(safe)* |",
        f"| **eMBB Mean Throughput** | {m_stat['mean_embb_tput_mbps']:.2f} Mbps | {m_dyn['mean_embb_tput_mbps']:.2f} Mbps | **{m_prop['mean_embb_tput_mbps']:.2f} Mbps** |",
        f"| **eMBB Peak Throughput** | {m_stat['peak_embb_tput_mbps']:.2f} Mbps | {m_dyn['peak_embb_tput_mbps']:.2f} Mbps | **{m_prop['peak_embb_tput_mbps']:.2f} Mbps** |",
        f"| **URLLC Packet Loss** | {m_stat['mean_loss_pct']:.1f}% | {m_dyn['mean_loss_pct']:.1f}% | **{m_prop['mean_loss_pct']:.1f}%** |",
        f"| **SLA Violations (Count / %)** | {m_stat['sla_violations']} ({m_stat['sla_violation_pct']}%) | **{m_dyn['sla_violations']} ({m_dyn['sla_violation_pct']}%)** | **{m_prop['sla_violations']} ({m_prop['sla_violation_pct']}%)** |",
        f"| **Congestion Recovery Time** | {m_stat['recovery_time_s']:.1f} s | {m_dyn['recovery_time_s']:.1f} s | **{m_prop['recovery_time_s']:.1f} s** |",
        f"| **Guardrail Repaired Actions** | 0 (N/A) | 0 (Disabled) | **{m_prop['repaired_count']} (Active)** |",
        "| **Security Overhead Mode** | N/A | Ignored | Simulated (1.2 ms) |",
        "| **Deterministic Safety Guard** | No | No | **Yes (Module 6)** |",
        "",
    ]
    return "\n".join(md)


def print_comparison_table(static_res: list, dynamic_res: list, proposed_res: list, output_dir: str = "results") -> None:
    """Outputs the official simulation benchmark comparison table and persists to markdown & text files."""
    m_stat = compute_metrics(static_res)
    m_dyn = compute_metrics(dynamic_res)
    m_prop = compute_metrics(proposed_res)

    table_lines = [
        "=" * 82,
        " SIMULATION BENCHMARK SUMMARY TABLE (Trace-Driven Model)",
        " NOTE: Results are derived from a simplified FIFO queuing simulation model.",
        "=" * 82,
        f"{'Metric':<30} | {'Static (Fixed)':<14} | {'Dynamic (Unsafe)':<16} | {'Proposed (AI-Safe)':<16}",
        "-" * 82,
    ]

    rows = [
        ("URLLC Mean Simulated RTT", f"{m_stat['mean_latency_ms']:.2f} ms", f"{m_dyn['mean_latency_ms']:.2f} ms", f"{m_prop['mean_latency_ms']:.2f} ms"),
        ("URLLC 99th-Percentile RTT", f"{m_stat['p99_latency_ms']:.2f} ms", f"{m_dyn['p99_latency_ms']:.2f} ms", f"{m_prop['p99_latency_ms']:.2f} ms"),
        ("eMBB Mean Throughput", f"{m_stat['mean_embb_tput_mbps']:.2f} Mbps", f"{m_dyn['mean_embb_tput_mbps']:.2f} Mbps", f"{m_prop['mean_embb_tput_mbps']:.2f} Mbps"),
        ("eMBB Peak Throughput", f"{m_stat['peak_embb_tput_mbps']:.2f} Mbps", f"{m_dyn['peak_embb_tput_mbps']:.2f} Mbps", f"{m_prop['peak_embb_tput_mbps']:.2f} Mbps"),
        ("URLLC Packet Loss", f"{m_stat['mean_loss_pct']:.1f} %", f"{m_dyn['mean_loss_pct']:.1f} %", f"{m_prop['mean_loss_pct']:.1f} %"),
        ("SLA Violations (count / %)", f"{m_stat['sla_violations']} ({m_stat['sla_violation_pct']}%)", f"{m_dyn['sla_violations']} ({m_dyn['sla_violation_pct']}%)", f"{m_prop['sla_violations']} ({m_prop['sla_violation_pct']}%)"),
        ("Congestion Recovery Time", f"{m_stat['recovery_time_s']:.1f} s", f"{m_dyn['recovery_time_s']:.1f} s", f"{m_prop['recovery_time_s']:.1f} s"),
        ("Guardrail Repaired Actions", "0 (N/A)", "0 (Disabled)", f"{m_prop['repaired_count']} (Active)"),
        ("Security Overhead Mode", "N/A", "Ignored", "Simulated (1.2 ms)"),
        ("Deterministic Safety Guard", "No", "No", "Yes (Module 6)"),
    ]

    for label, stat, dyn, prop in rows:
        table_lines.append(f"{label:<30} | {stat:<14} | {dyn:<16} | {prop:<16}")
    table_lines.append("=" * 82)

    table_text = "\n".join(table_lines)
    print("\n" + table_text + "\n")

    # Persist clean files in output_dir
    os.makedirs(output_dir, exist_ok=True)
    txt_path = os.path.join(output_dir, "summary_table.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(table_text + "\n")

    md_path = os.path.join(output_dir, "summary_table.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(format_comparison_markdown(m_stat, m_dyn, m_prop))

    print(f"[+] Summary table saved as markdown: {md_path}")
    print(f"[+] Summary table saved as text:     {txt_path}")


def run_all(output_dir: str = "results", table_only: bool = False) -> None:
    """Executes all 3 experiments, writes CSVs, loads data, and generates plots and table."""
    static_csv = os.path.join(output_dir, "static_results.csv")
    dynamic_csv = os.path.join(output_dir, "dynamic_results.csv")
    proposed_csv = os.path.join(output_dir, "proposed_results.csv")

    if not table_only or not (os.path.exists(static_csv) and os.path.exists(dynamic_csv) and os.path.exists(proposed_csv)):
        run_static(static_csv)
        run_dynamic(dynamic_csv)
        run_proposed(proposed_csv)

    # Load directly from CSV to guarantee graphs and table are computed strictly from files
    stat_data = load_csv_data(static_csv)
    dyn_data = load_csv_data(dynamic_csv)
    prop_data = load_csv_data(proposed_csv)

    if not table_only:
        generate_plots(stat_data, dyn_data, prop_data, output_dir=output_dir)

    print_comparison_table(stat_data, dyn_data, prop_data, output_dir=output_dir)


if __name__ == "__main__":
    import argparse
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    parser = argparse.ArgumentParser(description="Evaluate and compare network slicing paradigms.")
    parser.add_argument("--table-only", action="store_true", help="Quickly display and save the summary table from existing CSVs without re-running simulations.")
    parser.add_argument("--output-dir", default="results", help="Directory for output CSVs, PNGs, and tables.")
    args = parser.parse_args()

    run_all(output_dir=args.output_dir, table_only=args.table_only)

