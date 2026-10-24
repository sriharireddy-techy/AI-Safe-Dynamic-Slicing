# Contributions, Failure Scenarios & Production Roadmap
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## Table of Contents
1. [Team Contribution Breakdown](#1-team-contribution-breakdown)
2. [Deep-Dive Defense for My Modules (Srihari Reddy)](#2-deep-dive-defense-for-my-modules-srihari-reddy)
3. [Concise Teammate Presentation Summaries](#3-concise-teammate-presentation-summaries)
4. [Realistic Security & Failure Scenarios (15 Scenarios)](#4-realistic-security--failure-scenarios-15-scenarios)
5. [Achievable Production Roadmap (Phases 10–12)](#5-achievable-production-roadmap-phases-1012)

---

## 1. Team Contribution Breakdown

Verified directly against repository Git commit history (`git log --all --pretty=format:"%h - %an: %s"`):

| Contributor | Primary Modules & Responsibilities | Key Code Artifacts | Commits |
|---|---|---|---|
| **Srihari Reddy** *(You)* | **SDN Foundation, Baseline, Telemetry, Context Builder, SRA-LinUCB, Slicing Config & Full Pipeline Integration** | `topology/topology.py`, `telemetry/monitor.py`, `ai/context_builder.py`, `ai/linucb.py`, `slicing/slice_config.py`, `ai/test_*.py`, `README.md`, `COMPLETE_PROJECT_EXPLANATION.md` | `05a7147`, `aa16f83`, `1128507`, `1b1b289`, `d034e32`, `2c01906`, `d88588e`, `ce9bdf5` |
| **Preetham** *(masuldaripreetham2024-arch)* | **Security Profiling & Deterministic SLA Guardrail (Modules 05 & 06)** | `security/security_config.py`, `security/security_metrics.py`, `security/wireguard_adapter.py`, `guardrail/guardrail.py`, `guardrail/sla_config.py`, `tests/test_guardrail.py`, `tests/test_security.py` | `6d4024d`, `93a536f` |
| **Bishal** *(BishalDebnath-bit)* | **Reward Engine, Feedback Learner & Baseline Experiments (Modules 08 & 09)** | `feedback/reward.py`, `feedback/learner.py`, `experiments/static_baseline.py`, `experiments/dynamic_baseline.py`, `experiments/proposed_system.py`, `experiments/run_experiments.py` | `ef81fda`, `f0fa331`, `4f6b16a`, `fb5579d` |
| **Shared / Team** | Mininet topology testing, Ryu OpenFlow 1.3 MAC-learning setup, cross-module integration tests, regression debugging | `controller/ryu_controller.py`, `tests/test_pipeline_guardrail.py`, `tests/test_experiments.py` | Collaborative |

---

## 2. Deep-Dive Defense for My Modules (Srihari Reddy)

### A. Module 02: Network Telemetry Collector (`telemetry/monitor.py`)
- **30-Second Pitch:** "I built the non-invasive telemetry engine that continuously monitors physical and virtual network metrics. It probes URLLC latency through Mininet network namespaces using `mnexec`, derives egress throughput from Linux kernel sysfs byte counters, monitors bufferbloat from Linux `tc` queues, and exports defensive telemetry to CSV."
- **2-Minute Technical Explanation:** "In Linux SDN testbeds, Mininet isolates host interfaces in separate network namespaces. Running a standard ping from the root OS namespace fails. I solved this by dynamically discovering the operating system PID of host H1 and invoking `mnexec -a <PID> ping`, executing the active probe directly inside H1's isolated network stack. To compute throughput without adding probe traffic, I read cumulative bytes from `/sys/class/net/s1-eth4/statistics/tx_bytes` and calculate the differential rate over $\Delta t$. I also parsed `tc -s qdisc` to measure egress queue backlog in packets. If a probe drops completely, my code returns a defensive sentinel value (`-1.0 ms`, `100.0%` loss) rather than crashing the control loop."
- **Key Code:** [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py), [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py).
- **Mathematical Details:**
  $$\text{Throughput} = \frac{(\text{TX}_{\text{curr}} - \text{TX}_{\text{prev}}) \times 8.0}{\Delta t \times 1,000,000.0}$$
- **What I Must NOT Claim:** Do not claim that the telemetry collector samples every single packet in real-time. It samples at discrete intervals (1.0 s).

### B. Module 03: Context Builder (`ai/context_builder.py`)
- **30-Second Pitch:** "I developed the feature extraction module that converts heterogeneous network telemetry into a normalized, bounded 6-dimensional context vector $\mathbf{x}_t \in \mathbb{R}^6$, calculating temporal latency velocity to warn the AI before bufferbloat occurs."
- **2-Minute Technical Explanation:** "Machine learning algorithms suffer from numerical instability when inputs have mismatched scales. I designed `ContextBuilder` to normalize latency relative to a 50 ms ceiling, throughput to the 10 Mbps bottleneck, queue occupancy to the 50-packet buffer limit, and loss to 100%. Crucially, I engineered Feature 4: Temporal Latency Velocity ($x_4 = \text{clip}((\text{lat}_t - \text{lat}_{t-1})/10, -1, 1)$). This discrete derivative captures whether congestion is accelerating ($x_4 > 0$) or the network is recovering ($x_4 < 0$). I also built defensive sentinel sanitization: if a dropped probe passes $-1.0\text{ ms}$, my module overrides $x_1$ and $x_5$ to $1.0$ (maximum penalty), preventing linear models from treating a dropped connection as zero-latency."
- **Key Code:** [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py), [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py).
- **What I Must NOT Claim:** Do not claim that the context builder performs PCA or deep embeddings. It is a deterministic, domain-specific feature normalizer.

### C. Module 04: SRA-LinUCB Decision Engine (`ai/linucb.py`)
- **30-Second Pitch:** "I implemented the core AI decision engine using Security- and Risk-Aware LinUCB. It balances exploitation and exploration using closed-form ridge regression, while applying an SRA risk penalty to suppress risky actions during network stress."
- **2-Minute Technical Explanation:** "Standard LinUCB explores aggressively, picking risky bandwidth increases during stress just to reduce uncertainty. I implemented SRA-LinUCB with a Context Risk Indicator $R(\mathbf{x}_t) = 0.4 x_1 + 0.3 x_3 + 0.2 \max(0, x_4) + 0.1 x_5$. The action score is $\text{Score}_a = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$. For Action 2 (INCREASE_EMBB, $\rho_2 = +1.0$), high risk heavily penalizes its score. For Action 0 (DECREASE_EMBB, $\rho_0 = -1.0$), high risk boosts its score. To guarantee numerical stability, I solved for $\hat{\boldsymbol{\theta}}_a$ using `np.linalg.solve(A_a, b_a)` via LU/Cholesky decomposition rather than computing explicit matrix inverses."
- **Key Code:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py), [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py).
- **What I Must NOT Claim:** Do not claim that SRA-LinUCB alone guarantees 100% safety. It provides risk-averse guidance, but deterministic safety is strictly enforced by Module 06 Guardrail.

---

## 3. Concise Teammate Presentation Summaries

When presenting to faculty, use these descriptions for your teammates' work:

### Preetham's Modules (Modules 05 & 06: Security & Guardrail)
> "My teammate Preetham developed the Security Profiling and Deterministic Guardrail modules. In Module 05, he modeled the cryptographic latency overhead ($\approx 1.2\text{ ms}$) and header byte overhead of WireGuard secure tunnels, distinguishing measured kernel metrics from simulation baselines. In Module 06, he built the deterministic gatekeeper that enforces our 6 immutable safety gates—link capacity, URLLC minimum reservation, latency ceilings, packet loss, and security risk—implementing the proportional repair algorithm that automatically scales down over-budget allocations while protecting URLLC."

### Bishal's Modules (Modules 08 & 09: Feedback & Comparative Evaluation)
> "My teammate Bishal implemented the Closed-Loop Feedback Learner and Benchmark Evaluation. In Module 08, he created the multi-objective reward engine featuring a steep quadratic barrier penalty for SLA violations, along with Causal Safe Attribution to ensure the AI only updates parameters for executed actions. In Module 09, he implemented the trace-driven FIFO queuing simulation benchmark comparing Static, Unsafe Dynamic, and Proposed AI-Safe systems across a 20-step dynamic workload, generating the 24-column CSV datasets and performance plots."

---

## 4. Realistic Security & Failure Scenarios (15 Scenarios)

| # | Failure / Stress Scenario | What Current Code Does | What Robust Production Code Should Do | Safety Property at Stake | Verification Test / Evidence |
|---|---|---|---|---|---|
| **1** | AI proposes reducing URLLC below 3.0 Mbps | Guardrail flags `URLLC_MIN_BANDWIDTH_VIOLATION` and rejects/repairs. | Locks URLLC at guaranteed floor. | Starvation prevention. | [`test_guardrail.py::test_urllc_minimum_bandwidth_enforced`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) |
| **2** | Total requested allocation exceeds 10 Mbps | Guardrail triggers `_attempt_deterministic_repair()`, scaling eMBB down. | Proportional scaling preserving URLLC. | Physical capacity invariant. | [`test_guardrail.py::test_proportional_repair`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) |
| **3** | URLLC latency breaches 15.0 ms SLA | Guardrail rejects action (`URLLC_LATENCY_VIOLATION`); reward engine applies quadratic penalty. | Immediate throttle on non-critical slices. | Low-latency SLA guarantee. | [`test_pipeline_guardrail.py::test_latency_sla_breach`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) |
| **4** | Packet loss rises above 1.0% | Guardrail rejects action (`PACKET_LOSS_VIOLATION`). | Switch buffer drain. | Ultra-reliability invariant. | [`test_guardrail.py::test_loss_gate`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) |
| **5** | Security risk score exceeds 0.70 | Guardrail blocks candidate (`SECURITY_RISK_EXCEEDED`). | Divert traffic to inspection scrubber. | Threat containment. | [`test_security.py::test_risk_threshold`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) |
| **6** | Crypto delay exceeds 5.0 ms | Guardrail flags `SECURITY_OVERHEAD_EXCEEDED` and rejects. | Offload crypto to hardware accelerator. | Crypto delay ceiling. | [`test_guardrail.py::test_overhead_limit`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) |
| **7** | Telemetry probe dropped (sentinel -1.0) | Context builder maps $-1.0 \rightarrow 1.0$ (worst-case); reward applies max penalty 5.0. | Secondary ping retry via alternate path. | Resilience to probe loss. | [`test_context_builder.py::test_sentinel_handling`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py) |
| **8** | Guardrail rejects all candidates | System maintains current baseline allocation (`3/5/2 Mbps`). | Safe static fallback. | Fail-safe operation. | [`test_pipeline_guardrail.py::test_fallback`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) |
| **9** | Actuator command fails / times out | Planned Phase 10: Retain previous hardware flow rule. | Rollback transaction. | Control consistency. | Phase 10 Milestone. |
| **10** | Applied bandwidth differs from requested | Phase 10: Verify via `ovs-ofctl dump-meters`. | Alert operator on meter desync. | Data-plane compliance. | Phase 10 Milestone. |
| **11** | Network congested despite safe allocation | Temporal velocity $x_4 > 0$ triggers SRA risk suppression. | Dynamic throttle on eMBB. | Early congestion warning. | [`test_linucb.py::test_risk_suppression`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py) |
| **12** | Reward improves but SLA breached | Impossible: quadratic barrier penalty severely drives reward negative. | Mathematical penalty guarantee. | Optimization-safety alignment. | [`test_reward.py::test_quadratic_barrier`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_reward.py) |
| **13** | Learner receives feedback for repaired action | Causal Safe Attribution updates the *repaired* arm, not candidate. | Protects parameter matrices from false updates. | Causal learning integrity. | [`test_feedback.py::test_causal_attribution`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_feedback.py) |
| **14** | Controller running but traffic dropped | Verify flow rules installed via `ovs-ofctl dump-flows`. | Auto-reinstall table-miss rule. | Forwarding integrity. | Mininet CLI `pingall`. |
| **15** | WireGuard CLI (`wg`) uninstalled | `WireGuardAdapter` returns `available: False` cleanly. | Software fallback simulation. | Platform portability. | [`test_security.py::test_adapter_fallback`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) |

---

## 5. Achievable Production Roadmap (Phases 10–12)

```text
     [ Modules 1 - 9 Completed & Verified Across 114 Automated Tests ]
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │  Phase 10: Dynamic Data-Plane Rate Actuation           │
       │  - controller/slicing_actuator.py                      │
       │  - OpenFlow 1.3 Meter Bands (OFPMeterMod)              │
       │  - Linux HTB QoS queue modification (ovs-vsctl / tc)   │
       │  - Completion Metric: Verify rate via iperf3 on H2     │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │  Phase 11: Real-Time Web Dashboard                     │
       │  - dashboard/app.py (Streamlit)                        │
       │  - Real-time URLLC latency strip chart                 │
       │  - Live Guardrail Badge (APPROVED, REPAIRED, REJECTED) │
       │  - Completion Metric: Browser visualization at 1 Hz    │
       └────────────────────────────┬───────────────────────────┘
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │  Phase 12: Unified Live Closed-Loop Runner             │
       │  - run_live_system.py                                  │
       │  - Single command orchestrating Mininet, Ryu, Telemetry│
       │    AI, Guardrail, Actuator, and Feedback in real time  │
       │  - Completion Metric: 100-step live Mininet autonomous │
       │    closed-loop run with zero SLA violations            │
       └────────────────────────────────────────────────────────┘
```
