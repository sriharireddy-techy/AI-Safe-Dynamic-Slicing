"""
Live / Demonstration Pipeline: Module 2 -> Module 3 -> Module 4
================================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Demonstrates the real-time closed-loop decision sequence:
    TelemetryRecord (Module 2)
              |
              v
    ContextBuilder (Module 3)
              |
              v
    6D Context Vector x_t
              |
              v
    SRA-LinUCB (Module 4)
              |
              v
    Candidate Action in {0, 1, 2}

Modes:
- Default: Runs an illustrative 5-step scenario sequence (Healthy -> Congested -> Recovery).
- Live (--live): Connects to live NetworkTelemetryCollector polling active Mininet interfaces.

Note:
The selected action at this stage is strictly a CANDIDATE ACTION.
Deterministic safety guardrails (Module 6) and SDN flow enforcement (Module 7)
are integrated in later phases.
"""

import sys
import os
import time
import argparse
from typing import List

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.monitor import TelemetryRecord, NetworkTelemetryCollector
from ai.context_builder import ContextBuilder
from ai.linucb import (
    SRALinUCB,
    ACTION_DECREASE,
    ACTION_MAINTAIN,
    ACTION_INCREASE,
    ACTION_NAMES
)


def run_pipeline_step(record: TelemetryRecord, builder: ContextBuilder, agent: SRALinUCB, step_num: int):
    """Executes a single pass through Modules 2 -> 3 -> 4 and prints formatted diagnostic output."""
    # Module 3: Build context
    x_t = builder.build_context(record)

    # Module 4: Select candidate action
    action, diag = agent.select_action(x_t)

    print(f"==================================================================")
    print(f" PIPELINE STEP {step_num} | Time: {record.timestamp:.2f}s | Target: {record.interface}")
    print(f"==================================================================")
    print(" [Module 2 Telemetry]")
    print(f"   Latency    : {record.urllc_latency_ms:.2f} ms")
    print(f"   Packet Loss: {record.urllc_packet_loss:.1f} %")
    print(f"   Throughput : {record.throughput_mbps:.3f} Mbps")
    print(f"   Queue      : {record.queue_occupancy} packets")

    print("\n [Module 3 Context Vector x_t (R^6)]")
    formatted_ctx = [f"{val:.3f}" for val in x_t]
    print(f"   x_t = [{', '.join(formatted_ctx)}]")
    print(f"   (Bias={x_t[0]:.2f}, Lat={x_t[1]:.3f}, TPut={x_t[2]:.3f}, Q={x_t[3]:.3f}, Trend={x_t[4]:.3f}, Loss={x_t[5]:.3f})")

    print(f"\n [Module 4 SRA-LinUCB Decision]")
    print(f"   Context Risk R(x_t) : {diag['context_risk']:.4f}")
    print(f"   Action Scores:")
    for a in (ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE):
        score = diag["scores"][a]
        mean = diag["means"][a]
        uncert = diag["uncertainties"][a]
        risk_pen = diag["risk_penalties"][a]
        name = ACTION_NAMES[a]
        print(f"     [{a}] {name:<14} -> Total: {score:+.4f} (Mean: {mean:+.4f}, UCB-Bonus: {uncert:+.4f}, Risk-Pen: {risk_pen:+.4f})")

    chosen_name = ACTION_NAMES[action]
    print(f"\n   >>> CANDIDATE ACTION SELECTED: [{action}] {chosen_name}")
    print(f"   (Status: Candidate proposed by AI; pending safety guardrail validation)")
    print("-" * 66 + "\n")


def run_synthetic_demo():
    """Runs a simulated sequence demonstrating the AI adapting to network congestion."""
    builder = ContextBuilder(max_latency=50.0, max_throughput=10.0, max_queue=50.0)
    agent = SRALinUCB(d=6, n_actions=3, alpha=1.0, risk_lambda=0.5)

    scenarios: List[TelemetryRecord] = [
        # 1. Healthy baseline
        TelemetryRecord(
            timestamp=100.0, interface="s1-eth4",
            urllc_latency_ms=10.4, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=25000,
            throughput_mbps=2.5, traffic_rate_mbps=2.8, queue_occupancy=0
        ),
        # 2. eMBB traffic begins surging
        TelemetryRecord(
            timestamp=101.0, interface="s1-eth4",
            urllc_latency_ms=16.8, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=3000, bottleneck_tx_bytes=100000,
            throughput_mbps=8.2, traffic_rate_mbps=8.5, queue_occupancy=6
        ),
        # 3. Peak congestion (SLA boundary breached, buffer backlogged)
        TelemetryRecord(
            timestamp=102.0, interface="s1-eth4",
            urllc_latency_ms=36.5, urllc_packet_loss=3.0,
            bottleneck_rx_bytes=6000, bottleneck_tx_bytes=1300000,
            throughput_mbps=9.8, traffic_rate_mbps=10.0, queue_occupancy=28
        ),
        # 4. De-congestion and buffer drainage
        TelemetryRecord(
            timestamp=103.0, interface="s1-eth4",
            urllc_latency_ms=15.2, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=7000, bottleneck_tx_bytes=700000,
            throughput_mbps=5.5, traffic_rate_mbps=5.8, queue_occupancy=3
        ),
        # 5. Restored stable equilibrium
        TelemetryRecord(
            timestamp=104.0, interface="s1-eth4",
            urllc_latency_ms=10.8, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=8000, bottleneck_tx_bytes=350000,
            throughput_mbps=3.0, traffic_rate_mbps=3.2, queue_occupancy=0
        ),
    ]

    print("\n" + "=" * 66)
    print(" DEMO MODE: Running 5 Synthetic Pipeline Cycles (Mod 2 -> 3 -> 4)")
    print("=" * 66 + "\n")

    for step_num, rec in enumerate(scenarios, 1):
        run_pipeline_step(rec, builder, agent, step_num)
        time.sleep(0.3)


def run_live_pipeline():
    """Connects directly to the live NetworkTelemetryCollector running against Mininet."""
    print("\n" + "=" * 66)
    print(" LIVE MODE: Polling Mininet via NetworkTelemetryCollector (1s cadence)")
    print(" Press Ctrl+C to Stop")
    print("=" * 66 + "\n")

    collector = NetworkTelemetryCollector(interface="s1-eth4", h1_ip="10.0.0.1", h4_ip="10.0.0.4")
    builder = ContextBuilder(max_latency=50.0, max_throughput=10.0, max_queue=50.0)
    agent = SRALinUCB(d=6, n_actions=3, alpha=1.0, risk_lambda=0.5)

    step = 1
    try:
        while True:
            record = collector.collect()
            run_pipeline_step(record, builder, agent, step)
            step += 1
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Pipeline loop stopped by user]")


def main():
    parser = argparse.ArgumentParser(description="Demonstrate Module 2 -> 3 -> 4 Pipeline.")
    parser.add_argument("--live", action="store_true", help="Poll live Mininet environment.")
    args = parser.parse_args()

    if args.live:
        run_live_pipeline()
    else:
        run_synthetic_demo()


if __name__ == "__main__":
    main()
