"""Module 5: Security package for AI-Safe Dynamic Slicing.

Provides abstractions for Security OFF vs Security ON comparison,
overhead measurement modeling, protocol constants, and lightweight WireGuard integration.
"""

from security.security_config import (
    SecurityMode,
    SecurityProtocol,
    SecurityState,
    DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS,
    DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS,
    DEFAULT_WIREGUARD_LOSS_DELTA_PCT,
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

__all__ = [
    "SecurityMode",
    "SecurityProtocol",
    "SecurityState",
    "DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS",
    "DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS",
    "DEFAULT_WIREGUARD_LOSS_DELTA_PCT",
    "DEFAULT_SECURITY_RISK_LEVEL",
    "SliceMetrics",
    "SecurityOverheadReport",
    "WIREGUARD_TRANSPORT_HEADER_BYTES",
    "WIREGUARD_DEFAULT_CONFIGURED_MTU",
    "calculate_latency_overhead",
    "calculate_throughput_penalty",
    "calculate_loss_delta",
    "compare_security_off_on",
    "WireGuardAdapter",
]
