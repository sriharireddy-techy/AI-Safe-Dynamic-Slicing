"""
Network Slicing Configuration Package
"""

from slicing.slice_config import (
    SliceType,
    SliceProfile,
    SliceAllocation,
    NetworkSlicingConfig,
    DEFAULT_SLICING_CONFIG,
    URLLC_PROFILE,
    EMBB_PROFILE,
    BEST_EFFORT_PROFILE,
)

__all__ = [
    "SliceType",
    "SliceProfile",
    "SliceAllocation",
    "NetworkSlicingConfig",
    "DEFAULT_SLICING_CONFIG",
    "URLLC_PROFILE",
    "EMBB_PROFILE",
    "BEST_EFFORT_PROFILE",
]
