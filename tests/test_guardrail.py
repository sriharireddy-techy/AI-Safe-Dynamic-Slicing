"""Unit tests for Module 6: SLA/Security Guardrail.

Covers all 10 required test scenarios:
1. latency below SLA -> SAFE
2. latency above SLA -> UNSAFE
3. invalid/over-capacity bandwidth -> UNSAFE
4. acceptable action -> SAFE
5. unknown action -> UNSAFE
6. packet loss above threshold -> UNSAFE
7. security overhead above threshold -> UNSAFE
8. multiple violations -> UNSAFE
9. missing/invalid context -> safely rejected
10. valid safe case -> approved

Plus discrete actions, latency semantics (zero double-counting), and deterministic repair.
"""

import unittest

from guardrail.sla_config import GuardrailConfig
from guardrail.guardrail import (
    DiscreteAction,
    GuardrailViolation,
    SLASecurityGuardrail,
)
from security.security_config import SecurityState


class TestSLASecurityGuardrail(unittest.TestCase):
    """Test suite for SLASecurityGuardrail pre-execution validation."""

    def setUp(self):
        # Explicit test configuration matching project constraints
        # Total link capacity = 10.0 Mbps, URLLC latency SLA = 15.0 ms
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
    # 1. Latency below SLA -> SAFE
    # --------------------------------------------------------------------------
    def test_latency_below_sla_safe(self):
        context = {
            "urllc_latency": 9.5,  # <= 15.0 ms
            "packet_loss": 0.0,
        }
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
        result = self.guardrail.validate(action, context)

        self.assertTrue(result["approved"])
        self.assertIsNotNone(result["action"])
        self.assertEqual(len(result["violations"]), 0)
        self.assertIn("complies with all", result["reason"].lower())

    # --------------------------------------------------------------------------
    # 2. Latency above SLA -> UNSAFE
    # --------------------------------------------------------------------------
    def test_latency_above_sla_unsafe(self):
        context = {
            "urllc_latency": 17.5,  # > 15.0 ms SLA limit
            "packet_loss": 0.0,
        }
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
        result = self.guardrail.validate(action, context)

        self.assertFalse(result["approved"])
        self.assertIsNone(result["action"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, result["violations"])
        self.assertIn("exceeds sla threshold", result["reason"].lower())

    # --------------------------------------------------------------------------
    # 3. Invalid/over-capacity bandwidth -> UNSAFE
    # --------------------------------------------------------------------------
    def test_invalid_over_capacity_bandwidth(self):
        context = {
            "urllc_latency": 10.0,
            "packet_loss": 0.0,
        }
        # Total = 5.0 + 5.0 + 2.0 = 12.0 Mbps (> 10.0 Mbps capacity)
        action = {"URLLC": 5.0, "eMBB": 5.0, "BE": 2.0}
        result = self.guardrail.validate(action, context)

        self.assertFalse(result["approved"])
        self.assertIsNone(result["action"])
        self.assertIn(GuardrailViolation.CAPACITY_EXCEEDED.value, result["violations"])
        self.assertIn("exceeds link capacity", result["reason"].lower())

    # --------------------------------------------------------------------------
    # 4. Acceptable action -> SAFE
    # --------------------------------------------------------------------------
    def test_acceptable_action(self):
        context = {
            "urllc_latency": 8.0,
            "packet_loss": 0.1,
        }
        action = {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0}  # Sum = 10.0, URLLC >= 3.0
        result = self.guardrail.validate(action, context)

        self.assertTrue(result["approved"])
        self.assertEqual(result["action"]["URLLC"], 3.5)
        self.assertEqual(result["action"]["eMBB"], 4.5)
        self.assertEqual(result["action"]["BE"], 2.0)
        self.assertEqual(result["violations"], [])

    # --------------------------------------------------------------------------
    # 5. Unknown action -> UNSAFE
    # --------------------------------------------------------------------------
    def test_unknown_action(self):
        context = {
            "urllc_latency": 10.0,
            "packet_loss": 0.0,
        }
        # Unknown string action
        result = self.guardrail.validate("EXPLODE_TRAFFIC_SLICE", context)
        self.assertFalse(result["approved"])
        self.assertIn(GuardrailViolation.INVALID_ACTION.value, result["violations"])

        # Malformed dictionary with invalid slice keys
        invalid_dict_action = {"VOIP": 4.0, "VIDEO": 4.0, "BE": 2.0}
        result_dict = self.guardrail.validate(invalid_dict_action, context)
        self.assertFalse(result_dict["approved"])
        self.assertIn(GuardrailViolation.INVALID_ACTION.value, result_dict["violations"])

    # --------------------------------------------------------------------------
    # 6. Packet loss above threshold -> UNSAFE
    # --------------------------------------------------------------------------
    def test_packet_loss_above_threshold(self):
        context = {
            "urllc_latency": 10.0,
            "packet_loss": 2.5,  # > 1.0% limit
        }
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
        result = self.guardrail.validate(action, context)

        self.assertFalse(result["approved"])
        self.assertIn(GuardrailViolation.PACKET_LOSS_VIOLATION.value, result["violations"])
        self.assertIn("exceeds sla maximum limit", result["reason"].lower())

    # --------------------------------------------------------------------------
    # 7. Security overhead above threshold -> UNSAFE
    # --------------------------------------------------------------------------
    def test_security_overhead_above_threshold(self):
        context = {
            "urllc_latency": 10.0,
            "packet_loss": 0.0,
        }
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}

        # Case 7A: Overhead exceeds max allowed security overhead threshold (6.0 ms > 5.0 ms)
        sec_state_huge_overhead = SecurityState.create_from_measurement(
            latency_overhead_ms=6.0,
            throughput_penalty_mbps=1.0,
        )
        result_overhead = self.guardrail.validate(action, context, security_state=sec_state_huge_overhead)
        self.assertFalse(result_overhead["approved"])
        self.assertIn(GuardrailViolation.SECURITY_OVERHEAD_EXCEEDED.value, result_overhead["violations"])

        # Case 7B: Baseline latency (12 ms) + overhead (4.0 ms) pushes effective latency to 16.0 ms (> 15 ms SLA)
        sec_state_pushes_over = SecurityState.create_from_measurement(
            latency_overhead_ms=4.0,
            throughput_penalty_mbps=0.5,
        )
        context_borderline = {"urllc_latency": 12.0, "packet_loss": 0.0}
        result_sla = self.guardrail.validate(action, context_borderline, security_state=sec_state_pushes_over)
        self.assertFalse(result_sla["approved"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, result_sla["violations"])

    # --------------------------------------------------------------------------
    # 8. Multiple violations -> UNSAFE
    # --------------------------------------------------------------------------
    def test_multiple_violations(self):
        context = {
            "urllc_latency": 20.0,  # Latency violation
            "packet_loss": 3.0,     # Loss violation
        }
        # Capacity violation (total = 13.0 > 10.0) + URLLC min violation (2.0 < 3.0)
        action = {"URLLC": 2.0, "eMBB": 7.0, "BE": 4.0}
        sec_state = SecurityState.create_on_default(risk_level=0.9)  # Risk violation (> 0.7)

        result = self.guardrail.validate(action, context, security_state=sec_state)

        self.assertFalse(result["approved"])
        self.assertIn(GuardrailViolation.CAPACITY_EXCEEDED.value, result["violations"])
        self.assertIn(GuardrailViolation.URLLC_MIN_BANDWIDTH_VIOLATION.value, result["violations"])
        self.assertIn(GuardrailViolation.URLLC_LATENCY_VIOLATION.value, result["violations"])
        self.assertIn(GuardrailViolation.PACKET_LOSS_VIOLATION.value, result["violations"])
        self.assertIn(GuardrailViolation.SECURITY_RISK_EXCEEDED.value, result["violations"])

    # --------------------------------------------------------------------------
    # 9. Missing/invalid context -> safely rejected
    # --------------------------------------------------------------------------
    def test_missing_or_invalid_context_rejected(self):
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}

        # Context is None
        result_none = self.guardrail.validate(action, None)
        self.assertFalse(result_none["approved"])
        self.assertIn(GuardrailViolation.MISSING_CONTEXT.value, result_none["violations"])

        # Context is not a dictionary
        result_invalid = self.guardrail.validate(action, "invalid_context_type")
        self.assertFalse(result_invalid["approved"])
        self.assertIn(GuardrailViolation.MISSING_CONTEXT.value, result_invalid["violations"])

    # --------------------------------------------------------------------------
    # 10. Valid safe case -> approved
    # --------------------------------------------------------------------------
    def test_valid_safe_case_approved(self):
        context = {
            "urllc_latency": 11.0,
            "packet_loss": 0.05,
        }
        action = {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
        sec_state = SecurityState.create_off()

        result = self.guardrail.validate(action, context, security_state=sec_state)

        self.assertTrue(result["approved"])
        self.assertIsNotNone(result["action"])
        self.assertEqual(result["violations"], [])
        self.assertFalse(result["is_repaired"])
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["effective_urllc_latency_ms"], 11.0)
        self.assertEqual(result["metadata"]["total_allocated_bandwidth_mbps"], 10.0)

    # --------------------------------------------------------------------------
    # Additional: Discrete Actions Support (INCREASE_EMBB, MAINTAIN, DECREASE_EMBB)
    # --------------------------------------------------------------------------
    def test_discrete_actions_handling(self):
        context = {
            "urllc_latency": 9.0,
            "packet_loss": 0.0,
            "current_allocation": {"URLLC": 4.0, "eMBB": 3.0, "BE": 3.0},
        }

        # 1. MAINTAIN preserves current allocation
        res_maintain = self.guardrail.validate(DiscreteAction.MAINTAIN, context)
        self.assertTrue(res_maintain["approved"])
        self.assertEqual(res_maintain["action"]["eMBB"], 3.0)
        self.assertEqual(res_maintain["action"]["BE"], 3.0)

        # 2. INCREASE_EMBB steps eMBB by 1.0 Mbps (from 3.0 to 4.0) and adjusts BE (from 3.0 to 2.0)
        res_inc = self.guardrail.validate(DiscreteAction.INCREASE_EMBB, context)
        self.assertTrue(res_inc["approved"])
        self.assertEqual(res_inc["action"]["eMBB"], 4.0)
        self.assertEqual(res_inc["action"]["BE"], 2.0)

        # 3. DECREASE_EMBB steps eMBB down by 1.0 Mbps (from 3.0 to 2.0) and adjusts BE (from 3.0 to 4.0)
        res_dec = self.guardrail.validate(DiscreteAction.DECREASE_EMBB, context)
        self.assertTrue(res_dec["approved"])
        self.assertEqual(res_dec["action"]["eMBB"], 2.0)
        self.assertEqual(res_dec["action"]["BE"], 4.0)

    # --------------------------------------------------------------------------
    # Additional: Latency Semantics (Zero Double-Counting)
    # --------------------------------------------------------------------------
    def test_latency_semantics_zero_double_counting(self):
        sec_state = SecurityState.create_from_measurement(
            latency_overhead_ms=2.0,
            throughput_penalty_mbps=0.5,
        )
        action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}

        # Case A: context has baseline latency (14.0 ms) and latency_includes_security=False
        # 14.0 ms + 2.0 ms = 16.0 ms > 15.0 ms -> UNSAFE
        ctx_without_sec = {
            "urllc_latency": 14.0,
            "latency_includes_security": False,
        }
        res_a = self.guardrail.validate(action, ctx_without_sec, security_state=sec_state)
        self.assertFalse(res_a["approved"])
        self.assertEqual(res_a["metadata"]["effective_urllc_latency_ms"], 16.0)

        # Case B: context telemetry was already measured with security (14.0 ms total e2e)
        # latency_includes_security=True -> do NOT add 2.0 ms again -> 14.0 ms <= 15.0 ms -> SAFE
        ctx_with_sec = {
            "urllc_latency": 14.0,
            "latency_includes_security": True,
        }
        res_b = self.guardrail.validate(action, ctx_with_sec, security_state=sec_state)
        self.assertTrue(res_b["approved"])
        self.assertEqual(res_b["metadata"]["effective_urllc_latency_ms"], 14.0)
        self.assertEqual(res_b["metadata"]["added_security_overhead_ms"], 0.0)

    # --------------------------------------------------------------------------
    # Additional: Deterministic Repair
    # --------------------------------------------------------------------------
    def test_deterministic_repair_bandwidth_over_allocation(self):
        context = {
            "urllc_latency": 10.0,
            "packet_loss": 0.0,
        }
        # Over-allocation action: URLLC 2.0 (below min 3.0), eMBB 6.0, BE 4.0 -> Total = 12.0
        action = {"URLLC": 2.0, "eMBB": 6.0, "BE": 4.0}

        # Without repair: rejected
        res_no_repair = self.guardrail.validate(action, context, allow_repair=False)
        self.assertFalse(res_no_repair["approved"])

        # With repair: deterministic adjustment
        res_repaired = self.guardrail.validate(action, context, allow_repair=True)
        self.assertTrue(res_repaired["approved"])
        self.assertTrue(res_repaired["is_repaired"])
        self.assertGreaterEqual(res_repaired["action"]["URLLC"], 3.0)
        self.assertLessEqual(sum(res_repaired["action"].values()), 10.0)

    def test_deterministic_repair_cannot_override_bad_network_latency(self):
        # When network latency is already 18 ms, bandwidth repair cannot fix channel latency
        context = {
            "urllc_latency": 18.0,
            "packet_loss": 0.0,
        }
        action = {"URLLC": 5.0, "eMBB": 5.0, "BE": 2.0}
        res = self.guardrail.validate(action, context, allow_repair=True)
        # Must stay rejected
        self.assertFalse(res["approved"])


if __name__ == "__main__":
    unittest.main()
