"""Security configuration and state representations for Module 5.

Distinguishes between configured project default parameters and measured values.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SecurityMode(str, Enum):
    """Operational mode of the network security layer."""
    OFF = "OFF"
    ON = "ON"


class SecurityProtocol(str, Enum):
    """Supported security protocols / mechanisms."""
    NONE = "none"
    WIREGUARD = "wireguard"
    CUSTOM = "custom"


# ==============================================================================
# CONFIGURABLE PROJECT DEFAULTS
# NOTE: The following constants are configured project baseline defaults used
# for simulation, demonstration, and fallback when live testbed measurements
# are not available. They are NOT experimentally measured values.
# ==============================================================================
DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS: float = 1.2
DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS: float = 0.5
DEFAULT_WIREGUARD_LOSS_DELTA_PCT: float = 0.0
DEFAULT_SECURITY_RISK_LEVEL: float = 0.0


@dataclass
class SecurityState:
    """Represents the current security status and overhead profile.

    Attributes:
        mode: SecurityMode.OFF or SecurityMode.ON.
        risk_level: Security threat/risk level in range [0.0, 1.0].
                    0.0 indicates completely safe, 1.0 indicates severe threat.
        protocol: Security protocol identifier ('none', 'wireguard', 'custom').
        latency_overhead_ms: Added processing/crypto latency in milliseconds.
        throughput_penalty_mbps: Throughput reduction in Mbps due to crypto/headers.
        packet_loss_delta_pct: Additional packet loss percentage caused by security.
        is_measured: Boolean flag explicitly stating whether these values were
                     empirically measured from a live network or taken from
                     configured/default profiles.
    """
    mode: SecurityMode = SecurityMode.OFF
    risk_level: float = DEFAULT_SECURITY_RISK_LEVEL
    protocol: str = SecurityProtocol.NONE.value
    latency_overhead_ms: float = 0.0
    throughput_penalty_mbps: float = 0.0
    packet_loss_delta_pct: float = 0.0
    is_measured: bool = False

    def __post_init__(self):
        # Enforce normalized risk bounds
        if not (0.0 <= self.risk_level <= 1.0):
            raise ValueError(f"risk_level must be between 0.0 and 1.0, got {self.risk_level}")
        if self.latency_overhead_ms < 0.0:
            raise ValueError(f"latency_overhead_ms must be non-negative, got {self.latency_overhead_ms}")
        if self.throughput_penalty_mbps < 0.0:
            raise ValueError(f"throughput_penalty_mbps must be non-negative, got {self.throughput_penalty_mbps}")

    @property
    def is_enabled(self) -> bool:
        """Returns True if security is active (ON), False otherwise."""
        return self.mode == SecurityMode.ON

    @classmethod
    def create_off(cls, risk_level: float = 0.0) -> "SecurityState":
        """Factory for a Security OFF state."""
        return cls(
            mode=SecurityMode.OFF,
            risk_level=risk_level,
            protocol=SecurityProtocol.NONE.value,
            latency_overhead_ms=0.0,
            throughput_penalty_mbps=0.0,
            packet_loss_delta_pct=0.0,
            is_measured=False,
        )

    @classmethod
    def create_on_default(
        cls,
        protocol: str = SecurityProtocol.WIREGUARD.value,
        risk_level: float = DEFAULT_SECURITY_RISK_LEVEL,
    ) -> "SecurityState":
        """Factory for a Security ON state using configured project defaults."""
        return cls(
            mode=SecurityMode.ON,
            risk_level=risk_level,
            protocol=protocol,
            latency_overhead_ms=DEFAULT_WIREGUARD_LATENCY_OVERHEAD_MS,
            throughput_penalty_mbps=DEFAULT_WIREGUARD_THROUGHPUT_PENALTY_MBPS,
            packet_loss_delta_pct=DEFAULT_WIREGUARD_LOSS_DELTA_PCT,
            is_measured=False,
        )

    @classmethod
    def create_from_measurement(
        cls,
        latency_overhead_ms: float,
        throughput_penalty_mbps: float,
        packet_loss_delta_pct: float = 0.0,
        risk_level: float = 0.0,
        protocol: str = SecurityProtocol.WIREGUARD.value,
    ) -> "SecurityState":
        """Factory for a Security ON state using real experimental measurements."""
        return cls(
            mode=SecurityMode.ON,
            risk_level=risk_level,
            protocol=protocol,
            latency_overhead_ms=latency_overhead_ms,
            throughput_penalty_mbps=throughput_penalty_mbps,
            packet_loss_delta_pct=packet_loss_delta_pct,
            is_measured=True,
        )
