"""
Unit Tests for Reward Engine (Module 8)
"""

import unittest
from feedback.reward import (
    RewardConfig,
    RewardEngine,
    calculate_reward,
    DEFAULT_REWARD_ENGINE,
)
from telemetry.monitor import TelemetryRecord
from security.security_config import SecurityState, SecurityMode


class TestRewardEngine(unittest.TestCase):
    """Test suite verifying reward calculation, normalization, and barrier penalties."""

    def setUp(self):
        self.engine = RewardEngine()

    def test_healthy_network_positive_reward(self):
        """Healthy network within SLA (10.4 ms, 0% loss, 8 Mbps) produces positive reward."""
        record = TelemetryRecord(
            timestamp=100.0,
            interface="s1-eth4",
            urllc_latency_ms=10.4,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=25000,
            throughput_mbps=8.0,
            traffic_rate_mbps=8.2,
            queue_occupancy=0,
        )
        reward, diag = self.engine.compute_reward(record)
        self.assertGreater(reward, 0.0)
        self.assertFalse(diag["is_sla_violation"])
        self.assertEqual(diag["sla_penalty_term"], 0.0)

    def test_latency_sla_violation_triggers_barrier(self):
        """Latency > 15.0 ms triggers SLA violation barrier penalty."""
        violating_record = {
            "urllc_latency_ms": 20.0,  # 5 ms above SLA
            "urllc_packet_loss": 0.0,
            "throughput_mbps": 8.0,
        }
        reward, diag = self.engine.compute_reward(violating_record)
        self.assertTrue(diag["is_sla_violation"])
        self.assertLess(diag["sla_penalty_term"], 0.0)

    def test_quadratic_penalty_growth(self):
        """Higher latency violation yields quadratically steeper penalty."""
        rec_mild = {"urllc_latency_ms": 16.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        rec_severe = {"urllc_latency_ms": 30.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}

        _, diag_mild = self.engine.compute_reward(rec_mild)
        _, diag_severe = self.engine.compute_reward(rec_severe)

        # Penalty term is negative in diagnostics; severe must be significantly more negative
        self.assertLess(diag_severe["sla_penalty_term"], diag_mild["sla_penalty_term"])

    def test_sentinel_dropped_probe_handling(self):
        """Sentinel latency -1.0 ms (dropped probe) safely triggers maximum SLA penalty without crashing."""
        dropped_record = {
            "urllc_latency_ms": -1.0,
            "urllc_packet_loss": 100.0,
            "throughput_mbps": 0.0,
        }
        reward, diag = self.engine.compute_reward(dropped_record)
        self.assertTrue(diag["is_sla_violation"])
        self.assertLess(reward, -5.0)

    def test_missing_or_corrupted_fields_graceful_handling(self):
        """Corrupted or missing telemetry fields do not raise exceptions."""
        corrupted = {"urllc_latency_ms": "invalid", "packet_loss": None}
        reward, diag = self.engine.compute_reward(corrupted)
        self.assertIsInstance(reward, float)

    def test_unmeasured_security_does_not_fabricate_penalty(self):
        """Security state with is_measured=False does not inject fake overhead penalty."""
        unmeasured_sec = SecurityState(
            mode=SecurityMode.ON,
            latency_overhead_ms=3.5,
            is_measured=False,  # Unverified default
        )
        rec = {"urllc_latency_ms": 11.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        _, diag = self.engine.compute_reward(rec, security_state=unmeasured_sec)
        self.assertFalse(diag["security_measured"])
        self.assertEqual(diag["security_overhead_term"], 0.0)

    def test_measured_security_applies_penalty(self):
        """Security state with is_measured=True applies measured overhead penalty."""
        measured_sec = SecurityState(
            mode=SecurityMode.ON,
            latency_overhead_ms=2.5,
            is_measured=True,
        )
        rec = {"urllc_latency_ms": 11.0, "urllc_packet_loss": 0.0, "throughput_mbps": 5.0}
        _, diag = self.engine.compute_reward(rec, security_state=measured_sec)
        self.assertTrue(diag["security_measured"])
        self.assertLess(diag["security_overhead_term"], 0.0)

    def test_backwards_compatible_calculate_reward(self):
        """calculate_reward legacy function returns a float."""
        prev = {"urllc_latency": 12.0, "embb_throughput": 5.0, "packet_loss": 0.0}
        nxt = {"urllc_latency": 11.0, "embb_throughput": 6.0, "packet_loss": 0.0}
        r = calculate_reward(prev, None, nxt)
        self.assertIsInstance(r, float)


if __name__ == "__main__":
    unittest.main()