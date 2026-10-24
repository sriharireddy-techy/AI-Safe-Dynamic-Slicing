# Formulas, Metrics, and Guardrails Reference Manual
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## Table of Contents
1. [Master Consolidated Formula Sheet](#1-master-consolidated-formula-sheet)
2. [Metrics and Thresholds Master Table](#2-metrics-and-thresholds-master-table)
3. [The Six Immutable Guardrail Gates](#3-the-six-immutable-guardrail-gates)
4. [Deterministic Allocation Repair Mathematics](#4-deterministic-allocation-repair-mathematics)
5. [Fluid Queuing Simulation Model Physics](#5-fluid-queuing-simulation-model-physics)

---

## 1. Master Consolidated Formula Sheet

---

### Formula 1: Throughput Derivation from Byte Counters
- **Exact Expression:**
  $$\text{Throughput (Mbps)} = \frac{\Delta \text{TX Bytes} \times 8.0}{\Delta t \times 1,000,000.0}$$
- **Symbol & Unit Definitions:**
  - $\Delta \text{TX Bytes} = \text{TX}_{\text{curr}} - \text{TX}_{\text{prev}}$: Number of bytes transmitted by the interface during the sampling interval (bytes).
  - $8.0$: Bit-to-byte conversion factor ($\text{bits/byte}$).
  - $\Delta t = t_{\text{curr}} - t_{\text{prev}}$: Elapsed time between consecutive samples (seconds).
  - $1,000,000.0$: Bits per Megabit ($10^6 \text{ bits/Mb}$, standard decimal networking convention).
- **Why Needed:** Computes egress transmission rate without injecting probe packets into the network.
- **Worked Example:**
  - $\Delta \text{TX Bytes} = 625,000\text{ bytes}$, $\Delta t = 0.5\text{ s}$.
  - $\text{Throughput} = \frac{625,000 \times 8}{0.5 \times 1,000,000} = \frac{5,000,000}{500,000} = \mathbf{10.0\text{ Mbps}}$.
- **Code Reference:** [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py#L148) in `calculate_rates()`.
- **Assumptions & Limitations:** Assumes monotonic counter growth. If an interface resets or wraps ($\text{curr} < \text{prev}$), the code safely clamps delta to 0 to prevent negative throughput.

---

### Formula 2: Total Bidirectional Traffic Rate
- **Exact Expression:**
  $$\text{Traffic Rate (Mbps)} = \frac{(\Delta \text{TX Bytes} + \Delta \text{RX Bytes}) \times 8.0}{\Delta t \times 1,000,000.0}$$
- **Symbol & Unit Definitions:**
  - $\Delta \text{RX Bytes} = \text{RX}_{\text{curr}} - \text{RX}_{\text{prev}}$: Bytes received on the interface.
- **Why Needed:** Captures aggregate link utilization in full-duplex topologies.
- **Code Reference:** [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py#L148) in `calculate_rates()`.

---

### Formula 3: Temporal Latency Trend Velocity
- **Exact Expression:**
  $$x_4 = \text{clip}\left(\frac{\text{Latency}_t - \text{Latency}_{t-1}}{10.0}, \; -1.0, \; 1.0\right)$$
- **Symbol & Unit Definitions:**
  - $\text{Latency}_t$: Current measured round-trip time (ms).
  - $\text{Latency}_{t-1}$: Previous measured round-trip time (ms).
  - $10.0$: Scaling normalization window (ms).
  - $\text{clip}(v, -1.0, 1.0)$: Clamps values strictly between $-1.0$ and $+1.0$.
- **Why Needed:** Provides the AI with a discrete first derivative indicating whether congestion is building up ($x_4 > 0$), clearing ($x_4 < 0$), or steady ($x_4 = 0$).
- **Worked Example:**
  - $\text{Latency}_t = 22.0\text{ ms}$, $\text{Latency}_{t-1} = 12.0\text{ ms}$.
  - $x_4 = \text{clip}((22.0 - 12.0) / 10.0, -1, 1) = \text{clip}(1.0, -1, 1) = \mathbf{+1.0}$ (Rapid congestion spike).
- **Code Reference:** [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py#L172).

---

### Formula 4: 6-Dimensional Context Vector Formulation
- **Exact Expression:**
  $$\mathbf{x}_t = \begin{bmatrix}
  x_0 \\
  x_1 \\
  x_2 \\
  x_3 \\
  x_4 \\
  x_5
  \end{bmatrix} = \begin{bmatrix}
  1.0 \\
  \min(1.0, \; \text{Latency}_{\text{ms}} / 50.0) \\
  \min(1.0, \; \text{Throughput}_{\text{Mbps}} / 10.0) \\
  \min(1.0, \; \text{Queue}_{\text{pkts}} / 50.0) \\
  \text{clip}((\text{Latency}_t - \text{Latency}_{t-1})/10.0, \; -1.0, \; 1.0) \\
  \text{Loss}_{\%} / 100.0
  \end{bmatrix}$$
- **Why Needed:** Eliminates scale disparity across milliseconds, Mbps, packets, and percentages so linear ridge regression weights remain numerically stable.
- **Sentinel Rule:** If latency is $-1.0$ (dropped probe), $x_1$ and $x_5$ are mapped to $1.0$ (worst-case state).
- **Code Reference:** [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py#L178) in `build_context()`.

---

### Formula 5: SRA Context Risk Indicator
- **Exact Expression:**
  $$R(\mathbf{x}_t) = w_1 x_1 + w_3 x_3 + w_4 \max(0, x_4) + w_5 x_5$$
- **Symbol & Unit Definitions:**
  - $\mathbf{w} = [0.4, 0.3, 0.2, 0.1]$: Configured risk indicator weights.
  - $\max(0, x_4)$: Half-wave rectifier ensuring only positive (worsening) latency trend adds risk.
  - Output bounded in $[0.0, 1.0]$.
- **Worked Example:**
  - Let $x_1 = 0.50$, $x_3 = 0.40$, $x_4 = 0.80$, $x_5 = 0.0$.
  - $R(\mathbf{x}_t) = 0.4(0.50) + 0.3(0.40) + 0.2(0.80) + 0.1(0.0) = 0.20 + 0.12 + 0.16 = \mathbf{0.48}$.
- **Code Reference:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L162) in `compute_context_risk()`.

---

### Formula 6: SRA-LinUCB Candidate Action Selection Rule
- **Exact Expression:**
  $$\text{Score}_a(\mathbf{x}_t) = \underbrace{\mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a}_{\text{Exploitation Mean}} + \underbrace{\alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}}_{\text{Exploration Uncertainty}} - \underbrace{\lambda \rho_a R(\mathbf{x}_t)}_{\text{SRA Risk Penalty}}$$
  $$a^* = \arg\max_{a \in \{0, 1, 2\}} \text{Score}_a(\mathbf{x}_t)$$
- **Symbol & Unit Definitions:**
  - $\hat{\boldsymbol{\theta}}_a \in \mathbb{R}^6$: Estimated regression parameters computed by solving $\mathbf{A}_a \hat{\boldsymbol{\theta}}_a = \mathbf{b}_a$.
  - $\mathbf{A}_a \in \mathbb{R}^{6 \times 6}$: Precision covariance matrix ($\mathbf{A}_a = \mathbf{I}_6 + \sum \mathbf{x}_\tau \mathbf{x}_\tau^T$).
  - $\alpha$: Exploration coefficient ($\alpha = 1.0$).
  - $\lambda$: Risk-aversion coefficient ($\lambda = 0.5$).
  - $\rho_a$: Physical risk profile ($\rho_0 = -1.0, \rho_1 = 0.0, \rho_2 = +1.0$).
  - $R(\mathbf{x}_t)$: Context risk indicator.
- **Code Reference:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L209) in `select_action()`.

---

### Formula 7: Online Ridge Regression Recursive Update
- **Exact Expression:**
  $$\mathbf{A}_{a_t} \leftarrow \mathbf{A}_{a_t} + \mathbf{x}_t \mathbf{x}_t^T$$
  $$\mathbf{b}_{a_t} \leftarrow \mathbf{b}_{a_t} + r_t \mathbf{x}_t$$
- **Symbol & Unit Definitions:**
  - $a_t$: Executed action arm ($0, 1, \text{ or } 2$).
  - $r_t$: Scalar feedback reward.
  - $\mathbf{x}_t \mathbf{x}_t^T$: Outer product matrix ($6 \times 6$).
- **Computational Complexity:** Updating requires $O(d^2)$ operations ($6 \times 6 = 36$ multiplications), enabling sub-millisecond execution.
- **Code Reference:** [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py#L262) in `update()`.

---

### Formula 8: Continuous Multi-Objective Reward Function
- **Exact Expression:**
  $$r_t = w_{\text{tput}} \cdot \tilde{T}_t - w_{\text{lat}} \cdot \tilde{L}_t - w_{\text{loss}} \cdot \tilde{P}_t - w_{\text{sla}} \cdot \text{Penalty}_{\text{SLA}}(t) - w_{\text{sec}} \cdot \tilde{S}_t$$
- **Component Definitions:**
  - $\tilde{T}_t = \min\left(1.0, \frac{\text{Throughput}}{10.0}\right)$ (Normalized throughput $[0.0, 1.0]$).
  - $\tilde{L}_t = \max\left(0.0, \min\left(1.0, \frac{\text{Latency} - 10.0}{15.0 - 10.0}\right)\right)$ (Normalized queuing delay within operational span $[10.0, 15.0\text{ ms}]$).
  - $\tilde{P}_t = \min\left(1.0, \frac{\text{Loss \%}}{1.0}\right)$ (Normalized loss relative to 1.0% limit).
  - $\text{Penalty}_{\text{SLA}}(t)$:
    $$\text{Penalty}_{\text{SLA}}(t) = \begin{cases}
    0.0 & \text{if Latency} \le 15.0\text{ ms and Loss} \le 1.0\% \\
    \min\left(5.0, \left(\frac{\text{Latency} - 15.0}{15.0}\right)^2\right) & \text{if Latency} > 15.0\text{ ms} \\
    5.0 & \text{if Latency} = -1.0\text{ (dropped probe)}
    \end{cases}$$
  - $\tilde{S}_t = \min\left(1.0, \frac{\Delta_{\text{crypto}}}{5.0}\right)$ strictly when `is_measured == True`, else $0.0$.
  - Configured Weights: $w_{\text{tput}} = 1.0, w_{\text{lat}} = 1.0, w_{\text{loss}} = 2.0, w_{\text{sla}} = 5.0, w_{\text{sec}} = 0.5$.
- **Code Reference:** [`feedback/reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/reward.py#L151) in `compute_reward()`.

---

### Formula 9: Fluid FIFO Queuing Model Delay & Latency
- **Exact Expression:**
  $$\Delta Q = \frac{(\text{Admitted Traffic} - C) \times 10^6 \times \Delta t}{P_{\text{MTU}} \times 8}$$
  $$Q(t) = \min\left(Q_{\text{max}}, \; \max(0, \; Q(t-1) + \Delta Q)\right)$$
  $$RTT_{\text{sim}}(t) = RTT_{\text{base}} + \left(Q(t) \times \frac{P_{\text{MTU}} \times 8}{C \times 10^6} \times 1000\right) + \Delta_{\text{crypto}}$$
- **Parameter Constants:**
  - Bottleneck Capacity: $C = 10.0\text{ Mbps}$.
  - MTU Packet Size: $P_{\text{MTU}} = 1500\text{ bytes} = 12,000\text{ bits}$.
  - Packet Transmission Delay: $t_{\text{tx}} = \frac{12,000}{10.0 \times 10^6} = 0.0012\text{ s} = \mathbf{1.20\text{ ms/packet}}$.
  - Minimum Base Latency: $RTT_{\text{base}} = 10.15\text{ ms}$.
  - Buffer Limit: $Q_{\text{max}} = 50\text{ packets}$ ($60\text{ ms}$ max queuing delay).
- **Code Reference:** [`experiments/dynamic_baseline.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/dynamic_baseline.py#L80) and [`experiments/proposed_system.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/proposed_system.py#L90).

---

## 2. Metrics and Thresholds Master Table

| Metric | Meaning | Unit | Collection Method | Used By Module | Desired Direction | Project Threshold | Nature |
|---|---|:---:|---|---|:---:|:---:|:---:|
| **URLLC Latency (RTT)** | Round-trip time between H1 and H4 | ms | Active ICMP Ping via `mnexec` | M2, M3, M6, M8, M9 | Lower ($\downarrow$) | $\le 15.0\text{ ms}$ | Live / Measured |
| **Packet Loss** | Dropped packet ratio on URLLC | % | ICMP ping stdout parsing | M2, M3, M6, M8, M9 | Lower ($\downarrow$) | $\le 1.0\%$ | Live / Measured |
| **Bottleneck Throughput** | Egress bandwidth utilization | Mbps | Linux sysfs (`/sys/class/net/.../statistics`) | M2, M3, M8, M9 | Higher ($\uparrow$) | $\le 10.0\text{ Mbps}$ | Live / Derived |
| **Total Traffic Rate** | Bidirectional link utilization (RX+TX) | Mbps | Linux sysfs interface counters | M2 | Contextual | N/A | Live / Derived |
| **Queue Backlog** | Packets waiting in switch buffer | packets | Linux `tc -s qdisc show dev s1-eth4` | M2, M3, M9 | Lower ($\downarrow$) | $\le 50\text{ pkts}$ | Live / Parsed |
| **URLLC Allocation** | Bandwidth reserved for URLLC slice | Mbps | Guardrail / Slice config | M6, M9 | Higher ($\uparrow$) | $\ge 3.0\text{ Mbps}$ | Configured Guarantee |
| **Total Bandwidth** | Sum of all slice allocations | Mbps | Guardrail validation check | M6, M9 | Within budget | $\le 10.0\text{ Mbps}$ | Physical Constraint |
| **Security Risk Level** | Threat severity score | $[0.0, 1.0]$ | `SecurityState` dataclass | M5, M6 | Lower ($\downarrow$) | $\le 0.70$ | Configured / State |
| **Crypto Overhead** | Latency added by encryption tunnel | ms | `WireGuardAdapter` / `SecurityState` | M5, M6, M8 | Lower ($\downarrow$) | $\le 5.0\text{ ms}$ | Configured (1.2 ms default) |
| **Scalar Reward $r_t$** | Reinforcement feedback score | dimensionless | Continuous formula in `RewardEngine` | M8 | Higher ($\uparrow$) | $> 0$ (Healthy) | Derived |
| **SLA Violations** | Operational periods breaching SLA | count / % | Binary threshold check ($> 15\text{ms}$ or $> 1\%$) | M6, M9 | Zero ($0\%$) | $0\text{ violations}$ | Evaluated / Invariant |

---

## 3. The Six Immutable Guardrail Gates

Verified directly from [`guardrail/guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py#L317-L373):

```text
 Candidate Action (from AI)
             │
             ▼
   [Gate 1: Total Capacity] ────────► Violates if sum(Bandwidth) > 10.0 Mbps
             │ Pass
             ▼
   [Gate 2: URLLC Reservation] ─────► Violates if Bandwidth(URLLC) < 3.0 Mbps
             │ Pass
             ▼
   [Gate 3: URLLC Latency SLA] ─────► Violates if Effective Latency > 15.0 ms
             │ Pass
             ▼
   [Gate 4: Packet Loss SLA] ───────► Violates if Packet Loss > 1.0 %
             │ Pass
             ▼
   [Gate 5: Security Threat Gate] ──► Violates if Security Risk > 0.70
             │ Pass
             ▼
   [Gate 6: Crypto Overhead Delay] ─► Violates if Crypto Delay > 5.0 ms
             │
             ▼
      Action APPROVED
```

### Effective Latency Calculation (Preventing Double Counting)
```python
effective_latency, added_overhead, includes_sec = self.resolve_effective_latency(
    current_context, sec_state
)
```
- If `latency_includes_security == False` and `security_state.is_enabled == True`:
  $$\text{Effective Latency} = \text{Raw Latency} + \Delta_{\text{crypto}}$$
- If `latency_includes_security == True`:
  $$\text{Effective Latency} = \text{Raw Latency} \quad (\text{overhead is already present in measurement})$$

---

## 4. Deterministic Allocation Repair Mathematics

When candidate allocations violate **Gate 1 (Capacity)** but satisfy environmental gates (Latency $\le 15\text{ ms}$, Loss $\le 1\%$, Risk $\le 0.70$), the Guardrail triggers deterministic proportional repair (`_attempt_deterministic_repair()`):

1. **Lock URLLC Allocation:**
   $$B_{\text{URLLC}}^{\text{repaired}} = \max(B_{\text{URLLC}}^{\text{candidate}}, \; 3.0\text{ Mbps})$$
2. **Calculate Remaining Capacity:**
   $$C_{\text{rem}} = 10.0\text{ Mbps} - B_{\text{URLLC}}^{\text{repaired}}$$
3. **Scale eMBB Allocation:**
   $$B_{\text{eMBB}}^{\text{repaired}} = \min\left(\max(B_{\text{eMBB}}^{\text{candidate}}, \; 1.0\text{ Mbps}), \; C_{\text{rem}} - 0.5\text{ Mbps}\right)$$
4. **Allocate Remaining Capacity to Best Effort:**
   $$B_{\text{BE}}^{\text{repaired}} = \max(0.5\text{ Mbps}, \; C_{\text{rem}} - B_{\text{eMBB}}^{\text{repaired}})$$

### Verified Test Case:
- Candidate: `{URLLC: 4.0, eMBB: 7.0, BE: 2.0}` (Total: $13.0\text{ Mbps} > 10.0\text{ Mbps}$)
- Repaired:
  - $B_{\text{URLLC}} = \max(4.0, 3.0) = \mathbf{4.0\text{ Mbps}}$.
  - $C_{\text{rem}} = 10.0 - 4.0 = 6.0\text{ Mbps}$.
  - $B_{\text{eMBB}} = \min(7.0, 6.0 - 0.5) = \mathbf{5.5\text{ Mbps}}$.
  - $B_{\text{BE}} = 6.0 - 5.5 = \mathbf{0.5\text{ Mbps}}$.
  - Total: $4.0 + 5.5 + 0.5 = \mathbf{10.0\text{ Mbps}}$. (Satisfies capacity and minimum floors).

---

## 5. Fluid Queuing Simulation Model Physics

In Module 09, queuing delay is not modeled with random noise. It is modeled using fluid packet flow physics:

1. **Packet Size:** Standard Ethernet MTU $= 1500\text{ bytes} = 12,000\text{ bits}$.
2. **Bottleneck Rate:** $C = 10.0\text{ Mbps} = 10,000,000\text{ bits/s}$.
3. **Packet Transmission Time ($t_{\text{tx}}$):**
   $$t_{\text{tx}} = \frac{12,000\text{ bits}}{10,000,000\text{ bits/s}} = 0.0012\text{ seconds} = \mathbf{1.20\text{ ms per packet}}$$
4. **Buffer Accumulation:**
   If incoming traffic rate exceeds 10.0 Mbps by $\Delta B\text{ Mbps}$, packets accumulate at:
   $$\text{Rate of queue buildup} = \frac{\Delta B \times 10^6}{12,000}\text{ packets per second}$$
5. **Physical Buffer Limit:**
   The egress buffer holds a maximum of $50\text{ packets}$.
   $$\text{Maximum Queuing Delay} = 50\text{ packets} \times 1.20\text{ ms} = \mathbf{60.0\text{ ms}}$$
   Any packets arriving when $Q = 50$ are tail-dropped, causing packet loss.
6. **Total Simulated RTT:**
   $$RTT_{\text{sim}} = 10.15\text{ ms (base)} + (Q \times 1.20\text{ ms}) + \Delta_{\text{crypto}}$$
