"""
Experiment 1: Static Network Slicing Baseline (Module 9)
========================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

SIMULATION MODEL SPECIFICATION & LIMITATIONS:
--------------------------------------------
- Architecture: Simplified single-buffer FIFO queuing model for comparative behavioral evaluation.
- Assumptions & Physical Parameters (from topology/topology.py):
    * Base RTT: 10.15 ms (2 * 5.0 ms propagation delay + 0.15 ms baseline switch delay).
    * Link Capacity: 10.0 Mbps bottleneck capacity (12,000 bits / 10 Mbps = 1.20 ms transmission delay per 1500B packet).
    * Buffer Capacity: 50 packets maximum egress buffer limit.
    * Fixed Static Allocation:
        - URLLC Slice: 3.0 Mbps (locked reservation)
        - eMBB Slice:  5.0 Mbps (locked rate ceiling)
        - Best-Effort: 2.0 Mbps (locked background partition)
- Limitations:
    * This is a trace-driven simulation benchmark, NOT a validated physical Linux HTB/OVS measurement.
    * All latency values are SIMULATED round-trip times (simulated_urllc_rtt_ms).
"""

import os
import sys
import argparse
import csv
from typing import List, Dict, Any, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from slicing.slice_config import DEFAULT_SLICING_CONFIG, SliceAllocation


# ------------------------------------------------------------------------------
# SYNTHETIC MULTI-SLICE WORKLOAD TRACE (20 Time Steps)
# Accounts for URLLC, eMBB, and Best-Effort traffic
# ------------------------------------------------------------------------------
SYNTHETIC_WORKLOAD_PROFILE: List[Dict[str, Any]] = [
    # Phase 1: Baseline steady-state traffic (Steps 1-5)
    {"step": 1,  "urllc_offered": 1.0, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Normal traffic"},
    {"step": 2,  "urllc_offered": 1.0, "embb_offered": 3.5, "be_offered": 1.0, "desc": "Normal traffic"},
    {"step": 3,  "urllc_offered": 1.2, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Normal traffic"},
    {"step": 4,  "urllc_offered": 1.0, "embb_offered": 4.0, "be_offered": 1.0, "desc": "Normal traffic"},
    {"step": 5,  "urllc_offered": 1.1, "embb_offered": 4.2, "be_offered": 1.0, "desc": "Normal traffic"},
    # Phase 2: eMBB traffic surge (Steps 6-12)
    {"step": 6,  "urllc_offered": 1.5, "embb_offered": 7.0, "be_offered": 1.0, "desc": "eMBB surge start"},
    {"step": 7,  "urllc_offered": 1.5, "embb_offered": 8.5, "be_offered": 1.0, "desc": "eMBB high surge"},
    {"step": 8,  "urllc_offered": 1.8, "embb_offered": 9.2, "be_offered": 1.0, "desc": "eMBB peak surge"},
    {"step": 9,  "urllc_offered": 1.8, "embb_offered": 9.5, "be_offered": 1.0, "desc": "eMBB peak surge"},
    {"step": 10, "urllc_offered": 1.5, "embb_offered": 9.0, "be_offered": 1.0, "desc": "eMBB peak surge"},
    {"step": 11, "urllc_offered": 1.2, "embb_offered": 8.5, "be_offered": 1.0, "desc": "eMBB sustained surge"},
    {"step": 12, "urllc_offered": 1.0, "embb_offered": 7.5, "be_offered": 1.0, "desc": "eMBB surge subsiding"},
    # Phase 3: Traffic recovery (Steps 13-18)
    {"step": 13, "urllc_offered": 1.0, "embb_offered": 5.0, "be_offered": 1.0, "desc": "Congestion recovery"},
    {"step": 14, "urllc_offered": 1.0, "embb_offered": 4.0, "be_offered": 1.0, "desc": "Recovery to normal"},
    {"step": 15, "urllc_offered": 1.1, "embb_offered": 3.5, "be_offered": 1.0, "desc": "Normal steady state"},
    {"step": 16, "urllc_offered": 1.0, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Normal steady state"},
    {"step": 17, "urllc_offered": 1.0, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Normal steady state"},
    {"step": 18, "urllc_offered": 1.0, "embb_offered": 3.2, "be_offered": 1.0, "desc": "Normal steady state"},
    # Phase 4: Security modeling check (Steps 19-20)
    {"step": 19, "urllc_offered": 1.2, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Security tunnel check"},
    {"step": 20, "urllc_offered": 1.0, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Final baseline step"},
]


def simulate_static_step(
    step_data: Dict[str, Any],
    static_alloc: SliceAllocation,
    current_queue_pkts: float = 0.0
) -> Dict[str, Any]:
    """
    Simulates network response under rigid static slice partitioning.
    - URLLC is allocated static_alloc.urllc_mbps (3.0 Mbps).
    - eMBB is allocated static_alloc.embb_mbps (5.0 Mbps).
    - Best-Effort is allocated static_alloc.be_mbps (2.0 Mbps).
    Traffic exceeding the slice's static ceiling is dropped at the slice boundary.
    """
    urllc_off = float(step_data["urllc_offered"])
    embb_off = float(step_data["embb_offered"])
    be_off = float(step_data.get("be_offered", 1.0))
    total_offered = round(urllc_off + embb_off + be_off, 3)

    # Actual throughput admitted per slice under static rate ceilings
    urllc_tput = min(urllc_off, static_alloc.urllc_mbps)
    embb_tput = min(embb_off, static_alloc.embb_mbps)
    be_tput = min(be_off, static_alloc.be_mbps)
    total_tput = round(urllc_tput + embb_tput + be_tput, 3)

    # Dropped traffic per slice
    embb_dropped = round(max(0.0, embb_off - static_alloc.embb_mbps), 3)
    be_dropped = round(max(0.0, be_off - static_alloc.be_mbps), 3)

    # Fluid FIFO queue dynamics on admitted traffic:
    # Admitted traffic (total_tput) never exceeds 3.0 + 5.0 + 2.0 = 10.0 Mbps link capacity
    admitted_surplus = total_tput - 10.0
    # Queue evolution: drains to 0 because admitted <= 10.0 Mbps
    new_queue = max(0.0, current_queue_pkts + (admitted_surplus * 1e6 / 12000.0))
    # Simulated RTT: base RTT 10.15 ms + transmission delay (1.20 ms per packet)
    sim_rtt = round(10.15 + (new_queue * 1.20), 3)
    packet_loss_pct = 0.0

    sla_violation = 1 if (sim_rtt > 15.0 or packet_loss_pct > 1.0) else 0

    return {
        "step": int(step_data["step"]),
        "time_s": float(step_data["step"]),
        "mode": "STATIC_SLICING",
        "description": str(step_data["desc"]),
        "urllc_offered_mbps": round(urllc_off, 3),
        "embb_offered_mbps": round(embb_off, 3),
        "be_offered_mbps": round(be_off, 3),
        "total_offered_mbps": total_offered,
        "urllc_alloc_mbps": round(static_alloc.urllc_mbps, 3),
        "embb_alloc_mbps": round(static_alloc.embb_mbps, 3),
        "be_alloc_mbps": round(static_alloc.be_mbps, 3),
        "total_alloc_mbps": round(static_alloc.total_mbps, 3),
        "urllc_tput_mbps": round(urllc_tput, 3),
        "embb_tput_mbps": round(embb_tput, 3),
        "be_tput_mbps": round(be_tput, 3),
        "total_tput_mbps": total_tput,
        "embb_dropped_mbps": embb_dropped,
        "be_dropped_mbps": be_dropped,
        "queue_occupancy_pkts": round(new_queue, 2),
        "simulated_urllc_rtt_ms": sim_rtt,
        "urllc_packet_loss_pct": packet_loss_pct,
        "sla_violation": sla_violation,
        "guardrail_status": "NOT_APPLICABLE",
        "reward": 0.0,
    }


def run_simulation(output_csv: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs Experiment 1 in trace simulation mode across the full 20-step workload."""
    static_alloc = DEFAULT_SLICING_CONFIG.get_default_static_allocation()  # 3.0 URLLC, 5.0 eMBB, 2.0 BE
    results: List[Dict[str, Any]] = []
    current_q = 0.0

    print("\n" + "=" * 75)
    print(" EXPERIMENT 1: STATIC SLICING BASELINE (Trace-Driven Simulation)")
    print(f" Fixed Allocation: URLLC={static_alloc.urllc_mbps}M | eMBB={static_alloc.embb_mbps}M | BE={static_alloc.be_mbps}M (Total=10.0M)")
    print("=" * 75)

    for item in SYNTHETIC_WORKLOAD_PROFILE:
        res = simulate_static_step(item, static_alloc, current_queue_pkts=current_q)
        current_q = res["queue_occupancy_pkts"]
        results.append(res)
        print(
            f" Step {res['step']:02d} | eMBB TPut: {res['embb_tput_mbps']:.2f} Mbps "
            f"(Offered: {res['embb_offered_mbps']:.1f}M, Drop: {res['embb_dropped_mbps']:.1f}M) | "
            f"Sim RTT: {res['simulated_urllc_rtt_ms']:.2f} ms | SLA Violations: {res['sla_violation']}"
        )

    if output_csv:
        os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
        keys = results[0].keys()
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[+] Results saved to: {output_csv}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Experiment 1: Static Slicing Baseline (Simulation).")
    parser.add_argument("--output", type=str, default="results/static_results.csv", help="CSV output path.")
    args = parser.parse_args()
    run_simulation(output_csv=args.output)


if __name__ == "__main__":
    main()