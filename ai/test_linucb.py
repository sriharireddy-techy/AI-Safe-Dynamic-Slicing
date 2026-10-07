"""
Unit Tests for Module 4: SRA-LinUCB
===================================
Tests LinUCB matrix initialization, Ridge Regression updates, UCB calculation,
numerical solve stability, SRA risk adjustments, and action selection dynamics.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.linucb import (
    SRALinUCB,
    ACTION_DECREASE,
    ACTION_MAINTAIN,
    ACTION_INCREASE,
    ACTION_NAMES,
    ACTION_RISK_PROFILES
)


class TestSRALinUCB(unittest.TestCase):
    """Test suite for SRALinUCB (Module 4)."""

    def setUp(self):
        """Create a default SRA-LinUCB agent before each test."""
        self.agent = SRALinUCB(
            d=6,
            n_actions=3,
            alpha=1.0,
            risk_lambda=0.5,
            risk_weights=(0.4, 0.3, 0.2, 0.1)
        )

    def test_initialization(self):
        """Verify matrices A_a are Identity and vectors b_a are Zeros."""
        self.assertEqual(self.agent.d, 6)
        self.assertEqual(self.agent.n_actions, 3)

        for a in range(3):
            # A_a should be 6x6 Identity
            np.testing.assert_array_equal(self.agent.A[a], np.identity(6))
            # b_a should be 6-dim Zeros
            np.testing.assert_array_equal(self.agent.b[a], np.zeros(6))
            # Initial theta_hat should be all zeros
            np.testing.assert_array_equal(self.agent.estimate_theta(a), np.zeros(6))
            self.assertEqual(self.agent.action_counts[a], 0)

    def test_initial_ucb_calculation(self):
        """
        Verify initial UCB calculation on pristine state:
        With A_a = I, b_a = 0:
        mean = x^T 0 = 0.0
        variance = x^T I x = ||x||^2
        bonus = alpha * sqrt(||x||^2) = alpha * ||x||
        """
        ctx = np.array([1.0, 0.2, 0.5, 0.1, 0.0, 0.0], dtype=np.float64)
        norm_x = np.linalg.norm(ctx)

        for a in range(3):
            std_ucb, mean, bonus = self.agent.compute_standard_ucb(a, ctx)
            self.assertEqual(mean, 0.0)
            self.assertAlmostEqual(bonus, norm_x, places=5)
            self.assertAlmostEqual(std_ucb, norm_x, places=5)

    def test_solve_vs_inv_numerical_equivalence(self):
        """
        Verify that np.linalg.solve() produces the mathematically identical
        result as explicit inversion (np.linalg.inv) without the instability.
        """
        ctx = np.array([1.0, 0.5, 0.8, 0.3, 0.2, 0.0])
        # Add some updates to make A non-trivial
        self.agent.update(0, ctx, reward=1.0)

        # Check theta_hat: solve(A, b) vs inv(A) @ b
        theta_solve = self.agent.estimate_theta(0)
        theta_inv = np.linalg.inv(self.agent.A[0]) @ self.agent.b[0]
        np.testing.assert_allclose(theta_solve, theta_inv, rtol=1e-10)

        # Check variance: ctx @ solve(A, ctx) vs ctx @ inv(A) @ ctx
        var_solve = float(ctx @ np.linalg.solve(self.agent.A[0], ctx))
        var_inv = float(ctx @ np.linalg.inv(self.agent.A[0]) @ ctx)
        self.assertAlmostEqual(var_solve, var_inv, places=10)

    def test_context_risk_calculation(self):
        """
        Verify calculation of R(x_t) = w1*x1 + w3*x3 + w4*max(0,x4) + w5*x5:
        w = [0.4, 0.3, 0.2, 0.1]
        x1 (lat) = 0.5   => 0.4 * 0.5 = 0.20
        x3 (queue) = 0.4 => 0.3 * 0.4 = 0.12
        x4 (trend) = 0.5 => 0.2 * 0.5 = 0.10
        x5 (loss) = 0.2  => 0.1 * 0.2 = 0.02
        Expected R(x) = 0.20 + 0.12 + 0.10 + 0.02 = 0.44
        """
        ctx = np.array([1.0, 0.5, 0.9, 0.4, 0.5, 0.2])
        risk = self.agent.compute_context_risk(ctx)
        self.assertAlmostEqual(risk, 0.44, places=5)

    def test_negative_latency_trend_does_not_add_risk(self):
        """Verify that negative latency trend (recovering network) clips to 0 in risk term."""
        ctx = np.array([1.0, 0.2, 0.5, 0.0, -0.8, 0.0])  # trend = -0.8
        # R(x) = 0.4*0.2 + 0.3*0.0 + 0.2*max(0, -0.8) + 0.1*0.0 = 0.08
        risk = self.agent.compute_context_risk(ctx)
        self.assertAlmostEqual(risk, 0.08, places=5)

    def test_sra_risk_adjustments_per_action(self):
        """
        Verify that:
        - Action 2 (INCREASE, rho=+1.0) is penalized by lambda * R(x)
        - Action 0 (DECREASE, rho=-1.0) receives a boost +lambda * R(x)
        - Action 1 (MAINTAIN, rho=0.0) has 0.0 adjustment
        """
        ctx = np.array([1.0, 0.5, 0.8, 0.4, 0.5, 0.0])
        risk = self.agent.compute_context_risk(ctx)
        self.assertGreater(risk, 0.0)

        # Risk adjustment = lambda * rho_a * risk
        adj_dec = self.agent.compute_risk_adjustment(ACTION_DECREASE, ctx)
        adj_maint = self.agent.compute_risk_adjustment(ACTION_MAINTAIN, ctx)
        adj_inc = self.agent.compute_risk_adjustment(ACTION_INCREASE, ctx)

        self.assertAlmostEqual(adj_dec, -0.5 * 1.0 * risk)
        self.assertAlmostEqual(adj_maint, 0.0)
        self.assertAlmostEqual(adj_inc, +0.5 * 1.0 * risk)

    def test_sra_dampens_reckless_increase_under_congestion(self):
        """
        Critical test: In a congested context, verify that SRA-LinUCB suppresses
        Action 2 (INCREASE) and promotes Action 0 (DECREASE).
        """
        # Congested state: Latency high (0.8), Queue high (0.8), Trend rising (+0.6)
        congested_ctx = np.array([1.0, 0.8, 0.95, 0.8, 0.6, 0.05])

        # Standard LinUCB (lambda = 0) treats all arms equally because none have been pulled
        agent_standard = SRALinUCB(risk_lambda=0.0)
        _, diag_std = agent_standard.select_action(congested_ctx)
        # All scores equal in standard LinUCB prior
        self.assertEqual(diag_std["scores"][ACTION_DECREASE], diag_std["scores"][ACTION_INCREASE])

        # SRA-LinUCB (lambda = 0.5) gives Action 0 a higher score than Action 2
        agent_sra = SRALinUCB(risk_lambda=0.5)
        chosen_action, diag_sra = agent_sra.select_action(congested_ctx)

        score_dec = diag_sra["scores"][ACTION_DECREASE]
        score_inc = diag_sra["scores"][ACTION_INCREASE]
        self.assertGreater(score_dec, score_inc)
        self.assertEqual(chosen_action, ACTION_DECREASE)

    def test_update_modifies_only_chosen_arm(self):
        """
        Verify that update() updates ONLY the chosen action's matrices,
        leaving all other arms untouched.
        """
        ctx = np.array([1.0, 0.2, 0.3, 0.1, 0.0, 0.0])
        reward = 5.0

        # Update Action 1 (MAINTAIN)
        self.agent.update(ACTION_MAINTAIN, ctx, reward)

        # Action 1 should be modified
        self.assertFalse(np.array_equal(self.agent.A[ACTION_MAINTAIN], np.identity(6)))
        self.assertFalse(np.array_equal(self.agent.b[ACTION_MAINTAIN], np.zeros(6)))
        self.assertEqual(self.agent.action_counts[ACTION_MAINTAIN], 1)

        # Action 0 and Action 2 must remain in pristine identity/zero state
        np.testing.assert_array_equal(self.agent.A[ACTION_DECREASE], np.identity(6))
        np.testing.assert_array_equal(self.agent.b[ACTION_DECREASE], np.zeros(6))
        self.assertEqual(self.agent.action_counts[ACTION_DECREASE], 0)

        np.testing.assert_array_equal(self.agent.A[ACTION_INCREASE], np.identity(6))
        np.testing.assert_array_equal(self.agent.b[ACTION_INCREASE], np.zeros(6))
        self.assertEqual(self.agent.action_counts[ACTION_INCREASE], 0)

    def test_learning_from_reward_feedback(self):
        """
        Verify that giving high rewards to an action in a specific context
        increases its estimated theta and causes the agent to prefer that action.
        """
        ctx_idle = np.array([1.0, 0.1, 0.2, 0.0, 0.0, 0.0])  # Idle network

        # Train: repeatedly reward Action 2 (INCREASE) in idle state
        for _ in range(10):
            self.agent.update(ACTION_INCREASE, ctx_idle, reward=2.0)
            self.agent.update(ACTION_DECREASE, ctx_idle, reward=-1.0)

        # Now in idle state, Action 2 should have much higher mean estimate than Action 0
        _, diag = self.agent.select_action(ctx_idle)
        self.assertGreater(diag["means"][ACTION_INCREASE], diag["means"][ACTION_DECREASE])
        self.assertEqual(diag["selected_action"], ACTION_INCREASE)

    def test_reset_functionality(self):
        """Verify reset() restores all matrices back to pristine priors."""
        ctx = np.array([1.0, 0.5, 0.5, 0.5, 0.0, 0.0])
        self.agent.update(0, ctx, reward=3.0)
        self.agent.reset()

        for a in range(3):
            np.testing.assert_array_equal(self.agent.A[a], np.identity(6))
            np.testing.assert_array_equal(self.agent.b[a], np.zeros(6))
            self.assertEqual(self.agent.action_counts[a], 0)

    def test_invalid_action_raises_error(self):
        """Verify updating with out-of-range action index raises ValueError."""
        ctx = np.array([1.0, 0.1, 0.1, 0.1, 0.0, 0.0])
        with self.assertRaises(ValueError):
            self.agent.update(5, ctx, reward=1.0)


if __name__ == "__main__":
    unittest.main()
