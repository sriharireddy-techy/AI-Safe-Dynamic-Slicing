"""
End-to-End Pipeline Integration Tests: Module 2 -> Module 3 -> Module 4 -> Module 6
===================================================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Verifies that:
1. Module 2 (Network Telemetry) produces a raw TelemetryRecord.
2. Module 3 (ContextBuilder) transforms it into a normalized 6D context vector.
3. Module 4 (SRA-LinUCB) proposes a candidate resource allocation action.
4. Module 6 (SLASecurityGuardrail) deterministically validates the candidate action
   against physical capacity, URLLC latency SLA (15 ms), packet loss limits (1%),
   and security constraints (Module 5 SecurityState).

Core Architectural Invariant:
Optimization and Safety are separate concerns. Regardless of whether Module 4's
candidate action is safe, aggressive, or exploratory, Module 6 deterministically
enforces hard safety boundaries before any action can reach the SDN controller.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is in python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.monitor import TelemetryRecord
from ai.context_builder import ContextBuilder
from ai.linucb import (
    SRALinUCB,
    ACTION_DECREASE,
    ACTION_MAINTAIN,
    ACTION_INCREASE,
    ACTION_NAMES,
)
from guardrail.sla_config import GuardrailConfig
from guardrail.guardrail import (
    DiscreteAction,
    GuardrailViolation,
    SLASecurityGuardrail,
)
from security.security_config import (
    SecurityMode,
    SecurityProtocol,
    SecurityState,
)


class TestPipelineGuardrailIntegration(unittest.TestCase):
    """End-to-End integration test suite for M2 -> M3 -> M4 -> M6."""

    def setUp(self):
        """Initialize clean instances of each pipeline stage."""
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
        self.config = GuardrailConfig(
            total_bandwidth_capacity_mbps=10.0,
            urllc_latency_sla_ms=15.0,
            urllc_min_bandwidth_mbps=3.0,
            embb_min_bandwidth_mbps=1.0,
            be_min_bandwidth_mbps=0.5,
            max_packet_loss_pct=1.0,
            max_security_risk=0.7,
            max_allowed_security_overhead_ms=5.0,
            discrete_bandwidth_step_mbps=1.0,
        )
        self.guardrail = SLASecurityGuardrail(self.config)

    # --------------------------------------------------------------------------
    # Scenario 1: Healthy Network
    # --------------------------------------------------------------------------
    def test_scenario_1_healthy_network_approved(self):
        """
        Scenario 1:
        - Telemetry reports healthy network (latency 10.2 ms, loss 0%, queue 0).
        - Module 3 produces valid 6D context.
        - Module 4 proposes candidate action.
        - Module 6 validates candidate action against raw telemetry.
        - Verified: Safe candidate action is approved with concrete bandwidth allocation.
        """
        record = TelemetryRecord(
            timestamp=100.0,
            interface="s1-eth4",
            urllc_latency_ms=10.2,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=25000,
            throughput_mbps=2.5,
            traffic_rate_mbps=2.8,
            queue_occupancy=0
        )

        # M2 -> M3
        x_t = self.builder.build_context(record)
        self.assertEqual(x_t.shape, (6,))

        # M3 -> M4
        candidate_action, diag = self.agent.select_action(x_t)
        self.assertIn(candidate_action, {ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE})

        # M4 -> M6 (pass candidate action and Module 2 TelemetryRecord)
        sec_state = SecurityState.create_off()
        decision = self.guardrail.validate(
            candidate_action=candidate_action,
            current_context=record,
            security_state=sec_state
        )

        # M6 Decision Verification
        self.assertTrue(decision["approved"], f"Expected approval, reason: {decision['reason']}")
        self.assertIsNotNone(decision["action"])
        self.assertEqual(decision["violations"], [])
        self.assertFalse(decision["is_repaired"])

        # Check concrete allocation properties
        alloc = decision["action"]
        self.assertGreaterEqual(alloc["URLLC"], self.config.urllc_min_bandwidth_mbps)
        self.assertLessEqual(sum(alloc.values()), self.config.total_bandwidth_capacity_mbps + 1e-6)

    # --------------------------------------------------------------------------
    # Scenario 2: Latency SLA Violation
    # --------------------------------------------------------------------------
    def test_scenario_2_latency_sla_violation_rejected(self):
        """
        Scenario 2:
        - Telemetry reports latency = 18.5 ms (> 15.0 ms SLA limit).
        - Module 6 must reject candidate action regardless of what M4 proposes.
        - Verified: Action is rejected with URLLC_LATENCY_VIOLATION.
        """
        record = TelemetryRecord(
            timestamp=101.0,
            interface="s1-eth4",
            urllc_latency_ms=18.5,  # Breaches 15 ms limit
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=5000,
            bottleneck_tx_bytes=1200000,
            throughput_mbps=9.2,
            traffic_rate_mbps=9.5,
            queue_occupancy=14
        )

        x_t = self.builder.build_context(record)
        candidate_action, _ = self.agent.select_action(x_t)

        decision = self.guardrail.validate(
            candidate_action=candidate_action,
            current_context=record
        )

        self.assertFalse(decision["approved"])
        self.assertIsNone(decision["action"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, decision["violations"])
        self.assertIn("exceeds sla threshold", decision["reason"].lower())

    # --------------------------------------------------------------------------
    # Scenario 3: Packet-Loss SLA Violation
    # --------------------------------------------------------------------------
    def test_scenario_3_packet_loss_sla_violation_rejected(self):
        """
        Scenario 3:
        - Telemetry reports packet loss = 2.5% (> 1.0% limit).
        - Module 6 must reject candidate action.
        - Verified: Action is rejected with PACKET_LOSS_VIOLATION.
        """
        record = TelemetryRecord(
            timestamp=102.0,
            interface="s1-eth4",
            urllc_latency_ms=11.0,  # Latency safe
            urllc_packet_loss=2.5,  # Loss exceeds 1.0% limit
            bottleneck_rx_bytes=2000,
            bottleneck_tx_bytes=500000,
            throughput_mbps=4.0,
            traffic_rate_mbps=4.2,
            queue_occupancy=5
        )

        x_t = self.builder.build_context(record)
        candidate_action, _ = self.agent.select_action(x_t)

        decision = self.guardrail.validate(
            candidate_action=candidate_action,
            current_context=record
        )

        self.assertFalse(decision["approved"])
        self.assertIsNone(decision["action"])
        self.assertIn(GuardrailViolation.PACKET_LOSS_VIOLATION.value, decision["violations"])
        self.assertIn("exceeds sla maximum limit", decision["reason"].lower())

    # --------------------------------------------------------------------------
    # Scenario 4: Severe Congestion — Guardrail Blocks Unsafe INCREASE
    # --------------------------------------------------------------------------
    def test_scenario_4_severe_congestion_blocks_unsafe_increase(self):
        """
        Scenario 4:
        - Network suffers severe congestion: latency 35 ms, loss 3%, queue 26.
        - Even if candidate action is explicitly INCREASE eMBB (Action 2),
          the guardrail deterministically suppresses and blocks it.
        - Verified: INCREASE action is firmly rejected under high latency and loss.
        """
        record = TelemetryRecord(
            timestamp=103.0,
            interface="s1-eth4",
            urllc_latency_ms=35.0,
            urllc_packet_loss=3.0,
            bottleneck_rx_bytes=8000,
            bottleneck_tx_bytes=1400000,
            throughput_mbps=9.8,
            traffic_rate_mbps=10.0,
            queue_occupancy=26
        )

        # Explicitly test candidate INCREASE eMBB (Action 2)
        decision = self.guardrail.validate(
            candidate_action=ACTION_INCREASE,
            current_context=record
        )

        self.assertFalse(decision["approved"])
        self.assertIsNone(decision["action"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, decision["violations"])
        self.assertIn(GuardrailViolation.PACKET_LOSS_VIOLATION.value, decision["violations"])

    # --------------------------------------------------------------------------
    # Scenario 5: Deterministic Repair
    # --------------------------------------------------------------------------
    def test_scenario_5_deterministic_repair_over_allocation(self):
        """
        Scenario 5:
        - Candidate allocation violates bandwidth constraints (total 12 Mbps, URLLC 2 Mbps < 3 Mbps).
        - Environmental channel is healthy (latency 10 ms, loss 0%).
        - allow_repair=True is enabled.
        - Verified: Guardrail repairs allocation so total <= 10 Mbps and URLLC >= 3.0 Mbps.
        """
        healthy_record = TelemetryRecord(
            timestamp=104.0,
            interface="s1-eth4",
            urllc_latency_ms=10.0,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=50000,
            throughput_mbps=2.0,
            traffic_rate_mbps=2.2,
            queue_occupancy=0
        )

        # Bad candidate allocation: URLLC 2.0 (below min 3.0), eMBB 6.0, BE 4.0 -> Total = 12.0 Mbps
        bad_action = {"URLLC": 2.0, "eMBB": 6.0, "BE": 4.0}

        # Validate with repair enabled
        decision = self.guardrail.validate(
            candidate_action=bad_action,
            current_context=healthy_record,
            allow_repair=True
        )

        self.assertTrue(decision["approved"])
        self.assertTrue(decision["is_repaired"])
        self.assertIsNotNone(decision["action"])

        repaired = decision["action"]
        self.assertGreaterEqual(repaired["URLLC"], 3.0, "Repaired URLLC must guarantee minimum reservation")
        self.assertLessEqual(sum(repaired.values()), 10.0 + 1e-6, "Repaired total must not exceed 10 Mbps")

    # --------------------------------------------------------------------------
    # Scenario 6: Security-Risk Enforcement (Module 5 API)
    # --------------------------------------------------------------------------
    def test_scenario_6_security_risk_and_overhead_enforcement(self):
        """
        Scenario 6:
        - Uses Module 5 SecurityState API.
        - Case A: High security threat level (risk_level = 0.85 > max 0.70).
          Guardrail blocks the candidate action with SECURITY_RISK_EXCEEDED.
        - Case B: Excessive security cryptographic latency overhead (6.0 ms > max 5.0 ms).
          Guardrail blocks the candidate action with SECURITY_OVERHEAD_EXCEEDED.
        """
        healthy_record = TelemetryRecord(
            timestamp=105.0,
            interface="s1-eth4",
            urllc_latency_ms=10.0,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=50000,
            throughput_mbps=3.0,
            traffic_rate_mbps=3.2,
            queue_occupancy=0
        )

        # Case A: Elevated security risk level
        sec_state_high_risk = SecurityState.create_on_default(risk_level=0.85)
        decision_risk = self.guardrail.validate(
            candidate_action=ACTION_MAINTAIN,
            current_context=healthy_record,
            security_state=sec_state_high_risk
        )

        self.assertFalse(decision_risk["approved"])
        self.assertIn(GuardrailViolation.SECURITY_RISK_EXCEEDED.value, decision_risk["violations"])
        self.assertIn("security risk level", decision_risk["reason"].lower())

        # Case B: Excessive security processing latency overhead
        sec_state_high_overhead = SecurityState.create_from_measurement(
            latency_overhead_ms=6.0,  # Exceeds max 5.0 ms
            throughput_penalty_mbps=1.0,
            risk_level=0.1
        )
        decision_overhead = self.guardrail.validate(
            candidate_action=ACTION_MAINTAIN,
            current_context=healthy_record,
            security_state=sec_state_high_overhead
        )

        self.assertFalse(decision_overhead["approved"])
        self.assertIn(GuardrailViolation.SECURITY_OVERHEAD_EXCEEDED.value, decision_overhead["violations"])
        self.assertIn("security latency overhead", decision_overhead["reason"].lower())

    # --------------------------------------------------------------------------
    # Scenario 7: Exact Boundary-Value Checks
    # --------------------------------------------------------------------------
    def test_scenario_7_exact_boundary_conditions(self):
        """
        Scenario 7:
        Boundary-value checks against SLA thresholds:
        - Latency: exactly 15.0 ms is approved; 15.05 ms is rejected.
        - Packet loss: exactly 1.0% is approved; 1.05% is rejected.
        - Total capacity: exactly 10.0 Mbps is approved; 10.05 Mbps is rejected.
        """
        # Boundary 1: Latency exactly 15.0 ms
        rec_lat_exact = TelemetryRecord(
            timestamp=106.0, interface="s1-eth4",
            urllc_latency_ms=15.0, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=50000,
            throughput_mbps=3.0, traffic_rate_mbps=3.2, queue_occupancy=0
        )
        res_lat_exact = self.guardrail.validate(ACTION_MAINTAIN, rec_lat_exact)
        self.assertTrue(res_lat_exact["approved"], "Latency exactly 15.0 ms must be approved (at SLA boundary)")

        # Boundary 2: Latency 15.05 ms
        rec_lat_over = TelemetryRecord(
            timestamp=106.1, interface="s1-eth4",
            urllc_latency_ms=15.05, urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=50000,
            throughput_mbps=3.0, traffic_rate_mbps=3.2, queue_occupancy=0
        )
        res_lat_over = self.guardrail.validate(ACTION_MAINTAIN, rec_lat_over)
        self.assertFalse(res_lat_over["approved"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, res_lat_over["violations"])

        # Boundary 3: Loss exactly 1.0%
        rec_loss_exact = TelemetryRecord(
            timestamp=106.2, interface="s1-eth4",
            urllc_latency_ms=10.0, urllc_packet_loss=1.0,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=50000,
            throughput_mbps=3.0, traffic_rate_mbps=3.2, queue_occupancy=0
        )
        res_loss_exact = self.guardrail.validate(ACTION_MAINTAIN, rec_loss_exact)
        self.assertTrue(res_loss_exact["approved"], "Packet loss exactly 1.0% must be approved")

        # Boundary 4: Loss 1.05%
        rec_loss_over = TelemetryRecord(
            timestamp=106.3, interface="s1-eth4",
            urllc_latency_ms=10.0, urllc_packet_loss=1.05,
            bottleneck_rx_bytes=1000, bottleneck_tx_bytes=50000,
            throughput_mbps=3.0, traffic_rate_mbps=3.2, queue_occupancy=0
        )
        res_loss_over = self.guardrail.validate(ACTION_MAINTAIN, rec_loss_over)
        self.assertFalse(res_loss_over["approved"])
        self.assertIn(GuardrailViolation.PACKET_LOSS_VIOLATION.value, res_loss_over["violations"])

        # Boundary 5: Total allocation exactly 10.0 Mbps
        alloc_exact = {"URLLC": 3.0, "eMBB": 4.0, "BE": 3.0}
        res_alloc_exact = self.guardrail.validate(alloc_exact, rec_lat_exact)
        self.assertTrue(res_alloc_exact["approved"], "Total bandwidth exactly 10.0 Mbps must be approved")

        # Boundary 6: Total allocation 10.05 Mbps
        alloc_over = {"URLLC": 3.0, "eMBB": 4.05, "BE": 3.0}
        res_alloc_over = self.guardrail.validate(alloc_over, rec_lat_exact)
        self.assertFalse(res_alloc_over["approved"])
        self.assertIn(GuardrailViolation.CAPACITY_EXCEEDED.value, res_alloc_over["violations"])


if __name__ == "__main__":
    unittest.main()
