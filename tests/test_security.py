"""Unit tests for Module 5: Security.

Tests Security OFF vs Security ON comparison, overhead calculation formulas,
state representations, and the lightweight WireGuard adapter.
"""

import unittest

from security.security_config import (
    SecurityMode,
    SecurityProtocol,
    SecurityState,
    DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS,
    DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS,
    DEFAULT_SECURITY_RISK_LEVEL,
)
from security.security_metrics import (
    SliceMetrics,
    SecurityOverheadReport,
    WIREGUARD_TRANSPORT_HEADER_BYTES,
    WIREGUARD_DEFAULT_CONFIGURED_MTU,
    calculate_latency_overhead,
    calculate_throughput_penalty,
    calculate_loss_delta,
    compare_security_off_on,
)
from security.wireguard_adapter import WireGuardAdapter


class TestSecurityConfig(unittest.TestCase):
    """Tests for SecurityState and SecurityMode abstractions."""

    def test_security_off_creation(self):
        state = SecurityState.create_off()
        self.assertEqual(state.mode, SecurityMode.OFF)
        self.assertFalse(state.is_enabled)
        self.assertEqual(state.risk_level, 0.0)
        self.assertEqual(state.latency_overhead_ms, 0.0)
        self.assertEqual(state.throughput_penalty_mbps, 0.0)
        self.assertFalse(state.is_measured)

    def test_security_on_default_creation(self):
        state = SecurityState.create_on_default()
        self.assertEqual(state.mode, SecurityMode.ON)
        self.assertTrue(state.is_enabled)
        self.assertEqual(state.protocol, SecurityProtocol.WIREGUARD.value)
        self.assertEqual(state.latency_overhead_ms, DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS)
        self.assertEqual(state.throughput_penalty_mbps, DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS)
        self.assertFalse(state.is_measured, "Configured defaults must not claim to be measured")

    def test_security_on_measured_creation(self):
        state = SecurityState.create_from_measurement(
            latency_overhead_ms=1.45,
            throughput_penalty_mbps=0.62,
            packet_loss_delta_pct=0.01,
            risk_level=0.2,
        )
        self.assertEqual(state.mode, SecurityMode.ON)
        self.assertTrue(state.is_enabled)
        self.assertEqual(state.latency_overhead_ms, 1.45)
        self.assertEqual(state.throughput_penalty_mbps, 0.62)
        self.assertEqual(state.packet_loss_delta_pct, 0.01)
        self.assertTrue(state.is_measured, "Measured factory must set is_measured=True")

    def test_invalid_risk_level(self):
        with self.assertRaises(ValueError):
            SecurityState(risk_level=1.5)
        with self.assertRaises(ValueError):
            SecurityState(risk_level=-0.1)

    def test_negative_overheads_rejected(self):
        with self.assertRaises(ValueError):
            SecurityState(latency_overhead_ms=-1.0)
        with self.assertRaises(ValueError):
            SecurityState(throughput_penalty_mbps=-0.5)


class TestSecurityMetrics(unittest.TestCase):
    """Tests for overhead formulas and comparison reporting."""

    def test_calculate_latency_overhead(self):
        # Base latency = 10 ms, with security = 12 ms -> delta = 2 ms, relative = 20%
        delta, pct = calculate_latency_overhead(10.0, 12.0)
        self.assertAlmostEqual(delta, 2.0)
        self.assertAlmostEqual(pct, 20.0)

    def test_calculate_throughput_penalty(self):
        # Base throughput = 8 Mbps, with security = 7 Mbps -> penalty = 1 Mbps, relative = 12.5%
        delta, pct = calculate_throughput_penalty(8.0, 7.0)
        self.assertAlmostEqual(delta, 1.0)
        self.assertAlmostEqual(pct, 12.5)

    def test_calculate_loss_delta(self):
        delta = calculate_loss_delta(0.1, 0.3)
        self.assertAlmostEqual(delta, 0.2)

    def test_compare_security_off_on_configured(self):
        off = SliceMetrics(latency_ms=8.0, throughput_mbps=9.5, packet_loss_pct=0.0, is_measured=False)
        on = SliceMetrics(latency_ms=9.2, throughput_mbps=9.0, packet_loss_pct=0.0, is_measured=False)

        report = compare_security_off_on(off, on)
        self.assertAlmostEqual(report.latency_overhead_ms, 1.2)
        self.assertAlmostEqual(report.latency_overhead_pct, 15.0)
        self.assertAlmostEqual(report.throughput_penalty_mbps, 0.5)
        self.assertFalse(report.is_measured, "Should be False when inputs are not measured")

    def test_compare_security_off_on_measured(self):
        off = SliceMetrics(latency_ms=10.0, throughput_mbps=8.0, packet_loss_pct=0.05, is_measured=True)
        on = SliceMetrics(latency_ms=11.5, throughput_mbps=7.2, packet_loss_pct=0.08, is_measured=True)

        report = compare_security_off_on(off, on)
        self.assertAlmostEqual(report.latency_overhead_ms, 1.5)
        self.assertAlmostEqual(report.throughput_penalty_mbps, 0.8)
        self.assertAlmostEqual(report.loss_delta_pct, 0.03)
        self.assertTrue(report.is_measured, "Should be True when both inputs are measured")

    def test_protocol_constants_documentation(self):
        self.assertEqual(WIREGUARD_TRANSPORT_HEADER_BYTES, 32)
        self.assertEqual(WIREGUARD_DEFAULT_CONFIGURED_MTU, 1420)


class TestWireGuardAdapter(unittest.TestCase):
    """Tests for lightweight WireGuard adapter and graceful fallback."""

    def test_adapter_graceful_status(self):
        adapter = WireGuardAdapter(interface_name="wg0")
        status = adapter.get_status()
        self.assertIn("available", status)
        self.assertIn("active", status)
        self.assertIn("reason", status)
        # Even if wg is not installed on Windows/host, it must not throw an exception

    def test_adapter_sample_config_generation(self):
        config_text = WireGuardAdapter.generate_sample_config()
        self.assertIn("[Interface]", config_text)
        self.assertIn("[Peer]", config_text)
        self.assertIn("AllowedIPs = 10.0.0.0/24", config_text)


if __name__ == "__main__":
    unittest.main()
