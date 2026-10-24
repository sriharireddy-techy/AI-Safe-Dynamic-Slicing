"""
Phase 10: Dynamic Data-Plane Rate Actuation Test Suite
=====================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Verifies:
1. Validation of Module 06 Guardrail decisions (approval checks, input sanity).
2. Physical link capacity ceiling enforcement (<= 10.0 Mbps).
3. URLLC minimum bandwidth reservation floor enforcement (>= 3.0 Mbps).
4. Acceptance and application of guardrail-repaired allocations.
5. Unit conversion and Linux tc HTB class command formatting.
6. Open vSwitch QoS queue command formatting.
7. Traffic classification rule mapping for slice egress queues.
8. Parsing of `tc -s class show` output across multiple unit formats (Mbit, Kbit, bps).
9. Read-back verification and tolerance checks.
10. Simulated / dry-run actuation mode.
11. Automatic rollback to known-safe baseline on command execution failure.
12. End-to-end integration from Guardrail output to SlicingActuator.
"""

import pytest
from typing import Dict, List, Tuple
from controller.slicing_actuator import (
    SlicingActuator,
    ActuatorStatus,
    ActuatorResult,
    KNOWN_SAFE_ALLOCATION,
    TOTAL_CAPACITY_MBPS,
    URLLC_MIN_RESERVATION_MBPS,
    SLICE_CLASS_MAP,
)
from guardrail.guardrail import SLASecurityGuardrail
from slicing.slice_config import DEFAULT_SLICING_CONFIG


# ==============================================================================
# 1. INITIALIZATION & CONFIGURATION TESTS
# ==============================================================================

def test_actuator_default_initialization():
    """Verifies default parameters and baseline state of the actuator."""
    actuator = SlicingActuator()
    assert actuator.interface == "s1-eth4"
    assert actuator.total_capacity_mbps == 10.0
    assert actuator.dry_run is False
    assert actuator.last_applied_allocation == KNOWN_SAFE_ALLOCATION
    assert len(actuator.actuation_history) == 0


def test_actuator_custom_initialization():
    """Verifies custom interface and dry_run configuration."""
    actuator = SlicingActuator(interface="s2-eth4", total_capacity_mbps=20.0, dry_run=True)
    assert actuator.interface == "s2-eth4"
    assert actuator.total_capacity_mbps == 20.0
    assert actuator.dry_run is True


# ==============================================================================
# 2. DECISION VALIDATION TESTS
# ==============================================================================

def test_validation_rejects_unapproved_decision():
    """Verifies that actuator rejects any decision where approved is False."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": False,
        "action": {"URLLC": 1.0, "eMBB": 7.0, "BE": 2.0},
        "violations": ["URLLC below SLA floor"],
        "reason": "Dangerous allocation",
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is False
    assert alloc is None
    assert "rejected" in msg.lower()


def test_validation_rejects_non_dict_decision():
    """Verifies graceful rejection if input is not a dictionary."""
    actuator = SlicingActuator(dry_run=True)
    valid, alloc, msg = actuator.validate_decision("invalid_string_decision")  # type: ignore
    assert valid is False
    assert alloc is None


def test_validation_rejects_missing_action():
    """Verifies rejection when 'action' key is absent or not a dict."""
    actuator = SlicingActuator(dry_run=True)
    decision = {"approved": True, "action": None}
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is False
    assert alloc is None


def test_validation_rejects_over_capacity():
    """Verifies rejection if total aggregate bandwidth exceeds 10.0 Mbps."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 4.0, "eMBB": 5.0, "BE": 2.0},  # Total = 11.0 Mbps
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is False
    assert alloc is None
    assert "exceeds link capacity" in msg


def test_validation_rejects_urllc_below_floor():
    """Verifies rejection if URLLC bandwidth is below 3.0 Mbps."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 2.5, "eMBB": 5.5, "BE": 2.0},  # URLLC < 3.0
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is False
    assert alloc is None
    assert "violates minimum 3.0 Mbps floor" in msg


def test_validation_rejects_negative_bandwidth():
    """Verifies rejection if any slice has negative bandwidth."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 4.0, "eMBB": -1.0, "BE": 2.0},
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is False
    assert alloc is None
    assert "negative" in msg


def test_validation_accepts_valid_allocation():
    """Verifies approval of valid compliant allocation."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0},
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is True
    assert alloc == {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}


def test_validation_normalizes_case_variants():
    """Verifies case-insensitive slice key mapping."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"urllc": 3.5, "embb": 4.5, "best-effort": 2.0},
    }
    valid, alloc, msg = actuator.validate_decision(decision)
    assert valid is True
    assert alloc == {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0}


# ==============================================================================
# 3. COMMAND GENERATION & UNIT CONVERSION TESTS
# ==============================================================================

def test_build_tc_commands_formatting_and_units():
    """Verifies tc command construction, units conversion (Mbps -> kbit), and class IDs."""
    actuator = SlicingActuator(interface="s1-eth4")
    allocation = {"URLLC": 4.0, "eMBB": 4.5, "BE": 1.5}

    commands = actuator.build_tc_commands(allocation)
    assert len(commands) == 3

    # URLLC command checks: 4.0 Mbps -> 4000kbit, class 1:10, prio 0
    urllc_cmd = commands[0]
    assert urllc_cmd == [
        "tc", "class", "replace",
        "dev", "s1-eth4",
        "parent", "1:1",
        "classid", "1:10",
        "htb",
        "rate", "4000kbit",
        "ceil", "10000kbit",
        "prio", "0",
    ]

    # eMBB command checks: 4.5 Mbps -> 4500kbit, class 1:20, prio 1
    embb_cmd = commands[1]
    assert embb_cmd[8] == "1:20"
    assert embb_cmd[10] == "rate"
    assert embb_cmd[11] == "4500kbit"
    assert embb_cmd[14] == "prio"
    assert embb_cmd[15] == "1"

    # BE command checks: 1.5 Mbps -> 1500kbit, class 1:30, prio 2
    be_cmd = commands[2]
    assert be_cmd[8] == "1:30"
    assert be_cmd[10] == "rate"
    assert be_cmd[11] == "1500kbit"
    assert be_cmd[14] == "prio"
    assert be_cmd[15] == "2"


def test_build_ovs_queue_commands():
    """Verifies OVS queue command generation in bps."""
    actuator = SlicingActuator()
    allocation = {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
    commands = actuator.build_ovs_queue_commands(allocation)
    assert len(commands) == 3
    # URLLC: 3.0 Mbps -> 3,000,000 bps
    assert "other-config:min-rate=3000000" in commands[0]
    assert "s1-eth4-q0" in commands[0]


def test_build_classification_rules():
    """Verifies traffic classification mappings for queue directing."""
    actuator = SlicingActuator()
    rules = actuator.build_classification_rules()
    assert len(rules) == 3

    rule_map = {r["slice"]: r for r in rules}
    assert rule_map["URLLC"]["queue_id"] == 0
    assert rule_map["URLLC"]["src_ip"] == "10.0.0.1"
    assert rule_map["URLLC"]["dst_ip"] == "10.0.0.4"
    assert rule_map["URLLC"]["prio"] == 0

    assert rule_map["eMBB"]["queue_id"] == 1
    assert rule_map["eMBB"]["src_ip"] == "10.0.0.2"
    assert rule_map["eMBB"]["dst_ip"] == "10.0.0.5"

    assert rule_map["BE"]["queue_id"] == 2
    assert rule_map["BE"]["src_ip"] == "10.0.0.3"
    assert rule_map["BE"]["dst_ip"] == "10.0.0.6"


# ==============================================================================
# 4. OUTPUT PARSING & READ-BACK VERIFICATION TESTS
# ==============================================================================

def test_parse_tc_class_output_mbit():
    """Verifies parsing of tc output formatted with Mbit."""
    sample_output = """
class htb 1:10 parent 1:1 prio 0 rate 4Mbit ceil 10Mbit burst 1599b cburst 1599b
 Sent 1024 bytes 10 pkt (dropped 0, overlimits 0 requeues 0)
class htb 1:20 parent 1:1 prio 1 rate 4.5Mbit ceil 10Mbit burst 1599b cburst 1599b
 Sent 4096 bytes 30 pkt (dropped 0, overlimits 0 requeues 0)
class htb 1:30 parent 1:1 prio 2 rate 1.5Mbit ceil 10Mbit burst 1599b cburst 1599b
 Sent 512 bytes 4 pkt (dropped 0, overlimits 0 requeues 0)
"""
    actuator = SlicingActuator()
    parsed = actuator.parse_tc_class_output(sample_output)
    assert parsed == {"URLLC": 4.0, "eMBB": 4.5, "BE": 1.5}


def test_parse_tc_class_output_kbit():
    """Verifies parsing of tc output formatted with Kbit."""
    sample_output = """
class htb 1:10 parent 1:1 rate 3000Kbit ceil 10000Kbit
class htb 1:20 parent 1:1 rate 5000Kbit ceil 10000Kbit
class htb 1:30 parent 1:1 rate 2000Kbit ceil 10000Kbit
"""
    actuator = SlicingActuator()
    parsed = actuator.parse_tc_class_output(sample_output)
    assert parsed == {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}


def test_parse_tc_class_output_empty():
    """Verifies parsing on empty or malformed string returns empty dict."""
    actuator = SlicingActuator()
    assert actuator.parse_tc_class_output("") == {}
    assert actuator.parse_tc_class_output("random non matching text") == {}


def test_verify_applied_rates_match():
    """Verifies that rate verification succeeds when applied rates match requested."""
    actuator = SlicingActuator(dry_run=True)
    actuator.last_applied_allocation = {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
    ok, applied, msg = actuator.verify_applied_rates({"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0})
    assert ok is True
    assert applied == {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
    assert "Verified" in msg


def test_verify_applied_rates_mismatch():
    """Verifies that rate verification flags discrepancies exceeding tolerance."""
    actuator = SlicingActuator(dry_run=True)
    actuator.last_applied_allocation = {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
    # Requesting 4.0 Mbps when 3.0 is applied
    ok, applied, msg = actuator.verify_applied_rates({"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0})
    assert ok is False
    assert "mismatch" in msg.lower()


# ==============================================================================
# 5. DRY-RUN ACTUATION TESTS
# ==============================================================================

def test_dry_run_approved_actuation():
    """Verifies end-to-end dry-run application of an approved decision."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0},
        "is_repaired": False,
    }
    res = actuator.apply_allocation(decision)
    assert res.success is True
    assert res.status == ActuatorStatus.DRY_RUN
    assert res.applied_allocation == {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0}
    assert len(res.commands_executed) == 3
    assert actuator.last_applied_allocation == {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0}
    assert len(actuator.actuation_history) == 1


def test_dry_run_repaired_actuation():
    """Verifies dry-run application of a guardrail-repaired decision."""
    actuator = SlicingActuator(dry_run=True)
    decision = {
        "approved": True,
        "action": {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0},
        "is_repaired": True,
    }
    res = actuator.apply_allocation(decision)
    assert res.success is True
    assert res.status == ActuatorStatus.REPAIRED_APPLIED
    assert res.is_repaired is True


def test_dry_run_rejected_decision():
    """Verifies that unapproved decisions are rejected without modifying state."""
    actuator = SlicingActuator(dry_run=True)
    initial_state = dict(actuator.last_applied_allocation)

    decision = {
        "approved": False,
        "action": {"URLLC": 1.0, "eMBB": 7.0, "BE": 2.0},
        "violations": ["URLLC below 3.0"],
    }
    res = actuator.apply_allocation(decision)
    assert res.success is False
    assert res.status == ActuatorStatus.REJECTED
    assert res.applied_allocation is None
    assert actuator.last_applied_allocation == initial_state


# ==============================================================================
# 6. MOCKED COMMAND RUNNER & ROLLBACK ON FAILURE TESTS
# ==============================================================================

def test_mocked_command_execution_success():
    """Verifies execution using a mocked successful subprocess runner."""
    executed = []

    def mock_runner(cmd: List[str]) -> Tuple[int, str, str]:
        executed.append(cmd)
        if "-s" in cmd:  # read-back command
            return 0, """
class htb 1:10 parent 1:1 rate 4000Kbit ceil 10000Kbit
class htb 1:20 parent 1:1 rate 4000Kbit ceil 10000Kbit
class htb 1:30 parent 1:1 rate 2000Kbit ceil 10000Kbit
""", ""
        return 0, "", ""

    actuator = SlicingActuator(dry_run=False, command_runner=mock_runner)
    decision = {
        "approved": True,
        "action": {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0},
    }
    res = actuator.apply_allocation(decision)
    assert res.success is True
    assert res.status == ActuatorStatus.SUCCESS
    assert res.applied_allocation == {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
    assert res.verified_allocation == {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
    assert len(executed) == 4  # 3 class replace + 1 class show


def test_mocked_command_execution_failure_triggers_rollback():
    """Verifies that when a tc command fails, automatic rollback is triggered."""
    executed = []

    def failing_runner(cmd: List[str]) -> Tuple[int, str, str]:
        executed.append(cmd)
        if "4000kbit" in cmd:
            # Simulate kernel RTNETLINK error during candidate actuation
            return 1, "", "RTNETLINK answers: No such file or directory"
        if "-s" in cmd:
            return 0, """
class htb 1:10 parent 1:1 rate 3000Kbit ceil 10000Kbit
class htb 1:20 parent 1:1 rate 5000Kbit ceil 10000Kbit
class htb 1:30 parent 1:1 rate 2000Kbit ceil 10000Kbit
""", ""
        return 0, "", ""

    actuator = SlicingActuator(dry_run=False, command_runner=failing_runner)
    decision = {
        "approved": True,
        "action": {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0},
    }
    res = actuator.apply_allocation(decision, allow_rollback=True)
    assert res.success is False
    assert res.status == ActuatorStatus.FAILED_ROLLED_BACK
    assert "rollback to safe baseline" in res.message.lower()
    # Verified allocation should reflect the rolled-back baseline
    assert res.applied_allocation == KNOWN_SAFE_ALLOCATION
    assert actuator.last_applied_allocation == KNOWN_SAFE_ALLOCATION


# ==============================================================================
# 7. END-TO-END PIPELINE: GUARDRAIL -> ACTUATOR INTEGRATION
# ==============================================================================

def test_pipeline_guardrail_approved_proposal_reaches_actuator():
    """Verifies direct coupling of SLASecurityGuardrail approved proposal to SlicingActuator."""
    guardrail = SLASecurityGuardrail()
    actuator = SlicingActuator(dry_run=True)

    # Valid candidate proposal
    candidate_action = {"URLLC": 4.0, "eMBB": 4.0, "BE": 2.0}
    current_metrics = {"latency_ms": 11.2, "packet_loss_pct": 0.2, "link_utilization": 0.65}

    guardrail_decision = guardrail.validate(candidate_action, current_metrics)
    assert guardrail_decision["approved"] is True

    # Feed decision to actuator
    actuation_res = actuator.apply_allocation(guardrail_decision)
    assert actuation_res.success is True
    assert actuation_res.applied_allocation == candidate_action


def test_pipeline_guardrail_repaired_proposal_actuates_safely():
    """Verifies that an unsafe AI proposal repaired by Guardrail is actuated as repaired."""
    guardrail = SLASecurityGuardrail()
    actuator = SlicingActuator(dry_run=True)

    # Greedy AI proposal violating URLLC floor (URLLC = 1.0 Mbps)
    unsafe_proposal = {"URLLC": 1.0, "eMBB": 7.0, "BE": 2.0}
    current_metrics = {"latency_ms": 14.5, "packet_loss_pct": 0.5, "link_utilization": 0.8}

    guardrail_decision = guardrail.validate(unsafe_proposal, current_metrics, allow_repair=True)
    # Guardrail repairs it to meet URLLC safety floor
    assert guardrail_decision["approved"] is True
    assert guardrail_decision["is_repaired"] is True

    actuation_res = actuator.apply_allocation(guardrail_decision)
    assert actuation_res.success is True
    assert actuation_res.status == ActuatorStatus.REPAIRED_APPLIED
    assert actuation_res.applied_allocation["URLLC"] >= URLLC_MIN_RESERVATION_MBPS
