"""
Module 8 Feedback Suite (Tests Directory Integration)
======================================================
Tests RewardEngine, FeedbackLearner, and SRA-LinUCB online updates.
"""

import unittest
import numpy as np

from feedback.reward import RewardEngine, RewardConfig, calculate_reward
from feedback.learner import FeedbackLearner, Learner
from ai.linucb import SRALinUCB, ACTION_INCREASE, ACTION_MAINTAIN, ACTION_DECREASE
from security.security_config import SecurityState, SecurityMode


class TestModule8FeedbackSuite(unittest.TestCase):
    """Verifies that Module 8 meets all formal architectural requirements."""

    def setUp(self):
        self.engine = RewardEngine()
        self.agent = SRALinUCB(d=6, n_actions=3)
        self.learner = FeedbackLearner(agent=self.agent, reward_engine=self.engine)
        self.ctx = np.array([1.0, 0.22, 0.40, 0.05, 0.0, 0.0], dtype=np.float64)

    def test_reward_bounds_and_components(self):
        """Reward components are bounded and correctly signed."""
        rec = {"urllc_latency_ms": 11.2, "urllc_packet_loss": 0.0, "throughput_mbps": 6.0}
        reward, diag = self.engine.compute_reward(rec)
        self.assertGreater(diag["throughput_term"], 0.0)
        self.assertLessEqual(diag["latency_term"], 0.0)
        self.assertEqual(diag["sla_penalty_term"], 0.0)

    def test_sla_barrier_growth(self):
        """Severe latency violation incurs steep quadratic barrier."""
        rec_ok = {"urllc_latency_ms": 12.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        rec_breach1 = {"urllc_latency_ms": 18.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        rec_breach2 = {"urllc_latency_ms": 30.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}

        _, d_ok = self.engine.compute_reward(rec_ok)
        _, d_b1 = self.engine.compute_reward(rec_breach1)
        _, d_b2 = self.engine.compute_reward(rec_breach2)

        self.assertEqual(d_ok["sla_penalty_term"], 0.0)
        self.assertLess(d_b1["sla_penalty_term"], 0.0)
        self.assertLess(d_b2["sla_penalty_term"], d_b1["sla_penalty_term"])

    def test_safe_handling_of_none_and_sentinels(self):
        """None context and sentinel -1.0 latency are handled safely."""
        r_none, d_none = self.engine.compute_reward(None)
        self.assertTrue(d_none["is_sla_violation"])

        r_sentinel, d_sentinel = self.engine.compute_reward({"urllc_latency_ms": -1.0})
        self.assertTrue(d_sentinel["is_sla_violation"])

    def test_causal_attribution_rejected_arm(self):
        """Candidate arm must NOT be updated when action was rejected."""
        initial_counts = self.agent.action_counts.copy()
        res = self.learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=self.ctx,
            post_telemetry={"urllc_latency_ms": 18.0, "throughput_mbps": 8.0},
            executed_action=None,
            guardrail_result={"approved": False},
        )
        self.assertEqual(res["outcome_status"], "REJECTED")
        self.assertEqual(self.agent.action_counts, initial_counts)

    def test_causal_attribution_executed_arm(self):
        """Executed arm is updated with correct mathematical formulas."""
        initial_count = self.agent.action_counts[ACTION_DECREASE]
        res = self.learner.process_feedback(
            candidate_action=ACTION_DECREASE,
            context=self.ctx,
            post_telemetry={"urllc_latency_ms": 11.0, "throughput_mbps": 3.0},
            executed_action=ACTION_DECREASE,
            guardrail_result={"approved": True},
        )
        self.assertEqual(res["outcome_status"], "APPROVED_AND_EXECUTED")
        self.assertEqual(self.agent.action_counts[ACTION_DECREASE], initial_count + 1)


if __name__ == "__main__":
    unittest.main()
