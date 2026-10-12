"""
Unit Tests for Feedback Learner (Module 8)
"""

import unittest
import numpy as np
from ai.linucb import SRALinUCB, ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE
from feedback.learner import FeedbackLearner, Learner


class TestFeedbackLearner(unittest.TestCase):
    """Test suite verifying feedback processing, model updating, and action attribution."""

    def setUp(self):
        self.agent = SRALinUCB(d=6, n_actions=3)
        self.learner = FeedbackLearner(agent=self.agent)
        self.context = np.array([1.0, 0.2, 0.5, 0.1, 0.0, 0.0], dtype=np.float64)

    def test_approved_action_updates_linucb_matrices(self):
        """Approved action updates A and b matrices for that specific arm."""
        initial_A = self.agent.A[ACTION_INCREASE].copy()
        initial_b = self.agent.b[ACTION_INCREASE].copy()

        post_state = {"urllc_latency_ms": 11.0, "urllc_packet_loss": 0.0, "throughput_mbps": 7.0}
        result = self.learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=self.context,
            post_telemetry=post_state,
            executed_action=ACTION_INCREASE,
            guardrail_result={"approved": True, "is_repaired": False},
        )

        self.assertEqual(result["outcome_status"], "APPROVED_AND_EXECUTED")
        self.assertEqual(result["updated_arm"], ACTION_INCREASE)

        # Verify A matrix updated by outer product: x_t x_t^T
        expected_A = initial_A + np.outer(self.context, self.context)
        np.testing.assert_allclose(self.agent.A[ACTION_INCREASE], expected_A)

        # Verify step counts
        self.assertEqual(self.learner.approved_count, 1)
        self.assertEqual(self.learner.steps, 1)

    def test_rejected_action_does_not_update_linucb(self):
        """Rejected action NEVER updates candidate action's matrices."""
        initial_A = self.agent.A[ACTION_INCREASE].copy()
        initial_b = self.agent.b[ACTION_INCREASE].copy()

        post_state = {"urllc_latency_ms": 16.0, "urllc_packet_loss": 0.0, "throughput_mbps": 4.0}
        result = self.learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=self.context,
            post_telemetry=post_state,
            executed_action=None,  # Guardrail blocked execution
            guardrail_result={"approved": False, "is_repaired": False},
        )

        self.assertEqual(result["outcome_status"], "REJECTED")
        self.assertIsNone(result["updated_arm"])

        # Candidate arm matrices must be completely untouched
        np.testing.assert_allclose(self.agent.A[ACTION_INCREASE], initial_A)
        np.testing.assert_allclose(self.agent.b[ACTION_INCREASE], initial_b)

        # Step count for executed actions must NOT increment
        self.assertEqual(self.learner.steps, 0)
        self.assertEqual(self.learner.rejected_count, 1)

    def test_repaired_action_updates_repaired_arm_only(self):
        """When guardrail repairs candidate action, only the executed arm is updated."""
        initial_A_candidate = self.agent.A[ACTION_INCREASE].copy()
        initial_A_repaired = self.agent.A[ACTION_MAINTAIN].copy()

        post_state = {"urllc_latency_ms": 12.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        result = self.learner.process_feedback(
            candidate_action=ACTION_INCREASE,
            context=self.context,
            post_telemetry=post_state,
            executed_action=ACTION_MAINTAIN,  # Repaired to MAINTAIN
            guardrail_result={"approved": True, "is_repaired": True},
        )

        self.assertEqual(result["outcome_status"], "REPAIRED")
        self.assertEqual(result["updated_arm"], ACTION_MAINTAIN)

        # Candidate arm must be untouched
        np.testing.assert_allclose(self.agent.A[ACTION_INCREASE], initial_A_candidate)

        # Repaired arm must be updated
        expected_A = initial_A_repaired + np.outer(self.context, self.context)
        np.testing.assert_allclose(self.agent.A[ACTION_MAINTAIN], expected_A)
        self.assertEqual(self.learner.repaired_count, 1)

    def test_legacy_learner_class_wrapper(self):
        """Legacy Learner class supports total_reward, steps, and update()."""
        legacy = Learner(agent=self.agent)
        legacy.update("increase_bandwidth", 3.0, self.context)
        self.assertEqual(legacy.steps, 1)
        self.assertEqual(legacy.total_reward, 3.0)
        self.assertEqual(legacy.average_reward(), 3.0)


if __name__ == "__main__":
    unittest.main()