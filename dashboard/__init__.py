"""
Web Dashboard Package (Phase 11)
================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks
"""

from dashboard.data_loader import (
    load_telemetry,
    load_benchmark_csvs,
    load_summary_table_markdown,
    get_available_plots,
    check_live_data_plane_status,
)

__all__ = [
    "load_telemetry",
    "load_benchmark_csvs",
    "load_summary_table_markdown",
    "get_available_plots",
    "check_live_data_plane_status",
]
