"""
SRA-LinUCB Module (Module 4)
============================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

This module implements Security- and Risk-Aware LinUCB (SRA-LinUCB) for online
contextual resource allocation in SDN networks.

Mathematical Specification:
---------------------------
Context: x_t in R^6
Actions:
    0: DECREASE eMBB (rho_0 = -1.0)
    1: MAINTAIN      (rho_1 =  0.0)
    2: INCREASE eMBB (rho_2 = +1.0)

Standard LinUCB Components:
    A_a = I_6 + sum_{tau} x_tau x_tau^T
    b_a = sum_{tau} r_tau x_tau
    theta_hat_a = A_a^{-1} b_a  [computed via np.linalg.solve(A_a, b_a)]
    UCB_a = x_t^T theta_hat_a + alpha * sqrt(x_t^T A_a^{-1} x_t)

SRA Modification:
    R(x_t) = w1 * x1 + w3 * x3 + w4 * max(0, x4) + w5 * x5  (Context Risk Indicator)
    Score_a(x_t) = UCB_a(x_t) - lambda * rho_a * R(x_t)
    Candidate Action = argmax_a Score_a(x_t)

Design Principles:
- Numerically stable matrix math using np.linalg.solve() rather than explicit inverses.
- Separation of standard LinUCB from SRA risk penalty.
- Reward calculation is external; update() consumes external scalar reward.
- Deterministic safety validation is deferred to Module 6 guardrails.
"""

from typing import Tuple, Dict, Any, Optional, List
import numpy as np


# Discrete Action Definitions
ACTION_DECREASE: int = 0   # Throttle eMBB allocation to relieve bottleneck congestion
ACTION_MAINTAIN: int = 1   # Hold current allocation steady (avoid control chatter)
ACTION_INCREASE: int = 2   # Expand eMBB allocation to reclaim spare capacity

ACTION_NAMES: Dict[int, str] = {
    ACTION_DECREASE: "DECREASE_EMBB",
    ACTION_MAINTAIN: "MAINTAIN",
    ACTION_INCREASE: "INCREASE_EMBB",
}

# Action physical risk profile on the shared bottleneck link:
# Negative = de-congesting (safe), Zero = neutral, Positive = aggressive (congestion risk)
ACTION_RISK_PROFILES: Dict[int, float] = {
    ACTION_DECREASE: -1.0,
    ACTION_MAINTAIN:  0.0,
    ACTION_INCREASE: +1.0,
}


class SRALinUCB:
    """
    Security- and Risk-Aware Linear Upper Confidence Bound (SRA-LinUCB) agent.
    
    Selects candidate resource allocation actions based on continuous network context
    and adapts its ridge regression estimates online from reward feedback.
    """

    def __init__(
        self,
        d: int = 6,
        n_actions: int = 3,
        alpha: float = 1.0,
        risk_lambda: float = 0.5,
        risk_weights: Optional[Tuple[float, float, float, float]] = None
    ):
        """
        Initialize SRA-LinUCB.
        
        Args:
            d: Context dimension (strictly 6 for this architecture).
            n_actions: Number of discrete allocation actions (strictly 3).
            alpha: Exploration parameter (exploration aggressiveness).
            risk_lambda: Risk-aversion coefficient lambda >= 0.
                         When lambda = 0.0, algorithm behaves as standard LinUCB.
            risk_weights: Tuple of (w1, w3, w4, w5) weights for the context risk indicator.
                          Defaults to (0.4, 0.3, 0.2, 0.1).
        """
        self.d = int(d)
        self.n_actions = int(n_actions)
        self.alpha = float(alpha)
        self.risk_lambda = float(risk_lambda)

        # Risk indicator weights: (latency w1, queue w3, positive trend w4, loss w5)
        self.risk_weights = risk_weights or (0.4, 0.3, 0.2, 0.1)

        # Initialize per-action Ridge Regression matrices
        # A_a = I_d (Identity matrix guarantees positive-definiteness and invertibility)
        self.A: List[np.ndarray] = [
            np.identity(self.d, dtype=np.float64) for _ in range(self.n_actions)
        ]
        # b_a = 0_d (Reward-weighted context accumulation vector)
        self.b: List[np.ndarray] = [
            np.zeros(self.d, dtype=np.float64) for _ in range(self.n_actions)
        ]

        # Action selection counter for empirical tracking
        self.action_counts: List[int] = [0] * self.n_actions

    def reset(self) -> None:
        """Resets all learned matrices and counters back to initial prior states."""
        self.A = [np.identity(self.d, dtype=np.float64) for _ in range(self.n_actions)]
        self.b = [np.zeros(self.d, dtype=np.float64) for _ in range(self.n_actions)]
        self.action_counts = [0] * self.n_actions

    def estimate_theta(self, action: int) -> np.ndarray:
        """
        Computes the ridge regression parameter estimate theta_hat_a = A_a^{-1} b_a.
        
        Uses np.linalg.solve() rather than computing explicit matrix inverse for
        optimal numerical stability and performance.
        
        Args:
            action: Action index (0, 1, or 2).
            
        Returns:
            np.ndarray: Estimated weight vector theta_hat_a of shape (d,).
        """
        return np.linalg.solve(self.A[action], self.b[action])

    def compute_standard_ucb(self, action: int, context: np.ndarray) -> Tuple[float, float, float]:
        """
        Computes standard LinUCB exploitation mean and exploration bonus.
        
        Formula:
            mean = x_t^T theta_hat_a
            uncertainty = alpha * sqrt(x_t^T A_a^{-1} x_t)
            standard_ucb = mean + uncertainty
            
        Args:
            action: Action index.
            context: Context vector x_t of shape (d,).
            
        Returns:
            Tuple of (standard_ucb, estimated_mean, exploration_bonus).
        """
        # 1. Compute theta_hat_a via linear solve: A_a @ theta_hat = b_a
        theta_hat = self.estimate_theta(action)
        mean_estimate = float(context @ theta_hat)

        # 2. Compute x_t^T A_a^{-1} x_t without matrix inversion:
        # Solve A_a @ v = x_t  =>  v = A_a^{-1} x_t
        # Then x_t^T A_a^{-1} x_t = x_t @ v
        v = np.linalg.solve(self.A[action], context)
        variance = float(context @ v)

        # Numerical safety: precision errors can rarely yield tiny negative variance
        variance = max(0.0, variance)
        exploration_bonus = float(self.alpha * np.sqrt(variance))

        standard_ucb = mean_estimate + exploration_bonus
        return standard_ucb, mean_estimate, exploration_bonus

    def compute_context_risk(self, context: np.ndarray) -> float:
        """
        Computes the scalar Context Risk Indicator R(x_t) in [0.0, 1.0].
        
        Formula:
            R(x_t) = w1 * x1 + w3 * x3 + w4 * max(0, x4) + w5 * x5
            
        where:
            x1 = Normalized latency
            x3 = Normalized queue occupancy
            x4 = Latency trend (only positive rising trend adds risk)
            x5 = Packet loss ratio
            
        Args:
            context: Context vector x_t of shape (6,).
            
        Returns:
            float: Scalar risk value bounded in [0.0, 1.0].
        """
        w1, w3, w4, w5 = self.risk_weights

        x1_lat = float(context[1])
        x3_queue = float(context[3])
        x4_trend = float(context[4])
        x5_loss = float(context[5])

        # Rising trend adds risk; recovering trend (negative) does not
        pos_trend = max(0.0, x4_trend)

        raw_risk = (w1 * x1_lat) + (w3 * x3_queue) + (w4 * pos_trend) + (w5 * x5_loss)
        return float(np.clip(raw_risk, 0.0, 1.0))

    def compute_risk_adjustment(self, action: int, context: np.ndarray) -> float:
        """
        Computes the SRA risk penalty or incentive term: lambda * rho_a * R(x_t).
        
        Args:
            action: Action index.
            context: Context vector x_t.
            
        Returns:
            float: Risk adjustment value to subtract from standard UCB.
        """
        rho_a = ACTION_RISK_PROFILES[action]
        risk = self.compute_context_risk(context)
        return float(self.risk_lambda * rho_a * risk)

    def select_action(self, context: np.ndarray) -> Tuple[int, Dict[str, Any]]:
        """
        Selects candidate resource allocation action using SRA-LinUCB scoring:
        
            Score_a(x_t) = Standard_UCB_a(x_t) - lambda * rho_a * R(x_t)
            
        Candidate action is argmax_a Score_a(x_t).
        
        Args:
            context: 1D NumPy array of shape (6,).
            
        Returns:
            Tuple of:
                - candidate_action: Selected action index (0, 1, or 2).
                - diagnostics: Comprehensive dictionary detailing scores, means,
                               bonuses, and risk penalties for explainability.
        """
        # Defensive shape validation
        if not isinstance(context, np.ndarray) or context.shape != (self.d,):
            context = np.asarray(context, dtype=np.float64).reshape(self.d)

        diagnostics: Dict[str, Any] = {
            "context_risk": self.compute_context_risk(context),
            "scores": {},
            "means": {},
            "uncertainties": {},
            "risk_penalties": {},
        }

        best_action: int = ACTION_MAINTAIN
        best_score: float = -float("inf")

        # Evaluate all arms
        for a in range(self.n_actions):
            std_ucb, mean_est, exp_bonus = self.compute_standard_ucb(a, context)
            risk_adj = self.compute_risk_adjustment(a, context)
            total_score = std_ucb - risk_adj

            diagnostics["scores"][a] = round(total_score, 4)
            diagnostics["means"][a] = round(mean_est, 4)
            diagnostics["uncertainties"][a] = round(exp_bonus, 4)
            diagnostics["risk_penalties"][a] = round(risk_adj, 4)

            # Tie-breaking: strictly greater score takes precedence
            if total_score > best_score:
                best_score = total_score
                best_action = a

        diagnostics["selected_action"] = best_action
        diagnostics["selected_action_name"] = ACTION_NAMES[best_action]

        return best_action, diagnostics

    def update(self, action: int, context: np.ndarray, reward: float) -> None:
        """
        Updates Ridge Regression statistics for the chosen arm given external scalar reward.
        
        Update equations:
            A_{a_t} <-- A_{a_t} + x_t x_t^T
            b_{a_t} <-- b_{a_t} + r_t x_t
            
        Args:
            action: Action executed (0, 1, or 2).
            context: Context vector x_t of shape (d,).
            reward: Externally computed scalar performance reward.
        """
        if action < 0 or action >= self.n_actions:
            raise ValueError(f"Invalid action index {action}. Must be in [0, {self.n_actions - 1}].")

        if not isinstance(context, np.ndarray) or context.shape != (self.d,):
            context = np.asarray(context, dtype=np.float64).reshape(self.d)

        # Outer product: x_t x_t^T (6x6 matrix)
        x_outer = np.outer(context, context)

        # Update covariance matrix and reward-weighted context
        self.A[action] += x_outer
        self.b[action] += float(reward) * context

        self.action_counts[action] += 1
