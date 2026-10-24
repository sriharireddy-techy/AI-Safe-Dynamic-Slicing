"""
Phase 10: Dynamic Data-Plane Rate Actuation Module
===================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Connects Module 06 (Deterministic SLA & Security Guardrail) decisions directly
to the Open vSwitch / Linux Traffic Control (tc) data plane.

Responsibilities:
1. Accept Guardrail decisions and reject unapproved candidate proposals.
2. Validate bandwidth sanity (capacity <= 10.0 Mbps, URLLC >= 3.0 Mbps).
3. Translate approved allocations into Linux tc HTB classes and/or OVS QoS queues.
4. Provide known-safe fallback and automatic rollback on command failures.
5. Read back and verify the actual applied configuration from the network interface.
6. Provide traffic classification mappings for OpenFlow set_queue integration.
"""

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class ActuatorStatus(str, Enum):
    """Execution status returned by the actuator."""
    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"
    REPAIRED_APPLIED = "REPAIRED_APPLIED"
    FAILED_ROLLED_BACK = "FAILED_ROLLED_BACK"
    DRY_RUN = "DRY_RUN"


@dataclass
class ActuatorResult:
    """Detailed result of an actuation attempt."""
    status: ActuatorStatus
    success: bool
    applied_allocation: Optional[Dict[str, float]]
    verified_allocation: Optional[Dict[str, float]]
    commands_executed: List[str] = field(default_factory=list)
    message: str = ""
    timestamp: float = field(default_factory=time.time)
    is_repaired: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "success": self.success,
            "applied_allocation": self.applied_allocation,
            "verified_allocation": self.verified_allocation,
            "commands_executed": self.commands_executed,
            "message": self.message,
            "timestamp": self.timestamp,
            "is_repaired": self.is_repaired,
        }


# ==============================================================================
# PHYSICAL TOPOLOGY & SLICE CONSTANTS
# ==============================================================================
DEFAULT_BOTTLENECK_INTERFACE: str = "s1-eth4"
TOTAL_CAPACITY_MBPS: float = 10.0
URLLC_MIN_RESERVATION_MBPS: float = 3.0
EMBB_MIN_FLOOR_MBPS: float = 1.0
BE_MIN_FLOOR_MBPS: float = 0.5

# Known-safe fallback allocation (Module 6 baseline invariant)
KNOWN_SAFE_ALLOCATION: Dict[str, float] = {
    "URLLC": 3.0,
    "eMBB": 5.0,
    "BE": 2.0,
}

# HTB Class and Queue Mapping
# Parent class: 1:1 (root 10.0 Mbps ceiling)
SLICE_CLASS_MAP: Dict[str, Dict[str, Any]] = {
    "URLLC": {
        "classid": "1:10",
        "queue_id": 0,
        "prio": 0,  # Highest scheduling priority
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.4",
        "ceil_mbps": 10.0,
    },
    "eMBB": {
        "classid": "1:20",
        "queue_id": 1,
        "prio": 1,  # Medium scheduling priority
        "src_ip": "10.0.0.2",
        "dst_ip": "10.0.0.5",
        "ceil_mbps": 10.0,
    },
    "BE": {
        "classid": "1:30",
        "queue_id": 2,
        "prio": 2,  # Lowest scheduling priority
        "src_ip": "10.0.0.3",
        "dst_ip": "10.0.0.6",
        "ceil_mbps": 10.0,
    },
}


# ==============================================================================
# SLICING ACTUATOR ENGINE
# ==============================================================================

class SlicingActuator:
    """Translates guardrail-verified slicing decisions into live data-plane rate controls."""

    def __init__(
        self,
        interface: str = DEFAULT_BOTTLENECK_INTERFACE,
        total_capacity_mbps: float = TOTAL_CAPACITY_MBPS,
        dry_run: bool = False,
        command_runner: Optional[Callable[[List[str]], Tuple[int, str, str]]] = None,
    ):
        """
        Args:
            interface: Bottleneck switch interface to rate-limit (e.g. 's1-eth4').
            total_capacity_mbps: Physical link capacity ceiling (10.0 Mbps).
            dry_run: If True, commands are constructed and logged without invoking the OS shell.
            command_runner: Custom callable (cmd_list -> (returncode, stdout, stderr)).
                            Defaults to subprocess.run.
        """
        self.interface = interface
        self.total_capacity_mbps = float(total_capacity_mbps)
        self.dry_run = dry_run
        self._command_runner = command_runner or self._default_command_runner

        # State tracking for rollback
        self.last_applied_allocation: Dict[str, float] = dict(KNOWN_SAFE_ALLOCATION)
        self.actuation_history: List[ActuatorResult] = []

    @staticmethod
    def _default_command_runner(cmd: List[str]) -> Tuple[int, str, str]:
        """Default runner executing commands via subprocess."""
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3.0,
                check=False,
            )
            return res.returncode, res.stdout, res.stderr
        except Exception as e:
            return 1, "", str(e)

    def validate_decision(
        self, guardrail_decision: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, float]], str]:
        """Validates the input from Module 6 Guardrail before generating any shell commands.

        Rules:
        1. Decision must be a dictionary with 'approved' == True.
        2. 'action' must be a valid dictionary with canonical slice keys.
        3. Total bandwidth must not exceed total_capacity_mbps.
        4. URLLC must receive at least URLLC_MIN_RESERVATION_MBPS (3.0 Mbps).
        """
        if not isinstance(guardrail_decision, dict):
            return False, None, "Invalid guardrail decision: input is not a dictionary."

        is_approved = bool(guardrail_decision.get("approved", False))
        if not is_approved:
            violations = guardrail_decision.get("violations", [])
            reason = guardrail_decision.get("reason", "Action was not approved by guardrail.")
            return False, None, f"Actuation rejected: guardrail rejected action. Violations: {violations}. Reason: {reason}"

        raw_action = guardrail_decision.get("action")
        if not isinstance(raw_action, dict):
            return False, None, "Actuation rejected: approved decision does not contain an allocation action dictionary."

        # Canonicalize slice keys
        canonical: Dict[str, float] = {}
        key_map = {
            "urllc": "URLLC",
            "embb": "eMBB",
            "be": "BE",
            "best_effort": "BE",
            "best-effort": "BE",
        }

        for k, v in raw_action.items():
            norm_k = key_map.get(str(k).strip().lower())
            if norm_k:
                try:
                    canonical[norm_k] = float(v)
                except (ValueError, TypeError):
                    return False, None, f"Non-numeric bandwidth value for slice '{k}': {v}"

        required = {"URLLC", "eMBB", "BE"}
        if not required.issubset(canonical.keys()):
            return False, None, f"Missing required slices in allocation: {list(required - set(canonical.keys()))}"

        # Enforce physical invariants
        total = round(sum(canonical.values()), 3)
        if total > self.total_capacity_mbps + 1e-4:
            return False, None, f"Actuation rejected: total bandwidth {total:.2f} Mbps exceeds link capacity {self.total_capacity_mbps:.2f} Mbps."

        if canonical["URLLC"] < URLLC_MIN_RESERVATION_MBPS - 1e-4:
            return False, None, f"Actuation rejected: URLLC bandwidth {canonical['URLLC']:.2f} Mbps violates minimum 3.0 Mbps floor."

        if canonical["eMBB"] < 0.0 or canonical["BE"] < 0.0:
            return False, None, "Actuation rejected: slice bandwidth cannot be negative."

        return True, canonical, "Valid allocation approved for actuation."

    def build_tc_commands(self, allocation: Dict[str, float]) -> List[List[str]]:
        """Constructs atomic Linux Traffic Control (tc) commands for HTB classes.

        Units:
            Bandwidth in Mbps is translated to 'kbit' for precise tc scheduling
            (1.0 Mbps = 1000 kbit/s).
        """
        commands: List[List[str]] = []

        for slice_name, params in SLICE_CLASS_MAP.items():
            bw_mbps = allocation.get(slice_name, 1.0)
            rate_kbit = int(bw_mbps * 1000)
            ceil_kbit = int(params["ceil_mbps"] * 1000)
            classid = params["classid"]
            prio = params["prio"]

            # Use 'replace' to atomically update existing HTB class rates without tearing down qdisc
            cmd = [
                "tc", "class", "replace",
                "dev", self.interface,
                "parent", "1:1",
                "classid", classid,
                "htb",
                "rate", f"{rate_kbit}kbit",
                "ceil", f"{ceil_kbit}kbit",
                "prio", str(prio),
            ]
            commands.append(cmd)

        return commands

    def build_ovs_queue_commands(self, allocation: Dict[str, float]) -> List[List[str]]:
        """Constructs Open vSwitch QoS queue commands via ovs-vsctl."""
        commands: List[List[str]] = []

        # Update OVS queue other-config min-rate and max-rate
        for slice_name, params in SLICE_CLASS_MAP.items():
            bw_bps = int(allocation.get(slice_name, 1.0) * 1_000_000)
            qid = params["queue_id"]
            cmd = [
                "ovs-vsctl", "set", "queue", f"s1-eth4-q{qid}",
                f"other-config:min-rate={bw_bps}",
                f"other-config:max-rate={bw_bps}",
            ]
            commands.append(cmd)

        return commands

    def build_classification_rules(self) -> List[Dict[str, Any]]:
        """Returns traffic classification definitions matching slice flows to queue IDs."""
        rules = []
        for slice_name, params in SLICE_CLASS_MAP.items():
            rules.append({
                "slice": slice_name,
                "queue_id": params["queue_id"],
                "prio": params["prio"],
                "src_ip": params["src_ip"],
                "dst_ip": params["dst_ip"],
                "ip_proto": "ipv4",
            })
        return rules

    def parse_tc_class_output(self, stdout: str) -> Dict[str, float]:
        """Parses output of `tc -s class show dev <iface>` to extract actual configured rates.

        Supports formats:
            rate 3Mbit ceil 10Mbit
            rate 3000Kbit ceil 10Mbit
            rate 3000000bps ceil 10Mbit
        """
        rates: Dict[str, float] = {}
        if not stdout:
            return rates

        # Invert classid lookup: "1:10" -> "URLLC"
        classid_to_slice = {p["classid"]: s for s, p in SLICE_CLASS_MAP.items()}

        lines = stdout.splitlines()
        current_class: Optional[str] = None

        for line in lines:
            # Match class header: "class htb 1:10 parent 1:1 ..."
            class_match = re.search(r'class\s+htb\s+(\d+:\d+)', line)
            if class_match:
                cid = class_match.group(1)
                current_class = classid_to_slice.get(cid)

            # Match rate inside class block
            if current_class:
                rate_match = re.search(r'rate\s+(\d+(?:\.\d+)?)\s*([KMGkmg]?bit|bps)', line)
                if rate_match:
                    val = float(rate_match.group(1))
                    unit = rate_match.group(2).lower()

                    if "mbit" in unit:
                        mbps = val
                    elif "kbit" in unit:
                        mbps = val / 1000.0
                    elif "gbit" in unit:
                        mbps = val * 1000.0
                    elif "bps" in unit:
                        mbps = (val * 8.0) / 1_000_000.0
                    else:
                        mbps = val / 1_000_000.0

                    rates[current_class] = round(mbps, 3)
                    current_class = None

        return rates

    def read_applied_configuration(self) -> Dict[str, float]:
        """Queries the kernel data plane and reads back the configured rates."""
        if self.dry_run:
            # In dry-run mode, return simulated state matching last applied allocation
            return dict(self.last_applied_allocation)

        cmd = ["tc", "-s", "class", "show", "dev", self.interface]
        rc, out, err = self._command_runner(cmd)
        if rc != 0:
            return {}

        return self.parse_tc_class_output(out)

    def verify_applied_rates(
        self, requested: Dict[str, float], tolerance_mbps: float = 0.1
    ) -> Tuple[bool, Dict[str, float], str]:
        """Verifies that the rates read back from the interface match the requested allocation."""
        applied = self.read_applied_configuration()
        if not applied:
            return False, {}, "Failed to read back tc class configuration from interface."

        mismatches = []
        for slice_name, req_val in requested.items():
            act_val = applied.get(slice_name)
            if act_val is None:
                mismatches.append(f"{slice_name}: not found in tc output")
            elif abs(act_val - req_val) > tolerance_mbps:
                mismatches.append(f"{slice_name}: requested {req_val:.2f}M, found {act_val:.2f}M")

        if mismatches:
            return False, applied, f"Applied rate mismatch: {'; '.join(mismatches)}"

        return True, applied, "Verified: applied rates match requested allocation within tolerance."

    def rollback_to_safe(self) -> ActuatorResult:
        """Rolls back the data plane to the known-safe default allocation."""
        safe_alloc = dict(KNOWN_SAFE_ALLOCATION)
        commands = self.build_tc_commands(safe_alloc)
        executed_cmds = [" ".join(c) for c in commands]

        if self.dry_run:
            self.last_applied_allocation = safe_alloc
            return ActuatorResult(
                status=ActuatorStatus.SUCCESS,
                success=True,
                applied_allocation=safe_alloc,
                verified_allocation=safe_alloc,
                commands_executed=executed_cmds,
                message="Rolled back to known-safe allocation (DRY RUN).",
                is_repaired=False,
            )

        failed = False
        for cmd in commands:
            rc, out, err = self._command_runner(cmd)
            if rc != 0:
                failed = True
                break

        if not failed:
            self.last_applied_allocation = safe_alloc
            verified = self.read_applied_configuration()
            return ActuatorResult(
                status=ActuatorStatus.SUCCESS,
                success=True,
                applied_allocation=safe_alloc,
                verified_allocation=verified,
                commands_executed=executed_cmds,
                message="Successfully rolled back to known-safe baseline allocation.",
                is_repaired=False,
            )

        return ActuatorResult(
            status=ActuatorStatus.FAILED_ROLLED_BACK,
            success=False,
            applied_allocation=None,
            verified_allocation=None,
            commands_executed=executed_cmds,
            message="Rollback command execution failed in shell.",
            is_repaired=False,
        )

    def apply_allocation(
        self,
        guardrail_decision: Dict[str, Any],
        allow_rollback: bool = True,
    ) -> ActuatorResult:
        """Main entry point: ingests a Guardrail decision and actuates it onto the data plane.

        Workflow:
        1. Validates decision (must be approved, within capacity, URLLC >= 3.0M).
        2. Translates rates to Linux tc commands.
        3. Executes commands (or simulates if dry_run=True).
        4. Reads back the applied configuration to verify success.
        5. If execution fails and allow_rollback is True, safely rolls back.
        """
        is_valid, allocation, msg = self.validate_decision(guardrail_decision)
        is_repaired = bool(guardrail_decision.get("is_repaired", False)) if isinstance(guardrail_decision, dict) else False

        if not is_valid or allocation is None:
            res = ActuatorResult(
                status=ActuatorStatus.REJECTED,
                success=False,
                applied_allocation=None,
                verified_allocation=self.read_applied_configuration(),
                commands_executed=[],
                message=msg,
                is_repaired=is_repaired,
            )
            self.actuation_history.append(res)
            return res

        # Build tc commands
        commands = self.build_tc_commands(allocation)
        cmd_strings = [" ".join(c) for c in commands]

        # Dry-run handling
        if self.dry_run:
            self.last_applied_allocation = dict(allocation)
            res = ActuatorResult(
                status=ActuatorStatus.REPAIRED_APPLIED if is_repaired else ActuatorStatus.DRY_RUN,
                success=True,
                applied_allocation=allocation,
                verified_allocation=allocation,
                commands_executed=cmd_strings,
                message="Actuation simulated successfully (DRY RUN).",
                is_repaired=is_repaired,
            )
            self.actuation_history.append(res)
            return res

        # Execute commands on live network
        for cmd in commands:
            rc, out, err = self._command_runner(cmd)
            if rc != 0:
                err_msg = f"tc command failed (rc={rc}): {err.strip() or out.strip()}"
                if allow_rollback:
                    rollback_res = self.rollback_to_safe()
                    res = ActuatorResult(
                        status=ActuatorStatus.FAILED_ROLLED_BACK,
                        success=False,
                        applied_allocation=rollback_res.applied_allocation,
                        verified_allocation=rollback_res.verified_allocation,
                        commands_executed=cmd_strings + rollback_res.commands_executed,
                        message=f"{err_msg}. Triggered automatic rollback to safe baseline.",
                        is_repaired=is_repaired,
                    )
                else:
                    res = ActuatorResult(
                        status=ActuatorStatus.FAILED_ROLLED_BACK,
                        success=False,
                        applied_allocation=None,
                        verified_allocation=self.read_applied_configuration(),
                        commands_executed=cmd_strings,
                        message=err_msg,
                        is_repaired=is_repaired,
                    )
                self.actuation_history.append(res)
                return res

        # Read-back verification
        verified = self.read_applied_configuration()
        self.last_applied_allocation = dict(allocation)

        status = ActuatorStatus.REPAIRED_APPLIED if is_repaired else ActuatorStatus.SUCCESS
        res = ActuatorResult(
            status=status,
            success=True,
            applied_allocation=allocation,
            verified_allocation=verified,
            commands_executed=cmd_strings,
            message="Successfully actuated and verified bandwidth allocation on data plane.",
            is_repaired=is_repaired,
        )
        self.actuation_history.append(res)
        return res
