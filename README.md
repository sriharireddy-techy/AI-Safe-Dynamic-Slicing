# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

[![Tests](https://img.shields.io/badge/Tests-83%20Passed-brightgreen)](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue)](https://www.python.org/)
[![SDN](https://img.shields.io/badge/SDN-Ryu%204.34%20%2B%20OpenFlow%201.3-orange)](https://ryu-sdn.org/)
[![Data Plane](https://img.shields.io/badge/Data%20Plane-Mininet%20%2B%20Open%20vSwitch-lightgrey)](http://mininet.org/)

---

## 1. Project Overview

This project implements an **AI-driven, safety-constrained dynamic network slicing system** for Software-Defined Networks (SDN).

In shared multi-tenant networks, high-bandwidth applications (such as 4K/8K video streaming) compete for bottleneck link capacity against mission-critical traffic (such as autonomous control and industrial sensors). Unregulated competition causes bufferbloat, queuing delays, and packet loss, leading to severe Service Level Agreement (SLA) violations.

### Core Architecture Principle

> **"Let AI optimize the network, but never let AI optimize at the cost of a critical SLA."**

The system establishes an architectural boundary between optimization and safety:
- **Optimization Layer (AI):** A Security- and Risk-Aware Linear Upper Confidence Bound ([`SRALinUCB`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L59)) agent explores resource adjustments to maximize bandwidth utilization.
- **Safety Layer (Guardrail):** An independent deterministic verifier ([`SLASecurityGuardrail`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py#L35)) intercepts candidate actions and enforces hard capacity, latency, loss, and security constraints *before* any flow modifications reach the OpenFlow switches.

```text
               ┌────────────────────────────────────────────────────────┐
               │              Physical / Emulated Data Plane            │
               │   Mininet 2.3.0 + Open vSwitch (OVS 3.3.9) Switches    │
               │   [H1..H3] ─── S1 ════(10 Mbps Bottleneck)════ S2 ─── [H4..H6] │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Active Probes & Queue Stats
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │           Module 02: Network Telemetry Collector       │
               │  - Active RTT/Loss via mnexec inside host namespaces    │
               │  - Passive /sys/class/net interface byte counters      │
               │  - Linux Traffic Control (tc) egress queue backlog     │
               └──────────────────────────┬─────────────────────────────┘
                                          │ TelemetryRecord / dict
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │         Module 03: Context & Feature Extraction        │
               │  - Defensive sentinel sanitization (-1.0 ms -> worst)  │
               │  - Dynamic temporal trend extraction (lat_t - lat_prev)│
               │  - Normalization to [0.0, 1.0] -> 6D Vector x_t in R^6 │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Context Vector x_t
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │             Module 04: SRA-LinUCB Decision Engine      │
               │  - Multi-armed contextual bandit (d=6, K=3)            │
               │  - Ridge regression via np.linalg.solve()              │
               │  - Risk-penalized score: UCB_a - lambda * rho_a * R(x) │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Candidate Action (0, 1, or 2)
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │      Module 06: Deterministic SLA & Security Guardrail │
               │  - Module 05 Security State & Overhead Profile         │
               │  - Hard Capacity Limit: sum(BW) <= 10.0 Mbps           │
               │  - URLLC Latency Gate: latency <= 15.0 ms              │
               │  - Loss Gate: loss <= 1.0% | Risk Gate: risk <= 0.7    │
               └──────────────┬──────────────────────────┬──────────────┘
                              │ SAFE                     │ UNSAFE
                              ▼                          ▼
               ┌────────────────────────┐  ┌────────────────────────────┐
               │   Approved Action      │  │ REJECT or DETERMINISTIC    │
               │   Forwarded to SDN     │  │ REPAIR to Safe Allocation  │
               └──────────────┬─────────┘  └─────────────┬──────────────┘
                              │                          │
                              └───────────┬──────────────┘
                                          │ Safe Enforcement
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │             Module 07: Ryu OpenFlow 1.3 Controller     │
               │  - Dynamic meter & queue slice reconfiguration         │
               │  - MAC-learning L2 forwarding on TCP port 6633         │
               └────────────────────────────────────────────────────────┘
```

---

## 2. Network Topology & Baseline Congestion Problem

The experimental topology is implemented in [`topology/topology.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/topology/topology.py) using Mininet, Open vSwitch, and Linux Traffic Control (`tc`).

### Logical Slices & Service Level Agreements

| Slice | Host Pair | Traffic Profile | Service Level Agreement (SLA) |
|---|---|---|---|
| **URLLC** | Host `H1` $\leftrightarrow$ Host `H4` | Mission-critical low-latency | Latency $\le 15.0\text{ ms}$, Loss $\le 1.0\%$, Min Bandwidth $\ge 2.0\text{ Mbps}$ |
| **eMBB** | Host `H2` $\leftrightarrow$ Host `H5` | High-bandwidth multimedia | Best-effort high throughput up to bottleneck capacity |
| **Best Effort (BE)** | Host `H3` $\leftrightarrow$ Host `H6` | Background web/elastic traffic | Remaining unallocated capacity |

### Physical Bottleneck Configuration

```text
   H1 (URLLC Source) ────┐                                ┌──── H4 (URLLC Sink)
   H2 (eMBB Source)  ────┤        10 Mbps Bottleneck      ├──── H5 (eMBB Sink)
   H3 (BE Source)    ────┴── Switch S1 ════════ Switch S2 ──┴──── H6 (BE Sink)
                               (s1-eth4)    (s2-eth4)
                              Delay: 5 ms, Buffer: 50 pkts
```

- **Switches:** Two Open vSwitch bridges (`S1`, `S2`) connected via OpenFlow 1.3 to the Ryu controller.
- **Bottleneck Link:** The inter-switch link (`s1-eth4` $\leftrightarrow$ `s2-eth4`) is constrained to **10 Mbps** bandwidth with a **5 ms propagation delay** (minimum round-trip time $\approx 10\text{ ms}$) and a Linux `tc` queue limit of **50 packets**.

### Empirical Baseline Results (Unregulated Network)

Baseline experiments conducted with concurrent `iperf3` (eMBB) and high-frequency `ping` (URLLC) prove the starvation problem:

```text
[Baseline Testbed Measurements]
1. Idle / URLLC Alone:
   Latency: Min = 10.09 ms, Avg = 10.15 ms, Max = 11.20 ms | Loss = 0.0%  --> SAFE (Within SLA)

2. Unregulated eMBB Burst (9.0 Mbps iperf3):
   Latency: Min = 10.09 ms, Avg = 29.88 ms, Max = 122.44 ms | Loss = 0.0% --> VIOLATION (> 15 ms SLA)
```

Because average latency nearly triples under heavy eMBB traffic, dynamic slice adaptation with hard safety enforcement is required.

---

## 3. Implemented Modules & Technical Formulas

### Module 01: SDN Network & Slicing Topology
- **Implementation:** [`topology/topology.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/topology/topology.py)
- Builds the 2-switch, 6-host Mininet topology. Configures per-interface bandwidth and delay using Linux HTB qdiscs.

### Module 07: SDN Control Plane
- **Implementation:** [`controller/ryu_controller.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/controller/ryu_controller.py)
- Ryu OpenFlow 1.3 MAC-learning switch controller listening on `0.0.0.0:6633`. Dynamically installs bidirectional flow entries, achieving **0% packet loss** across all host pairs during `pingall`.

### Module 02: Network Telemetry Collector
- **Implementation:** [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py)
- **Key Class:** [`TelemetryRecord`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py#L29) dataclass.
- **Collection Techniques:**
  1. *Active Probing:* Runs `mnexec -a <H1_PID> ping -c <count> -i 0.2 <H4_IP>` directly inside host `H1`'s network namespace, avoiding host-isolation anomalies.
  2. *Passive Interface Monitoring:* Reads bytes from `/sys/class/net/s1-eth4/statistics/`.
  3. *Queue Backlog Monitoring:* Parses `tc -s qdisc show dev s1-eth4` to extract current packet queue depth.
  4. *Defensive Sentinel:* Returns `-1.0 ms` latency and `100.0%` loss on dropped probes without crashing.
  5. *Persistence:* Thread-safe CSV appending to `data/telemetry.csv`.
- **Status:** **15 unit tests passing** in [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py).

### Module 03: Context & Feature Extraction
- **Implementation:** [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py)
- **Key Class:** [`ContextBuilder`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py#L31)
- **Mathematical Transformation:** Maps raw telemetry into a bounded 6D context vector $\mathbf{x}_t \in \mathbb{R}^6$:

$$\mathbf{x}_t = \begin{bmatrix}
x_0 \\
x_1 \\
x_2 \\
x_3 \\
x_4 \\
x_5
\end{bmatrix} = \begin{bmatrix}
1.0 & \text{(Bias / Intercept)} \\
\min\left(1.0, \frac{\text{URLLC Latency (ms)}}{50.0}\right) & \text{(Normalized Latency)} \\
\min\left(1.0, \frac{\text{Throughput (Mbps)}}{10.0}\right) & \text{(Normalized Bottleneck Rate)} \\
\min\left(1.0, \frac{\text{Queue Backlog (pkts)}}{50.0}\right) & \text{(Normalized Buffer Depth)} \\
\text{clip}\left(\frac{\text{Latency}_t - \text{Latency}_{t-1}}{10.0}, -1.0, 1.0\right) & \text{(Temporal Latency Velocity)} \\
\frac{\text{Packet Loss (\%)}}{100.0} & \text{(Normalized Packet Loss Ratio)}
\end{bmatrix}$$

- **Sentinel Handling:** Latency sentinel `-1.0 ms` is mapped to worst-case $x_1 = 1.0$.
- **Status:** **17 unit tests passing** in [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py).

### Module 04: SRA-LinUCB Decision Engine
- **Implementation:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py)
- **Key Class:** [`SRALinUCB`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L59)
- **Action Space ($K=3$):**
  - Action `0`: `DECREASE_EMBB` (Throttles eMBB; de-congesting risk profile $\rho_0 = -1.0$)
  - Action `1`: `MAINTAIN` (Holds steady; neutral risk profile $\rho_1 = 0.0$)
  - Action `2`: `INCREASE_EMBB` (Expands eMBB; congestion risk profile $\rho_2 = +1.0$)
- **Formulas & Algorithm:**
  - Online Ridge Regression Precision Matrix:
    $$A_a = I_6 + \sum_{\tau=1}^t \mathbf{x}_\tau \mathbf{x}_\tau^T \in \mathbb{R}^{6 \times 6}$$
  - Reward-Weighted Context Accumulator:
    $$\mathbf{b}_a = \sum_{\tau=1}^t r_\tau \mathbf{x}_\tau \in \mathbb{R}^6$$
  - Weight estimate $\hat{\boldsymbol{\theta}}_a$ calculated using numerically stable solver `np.linalg.solve(A_a, b_a)`.
  - Context Risk Indicator:
    $$R(\mathbf{x}_t) = w_1 x_1 + w_3 x_3 + w_4 \max(0, x_4) + w_5 x_5, \quad \mathbf{w} = [0.4, 0.3, 0.2, 0.1]$$
  - Final Selection Score:
    $$\text{Score}_a(\mathbf{x}_t) = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T A_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$$
  - Candidate Action:
    $$a^* = \arg\max_{a \in \{0, 1, 2\}} \text{Score}_a(\mathbf{x}_t)$$
- **Status:** **11 unit tests passing** in [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py).

### Module 05: Security & Overhead Profiling
- **Implementation:** [`security/security_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_config.py), [`security/security_metrics.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_metrics.py), [`security/wireguard_adapter.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/wireguard_adapter.py)
- **Key Classes:** [`SecurityState`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_config.py#L37), [`SecurityMetrics`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_metrics.py#L12), [`WireGuardAdapter`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/wireguard_adapter.py#L13).
- Models crypto tunnel overhead (crypto latency inflation, throughput penalty, loss delta) and distinguishes configured defaults from measured live telemetry.
- **Status:** **13 unit tests passing** in [`tests/test_security.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py).

### Module 06: Deterministic SLA & Security Guardrail
- **Implementation:** [`guardrail/guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py), [`guardrail/sla_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/sla_config.py)
- **Key Class:** [`SLASecurityGuardrail`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py#L35)
- **Deterministic Hard Constraints:**
  1. Total link capacity: $\sum BW_{\text{slices}} \le 10.0\text{ Mbps}$
  2. URLLC minimum guaranteed bandwidth: $BW_{\text{URLLC}} \ge 2.0\text{ Mbps}$
  3. URLLC latency SLA: Measured latency $\le 15.0\text{ ms}$
  4. URLLC packet loss threshold: Measured loss $\le 1.0\%$
  5. Security threat threshold: Risk level $\le 0.70$
  6. Security overhead threshold: Added crypto delay $\le 5.0\text{ ms}$
- **Deterministic Repair:** Clamps over-allocated bandwidth configurations while guaranteeing the minimum URLLC reservation.
- **Status:** **14 unit tests passing** in [`tests/test_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py).

---

## 4. Verification & Test Suite (83 / 83 Passing)

The project includes an automated test suite comprising **83 tests**, verifying individual unit math, edge cases, and end-to-end integration across modules.

```bash
pytest -q
# Output: 83 passed in 0.95s
```

### Complete Test Breakdown

| Test Suite | Path | Count | Status | Scope |
|---|---|:---:|:---:|---|
| **Telemetry Tests** | [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py) | 15 | Passed | Ping parsing, rate derivation, queue stats, CSV logging |
| **Context Builder Tests** | [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py) | 17 | Passed | 6D normalization, bounds, trend clipping, sentinel handling |
| **SRA-LinUCB Tests** | [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py) | 11 | Passed | Ridge updates, numerical stability, risk penalties, UCB math |
| **M2 $\rightarrow$ M3 $\rightarrow$ M4 Pipeline** | [`ai/test_integration.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_integration.py) | 6 | Passed | End-to-end telemetry $\rightarrow$ context $\rightarrow$ action selection |
| **Security Profiling Tests** | [`tests/test_security.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) | 13 | Passed | SecurityState, overhead metrics, WireGuard adapter |
| **SLA Guardrail Tests** | [`tests/test_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) | 14 | Passed | SLA gates, capacity limits, repair logic, discrete actions |
| **End-to-End Pipeline Guardrail** | [`tests/test_pipeline_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) | 7 | Passed | M2 $\rightarrow$ M3 $\rightarrow$ M4 $\rightarrow$ M6 closed-loop validation |
| **Total** | **Full Regression Suite** | **83** | **100% Passed** | Complete cross-module regression |

### Key Verified Pipeline Scenarios

The integration tests in [`tests/test_pipeline_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) explicitly verify:
1. **Healthy Network:** Safe context approves candidate actions (`is_safe = True, violations = []`).
2. **Latency SLA Violation:** Latency $> 15.0\text{ ms}$ immediately rejected with `URLLC_LATENCY_VIOLATION`.
3. **Packet Loss SLA Violation:** Loss $> 1.0\%$ immediately rejected with `PACKET_LOSS_VIOLATION`.
4. **Congestion Protection:** High latency/queue state suppresses unsafe `INCREASE_EMBB` (Action 2).
5. **Deterministic Repair:** Over-allocated total bandwidth ($> 10\text{ Mbps}$) is scaled down while preserving URLLC $\ge 2\text{ Mbps}$.
6. **Security Threat & Overhead:** Risk level $> 0.70$ or added crypto delay $> 5.0\text{ ms}$ is flagged and blocked.
7. **Exact Boundary Conditions:** Confirms exact equality thresholds ($\le 15.0\text{ ms}$, $\le 1.0\%$) behave consistently.

---

## 5. Future Remaining Work

The remaining project phases will complete data-plane actuation, online reward feedback, comparative evaluation benchmarks, and live visualization.

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                FUTURE REMAINING WORK                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│  PHASE 8: Module 08 — Closed-Loop Reward Engine & Feedback                             │
│  ─────────────────────────────────────────────────────────                             │
│  1. Implement ai/reward_engine.py:                                                     │
│     - Multi-objective scalar reward function:                                          │
│       r_t = w_tput * Throughput_norm - w_lat * Latency_norm - w_loss * Loss_norm       │
│             - SLA_Penalty(t)                                                           │
│     - Non-linear quadratic barrier penalty:                                            │
│       SLA_Penalty(t) = beta * (max(0, Latency_ms - 15.0))^2                            │
│     - Online learning feedback loop:                                                   │
│       Collect telemetry at t+1 -> compute r_t -> call SRALinUCB.update(a_t, x_t, r_t)  │
│                                                                                        │
│  PHASE 9: Data-Plane Dynamic Actuation (Ryu Meter & Queue Control)                     │
│  ─────────────────────────────────────────────────────────────────                     │
│  1. Implement controller/slicing_actuator.py:                                          │
│     - Connect guardrail-approved safe action directly to OpenFlow 1.3 switches:        │
│       * Approach A: OpenFlow 1.3 Meter Bands (OFPMeterMod) per slice flow.             │
│       * Approach B: Dynamic Linux HTB QoS Queues via ovs-vsctl and tc.                 │
│     - Ensure hitless bandwidth adjustments without interrupting active TCP streams.    │
│                                                                                        │
│  PHASE 10: Module 09 — Comprehensive Comparative Evaluation & Benchmarks               │
│  ───────────────────────────────────────────────────────────────────────               │
│  1. Automated experimental test harness (experiments/run_evaluation.py):               │
│     Evaluate and compare THREE distinct control paradigms under identical traffic:    │
│     - Benchmark 1: Static Slicing (Fixed 3 Mbps URLLC / 5 Mbps eMBB / 2 Mbps BE).      │
│     - Benchmark 2: Unsafe AI Dynamic Slicing (LinUCB directly actuating without M6).   │
│     - Benchmark 3: Proposed AI-Safe Dynamic Slicing (SRA-LinUCB + SLA Guardrail).      │
│  2. Quantitative Evaluation Metrics to report:                                         │
│     - URLLC SLA Violation Ratio: % of operational time latency exceeds 15.0 ms.        │
│     - Latency Distribution: Min, mean, median, and 99th-percentile (p99) latency.      │
│     - eMBB Throughput & Link Utilization: Aggregate throughput over 10 Mbps bottleneck.│
│     - Cumulative Regret & Convergence Time of SRA-LinUCB.                              │
│     - Guardrail Safety Intervention Statistics: Count of approved, rejected, repaired.│
│     - Security Overhead Analysis: Impact of active WireGuard encryption on SLA budget. │
│                                                                                        │
│  PHASE 11: Real-Time Telemetry & Monitoring Dashboard                                  │
│  ────────────────────────────────────────────────────                                  │
│  1. Implement dashboard/app.py (Streamlit / Dash / Web UI):                            │
│     - Real-time strip charts for URLLC latency, queue backlog, and eMBB throughput.    │
│     - 6D Context vector radar chart (x_0 through x_5).                                 │
│     - Bandit action confidence bounds (UCB scores) and selected arm.                   │
│     - Live Guardrail Safety Status Badge (APPROVED, REJECTED, REPAIRED).               │
│     - Dynamic slice bandwidth allocation distribution gauge.                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Repository File Layout

```text
AI-Safe-Dynamic-Slicing/
├── README.md                      # Complete system documentation & roadmap
├── requirements.txt               # Dependencies (numpy, ryu, pytest, etc.)
│
├── topology/                      # Module 01: SDN Network & Slices
│   └── topology.py                # 2-switch, 6-host Mininet topology with 10 Mbps bottleneck
│
├── controller/                    # Module 07: SDN Control Plane
│   └── ryu_controller.py          # Ryu OpenFlow 1.3 learning switch controller
│
├── telemetry/                     # Module 02: Network Telemetry Collector
│   ├── monitor.py                 # TelemetryRecord, namespace-aware probing, tc parsing
│   └── test_telemetry.py          # 15 unit tests for telemetry collection
│
├── ai/                            # Modules 03 & 04: AI Context & Decision Engine
│   ├── context_builder.py         # Module 03: Telemetry-to-context 6D normalization
│   ├── linucb.py                  # Module 04: SRA-LinUCB linear contextual bandit
│   ├── test_context_builder.py    # 17 unit tests for context building
│   ├── test_linucb.py             # 11 unit tests for SRA-LinUCB algorithm
│   ├── test_integration.py        # 6 integration tests (M2 -> M3 -> M4 pipeline)
│   └── test_pipeline_live.py      # Standalone live interactive pipeline demonstration
│
├── security/                      # Module 05: Security & Overhead Profiling
│   ├── __init__.py
│   ├── security_config.py         # SecurityState dataclass, modes, protocol defaults
│   ├── security_metrics.py        # Pure functions for security overhead calculation
│   └── wireguard_adapter.py       # WireGuard system adapter and simulation fallback
│
├── guardrail/                     # Module 06: Deterministic SLA & Security Guardrail
│   ├── __init__.py
│   ├── sla_config.py              # GuardrailConfig dataclass (thresholds and limits)
│   └── guardrail.py               # SLASecurityGuardrail validation and repair engine
│
├── tests/                         # Modules 05 & 06 Unit & Pipeline Integration Tests
│   ├── __init__.py
│   ├── test_security.py           # 13 unit tests for security profiling
│   ├── test_guardrail.py          # 14 unit tests for SLA guardrail validation
│   └── test_pipeline_guardrail.py # 7 end-to-end integration tests (M2 -> M3 -> M4 -> M6)
│
├── data/                          # Telemetry datasets
│   └── telemetry.csv              # Runtime telemetry log generated by monitor.py
│
└── results/                       # Experimental evaluation results and plots
```

---

## 7. Setup & Execution Instructions

### Environment Prerequisites

The project runs on **Windows with WSL2 Ubuntu 22.04 LTS**.

| Tool | Version | Purpose |
|---|---|---|
| **Python** | 3.9 (Ryu controller) / 3.10, 3.11 (AI & Tests) | Execution environments |
| **Ryu** | 4.34 | SDN OpenFlow 1.3 controller |
| **Mininet** | 2.3.0 | Network data plane emulation |
| **Open vSwitch** | 3.3.9 | Virtual SDN switching |
| **iperf3** | 3.16 | Traffic generation & throughput testing |

### Running the Test Suite (83 Tests)

Run the entire automated regression suite from the project root:

```bash
# Run all 83 tests in quiet mode
pytest -q

# Run with per-test details
pytest -v
```

### Running the Live Pipeline Demo

To execute the M2 $\rightarrow$ M3 $\rightarrow$ M4 pipeline processing simulated network state steps:

```bash
python ai/test_pipeline_live.py
```

### Running the Live SDN Testbed (WSL2)

#### Terminal 1: Start Ryu Controller
```bash
pyenv activate ryu-3.9
cd ~/AI-Safe-Dynamic-Slicing
ryu-manager controller/ryu_controller.py
```

#### Terminal 2: Start Mininet Network
```bash
pyenv activate ryu-3.9
cd ~/AI-Safe-Dynamic-Slicing
sudo mn -c   # Clean up residual OVS state
sudo "$(pyenv which python)" topology/topology.py
```

#### Terminal 3: Generate Traffic in Mininet
```bash
# Verify connectivity
mininet> pingall

# Run eMBB background traffic (H2 -> H5)
mininet> h5 iperf3 -s -D
mininet> h2 iperf3 -c 10.0.0.5 -t 30 -b 9M &

# Monitor URLLC latency (H1 -> H4)
mininet> h4 iperf3 -s -D
mininet> h1 ping -i 0.2 -c 50 h4
```
