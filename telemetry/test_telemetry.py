"""
Unit Tests for Module 2: Network Telemetry
=========================================
Tests parsing logic, rate derivations, CSV serialization, and edge cases
without requiring a live Mininet network.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is in the Python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from telemetry.monitor import (
    TelemetryRecord,
    parse_ping_output,
    parse_tc_queue_output,
    calculate_rates,
    log_to_csv,
    NetworkTelemetryCollector,
)


class TestTelemetryCalculations(unittest.TestCase):
    """Tests rate calculations and edge case handling."""

    def test_calculate_rates_normal(self):
        """
        Verify correct Mbps calculation for known byte and time differences.
        1,250,000 bytes over 1.0 second = 10,000,000 bits / 1s = 10.0 Mbps.
        """
        prev_tx = 0
        curr_tx = 1_250_000  # 1.25 MB
        prev_rx = 0
        curr_rx = 625_000    # 0.625 MB (5.0 Mbps)
        delta_t = 1.0

        throughput, total_rate = calculate_rates(
            prev_tx=prev_tx,
            curr_tx=curr_tx,
            prev_rx=prev_rx,
            curr_rx=curr_rx,
            delta_time=delta_t
        )

        self.assertEqual(throughput, 10.0)
        self.assertEqual(total_rate, 15.0)

    def test_calculate_rates_zero_delta_time(self):
        """Verify zero division is safely handled when delta_time <= 0."""
        throughput, total_rate = calculate_rates(
            prev_tx=100, curr_tx=500,
            prev_rx=100, curr_rx=500,
            delta_time=0.0
        )
        self.assertEqual(throughput, 0.0)
        self.assertEqual(total_rate, 0.0)

    def test_calculate_rates_negative_delta_time(self):
        """Verify negative elapsed time safely yields 0.0 Mbps."""
        throughput, total_rate = calculate_rates(
            prev_tx=100, curr_tx=500,
            prev_rx=100, curr_rx=500,
            delta_time=-0.5
        )
        self.assertEqual(throughput, 0.0)
        self.assertEqual(total_rate, 0.0)

    def test_calculate_rates_counter_reset(self):
        """Verify counter wraps or resets (curr < prev) don't produce negative rates."""
        throughput, total_rate = calculate_rates(
            prev_tx=10_000, curr_tx=500,  # Interface rebooted/reset
            prev_rx=10_000, curr_rx=200,
            delta_time=1.0
        )
        self.assertEqual(throughput, 0.0)
        self.assertEqual(total_rate, 0.0)

    def test_calculate_rates_zero_bytes(self):
        """Verify idle network (zero byte delta) produces 0.0 Mbps."""
        throughput, total_rate = calculate_rates(
            prev_tx=5000, curr_tx=5000,
            prev_rx=2000, curr_rx=2000,
            delta_time=2.0
        )
        self.assertEqual(throughput, 0.0)
        self.assertEqual(total_rate, 0.0)


class TestPingParsing(unittest.TestCase):
    """Tests parsing of various Linux ping output formats."""

    def test_parse_ping_successful(self):
        """Verify parsing of standard successful ping output."""
        sample_output = """
        PING 10.0.0.4 (10.0.0.4) 56(84) bytes of data.
        64 bytes from 10.0.0.4: icmp_seq=1 ttl=64 time=12.45 ms

        --- 10.0.0.4 ping statistics ---
        1 packets transmitted, 1 received, 0% packet loss, time 0ms
        rtt min/avg/max/mdev = 12.450/12.450/12.450/0.000 ms
        """
        avg_rtt, loss = parse_ping_output(sample_output)
        self.assertEqual(avg_rtt, 12.450)
        self.assertEqual(loss, 0.0)

    def test_parse_ping_multi_packet_congestion(self):
        """Verify parsing of ping with jitter and multiple packets."""
        sample_output = """
        --- 10.0.0.4 ping statistics ---
        5 packets transmitted, 4 received, 20% packet loss, time 4005ms
        rtt min/avg/max/mdev = 10.091/29.882/122.441/15.221 ms
        """
        avg_rtt, loss = parse_ping_output(sample_output)
        self.assertEqual(avg_rtt, 29.882)
        self.assertEqual(loss, 20.0)

    def test_parse_ping_100_percent_loss(self):
        """Verify that 100% loss returns sentinel -1.0 ms latency."""
        sample_output = """
        --- 10.0.0.4 ping statistics ---
        1 packets transmitted, 0 received, 100% packet loss, time 0ms
        """
        avg_rtt, loss = parse_ping_output(sample_output)
        self.assertEqual(avg_rtt, -1.0)
        self.assertEqual(loss, 100.0)

    def test_parse_ping_destination_unreachable(self):
        """Verify destination unreachable or malformed text returns sentinel."""
        sample_output = "From 10.0.0.1 icmp_seq=1 Destination Host Unreachable"
        avg_rtt, loss = parse_ping_output(sample_output)
        self.assertEqual(avg_rtt, -1.0)
        self.assertEqual(loss, 100.0)

    def test_parse_ping_empty_or_none(self):
        """Verify empty string or None returns sentinel."""
        self.assertEqual(parse_ping_output(""), (-1.0, 100.0))
        self.assertEqual(parse_ping_output(None), (-1.0, 100.0))


class TestQueueParsing(unittest.TestCase):
    """Tests parsing of Linux Traffic Control (tc) queue backlog."""

    def test_parse_tc_queue_backlog_present(self):
        """Verify extraction of packet count from active backlog output."""
        sample_tc = """
        qdisc htb 1: root refcnt 2 r2q 10 default 0 direct_packets_stat 0
         Sent 1048576 bytes 1024 pkt (dropped 12, overlimits 4 requeues 0)
         backlog 4500b 3p requeues 0
        """
        backlog_packets = parse_tc_queue_output(sample_tc)
        self.assertEqual(backlog_packets, 3)

    def test_parse_tc_queue_empty_backlog(self):
        """Verify zero backlog returns 0."""
        sample_tc = """
        qdisc fq_codel 0: dev eth0 root refcnt 2 limit 10240p
         Sent 5000 bytes 45 pkt (dropped 0, overlimits 0 requeues 0)
         backlog 0b 0p requeues 0
        """
        backlog_packets = parse_tc_queue_output(sample_tc)
        self.assertEqual(backlog_packets, 0)

    def test_parse_tc_malformed(self):
        """Verify malformed or empty output returns 0."""
        self.assertEqual(parse_tc_queue_output(""), 0)
        self.assertEqual(parse_tc_queue_output("Cannot find device"), 0)
        self.assertEqual(parse_tc_queue_output(None), 0)


class TestCSVLogging(unittest.TestCase):
    """Tests CSV file creation, header integrity, and record appending."""

    def test_csv_creation_and_appending(self):
        """Verify that CSV logger writes headers once and appends records properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_file = os.path.join(tmpdir, "test_telemetry.csv")

            record1 = TelemetryRecord(
                timestamp=1000.0,
                interface="s1-eth4",
                urllc_latency_ms=12.5,
                urllc_packet_loss=0.0,
                bottleneck_rx_bytes=1000,
                bottleneck_tx_bytes=2000,
                throughput_mbps=1.5,
                traffic_rate_mbps=2.5,
                queue_occupancy=0
            )

            record2 = TelemetryRecord(
                timestamp=1001.0,
                interface="s1-eth4",
                urllc_latency_ms=28.3,
                urllc_packet_loss=0.0,
                bottleneck_rx_bytes=2000,
                bottleneck_tx_bytes=4000,
                throughput_mbps=8.5,
                traffic_rate_mbps=10.5,
                queue_occupancy=4
            )

            # Log record 1 -> should create file and write header + row
            log_to_csv(record1, csv_file)
            self.assertTrue(os.path.exists(csv_file))

            # Log record 2 -> should append row without repeating header
            log_to_csv(record2, csv_file)

            with open(csv_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Header + 2 data rows = 3 lines total
            self.assertEqual(len(lines), 3)

            header = lines[0].strip().split(',')
            self.assertIn("timestamp", header)
            self.assertIn("urllc_latency_ms", header)
            self.assertIn("queue_occupancy", header)
            self.assertIn("throughput_mbps", header)

            row1 = lines[1].strip().split(',')
            self.assertEqual(row1[header.index("interface")], "s1-eth4")
            self.assertEqual(float(row1[header.index("urllc_latency_ms")]), 12.5)


class TestCollectorOrchestration(unittest.TestCase):
    """Tests NetworkTelemetryCollector end-to-end with mocked subsystems."""

    @patch.object(NetworkTelemetryCollector, 'read_port_counters')
    @patch.object(NetworkTelemetryCollector, 'read_queue_occupancy')
    @patch.object(NetworkTelemetryCollector, 'probe_urllc_latency')
    def test_collector_cycle(self, mock_probe, mock_queue, mock_counters):
        """Verify sequential collection cycles derive rates correctly."""
        # Cycle 1: initial values
        mock_counters.return_value = (1_000_000, 2_000_000)
        mock_queue.return_value = 0
        mock_probe.return_value = (11.2, 0.0)

        collector = NetworkTelemetryCollector(interface="s1-eth4")
        rec1 = collector.collect()

        self.assertEqual(rec1.urllc_latency_ms, 11.2)
        self.assertEqual(rec1.queue_occupancy, 0)
        # First sample has no delta, rate should be 0.0
        self.assertEqual(rec1.throughput_mbps, 0.0)

        # Fast forward state to simulate 1.0 second elapsed time and +1.25 MB transmitted
        collector.prev_timestamp = rec1.timestamp - 1.0
        mock_counters.return_value = (1_500_000, 3_250_000)  # +1.25MB TX = 10.0 Mbps
        mock_queue.return_value = 2
        mock_probe.return_value = (24.8, 0.0)

        rec2 = collector.collect()
        self.assertEqual(rec2.urllc_latency_ms, 24.8)
        self.assertEqual(rec2.queue_occupancy, 2)
        # Transmitted 1.25 MB in 1.0s = 10.0 Mbps
        self.assertAlmostEqual(rec2.throughput_mbps, 10.0, delta=0.1)


if __name__ == '__main__':
    unittest.main()
