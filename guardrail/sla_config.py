"""SLA and security thresholds configuration for Module 6 Guardrail.

Clearly separates stated project constraints (e.g., 10 Mbps topology bottleneck,
15 ms URLLC latency SLA) from configurable project defaults used for evaluation.
"""

from dataclasses import dataclass


@dataclass
class GuardrailConfig:
    """Configuration defining SLA limits, capacity, and security bounds.

    STATED PROJECT CONSTRAINTS:
        total_bandwidth_capacity_mbps: Total bottleneck link capacity (10 Mbps).
        urllc_latency_sla_ms: Strict upper bound on URLLC round-trip/e2e latency (15 ms).

    CONFIGURABLE PROJECT DEFAULTS:
        The following parameters are configurable project defaults for testing
        and development, not experimentally mandated constants.
    """

    # --- Stated Project Constraints ---
    total_bandwidth_capacity_mbps: float = 10.0
    urllc_latency_sla_ms: float = 15.0

    # --- Configurable Project Defaults ---
    urllc_min_bandwidth_mbps: float = 3.0
    embb_min_bandwidth_mbps: float = 1.0
    be_min_bandwidth_mbps: float = 0.5

    max_packet_loss_pct: float = 1.0
    max_security_risk: float = 0.7
    max_allowed_security_overhead_ms: float = 5.0

    discrete_bandwidth_step_mbps: float = 1.0

    def __post_init__(self):
        if self.total_bandwidth_capacity_mbps <= 0.0:
            raise ValueError("total_bandwidth_capacity_mbps must be positive")
        if self.urllc_latency_sla_ms <= 0.0:
            raise ValueError("urllc_latency_sla_ms must be positive")
        if self.urllc_min_bandwidth_mbps < 0.0:
            raise ValueError("urllc_min_bandwidth_mbps cannot be negative")
        if self.urllc_min_bandwidth_mbps > self.total_bandwidth_capacity_mbps:
            raise ValueError("urllc_min_bandwidth_mbps cannot exceed total capacity")
        if not (0.0 <= self.max_security_risk <= 1.0):
            raise ValueError("max_security_risk must be between 0.0 and 1.0")
        if not (0.0 <= self.max_packet_loss_pct <= 100.0):
            raise ValueError("max_packet_loss_pct must be between 0.0 and 100.0")
