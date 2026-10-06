"""Overhead measurement and evaluation formulas for Module 5.

Provides reusable mathematical formulas to quantify the performance overhead
introduced by enabling security mechanisms (e.g., WireGuard encryption).
"""

from dataclasses import dataclass
from typing import Tuple


# ==============================================================================
# CONFIGURED PROTOCOL DEFAULTS (NOT EMPIRICAL MEASUREMENTS)
# Standard WireGuard transport overhead for IPv4 UDP:
# 20 bytes (IPv4) + 8 bytes (UDP) + 4 bytes (WireGuard data packet header) = 32 bytes
# wg-quick default configured MTU on standard 1500-byte Ethernet interfaces: 1420 bytes
# ==============================================================================
WIREGUARD_TRANSPORT_HEADER_BYTES: int = 32
WIREGUARD_DEFAULT_CONFIGURED_MTU: int = 1420


@dataclass
class SliceMetrics:
    """Network performance metrics for a slice or traffic flow.

    Attributes:
        latency_ms: Measured or configured round-trip/one-way latency in milliseconds.
        throughput_mbps: Observed or configured throughput in Megabits per second.
        packet_loss_pct: Observed or configured packet loss percentage (0.0 to 100.0).
        is_measured: Flag indicating if these metrics come from live network measurement.
    """
    latency_ms: float
    throughput_mbps: float
    packet_loss_pct: float = 0.0
    is_measured: bool = False

    def __post_init__(self):
        if self.latency_ms < 0.0:
            raise ValueError(f"latency_ms cannot be negative, got {self.latency_ms}")
        if self.throughput_mbps < 0.0:
            raise ValueError(f"throughput_mbps cannot be negative, got {self.throughput_mbps}")
        if not (0.0 <= self.packet_loss_pct <= 100.0):
            raise ValueError(f"packet_loss_pct must be between 0.0 and 100.0, got {self.packet_loss_pct}")


@dataclass
class SecurityOverheadReport:
    """Comprehensive comparison report between Security OFF and Security ON states.

    Attributes:
        latency_overhead_ms: Absolute added latency in ms (Lat_on - Lat_off).
        latency_overhead_pct: Percentage increase in latency relative to Security OFF.
        throughput_penalty_mbps: Absolute throughput reduction in Mbps (Tput_off - Tput_on).
        throughput_penalty_pct: Percentage degradation in throughput relative to Security OFF.
        loss_delta_pct: Change in packet loss percentage (Loss_on - Loss_off).
        is_measured: True ONLY if both input metric sets were experimentally measured.
    """
    latency_overhead_ms: float
    latency_overhead_pct: float
    throughput_penalty_mbps: float
    throughput_penalty_pct: float
    loss_delta_pct: float
    is_measured: bool = False


def calculate_latency_overhead(lat_off: float, lat_on: float) -> Tuple[float, float]:
    """Computes absolute (ms) and relative (%) latency overhead.

    Formula:
        delta_latency = lat_on - lat_off
        relative_latency_pct = ((lat_on - lat_off) / lat_off) * 100.0

    Args:
        lat_off: Latency with Security OFF (ms).
        lat_on: Latency with Security ON (ms).

    Returns:
        Tuple of (delta_latency_ms, relative_latency_pct).
    """
    delta_ms = lat_on - lat_off
    pct = (delta_ms / lat_off * 100.0) if lat_off > 0.0 else 0.0
    return delta_ms, pct


def calculate_throughput_penalty(tput_off: float, tput_on: float) -> Tuple[float, float]:
    """Computes absolute (Mbps) and relative (%) throughput degradation.

    Formula:
        delta_tput = tput_off - tput_on
        relative_penalty_pct = ((tput_off - tput_on) / tput_off) * 100.0

    Args:
        tput_off: Throughput with Security OFF (Mbps).
        tput_on: Throughput with Security ON (Mbps).

    Returns:
        Tuple of (delta_tput_mbps, relative_penalty_pct).
    """
    delta_mbps = tput_off - tput_on
    pct = (delta_mbps / tput_off * 100.0) if tput_off > 0.0 else 0.0
    return delta_mbps, pct


def calculate_loss_delta(loss_off: float, loss_on: float) -> float:
    """Computes packet loss percentage difference.

    Formula:
        loss_delta = loss_on - loss_off

    Args:
        loss_off: Packet loss percentage with Security OFF.
        loss_on: Packet loss percentage with Security ON.

    Returns:
        Difference in packet loss percentage.
    """
    return loss_on - loss_off


def compare_security_off_on(
    off_metrics: SliceMetrics,
    on_metrics: SliceMetrics,
) -> SecurityOverheadReport:
    """Compares Security OFF vs Security ON metrics and generates an overhead report.

    Args:
        off_metrics: SliceMetrics collected or configured with Security OFF.
        on_metrics: SliceMetrics collected or configured with Security ON.

    Returns:
        SecurityOverheadReport detailing overhead deltas and percentage changes.
    """
    lat_delta_ms, lat_pct = calculate_latency_overhead(
        off_metrics.latency_ms, on_metrics.latency_ms
    )
    tput_delta_mbps, tput_pct = calculate_throughput_penalty(
        off_metrics.throughput_mbps, on_metrics.throughput_mbps
    )
    loss_delta = calculate_loss_delta(
        off_metrics.packet_loss_pct, on_metrics.packet_loss_pct
    )

    # Both must be genuine measurements for the report to claim is_measured = True
    both_measured = bool(off_metrics.is_measured and on_metrics.is_measured)

    return SecurityOverheadReport(
        latency_overhead_ms=lat_delta_ms,
        latency_overhead_pct=lat_pct,
        throughput_penalty_mbps=tput_delta_mbps,
        throughput_penalty_pct=tput_pct,
        loss_delta_pct=loss_delta,
        is_measured=both_measured,
    )
