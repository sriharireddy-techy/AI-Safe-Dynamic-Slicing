"""
AI-Driven Safe Dynamic Network Slicing Web Dashboard (Phase 11)
==============================================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

A professional, interactive Streamlit dashboard designed for technical defense
and faculty presentations.

Key Capabilities:
1. Overview: Multi-tenant topology, QoS profiles, and architectural pipeline.
2. Telemetry: Live/trace time-series, latency thresholding, and unreachable sample auditing.
3. AI Decision: Live 6-feature context vector construction and SRA-LinUCB diagnostic scoring.
4. Security & SLA: Deterministic guardrail approval, violation analysis, and repair.
5. Evaluation: Trace-driven simulation benchmark comparison (Static vs Unsafe vs Proposed).
6. Actuator: Phase 10 tc HTB class generation, classification rules, and read-back verification.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
import streamlit as st

# Add workspace root to Python path for direct imports of project modules
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from ai.context_builder import ContextBuilder
from ai.linucb import SRALinUCB, ACTION_NAMES
from guardrail.guardrail import SLASecurityGuardrail, DiscreteAction
from guardrail.sla_config import GuardrailConfig
from security.security_config import SecurityState, SecurityMode
from slicing.slice_config import DEFAULT_SLICING_CONFIG
from controller.slicing_actuator import (
    SlicingActuator,
    ActuatorStatus,
    KNOWN_SAFE_ALLOCATION,
    TOTAL_CAPACITY_MBPS,
    URLLC_MIN_RESERVATION_MBPS,
    SLICE_CLASS_MAP,
)
from dashboard.data_loader import (
    load_telemetry,
    load_benchmark_csvs,
    load_summary_table_markdown,
    get_available_plots,
    check_live_data_plane_status,
)


# ==============================================================================
# STREAMLIT PAGE CONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="AI-Safe SDN Network Slicing Dashboard",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .status-badge-live {
        background-color: #D1FAE5;
        color: #065F46;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
    }
    .status-badge-sim {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-block;
    }
    .metric-card {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #111827;
    }
    .metric-lbl {
        font-size: 0.85rem;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SIDEBAR NAVIGATION & RUNTIME ENVIRONMENT DETECTION
# ==============================================================================
live_status = check_live_data_plane_status()

st.sidebar.title("🎛️ Navigation")
section = st.sidebar.radio(
    "Select System View:",
    [
        "1. Overview & Topology",
        "2. Telemetry Monitoring",
        "3. AI Decision Engine",
        "4. Security & SLA Guardrail",
        "5. Evaluation & Benchmarks",
        "6. Actuator & Data Plane",
    ],
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📡 Environment Status")
if live_status.get("is_verified_live", False):
    st.sidebar.markdown(f'<div class="status-badge-live">● {live_status["mode"]}</div>', unsafe_allow_html=True)
    st.sidebar.caption(f"Interface: `{live_status['interface']}` — {live_status['details']}")
else:
    st.sidebar.markdown(f'<div class="status-badge-sim">○ {live_status["mode"]}</div>', unsafe_allow_html=True)
    st.sidebar.caption(f"{live_status['details']}\n\n*Actuator defaults to Dry-Run mode to prevent unverified network mutations.*")

st.sidebar.markdown("---")
st.sidebar.markdown(r"""
**Project:** AI-Driven Safe Dynamic Slicing  
**Topology:** 2 OVS Switches (s1, s2), 6 Hosts  
**Bottleneck Link:** 10.0 Mbps, 5 ms delay  
**Safety Floor:** URLLC $\ge$ 3.0 Mbps  
""")


# ==============================================================================
# SECTION 1: OVERVIEW & TOPOLOGY
# ==============================================================================
if section == "1. Overview & Topology":
    st.markdown('<div class="main-title">Network Architecture & Slicing Topology</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Multi-tenant network slicing on OpenFlow 1.3 Open vSwitch data plane with deterministic safety</div>', unsafe_allow_html=True)

    # Topology Summary Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-val">10.0 Mbps</div>
            <div class="metric-lbl">Bottleneck Capacity (s1-eth4)</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-val">&le; 15.0 ms</div>
            <div class="metric-lbl">URLLC Latency SLA</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-val">&le; 1.0 %</div>
            <div class="metric-lbl">URLLC Packet Loss SLA</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown("""
        <div class="metric-card">
            <div class="metric-val">&ge; 3.0 Mbps</div>
            <div class="metric-lbl">URLLC Safety Floor</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### 🏷️ Multi-Tenant Slice Configuration")
    slice_data = [
        {
            "Slice Type": "URLLC (Mission-Critical)",
            "Endpoints": "h1 (10.0.0.1) ↔ h4 (10.0.0.4)",
            "Queue ID": "Queue 0",
            "HTB Class": "1:10",
            "Priority": "0 (Highest)",
            "Min Guaranteed Bandwidth": "3.0 Mbps (Floor)",
            "Latency SLA": "≤ 15.0 ms RTT",
            "Loss SLA": "≤ 1.0 %",
        },
        {
            "Slice Type": "eMBB (High Throughput)",
            "Endpoints": "h2 (10.0.0.2) ↔ h5 (10.0.0.5)",
            "Queue ID": "Queue 1",
            "HTB Class": "1:20",
            "Priority": "1 (Medium)",
            "Min Guaranteed Bandwidth": "1.0 Mbps",
            "Latency SLA": "Best-Effort (Elastic)",
            "Loss SLA": "Elastic",
        },
        {
            "Slice Type": "Best-Effort (Background)",
            "Endpoints": "h3 (10.0.0.3) ↔ h6 (10.0.0.6)",
            "Queue ID": "Queue 2",
            "HTB Class": "1:30",
            "Priority": "2 (Lowest)",
            "Min Guaranteed Bandwidth": "0.5 Mbps",
            "Latency SLA": "N/A",
            "Loss SLA": "N/A",
        },
    ]
    st.table(pd.DataFrame(slice_data))

    st.markdown("### 🔄 End-to-End Control Pipeline")
    st.info(r"""
    **Closed-Loop Safety Workflow:**  
    1. **Physical Telemetry (Module 2):** Periodic probing extracts latency, throughput, queue occupancy, and packet loss.  
    2. **Context Builder (Module 3):** Normalizes telemetry into a sanitized 6D context vector $\mathbf{x}_t \in \mathbb{R}^6$.  
    3. **SRA-LinUCB (Module 4):** Contextual bandit scores candidate actions balancing exploration, exploitation, and risk penalty $\lambda \rho_a R(\mathbf{x}_t)$.  
    4. **Deterministic Guardrail (Module 6):** Mathematical validation checks total link capacity, minimum reservation floors, latency/loss SLAs, and security overhead. Unsafe proposals are deterministically repaired or rejected.  
    5. **Actuator (Module 10):** Enforces approved rates via Linux `tc` HTB classes, sets OpenFlow queue classification, and reads back applied kernel rates.  
    6. **Feedback Learner (Module 7):** Receives reward signal and updates LinUCB ridge regression matrices $(A_a, b_a)$.
    """)


# ==============================================================================
# SECTION 2: TELEMETRY MONITORING
# ==============================================================================
elif section == "2. Telemetry Monitoring":
    st.markdown('<div class="main-title">Telemetry & Network Health Monitoring</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Live measurements and historical trace logs from data/telemetry.csv</div>', unsafe_allow_html=True)

    valid_df, invalid_df, summary = load_telemetry()

    if not summary["exists"]:
        st.warning("⚠️ Telemetry data file `data/telemetry.csv` was not found. Please run the telemetry monitor or simulation.")
    else:
        # High-level metric summary
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Total Records", f"{summary['total_records']}")
        with c2:
            st.metric("Valid Measurements", f"{summary['valid_records']}")
        with c3:
            st.metric("Unreachable (-1.0)", f"{summary['invalid_records']}", delta=f"{summary['invalid_records']} dropped" if summary['invalid_records'] > 0 else "0", delta_color="inverse")
        with c4:
            st.metric("Mean Latency", f"{summary['mean_latency_ms']:.2f} ms" if summary['mean_latency_ms'] else "N/A")
        with c5:
            st.metric("P99 Latency", f"{summary['p99_latency_ms']:.2f} ms" if summary['p99_latency_ms'] else "N/A")

        if summary['invalid_records'] > 0:
            st.error(f"⚠️ **Data Integrity Note:** Found {summary['invalid_records']} telemetry records with sentinel value `-1.0` (host unreachable). These are strictly excluded from genuine latency statistics and never substituted with synthetic numbers.")

        st.markdown("---")
        st.markdown("### 📈 Telemetry Time-Series")

        if not valid_df.empty:
            # Sample slice selector
            max_rows = len(valid_df)
            window_size = st.slider("Select view window (recent samples):", min_value=10, max_value=max(10, max_rows), value=min(150, max_rows))
            display_df = valid_df.tail(window_size).reset_index(drop=True)

            tab1, tab2, tab3, tab4 = st.tabs(["URLLC Latency (ms)", "Bottleneck Throughput (Mbps)", "Packet Loss (%)", "Queue Occupancy (pkts)"])

            with tab1:
                st.caption("URLLC Round-Trip Latency over time. Red dashed line indicates the 15.0 ms SLA ceiling.")
                chart_df = pd.DataFrame({
                    "Latency (ms)": display_df["urllc_latency_ms"],
                    "SLA Threshold (15 ms)": 15.0,
                })
                st.line_chart(chart_df, color=["#2563EB", "#DC2626"])

            with tab2:
                st.caption("Total Bottleneck Throughput. Red dashed line indicates the 10.0 Mbps physical link capacity.")
                chart_df = pd.DataFrame({
                    "Throughput (Mbps)": display_df["throughput_mbps"],
                    "Link Capacity (10 Mbps)": 10.0,
                })
                st.line_chart(chart_df, color=["#10B981", "#DC2626"])

            with tab3:
                st.caption("Observed Packet Loss percentage.")
                st.line_chart(display_df[["urllc_packet_loss"]], color=["#F59E0B"])

            with tab4:
                st.caption("Bottleneck Buffer Queue Occupancy (packets). Normal buffer ceiling is 50 pkts.")
                st.line_chart(display_df[["queue_occupancy"]], color=["#8B5CF6"])

            with st.expander("🔍 Inspect Raw Telemetry Data Table"):
                st.dataframe(display_df)

        if not invalid_df.empty:
            with st.expander("🚨 View Omitted Unreachable / Sentinel Records (-1.0)"):
                st.dataframe(invalid_df)


# ==============================================================================
# SECTION 3: AI DECISION ENGINE
# ==============================================================================
elif section == "3. AI Decision Engine":
    st.markdown('<div class="main-title">Contextual Bandit Decision Engine (Module 3 & 4)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">SRA-LinUCB (Security- and Risk-Aware LinUCB) candidate action selection with transparent diagnostic breakdown</div>', unsafe_allow_html=True)

    st.markdown("### 🎛️ Interactive Faculty Demo Simulator")
    st.caption("Adjust physical network conditions below to observe live 6-feature context vector construction and SRA-LinUCB decision scoring:")

    sim_col1, sim_col2, sim_col3 = st.columns(3)
    with sim_col1:
        inp_latency = st.slider("Observed URLLC Latency (ms):", min_value=5.0, max_value=40.0, value=12.5, step=0.5)
        inp_loss = st.slider("URLLC Packet Loss (%):", min_value=0.0, max_value=10.0, value=0.1, step=0.1)
    with sim_col2:
        inp_tput = st.slider("Bottleneck Throughput (Mbps):", min_value=0.0, max_value=10.0, value=6.5, step=0.1)
        inp_queue = st.slider("Buffer Queue Occupancy (pkts):", min_value=0, max_value=50, value=5, step=1)
    with sim_col3:
        inp_trend = st.slider("Latency Trend / Velocity (ms/s):", min_value=-5.0, max_value=5.0, value=0.5, step=0.1)
        inp_alpha = st.slider("LinUCB Exploration Bonus (alpha):", min_value=0.0, max_value=1.0, value=0.3, step=0.05)

    # Ingest into actual Module 3 ContextBuilder
    builder = ContextBuilder(max_latency=50.0, max_throughput=10.0, max_queue=50.0)
    builder.prev_latency = inp_latency - inp_trend

    synthetic_record = {
        "urllc_latency_ms": inp_latency,
        "urllc_packet_loss": inp_loss,
        "throughput_mbps": inp_tput,
        "queue_occupancy": inp_queue,
    }
    x_t = builder.build_context(synthetic_record)

    st.markdown("---")
    st.markdown(r"### 🧬 Normalized Context Vector ($\mathbf{x}_t \in \mathbb{R}^6$)")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("x0: Bias", f"{x_t[0]:.2f}")
    with c2:
        st.metric("x1: Latency", f"{x_t[1]:.3f}")
    with c3:
        st.metric("x2: Throughput", f"{x_t[2]:.3f}")
    with c4:
        st.metric("x3: Queue", f"{x_t[3]:.3f}")
    with c5:
        st.metric("x4: Trend", f"{x_t[4]:.3f}")
    with c6:
        st.metric("x5: Loss", f"{x_t[5]:.3f}")

    # Ingest into actual Module 4 SRA-LinUCB
    bandit = SRALinUCB(alpha=inp_alpha, risk_lambda=0.5)
    selected_action, diagnostics = bandit.select_action(x_t)

    st.markdown("---")
    st.markdown("### ⚖️ SRA-LinUCB Diagnostic Scoring Breakdown")
    st.markdown(rf"**Context Risk Indicator $R(\mathbf{{x}}_t)$:** `{diagnostics['context_risk']:.4f}`")

    diag_rows = []
    for act_idx in [0, 1, 2]:
        act_name = ACTION_NAMES.get(act_idx, f"Action {act_idx}")
        mean_val = diagnostics["means"].get(act_idx, 0.0)
        bonus_val = diagnostics["uncertainties"].get(act_idx, 0.0)
        std_ucb_val = mean_val + bonus_val
        risk_adj_val = diagnostics["risk_penalties"].get(act_idx, 0.0)
        score_val = diagnostics["scores"].get(act_idx, 0.0)

        diag_rows.append({
            "Action Index": act_idx,
            "Action Name": act_name,
            "Estimated Reward (Mean)": f"{mean_val:.4f}",
            "Exploration Bonus": f"{bonus_val:.4f}",
            "Standard UCB": f"{std_ucb_val:.4f}",
            "Risk Penalty": f"{risk_adj_val:.4f}",
            "Final SRA Score": f"{score_val:.4f}",
            "Selected": "🏆 WINNER" if act_idx == selected_action else "",
        })
    st.table(pd.DataFrame(diag_rows))

    st.success(f"**AI Proposal Result:** `{ACTION_NAMES[selected_action]}` (Action {selected_action}) selected as candidate for Guardrail validation.")


# ==============================================================================
# SECTION 4: SECURITY & SLA GUARDRAIL
# ==============================================================================
elif section == "4. Security & SLA Guardrail":
    st.markdown('<div class="main-title">Deterministic SLA & Security Guardrail (Module 6)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Pre-execution mathematical verification enforcing physical link capacity, SLA boundaries, and deterministic repair</div>', unsafe_allow_html=True)

    guardrail = SLASecurityGuardrail()

    st.markdown("### 🛡️ Test Guardrail Against Candidate Proposals")
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.markdown("**Candidate Allocation Proposal (Mbps):**")
        p_urllc = st.number_input("Proposed URLLC Bandwidth (Mbps):", min_value=0.0, max_value=15.0, value=2.0, step=0.5)
        p_embb = st.number_input("Proposed eMBB Bandwidth (Mbps):", min_value=0.0, max_value=15.0, value=6.5, step=0.5)
        p_be = st.number_input("Proposed Best-Effort Bandwidth (Mbps):", min_value=0.0, max_value=15.0, value=1.5, step=0.5)
        allow_repair = st.checkbox("Enable Deterministic Safety Repair (Module 6)", value=True)

    with col_g2:
        st.markdown("**Observed Telemetry & Security Context:**")
        obs_lat = st.slider("Current URLLC Latency (ms):", 5.0, 30.0, 12.0, 0.5)
        obs_loss = st.slider("Current Packet Loss (%):", 0.0, 5.0, 0.2, 0.1)
        sec_mode = st.selectbox(
            "WireGuard Security Mode:",
            ["OFF (Plaintext - 0.0 ms overhead)", "ON (WireGuard Encrypted - 1.2 ms overhead)"],
        )

    sec_enabled = sec_mode.startswith("ON")
    sec_state = SecurityState.create_on_default() if sec_enabled else SecurityState.create_off()

    candidate_alloc = {"URLLC": p_urllc, "eMBB": p_embb, "BE": p_be}
    context = {"latency_ms": obs_lat, "packet_loss_pct": obs_loss, "throughput_mbps": 7.0}

    # Evaluate using actual Module 6 Guardrail
    decision = guardrail.validate(
        candidate_action=candidate_alloc,
        current_context=context,
        security_state=sec_state,
        allow_repair=allow_repair,
    )

    st.markdown("---")
    st.markdown("### 📋 Guardrail Verification Outcome")

    if decision["approved"] and not decision["is_repaired"]:
        st.success("✅ **STATUS: APPROVED** — The candidate allocation fully satisfies all SLA constraints and physical capacity bounds.")
    elif decision["approved"] and decision["is_repaired"]:
        st.warning("⚠️ **STATUS: REPAIRED** — Candidate proposal violated allocation invariants but was safely and deterministically repaired by Module 6.")
    else:
        st.error(f"❌ **STATUS: REJECTED** — {decision['reason']}")

    res_col1, res_col2 = st.columns(2)
    with res_col1:
        st.markdown("**Candidate Allocation Requested:**")
        st.json(candidate_alloc)
        st.caption(f"Total: {sum(candidate_alloc.values()):.2f} Mbps (Link limit: 10.0 Mbps)")

    with res_col2:
        st.markdown("**Action Forwarded to Actuator:**")
        st.json(decision["action"] if decision["action"] else "None (Blocked)")
        if decision.get("violations"):
            st.markdown(f"**Identified Violations:** `{decision['violations']}`")

    st.info(f"**Guardrail Message:** {decision['reason']}")


# ==============================================================================
# SECTION 5: EVALUATION & BENCHMARKS
# ==============================================================================
elif section == "5. Evaluation & Benchmarks":
    st.markdown('<div class="main-title">Module 9 Simulation Benchmark Evaluation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Comparative performance evaluation between Static Slicing, Unsafe Dynamic Slicing, and the Proposed AI-Safe System</div>', unsafe_allow_html=True)

    st.info("ℹ️ **Labeling Note:** Results presented below are derived from Module 9 trace-driven FIFO queuing simulation experiments on a 10.0 Mbps bottleneck link.")

    summary_md = load_summary_table_markdown()
    if summary_md:
        st.markdown("### 📊 Performance Summary Table")
        st.markdown(summary_md)

    st.markdown("---")
    st.markdown("### 🖼️ Comparative Benchmark Plots")

    plots = get_available_plots()
    plot_tabs = st.tabs(["Metric Comparison", "URLLC Latency Dynamics", "eMBB Throughput Dynamics"])

    with plot_tabs[0]:
        if plots["comparison"]:
            st.image(plots["comparison"], caption="Benchmark Performance Comparison: Static vs Unsafe Dynamic vs Proposed AI-Safe", use_container_width=True)
        else:
            st.warning("Plot `results/comparison.png` not found.")

    with plot_tabs[1]:
        if plots["latency"]:
            st.image(plots["latency"], caption="URLLC Round-Trip Latency under eMBB Traffic Surge (15.0 ms SLA breach in unsafe baseline)", use_container_width=True)
        else:
            st.warning("Plot `results/latency.png` not found.")

    with plot_tabs[2]:
        if plots["throughput"]:
            st.image(plots["throughput"], caption="Throughput Distribution and eMBB Elastic Burst Absorption", use_container_width=True)
        else:
            st.warning("Plot `results/throughput.png` not found.")

    with st.expander("📂 Inspect Simulation Benchmark Datasets (CSV)"):
        datasets = load_benchmark_csvs()
        ds_choice = st.selectbox("Select Dataset:", ["Proposed AI-Safe System", "Dynamic Unsafe Slicing", "Static Slicing Baseline"])
        mapping = {
            "Proposed AI-Safe System": "proposed",
            "Dynamic Unsafe Slicing": "dynamic",
            "Static Slicing Baseline": "static",
        }
        df_selected = datasets.get(mapping[ds_choice])
        if df_selected is not None and not df_selected.empty:
            st.dataframe(df_selected)
        else:
            st.warning("Selected dataset CSV not found.")


# ==============================================================================
# SECTION 6: ACTUATOR & DATA PLANE
# ==============================================================================
elif section == "6. Actuator & Data Plane":
    st.markdown('<div class="main-title">Phase 10: Dynamic Data-Plane Rate Actuation</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Linux Traffic Control (tc) HTB classes, OpenFlow queue classification, and read-back verification</div>', unsafe_allow_html=True)

    st.markdown("### ⚙️ Actuator Control Configuration")

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        actuator_mode = st.radio(
            "Actuation Execution Mode:",
            ["Dry-Run / Safe Simulation Mode (Recommended for Demos)", "Live Data-Plane Mode (Requires Root / Mininet)"],
            index=0,
        )
        is_dry_run = "Dry-Run" in actuator_mode

    with col_act2:
        target_iface = st.text_input("Target Bottleneck Switch Interface:", value="s1-eth4")

    actuator = SlicingActuator(interface=target_iface, dry_run=is_dry_run)

    st.markdown("---")
    st.markdown("### 🚀 Execute Actuation from Guardrail Decision")

    st.caption("Select an approved or test allocation to actuate onto the data plane:")
    c1, c2, c3 = st.columns(3)
    with c1:
        req_urllc = st.number_input("URLLC Rate (Mbps):", min_value=3.0, max_value=8.0, value=3.5, step=0.5)
    with c2:
        req_embb = st.number_input("eMBB Rate (Mbps):", min_value=1.0, max_value=8.0, value=4.5, step=0.5)
    with c3:
        req_be = st.number_input("Best-Effort Rate (Mbps):", min_value=0.5, max_value=4.0, value=2.0, step=0.5)

    test_guardrail_decision = {
        "approved": True,
        "action": {"URLLC": req_urllc, "eMBB": req_embb, "BE": req_be},
        "is_repaired": False,
        "violations": [],
        "reason": "Approved by Guardrail",
    }

    if st.button("Apply Allocation to Data Plane"):
        res = actuator.apply_allocation(test_guardrail_decision)

        if res.success:
            st.success(f"✅ **Actuation Result:** {res.status.value} — {res.message}")
            if is_dry_run:
                st.info("ℹ️ **Simulation Notice:** Actuator ran in Dry-Run mode. Validated commands were formatted and verified in simulation without altering live kernel qdiscs.")
            else:
                st.success(f"🔒 **Data Plane Verified:** Rate enforcement executed and confirmed on `{target_iface}` via read-back verification.")
        else:
            st.error(f"❌ **Actuation Result:** {res.status.value} — {res.message}")
            st.warning("⚠️ **Safety Invariant:** Dynamic bandwidth enforcement could not be confirmed. Safe baseline preserved.")

        st.markdown("#### 📜 Executed Shell Commands:")
        st.code("\n".join(res.commands_executed) if res.commands_executed else "No commands executed.")

        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown("**Applied Allocation:**")
            st.json(res.applied_allocation)
        with col_v2:
            st.markdown("**Read-Back Verified Allocation:**")
            st.json(res.verified_allocation)

    st.markdown("---")
    st.markdown("### 🏷️ OpenFlow Queue Classification Rules")
    st.caption("Traffic classification rules generated by SlicingActuator mapping flows to egress queues:")
    rules = actuator.build_classification_rules()
    st.table(pd.DataFrame(rules))

    st.markdown("### 🛟 Safety Fallback & Rollback Mechanism")
    st.info(f"""
    **Known-Safe Baseline Allocation:** `{KNOWN_SAFE_ALLOCATION}`  
    If any Linux `tc` command returns a non-zero exit code or fails kernel verification, `SlicingActuator` automatically initiates an atomic rollback to this baseline, restoring full URLLC guarantees.
    """)
