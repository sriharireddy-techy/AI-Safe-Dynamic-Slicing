"""Lightweight WireGuard adapter for Module 5.

Provides an interface to check WireGuard availability, interface status,
and configuration in Linux/Mininet environments, with graceful fallback
when WireGuard tools are not present.
"""

import shutil
import subprocess
import sys
from typing import Any, Dict, Optional


class WireGuardAdapter:
    """Lightweight WireGuard interface checker and configuration helper.

    Operates safely across platforms (Windows / WSL / Linux) and handles
    environments where WireGuard tools ('wg', 'wg-quick') are not installed.
    """

    def __init__(self, interface_name: str = "wg0"):
        self.interface_name = interface_name

    @staticmethod
    def is_available() -> bool:
        """Checks if the WireGuard CLI command 'wg' is installed and executable."""
        return shutil.which("wg") is not None

    @staticmethod
    def is_wg_quick_available() -> bool:
        """Checks if 'wg-quick' helper script is installed and executable."""
        return shutil.which("wg-quick") is not None

    def get_status(self) -> Dict[str, Any]:
        """Queries the current status of the WireGuard interface safely.

        Returns:
            Dictionary describing availability, operational status, and details.
        """
        if not self.is_available():
            return {
                "available": False,
                "interface": self.interface_name,
                "active": False,
                "reason": "WireGuard CLI ('wg') not found on system PATH",
                "details": None,
            }

        try:
            # Query interface via 'wg show <interface>'
            result = subprocess.run(
                ["wg", "show", self.interface_name],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if result.returncode == 0:
                return {
                    "available": True,
                    "interface": self.interface_name,
                    "active": True,
                    "reason": "Interface active",
                    "details": result.stdout.strip(),
                }
            return {
                "available": True,
                "interface": self.interface_name,
                "active": False,
                "reason": f"Interface not active: {result.stderr.strip() or 'Unknown error'}",
                "details": None,
            }
        except Exception as exc:
            return {
                "available": True,
                "interface": self.interface_name,
                "active": False,
                "reason": f"Execution error: {str(exc)}",
                "details": None,
            }

    @staticmethod
    def generate_sample_config(
        private_key: str = "<PRIVATE_KEY>",
        address: str = "10.0.0.1/24",
        listen_port: int = 51820,
        peer_public_key: str = "<PEER_PUBLIC_KEY>",
        peer_endpoint: str = "10.0.0.4:51820",
        allowed_ips: str = "10.0.0.0/24",
    ) -> str:
        """Generates a standard WireGuard peer configuration template."""
        return (
            "[Interface]\n"
            f"PrivateKey = {private_key}\n"
            f"Address = {address}\n"
            f"ListenPort = {listen_port}\n\n"
            "[Peer]\n"
            f"PublicKey = {peer_public_key}\n"
            f"Endpoint = {peer_endpoint}\n"
            f"AllowedIPs = {allowed_ips}\n"
        )
