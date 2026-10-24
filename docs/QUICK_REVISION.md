# Ultimate Last-Minute Revision Cheat Sheet
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## 1. 60-Second Elevator Pitch
> "In shared 5G/6G networks, heavy video traffic (eMBB) causes bufferbloat that starves latency-sensitive traffic (URLLC), breaching the 15 ms SLA. Static slicing prevents starvation but wastes up to 40% of link capacity when slices are idle. Unconstrained AI dynamic slicing explores aggressively, causing dangerous congestion spikes during learning.
> 
> Our system establishes a strict separation of concerns:
> 1. An **SRA-LinUCB contextual bandit** optimizes bandwidth allocation while penalizing risky exploration during network stress.
> 2. A **deterministic pre-execution guardrail** enforces 6 immutable safety gates, automatically repairing over-budget allocations before OpenFlow flow modification.
> Across 114 automated tests, our system achieves **zero SLA breaches (100% safety)** and delivers **+4.2% higher throughput** than static slicing."

---

## 2. Core Architecture in One Flow

```text
 Physical Network (Mininet 10M Bottleneck)
                     │
                     ▼ Active Ping (mnexec) & Passive sysfs stats
 Module 02: Network Telemetry Collector (TelemetryRecord)
                     │
                     ▼ Normalization & Latency Trend Velocity
 Module 03: Context Builder (6D Vector x_t in R^6)
                     │
                     ▼ SRA-LinUCB: Score_a = UCB_a - lambda * rho_a * R(x_t)
 Module 04: AI Decision Engine (Candidate Action 0, 1, or 2)
                     │
                     ▼ Gatekeeper: Capacity, URLLC Floor, Latency, Loss, Security
 Module 06: Deterministic Guardrail (APPROVED or DETERMINISTIC REPAIR)
                     │
                     ▼ Safe Allocation
 Module 07: Ryu OpenFlow 1.3 Controller (Flow Table Wire-Speed Forwarding)
                     │
                     ▼ Post-Action Network State
 Module 08: Closed-Loop Feedback Learner (Continuous Reward + Causal Attribution)
                     │
                     ▼ Parameter Updates (A_a += x x^T, b_a += r x)
 Back to Module 04 for next online decision cycle!
```

---

## 3. Top 5 Formulas to Memorize

1. **Context Vector $\mathbf{x}_t \in \mathbb{R}^6$:**
   $$\mathbf{x}_t = \left[1.0, \; \frac{\text{Lat}}{50}, \; \frac{\text{Tput}}{10}, \; \frac{\text{Queue}}{50}, \; \text{clip}\left(\frac{\Delta \text{Lat}}{10}, -1, 1\right), \; \frac{\text{Loss}}{100}\right]^T$$

2. **Context Risk Indicator $R(\mathbf{x}_t)$:**
   $$R(\mathbf{x}_t) = 0.4 x_1 + 0.3 x_3 + 0.2 \max(0, x_4) + 0.1 x_5$$

3. **SRA-LinUCB Action Score:**
   $$\text{Score}_a(\mathbf{x}_t) = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$$

4. **Multi-Objective Reward:**
   $$r_t = 1.0 \tilde{T} - 1.0 \tilde{L} - 2.0 \tilde{P} - 5.0 \cdot \text{Penalty}_{\text{SLA}} - 0.5 \tilde{S}$$

5. **Fluid Packet Queuing Delay:**
   $$t_{\text{tx}} = \frac{1500 \times 8\text{ bits}}{10 \times 10^6\text{ bps}} = \mathbf{1.20\text{ ms per packet}}$$
   $$RTT_{\text{sim}} = 10.15\text{ ms} + (Q \times 1.20\text{ ms}) + \Delta_{\text{crypto}}$$

---

## 4. Key Metrics & Thresholds Cheat Sheet

| Metric | Physical Link / Config | SLA Safety Gate Threshold |
|---|---|---|
| **Bottleneck Bandwidth** | 10.0 Mbps | $\sum \le 10.0\text{ Mbps}$ (Hard ceiling) |
| **URLLC Guaranteed Floor** | Initial: 3.0 Mbps | $\ge 3.0\text{ Mbps}$ (Zero starvation) |
| **URLLC Latency Target** | Baseline idle: 10.15 ms | $\le 15.0\text{ ms}$ (Hard SLA ceiling) |
| **URLLC Packet Loss** | Baseline idle: 0.0% | $\le 1.0\%$ (Ultra-reliability limit) |
| **Security Risk Level** | Baseline safe: 0.0 | $\le 0.70$ (Threat containment) |
| **WireGuard Crypto Delay** | Configured default: 1.2 ms | $\le 5.0\text{ ms}$ (Crypto delay ceiling) |
| **Egress Buffer Limit** | Physical switch buffer: 50 pkts | Max queuing delay: $50 \times 1.20 = 60.0\text{ ms}$ |

---

## 5. Module Summary Matrix (Modules 1–9)

| Module | Primary Code File | Key Role | Test Coverage |
|---|---|---|:---:|
| **M01: Topology** | `topology/topology.py` | 2-switch, 6-host Mininet 10M bottleneck | Live Mininet |
| **M07: Controller** | `controller/ryu_controller.py` | Ryu OpenFlow 1.3 L2 MAC-learning switch | Live `pingall` |
| **M02: Telemetry** | `telemetry/monitor.py` | Namespace ping probing + sysfs bytes + tc queue | 15 tests |
| **M03: Context** | `ai/context_builder.py` | 6D feature vector extraction + trend velocity | 17 tests |
| **M04: SRA-LinUCB** | `ai/linucb.py` | Online contextual bandit with risk suppression | 11 tests |
| **M05: Security** | `security/security_config.py` | WireGuard crypto latency modeling (1.2 ms) | 13 tests |
| **M06: Guardrail** | `guardrail/guardrail.py` | 6 immutable safety gates + allocation repair | 21 tests |
| **M08: Feedback** | `feedback/reward.py` | Multi-objective reward + causal model update | 19 tests |
| **M09: Evaluation** | `experiments/run_experiments.py` | FIFO simulation benchmark comparing 3 regimes | 7 tests |
| **Total** | **Full Project System** | **All 9 Modules Fully Integrated** | **114 / 114 Passed** |

---

## 6. Top 20 Essential Viva Defense Answers

1. **Why LinUCB over Deep RL?** Closed-form $O(d^2)$ updates, instant online learning from step 0, no black-box opacity, sub-millisecond inference delay.
2. **Why a Guardrail instead of Reward Penalties?** Reward penalties are soft post-execution signals after packets drop; the Guardrail is a pre-execution deterministic gatekeeper.
3. **Why 15 ms SLA?** Physical 5 ms propagation delay each way creates a 10 ms minimum RTT baseline; 15 ms allows 5 ms queuing before bufferbloat.
4. **How do you probe inside Mininet?** Query H1's PID and execute `mnexec -a <PID> ping -c 1 10.0.0.4`.
5. **How is throughput measured without probe overhead?** By reading Linux sysfs byte counters `/sys/class/net/s1-eth4/statistics/tx_bytes`.
6. **What is Feature $x_4$?** Discrete latency velocity: $(\text{lat}_t - \text{lat}_{t-1})/10.0$, clipped to $[-1.0, 1.0]$.
7. **What is sentinel -1.0?** A dropped probe indicator, defensively mapped to $x_1 = 1.0$ (maximum latency) and $x_5 = 1.0$ (100% loss).
8. **What are the 3 actions?** Action 0: `DECREASE_EMBB` ($\rho_0 = -1$), Action 1: `MAINTAIN` ($\rho_1 = 0$), Action 2: `INCREASE_EMBB` ($\rho_2 = +1$).
9. **Why `np.linalg.solve()` over `inv()`?** Avoids $O(d^3)$ inversion and floating-point instability via direct LU/Cholesky decomposition.
10. **How does SRA risk suppression work?** High risk subtracts $-\lambda \rho_a R(\mathbf{x}_t)$, penalizing Action 2 and boosting Action 0 during congestion.
11. **What is WireGuard crypto delay?** Configured default of 1.2 ms added delay and 32 bytes header encapsulation.
12. **What does the `is_measured` flag do?** Distinguishes live empirical kernel measurements from simulated project defaults.
13. **How does deterministic repair work?** Locks URLLC at $\ge 3.0\text{ Mbps}$, reserves BE floor ($0.5\text{ Mbps}$), and scales eMBB to fill the remaining capacity.
14. **Can repair fix external latency breaches?** No. External latency breaches cannot be solved by bandwidth repair and are safely rejected.
15. **Does the current controller enforce dynamic rates?** No, `ryu_controller.py` currently handles L2 MAC learning; dynamic rate actuation is Phase 10 work.
16. **What is Causal Safe Attribution?** Updating bandit matrices strictly for the executed arm, never penalizing rejected candidate actions.
17. **Why quadratic SLA penalty?** Creates a steep barrier function that heavily penalizes latency as it crosses the 15 ms threshold.
18. **Are Module 09 results live or simulated?** They are from a trace-driven FIFO queuing simulation model under a standardized 20-step dynamic workload.
19. **Where does $1.20\text{ ms/packet}$ come from?** 1500-byte MTU $= 12,000\text{ bits}$. On a 10 Mbps bottleneck, $12,000 / 10^7 = 1.20\text{ ms}$.
20. **What is the p99 latency finding?** In Unsafe AI, p99 latency was **26.35 ms (SLA breach)** despite an average of 11.15 ms. In our Proposed System, p99 was **12.51 ms (strictly safe)**.

---

## 7. Top 5 Golden Rules for Review 2

1. **Be Honest About Implementation vs. Simulation:** Modules 1–8 are fully implemented and verified across 114 unit/integration tests; Module 09 evaluation is a trace-driven queuing simulation.
2. **Never Claim AI Directly Changes Switch Bandwidth in Live Mininet:** Explain that the controller handles L2 forwarding today, and pushing guardrail rates to OpenFlow meters is Phase 10.
3. **Know the 10 ms Baseline:** $5\text{ ms forward} + 5\text{ ms reverse} = 10\text{ ms RTT}$. Therefore, a 15 ms SLA is physically justified.
4. **Emphasize the Separation of Concerns:** Optimization is AI (SRA-LinUCB); Safety is Deterministic (Module 06 Guardrail).
5. **Stand Behind Your 114 Tests:** Every formula, matrix update, and safety gate is mathematically proven by 114 passing tests.
