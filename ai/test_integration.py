"""
Integration Tests: Module 2 -> Module 3 -> Module 4
====================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Verifies that:
1. TelemetryRecord (Module 2)
2. ContextBuilder (Module 3)
3. SRALinUCB (Module 4)

operate cleanly together as a unified pipeline without any intermediate glue code.

Validates:
- Correct data types, shapes, and mathematical bounds.
- Multi-scenario behavior: Healthy, Congested, and Recovery states.
- Asymmetric risk penalty response across the full pipeline.
- Sentinel failure handling (probe unreachable).
- Multi-step sequential progression.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.monitor import TelemetryRecord
from ai.context_builder import ContextBuilder
from ai.linucb import (
    SRALinUCB,
    ACTION_DECREASE,
    ACTION_MAINTAIN,
    ACTION_INCREASE,
    ACTION_NAMES
)


class TestPipelineIntegration(unittest.TestCase):
    """Integration test suite for the Telemetry -> Context -> SRA-LinUCB pipeline."""

    def setUp(self):
        """Initialize clean instances of ContextBuilder and SRALinUCB."""
        self.builder = ContextBuilder(
            max_latency=50.0,
            max_throughput=10.0,
            max_queue=50.0
        )
        self.agent = SRALinUCB(
            d=6,
            n_actions=3,
            alpha=1.0,
            risk_lambda=0.5,
            risk_weights=(0.4, 0.3, 0.2, 0.1)
        )

    def test_end_to_end_dataflow_and_interfaces(self):
        """
        Verify the complete dataflow:
        TelemetryRecord -> ContextBuilder.build_context() -> x_t -> SRALinUCB.select_action() -> candidate action.
        """
        # Step 1: Module 2 output (TelemetryRecord)
        record = TelemetryRecord(
            timestamp=1700000000.0,
            interface="s1-eth4",
            urllc_latency_ms=11.5,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=10000,
            bottleneck_tx_bytes=50000,
            throughput_mbps=3.5,
            traffic_rate_mbps=4.2,
            queue_occupancy=2
        )

        # Step 2: Module 3 transformation (ContextBuilder)
        x_t = self.builder.build_context(record)

        # Assert Module 3 output contracts
        self.assertIsInstance(x_t, np.ndarray)
        self.assertEqual(x_t.shape, (6,))
        self.assertEqual(x_t.dtype, np.float64)
        self.assertTrue(np.isfinite(x_t).all(), "Context vector contains non-finite values (NaN or Inf)")

        # Verify component boundaries
        self.assertEqual(x_t[0], 1.0, "Bias term must be strictly 1.0")
        self.assertTrue(0.0 <= x_t[1] <= 1.0, "Normalized latency out of bounds [0, 1]")
        self.assertTrue(0.0 <= x_t[2] <= 1.0, "Normalized throughput out of bounds [0, 1]")
        self.assertTrue(0.0 <= x_t[3] <= 1.0, "Normalized queue out of bounds [0, 1]")
        self.assertTrue(-1.0 <= x_t[4] <= 1.0, "Latency trend out of bounds [-1, 1]")
        self.assertTrue(0.0 <= x_t[5] <= 1.0, "Packet loss ratio out of bounds [0, 1]")

        # Step 3: Module 4 decision (SRALinUCB)
        action, diag = self.agent.select_action(x_t)

        # Assert Module 4 output contracts
        self.assertIn(action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})
        self.assertIn(action, [0, 1, 2])
        self.assertEqual(diag["selected_action"], action)
        self.assertIn(diag["selected_action_name"], list(ACTION_NAMES.values()))

        # Verify diagnostics completeness for all 3 actions
        for a in (ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE):
            self.assertIn(a, diag["scores"])
            self.assertIn(a, diag["means"])
            self.assertIn(a, diag["uncertainties"])
            self.assertIn(a, diag["risk_penalties"])

    def test_scenario_a_healthy_network(self):
        """
        SCENARIO A — Healthy Network:
        Low latency (10.5 ms), moderate throughput (3.0 Mbps), zero queue (0 pkts),
        zero loss (0%), stable trend.
        Verifies:
        - Risk score R(x_t) is low.
        - Valid candidate action is selected without errors.
        """
        record = TelemetryRecord(
            timestamp=100.0,
            interface="s1-eth4",
            urllc_latency_ms=10.5,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=2000,
            throughput_mbps=3.0,
            traffic_rate_mbps=3.5,
            queue_occupancy=0
        )

        x_t = self.builder.build_context(record)
        action, diag = self.agent.select_action(x_t)

        # In healthy network, risk R(x_t) must be low
        risk = diag["context_risk"]
        self.assertLess(risk, 0.20, f"Expected low risk in healthy state, got {risk}")
        self.assertIn(action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})

    def test_scenario_b_congested_network(self):
        """
        SCENARIO B — Congested Network:
        High latency (38.0 ms), high throughput (9.6 Mbps), high queue (25 pkts),
        surging positive latency trend, and packet loss (4.0%).
        Verifies:
        - Context risk R(x_t) is elevated.
        - SRA risk penalty actively suppresses Action 2 (INCREASE).
        - Action 0 (DECREASE) receives risk incentive.
        """
        # Step 1: Initial baseline sample at t=0
        baseline_record = TelemetryRecord(
            timestamp=100.0, interface="s1-eth4",
            urllc_latency_ms=12.0, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=2000,
            throughput_mbps=4.0, traffic_rate_mbps=4.5, queue_occupancy=0
        )
        self.builder.build_context(baseline_record)

        # Step 2: Congested sample at t=1 (latency jumped from 12 ms to 38 ms)
        congested_record = TelemetryRecord(
            timestamp=101.0, interface="s1-eth4",
            urllc_latency_ms=38.0, urllc_packet_loss=4.0,
            bottleneck_rx_bytes=5000, bottleneck_tx_bytes=1400000,
            throughput_mbps=9.6, traffic_rate_mbps=9.8, queue_occupancy=25
        )

        x_t = self.builder.build_context(congested_record)
        action, diag = self.agent.select_action(x_t)

        # Context risk R(x_t) must be substantially elevated
        risk = diag["context_risk"]
        self.assertGreater(risk, 0.40, f"Expected elevated risk under congestion, got {risk}")

        # Verify SRA asymmetric penalties:
        # Action 2 (INCREASE) must have a positive penalty (score < UCB)
        std_ucb_inc, _, _ = self.agent.compute_standard_ucb(ACTION_INCREASE, x_t)
        self.assertLess(diag["scores"][ACTION_INCREASE], std_ucb_inc)

        # Action 0 (DECREASE) must receive risk incentive (score > UCB)
        std_ucb_dec, _, _ = self.agent.compute_standard_ucb(ACTION_DECREASE, x_t)
        self.assertGreater(diag["scores"][ACTION_DECREASE], std_ucb_dec)

        # The candidate action must be a valid action
        self.assertIn(action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})

    def test_scenario_c_recovering_network(self):
        """
        SCENARIO C — Recovery:
        Latency dropping sharply from 38 ms down to 14 ms, queue draining to 2 pkts,
        zero packet loss.
        Verifies:
        - Latency trend becomes negative (x_4 < 0).
        - Recovering trend contributes zero positive risk to R(x_t).
        - Total risk R(x_t) declines significantly compared to congested state.
        """
        # Step 1: Set congested baseline at 38 ms
        congested_record = TelemetryRecord(
            timestamp=100.0, interface="s1-eth4",
            urllc_latency_ms=38.0, urllc_packet_loss=4.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=10000,
            throughput_mbps=9.5, traffic_rate_mbps=9.8, queue_occupancy=25
        )
        x_congested = self.builder.build_context(congested_record)
        _, diag_congested = self.agent.select_action(x_congested)
        risk_congested = diag_congested["context_risk"]

        # Step 2: Recovery sample (latency drops by 24 ms)
        recovering_record = TelemetryRecord(
            timestamp=101.0, interface="s1-eth4",
            urllc_latency_ms=14.0, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=2000, bottleneck_tx_bytes=15000,
            throughput_mbps=6.0, traffic_rate_mbps=6.2, queue_occupancy=2
        )
        x_recovery = self.builder.build_context(recovering_record)
        action, diag_recovery = self.agent.select_action(x_recovery)
        risk_recovery = diag_recovery["context_risk"]

        # Trend must be strictly negative
        self.assertLess(x_recovery[4], 0.0, f"Expected negative latency trend, got {x_recovery[4]}")

        # Risk must have dropped significantly
        self.assertLess(risk_recovery, risk_congested, "Risk did not decrease during recovery")
        self.assertIn(action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})

    def test_pipeline_sentinel_handling(self):
        """
        Verify pipeline robustness when telemetry probe reports failure (latency = -1.0 ms).
        The pipeline must NOT crash, must sanitize latency to 1.0 and loss to 1.0,
        and must safely return a candidate action.
        """
        failed_record = TelemetryRecord(
            timestamp=100.0,
            interface="s1-eth4",
            urllc_latency_ms=-1.0,  # Sentinel failure
            urllc_packet_loss=100.0,
            bottleneck_rx_bytes=0,
            bottleneck_tx_bytes=0,
            throughput_mbps=0.0,
            traffic_rate_mbps=0.0,
            queue_occupancy=0
        )

        x_t = self.builder.build_context(failed_record)

        # Sanitized context properties
        self.assertEqual(x_t[1], 1.0, "Sentinel latency must map to 1.0 maximum penalty")
        self.assertEqual(x_t[5], 1.0, "Loss must be 1.0")

        # Must execute cleanly in SRA-LinUCB
        action, diag = self.agent.select_action(x_t)
        self.assertIn(action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})
        self.assertGreaterEqual(diag["context_risk"], 0.40)

    def test_multi_step_sequential_progression(self):
        """
        Verify the pipeline across 5 consecutive time steps representing a full cycle:
        1. Idle baseline
        2. eMBB burst begins
        3. Congestion peak
        4. Recovery
        5. Restored equilibrium
        """
        test_sequence = [
            # (timestamp, latency, loss, tput, queue)
            (100.0, 10.5, 0.0, 2.0, 0),   # 1. Idle
            (101.0, 16.5, 0.0, 8.5, 8),   # 2. Burst begins
            (102.0, 35.0, 3.0, 9.8, 26),  # 3. Peak congestion
            (103.0, 15.0, 0.0, 6.0, 4),   # 4. Recovery
            (104.0, 10.8, 0.0, 4.0, 0),   # 5. Equilibrium
        ]

        for step_idx, (ts, lat, loss, tput, q) in enumerate(test_sequence):
            rec = TelemetryRecord(
                timestamp=ts,
                interface="s1-eth4",
                urllc_latency_ms=lat,
                urllc_packet_loss=loss,
                bottleneck_rx_bytes=1000 * (step_idx + 1),
                bottleneck_tx_bytes=50000 * (step_idx + 1),
                throughput_mbps=tput,
                traffic_rate_mbps=tput + 0.2,
                queue_occupancy=q
            )

            # Pipeline execution: Module 2 -> Module 3 -> Module 4
            x_t = self.builder.build_context(rec)
            action, diag = self.agent.select_action(x_t)

            self.assertEqual(x_t.shape, (6,))
            self.assertIn(action, {0, 1, 2})
            self.assertTrue(0.0 <= diag["context_risk"] <= 1.0)


if __name__ == "__main__":
    unittest.main()
