# Comprehensive Faculty Viva Question Bank (60 Questions & Answers)
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## Category 1: Problem Statement & Motivation

#### Q1: What is the primary problem your project solves?
**Answer:** In shared SDN networks, bursty high-bandwidth video traffic (eMBB) causes switch bufferbloat that starves latency-critical traffic (URLLC), spiking latency from 10 ms to over 30–120 ms and violating the 15 ms SLA. Static partitioning prevents starvation but wastes up to 40% of link capacity when slices are idle. We solve this by introducing an AI dynamic slicer constrained by a deterministic safety guardrail that mathematically guarantees zero SLA breaches while reclaiming spare bandwidth.

#### Q2: Why is using Reinforcement Learning alone dangerous for network slicing?
**Answer:** Machine learning agents learn through stochastic exploration (trial-and-error). During exploration, the AI tests aggressive bandwidth allocations to eMBB, causing queue accumulation and bufferbloat in the physical switches. In safety-critical applications like autonomous driving, exploration mistakes cause physical packet drops and latency spikes that cannot be reversed by a negative reward.

#### Q3: Why did you set the URLLC SLA threshold at 15.0 ms instead of 1.0 ms?
**Answer:** In our Mininet topology, the physical link between switches `S1` and `S2` has a configured propagation delay of 5.0 ms each way. Thus, the theoretical minimum round-trip time alone is $10.0\text{ ms}$ ($5\text{ ms} \times 2$). A 1.0 ms SLA is physically impossible on this topology. The 15.0 ms threshold allows up to 5.0 ms of queuing buffer before the network enters an unrecoverable bufferbloat state.

#### Q4: How do you prove that unregulated eMBB traffic actually causes URLLC starvation?
**Answer:** Through our empirical baseline experiment in Mininet: with URLLC alone, average latency was 10.15 ms with 0% loss. When we injected an unregulated 9.0 Mbps eMBB iperf3 burst across the 10 Mbps bottleneck, URLLC latency surged to an average of 29.88 ms and peaked at 122.44 ms, heavily breaching the 15.0 ms SLA.

#### Q5: What is the core architectural philosophy of your project?
**Answer:** *"Let AI optimize the network, but never let AI optimize at the cost of a critical SLA."* We enforce this by decoupling optimization (AI contextual bandit) from safety (pre-execution deterministic guardrail).

---

## Category 2: Network Slicing & SDN Fundamentals

#### Q6: What is the fundamental difference between SDN and traditional networking?
**Answer:** Traditional networking bundles the control plane (routing/forwarding intelligence) and data plane (forwarding hardware) inside proprietary routers. SDN decouples them: dumb forwarding switches (Data Plane) forward packets at wire speed, while a centralized software program (Control Plane, such as Ryu) installs flow rules dynamically via OpenFlow.

#### Q7: What are the three 5G slice types supported by your architecture?
**Answer:**
1. **URLLC (Ultra-Reliable Low-Latency Communication):** Host pair H1 $\leftrightarrow$ H4, SLA: $\le 15.0\text{ ms}$ latency, $\le 1.0\%$ loss, $\ge 3.0\text{ Mbps}$ guaranteed floor.
2. **eMBB (Enhanced Mobile Broadband):** Host pair H2 $\leftrightarrow$ H5, elastic bulk video/transfer traffic.
3. **Best Effort (BE):** Host pair H3 $\leftrightarrow$ H6, background traffic utilizing spare link budget.

#### Q8: Does your current Mininet topology implement physical queuing per slice?
**Answer:** In the current `topology.py`, slices are logical host pairs mapped to IP endpoints (`10.0.0.1`–`10.0.0.6`) sharing the default physical queue on interface `s1-eth4`. Creating separate physical Linux HTB classes (`tc class add`) or OpenFlow meter bands (`OFPMeterMod`) is planned for Phase 10 actuation.

#### Q9: What is OpenFlow 1.3 and why did you choose it over OpenFlow 1.0?
**Answer:** OpenFlow 1.3 introduced multipart statistics, per-flow meter bands for rate-limiting, and multiple flow tables. OpenFlow 1.0 only supported simple single-table forwarding without native metering.

#### Q10: What is the difference between an OpenFlow flow entry and a Linux Traffic Control (tc) qdisc?
**Answer:** OpenFlow flow entries determine packet routing and matching in switch hardware/OVS flow tables. Linux `tc` qdiscs manage egress buffer queuing, packet scheduling (FIFO, HTB), rate limiting, and artificial link delays at the Linux kernel network interface level.

---

## Category 3: Architecture & Topology

#### Q11: Walk through your project's physical topology.
**Answer:** Two Open vSwitch bridges (`s1` and `s2`) connected over a bottleneck link. Hosts `h1`, `h2`, `h3` connect to `s1`; hosts `h4`, `h5`, `h6` connect to `s2`. The bottleneck link is configured via `TCLink` with 10.0 Mbps bandwidth, 5.0 ms propagation delay each way, and a 50-packet egress buffer.

#### Q12: Why are host-to-switch links unconstrained while the switch-to-switch link is constrained?
**Answer:** Host-to-switch links emulate high-speed local access links (1 Gbps virtual Ethernet). The switch-to-switch link emulates the shared wide-area or backhaul aggregation bottleneck where multi-tenant contention and bufferbloat physically occur.

#### Q13: In `topology.py`, does the 5 ms delay apply in one direction or both?
**Answer:** Mininet's `TCLink` applies Linux netem delay to both egress interfaces (`s1-eth4` and `s2-eth4`). Therefore, a packet experiences 5 ms forward delay and 5 ms return delay, resulting in a theoretical minimum round-trip time of 10.0 ms.

#### Q14: What is the role of Open vSwitch (OVS) in your setup?
**Answer:** OVS is a production-grade virtual switch that executes in the Linux kernel. It maintains flow tables, performs OpenFlow 1.3 packet matching, and handles packet encapsulation and hardware rate metering.

#### Q15: How does your architecture handle switch failure or controller disconnection?
**Answer:** In OpenFlow, switches can enter "fail-standalone" or "fail-secure" mode. In our production design, switches fall back to safe static partitioning (URLLC 3 Mbps, eMBB 5 Mbps, BE 2 Mbps) if controller connectivity is lost.

---

## Category 4: Telemetry & Metrics

#### Q16: How does `telemetry/monitor.py` solve the Mininet network namespace isolation problem?
**Answer:** Mininet isolates host interfaces inside private Linux network namespaces. A standard ping from the root OS namespace cannot route to `10.0.0.4`. Our telemetry collector dynamically queries host H1's operating system process ID (`ps -eo pid=,args= | grep mininet:h1`) and runs `mnexec -a <PID> ping -c 1 10.0.0.4` directly inside H1's isolated network stack.

#### Q17: How is throughput calculated without injecting overhead probes into the bottleneck?
**Answer:** By reading raw cumulative transmitted bytes directly from the Linux kernel sysfs filesystem (`/sys/class/net/s1-eth4/statistics/tx_bytes`) at consecutive timestamps:
$$\text{Throughput} = \frac{(\text{TX}_{\text{curr}} - \text{TX}_{\text{prev}}) \times 8}{\Delta t \times 10^6}$$

#### Q18: What is a defensive sentinel value and why does your telemetry use it?
**Answer:** If an active ping probe is completely dropped due to extreme congestion, returning `None` or raising an exception would crash the AI control loop. The collector returns sentinel values: `-1.0 ms` latency and `100.0%` loss. Module 03 sanitizes `-1.0 ms` into `1.0` (maximum normalized penalty).

#### Q19: How do you monitor switch queue backlog?
**Answer:** By executing `tc -s qdisc show dev s1-eth4` and regex-parsing the `backlog <bytes>b <packets>p` string to extract the exact integer packet count backlogged in the buffer.

#### Q20: What is the sampling interval of your telemetry collector?
**Answer:** In simulation benchmarks, telemetry is sampled at discrete 1.0-second steps. In live Mininet monitoring, it polls continuously with a 1.0-second sleeping interval between active probes.

---

## Category 5: Context Construction

#### Q21: What are the 6 features in your context vector $\mathbf{x}_t$, in exact order?
**Answer:**
- $x_0 = 1.0$: Bias / baseline intercept.
- $x_1 = \min(1.0, \text{Latency} / 50.0)$: Normalized URLLC latency.
- $x_2 = \min(1.0, \text{Throughput} / 10.0)$: Normalized bottleneck utilization.
- $x_3 = \min(1.0, \text{Queue} / 50.0)$: Normalized queue occupancy.
- $x_4 = \text{clip}((\text{Latency}_t - \text{Latency}_{t-1})/10.0, -1.0, 1.0)$: Temporal latency velocity.
- $x_5 = \text{Loss} / 100.0$: Normalized packet loss ratio.

#### Q22: Why is feature normalization required for LinUCB?
**Answer:** Raw telemetry features have vast scale differences: latency is $10\text{--}100\text{ ms}$, throughput is $0\text{--}10\text{ Mbps}$, queue is $0\text{--}50\text{ pkts}$, and loss is $0\text{--}100\%$. Unnormalized features with large magnitudes would numerically dominate ridge regression, causing floating-point instability. Normalization to $[0.0, 1.0]$ ensures balanced learning.

#### Q23: Why is temporal velocity ($x_4$) calculated and clipped to $[-1.0, 1.0]$?
**Answer:** Standard static features only capture instantaneous state. Temporal velocity calculates the discrete derivative of latency. A positive value ($x_4 > 0$) warns the AI that congestion is accelerating before packet loss occurs, while a negative value ($x_4 < 0$) indicates network recovery.

#### Q24: What happens if raw latency is negative (sentinel -1.0)?
**Answer:** If raw latency is negative, `ContextBuilder` overrides the values: $x_1$ is set to $1.0$ (worst-case latency) and $x_5$ is set to $1.0$ (100% loss). This prevents linear regression from interpreting a dropped probe as super-fast zero-latency.

#### Q25: Why must feature order remain strictly identical between training and inference?
**Answer:** Ridge regression associates weight parameter $\theta_{a,i}$ with feature position $i$. If the order of features changes, the learned weights would multiply the wrong network metrics, completely corrupting the AI's decisions.

---

## Category 6: SRA-LinUCB Mathematics

#### Q26: What does SRA-LinUCB stand for?
**Answer:** Security- and Risk-Aware Linear Upper Confidence Bound.

#### Q27: What is the discrete action space of your bandit?
**Answer:**
- Action `0`: `DECREASE_EMBB` ($\rho_0 = -1.0$, de-congesting/safe).
- Action `1`: `MAINTAIN` ($\rho_1 = 0.0$, neutral).
- Action `2`: `INCREASE_EMBB` ($\rho_2 = +1.0$, aggressive/congestion risk).

#### Q28: State the complete SRA-LinUCB action selection formula.
**Answer:**
$$\text{Score}_a(\mathbf{x}_t) = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$$
$$a^* = \arg\max_a \text{Score}_a(\mathbf{x}_t)$$

#### Q29: Define every term in the action selection formula.
**Answer:**
- $\mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a$: Estimated expected reward (exploitation).
- $\alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}$: Upper confidence bound uncertainty bonus (exploration).
- $\lambda \rho_a R(\mathbf{x}_t)$: SRA risk penalty. $\lambda = 0.5$ is risk aversion, $\rho_a$ is action risk profile, and $R(\mathbf{x}_t)$ is context risk indicator.

#### Q30: Why did you use `np.linalg.solve(A_a, b_a)` instead of `np.linalg.inv(A_a)`?
**Answer:** Explicit matrix inversion requires $O(d^3)$ operations and introduces floating-point precision loss. `np.linalg.solve` solves the linear system $\mathbf{A}_a \hat{\boldsymbol{\theta}}_a = \mathbf{b}_a$ via direct LU or Cholesky decomposition, ensuring numerical stability and executing faster.

---

## Category 7: Security Model

#### Q31: Why must network slicing consider cryptographic security?
**Answer:** Mission-critical slices carry sensitive industrial or medical data requiring end-to-end encryption (e.g., WireGuard tunnels). Encryption adds 32-byte transport header overhead and $\approx 1.2\text{ ms}$ cryptographic processing delay. Ignoring this overhead can push URLLC latency past the 15.0 ms SLA threshold.

#### Q32: What is the `SecurityState` dataclass?
**Answer:** A dataclass in `security/security_config.py` tracking:
- `mode`: Security operational mode (`OFF` or `ON`).
- `risk_level`: Normalized threat score $[0.0, 1.0]$.
- `latency_overhead_ms`: Added delay (default 1.2 ms).
- `throughput_penalty_mbps`: Throughput degradation (default 0.5 Mbps).
- `is_measured`: Boolean flag indicating whether values are live measurements or simulation defaults.

#### Q33: How does `WireGuardAdapter` handle non-Linux systems?
**Answer:** It uses `shutil.which("wg")` to check if WireGuard CLI tools exist. If uninstalled or running on Windows without root access, it returns a safe fallback dictionary (`available: False`) without throwing unhandled exceptions.

#### Q34: What is the configured WireGuard packet header overhead?
**Answer:** 32 bytes: 20 bytes IPv4 header + 8 bytes UDP header + 4 bytes WireGuard data transport header.

#### Q35: Does Module 05 include an Intrusion Detection System (IDS)?
**Answer:** No. It is an overhead profiler and security state model. It quantifies the performance costs of encryption and models threat levels; it does not inspect packet payloads for malware.

---

## Category 8: SLA Guardrail & Repair

#### Q36: List all 6 gates enforced by Module 06 Guardrail.
**Answer:**
1. Total Bandwidth Capacity Gate: $\sum \text{Bandwidth} \le 10.0\text{ Mbps}$.
2. URLLC Minimum Bandwidth Gate: $\text{Bandwidth}_{\text{URLLC}} \ge 3.0\text{ Mbps}$.
3. URLLC Latency SLA Gate: Measured effective latency $\le 15.0\text{ ms}$.
4. Packet Loss Gate: Packet loss ratio $\le 1.0\%$.
5. Security Threat Gate: Security risk score $\le 0.70$.
6. Crypto Overhead Gate: Cryptographic delay $\le 5.0\text{ ms}$.

#### Q37: How does deterministic repair work when capacity is exceeded?
**Answer:** The guardrail locks URLLC at its guaranteed reservation ($\ge 3.0\text{ Mbps}$), reserves the Best-Effort floor ($0.5\text{ Mbps}$), and dynamically scales eMBB to fill the exact remaining link budget ($10.0 - B_{\text{URLLC}} - 0.5$), ensuring total allocation never exceeds 10.0 Mbps.

#### Q38: Why can't deterministic repair fix an external latency breach?
**Answer:** Bandwidth repair can only adjust switch rate limiters. If external network latency exceeds 15.0 ms (due to propagation delay or external line degradation), mathematically modifying allocations cannot reduce external physical delay. The action is safely rejected.

#### Q39: How does the guardrail prevent double-counting of security overhead?
**Answer:** It inspects the `latency_includes_security` flag in the context dictionary. If True, the observed latency already includes crypto delay. If False, the guardrail explicitly adds `security_state.latency_overhead_ms` before comparing against the 15.0 ms ceiling.

#### Q40: What happens if an invalid action string or negative bandwidth is passed to the guardrail?
**Answer:** The guardrail rejects the candidate action immediately, returns `approved: False`, and records violation `INVALID_ACTION`.

---

## Category 9: Controller & Enforcement

#### Q41: What role does Ryu play in this project?
**Answer:** Ryu is the central SDN controller listening on TCP port 6633. It establishes OpenFlow 1.3 handshakes with switches `s1` and `s2` and installs hardware flow rules.

#### Q42: Does your current Ryu controller dynamically modify switch queue rates?
**Answer:** No. In the current repository, `controller/ryu_controller.py` implements an L2 MAC-learning switch for wire-speed forwarding. Pushing guardrail decisions to OpenFlow meter bands (`OFPMeterMod`) is planned for Phase 10.

#### Q43: How does an OpenFlow meter band enforce bandwidth limits?
**Answer:** An `OFPMeterMod` message configures a meter table entry with a specific rate in kbps and burst size. Flow table entries point to this meter ID. When traffic exceeds the meter rate, excess packets are dropped or remarked.

#### Q44: What is the alternative to OpenFlow meter bands for rate enforcement?
**Answer:** Linux Hierarchical Token Bucket (HTB) queues managed via `tc` and `ovs-vsctl set port s1-eth4 qos=@newqos`. Packets are assigned to queues using the `set_queue` OpenFlow action.

#### Q45: How did you verify controller connectivity in your tests?
**Answer:** By launching Ryu, starting Mininet, and executing `pingall`, verifying that all 6 hosts learn MAC routes and achieve 0% packet loss.

---

## Category 10: Reward & Feedback

#### Q46: State the continuous reward formulation in Module 08.
**Answer:**
$$r_t = 1.0 \tilde{T}_t - 1.0 \tilde{L}_t - 2.0 \tilde{P}_t - 5.0 \cdot \text{Penalty}_{\text{SLA}}(t) - 0.5 \tilde{S}_t$$
Rewarding throughput ($\tilde{T}$), penalizing queuing latency ($\tilde{L}$), packet loss ($\tilde{P}$), SLA violation barrier ($\text{Penalty}_{\text{SLA}}$), and crypto overhead ($\tilde{S}$).

#### Q47: What is Causal Safe Attribution and why is it essential?
**Answer:** When the guardrail rejects an unsafe action, that action was never executed on the switches. If the AI model updated its parameters using post-rejection telemetry, it would receive false negative feedback for an action it did not take. Causal Safe Attribution ensures model statistics are updated strictly for executed actions.

#### Q48: How is the quadratic SLA penalty calculated?
**Answer:** If latency $\le 15.0\text{ ms}$, penalty is $0.0$. If latency $> 15.0\text{ ms}$, penalty grows quadratically:
$$\text{Penalty}_{\text{SLA}} = \min\left(5.0, \; \left(\frac{\text{Latency} - 15.0}{15.0}\right)^2\right)$$
If a probe is completely dropped (sentinel -1.0), it receives the maximum penalty of $5.0$.

#### Q49: Why is the security overhead term only included when `is_measured == True`?
**Answer:** To prevent corrupting the mathematical learning signal with fabricated, unverified penalties when running in simulation fallback mode.

#### Q50: How does Module 08 update the LinUCB agent?
**Answer:** It calls `agent.update(action, context, reward)`, which executes the recursive outer product updates: $\mathbf{A}_a \leftarrow \mathbf{A}_a + \mathbf{x}_t \mathbf{x}_t^T$ and $\mathbf{b}_a \leftarrow \mathbf{b}_a + r_t \mathbf{x}_t$.

---

## Category 11: Evaluation & Comparisons

#### Q51: Are the Module 09 benchmark results from a live network or a simulation?
**Answer:** They are generated by a **trace-driven simulation model** using first-principles fluid FIFO queuing physics under identical 20-step dynamic workloads.

#### Q52: What is the 99th-percentile (p99) latency and why is it critical?
**Answer:** The p99 latency is the value below which 99% of observations fall. Mean latency can look deceptively healthy even when severe tail spikes occur. In our benchmarks, Unsafe AI had an acceptable mean latency (11.15 ms) but a disastrous p99 latency of **26.35 ms**, hiding an SLA breach that p99 exposed.

#### Q53: What happened during the surge in the Unsafe AI baseline?
**Answer:** At Step 11, the eMBB offered load surged to 8.5 Mbps. Unsafe LinUCB allocated 9.0 Mbps, pushing total admitted traffic to 11.5 Mbps on the 10.0 Mbps bottleneck. Buffer accumulation ($16.67\text{ pkts}$) spiked latency to **30.15 ms**, causing an SLA breach.

#### Q54: How did the Proposed AI-Safe system handle the same surge?
**Answer:** The guardrail intercepted candidate allocations exceeding 10.0 Mbps and deterministically repaired them: URLLC was locked at $\ge 3.0\text{ Mbps}$ and eMBB was capped at $6.5\text{ Mbps}$. As a result, latency peaked at only **12.51 ms** (zero breaches) and throughput was higher than static slicing (4.19 vs 4.02 Mbps).

#### Q55: What do the generated plots in `results/` show?
**Answer:**
- `comparison.png`: Grouped bar chart showing SLA violations (5% in Unsafe vs 0% in Proposed) and throughput gains.
- `latency.png`: 3-panel time series plotting simulated RTT against the 15.0 ms red dashed SLA ceiling.
- `throughput.png`: 3-panel time series showing dynamic bandwidth allocation adaptation over time.

---

## Category 12: Testing, Limitations, & Future Work

#### Q56: How many automated tests exist in your test suite and do they pass?
**Answer:** **114 automated unit and integration tests** across 13 test files, passing with 100% success in under 4 seconds on Python 3.11.

#### Q57: What does passing the 114 tests prove, and what does it NOT prove?
**Answer:**
- **What it proves:** Complete algorithmic correctness, mathematical invariance of context building, numerical stability of SRA-LinUCB, guardrail gate enforcement, deterministic repair logic, and causal feedback attribution.
- **What it does NOT prove:** It does not prove that an OpenFlow switch in hardware will not drop packets if its physical CPU overheats or if kernel queues desynchronize.

#### Q58: What is the single biggest limitation of your current implementation?
**Answer:** The control loop currently runs closed-loop in the simulation benchmark (Module 09), while the live Ryu controller (Module 07) operates as an L2 forwarding switch without dynamic meter actuation. Connecting the guardrail directly to live switch flow tables is Phase 10 work.

#### Q59: What are your three remaining milestones for final production deployment?
**Answer:**
1. **Phase 10:** Dynamic data-plane actuation via OpenFlow meters or OVS HTB queues (`controller/slicing_actuator.py`).
2. **Phase 11:** Real-time web visualization dashboard (`dashboard/app.py`).
3. **Phase 12:** Single-command unified live runner (`run_live_system.py`).

#### Q60: If a faculty member asks: "Could you deploy this system on a campus or 5G enterprise network tomorrow?", how do you answer?
**Answer:** "The decision and safety pipeline—telemetry collection, context extraction, SRA-LinUCB decision making, and deterministic guardrail gatekeeping—is fully implemented, mathematically verified, and tested across 114 tests. To deploy on production enterprise hardware tomorrow, we would configure OpenFlow 1.3 meter bands or hardware QoS queues on the physical aggregation switches to enforce the guardrail's bandwidth outputs on the physical wire."
