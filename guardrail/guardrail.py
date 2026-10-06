"""Core SLA and Security Guardrail for Module 6.

Validates candidate slicing actions against total capacity, URLLC minimum reservations,
URLLC latency SLAs, packet loss thresholds, and security risk/overhead limits before execution.
Supports both discrete AI actions and explicit bandwidth allocation dictionaries.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from guardrail.sla_config import GuardrailConfig
from security.security_config import SecurityState, SecurityMode


class DiscreteAction(str, Enum):
    """Discrete candidate resource adjustment actions produced by the AI module."""
    INCREASE_EMBB = "INCREASE_EMBB"
    MAINTAIN = "MAINTAIN"
    DECREASE_EMBB = "DECREASE_EMBB"


class GuardrailViolation(str, Enum):
    """Enumeration of standard guardrail constraint violations."""
    INVALID_ACTION = "INVALID_ACTION"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    CAPACITY_EXCEEDED = "CAPACITY_EXCEEDED"
    URLLC_MIN_BANDWIDTH_VIOLATION = "URLLC_MIN_BANDWIDTH_VIOLATION"
    URLLC_LATENCY_VIOLATION = "URLLC_LATENCY_VIOLATION"
    PACKET_LOSS_VIOLATION = "PACKET_LOSS_VIOLATION"
    SECURITY_RISK_EXCEEDED = "SECURITY_RISK_EXCEEDED"
    SECURITY_OVERHEAD_EXCEEDED = "SECURITY_OVERHEAD_EXCEEDED"


class SLASecurityGuardrail:
    """Pre-execution validation guardrail for SDN dynamic slicing."""

    def __init__(self, config: Optional[GuardrailConfig] = None):
        self.config = config or GuardrailConfig()

    def _normalize_allocation(self, alloc: Dict[str, Any]) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
        """Normalizes slice dictionary keys to canonical names: 'URLLC', 'eMBB', 'BE'."""
        canonical = {"URLLC": 0.0, "eMBB": 0.0, "BE": 0.0}
        found_keys = set()

        key_map = {
            "urllc": "URLLC",
            "embb": "eMBB",
            "be": "BE",
            "best_effort": "BE",
            "best-effort": "BE",
            "besteffort": "BE",
        }

        for k, v in alloc.items():
            norm_key = key_map.get(str(k).strip().lower())
            if not norm_key:
                return None, f"Unknown slice identifier '{k}' in candidate action"
            try:
                val = float(v)
                if val < 0.0:
                    return None, f"Bandwidth allocation for '{k}' cannot be negative ({val})"
                canonical[norm_key] = val
                found_keys.add(norm_key)
            except (ValueError, TypeError):
                return None, f"Non-numeric bandwidth value for '{k}': {v}"

        if not found_keys.issuperset({"URLLC", "eMBB", "BE"}):
            missing = {"URLLC", "eMBB", "BE"} - found_keys
            return None, f"Missing required slice allocations in candidate action: {list(missing)}"

        return canonical, None

    def map_candidate_action(
        self,
        candidate_action: Union[str, DiscreteAction, Dict[str, Any]],
        current_context: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, float]], Optional[str]]:
        """Maps discrete actions or validates explicit bandwidth dictionaries into canonical form.

        Args:
            candidate_action: String name, DiscreteAction enum, or dictionary with slice bandwidths.
            current_context: Context dictionary containing 'current_allocation' if available.

        Returns:
            Tuple of (canonical_bandwidth_dict, error_string_if_any).
        """
        # Case 1: Direct Bandwidth Allocation Dictionary
        if isinstance(candidate_action, dict):
            return self._normalize_allocation(candidate_action)

        # Case 2: Discrete Candidate Action
        action_str = str(candidate_action.value if isinstance(candidate_action, Enum) else candidate_action).strip().upper()

        # Retrieve current baseline allocation or fallback to project default safe baseline
        curr_alloc = current_context.get("current_allocation")
        if isinstance(curr_alloc, dict):
            base_alloc, err = self._normalize_allocation(curr_alloc)
            if err or base_alloc is None:
                base_alloc = {
                    "URLLC": self.config.urllc_min_bandwidth_mbps,
                    "eMBB": 4.0,
                    "BE": 3.0,
                }
        else:
            base_alloc = {
                "URLLC": 4.0,
                "eMBB": 4.0,
                "BE": 2.0,
            }

        step = self.config.discrete_bandwidth_step_mbps

        if action_str == DiscreteAction.MAINTAIN.value:
            return dict(base_alloc), None

        elif action_str == DiscreteAction.INCREASE_EMBB.value:
            candidate = dict(base_alloc)
            # Increase eMBB by step; reduce BE if possible to maintain capacity
            candidate["eMBB"] += step
            if candidate["BE"] >= step:
                candidate["BE"] -= step
            return candidate, None

        elif action_str == DiscreteAction.DECREASE_EMBB.value:
            candidate = dict(base_alloc)
            if candidate["eMBB"] >= (self.config.embb_min_bandwidth_mbps + step):
                candidate["eMBB"] -= step
                candidate["BE"] += step
            else:
                candidate["eMBB"] = max(self.config.embb_min_bandwidth_mbps, candidate["eMBB"] - step)
            return candidate, None

        else:
            return None, f"Unrecognized discrete action: '{candidate_action}'"

    def resolve_effective_latency(
        self,
        current_context: Dict[str, Any],
        security_state: Optional[SecurityState],
    ) -> Tuple[float, float, bool]:
        """Calculates effective URLLC latency avoiding double-counting of security overhead.

        Semantics:
            If context flag 'latency_includes_security' is True:
                The observed latency in context already includes security overhead.
                No security overhead is added.
            If context flag 'latency_includes_security' is False:
                The observed latency is baseline network latency. If security is ON,
                add security_state.latency_overhead_ms.

        Returns:
            Tuple of (effective_latency_ms, added_security_overhead_ms, includes_flag_value).
        """
        raw_latency = float(
            current_context.get("urllc_latency")
            or current_context.get("latency_ms")
            or current_context.get("latency", 0.0)
        )

        includes_sec = bool(
            current_context.get("latency_includes_security")
            or current_context.get("is_security_included", False)
        )

        added_overhead = 0.0
        if not includes_sec and security_state and security_state.is_enabled:
            added_overhead = float(security_state.latency_overhead_ms)

        effective_latency = raw_latency + added_overhead
        return effective_latency, added_overhead, includes_sec

    def _attempt_deterministic_repair(
        self,
        candidate_action: Union[str, DiscreteAction, Dict[str, Any]],
        current_context: Dict[str, Any],
        violations: List[str],
    ) -> Optional[Dict[str, float]]:
        """Performs simple, deterministic repair/fallback for allocation-only violations.

        NOTE: If violations include environmental SLA breaches (latency, loss, security risk),
        deterministic repair cannot override external network conditions and returns None.
        """
        unrepairable_violations = {
            GuardrailViolation.URLLC_LATENCY_VIOLATION.value,
            GuardrailViolation.PACKET_LOSS_VIOLATION.value,
            GuardrailViolation.SECURITY_RISK_EXCEEDED.value,
            GuardrailViolation.SECURITY_OVERHEAD_EXCEEDED.value,
            GuardrailViolation.MISSING_CONTEXT.value,
            GuardrailViolation.INVALID_ACTION.value,
        }

        # If any fundamental network SLA is violated, cannot repair
        if any(v in unrepairable_violations for v in violations):
            return None

        # Fallback for discrete actions: maintain current safe allocation
        if isinstance(candidate_action, (str, DiscreteAction)):
            curr_alloc = current_context.get("current_allocation")
            if isinstance(curr_alloc, dict):
                norm_curr, _ = self._normalize_allocation(curr_alloc)
                if norm_curr and sum(norm_curr.values()) <= self.config.total_bandwidth_capacity_mbps:
                    return norm_curr
            # Fallback to standard safe default
            return {
                "URLLC": self.config.urllc_min_bandwidth_mbps,
                "eMBB": 4.0,
                "BE": self.config.total_bandwidth_capacity_mbps - self.config.urllc_min_bandwidth_mbps - 4.0,
            }

        # Deterministic repair for continuous dictionary actions:
        # Guarantee URLLC minimum first, allocate eMBB, remainder to BE
        if isinstance(candidate_action, dict):
            mapped, err = self._normalize_allocation(candidate_action)
            if not mapped:
                return None

            cap = self.config.total_bandwidth_capacity_mbps
            urllc_alloc = max(mapped["URLLC"], self.config.urllc_min_bandwidth_mbps)
            remaining_cap = cap - urllc_alloc

            embb_alloc = min(max(mapped["eMBB"], self.config.embb_min_bandwidth_mbps), remaining_cap - self.config.be_min_bandwidth_mbps)
            be_alloc = max(self.config.be_min_bandwidth_mbps, remaining_cap - embb_alloc)

            return {
                "URLLC": round(urllc_alloc, 2),
                "eMBB": round(embb_alloc, 2),
                "BE": round(be_alloc, 2),
            }

        return None

    def validate(
        self,
        candidate_action: Union[str, DiscreteAction, Dict[str, Any]],
        current_context: Optional[Dict[str, Any]],
        security_state: Optional[SecurityState] = None,
        allow_repair: bool = False,
    ) -> Dict[str, Any]:
        """Validates candidate action against bandwidth, latency, loss, and security constraints.

        Args:
            candidate_action: Candidate allocation or discrete action.
            current_context: Observed network telemetry and context dictionary.
            security_state: Optional SecurityState object (OFF/ON and overhead profile).
            allow_repair: If True, simple deterministic repair/fallback is applied
                          for repairable allocation issues.

        Returns:
            Dictionary with structure:
            {
                "approved": bool,
                "action": Optional[Dict[str, float]],
                "reason": str,
                "violations": List[str],
                "is_repaired": bool,
                "metadata": Dict[str, Any]
            }
        """
        # 1. Validate Context Input
        if current_context is None or not isinstance(current_context, dict):
            return {
                "approved": False,
                "action": None,
                "reason": "Missing or invalid context dictionary provided to guardrail.",
                "violations": [GuardrailViolation.MISSING_CONTEXT.value],
                "is_repaired": False,
                "metadata": {},
            }

        # 2. Map and Normalize Action
        mapped_action, action_err = self.map_candidate_action(candidate_action, current_context)
        if action_err or mapped_action is None:
            return {
                "approved": False,
                "action": None,
                "reason": f"Invalid candidate action: {action_err}",
                "violations": [GuardrailViolation.INVALID_ACTION.value],
                "is_repaired": False,
                "metadata": {},
            }

        # Ensure a default SecurityState if none provided
        sec_state = security_state or SecurityState.create_off()

        violations: List[str] = []
        reasons: List[str] = []

        # 3. Check Total Bandwidth Capacity (10.0 Mbps constraint)
        total_bandwidth = sum(mapped_action.values())
        if total_bandwidth > self.config.total_bandwidth_capacity_mbps + 1e-6:
            violations.append(GuardrailViolation.CAPACITY_EXCEEDED.value)
            reasons.append(
                f"Total bandwidth {total_bandwidth:.2f} Mbps exceeds link capacity "
                f"{self.config.total_bandwidth_capacity_mbps:.2f} Mbps."
            )

        # 4. Check URLLC Minimum Bandwidth Guarantee
        if mapped_action["URLLC"] < self.config.urllc_min_bandwidth_mbps - 1e-6:
            violations.append(GuardrailViolation.URLLC_MIN_BANDWIDTH_VIOLATION.value)
            reasons.append(
                f"URLLC allocated {mapped_action['URLLC']:.2f} Mbps is below minimum SLA guarantee "
                f"of {self.config.urllc_min_bandwidth_mbps:.2f} Mbps."
            )

        # 5. Check URLLC Latency SLA (15.0 ms constraint) with clear semantics
        effective_latency, added_overhead, includes_sec = self.resolve_effective_latency(
            current_context, sec_state
        )
        if effective_latency > self.config.urllc_latency_sla_ms + 1e-6:
            violations.append(GuardrailViolation.URLLC_LATENCY_VIOLATION.value)
            reasons.append(
                f"Effective URLLC latency {effective_latency:.2f} ms exceeds SLA threshold "
                f"of {self.config.urllc_latency_sla_ms:.2f} ms."
            )

        # 6. Check Packet Loss SLA
        packet_loss = float(
            current_context.get("urllc_loss")
            or current_context.get("packet_loss_pct")
            or current_context.get("packet_loss", 0.0)
        )
        if packet_loss > self.config.max_packet_loss_pct + 1e-6:
            violations.append(GuardrailViolation.PACKET_LOSS_VIOLATION.value)
            reasons.append(
                f"Packet loss {packet_loss:.2f}% exceeds SLA maximum limit of "
                f"{self.config.max_packet_loss_pct:.2f}%."
            )

        # 7. Check Security Risk Level
        if sec_state.risk_level > self.config.max_security_risk + 1e-6:
            violations.append(GuardrailViolation.SECURITY_RISK_EXCEEDED.value)
            reasons.append(
                f"Security risk level {sec_state.risk_level:.2f} exceeds safety threshold "
                f"of {self.config.max_security_risk:.2f}."
            )

        # 8. Check Security Latency Overhead Limit
        if sec_state.is_enabled and sec_state.latency_overhead_ms > self.config.max_allowed_security_overhead_ms + 1e-6:
            violations.append(GuardrailViolation.SECURITY_OVERHEAD_EXCEEDED.value)
            reasons.append(
                f"Security latency overhead {sec_state.latency_overhead_ms:.2f} ms exceeds allowed limit "
                f"of {self.config.max_allowed_security_overhead_ms:.2f} ms."
            )

        metadata = {
            "candidate_action_raw": str(candidate_action),
            "effective_urllc_latency_ms": round(effective_latency, 2),
            "added_security_overhead_ms": round(added_overhead, 2),
            "latency_includes_security": includes_sec,
            "total_allocated_bandwidth_mbps": round(total_bandwidth, 2),
            "security_mode": sec_state.mode.value,
            "security_risk": sec_state.risk_level,
            "security_is_measured": sec_state.is_measured,
        }

        # 9. Handle Violations or Approval
        if not violations:
            return {
                "approved": True,
                "action": mapped_action,
                "reason": "Action complies with all capacity, SLA, and security constraints.",
                "violations": [],
                "is_repaired": False,
                "metadata": metadata,
            }

        # Attempt simple deterministic repair if requested
        if allow_repair:
            repaired_action = self._attempt_deterministic_repair(
                candidate_action, current_context, violations
            )
            if repaired_action:
                metadata["original_action"] = mapped_action
                return {
                    "approved": True,
                    "action": repaired_action,
                    "reason": f"Action was repaired to satisfy capacity constraints. Original violations: {'; '.join(reasons)}",
                    "violations": violations,
                    "is_repaired": True,
                    "metadata": metadata,
                }

        return {
            "approved": False,
            "action": None,
            "reason": "; ".join(reasons),
            "violations": violations,
            "is_repaired": False,
            "metadata": metadata,
        }
