"""
Unit Tests for Module 3: Context & Feature Extraction
=====================================================
Tests ContextBuilder normalization, trend derivation, sentinel sanitization,
output dimensions, and bound guarantees.
"""

import os
import sys
import unittest
import numpy as np

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.monitor import TelemetryRecord
from ai.context_builder import ContextBuilder


class TestContextBuilder(unittest.TestCase):
    """Test suite for ContextBuilder (Module 3)."""

    def setUp(self):
        """Create a fresh ContextBuilder instance before every test."""
        self.builder = ContextBuilder(
            max_latency=50.0,
            max_throughput=10.0,
            max_queue=50.0
        )

    def test_output_type_and_shape(self):
        """Verify output is a 1D NumPy array with exactly shape (6,) and float64 dtype."""
        record = TelemetryRecord(
            timestamp=100.0,
            interface="s1-eth4",
            urllc_latency_ms=10.0,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=1000,
            bottleneck_tx_bytes=2000,
            throughput_mbps=5.0,
            traffic_rate_mbps=8.0,
            queue_occupancy=5
        )
        ctx = self.builder.build_context(record)

        self.assertIsInstance(ctx, np.ndarray)
        self.assertEqual(ctx.shape, (6,))
        self.assertEqual(ctx.dtype, np.float64)

    def test_bias_term(self):
        """Verify feature x_0 is strictly 1.0."""
        ctx = self.builder.build_context({"urllc_latency_ms": 10.0})
        self.assertEqual(ctx[0], 1.0)

    def test_normal_latency_normalization(self):
        """
        Verify latency normalization:
        10.0 ms / 50.0 ms ceiling = 0.2
        25.0 ms / 50.0 ms ceiling = 0.5
        """
        ctx1 = self.builder.build_context({"urllc_latency_ms": 10.0})
        self.assertAlmostEqual(ctx1[1], 0.20, places=4)

        ctx2 = self.builder.build_context({"urllc_latency_ms": 25.0})
        self.assertAlmostEqual(ctx2[1], 0.50, places=4)

    def test_normal_throughput_normalization(self):
        """
        Verify throughput normalization:
        5.0 Mbps / 10.0 Mbps = 0.5
        9.0 Mbps / 10.0 Mbps = 0.9
        """
        ctx = self.builder.build_context({
            "urllc_latency_ms": 10.0,
            "throughput_mbps": 9.0
        })
        self.assertAlmostEqual(ctx[2], 0.90, places=4)

    def test_normal_queue_normalization(self):
        """
        Verify queue normalization:
        10 packets / 50.0 = 0.20
        """
        ctx = self.builder.build_context({
            "urllc_latency_ms": 10.0,
            "queue_occupancy": 10
        })
        self.assertAlmostEqual(ctx[3], 0.20, places=4)

    def test_packet_loss_normalization(self):
        """
        Verify packet loss ratio:
        0.0% -> 0.0
        5.0% -> 0.05
        100.0% -> 1.0
        """
        ctx1 = self.builder.build_context({
            "urllc_latency_ms": 10.0,
            "urllc_packet_loss": 5.0
        })
        self.assertAlmostEqual(ctx1[5], 0.05, places=4)

    def test_values_above_ceiling_clipped_to_one(self):
        """Verify inputs exceeding maximum normalization ceilings clip cleanly to 1.0."""
        ctx = self.builder.build_context({
            "urllc_latency_ms": 120.0,    # Above 50 ms
            "throughput_mbps": 15.0,      # Above 10 Mbps
            "queue_occupancy": 150,       # Above 50 pkts
            "urllc_packet_loss": 120.0    # Malformed / above 100%
        })
        self.assertEqual(ctx[1], 1.0)
        self.assertEqual(ctx[2], 1.0)
        self.assertEqual(ctx[3], 1.0)
        self.assertEqual(ctx[5], 1.0)

    def test_sentinel_latency_handling(self):
        """
        Verify that unreachable sentinel (-1.0) is sanitized:
        - normalized latency becomes 1.0 (maximum penalty)
        - packet loss becomes 1.0 (100% loss)
        - NEVER produces negative values in x_t!
        """
        ctx = self.builder.build_context({
            "urllc_latency_ms": -1.0,
            "urllc_packet_loss": 100.0
        })
        self.assertEqual(ctx[1], 1.0)
        self.assertEqual(ctx[5], 1.0)
        self.assertGreaterEqual(ctx[1], 0.0)

    def test_first_sample_trend_zero(self):
        """Verify the first sample has trend x_4 = 0.0 since no predecessor exists."""
        ctx = self.builder.build_context({"urllc_latency_ms": 15.0})
        self.assertEqual(ctx[4], 0.0)

    def test_positive_latency_trend(self):
        """
        Verify positive latency trend (worsening congestion):
        t1: 10.0 ms
        t2: 15.0 ms -> delta = +5.0 ms -> x_4 = +5.0 / 10.0 = +0.50
        """
        self.builder.build_context({"urllc_latency_ms": 10.0})
        ctx2 = self.builder.build_context({"urllc_latency_ms": 15.0})
        self.assertAlmostEqual(ctx2[4], 0.50, places=4)

    def test_negative_latency_trend(self):
        """
        Verify negative latency trend (recovering network):
        t1: 30.0 ms
        t2: 20.0 ms -> delta = -10.0 ms -> x_4 = -10.0 / 10.0 = -1.0
        """
        self.builder.build_context({"urllc_latency_ms": 30.0})
        ctx2 = self.builder.build_context({"urllc_latency_ms": 20.0})
        self.assertAlmostEqual(ctx2[4], -1.0, places=4)

    def test_zero_latency_trend(self):
        """
        Verify zero latency trend (stable network):
        t1: 12.0 ms
        t2: 12.0 ms -> delta = 0.0 -> x_4 = 0.0
        """
        self.builder.build_context({"urllc_latency_ms": 12.0})
        ctx2 = self.builder.build_context({"urllc_latency_ms": 12.0})
        self.assertAlmostEqual(ctx2[4], 0.0, places=4)

    def test_trend_clipping_bounds(self):
        """
        Verify massive latency surge or drop clips to [-1.0, 1.0]:
        t1: 10.0 ms
        t2: 100.0 ms -> delta = +90.0 ms -> clips to +1.0
        """
        self.builder.build_context({"urllc_latency_ms": 10.0})
        ctx2 = self.builder.build_context({"urllc_latency_ms": 100.0})
        self.assertEqual(ctx2[4], 1.0)

    def test_consecutive_state_tracking(self):
        """Verify sequential samples update previous latency properly across 3 steps."""
        ctx1 = self.builder.build_context({"urllc_latency_ms": 10.0})
        self.assertEqual(ctx1[4], 0.0)

        ctx2 = self.builder.build_context({"urllc_latency_ms": 14.0})
        self.assertAlmostEqual(ctx2[4], 0.4, places=4)

        ctx3 = self.builder.build_context({"urllc_latency_ms": 11.0})
        self.assertAlmostEqual(ctx3[4], -0.3, places=4)

    def test_reset_method(self):
        """Verify reset() clears historical state for subsequent runs."""
        self.builder.build_context({"urllc_latency_ms": 10.0})
        self.builder.reset()
        ctx = self.builder.build_context({"urllc_latency_ms": 20.0})
        # After reset, this sample acts as the first sample (trend = 0.0)
        self.assertEqual(ctx[4], 0.0)

    def test_compatibility_with_telemetry_record_object(self):
        """Verify ContextBuilder accepts real TelemetryRecord dataclass objects."""
        record = TelemetryRecord(
            timestamp=12345.67,
            interface="s1-eth4",
            urllc_latency_ms=11.2,
            urllc_packet_loss=0.0,
            bottleneck_rx_bytes=50000,
            bottleneck_tx_bytes=100000,
            throughput_mbps=7.5,
            traffic_rate_mbps=9.2,
            queue_occupancy=4
        )
        ctx = self.builder.build_context(record)
        self.assertEqual(len(ctx), 6)
        self.assertEqual(ctx[0], 1.0)
        self.assertAlmostEqual(ctx[1], 11.2 / 50.0, places=4)
        self.assertAlmostEqual(ctx[2], 7.5 / 10.0, places=4)
        self.assertAlmostEqual(ctx[3], 4.0 / 50.0, places=4)
        self.assertEqual(ctx[4], 0.0)
        self.assertEqual(ctx[5], 0.0)

    def test_defensive_against_missing_or_malformed_keys(self):
        """Verify empty dictionary or malformed fields safely yield valid numbers."""
        ctx = self.builder.build_context({})
        self.assertEqual(ctx.shape, (6,))
        self.assertFalse(np.isnan(ctx).any())
        self.assertFalse(np.isinf(ctx).any())


if __name__ == "__main__":
    unittest.main()
