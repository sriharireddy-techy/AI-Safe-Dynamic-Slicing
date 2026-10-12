"""
Feedback Learner and Model Updater (Module 8)
==============================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Connects network consequences and reward signals back to the SRA-LinUCB bandit.

Core Invariants:
----------------
1. Correct Causal Attribution:
   - An action proposed by AI can be APPROVED, REJECTED, or REPAIRED by the SLA Guardrail.
   - If an action was REJECTED: It was NEVER executed on the OpenFlow switches.
     The post-action network state was NOT caused by the candidate action.
     Therefore, the model MUST NOT update the candidate action's statistics.
   - If an action was REPAIRED: The executed action was the repaired action, NOT the candidate.
     The model updates statistics for the REPAIRED action that actually ran on the switches.
   - If an action was APPROVED: The candidate action was executed; model updates normally.

2. Integration with SRA-LinUCB:
   Calls the official SRALinUCB.update(action, context, reward) method, which performs
   the closed-form Ridge Regression covariance updates:
       A_{a_t} <-- A_{a_t} + x_t x_t^T
       b_{a_t} <-- b_{a_t} + r_t x_t
"""

from typing import Optional, Dict, Any, Union, Tuple
import numpy as np

from ai.linucb import SRALinUCB, ACTION_NAMES
from feedback.reward import RewardEngine, DEFAULT_REWARD_ENGINE


class FeedbackLearner:
    """
    Manages the closed-loop feedback cycle and ensures valid causal model updates.
    """

    def __init__(
        self,
        agent: Optional[SRALinUCB] = None,
        reward_engine: Optional[RewardEngine] = None
    ):
        """
        Args:
            agent: Instance of SRALinUCB (or creates default if None).
            reward_engine: Instance of RewardEngine.
        """
        self.agent = agent or SRALinUCB(d=6, n_actions=3)
        self.reward_engine = reward_engine or DEFAULT_REWARD_ENGINE

        # Performance and history tracking
        self.steps: int = 0
        self.total_reward: float = 0.0
        self.approved_count: int = 0
        self.rejected_count: int = 0
        self.repaired_count: int = 0
        self.history = []

    @property
    def average_reward(self) -> float:
        """Returns mean reward over executed steps."""
        if self.steps == 0:
            return 0.0
        return self.total_reward / self.steps

    def process_feedback(
        self,
        candidate_action: int,
        context: np.ndarray,
        post_telemetry: Union[Dict[str, Any], Any],
        executed_action: Optional[int] = None,
        guardrail_result: Optional[Dict[str, Any]] = None,
        security_state: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Processes feedback from network telemetry and conditionally updates the AI model.

        Args:
            candidate_action: Action index proposed by AI bandit (0, 1, or 2).
            context: 6D context vector x_t used when selecting the candidate action.
            post_telemetry: Network state observed after action execution.
            executed_action: Action actually applied to the switches (None if rejected).
            guardrail_result: Optional validation dictionary from Module 6 Guardrail.
            security_state: Optional SecurityState from Module 5.

        Returns:
            Dictionary with execution status, reward, and diagnostics.
        """
        # Determine execution outcome from guardrail or explicit arguments
        is_approved = True
        is_repaired = False
        actual_action = executed_action

        if guardrail_result is not None:
            is_approved = bool(guardrail_result.get("approved", True))
            is_repaired = bool(guardrail_result.get("is_repaired", False))
            if not is_approved:
                actual_action = None

        if actual_action is None and is_approved:
            actual_action = candidate_action

        # Compute performance reward from observed telemetry
        reward, diag = self.reward_engine.compute_reward(
            telemetry=post_telemetry,
            security_state=security_state
        )

        outcome_status = "UNKNOWN"
        updated_arm: Optional[int] = None

        if actual_action is None:
            # -------------------------------------------------------------
            # CASE 1: REJECTED ACTION
            # Action was blocked by guardrail; do NOT attribute state to candidate
            # -------------------------------------------------------------
            outcome_status = "REJECTED"
            self.rejected_count += 1
            updated_arm = None

        elif is_repaired or (actual_action != candidate_action):
            # -------------------------------------------------------------
            # CASE 2: REPAIRED ACTION
            # Action was modified by guardrail; update the REPAIRED arm
            # -------------------------------------------------------------
            outcome_status = "REPAIRED"
            self.repaired_count += 1
            self.steps += 1
            self.total_reward += reward
            self.agent.update(actual_action, context, reward)
            updated_arm = actual_action

        else:
            # -------------------------------------------------------------
            # CASE 3: APPROVED ACTION
            # Action was approved and executed; update candidate arm
            # -------------------------------------------------------------
            outcome_status = "APPROVED_AND_EXECUTED"
            self.approved_count += 1
            self.steps += 1
            self.total_reward += reward
            self.agent.update(candidate_action, context, reward)
            updated_arm = candidate_action

        record = {
            "step": self.steps,
            "candidate_action": candidate_action,
            "candidate_name": ACTION_NAMES.get(candidate_action, "UNKNOWN"),
            "executed_action": actual_action,
            "executed_name": ACTION_NAMES.get(actual_action, "NONE") if actual_action is not None else "NONE",
            "outcome_status": outcome_status,
            "updated_arm": updated_arm,
            "reward": round(reward, 4),
            "diagnostics": diag,
        }

        self.history.append(record)
        return record


class Learner:
    """
    Backwards-compatible interface matching the teammate's original Learner signature,
    now backed by a real SRA-LinUCB model and reward calculation.
    """

    def __init__(self, agent: Optional[SRALinUCB] = None):
        self._feedback_learner = FeedbackLearner(agent=agent)

    @property
    def total_reward(self) -> float:
        return self._feedback_learner.total_reward

    @property
    def steps(self) -> int:
        return self._feedback_learner.steps

    def average_reward(self) -> float:
        return self._feedback_learner.average_reward

    def update(
        self,
        action: Any,
        reward: float,
        context: Optional[Any] = None
    ) -> None:
        """
        Updates internal metrics and passes update to SRALinUCB if valid context is provided.
        """
        # Map string action or int to integer index
        action_idx = 1  # Default MAINTAIN
        if isinstance(action, int):
            action_idx = action
        elif isinstance(action, str):
            from ai.linucb import ACTION_DECREASE, ACTION_MAINTAIN, ACTION_INCREASE
            mapping = {
                "decrease": ACTION_DECREASE,
                "decrease_embb": ACTION_DECREASE,
                "maintain": ACTION_MAINTAIN,
                "increase": ACTION_INCREASE,
                "increase_embb": ACTION_INCREASE,
                "increase_bandwidth": ACTION_INCREASE,
            }
            action_idx = mapping.get(action.lower().strip(), ACTION_MAINTAIN)

        # Context vector handling
        if isinstance(context, np.ndarray) and context.shape == (self._feedback_learner.agent.d,):
            ctx_vec = context
        else:
            # Fallback zero vector if no valid context passed
            ctx_vec = np.zeros(self._feedback_learner.agent.d, dtype=np.float64)
            ctx_vec[0] = 1.0  # bias

        self._feedback_learner.steps += 1
        self._feedback_learner.total_reward += reward
        self._feedback_learner.agent.update(action_idx, ctx_vec, reward)