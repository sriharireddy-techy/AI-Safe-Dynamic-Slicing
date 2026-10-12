"""
Closed-Loop Reward Engine for AI-Safe Dynamic Network Slicing (Module 8)
========================================================================

Computes scalar performance feedback r_t based on actual measured network outcomes.

Mathematical Formulation:
--------------------------
    r_t = w_tput * T_norm - w_lat * L_norm - w_loss * P_norm - w_sla * SLA_Penalty - w_sec * Sec_Overhead

Where:
    1. T_norm (Normalized Bottleneck Throughput):
       T_norm = min(1.0, throughput_mbps / link_capacity_mbps)
       Scale: [0.0, 1.0]. Rewarding network utilization within physical capacity (10 Mbps).

    2. L_norm (Normalized Latency within Operational Region):
       L_norm = min(1.0, max(0.0, latency_ms - min_prop_delay) / (sla_latency_ms - min_prop_delay))
       Where min_prop_delay = 10.0 ms (2 * 5.0 ms propagation delay from topology.py).
       Scale: [0.0, 1.0]. Penalizes rising queuing delay.

    3. P_norm (Normalized Packet Loss):
       P_norm = min(1.0, packet_loss_pct / max_loss_threshold)
       Scale: [0.0, 1.0]. Penalizes packet drops relative to 1.0% limit.

    4. SLA_Penalty (SLA Violation Barrier):
       If latency_ms <= 15.0 ms and packet_loss <= 1.0%:
           SLA_Penalty = 0.0
       If latency_ms > 15.0 ms:
           delta_lat = latency_ms - 15.0 ms
           SLA_Penalty = (delta_lat / 15.0)^2   (steep quadratic growth)
       If latency_ms == -1.0 (sentinel dropped probe / 100% loss):
           SLA_Penalty = 5.0 (maximum violation penalty)

    5. Sec_Overhead (Security Overhead - ONLY if empirically measured):
       If SecurityState is present AND is_measured == True:
           Sec_Overhead = min(1.0, latency_overhead_ms / max_overhead_ms)
       If unmeasured or missing:
           Sec_Overhead = 0.0 (Strictly avoided to prevent fabricating unverified signals)

Important Architectural Rule:
-----------------------------
The reward function provides soft behavioral optimization feedback to the SRA-LinUCB
bandit. It does NOT replace the hard deterministic SLA Guardrail (Module 6), which
remains the absolute pre-execution gatekeeper for network safety.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, Tuple
import math


@dataclass
class RewardConfig:
    """Configurable weights and normalization boundaries for reward calculation."""

    # Normalization baselines (from topology and SLA constraints)
    link_capacity_mbps: float = 10.0
    min_propagation_delay_ms: float = 10.0   # 2 * 5.0 ms link delay
    urllc_latency_sla_ms: float = 15.0       # Hard project SLA threshold
    max_packet_loss_pct: float = 1.0         # 1.0% target
    max_security_overhead_ms: float = 5.0    # 5.0 ms overhead ceiling

    # Objective weights (Configurable evaluation parameters)
    w_throughput: float = 1.0
    w_latency: float = 1.0
    w_packet_loss: float = 2.0
    w_sla_violation: float = 5.0
    w_security_overhead: float = 0.5

    def __post_init__(self):
        if self.link_capacity_mbps <= 0:
            raise ValueError("link_capacity_mbps must be positive")
        if self.urllc_latency_sla_ms <= 0:
            raise ValueError("urllc_latency_sla_ms must be positive")


class RewardEngine:
    """
    Computes mathematically rigorous, continuous reward signals from measured telemetry.
    Supports TelemetryRecord dataclasses, dictionaries, and optional SecurityState.
    """

    def __init__(self, config: Optional[RewardConfig] = None):
        self.config = config or RewardConfig()

    def extract_metrics(
        self,
        telemetry: Union[Dict[str, Any], Any]
    ) -> Dict[str, float]:
        """
        Safely extracts and standardizes network metrics from a TelemetryRecord
        or dictionary, defending against missing keys and sentinel values.
        """
        if telemetry is None:
            return {
                "latency_ms": -1.0,
                "packet_loss": 100.0,
                "throughput_mbps": 0.0,
            }

        # Convert dataclass if needed
        if hasattr(telemetry, "to_dict"):
            data = telemetry.to_dict()
        elif hasattr(telemetry, "__dataclass_fields__"):
            import dataclasses
            data = dataclasses.asdict(telemetry)
        elif isinstance(telemetry, dict):
            data = telemetry
        else:
            data = {}

        # Safe extraction of latency (ms)
        raw_lat = (
            data.get("urllc_latency_ms")
            if "urllc_latency_ms" in data
            else data.get("urllc_latency", data.get("latency_ms", data.get("latency", 0.0)))
        )
        try:
            latency_ms = float(raw_lat) if raw_lat is not None else -1.0
        except (ValueError, TypeError):
            latency_ms = -1.0

        # Safe extraction of packet loss (%)
        raw_loss = (
            data.get("urllc_packet_loss")
            if "urllc_packet_loss" in data
            else data.get("packet_loss", data.get("loss", 0.0))
        )
        try:
            packet_loss = float(raw_loss) if raw_loss is not None else 100.0
        except (ValueError, TypeError):
            packet_loss = 100.0

        # Safe extraction of throughput (Mbps)
        raw_tput = (
            data.get("throughput_mbps")
            if "throughput_mbps" in data
            else data.get("embb_throughput", data.get("throughput", 0.0))
        )
        try:
            throughput_mbps = float(raw_tput) if raw_tput is not None else 0.0
        except (ValueError, TypeError):
            throughput_mbps = 0.0

        return {
            "latency_ms": latency_ms,
            "packet_loss": packet_loss,
            "throughput_mbps": throughput_mbps,
        }

    def compute_reward(
        self,
        telemetry: Union[Dict[str, Any], Any],
        security_state: Optional[Any] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculates the continuous scalar reward r_t and returns diagnostic breakdown.

        Args:
            telemetry: Post-action network state (TelemetryRecord or dict).
            security_state: Optional SecurityState object from Module 5.

        Returns:
            Tuple of:
                - scalar_reward: float
                - diagnostics: Dict[str, Any] with component breakdown.
        """
        metrics = self.extract_metrics(telemetry)
        lat = metrics["latency_ms"]
        loss = metrics["packet_loss"]
        tput = metrics["throughput_mbps"]

        cfg = self.config

        # 1. Normalized Throughput [0.0, 1.0]
        norm_tput = max(0.0, min(1.0, tput / cfg.link_capacity_mbps))

        # 2. Sentinel Handling & Latency Normalization
        is_sentinel_dropped = (lat < 0.0 or lat == -1.0)

        if is_sentinel_dropped:
            norm_lat = 1.0
            norm_loss = 1.0
            sla_penalty = 5.0  # Max barrier penalty for total connection drop
            is_sla_violation = True
        else:
            # Latency normalized within operational span [min_prop_delay, SLA]
            span = max(1.0, cfg.urllc_latency_sla_ms - cfg.min_propagation_delay_ms)
            norm_lat = max(0.0, min(1.0, (lat - cfg.min_propagation_delay_ms) / span))

            # Packet loss normalized relative to max allowed threshold
            norm_loss = max(0.0, min(1.0, loss / cfg.max_packet_loss_pct))

            # SLA Barrier Penalty (Quadratic growth beyond 15.0 ms SLA)
            if lat > cfg.urllc_latency_sla_ms:
                is_sla_violation = True
                excess_lat = lat - cfg.urllc_latency_sla_ms
                # Bounded quadratic barrier: (excess / 15.0)^2 capped at 5.0
                sla_penalty = min(5.0, (excess_lat / cfg.urllc_latency_sla_ms) ** 2)
            elif loss > cfg.max_packet_loss_pct:
                is_sla_violation = True
                excess_loss = loss - cfg.max_packet_loss_pct
                sla_penalty = min(5.0, (excess_loss / cfg.max_packet_loss_pct) ** 2)
            else:
                is_sla_violation = False
                sla_penalty = 0.0

        # 3. Security Overhead Handling (Only included if empirically measured)
        sec_overhead_val = 0.0
        sec_overhead_norm = 0.0
        sec_measured = False

        if security_state is not None:
            # Check is_measured flag to prevent fabricating unmeasured defaults
            sec_measured = getattr(security_state, "is_measured", False)
            if sec_measured:
                raw_oh = getattr(security_state, "latency_overhead_ms", 0.0)
                sec_overhead_val = max(0.0, float(raw_oh))
                sec_overhead_norm = min(1.0, sec_overhead_val / cfg.max_security_overhead_ms)

        # 4. Total Weighted Reward Calculation
        # Good TPut (+) | Low Latency (-) | Low Loss (-) | SLA Barrier (-) | Security Overhead (-)
        tput_term = cfg.w_throughput * norm_tput
        lat_term = cfg.w_latency * norm_lat
        loss_term = cfg.w_packet_loss * norm_loss
        sla_term = cfg.w_sla_violation * sla_penalty
        sec_term = cfg.w_security_overhead * sec_overhead_norm

        total_reward = tput_term - lat_term - loss_term - sla_term - sec_term

        diagnostics = {
            "total_reward": round(total_reward, 4),
            "throughput_term": round(tput_term, 4),
            "latency_term": round(-lat_term, 4),
            "loss_term": round(-loss_term, 4),
            "sla_penalty_term": round(-sla_term, 4),
            "security_overhead_term": round(-sec_term, 4),
            "is_sla_violation": is_sla_violation,
            "security_measured": sec_measured,
            "measured_latency_ms": lat,
            "measured_packet_loss": loss,
            "measured_throughput_mbps": tput,
        }

        return float(total_reward), diagnostics


# Global default engine instance
DEFAULT_REWARD_ENGINE = RewardEngine()


def calculate_reward(
    previous_state: Optional[Dict[str, Any]],
    action: Any,
    new_state: Optional[Dict[str, Any]],
    security_state: Optional[Any] = None
) -> float:
    """
    Backwards-compatible API wrapper for Module 8 reward calculation.
    Consumes post-action state and returns scalar reward float.
    """
    reward, _ = DEFAULT_REWARD_ENGINE.compute_reward(
        telemetry=new_state,
        security_state=security_state
    )
    return reward