# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

[![Tests](https://img.shields.io/badge/Tests-154%20Passed%20(100%25)-brightgreen?style=for-the-badge&logo=pytest)](tests/)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![SDN Controller](https://img.shields.io/badge/SDN-Ryu%204.34%20%2B%20OpenFlow%201.3-orange?style=for-the-badge)](https://ryu-sdn.org/)
[![Data Plane](https://img.shields.io/badge/Data%20Plane-Mininet%20%2B%20Open%20vSwitch-lightgrey?style=for-the-badge)](http://mininet.org/)
[![Dashboard](https://img.shields.io/badge/Dashboard-Streamlit%201.30%2B-red?style=for-the-badge&logo=streamlit)](http://localhost:8501)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

## 1. Executive Summary & Abstract

Next-generation multi-tenant Software-Defined Networks (SDN) in 5G and 6G architectures must simultaneously host heterogeneous service classes over shared physical infrastructure:
- **Ultra-Reliable Low-Latency Communication (URLLC):** Mission-critical services (autonomous vehicles, telesurgery, industrial robotics) requiring round-trip latency $\le 15.0\text{ ms}$ and packet loss $\le 1.0\%$.
- **Enhanced Mobile Broadband (eMBB):** Bandwidth-intensive applications (4K/8K video streaming, AR/VR) seeking maximum throughput.
- **Best-Effort (BE):** Standard elastic background traffic (email, web browsing).

### The Shared Link Bottleneck Problem
When high-bandwidth eMBB traffic surges on a shared bottleneck link (10.0 Mbps link between switches `s1` and `s2`), eMBB packets flood the egress switch buffer (**bufferbloat**). Under First-In-First-Out (FIFO) queue processing, URLLC packets arrive and are forced to queue behind bulk eMBB frames. This causes URLLC latency to spike from a nominal **$10.15\text{ ms}$ baseline to over $30\text{--}120\text{ ms}$**, resulting in catastrophic Service Level Agreement (SLA) violations.

### Why Pure AI is Dangerous for Network Control
Conventional static network slicing rigidly partitions bandwidth (e.g., locking URLLC to 3 Mbps and eMBB to 5 Mbps). This guarantees isolation but causes severe resource underutilization: when URLLC is idle, up to 70% of its reserved bandwidth is wasted while competing eMBB flows drop packets.

Conversely, unconstrained Reinforcement Learning (RL) or Contextual Bandits learn through stochastic exploration (trial-and-error). During exploration, pure AI models routinely allocate excessive bandwidth to eMBB to maximize reward, inadvertently causing the very congestion and bufferbloat that breaches mission-critical SLAs.

### Core Architectural Principle
> **"Let AI optimize the network, but never let AI optimize at the cost of a critical SLA."**

This project introduces a **two-tier defense-in-depth architecture**:
1. **Optimization Layer (AI):** A Security- and Risk-Aware Linear Upper Confidence Bound (**SRA-LinUCB**) contextual bandit dynamically optimizes slice bandwidth allocations from real-time physical telemetry while penalizing risky actions during network stress.
2. **Safety Layer (Deterministic Guardrail):** An independent mathematical gatekeeper (**SLASecurityGuardrail**) intercepts candidate allocations *before* they are sent to the data plane. It enforces 6 hard physical and operational gates (Capacity, URLLC Floor, Latency, Loss, Security Risk, Crypto Delay) and features an atomic **Deterministic Repair Engine** that safely scales down lower-priority slices while locking URLLC at its guaranteed reservation.
3. **Data-Plane Actuator (Phase 10):** Translates approved allocations into Linux Traffic Control (`tc`) Hierarchical Token Bucket (HTB) rate classes on Open vSwitch interfaces with kernel read-back verification and atomic rollback to a known-safe baseline.
4. **Interactive Web Dashboard (Phase 11):** A real-time Streamlit visualization suite allowing full auditability, live slider-based AI simulation, and comparative benchmark inspection.

---

## 2. End-to-End System Architecture (Strict Module 01 to 11 Flow)

The system is organized into a clean, sequential pipeline where every module from **Module 01 to Module 11** operates in strict, ordered succession:

```text
===================================================================================================
               STRICT MODULE-BY-MODULE SYSTEM ARCHITECTURE (MODULES 01 TO 11)
===================================================================================================

 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 01: Physical / Emulated Slicing Topology (topology/topology.py)                         │
 │ - Mininet 2.3 + Open vSwitch (OVS 3.3) switches (S1, S2) and 6 hosts (H1..H6)                 │
 │ - 10.0 Mbps Physical Bottleneck Link (s1-eth4 <-> s2-eth4) with 5.0 ms One-Way Delay           │
 │ - Logical Slices: URLLC (H1<->H4, >=3M floor) | eMBB (H2<->H5, elastic) | Best Effort (H3<->H6)│
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Physical Packets, Interface Bytes & Queue Backlog
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 02: Network Telemetry Collector (telemetry/monitor.py)                                 │
 │ - Active namespace-aware probing via mnexec (measures URLLC round-trip latency & packet loss) │
 │ - Passive interface statistics from /sys/class/net & Linux tc egress queue buffer occupancy   │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Raw TelemetryRecord
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 03: Context & Feature Extraction (ai/context_builder.py)                               │
 │ - Sanitizes telemetry (translates -1.0 ms drops into 1.0 worst-case)                          │
 │ - Normalizes metrics into a 6D mathematical vector x_t in R^6:                                │
 │   x0: Bias (1.0) | x1: Latency | x2: Throughput | x3: Queue | x4: Trend Velocity | x5: Loss   │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ 6D Normalized Context Vector x_t
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 04: SRA-LinUCB Decision Engine (ai/linucb.py)                                          │
 │ - Multi-armed contextual bandit evaluating 3 actions: DECREASE_EMBB, MAINTAIN, INCREASE_EMBB  │
 │ - Incorporates proactive risk penalty: Score_a(x_t) = UCB_a(x_t) - lambda * rho_a * R(x_t)   │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Candidate Action Proposal
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 05: Security State & Overhead Profiler (security/security_config.py)                   │
 │ - Profiles WireGuard cryptographic tunnel latency overhead (empirical 1.2 ms delay)          │
 │ - Passes encryption budget to Guardrail so security delay is accounted for before switch      │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Candidate Action + Security Budget
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 06: Deterministic SLA & Security Guardrail (guardrail/guardrail.py)                    │
 │ - Pre-execution mathematical gatekeeper enforcing 6 hard safety gates                         │
 │ - If candidate violates capacity (>10M) or URLLC floor (<3M):                                 │
 │   Triggers Deterministic Repair: Locks URLLC = 3.0M, Protects BE = 0.5M, Caps eMBB = 6.5M     │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Verified & Safe Allocation
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 07: Ryu OpenFlow 1.3 SDN Controller (controller/ryu_controller.py)                     │
 │ - Pushes OpenFlow 1.3 flow modification messages (OFPFlowMod) to Open vSwitch switches        │
 │ - Implements layer-2 MAC address learning and maps slice flows to designated queue IDs        │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Post-Enforcement Network Consequences
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 08: Closed-Loop Reward Engine & Feedback Learner (feedback/)                           │
 │ - Computes multi-objective reward with steep quadratic barrier penalty for SLA violations     │
 │ - Causal Safe Attribution: Updates LinUCB covariance matrices (A_a, b_a) in Module 04        │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Validated Closed-Loop System
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 09: Trace-Driven Simulation Benchmark Evaluation (experiments/)                        │
 │ - First-principles fluid FIFO queuing simulation model under standardized 20-step trace       │
 │ - Scientific 3-way evaluation: Static Slicing vs Unsafe LinUCB vs Proposed AI-Safe System     │
 │ - Generates 24-column CSVs, summary tables, and publication plots (comparison, latency, tput) │
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Actuation Commands & Read-Back Verification
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 10: Dynamic Data-Plane Rate Actuator (controller/slicing_actuator.py)                  │
 │ - Enforces approved rates via Linux tc HTB classes (1:10 URLLC, 1:20 eMBB, 1:30 Best-Effort)  │
 │ - Reads back kernel state via /sbin/tc class show; auto-rolls back to safe baseline on failure│
 └──────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                │ Unified System State & Visual Analytics
                                                ▼
 ┌───────────────────────────────────────────────────────────────────────────────────────────────┐
 │ MODULE 11: Real-Time Interactive Web Dashboard (dashboard/app.py on http://localhost:8501)    │
 │ - Interactive Streamlit UI presenting all 6 operational views to the user and examiner:       │
 │   1. Topology Overview      2. Live Telemetry vs SLA  3. AI Simulator & 6D Context            │
 │   4. Guardrail Sandbox      5. Benchmark Plots        6. Data-Plane Actuator Verification     │
 └───────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Network Topology & Slicing Specifications

Implemented in [`topology/topology.py`](topology/topology.py) using Mininet, Open vSwitch, and Linux Traffic Control (`tc`).

```text
   H1 (URLLC Source) ────┐                                ┌──── H4 (URLLC Sink)
   H2 (eMBB Source)  ────┤        10 Mbps Bottleneck      ├──── H5 (eMBB Sink)
   H3 (BE Source)    ────┴── Switch S1 ════════ Switch S2 ──┴──── H6 (BE Sink)
                               (s1-eth4)    (s2-eth4)
                              Delay: 5 ms, Buffer: 50 pkts
```

### Logical Slices & Service Level Agreements (SLAs)

| Slice | Endpoints | Traffic Type | Queue / HTB | Priority | Guaranteed Floor | SLA Latency Ceiling | SLA Loss Limit |
|---|:---:|---|:---:|:---:|:---:|:---:|:---:|
| **URLLC** | `h1` $\leftrightarrow$ `h4` | Mission-Critical Low Latency | Queue 0 / `1:10` | 0 (Highest) | **$\ge 3.0\text{ Mbps}$** | **$\le 15.0\text{ ms}$** | **$\le 1.0\%$** |
| **eMBB** | `h2` $\leftrightarrow$ `h5` | High-Throughput Bulk Video | Queue 1 / `1:20` | 1 (Medium) | $\ge 1.0\text{ Mbps}$ | Elastic | Elastic |
| **Best Effort (BE)** | `h3` $\leftrightarrow$ `h6` | Background Elastic Traffic | Queue 2 / `1:30` | 2 (Lowest) | $\ge 0.5\text{ Mbps}$ | Elastic | Elastic |

* **Physical Bottleneck:** The inter-switch link (`s1-eth4` $\leftrightarrow$ `s2-eth4`) is constrained to **10.0 Mbps** with a **5.0 ms propagation delay** each way.
* **Theoretical Physical RTT Baseline:** $2 \times 5.0\text{ ms} = 10.0\text{ ms}$ ($10.15\text{ ms}$ with OVS switching delay).
* **Buffer Capacity:** Egress queue limit is clamped to **50 packets** to prevent bufferbloat.

---

## 4. Complete Phase & Module Breakdown (Phases 01 to 12)

> **Architectural Note on Phase Numbering vs. Runtime Pipeline Order:**  
> - **Chronological Phases (01 to 12):** Represent the sequential engineering and verification roadmap of the project.  
> - **Runtime Dataflow Execution Order:** When the network operates, data flows in closed-loop order: Telemetry (Phase 02) $\rightarrow$ Context Extraction (Phase 03) $\rightarrow$ AI Scoring (Phase 04) $\rightarrow$ Guardrail Validation (Phases 05 & 06) $\rightarrow$ **Data-Plane Actuator (Phase 10)** $\rightarrow$ **SDN Switch (Phase 07)** $\rightarrow$ Online Feedback (Phase 08) $\rightarrow$ **Comparative Evaluation (Phase 09)** $\rightarrow$ **Web Dashboard (Phase 11)**.

### Chronological Development Phases vs. Runtime Pipeline

| Phase | Module & Subsystem | Primary Code File | Runtime Pipeline Function |
|:---:|---|---|---|
| **Phase 01** | Module 01: Slicing Topology | [`topology/topology.py`](topology/topology.py) | Mininet OVS Data Plane Foundation (10 Mbps bottleneck) |
| **Phase 02** | Module 02: Telemetry Collector | [`telemetry/monitor.py`](telemetry/monitor.py) | Step 1: Active `mnexec` probing & passive interface stats |
| **Phase 03** | Module 03: Context Builder | [`ai/context_builder.py`](ai/context_builder.py) | Step 2: 6D feature vector normalization $\mathbf{x}_t \in \mathbb{R}^6$ |
| **Phase 04** | Module 04: SRA-LinUCB Engine | [`ai/linucb.py`](ai/linucb.py) | Step 3: Contextual bandit scoring with risk penalty |
| **Phase 05** | Module 05: Security Profiling | [`security/security_config.py`](security/security_config.py) | Step 4: WireGuard $1.2\text{ ms}$ cryptographic overhead budget |
| **Phase 06** | Module 06: Deterministic Guardrail | [`guardrail/guardrail.py`](guardrail/guardrail.py) | Step 5: 6 hard safety gates & deterministic repair engine |
| **Phase 07** | Module 07: Ryu SDN Controller | [`controller/ryu_controller.py`](controller/ryu_controller.py) | Step 6: OpenFlow 1.3 flow modification & MAC learning |
| **Phase 10** | Module 10: Data-Plane Actuator | [`controller/slicing_actuator.py`](controller/slicing_actuator.py) | Step 7: Linux `tc` HTB rate classes & read-back verify |
| **Phase 08** | Module 08: Reward & Learner | [`feedback/reward.py`](feedback/reward.py) | Step 8: Multi-objective reward & Causal Safe Attribution |
| **Phase 09** | Module 09: Simulation Benchmark | [`experiments/run_experiments.py`](experiments/run_experiments.py) | Step 9: 20-step dynamic evaluation (Static vs Unsafe vs Safe) |
| **Phase 11** | Module 11: Streamlit Dashboard | [`dashboard/app.py`](dashboard/app.py) | Step 10: 6-view interactive web UI on port `8501` |
| **Phase 12** | Production Roadmap Orchestrator| [`docs/CONTRIBUTIONS_AND_FUTURE_WORK.md`](docs/CONTRIBUTIONS_AND_FUTURE_WORK.md) | Step 11: Unified autonomous live closed-loop runner |

---

### Phase 01 / Module 01: Physical Network Topology (`topology/`)
- **File:** [`topology/topology.py`](topology/topology.py)
- **Role:** Builds the OpenFlow 1.3 dual-switch, 6-host Mininet topology. Configures the 10 Mbps bottleneck link with 5 ms delay.

### Phase 02 / Module 02: Network Telemetry Collector (`telemetry/`)
- **File:** [`telemetry/monitor.py`](telemetry/monitor.py)
- **Role:** Non-invasive telemetry probe. Solves Mininet host namespace isolation by querying host process IDs (PIDs) and executing probes inside host network namespaces via `mnexec -a <PID> ping`. Collects passive interface bytes from `/sys/class/net/` and egress queue backlog from Linux `tc`.
- **Integrity Design:** Missing packets or unreachable hosts defensively produce sentinel `-1.0 ms` records rather than synthetic falsifications.

### Phase 03 / Module 03: Context & Feature Extraction (`ai/context_builder.py`)
- **File:** [`ai/context_builder.py`](ai/context_builder.py)
- **Role:** Normalizes telemetry into a sanitized 6D numerical context vector $\mathbf{x}_t \in \mathbb{R}^6$:
  - $x_0 = 1.0$: Bias / intercept term.
  - $x_1 = \min(1.0, \text{latency} / 50.0)$: Bounded latency metric.
  - $x_2 = \min(1.0, \text{throughput} / 10.0)$: Link utilization metric.
  - $x_3 = \min(1.0, \text{queue} / 50.0)$: Buffer occupancy ratio.
  - $x_4 \in [-1.0, 1.0]$: Latency velocity trend $(\Delta \text{latency} / \Delta t)$.
  - $x_5 \in [0.0, 1.0]$: Packet drop ratio.
- **Sentinel Sanitization:** Automatically translates sentinel `-1.0` into $1.0$ (worst-case), preventing math crashes.

### Phase 04 / Module 04: SRA-LinUCB Decision Engine (`ai/linucb.py`)
- **File:** [`ai/linucb.py`](ai/linucb.py)
- **Role:** Contextual bandit resource allocation with three discrete actions:
  - `0: DECREASE_EMBB` ($\rho_0 = -1.0$) — Throttles eMBB to relieve congestion.
  - `1: MAINTAIN` ($\rho_1 = 0.0$) — Holds steady to prevent control chatter.
  - `2: INCREASE_EMBB` ($\rho_2 = +1.0$) — Expands eMBB to reclaim spare link budget.
- **Decision Formula:**
  $$\text{Score}_a(\mathbf{x}_t) = \underbrace{\mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}}_{\text{Standard LinUCB Exploitation + Exploration}} - \underbrace{\lambda \cdot \rho_a \cdot R(\mathbf{x}_t)}_{\text{SRA Risk Penalty}}$$
  Where $R(\mathbf{x}_t) = 0.4 x_1 + 0.3 x_3 + 0.2 \max(0, x_4) + 0.1 x_5$ is the physical risk indicator.
- **Numerical Stability:** Solves the linear system $\mathbf{A}_a \hat{\boldsymbol{\theta}}_a = \mathbf{b}_a$ using `np.linalg.solve()` rather than explicit matrix inversion (`np.linalg.inv()`), ensuring stability and $O(d^2)$ efficiency.

### Phase 05 / Module 05: Security State & Overhead Profiling (`security/`)
- **File:** [`security/security_config.py`](security/security_config.py)
- **Role:** Profiles the cryptographic delay introduced by WireGuard tunnel encryption ($1.2\text{ ms}$ empirical overhead) so security overhead is accounted for before reaching the 15 ms latency ceiling.

### Phase 06 / Module 06: Deterministic SLA & Security Guardrail (`guardrail/`)
- **File:** [`guardrail/guardrail.py`](guardrail/guardrail.py)
- **Role:** The immutable safety barrier. Pre-validates all candidate actions against 6 hard gates:
  1. Total Capacity Gate: $\sum \text{Bandwidth} \le 10.0\text{ Mbps}$.
  2. URLLC Reservation Floor Gate: $\text{BW}_{\text{URLLC}} \ge 3.0\text{ Mbps}$.
  3. URLLC Latency Gate: $\text{Observed Latency} \le 15.0\text{ ms}$.
  4. Packet Loss Gate: $\text{Loss} \le 1.0\%$.
  5. Security Threat Gate: $\text{Risk} \le 0.70$.
  6. Crypto Overhead Gate: Security delay $\le 5.0\text{ ms}$.
- **Deterministic Repair Engine:** If an AI action exceeds link capacity, rather than dropping traffic, it mathematically recalculates the allocation:
  $$\text{URLLC}_{\text{repaired}} = 3.0\text{ Mbps (Locked Floor)}$$
  $$\text{BE}_{\text{repaired}} = 0.5\text{ Mbps (Protected Baseline)}$$
  $$\text{eMBB}_{\text{repaired}} = 10.0 - 3.0 - 0.5 = 6.5\text{ Mbps (Remaining Budget)}$$

### Phase 07 / Module 07: SDN Control Plane with Ryu (`controller/`)
- **File:** [`controller/ryu_controller.py`](controller/ryu_controller.py)
- **Role:** Implements an OpenFlow 1.3 learning switch controller on TCP port 6633. Installs table-miss flow entries and handles flow modifications.

### Phase 08 / Module 08: Closed-Loop Reward Engine & Feedback Learner (`feedback/`)
- **Files:** [`feedback/reward.py`](feedback/reward.py) and [`feedback/learner.py`](feedback/learner.py)
- **Role:** Computes multi-objective scalar rewards incorporating throughput, latency, loss, and a steep quadratic SLA barrier penalty $\left(\frac{\Delta\text{lat}}{15.0}\right)^2$.
- **Causal Safe Attribution:** Ensures model covariance matrices $(\mathbf{A}_a, \mathbf{b}_a)$ are updated strictly for the action executed on the physical switches. Rejected actions receive no updates, preventing model corruption.

### Phase 09 / Module 09: Trace-Driven Simulation Benchmark (`experiments/`)
- **Files:** [`experiments/run_experiments.py`](experiments/run_experiments.py), [`experiments/static_baseline.py`](experiments/static_baseline.py), [`experiments/dynamic_baseline.py`](experiments/dynamic_baseline.py), [`experiments/proposed_system.py`](experiments/proposed_system.py)
- **Role:** Comprehensive trace-driven simulation benchmarking comparing Static Slicing vs. Unconstrained AI vs. the Proposed AI-Safe System.
- **First-Principles Queuing Physics:**
  - Implements a fluid FIFO buffer model on a 10.0 Mbps bottleneck link with a maximum queue capacity of $Q_{\text{max}} = 50\text{ packets}$.
  - Derives exact packet serialization latency from Ethernet MTU physics: a standard $1500\text{-byte}$ packet contains $12,000\text{ bits}$. On a $10.0\text{ Mbps}$ bottleneck, transmission serialization delay is exactly:
    $$\tau_{\text{serial}} = \frac{12,000\text{ bits}}{10,000,000\text{ bps}} = 1.20\text{ ms/packet}$$
  - The instantaneous simulated round-trip time is computed from physical baseline RTT ($10.15\text{ ms}$), buffer backlog delay, and cryptographic delay:
    $$RTT_{\text{sim}} = 10.15\text{ ms} + (Q_t \times 1.20\text{ ms}) + \Delta L_{\text{crypto}}$$
- **Standardized 20-Step Workload Trace:**
  - *Steps 1–7 (Healthy Baseline):* eMBB demands $3.5\text{ Mbps}$, URLLC consumes $1.0\text{ Mbps}$, total load $< 10\text{ Mbps}$.
  - *Steps 8–11 (Severe Traffic Surge):* eMBB demand violently surges to $8.5\text{ Mbps}$ on the shared $10\text{ Mbps}$ bottleneck.
  - *Steps 12–20 (Recovery & Stabilization):* eMBB demand relaxes to $4.0\text{ Mbps}$.
- **Comparative Regimes Evaluated:**
  1. *Static Partitioning Baseline:* Fixed allocation (`URLLC: 3.0, eMBB: 5.0, BE: 2.0 Mbps`). Maintains $0\%$ SLA violations but artificially starves eMBB during the surge and leaves bandwidth idle off-peak.
  2. *Unsafe Dynamic Baseline:* Standard LinUCB without safety constraints ($\lambda = 0.0$, Guardrail disabled). Greedily allocates $9.0\text{ Mbps}$ to eMBB at Step 11, causing queue accumulation ($16.67\text{ pkts}$) and spiking latency to **$30.15\text{ ms}$**—violating the $15.0\text{ ms}$ SLA.
  3. *Proposed AI-Safe System:* SRA-LinUCB ($\lambda = 0.5$) with Module 06 Guardrail and Module 08 Feedback. Intercepts candidate overloads, triggers deterministic repair, locks URLLC at $\ge 3.0\text{ Mbps}$, caps eMBB to $6.5\text{ Mbps}$, and delivers **$100\%$ SLA compliance (0 violations)** with **$12.51\text{ ms}$ peak latency**.
- **Generated Artifacts:** Generates 24-column standardized CSV trace logs, formatted summary tables (`results/summary_table.md`), and high-resolution comparison plots (`results/*.png`).

### Phase 10 / Module 10: Dynamic Data-Plane Rate Actuation (`controller/`)
- **File:** [`controller/slicing_actuator.py`](controller/slicing_actuator.py)
- **Role:** Bridges Module 06 Guardrail decisions directly into the Open vSwitch data plane and Linux kernel Traffic Control (`tc`) subsystem.
- **Linux Traffic Control (`tc`) Hierarchical Token Bucket (HTB) Architecture:**
  - Configures the egress queue discipline on the switch bottleneck interface (`s1-eth4`):
    ```bash
    tc qdisc add dev s1-eth4 root handle 1: htb default 30
    ```
  - Dynamically updates hierarchical rate classes based on approved decisions:
    - `Class 1:10 (URLLC)`: `rate 3.0Mbit ceil 10.0Mbit prio 0` (Highest priority, guaranteed floor).
    - `Class 1:20 (eMBB)`: `rate <embb>Mbit ceil 10.0Mbit prio 1` (Medium priority, dynamic burst).
    - `Class 1:30 (Best-Effort)`: `rate <be>Mbit ceil 10.0Mbit prio 2` (Lowest priority, background).
- **OpenFlow 1.3 Queue Classification:**
  - Generates OpenFlow flow rules matching IP/port tuples and executing `set_queue:<id>` before forwarding to switch output ports.
- **Kernel Read-Back Verification:**
  - Following every rate change, executes `/sbin/tc -s class show dev s1-eth4` and verifies that the active kernel rates match the target allocation within a numerical tolerance of $\pm 0.1\text{ Mbps}$.
- **Atomic Safety Fallback & Emergency Rollback:**
  - If any Linux `tc` command returns a non-zero exit code or fails read-back verification, the actuator immediately triggers an atomic rollback to `KNOWN_SAFE_ALLOCATION = {'URLLC': 3.0, 'eMBB': 5.0, 'BE': 2.0}`, ensuring network traffic never freezes.

### Phase 11 / Module 11: Real-Time Interactive Web Dashboard (`dashboard/`)
- **Files:** [`dashboard/app.py`](dashboard/app.py) and [`dashboard/data_loader.py`](dashboard/data_loader.py)
- **Role:** Production-ready Streamlit web interface operating on port `8501`, designed for interactive faculty demonstrations, telemetry analysis, and technical defense.
- **Six Comprehensive System Views:**
  1. *1. Overview & Topology:* Displays the multi-tenant topology, QoS profile table, and end-to-end closed-loop control pipeline.
  2. *2. Telemetry Monitoring:* Live time-series charts for URLLC latency (with red dashed 15.0 ms SLA threshold line), bottleneck throughput, loss %, and queue occupancy. Features an isolated audit expander for dropped/unreachable `-1.0` sentinel records.
  3. *3. AI Decision Engine:* Interactive demo sliders allowing examiners to adjust latency, loss, throughput, and queue occupancy in real time. Visualizes the live 6D context vector $\mathbf{x}_t \in \mathbb{R}^6$ and displays the complete SRA-LinUCB diagnostic scoring breakdown table.
  4. *4. Security & SLA Guardrail:* Sandbox for testing arbitrary candidate allocations. Shows live status badges (`APPROVED`, `REPAIRED`, `REJECTED`), side-by-side requested vs forwarded allocations, and WireGuard cryptographic delay toggling ($1.2\text{ ms}$).
  5. *5. Evaluation & Benchmarks:* Formats and renders the simulation benchmark datasets, comparative plots (`comparison.png`, `latency.png`, `throughput.png`), and markdown summary table.
  6. *6. Actuator & Data Plane:* Provides Dry-Run vs Live execution modes, displays real-time generated Linux `tc` shell commands, shows read-back verification JSONs, and lists OpenFlow queue classification rules.

### Phase 12 / Production Roadmap: Unified Live Closed-Loop Runner
- **Role:** Autonomous orchestrator linking physical Mininet traffic injection, namespace-aware telemetry probing, 6D context normalization, SRA-LinUCB scoring, deterministic Guardrail verification, Linux `tc` actuation, and causal feedback learning in continuous autonomous 1-second control cycles.


---

## 5. Experimental Results & Benchmark Evaluation

Evaluated across a standardized 20-step dynamic traffic trace featuring an 8.5 Mbps eMBB traffic surge on a 10.0 Mbps bottleneck link.

### Scientific Benchmark Performance Summary Table

| Performance Metric | Static Slicing (Fixed) | Dynamic Slicing (Unsafe LinUCB) | Proposed System (AI-Safe System) | Architectural Significance |
|---|:---:|:---:|:---:|---|
| **URLLC Mean Simulated RTT** | **10.15 ms** | 11.15 ms | **11.07 ms** | Healthy baseline across all regimes |
| **URLLC 99th-Percentile (p99) RTT** | **10.15 ms** | **26.35 ms** *(BREACH)* | **12.51 ms** *(SAFE)* | **Unsafe AI breaches 15 ms SLA; Proposed remains strictly safe** |
| **eMBB Mean Throughput** | 4.02 Mbps | 4.24 Mbps | **4.19 Mbps** | **Proposed delivers +4.2% higher throughput than static** |
| **eMBB Peak Throughput** | 5.00 Mbps | 8.50 Mbps *(Hazardous)*| **6.50 Mbps** *(Safe Max)* | Proposed safely reclaims idle capacity without congestion |
| **URLLC Packet Loss** | **0.0 %** | **0.0 %** | **0.0 %** | Zero dropped packets |
| **SLA Violations (Count / %)** | **0 (0.0%)** | **1 (5.0%)** | **0 (0.0%)** | **100% SLA preservation with AI active** |
| **Congestion Recovery Time** | **0.0 s** | 1.0 s | **0.0 s** | Zero buffer backlog overflow |
| **Guardrail Repaired Actions** | 0 (N/A) | 0 (Disabled) | **3 (Active Repairs)** | Proves guardrail actively intervened during the surge |
| **Security Overhead Mode** | N/A | Ignored | **Simulated (1.2 ms)** | WireGuard crypto latency factored into decision |
| **Deterministic Safety Guard** | No | No | **Yes (Module 06)** | Un-bypassable mathematical guarantee |

### Visual Artifacts in `results/`

All evaluation plots are generated directly by `experiments/run_experiments.py`:
1. **[`results/comparison.png`](results/comparison.png):** Side-by-side grouped bar chart illustrating SLA violations (%), mean latency, and throughput across all three regimes.
2. **[`results/latency.png`](results/latency.png):** 3-panel time series plotting simulated RTT against the red dashed **15.0 ms SLA threshold line**. Unsafe LinUCB spikes to **30.15 ms** at Step 11, whereas the Proposed System stays safely bounded at **12.51 ms**.
3. **[`results/throughput.png`](results/throughput.png):** Bandwidth allocation timeline showing how the Guardrail expands eMBB to 6.5 Mbps while preserving the 3.0 Mbps URLLC safety floor.

---

## 6. Complete Step-by-Step Running Guide

### Prerequisites
- **Operating System:** Linux (Ubuntu 22.04 LTS recommended) or **Windows WSL2** (Ubuntu).
- **Python:** 3.9, 3.10, or 3.11.
- **Packages:** Ryu 4.34, Mininet 2.3.0, Open vSwitch 3.x, Streamlit 1.30+.

Install all Python dependencies:
```bash
pip install -r requirements.txt
```

---

### Command 1: Run Full 154-Test Verification Suite
Verifies all modules, math formulas, guardrail gates, and actuator commands:
```bash
pytest --disable-warnings -q
```
**Expected Output:**
```text
154 passed, 14 warnings in 24.55s (100% Success Rate)
```

---

### Command 2: Run the 5-Step Live Pipeline Walkthrough
Traces live telemetry dataflow into the 6D context vector, calculates risk $R(\mathbf{x}_t)$, and demonstrates proactive risk suppression:
```bash
python ai/test_pipeline_live.py
```
**Expected Output:** Shows low risk ($R=0.083$) under healthy conditions, and high risk ($R=0.663$) during congestion, automatically steering SRA-LinUCB from `INCREASE_EMBB` to `DECREASE_EMBB`.

---

### Command 3: Run Benchmark Simulation & View Table
Executes the trace-driven comparative benchmark and prints the performance table:
```bash
# Print summary table instantly:
python experiments/run_experiments.py --table-only

# Or run full simulation to re-generate all CSVs and PNG plots:
python experiments/run_experiments.py
```

---

### Command 4: Run the Interactive Streamlit Web Dashboard
Launches the web UI for live presentations and faculty defense:
```bash
streamlit run dashboard/app.py
```
Open your browser to: **`http://localhost:8501`**

#### What to Show on the Dashboard:
1. **Overview & Topology:** 10.0 Mbps bottleneck, 3 slices, 15.0 ms SLA ceiling, 3.0 Mbps floor.
2. **Telemetry Monitoring:** Live latency time-series vs 15.0 ms SLA threshold line, throughput, and audit of sentinel `-1.0` records.
3. **AI Decision Engine:** Interactive sliders to adjust latency/queue. Shows real-time 6D context vector construction and SRA-LinUCB diagnostic scoring breakdown.
4. **Security & SLA Guardrail:** Set an unsafe candidate allocation (e.g., URLLC = 2.0, eMBB = 7.0, BE = 2.5). Watch the Guardrail trigger **`STATUS: REPAIRED`** and clamp URLLC to 3.0 Mbps.
5. **Evaluation & Benchmarks:** Full scientific summary table and interactive tabs for all 3 comparison plots.
6. **Actuator & Data Plane:** Click "Apply Allocation" in dry-run mode to see formatted Linux `tc` commands and read-back verification.

---

### Command 5: Full Live Mininet + Ryu Testbed (Multi-Terminal)

For a live network demonstration on Ubuntu/WSL:

#### Terminal 1: Start Ryu SDN Controller
```bash
ryu-manager controller/ryu_controller.py --verbose
```
*(Controller initializes on port 6633 and waits for switches).*

#### Terminal 2: Start Mininet Network
```bash
sudo mn -c   # Clean up any residual switch state
sudo python topology/topology.py
```
*(Mininet starts; Terminal 1 will immediately print `Switch connected: 1` and `Switch connected: 2`).*

#### Terminal 2 (Inside Mininet CLI): Generate Congestion
```text
# 1. Verify connectivity
mininet> pingall

# 2. Start iperf3 servers on sink hosts H4 and H5
mininet> h4 iperf3 -s -D
mininet> h5 iperf3 -s -D

# 3. Check baseline healthy latency (averages ~10.15 ms)
mininet> h1 ping -c 5 10.0.0.4

# 4. Inject heavy 8.5 Mbps eMBB traffic burst
mininet> h2 iperf3 -c 10.0.0.5 -u -b 8.5M -t 40 &

# 5. Measure latency under congestion (spikes to >30 ms without guardrail)
mininet> h1 ping -c 10 10.0.0.4
```

#### Terminal 3: Start Telemetry Monitor
```bash
sudo python telemetry/monitor.py
```
*(Streams live measurements to `data/telemetry.csv`).*

---

## 7. Repository File Structure

```text
AI-Safe-Dynamic-Slicing/
├── .gitignore                      # Git configuration (tracks benchmarks & sample data)
├── .python-version                 # Pyenv specification (3.10.14 / 3.9.18)
├── README.md                       # Master comprehensive documentation & execution guide
├── requirements.txt                # Complete Python dependencies (Ryu, Streamlit, Pytest...)
│
├── topology/                       # Module 01: Physical Data Plane Topology
│   └── topology.py                 # Mininet topology, 2 switches, 6 hosts, 10 Mbps bottleneck
│
├── telemetry/                      # Module 02: Network Telemetry Collector
│   ├── monitor.py                  # Namespace-aware active & passive telemetry monitor
│   └── test_telemetry.py           # Unit tests for ping parsing, loss %, and queue parsing
│
├── ai/                             # Modules 03 & 04: AI Context Builder & SRA-LinUCB
│   ├── context_builder.py          # 6D context vector extraction & sentinel sanitization
│   ├── linucb.py                   # SRA-LinUCB decision engine with proactive risk penalty
│   ├── test_context_builder.py     # Unit tests for context normalization
│   ├── test_linucb.py              # Unit tests for bandit math & solve operations
│   ├── test_integration.py         # M2 -> M3 -> M4 integration tests
│   └── test_pipeline_live.py       # Live 5-step synthetic pipeline demonstration script
│
├── security/                       # Module 05: Cryptographic Overhead & WireGuard
│   ├── security_config.py          # SecurityState dataclass & 1.2 ms WireGuard delay profile
│   ├── security_metrics.py         # Security metric calculation wrappers
│   └── wireguard_adapter.py        # System WireGuard interface & fallback query adapter
│
├── guardrail/                      # Module 06: Deterministic SLA & Security Guardrail
│   ├── guardrail.py                # Pre-execution validator enforcing 6 gates & repair engine
│   └── sla_config.py               # GuardrailConfig boundaries & thresholds
│
├── slicing/                        # Centralized Slice Specifications
│   └── slice_config.py             # SliceQoSProfile definitions & DEFAULT_SLICING_CONFIG
│
├── controller/                     # Modules 07 & 10: SDN Control Plane & Dynamic Actuator
│   ├── ryu_controller.py           # Ryu OpenFlow 1.3 learning switch & flow installer
│   └── slicing_actuator.py         # Linux tc HTB rate modifier & read-back verifier
│
├── feedback/                       # Module 08: Reward Engine & Causal Feedback Learner
│   ├── reward.py                   # Multi-objective reward with quadratic SLA penalty
│   ├── learner.py                  # FeedbackLearner with Causal Safe Attribution
│   ├── test_reward.py              # Unit tests for reward engine calculations
│   ├── test_learner.py             # Unit tests for causal attribution updates
│   └── test_feedback.py            # Integration tests for feedback loop
│
├── experiments/                    # Module 09: Trace-Driven Simulation Benchmarks
│   ├── run_experiments.py         # Master runner comparing Static, Unsafe, and Proposed
│   ├── static_baseline.py          # Static fixed partitioning simulation
│   ├── dynamic_baseline.py         # Unsafe LinUCB baseline simulation
│   └── proposed_system.py          # Proposed AI-Safe System simulation
│
├── dashboard/                      # Module 11: Real-Time Interactive Web Dashboard
│   ├── app.py                      # Streamlit application with 6 functional views
│   └── data_loader.py              # Telemetry & benchmark CSV ingestion with sentinel audit
│
├── config/                         # System Configuration
│   └── network_config.yaml         # Centralized network parameters & constants
│
├── tests/                          # Automated Regression Test Suite (154/154 Passing)
│   ├── test_actuator.py            # Tests for Linux tc commands & rollback
│   ├── test_dashboard.py           # Headless smoke & UI component tests
│   ├── test_experiments.py         # Tests for FIFO queuing simulator
│   ├── test_feedback.py            # Tests for causal feedback updates
│   ├── test_guardrail.py           # Tests for all 6 guardrail gates & repair
│   ├── test_pipeline_guardrail.py  # End-to-end closed-loop pipeline tests
│   ├── test_security.py            # Tests for security profiles & WireGuard adapter
│   └── test_slice_config.py        # Tests for slice configuration invariants
│
├── data/                           # Real Telemetry Datasets
│   └── telemetry.csv               # Measured network traces
│
├── results/                        # Generated Scientific Artifacts
│   ├── summary_table.md            # Benchmark performance summary table (Markdown)
│   ├── summary_table.txt           # Benchmark performance summary table (Plaintext)
│   ├── comparison.png              # Grouped bar chart comparison
│   ├── latency.png                 # 3-panel latency time-series vs 15 ms SLA ceiling
│   ├── throughput.png              # 3-panel dynamic slice throughput adaptation
│   ├── static_results.csv          # 20-step static slicing trace log
│   ├── dynamic_results.csv         # 20-step unsafe dynamic slicing trace log
│   └── proposed_results.csv        # 20-step proposed AI-Safe slicing trace log
│
└── docs/                           # Supplementary Technical Documentation
    ├── CONTRIBUTIONS_AND_FUTURE_WORK.md # Research contributions & production roadmap
    ├── DEMO_AND_TESTING_GUIDE.md        # Step-by-step faculty demonstration guide
    ├── FORMULAS_METRICS_AND_GUARDRAILS.md # Complete mathematical reference
    ├── MODULE_BY_MODULE_GUIDE.md        # Detailed module-by-module documentation
    ├── QUICK_REVISION.md                # 5-minute quick revision before presentation
    └── VIVA_QUESTIONS_AND_ANSWERS.md    # Comprehensive technical reference
```

---

## 8. License & Attribution

This project is licensed under the MIT License. Developed for research in **AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks**.
