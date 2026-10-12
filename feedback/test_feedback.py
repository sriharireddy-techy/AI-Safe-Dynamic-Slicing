"""
Integration Tests for Feedback Package (Module 8)
=================================================
Validates full cycle from raw telemetry to reward computation to model update.
"""

import unittest
import numpy as np

from telemetry.monitor import TelemetryRecord
from ai.context_builder import ContextBuilder
from ai.linucb import SRALinUCB, ACTION_DECREASE, ACTION_INCREASE
from feedback.reward import calculate_reward, RewardEngine
from feedback.learner import FeedbackLearner


class TestFeedbackIntegration(unittest.TestCase):
    """End-to-end integration tests for Module 8 feedback loop."""

    def setUp(self):
        self.builder = ContextBuilder()
        self.agent = SRALinUCB(d=6, n_actions=3)
        self.learner = FeedbackLearner(agent=self.agent)

    def test_full_feedback_cycle_healthy_progression(self):
        """Simulate step t -> action selection -> post-action observation -> update."""
        rec_t = TelemetryRecord(
            timestamp=10.0,
            interface="s1-eth4",
            urllc_latency_ms=10.5,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=20000,
            throughput_mbps=4.0,
            traffic_rate_mbps=4.2,
            queue_occupancy=0,
        )
        x_t = self.builder.build_context(rec_t)
        action, _ = self.agent.select_action(x_t)

        # Post-action telemetry at t+1 (network remains healthy)
        rec_next = TelemetryRecord(
            timestamp=11.0,
            interface="s1-eth4",
            urllc_latency_ms=10.8,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=2000,
            bottleneck_tx_bytes=40000,
            throughput_mbps=5.5,
            traffic_rate_mbps=5.7,
            queue_occupancy=0,
        )

        res = self.learner.process_feedback(
            candidate_action=action,
            context=x_t,
            post_telemetry=rec_next,
            executed_action=action,
            guardrail_result={"approved": True, "is_repaired": False},
        )

        self.assertEqual(res["outcome_status"], "APPROVED_AND_EXECUTED")
        self.assertGreater(res["reward"], 0.0)
        self.assertEqual(self.agent.action_counts[action], 1)

    def test_full_feedback_cycle_sla_violation_rejection(self):
        """Simulate candidate action rejected by guardrail during SLA violation."""
        rec_t = TelemetryRecord(
            timestamp=10.0,
            interface="s1-eth4",
            urllc_latency_ms=18.0,  # SLA violated
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=5000,
            bottleneck_tx_bytes=1000000,
            throughput_mbps=9.5,
            traffic_rate_mbps=9.8,
            queue_occupancy=25,
        )
        x_t = self.builder.build_context(rec_t)

        # Candidate wants to increase, but guardrail blocks it
        res = self.learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=x_t,
            post_telemetry=rec_t,
            executed_action=None,
            guardrail_result={"approved": False, "violations": ["URLLC_LATENCY_VIOLATION"]},
        )

        self.assertEqual(res["outcome_status"], "REJECTED")
        self.assertEqual(self.agent.action_counts[ACTION_INCREASE], 0)
        self.assertEqual(self.learner.rejected_count, 1)


if __name__ == "__main__":
    unittest.main()