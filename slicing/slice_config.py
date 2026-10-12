"""
Network Slice Configuration and Data Models
============================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Defines the formal data contracts, QoS parameters, network endpoint mappings,
and bandwidth boundaries for the multi-tenant slicing architecture:
- URLLC (Ultra-Reliable Low-Latency Communication): H1 -> H4
- eMBB (Enhanced Mobile Broadband): H2 -> H5
- Best-Effort (BE): H3 -> H6

Topology Constraints:
- Bottleneck Link (s1 <-> s2): 10.0 Mbps, 5 ms propagation delay, 50 pkt queue
- URLLC Latency SLA: <= 15.0 ms round-trip latency
- URLLC Packet Loss SLA: <= 1.0%
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SliceType(str, Enum):
    """Enumeration of supported network slice categories."""
    URLLC = "URLLC"
    EMBB = "eMBB"
    BEST_EFFORT = "Best-Effort"


@dataclass(frozen=True)
class SliceProfile:
    """QoS, SLA, and endpoint profile for a specific network slice."""
    slice_type: SliceType
    name: str
    src_host: str
    src_ip: str
    dst_host: str
    dst_ip: str
    queue_id: int
    priority: int  # 0 = highest priority, 2 = lowest
    min_bandwidth_mbps: float
    max_bandwidth_mbps: float
    latency_sla_ms: Optional[float] = None
    packet_loss_sla_pct: Optional[float] = None
    description: str = ""

    def validate(self) -> None:
        """Validates configuration parameters."""
        if self.min_bandwidth_mbps < 0:
            raise ValueError(f"[{self.name}] min_bandwidth_mbps cannot be negative.")
        if self.max_bandwidth_mbps < self.min_bandwidth_mbps:
            raise ValueError(
                f"[{self.name}] max_bandwidth ({self.max_bandwidth_mbps}) cannot be less than "
                f"min_bandwidth ({self.min_bandwidth_mbps})."
            )
        if self.latency_sla_ms is not None and self.latency_sla_ms <= 0:
            raise ValueError(f"[{self.name}] latency_sla_ms must be positive if specified.")
        if self.packet_loss_sla_pct is not None and not (0.0 <= self.packet_loss_sla_pct <= 100.0):
            raise ValueError(f"[{self.name}] packet_loss_sla_pct must be between 0.0 and 100.0.")


@dataclass
class SliceAllocation:
    """Represents a discrete or continuous bandwidth allocation across all active slices."""
    urllc_mbps: float = 3.0
    embb_mbps: float = 5.0
    be_mbps: float = 2.0

    @property
    def total_mbps(self) -> float:
        """Returns total aggregate allocated bandwidth across all slices."""
        return round(self.urllc_mbps + self.embb_mbps + self.be_mbps, 4)

    def is_valid(self, link_capacity_mbps: float = 10.0, urllc_min_mbps: float = 2.0) -> bool:
        """
        Validates if this allocation obeys physical link capacity and minimum guarantees.
        """
        if self.total_mbps > link_capacity_mbps:
            return False
        if self.urllc_mbps < urllc_min_mbps:
            return False
        if self.embb_mbps < 0.0 or self.be_mbps < 0.0:
            return False
        return True

    def to_dict(self) -> Dict[str, float]:
        """Serializes allocation to a dictionary."""
        return {
            "URLLC": round(self.urllc_mbps, 3),
            "eMBB": round(self.embb_mbps, 3),
            "Best-Effort": round(self.be_mbps, 3),
            "total": self.total_mbps,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "SliceAllocation":
        """Constructs a SliceAllocation from dictionary mapping."""
        return cls(
            urllc_mbps=float(data.get("URLLC", data.get("urllc_mbps", 3.0))),
            embb_mbps=float(data.get("eMBB", data.get("embb_mbps", 5.0))),
            be_mbps=float(data.get("Best-Effort", data.get("be_mbps", 2.0))),
        )


@dataclass
class NetworkSlicingConfig:
    """
    Central repository of slice profiles and global bottleneck link parameters.
    """
    bottleneck_capacity_mbps: float = 10.0
    bottleneck_propagation_delay_ms: float = 5.0
    bottleneck_queue_limit: int = 50
    urllc_latency_sla_ms: float = 15.0
    urllc_packet_loss_sla_pct: float = 1.0

    profiles: Dict[SliceType, SliceProfile] = field(default_factory=dict)

    def __post_init__(self):
        if not self.profiles:
            self.profiles = self._create_default_profiles()

    def _create_default_profiles(self) -> Dict[SliceType, SliceProfile]:
        """Creates the default profiles matching the project's Mininet topology."""
        return {
            SliceType.URLLC: SliceProfile(
                slice_type=SliceType.URLLC,
                name="URLLC",
                src_host="h1",
                src_ip="10.0.0.1",
                dst_host="h4",
                dst_ip="10.0.0.4",
                queue_id=0,
                priority=0,
                min_bandwidth_mbps=2.0,
                max_bandwidth_mbps=5.0,
                latency_sla_ms=self.urllc_latency_sla_ms,
                packet_loss_sla_pct=self.urllc_packet_loss_sla_pct,
                description="Ultra-Reliable Low-Latency Communication (Mission-Critical)",
            ),
            SliceType.EMBB: SliceProfile(
                slice_type=SliceType.EMBB,
                name="eMBB",
                src_host="h2",
                src_ip="10.0.0.2",
                dst_host="h5",
                dst_ip="10.0.0.5",
                queue_id=1,
                priority=1,
                min_bandwidth_mbps=1.0,
                max_bandwidth_mbps=8.0,
                latency_sla_ms=None,
                packet_loss_sla_pct=None,
                description="Enhanced Mobile Broadband (High Throughput / Video Streaming)",
            ),
            SliceType.BEST_EFFORT: SliceProfile(
                slice_type=SliceType.BEST_EFFORT,
                name="Best-Effort",
                src_host="h3",
                src_ip="10.0.0.3",
                dst_host="h6",
                dst_ip="10.0.0.6",
                queue_id=2,
                priority=2,
                min_bandwidth_mbps=0.5,
                max_bandwidth_mbps=3.0,
                latency_sla_ms=None,
                packet_loss_sla_pct=None,
                description="Best-Effort Internet Traffic (Elastic Background)",
            ),
        }

    def get_profile(self, slice_type: SliceType) -> SliceProfile:
        """Retrieves profile for a given slice type."""
        return self.profiles[slice_type]

    def get_profile_by_ip(self, src_ip: str) -> Optional[SliceProfile]:
        """Finds slice profile matching source IP address."""
        for profile in self.profiles.values():
            if profile.src_ip == src_ip or profile.dst_ip == src_ip:
                return profile
        return None

    def get_default_static_allocation(self) -> SliceAllocation:
        """Returns standard static allocation baseline (3 Mbps URLLC, 5 Mbps eMBB, 2 Mbps BE)."""
        return SliceAllocation(urllc_mbps=3.0, embb_mbps=5.0, be_mbps=2.0)


# Module-level convenience constants & default singleton instance
DEFAULT_SLICING_CONFIG = NetworkSlicingConfig()
URLLC_PROFILE = DEFAULT_SLICING_CONFIG.get_profile(SliceType.URLLC)
EMBB_PROFILE = DEFAULT_SLICING_CONFIG.get_profile(SliceType.EMBB)
BEST_EFFORT_PROFILE = DEFAULT_SLICING_CONFIG.get_profile(SliceType.BEST_EFFORT)
