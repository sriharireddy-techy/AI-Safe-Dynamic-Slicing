"""Module 6: SLA/Security Guardrail package for AI-Safe Dynamic Slicing.

Provides pre-execution validation for candidate network slicing actions,
verifying total capacity, URLLC minimum reservations, latency SLAs,
packet loss limits, security overhead, and security threat constraints.
"""

from guardrail.sla_config import GuardrailConfig
from guardrail.guardrail import (
    DiscreteAction,
    GuardrailViolation,
    SLASecurityGuardrail,
)

__all__ = [
    "GuardrailConfig",
    "DiscreteAction",
    "GuardrailViolation",
    "SLASecurityGuardrail",
]
