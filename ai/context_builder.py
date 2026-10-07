"""
Context & Feature Extraction Module (Module 3)
==============================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

This module acts as the translator between raw physical network telemetry (Module 2)
and the contextual bandit decision engine (Module 4, SRA-LinUCB).

Responsibilities:
1. Ingest TelemetryRecord (or compatible dictionary) from Module 2.
2. Defensively sanitize invalid/sentinel values (e.g., -1.0 ping unreachable).
3. Compute dynamic temporal features (latency trend / velocity).
4. Apply bounded mathematical normalization to eliminate scale disparity.
5. Construct and return a 1D NumPy vector x_t in R^6.

Design Constraints:
- Module 3 DOES NOT implement LinUCB, reward estimation, or SLA guardrails.
- Purely responsible for preparing the numerical context vector x_t.
"""

from typing import Optional, Union, Dict, Any
import numpy as np

# Import TelemetryRecord if available; support duck-typing / dictionary fallback
try:
    from telemetry.monitor import TelemetryRecord
except ImportError:
    TelemetryRecord = None  # type: ignore


class ContextBuilder:
    """
    Transforms raw telemetry measurements into a normalized 6-dimensional
    context vector x_t for linear contextual bandits.
    
    Feature Vector Layout:
        x_0: Bias / Intercept term (always 1.0)
        x_1: Normalized URLLC latency in [0.0, 1.0]
        x_2: Normalized bottleneck throughput in [0.0, 1.0]
        x_3: Normalized queue occupancy in [0.0, 1.0]
        x_4: Latency trend (velocity) in [-1.0, 1.0]
        x_5: Packet loss ratio in [0.0, 1.0]
        
    State:
        Maintains previous latency to compute discrete derivative (trend).
    """

    def __init__(
        self,
        max_latency: float = 50.0,
        max_throughput: float = 10.0,
        max_queue: float = 50.0
    ):
        """
        Initialize the context builder with configurable normalization ceilings.
        
        Args:
            max_latency: Normalization ceiling for URLLC latency in milliseconds.
                         Note: Experimental SLA is 15 ms, but 50 ms provides a wider
                         observation ceiling without immediate saturation.
            max_throughput: Normalization ceiling for bottleneck link (10.0 Mbps).
            max_queue: Normalization ceiling for bottleneck buffer (50.0 packets).
        """
        self.max_latency = float(max_latency)
        self.max_throughput = float(max_throughput)
        self.max_queue = float(max_queue)

        # Internal state for differential trend calculation
        self.prev_latency: Optional[float] = None

    def reset(self) -> None:
        """Resets historical state (e.g. at the start of a new experiment run)."""
        self.prev_latency = None

    def build_context(self, record: Union[Any, Dict[str, Any]]) -> np.ndarray:
        """
        Converts a single telemetry sample into a normalized context vector x_t.
        
        Args:
            record: TelemetryRecord dataclass instance or compatible dictionary.
            
        Returns:
            np.ndarray: 1D NumPy array of shape (6,) with dtype float64.
        """
        # 1. Safely extract raw features whether record is a dataclass or a dictionary
        if isinstance(record, dict):
            raw_lat = record.get("urllc_latency_ms", 0.0)
            raw_loss = record.get("urllc_packet_loss", 0.0)
            raw_tput = record.get("throughput_mbps", 0.0)
            raw_queue = record.get("queue_occupancy", 0)
        else:
            raw_lat = getattr(record, "urllc_latency_ms", 0.0)
            raw_loss = getattr(record, "urllc_packet_loss", 0.0)
            raw_tput = getattr(record, "throughput_mbps", 0.0)
            raw_queue = getattr(record, "queue_occupancy", 0)

        # Defensive fallback for None or non-numeric types
        try:
            raw_lat = float(raw_lat)
        except (TypeError, ValueError):
            raw_lat = -1.0

        try:
            raw_loss = float(raw_loss)
        except (TypeError, ValueError):
            raw_loss = 100.0

        try:
            raw_tput = float(raw_tput)
        except (TypeError, ValueError):
            raw_tput = 0.0

        try:
            raw_queue = float(raw_queue)
        except (TypeError, ValueError):
            raw_queue = 0.0

        # ====================================================================
        # FEATURE 0: BIAS / INTERCEPT
        # ====================================================================
        # Provides baseline intercept so LinUCB can learn theta_0 independently.
        x0_bias = 1.0

        # ====================================================================
        # FEATURE 1: NORMALIZED URLLC LATENCY & SENTINEL SANITIZATION
        # ====================================================================
        # Sentinel -1.0 means ping failed / destination unreachable / 100% loss.
        # NEVER pass negative values to the AI. Negative latency would trick
        # a linear reward model into treating failure as super-low latency!
        is_sentinel = raw_lat < 0.0

        if is_sentinel:
            # Map failure to worst-case network condition
            x1_latency = 1.0
            x5_loss = 1.0
        else:
            # Standard bounded normalization: [0, max_latency] -> [0.0, 1.0]
            x1_latency = float(np.clip(raw_lat / self.max_latency, 0.0, 1.0))
            # Packet loss ratio: [0.0, 100.0] -> [0.0, 1.0]
            x5_loss = float(np.clip(raw_loss / 100.0, 0.0, 1.0))

        # ====================================================================
        # FEATURE 2: NORMALIZED BOTTLENECK THROUGHPUT
        # ====================================================================
        # Normalizes utilization relative to 10 Mbps bottleneck capacity.
        x2_throughput = float(np.clip(raw_tput / self.max_throughput, 0.0, 1.0))

        # ====================================================================
        # FEATURE 3: NORMALIZED QUEUE OCCUPANCY
        # ====================================================================
        # Measures buffer buildup in packets; leading indicator of congestion.
        x3_queue = float(np.clip(raw_queue / self.max_queue, 0.0, 1.0))

        # ====================================================================
        # FEATURE 4: LATENCY TREND (DELTA LATENCY)
        # ====================================================================
        # Discrete velocity: (current - previous) / scaling_window.
        # Positive = congestion worsening. Negative = network recovering.
        if is_sentinel:
            # If current probe failed and we have no baseline, trend is neutral (0.0).
            # If we had a baseline, a sudden drop into unreachable represents
            # maximum positive congestion trend (+1.0).
            if self.prev_latency is None:
                x4_trend = 0.0
            else:
                x4_trend = 1.0
        elif self.prev_latency is None:
            # First valid sample has no temporal predecessor
            x4_trend = 0.0
            self.prev_latency = raw_lat
        else:
            delta_latency = raw_lat - self.prev_latency
            # Scale by 10.0 ms trend window and clip to [-1.0, 1.0]
            x4_trend = float(np.clip(delta_latency / 10.0, -1.0, 1.0))
            # Update state for next cycle
            self.prev_latency = raw_lat

        # Construct final 6-dimensional context vector
        context_vector = np.array(
            [
                x0_bias,
                x1_latency,
                x2_throughput,
                x3_queue,
                x4_trend,
                x5_loss
            ],
            dtype=np.float64
        )

        return context_vector
