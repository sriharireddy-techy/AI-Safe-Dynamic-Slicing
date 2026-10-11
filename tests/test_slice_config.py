"""
Unit Tests for Slicing Configuration and Data Models
"""

import unittest
from slicing.slice_config import (
    SliceType,
    SliceProfile,
    SliceAllocation,
    NetworkSlicingConfig,
    DEFAULT_SLICING_CONFIG,
)


class TestSliceConfig(unittest.TestCase):
    """Test suite for slice_config data classes and validation methods."""

    def test_default_profiles_exist(self):
        """Verify that URLLC, eMBB, and Best-Effort profiles exist by default."""
        config = NetworkSlicingConfig()
        urllc = config.get_profile(SliceType.URLLC)
        embb = config.get_profile(SliceType.EMBB)
        be = config.get_profile(SliceType.BEST_EFFORT)

        self.assertEqual(urllc.src_host, "h1")
        self.assertEqual(urllc.dst_host, "h4")
        self.assertEqual(urllc.src_ip, "10.0.0.1")
        self.assertEqual(urllc.dst_ip, "10.0.0.4")
        self.assertEqual(urllc.latency_sla_ms, 15.0)
        self.assertEqual(urllc.packet_loss_sla_pct, 1.0)

        self.assertEqual(embb.src_host, "h2")
        self.assertEqual(embb.dst_host, "h5")
        self.assertEqual(embb.src_ip, "10.0.0.2")
        self.assertEqual(embb.dst_ip, "10.0.0.5")

        self.assertEqual(be.src_host, "h3")
        self.assertEqual(be.dst_host, "h6")

    def test_lookup_by_ip(self):
        """Test finding slice profile by host IP address."""
        config = NetworkSlicingConfig()
        profile_h1 = config.get_profile_by_ip("10.0.0.1")
        profile_h4 = config.get_profile_by_ip("10.0.0.4")
        profile_h2 = config.get_profile_by_ip("10.0.0.2")
        profile_unknown = config.get_profile_by_ip("10.0.0.99")

        self.assertIsNotNone(profile_h1)
        self.assertEqual(profile_h1.slice_type, SliceType.URLLC)
        self.assertEqual(profile_h4.slice_type, SliceType.URLLC)
        self.assertIsNotNone(profile_h2)
        self.assertEqual(profile_h2.slice_type, SliceType.EMBB)
        self.assertIsNone(profile_unknown)

    def test_slice_allocation_validity(self):
        """Test SliceAllocation total calculation and validation checks."""
        alloc = SliceAllocation(urllc_mbps=3.0, embb_mbps=5.0, be_mbps=2.0)
        self.assertEqual(alloc.total_mbps, 10.0)
        self.assertTrue(alloc.is_valid(link_capacity_mbps=10.0, urllc_min_mbps=2.0))

        # Over-capacity allocation
        over_alloc = SliceAllocation(urllc_mbps=4.0, embb_mbps=6.0, be_mbps=2.0)  # total 12.0
        self.assertEqual(over_alloc.total_mbps, 12.0)
        self.assertFalse(over_alloc.is_valid(link_capacity_mbps=10.0))

        # Starving URLLC below minimum
        starved_alloc = SliceAllocation(urllc_mbps=1.0, embb_mbps=7.0, be_mbps=2.0)
        self.assertFalse(starved_alloc.is_valid(urllc_min_mbps=2.0))

    def test_slice_allocation_serialization(self):
        """Test to_dict and from_dict serialization."""
        original = SliceAllocation(urllc_mbps=3.5, embb_mbps=4.5, be_mbps=1.5)
        d = original.to_dict()
        self.assertEqual(d["URLLC"], 3.5)
        self.assertEqual(d["eMBB"], 4.5)
        self.assertEqual(d["Best-Effort"], 1.5)
        self.assertEqual(d["total"], 9.5)

        restored = SliceAllocation.from_dict(d)
        self.assertEqual(restored.urllc_mbps, 3.5)
        self.assertEqual(restored.embb_mbps, 4.5)
        self.assertEqual(restored.be_mbps, 1.5)

    def test_profile_validation_errors(self):
        """Test that invalid profiles raise ValueError."""
        with self.assertRaises(ValueError):
            # min > max
            bad_profile = SliceProfile(
                slice_type=SliceType.URLLC,
                name="Bad",
                src_host="h1",
                src_ip="10.0.0.1",
                dst_host="h4",
                dst_ip="10.0.0.4",
                queue_id=0,
                priority=0,
                min_bandwidth_mbps=6.0,
                max_bandwidth_mbps=4.0,
            )
            bad_profile.validate()

        with self.assertRaises(ValueError):
            # negative min
            bad_profile2 = SliceProfile(
                slice_type=SliceType.URLLC,
                name="Bad2",
                src_host="h1",
                src_ip="10.0.0.1",
                dst_host="h4",
                dst_ip="10.0.0.4",
                queue_id=0,
                priority=0,
                min_bandwidth_mbps=-1.0,
                max_bandwidth_mbps=5.0,
            )
            bad_profile2.validate()


if __name__ == "__main__":
    unittest.main()
