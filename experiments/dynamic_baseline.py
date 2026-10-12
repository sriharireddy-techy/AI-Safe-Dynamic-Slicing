"""
Experiment 2: Dynamic Slicing Without Safety (Module 9)
=======================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

SIMULATION MODEL SPECIFICATION & LIMITATIONS:
--------------------------------------------
- Architecture: Simplified single-buffer FIFO queuing model for comparative behavioral evaluation.
- Unconstrained AI Policy:
    * Policy: Risk-neutral LinUCB (alpha=1.0, lambda=0.0, no risk penalty).
    * Safety Layer: NONE (SLA Guardrail is DISABLED).
    * Step Size: 2.0 Mbps adjustments per action (matching original baseline design).
    * Control Mechanism: LinUCB directly adjusts eMBB bandwidth limit between 2.0 and 9.0 Mbps.
- Physical & Queuing Model (from topology/topology.py):
    * Base RTT: 10.15 ms.
    * Link Capacity: 10.0 Mbps bottleneck service rate (1.20 ms per 1500B packet).
    * Buffer Limit: 50 packets maximum buffer depth.
    * Overload Dynamics: When admitted traffic exceeds 10.0 Mbps, unserviced packets
      accumulate in the egress buffer at rate dQ = (Admitted - 10.0) * 1e6 / 12000 pkts/s.
    * Bufferbloat Latency: simulated_urllc_rtt_ms = 10.15 ms + (Queue_pkts * 1.20 ms).
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

from ai.context_builder import ContextBuilder
from ai.linucb import SRALinUCB, ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE, ACTION_NAMES
from telemetry.monitor import TelemetryRecord
from feedback.reward import DEFAULT_REWARD_ENGINE
from feedback.learner import FeedbackLearner
from experiments.static_baseline import SYNTHETIC_WORKLOAD_PROFILE


def simulate_dynamic_step(
    step_data: Dict[str, Any],
    embb_limit: float,
    current_queue_pkts: float = 0.0,
    link_capacity: float = 10.0,
    buffer_limit: float = 50.0
) -> Dict[str, Any]:
    """
    Simulates network response when LinUCB's allocation is applied WITHOUT safety validation.
    - eMBB is granted embb_limit (up to 9.0 Mbps).
    - Best-Effort is granted remaining nominal bandwidth (min 0.5 Mbps).
    - When aggregate admitted load exceeds link_capacity (10 Mbps), queue accumulates packets,
      producing bufferbloat delay (1.20 ms per packet) and tail-drop packet loss if queue exceeds 50.
    """
    urllc_off = float(step_data["urllc_offered"])
    embb_off = float(step_data["embb_offered"])
    be_off = float(step_data.get("be_offered", 1.0))
    total_offered = round(urllc_off + embb_off + be_off, 3)

    # Allocations under unconstrained AI (no guardrail gatekeeper)
    urllc_alloc = 3.0
    embb_alloc = embb_limit
    be_alloc = max(0.5, link_capacity - urllc_alloc - embb_alloc)
    total_alloc = round(urllc_alloc + embb_alloc + be_alloc, 3)

    # Traffic admitted onto the link
    urllc_tput = urllc_off  # URLLC injected at line rate
    embb_tput = min(embb_off, embb_alloc)
    be_tput = min(be_off, be_alloc)

    embb_dropped = round(max(0.0, embb_off - embb_alloc), 3)
    be_dropped = round(max(0.0, be_off - be_alloc), 3)

    # Total traffic attempting to traverse the 10.0 Mbps bottleneck
    admitted_traffic = urllc_tput + embb_tput + be_tput
    total_tput = min(link_capacity, admitted_traffic)

    # Fluid queue evolution:
    # When admitted_traffic exceeds link_capacity (10.0 Mbps), bufferbloat occurs
    surplus_mbps = admitted_traffic - link_capacity
    delta_pkts = (surplus_mbps * 1e6) / 12000.0  # packets accumulated per second

    new_queue = max(0.0, current_queue_pkts + delta_pkts)

    if new_queue > buffer_limit:
        overflow_pkts = new_queue - buffer_limit
        new_queue = buffer_limit
        packet_loss_pct = round(min(10.0, (overflow_pkts / (admitted_traffic * 1e6 / 12000.0)) * 100.0), 1)
    else:
        packet_loss_pct = 0.0

    # Simulated RTT = base RTT 10.15 ms + queuing delay (1.20 ms per packet)
    sim_rtt = round(10.15 + (new_queue * 1.20), 3)

    sla_violation = 1 if (sim_rtt > 15.0 or packet_loss_pct > 1.0) else 0

    return {
        "step": int(step_data["step"]),
        "time_s": float(step_data["step"]),
        "mode": "DYNAMIC_UNSAFE_AI",
        "description": str(step_data["desc"]),
        "urllc_offered_mbps": round(urllc_off, 3),
        "embb_offered_mbps": round(embb_off, 3),
        "be_offered_mbps": round(be_off, 3),
        "total_offered_mbps": total_offered,
        "urllc_alloc_mbps": round(urllc_alloc, 3),
        "embb_alloc_mbps": round(embb_alloc, 3),
        "be_alloc_mbps": round(be_alloc, 3),
        "total_alloc_mbps": total_alloc,
        "urllc_tput_mbps": round(urllc_tput, 3),
        "embb_tput_mbps": round(embb_tput, 3),
        "be_tput_mbps": round(be_tput, 3),
        "total_tput_mbps": round(total_tput, 3),
        "embb_dropped_mbps": embb_dropped,
        "be_dropped_mbps": be_dropped,
        "queue_occupancy_pkts": round(new_queue, 2),
        "simulated_urllc_rtt_ms": sim_rtt,
        "urllc_packet_loss_pct": packet_loss_pct,
        "sla_violation": sla_violation,
        "guardrail_status": "UNSAFE_BLIND",
    }


def run_simulation(output_csv: Optional[str] = None) -> List[Dict[str, Any]]:
    """Runs Experiment 2 in trace simulation mode across the full 20-step workload."""
    builder = ContextBuilder()
    agent = SRALinUCB(d=6, n_actions=3, alpha=1.0, risk_lambda=0.0)  # Pure risk-neutral LinUCB
    learner = FeedbackLearner(agent=agent)

    current_limit = 5.0
    current_q = 0.0
    results: List[Dict[str, Any]] = []

    print("\n" + "=" * 75)
    print(" EXPERIMENT 2: DYNAMIC SLICING WITHOUT SAFETY (Trace-Driven Simulation)")
    print(" Policy: Risk-Neutral LinUCB (lambda=0.0) | Safety Guardrail: DISABLED (NONE)")
    print("=" * 75)

    last_rec = TelemetryRecord(
        timestamp=0.0, interface="s1-eth4",
        urllc_latency_ms=10.15, urllc_packet_loss=0.0,
        bottleneck_rx_bytes=0, bottleneck_tx_bytes=0,
        throughput_mbps=4.0, traffic_rate_mbps=4.2, queue_occupancy=0
    )

    for step_data in SYNTHETIC_WORKLOAD_PROFILE:
        step_num = int(step_data["step"])

        # 1. Build context vector from current telemetry
        x_t = builder.build_context(last_rec)

        # 2. AI selects action WITHOUT guardrail
        action, diag = agent.select_action(x_t)

        # 3. Apply action to update eMBB limit (step size 2.0 Mbps, matching teammate baseline)
        if action == ACTION_DECREASE:
            current_limit = max(2.0, current_limit - 2.0)
        elif action == ACTION_INCREASE:
            current_limit = min(9.0, current_limit + 2.0)

        # 4. Simulate network response
        res = simulate_dynamic_step(
            step_data=step_data,
            embb_limit=current_limit,
            current_queue_pkts=current_q
        )
        current_q = res["queue_occupancy_pkts"]

        # 5. Form post-action telemetry
        post_rec = TelemetryRecord(
            timestamp=float(step_num), interface="s1-eth4",
            urllc_latency_ms=res["simulated_urllc_rtt_ms"],
            urllc_packet_loss=res["urllc_packet_loss_pct"],
            bottleneck_rx_bytes=1000 * step_num,
            bottleneck_tx_bytes=int(res["total_tput_mbps"] * 125000),
            throughput_mbps=res["embb_tput_mbps"],
            traffic_rate_mbps=res["total_tput_mbps"],
            queue_occupancy=int(res["queue_occupancy_pkts"])
        )
        last_rec = post_rec

        # 6. Feedback reward and model update
        fb_res = learner.process_feedback(
            candidate_action=action,
            context=x_t,
            post_telemetry=post_rec,
            executed_action=action,
            guardrail_result={"approved": True}
        )
        res["reward"] = fb_res["reward"]
        results.append(res)

        print(
            f" Step {step_num:02d} | AI: {ACTION_NAMES[action]:<13} (Limit: {current_limit:.1f}M) | "
            f"eMBB TPut: {res['embb_tput_mbps']:.2f}M | Sim RTT: {res['simulated_urllc_rtt_ms']:.2f} ms | "
            f"Queue: {res['queue_occupancy_pkts']:.1f} pkts | SLA Violations: {res['sla_violation']} | Reward: {fb_res['reward']:+.2f}"
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
    parser = argparse.ArgumentParser(description="Experiment 2: Dynamic Slicing Without Safety (Simulation).")
    parser.add_argument("--output", type=str, default="results/dynamic_results.csv", help="CSV output path.")
    args = parser.parse_args()
    run_simulation(output_csv=args.output)


if __name__ == "__main__":
    main()
