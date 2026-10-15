# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

[![Tests](https://img.shields.io/badge/Tests-114%20Passed-brightgreen)](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests)
[![Python](https://img.shields.io/badge/Python-3.9%20%7C%203.10%20%7C%203.11-blue)](https://www.python.org/)
[![SDN](https://img.shields.io/badge/SDN-Ryu%204.34%20%2B%20OpenFlow%201.3-orange)](https://ryu-sdn.org/)
[![Data Plane](https://img.shields.io/badge/Data%20Plane-Mininet%20%2B%20Open%20vSwitch-lightgrey)](http://mininet.org/)
[![Modules](https://img.shields.io/badge/Modules-1%20to%209%20Integrated-success)](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing)

---

## 1. Project Overview & Architecture

This project implements an **AI-driven, safety-constrained dynamic network slicing system** for Software-Defined Networks (SDN).

In shared multi-tenant 5G/6G networks, bandwidth-hungry applications (such as enhanced Mobile Broadband / eMBB 4K video) compete for bottleneck link capacity against mission-critical, low-latency traffic (such as Ultra-Reliable Low-Latency Communication / URLLC for autonomous vehicles, industrial robotics, and healthcare). Unregulated bandwidth competition leads to bufferbloat, queuing delay spikes, and packet drops that breach Service Level Agreements (SLAs).

### Core Architectural Principle

> **"Let AI optimize the network, but never let AI optimize at the cost of a critical SLA."**

The system establishes an architectural boundary between optimization and safety:
- **Optimization Layer (AI):** A Security- and Risk-Aware Linear Upper Confidence Bound ([`SRALinUCB`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py)) contextual bandit explores and optimizes resource allocations.
- **Safety Layer (Guardrail):** An independent deterministic verifier ([`SLASecurityGuardrail`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py)) intercepts candidate actions and enforces hard physical capacity, latency, loss, and security constraints *before* any flow modifications reach the data plane.
- **Feedback & Learning Layer:** A closed-loop reward engine and causal learner ([`feedback/`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback)) updates bandit parameters strictly based on actual executed allocations, with safe feedback attribution for repaired and rejected actions.

### Complete System Architecture

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
                                          │ TelemetryRecord (Raw stats)
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
               │  - Module 05 Security State & WireGuard Profile        │
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
                                          │ Executed Safe Allocation
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │             Module 07: Ryu OpenFlow 1.3 Controller     │
               │  - Dynamic meter & queue slice reconfiguration         │
               │  - MAC-learning L2 forwarding on TCP port 6633         │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Post-Enforcement Telemetry
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │        Module 08: Feedback & Online Learning Engine    │
               │  - Multi-Objective Reward: TPut, Latency, Loss, SLA    │
               │  - Quadratic Barrier Penalty for SLA Violations        │
               │  - Causal Safe Attribution: Updates executed arms only │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Model Update: A_a, b_a
                                          └───────► (Back to Module 04)
```

---

## 2. Network Topology & Slicing Specifications

Implemented in [`topology/topology.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/topology/topology.py) using Mininet, Open vSwitch, and Linux Traffic Control (`tc`).

### Logical Slices & Service Level Agreements

| Slice | Host Pair | Traffic Profile | Service Level Agreement (SLA) | Initial Share |
|---|---|---|---|:---:|
| **URLLC** | Host `H1` $\leftrightarrow$ Host `H4` | Ultra-Reliable Low-Latency | Latency $\le 15.0\text{ ms}$, Loss $\le 1.0\%$, Min Bandwidth $\ge 3.0\text{ Mbps}$ | $3.0\text{ Mbps}$ |
| **eMBB** | Host `H2` $\leftrightarrow$ Host `H5` | High-Throughput Video/Bulk | High throughput up to remaining link budget | $5.0\text{ Mbps}$ |
| **Best Effort (BE)** | Host `H3` $\leftrightarrow$ Host `H6` | Background Elastic Traffic | Elastic best-effort background communication | $2.0\text{ Mbps}$ |

### Physical Bottleneck Configuration

```text
   H1 (URLLC Source) ────┐                                ┌──── H4 (URLLC Sink)
   H2 (eMBB Source)  ────┤        10 Mbps Bottleneck      ├──── H5 (eMBB Sink)
   H3 (BE Source)    ────┴── Switch S1 ════════ Switch S2 ──┴──── H6 (BE Sink)
                               (s1-eth4)    (s2-eth4)
                              Delay: 5 ms, Buffer: 50 pkts
```

- **Switches:** Two Open vSwitch bridges (`S1`, `S2`) connected via OpenFlow 1.3 to the Ryu controller.
- **Bottleneck Link:** The inter-switch link (`s1-eth4` $\leftrightarrow$ `s2-eth4`) is constrained to **10.0 Mbps** bandwidth with a **5.0 ms propagation delay** (minimum round-trip time $RTT_{\text{base}} \approx 10.15\text{ ms}$) and an egress buffer limit of **50 packets**.

### Empirical Congestion Baseline (The Starvation Problem)

Controlled network experiments demonstrate why static or unprotected networks fail:
1. **Idle / URLLC Alone:** Average latency is **10.15 ms** with **0.0% packet loss** (well within the 15.0 ms SLA).
2. **Unregulated eMBB Burst (9.0 Mbps via iperf3):**
   - Average URLLC latency surges to **29.88 ms**.
   - Maximum observed latency spikes to **122.44 ms**.
   - The 15.0 ms SLA threshold is heavily violated, starving mission-critical traffic.

---

## 3. Implemented Modules & Technical Formulations

### Module 01: SDN Network & Slicing Topology
- **File:** [`topology/topology.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/topology/topology.py)
- Builds the 2-switch, 6-host Mininet topology. Configures per-interface bandwidth, propagation delay, and buffer sizes using Linux HTB qdiscs.

### Module 07: SDN Control Plane
- **File:** [`controller/ryu_controller.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/controller/ryu_controller.py)
- Asynchronous Ryu OpenFlow 1.3 MAC-learning switch controller listening on TCP port 6633. Dynamically installs bidirectional flow rules, achieving **0% packet loss** during `pingall`.

### Module 02: Network Telemetry Collector
- **File:** [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py)
- **Key Class:** [`TelemetryRecord`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py#L29) dataclass.
- **Capabilities:**
  1. *Active Probing:* Runs `mnexec -a <H1_PID> ping -c <count> -i 0.2 <H4_IP>` directly inside host `H1`'s isolated network namespace.
  2. *Passive Interface Monitoring:* Reads bytes from `/sys/class/net/s1-eth4/statistics/`.
  3. *Queue Backlog Monitoring:* Parses `tc -s qdisc show dev s1-eth4` to extract current packet queue depth.
  4. *Defensive Sentinel:* Returns `-1.0 ms` latency and `100.0%` loss on dropped probes without crashing.
  5. *Persistence:* Thread-safe CSV logging to `data/telemetry.csv`.

### Module 03: Context & Feature Extraction
- **File:** [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py)
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

### Module 04: SRA-LinUCB Decision Engine
- **File:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py)
- **Key Class:** [`SRALinUCB`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L59)
- **Action Space ($K=3$):**
  - Action `0`: `DECREASE_EMBB` (Throttles eMBB; de-congesting risk profile $\rho_0 = -1.0$)
  - Action `1`: `MAINTAIN` (Holds steady; neutral risk profile $\rho_1 = 0.0$)
  - Action `2`: `INCREASE_EMBB` (Expands eMBB; congestion risk profile $\rho_2 = +1.0$)
- **Mathematical Formulations:**
  - Online Ridge Regression Precision Matrix:
    $$\mathbf{A}_a = \mathbf{I}_6 + \sum_{\tau=1}^t \mathbf{x}_\tau \mathbf{x}_\tau^T \in \mathbb{R}^{6 \times 6}$$
  - Reward-Weighted Context Accumulator:
    $$\mathbf{b}_a = \sum_{\tau=1}^t r_\tau \mathbf{x}_\tau \in \mathbb{R}^6$$
  - Weight estimate $\hat{\boldsymbol{\theta}}_a$ computed via numerically stable `np.linalg.solve(A_a, b_a)`.
  - Context Risk Indicator:
    $$R(\mathbf{x}_t) = 0.4 x_1 + 0.3 x_3 + 0.2 \max(0, x_4) + 0.1 x_5$$
  - SRA Action Selection Score:
    $$\text{Score}_a(\mathbf{x}_t) = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$$
  - Candidate Action:
    $$a^* = \arg\max_{a \in \{0, 1, 2\}} \text{Score}_a(\mathbf{x}_t)$$

### Module 05: Security & Overhead Profiling
- **Files:** [`security/security_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_config.py), [`security/security_metrics.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_metrics.py), [`security/wireguard_adapter.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/wireguard_adapter.py)
- **Key Classes:** [`SecurityState`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_config.py#L37), [`SecurityMetrics`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_metrics.py#L12), [`WireGuardAdapter`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/wireguard_adapter.py#L13).
- Models crypto tunnel delay ($\Delta_{\text{crypto}} \approx 1.2\text{ ms}$), throughput penalty, and threat levels. Distinguishes live empirical measurements (`is_measured=True`) from simulation defaults.

### Module 06: Deterministic SLA & Security Guardrail
- **Files:** [`guardrail/guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py), [`guardrail/sla_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/sla_config.py)
- **Key Class:** [`SLASecurityGuardrail`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py#L35)
- **Six Immutable Operational Gates:**
  1. Total Link Capacity Gate: $\sum \text{Bandwidth}_{\text{slices}} \le 10.0\text{ Mbps}$
  2. URLLC Guaranteed Reservation Gate: $\text{Bandwidth}_{\text{URLLC}} \ge 3.0\text{ Mbps}$
  3. URLLC Latency SLA Gate: Measured latency $\le 15.0\text{ ms}$
  4. Packet Loss Gate: Drop rate $\le 1.0\%$
  5. Security Threat Gate: Risk score $\le 0.70$
  6. Crypto Overhead Gate: Added crypto delay $\le 5.0\text{ ms}$
- **Deterministic Repair Mechanism:** Over-allocated requests (e.g. $13.0\text{ Mbps} > 10.0\text{ Mbps}$) are automatically repaired by locking URLLC at its guaranteed reservation ($\ge 3.0\text{ Mbps}$), preserving a Best-Effort baseline, and scaling eMBB to exactly fill the remaining link budget ($6.5\text{ Mbps}$), preventing packet drops without terminating flows.

### Module 08: Closed-Loop Reward Engine & Feedback Learner
- **Files:** [`feedback/reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/reward.py), [`feedback/learner.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/learner.py), [`feedback/__init__.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/__init__.py)
- **Key Classes:** [`RewardEngine`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/reward.py#L22), [`FeedbackLearner`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/learner.py#L28).
- **Multi-Objective Reward Function:**
  $$r_t = w_{\text{tput}} \cdot \tilde{T}_t - w_{\text{lat}} \cdot \tilde{L}_t - w_{\text{loss}} \cdot \tilde{P}_t - \text{Penalty}_{\text{SLA}}(t) - w_{\text{sec}} \cdot \tilde{S}_t$$
  - Normalized Throughput ($w_{\text{tput}} = 1.0$): $\tilde{T}_t = \min\left(1.0, \frac{\text{Throughput}}{10.0}\right)$
  - Operational Latency ($w_{\text{lat}} = 1.0$): $\tilde{L}_t = \min\left(1.0, \frac{\text{Latency}}{15.0}\right)$
  - Packet Loss ($w_{\text{loss}} = 2.0$): $\tilde{P}_t = \frac{\text{Loss \%}}{100.0}$
  - Security Overhead ($w_{\text{sec}} = 0.5$): Included strictly when `is_measured=True`.
- **Quadratic Barrier SLA Penalty:**
  $$\text{Penalty}_{\text{SLA}}(t) = \beta \cdot \max(0, \text{Latency}_{\text{ms}} - 15.0)^2, \quad \beta = 5.0$$
- **Causal Safe Attribution Policy:**
  - *Approved Actions:* Model updates $\mathbf{A}_a$ and $\mathbf{b}_a$ for the executed arm $a \in \{0, 1, 2\}$.
  - *Rejected Actions:* The model is **not updated** for the candidate arm, preventing false negative credit assignment.
  - *Repaired Actions:* Checked against discrete arms; unmapped repaired continuous allocations are logged without distorting bandit matrices.

### Module 09: Evaluation & Comparative Benchmarking
- **Files:** [`experiments/static_baseline.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/static_baseline.py), [`experiments/dynamic_baseline.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/dynamic_baseline.py), [`experiments/proposed_system.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/proposed_system.py), [`experiments/run_experiments.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/run_experiments.py)
- **First-Principles FIFO Queuing Simulation Model:**
  - Bottleneck Capacity: $C = 10.0\text{ Mbps}$, MTU packet size $P = 1500\text{ bytes} = 12,000\text{ bits}$.
  - Packet transmission delay: $t_{\text{tx}} = \frac{12,000}{10.0 \times 10^6} = 1.20\text{ ms/packet}$.
  - Queue dynamics: $\Delta Q = \frac{(\text{Aggregate Load} - C) \times 10^6 \times \Delta t}{12,000}$
  - Buffer limit: $50\text{ packets}$ ($60\text{ ms}$ max queuing delay before tail drop).
  - Simulated Latency: $RTT_{\text{sim}}(t) = RTT_{\text{base}} + (Q(t) \times 1.20\text{ ms}) + \Delta_{\text{crypto}}$.
- **Standardized 24-Column CSV Schema:** Full accounting of URLLC, eMBB, and Best-Effort offered rates, allocations, throughputs, drops, queue depth, simulated RTT, and decisions.

---

## 4. Benchmark Performance Results

All summary metrics are calculated strictly from the generated 20-step experimental CSV files:

```text
==================================================================================
 SIMULATION BENCHMARK SUMMARY TABLE (Trace-Driven Model)
 NOTE: Results are derived from a simplified FIFO queuing simulation model.
==================================================================================
Metric                         | Static (Fixed) | Dynamic (Unsafe) | Proposed (AI-Safe)
----------------------------------------------------------------------------------
URLLC Mean Simulated RTT       | 10.15 ms       | 11.15 ms         | 11.07 ms        
URLLC 99th-Percentile RTT      | 10.15 ms       | 26.35 ms (breach)| 12.51 ms (safe) 
eMBB Mean Throughput           | 4.02 Mbps      | 4.24 Mbps        | 4.19 Mbps       
eMBB Peak Throughput           | 5.00 Mbps      | 8.50 Mbps        | 6.50 Mbps       
URLLC Packet Loss              | 0.0 %          | 0.0 %            | 0.0 %           
SLA Violations (count / %)     | 0 (0.0%)       | 1 (5.0%)         | 0 (0.0%)        
Congestion Recovery Time       | 0.0 s          | 1.0 s            | 0.0 s           
Guardrail Repaired Actions     | 0 (N/A)        | 0 (Disabled)     | 3 (Active)      
Security Overhead Mode         | N/A            | Ignored          | Simulated (1.2 ms)
Deterministic Safety Guard     | No             | No               | Yes (Module 6)  
==================================================================================
```

### Analysis of Regimes

1. **Static Slicing (Fixed Partitioning):**
   - Fixed allocation: URLLC $3.0\text{ Mbps}$, eMBB $5.0\text{ Mbps}$, BE $2.0\text{ Mbps}$.
   - **Advantage:** Predictable; zero SLA violations ($RTT = 10.15\text{ ms}$).
   - **Disadvantage:** Inflexible; throttles eMBB throughput at $5.0\text{ Mbps}$ during peak demand despite idle bandwidth.
2. **Dynamic Slicing Without Safety (Unsafe LinUCB):**
   - Risk-neutral LinUCB ($\lambda = 0.0$, guardrail disabled).
   - **Behavior:** Greedily allocates $9.0\text{ Mbps}$ to eMBB during the surge. Aggregate load reaches $13.0\text{ Mbps}$, causing buffer accumulation ($16.67\text{ pkts}$), spiking latency to **$30.15\text{ ms}$**, and breaching the $15.0\text{ ms}$ SLA.
3. **Proposed AI-Safe Dynamic Slicing:**
   - SRA-LinUCB ($\lambda = 0.5$) with Module 6 Deterministic Guardrail and Module 8 Reward Feedback.
   - **Behavior:** During the surge, candidate requests of $13.0\text{ Mbps}$ are intercepted and deterministically repaired: URLLC reservation is protected at $\ge 3.0\text{ Mbps}$, BE is preserved, and eMBB is capped at $6.5\text{ Mbps}$.
   - **Outcome:** Zero SLA violations ($RTT_{\text{p99}} = 12.51\text{ ms}$), $0\text{ s}$ recovery time, and higher throughput ($4.19\text{ Mbps}$ mean) than static slicing.

### Generated Artifacts in `results/`

- [`results/comparison.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/comparison.png): Comparative bar chart (SLA Violations, Mean Latency, Throughput).
- [`results/latency.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/latency.png): 3-panel time-series showing URLLC latency response across all 20 steps.
- [`results/throughput.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/throughput.png): 3-panel time-series tracking per-slice bandwidth allocations.
- [`results/summary_table.md`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/summary_table.md): Formatted GitHub markdown comparison table.
- [`results/summary_table.txt`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/summary_table.txt): Clean text comparison table.
- [`results/static_results.csv`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/static_results.csv), [`dynamic_results.csv`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/dynamic_results.csv), [`proposed_results.csv`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/proposed_results.csv): Raw 24-column datasets.

---

## 5. Verification & Regression Suite (114 / 114 Passing)

The complete codebase is validated by **114 automated unit and integration tests** passing with 100% success:

```text
============================= 114 passed in 1.80s =============================
```

### Complete Test Suite Breakdown

| Test File | Module Under Test | Test Count | Scope Verified |
|---|---|:---:|---|
| [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py) | Module 03 (Context) | 17 | 6D normalization bounds, trend velocity, negative velocity, sentinel handling |
| [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py) | Module 04 (SRA-LinUCB) | 11 | Ridge regression updates, matrix solving (`solve` vs `inv`), risk dampening |
| [`ai/test_integration.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_integration.py) | Modules 02 $\rightarrow$ 03 $\rightarrow$ 04 | 6 | Dataflow integrity, multi-cycle healthy/congested transitions |
| [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py) | Module 02 (Telemetry) | 15 | Active ping parsing, loss percentage, rate calculation, queue backlog parsing |
| [`tests/test_security.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) | Module 05 (Security) | 13 | SecurityState dataclass, crypto overhead metrics, WireGuard fallback probe |
| [`tests/test_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) | Module 06 (Guardrail) | 14 | Hard capacity limits, URLLC latency gate, loss gate, proportional repair |
| [`tests/test_pipeline_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) | M2 $\rightarrow$ M3 $\rightarrow$ M4 $\rightarrow$ M6 | 7 | End-to-end closed-loop validation across 7 operational network scenarios |
| [`tests/test_slice_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_slice_config.py) | Slicing Config | 5 | Slice bandwidth floors, capacity ceiling constraints, default validation |
| [`feedback/test_reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_reward.py) | Module 08 (Reward Engine) | 8 | Multi-objective reward bounds, quadratic SLA barrier penalty, security term |
| [`feedback/test_learner.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_learner.py) | Module 08 (Feedback Learner)| 4 | SRA-LinUCB parameter updates, causal arm attribution, convergence |
| [`feedback/test_feedback.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_feedback.py) | Module 08 (Package Tests) | 2 | Module export sanity, legacy compatibility wrappers |
| [`tests/test_feedback.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_feedback.py) | Module 08 Integration | 5 | Safe feedback attribution on rejected/repaired actions, sentinel handling |
| [`tests/test_experiments.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_experiments.py) | Module 09 (Experiments) | 7 | FIFO queue dynamics, buffer overflow, real guardrail intervention, schema |
| **Total** | **Full Regression Suite** | **114** | **100% Passed** across Python 3.9, 3.10, and 3.11 |

---

## 6. Setup & Execution Instructions

### Environment Prerequisites

- **OS:** Windows 10/11 or Ubuntu 22.04 LTS (native or WSL2).
- **Python:** Python 3.9 (for Ryu SDN controller) / Python 3.10 or 3.11 (for AI, Guardrail, Feedback, and Experiments).
- **Packages:** `numpy`, `matplotlib`, `pytest` (listed in [`requirements.txt`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/requirements.txt)).

---

### Execution Option 1: Automated Testing & Evaluation (Windows / Linux)

#### 1. Run the Full 114-Test Regression Suite
```bash
pytest
```
*(To suppress third-party matplotlib deprecation warnings on Python 3.9, run `pytest --disable-warnings`).*

#### 2. Run Module 9 Experiments & Regenerate Graphs
```bash
python experiments/run_experiments.py
```
*(Executes all three slicing regimes across the 20-step workload, writes CSV files, plots latency/throughput/comparison PNGs, and prints the summary table).*

#### 3. Display the Benchmark Comparison Table Instantly
```bash
python experiments/run_experiments.py --table-only
```
*(Loads saved experiment data instantly and saves clean copies to `results/summary_table.md` and `results/summary_table.txt`).*

#### 4. Run the Interactive 5-Step Pipeline Simulation
```bash
python ai/test_pipeline_live.py
```
*(Demonstrates the live dataflow from telemetry to context vector $\mathbf{x}_t$, risk penalties, and LinUCB candidate selection).*

---

### Execution Option 2: Live SDN Network Testbed (WSL2 / Ubuntu Linux)

To run the live closed loop against Mininet and Ryu:

#### Terminal 1: Start Ryu SDN Controller (Control Plane)
```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
ryu-manager controller/ryu_controller.py --verbose
keep running it dont close
```

#### Terminal 2: Start Mininet Network (Data Plane)
```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
sudo mn -c   # Clean up residual state
sudo "$(pyenv which python)" topology/topology.py
```

#### Terminal 3: Generate Traffic in Mininet
In Terminal 2 at the `mininet>` prompt:
```text
# Verify connectivity
mininet> pingall

# Start iperf3 servers on sink hosts
mininet> h4 iperf3 -s -D
mininet> h5 iperf3 -s -D

# Inject heavy eMBB traffic surge (H2 -> H5)
mininet> h2 iperf3 -c 10.0.0.5 -u -b 8.5M -t 60 &

# Ping URLLC (H1 -> H4)
mininet> h1 ping -i 0.2 -c 50 10.0.0.4
```

#### Terminal 4: Start Network Telemetry Monitor
```bash
cd ~/AI-Safe-Dynamic-Slicing
sudo python telemetry/monitor.py
```

#### Terminal 5: Run Live Closed-Loop AI Pipeline
```bash
cd ~/AI-Safe-Dynamic-Slicing
python ai/test_pipeline_live.py --live
```

---

## 7. Repository Directory Structure

```text
AI-Safe-Dynamic-Slicing/
├── README.md                      # Comprehensive system documentation
├── requirements.txt               # Project dependencies
├── COMPLETE_PROJECT_EXPLANATION.md # Master project explanation, architecture & results guide
├── PROJECT_PHASES_EXPLANATION.md  # Detailed phase walkthrough and Viva Q&A
│
├── topology/                      # Module 01: SDN Network & Topology
│   └── topology.py                # Mininet 2-switch, 6-host 10 Mbps bottleneck topology
│
├── controller/                    # Module 07: SDN Control Plane
│   └── ryu_controller.py          # Ryu OpenFlow 1.3 MAC-learning switch controller
│
├── telemetry/                     # Module 02: Network Telemetry Collector
│   ├── monitor.py                 # TelemetryRecord, namespace-aware probing, tc parser
│   └── test_telemetry.py          # 15 unit tests for telemetry
│
├── ai/                            # Modules 03 & 04: Context Builder & SRA-LinUCB
│   ├── context_builder.py         # Module 03: 6D context extraction and trend velocity
│   ├── linucb.py                  # Module 04: SRA-LinUCB contextual bandit
│   ├── test_context_builder.py    # 17 unit tests for context building
│   ├── test_linucb.py             # 11 unit tests for SRA-LinUCB algorithm
│   ├── test_integration.py        # 6 integration tests (M2 -> M3 -> M4)
│   └── test_pipeline_live.py      # Standalone live interactive pipeline demonstration
│
├── security/                      # Module 05: Security & Overhead Profiling
│   ├── security_config.py         # SecurityState dataclass, modes, protocol defaults
│   ├── security_metrics.py        # Overhead calculations (crypto delay, rate penalty)
│   └── wireguard_adapter.py       # WireGuard adapter probe and simulation fallback
│
├── guardrail/                     # Module 06: Deterministic SLA & Security Guardrail
│   ├── sla_config.py              # GuardrailConfig dataclass (thresholds and limits)
│   └── guardrail.py               # SLASecurityGuardrail validation and repair engine
│
├── feedback/                      # Module 08: Closed-Loop Feedback & Learning
│   ├── __init__.py                # Package exports
│   ├── reward.py                  # Continuous reward engine with quadratic SLA barrier
│   ├── learner.py                 # Causal FeedbackLearner updating SRA-LinUCB
│   ├── test_reward.py             # 8 unit tests for reward calculation
│   ├── test_learner.py            # 4 unit tests for online parameter updates
│   └── test_feedback.py           # 2 sanity and interface compatibility tests
│
├── slicing/                       # Slicing Configuration
│   └── slice_config.py            # Bandwidth limits, slice profiles, and validation
│
├── experiments/                   # Module 09: Evaluation & Comparative Benchmarks
│   ├── static_baseline.py         # Benchmark 1: Static fixed partitioning (3/5/2 Mbps)
│   ├── dynamic_baseline.py        # Benchmark 2: Unsafe dynamic LinUCB (no guardrail)
│   ├── proposed_system.py         # Benchmark 3: Proposed AI-Safe system (M4 + M6 + M8)
│   └── run_experiments.py         # Experiment runner, CSV loader, graph & table generator
│
├── tests/                         # Full Integration & Invariant Regression Suite
│   ├── test_security.py           # 13 tests for security profiling
│   ├── test_guardrail.py          # 14 tests for SLA guardrail validation
│   ├── test_pipeline_guardrail.py # 7 end-to-end integration tests (M2 -> M3 -> M4 -> M6)
│   ├── test_slice_config.py       # 5 tests for slice configuration constraints
│   ├── test_feedback.py           # 5 integration tests for feedback attribution
│   └── test_experiments.py        # 7 invariant tests for FIFO queuing and guardrail
│
├── data/                          # Telemetry datasets
│   └── telemetry.csv              # Runtime telemetry generated by monitor.py
│
└── results/                       # Generated Benchmark Results & Plots
    ├── static_results.csv         # 24-column dataset for static baseline
    ├── dynamic_results.csv        # 24-column dataset for dynamic unsafe baseline
    ├── proposed_results.csv       # 24-column dataset for proposed AI-safe system
    ├── latency.png                # URLLC latency comparison plot
    ├── throughput.png             # eMBB throughput adaptation plot
    ├── comparison.png             # Metric comparison bar chart
    ├── summary_table.md           # Formatted markdown summary table
    └── summary_table.txt          # Plain text summary table
```

---

## 8. Remaining Roadmap for Full Final Deployment

With Modules 1 through 9 fully implemented and passing all 114 tests, the remaining items for a complete final production release are:

1. **Phase 10: Dynamic Data-Plane Actuation (`controller/slicing_actuator.py`)**:
   - Push guardrail-approved safe bandwidth allocations directly to physical Open vSwitch flow tables using OpenFlow 1.3 Meter Bands (`OFPMeterMod`) or Linux HTB QoS queues via `tc` and `ovs-vsctl`.
2. **Phase 11: Real-Time Telemetry & Monitoring Dashboard (`dashboard/app.py`)**:
   - Build a browser-based UI (Streamlit or Dash) displaying real-time URLLC latency strip charts, dynamic slice allocation gauges, 6D context radar charts, and live guardrail status badges (`APPROVED`, `REJECTED`, `REPAIRED`).
3. **Phase 12: Unified Live Closed-Loop Runner (`run_live_system.py`)**:
   - Single-command orchestrator linking live Mininet traffic generation, telemetry monitoring, AI decision making, guardrail verification, data-plane actuation, and reward feedback learning into a unified real-time loop.
