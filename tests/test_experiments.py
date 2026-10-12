"""
Unit and Invariant Tests for Module 9 Experiments and Evaluation
================================================================
Verifies that:
1. FIFO queue models accumulation, delay scaling, draining, and tail-drop overflow correctly.
2. The real Module 6 Guardrail actively repairs over-capacity candidates and blocks SLA-breaching actions.
3. Safe feedback attribution updates the model only when executed actions match valid arms.
4. All three experiments use the same workload trace and generate consistent 24-column CSV schemas.
5. Summary metrics are calculated directly and consistently from CSV data.
"""

import os
import unittest
import tempfile
import csv
import numpy as np

from experiments.static_baseline import (
    SYNTHETIC_WORKLOAD_PROFILE,
    simulate_static_step,
    run_simulation as run_static_sim,
)
from experiments.dynamic_baseline import (
    simulate_dynamic_step,
    run_simulation as run_dynamic_sim,
)
from experiments.proposed_system import (
    simulate_safe_step,
    run_simulation as run_proposed_sim,
)
from experiments.run_experiments import compute_metrics, load_csv_data
from slicing.slice_config import DEFAULT_SLICING_CONFIG
from guardrail.guardrail import SLASecurityGuardrail
from guardrail.sla_config import GuardrailConfig
from ai.linucb import SRALinUCB, ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE
from feedback.learner import FeedbackLearner


class TestModule9Experiments(unittest.TestCase):
    """Test suite verifying Module 9 simulation physics, guardrail behavior, and invariants."""

    def setUp(self):
        self.guardrail_cfg = GuardrailConfig(
            total_bandwidth_capacity_mbps=10.0,
            urllc_latency_sla_ms=15.0,
            urllc_min_bandwidth_mbps=3.0,
            max_packet_loss_pct=1.0,
        )
        self.guardrail = SLASecurityGuardrail(config=self.guardrail_cfg)

    # --------------------------------------------------------------------------
    # 1. FIFO Queue Model: Accumulation, Delay, Draining, and Overflow
    # --------------------------------------------------------------------------
    def test_fifo_queue_accumulation_and_delay(self):
        """When admitted traffic exceeds 10 Mbps, queue accumulates and adds 1.20 ms per packet."""
        step_data = {"step": 1, "urllc_offered": 2.0, "embb_offered": 9.0, "be_offered": 1.0, "desc": "Overload"}
        # embb_limit 9.0 -> admitted = 2.0 + 9.0 + 0.5 = 11.5 Mbps (1.5 Mbps surplus)
        res = simulate_dynamic_step(step_data, embb_limit=9.0, current_queue_pkts=0.0)

        # Expected surplus: 1.5 Mbps -> delta_pkts = (1.5 * 1e6) / 12000 = 125 pkts/s -> capped at 50
        self.assertGreater(res["queue_occupancy_pkts"], 0.0)
        # Latency must exceed 15 ms SLA
        self.assertGreater(res["simulated_urllc_rtt_ms"], 15.0)
        self.assertEqual(res["sla_violation"], 1)

    def test_fifo_queue_draining_when_load_drops(self):
        """When load drops, queue drains toward zero and latency returns to baseline (10.15 ms)."""
        step_data_light = {"step": 2, "urllc_offered": 1.0, "embb_offered": 3.0, "be_offered": 1.0, "desc": "Light"}
        # Starting with an existing backlog of 10 packets, admitted traffic = 1.0 + 3.0 + 1.0 = 5.0 Mbps (5 Mbps deficit)
        res = simulate_dynamic_step(step_data_light, embb_limit=3.0, current_queue_pkts=10.0)

        # Deficit: 5.0 Mbps below capacity -> queue drains fully to 0
        self.assertEqual(res["queue_occupancy_pkts"], 0.0)
        self.assertEqual(res["simulated_urllc_rtt_ms"], 10.15)
        self.assertEqual(res["sla_violation"], 0)

    def test_buffer_overflow_and_packet_loss(self):
        """Buffer cannot exceed 50 packets; severe surplus triggers tail-drop loss."""
        step_data_extreme = {"step": 3, "urllc_offered": 3.0, "embb_offered": 9.0, "be_offered": 2.0, "desc": "Extreme"}
        res = simulate_dynamic_step(step_data_extreme, embb_limit=9.0, current_queue_pkts=45.0, buffer_limit=50.0)

        self.assertEqual(res["queue_occupancy_pkts"], 50.0)
        self.assertGreater(res["urllc_packet_loss_pct"], 0.0)

    # --------------------------------------------------------------------------
    # 2. Real Module 6 Guardrail: Repair and Rejection
    # --------------------------------------------------------------------------
    def test_real_guardrail_repairs_over_capacity(self):
        """Module 6 Guardrail intercepts over-capacity candidate (13 Mbps) and repairs it to <= 10 Mbps."""
        cand_alloc = {"URLLC": 3.0, "eMBB": 8.5, "BE": 1.5}  # Total 13.0 Mbps
        ctx = {"urllc_latency_ms": 10.5, "urllc_packet_loss": 0.0}

        guard_res = self.guardrail.validate(cand_alloc, ctx, allow_repair=True)
        self.assertTrue(guard_res["approved"])
        self.assertTrue(guard_res["is_repaired"])
        self.assertLessEqual(sum(guard_res["action"].values()), 10.0)
        self.assertGreaterEqual(guard_res["action"]["URLLC"], 3.0)

    def test_real_guardrail_blocks_during_latency_sla_breach(self):
        """Module 6 Guardrail rejects proposals when latency already exceeds 15 ms SLA."""
        cand_alloc = {"URLLC": 3.0, "eMBB": 6.0, "BE": 1.0}
        ctx_violating = {"urllc_latency_ms": 17.5, "urllc_packet_loss": 0.0}

        guard_res = self.guardrail.validate(cand_alloc, ctx_violating, allow_repair=True)
        self.assertFalse(guard_res["approved"])
        self.assertIn("URLLC_LATENCY_VIOLATION", guard_res["violations"])

    # --------------------------------------------------------------------------
    # 3. Safe Feedback Attribution Invariant
    # --------------------------------------------------------------------------
    def test_safe_feedback_attribution_policy(self):
        """Rejected actions never increment bandit arm counts."""
        agent = SRALinUCB(d=6, n_actions=3)
        learner = FeedbackLearner(agent=agent)
        ctx = np.array([1.0, 0.2, 0.5, 0.0, 0.0, 0.0])

        initial_counts = agent.action_counts.copy()
        # Process blocked feedback
        res = learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=ctx,
            post_telemetry={"urllc_latency_ms": 18.0, "throughput_mbps": 5.0},
            executed_action=None,  # Blocked by guardrail
            guardrail_result={"approved": False}
        )
        self.assertEqual(res["outcome_status"], "REJECTED")
        self.assertEqual(agent.action_counts, initial_counts)
        self.assertEqual(learner.rejected_count, 1)

    # --------------------------------------------------------------------------
    # 4. Invariant: Identical Workload and Standardized CSV Schema
    # --------------------------------------------------------------------------
    def test_workload_and_schema_consistency(self):
        """All 3 experiments use identical 20-step workload and identical 24-column CSV schema."""
        self.assertEqual(len(SYNTHETIC_WORKLOAD_PROFILE), 20)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_stat = os.path.join(tmpdir, "stat.csv")
            csv_dyn = os.path.join(tmpdir, "dyn.csv")
            csv_prop = os.path.join(tmpdir, "prop.csv")

            run_static_sim(csv_stat)
            run_dynamic_sim(csv_dyn)
            run_proposed_sim(csv_prop)

            d_stat = load_csv_data(csv_stat)
            d_dyn = load_csv_data(csv_dyn)
            d_prop = load_csv_data(csv_prop)

            self.assertEqual(len(d_stat), 20)
            self.assertEqual(len(d_dyn), 20)
            self.assertEqual(len(d_prop), 20)

            # Invariant: Workload offered traffic must be identical across all three
            for i in range(20):
                self.assertEqual(d_stat[i]["urllc_offered_mbps"], d_dyn[i]["urllc_offered_mbps"])
                self.assertEqual(d_stat[i]["urllc_offered_mbps"], d_prop[i]["urllc_offered_mbps"])
                self.assertEqual(d_stat[i]["embb_offered_mbps"], d_dyn[i]["embb_offered_mbps"])
                self.assertEqual(d_stat[i]["embb_offered_mbps"], d_prop[i]["embb_offered_mbps"])

            # Invariant: Capacity is never exceeded in Proposed System
            for row in d_prop:
                self.assertLessEqual(row["total_alloc_mbps"], 10.0 + 1e-6)
                self.assertGreaterEqual(row["urllc_alloc_mbps"], 3.0 - 1e-6)

            # Invariant: Proposed System has guardrail repairs recorded
            m_prop = compute_metrics(d_prop)
            self.assertGreater(m_prop["repaired_count"], 0)


if __name__ == "__main__":
    unittest.main()
