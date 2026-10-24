"""
Phase 11: Web Dashboard Test Suite
==================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

Verifies:
1. Robust telemetry loading from CSV with valid and sentinel records.
2. Definite separation of genuine measurements from unreachable (-1.0) records.
3. Accurate statistical summary calculation on valid data only.
4. Handling of non-existent or corrupted telemetry files.
5. Benchmark CSV loading (Static, Dynamic Unsafe, Proposed AI-Safe).
6. Summary table markdown ingestion.
7. Benchmark plot path retrieval.
8. Non-intrusive live data plane status detection.
9. Dashboard app file syntax and module import validity.
"""

import os
import tempfile
import pytest
import pandas as pd
from pathlib import Path
from dashboard.data_loader import (
    load_telemetry,
    load_benchmark_csvs,
    load_summary_table_markdown,
    get_available_plots,
    check_live_data_plane_status,
)


# ==============================================================================
# 1. TELEMETRY LOADER TESTS
# ==============================================================================

def test_load_telemetry_existing_file():
    """Verifies that the project's actual data/telemetry.csv loads successfully."""
    valid_df, invalid_df, summary = load_telemetry()
    assert summary["exists"] is True
    assert summary["total_records"] > 0
    assert summary["valid_records"] > 0
    assert summary["valid_records"] + summary["invalid_records"] == summary["total_records"]
    assert summary["mean_latency_ms"] is not None
    assert summary["mean_latency_ms"] > 0.0


def test_load_telemetry_omits_sentinel_negative_one():
    """Verifies that records with urllc_latency_ms == -1.0 are placed in invalid_df and excluded from mean."""
    # Create temporary CSV with mixed valid and -1.0 records
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("timestamp,urllc_latency_ms,throughput_mbps,urllc_packet_loss,queue_occupancy\n")
        f.write("100.0,10.0,5.0,0.0,2\n")
        f.write("101.0,-1.0,0.0,100.0,0\n")  # Unreachable sentinel
        f.write("102.0,12.0,6.0,0.0,3\n")
        f.write("103.0,-1.0,0.0,100.0,0\n")  # Unreachable sentinel
        temp_path = f.name

    try:
        valid_df, invalid_df, summary = load_telemetry(temp_path)
        assert summary["total_records"] == 4
        assert summary["valid_records"] == 2
        assert summary["invalid_records"] == 2
        # Mean latency should only be (10.0 + 12.0) / 2 = 11.0, NOT dragged down by -1.0
        assert summary["mean_latency_ms"] == pytest.approx(11.0, 1e-4)
        assert summary["min_latency_ms"] == 10.0
        assert summary["max_latency_ms"] == 12.0
        assert len(invalid_df) == 2
        assert (invalid_df["urllc_latency_ms"] == -1.0).all()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_load_telemetry_missing_file():
    """Verifies graceful handling when file does not exist."""
    valid_df, invalid_df, summary = load_telemetry("non_existent_path_xyz.csv")
    assert summary["exists"] is False
    assert summary["total_records"] == 0
    assert summary["valid_records"] == 0
    assert summary["mean_latency_ms"] is None
    assert valid_df.empty
    assert invalid_df.empty


def test_load_telemetry_corrupted_empty_file():
    """Verifies handling of empty file without blowing up."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("")
        temp_path = f.name

    try:
        valid_df, invalid_df, summary = load_telemetry(temp_path)
        assert valid_df.empty
        assert invalid_df.empty
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ==============================================================================
# 2. BENCHMARK CSV & RESULT LOADER TESTS
# ==============================================================================

def test_load_benchmark_csvs():
    """Verifies loading of Module 9 benchmark CSV files."""
    datasets = load_benchmark_csvs()
    assert "static" in datasets
    assert "dynamic" in datasets
    assert "proposed" in datasets

    # Actual results exist in results/
    assert not datasets["proposed"].empty
    assert "urllc_alloc_mbps" in datasets["proposed"].columns
    assert "simulated_urllc_rtt_ms" in datasets["proposed"].columns


def test_load_benchmark_csvs_missing_dir():
    """Verifies graceful fallback for missing benchmark directory."""
    datasets = load_benchmark_csvs("non_existent_results_dir_xyz")
    assert datasets["static"].empty
    assert datasets["dynamic"].empty
    assert datasets["proposed"].empty


def test_load_summary_table_markdown():
    """Verifies summary table markdown is readable."""
    md = load_summary_table_markdown()
    assert md is not None
    assert "Simulation Benchmark Performance Summary Table" in md
    assert "Static Slicing" in md
    assert "Proposed System" in md


def test_get_available_plots():
    """Verifies retrieval of evaluation plot paths."""
    plots = get_available_plots()
    assert "comparison" in plots
    assert "latency" in plots
    assert "throughput" in plots
    # All 3 plots exist in results/
    assert plots["comparison"] is not None
    assert plots["latency"] is not None
    assert plots["throughput"] is not None


# ==============================================================================
# 3. LIVE STATUS CHECK TESTS
# ==============================================================================

def test_check_live_data_plane_status_non_intrusive():
    """Verifies non-intrusive checking does not throw exception."""
    status = check_live_data_plane_status("s1-eth4")
    assert isinstance(status, dict)
    assert "is_live" in status
    assert "mode" in status
    assert "interface" in status
    assert status["interface"] == "s1-eth4"


# ==============================================================================
# 5. REGRESSION TESTS FOR PHASE 11 BUGS
# ==============================================================================

def test_regression_bug1_linucb_diagnostic_structure():
    """Bug 1 Regression: Verifies SRALinUCB diagnostics return structure matches dashboard expectations.

    Ensures no KeyError: 'actions' occurs and that scores, means, uncertainties,
    and risk penalties are present for all arms.
    """
    import numpy as np
    from ai.linucb import SRALinUCB, ACTION_NAMES

    bandit = SRALinUCB(alpha=0.3, risk_lambda=0.5)
    context = np.array([1.0, 0.25, 0.65, 0.1, 0.0, 0.01])  # 6D context vector

    selected_action, diagnostics = bandit.select_action(context)

    # Must NOT have 'actions' key (which caused the KeyError)
    assert "actions" not in diagnostics

    # Must contain canonical keys
    assert "context_risk" in diagnostics
    assert "scores" in diagnostics
    assert "means" in diagnostics
    assert "uncertainties" in diagnostics
    assert "risk_penalties" in diagnostics
    assert "selected_action" in diagnostics
    assert "selected_action_name" in diagnostics

    # Diagnostic table generation must succeed for all 3 arms without KeyError
    diag_rows = []
    for act_idx in [0, 1, 2]:
        act_name = ACTION_NAMES[act_idx]
        mean_val = diagnostics["means"][act_idx]
        bonus_val = diagnostics["uncertainties"][act_idx]
        std_ucb_val = mean_val + bonus_val
        risk_pen_val = diagnostics["risk_penalties"][act_idx]
        score_val = diagnostics["scores"][act_idx]

        diag_rows.append({
            "Action Index": act_idx,
            "Action Name": act_name,
            "Estimated Reward (Mean)": mean_val,
            "Exploration Bonus": bonus_val,
            "Standard UCB": std_ucb_val,
            "Risk Penalty": risk_pen_val,
            "Final SRA Score": score_val,
            "Selected": act_idx == selected_action,
        })

    assert len(diag_rows) == 3


def test_regression_bug2_security_mode_members():
    """Bug 2 Regression: Verifies SecurityMode has valid members and does not raise AttributeError: STANDARD."""
    from security.security_config import SecurityMode, SecurityState
    from guardrail.guardrail import SLASecurityGuardrail

    # Members must be OFF and ON
    assert hasattr(SecurityMode, "OFF")
    assert hasattr(SecurityMode, "ON")
    assert not hasattr(SecurityMode, "STANDARD")  # Confirm obsolete name is not used

    # Test factory creations
    state_off = SecurityState.create_off()
    state_on = SecurityState.create_on_default()

    assert state_off.mode == SecurityMode.OFF
    assert state_off.latency_overhead_ms == 0.0
    assert state_on.mode == SecurityMode.ON
    assert state_on.latency_overhead_ms > 0.0

    # Test compatibility with SLASecurityGuardrail.validate
    guardrail = SLASecurityGuardrail()
    candidate = {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0}
    context = {"latency_ms": 11.0, "packet_loss_pct": 0.1, "throughput_mbps": 6.0}

    # Must evaluate cleanly for both security states without AttributeError
    res_off = guardrail.validate(candidate, context, security_state=state_off)
    assert res_off["approved"] is True

    res_on = guardrail.validate(candidate, context, security_state=state_on)
    assert res_on["approved"] is True


def test_regression_bug3_data_plane_verification_stages():
    """Bug 3 Regression: Verifies three-stage environment status logic non-intrusively.

    Stage 1: Interface missing -> OFFLINE_SIMULATION, is_verified_live=False.
    Stage 2: Interface exists but HTB classes missing -> INTERFACE_ONLY_UNCONFIGURED, is_verified_live=False.
    Stage 3: Classes present but rates unverified -> CLASSES_PRESENT_UNVERIFIED_RATES, is_verified_live=False.
    Stage 4: Classes present AND applied rates confirmed -> LIVE_VERIFIED, is_verified_live=True.
    """
    from dashboard.data_loader import check_live_data_plane_status

    # Stage 1: Interface does not exist (mock failure)
    def runner_no_interface(cmd):
        return 1, "", "Device does not exist"

    s1 = check_live_data_plane_status("s1-eth4", command_runner=runner_no_interface)
    assert s1["status"] == "OFFLINE_SIMULATION"
    assert s1["is_verified_live"] is False
    assert s1["interface_exists"] is False
    assert "Offline" in s1["mode"]

    # Stage 2: Interface exists, but child classes (1:10, 1:20, 1:30) are missing
    def runner_interface_only(cmd):
        if "qdisc" in cmd:
            return 0, "qdisc htb 1: root refcnt 2", ""
        if "class" in cmd:
            return 0, "class htb 1:1 root prio 0 rate 10Mbit", ""  # Missing child classes 1:10, 1:20, 1:30
        return 0, "", ""

    s2 = check_live_data_plane_status("s1-eth4", command_runner=runner_interface_only)
    assert s2["status"] == "INTERFACE_ONLY_UNCONFIGURED"
    assert s2["is_verified_live"] is False
    assert s2["interface_exists"] is True
    assert s2["classes_present"] is False
    assert "Unverified" in s2["mode"]

    # Stage 3: Child classes 1:10, 1:20, 1:30 exist, but rate change has not been verified
    def runner_classes_present(cmd):
        if "qdisc" in cmd:
            return 0, "qdisc htb 1: root refcnt 2", ""
        if "class" in cmd:
            return 0, """
class htb 1:10 parent 1:1 rate 3Mbit ceil 10Mbit
class htb 1:20 parent 1:1 rate 5Mbit ceil 10Mbit
class htb 1:30 parent 1:1 rate 2Mbit ceil 10Mbit
""", ""
        return 0, "", ""

    s3 = check_live_data_plane_status("s1-eth4", command_runner=runner_classes_present)
    assert s3["status"] == "CLASSES_PRESENT_UNVERIFIED_RATES"
    assert s3["is_verified_live"] is False
    assert s3["interface_exists"] is True
    assert s3["classes_present"] is True
    assert s3["enforcement_verified"] is False
    assert "Unverified" in s3["mode"]

    # Stage 4: Classes present AND rates confirmed via verified allocation
    verified_alloc = {"URLLC": 3.0, "eMBB": 5.0, "BE": 2.0}
    s4 = check_live_data_plane_status(
        "s1-eth4", command_runner=runner_classes_present, verified_applied_allocation=verified_alloc
    )
    assert s4["status"] == "LIVE_VERIFIED"
    assert s4["is_verified_live"] is True
    assert s4["enforcement_verified"] is True
    assert "Live" in s4["mode"]


def test_all_six_sections_execution_logic():
    """Verifies that all logic across all 6 sections executes cleanly without exceptions."""
    import numpy as np
    from ai.context_builder import ContextBuilder
    from ai.linucb import SRALinUCB, ACTION_NAMES
    from guardrail.guardrail import SLASecurityGuardrail
    from security.security_config import SecurityState, SecurityMode
    from controller.slicing_actuator import SlicingActuator

    # Section 1 logic: slice table definition
    slice_data = [{"Slice Type": "URLLC", "Queue ID": "Queue 0"}]
    df_slice = pd.DataFrame(slice_data)
    assert not df_slice.empty

    # Section 2 logic: telemetry loading
    valid_df, invalid_df, summary = load_telemetry()
    assert summary["exists"] is True

    # Section 3 logic: ContextBuilder and SRALinUCB diagnostic extraction
    builder = ContextBuilder()
    builder.prev_latency = 12.0
    x_t = builder.build_context({
        "urllc_latency_ms": 12.5,
        "urllc_packet_loss": 0.1,
        "throughput_mbps": 6.5,
        "queue_occupancy": 5,
    })
    bandit = SRALinUCB(alpha=0.3, risk_lambda=0.5)
    action_idx, diag = bandit.select_action(x_t)
    assert action_idx in [0, 1, 2]
    # Build diag rows exactly as app.py does
    diag_rows = []
    for a in [0, 1, 2]:
        diag_rows.append({
            "idx": a,
            "mean": diag["means"][a],
            "bonus": diag["uncertainties"][a],
            "std_ucb": diag["means"][a] + diag["uncertainties"][a],
            "risk": diag["risk_penalties"][a],
            "score": diag["scores"][a],
        })
    assert len(diag_rows) == 3

    # Section 4 logic: SLASecurityGuardrail with both SecurityState modes
    guardrail = SLASecurityGuardrail()
    for state in [SecurityState.create_off(), SecurityState.create_on_default()]:
        dec = guardrail.validate(
            candidate_action={"URLLC": 2.0, "eMBB": 6.5, "BE": 1.5},
            current_context={"latency_ms": 12.0, "packet_loss_pct": 0.2, "throughput_mbps": 7.0},
            security_state=state,
            allow_repair=True,
        )
        assert dec["approved"] is True
        assert dec["is_repaired"] is True
        assert dec["action"]["URLLC"] >= 3.0

    # Section 5 logic: Benchmarks & plots retrieval
    benchmarks = load_benchmark_csvs()
    assert "proposed" in benchmarks
    plots = get_available_plots()
    assert "comparison" in plots

    # Section 6 logic: Actuator dry-run execution and classification rules
    actuator = SlicingActuator(interface="s1-eth4", dry_run=True)
    res = actuator.apply_allocation({
        "approved": True,
        "action": {"URLLC": 3.5, "eMBB": 4.5, "BE": 2.0},
        "is_repaired": False,
    })
    assert res.success is True
    rules = actuator.build_classification_rules()
    assert len(rules) == 3


def test_expected_htb_parent_and_class_ids_match_actuator():
    """Verifies that dashboard data loader uses the identical class IDs as SlicingActuator."""
    from dashboard.data_loader import REQUIRED_SLICE_CLASSES
    from controller.slicing_actuator import SLICE_CLASS_MAP

    for slice_name, classid in REQUIRED_SLICE_CLASSES.items():
        assert slice_name in SLICE_CLASS_MAP
        assert SLICE_CLASS_MAP[slice_name]["classid"] == classid


def test_dashboard_app_smoke_all_sections():
    """Live smoke test using Streamlit AppTest to verify all 6 navigation sections render with 0 exceptions."""
    from streamlit.testing.v1 import AppTest

    sections = [
        "1. Overview & Topology",
        "2. Telemetry Monitoring",
        "3. AI Decision Engine",
        "4. Security & SLA Guardrail",
        "5. Evaluation & Benchmarks",
        "6. Actuator & Data Plane",
    ]
    app_file = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")
    at = AppTest.from_file(app_file, default_timeout=15)
    at.run()
    assert len(at.exception) == 0

    for sec in sections:
        at.sidebar.radio[0].set_value(sec)
        at.run()
        assert len(at.exception) == 0, f"Exception occurred in section '{sec}': {at.exception}"



