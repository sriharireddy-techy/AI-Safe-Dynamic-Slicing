# Module-by-Module Technical & Defense Guide
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## Guide Overview
This document provides an exhaustive, code-verified technical breakdown of all 9 modules in the project. Every module is analyzed using the standardized 17-point engineering and viva defense structure.

---

## Module 01: SDN Network & Slicing Topology

1. **Module Number and Name:** Module 01 — SDN Network & Slicing Topology
2. **Purpose in One Sentence:** Builds a 2-switch, 6-host Mininet emulation environment modeling a 10 Mbps bottleneck with isolated 5G traffic slices.
3. **The Problem It Solves:** Physical telecommunication testbeds cost thousands of dollars and lack reproducibility. Module 01 provides an open, deterministic, software-emulated physical data plane.
4. **Why Needed:** Required to generate genuine Linux kernel networking packets, host namespaces, and physical buffer competition for testing our AI and guardrail.
5. **Inputs:** Link parameters (`bw=10`, `delay='5ms'`), switch protocol (`OpenFlow13`), host IP assignments.
6. **Outputs:** Running Mininet network with virtual switches `s1`, `s2` and hosts `h1` through `h6`.
7. **Files, Classes, and Functions:**
   - File: [`topology/topology.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/topology/topology.py)
   - Classes: `SlicingTopo(Topo)`
   - Functions: `SlicingTopo.build()`, `run()`
8. **Step-by-Step Execution Flow:**
   1. `SlicingTopo.build()` instantiates switches `s1` and `s2` with OpenFlow 1.3.
   2. Creates hosts `h1..h3` on `s1` and `h4..h6` on `s2`.
   3. Instantiates host-to-switch links with default line-speed parameters.
   4. Instantiates inter-switch bottleneck link with Linux `TCLink` applying 10 Mbps bandwidth and 5 ms delay.
   5. `run()` binds topology to `RemoteController` on `127.0.0.1:6633` and launches CLI.
9. **Important Variables and Data Structures:**
   - `s1`, `s2`: Open vSwitch bridges.
   - `h1` (`10.0.0.1`), `h4` (`10.0.0.4`): URLLC slice endpoints.
   - `h2` (`10.0.0.2`), `h5` (`10.0.0.5`): eMBB slice endpoints.
   - `h3` (`10.0.0.3`), `h6` (`10.0.0.6`): Best-Effort slice endpoints.
10. **Mathematical Formulas:**
    $$RTT_{\text{prop}} = \text{delay}(s1 \rightarrow s2) + \text{delay}(s2 \rightarrow s1) = 5.0\text{ ms} + 5.0\text{ ms} = 10.0\text{ ms}$$
11. **Worked Example:**
    - Sending 1 ping from `H1` to `H4` with zero queuing:
      $$\text{Latency} = 5.0\text{ ms forward} + 5.0\text{ ms return} + 0.15\text{ ms OS overhead} = 10.15\text{ ms}$$
12. **Why Chosen vs. Alternatives:**
    - Chosen: Mininet with Open vSwitch.
    - Alternative: NS-3 simulation or physical hardware.
    - Trade-off: NS-3 cannot run real Linux network tools (`ping`, `iperf3`, `tc`); physical hardware is costly and inflexible. Mininet executes actual Linux kernel network stacks.
13. **Failure Cases & Limitations:**
    - Mininet requires root/sudo privileges and Linux kernel support.
    - If residual Mininet processes remain running, ports conflict (`sudo mn -c` required).
14. **Connection to Other Modules:**
    - Data plane monitored by Module 02 (Telemetry).
    - Forwarding controlled by Module 07 (Ryu Controller).
15. **Tests Covering It:** Live Mininet `pingall` verification.
16. **Implementation Evidence:** Code present in `topology/topology.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: Why is the bottleneck link 10 Mbps?* A: To simulate severe resource contention and bufferbloat under modest traffic generation in an emulation environment.
    - *Q2: Is delay one-way or two-way?* A: Mininet `TCLink` configures netem on both interfaces, so 5 ms applies in each direction, producing a 10 ms RTT baseline.
    - *Q3: What protocol version connects switches to the controller?* A: OpenFlow 1.3.
    - *Q4: Are physical queues configured on the switch ports?* A: No, in the current topology code, slices are logical IP endpoints sharing the default queue.
    - *Q5: How do you clean up an aborted Mininet session?* A: Run `sudo mn -c`.

---

## Module 07: SDN Control Plane with Ryu

1. **Module Number and Name:** Module 07 — SDN Control Plane with Ryu
2. **Purpose in One Sentence:** Implements an asynchronous OpenFlow 1.3 MAC-learning switch controller that dynamically installs wire-speed forwarding rules.
3. **The Problem It Solves:** Without a controller, OpenFlow switches drop all packets by default. Module 07 provides the intelligence to learn MAC addresses and install forwarding rules.
4. **Why Needed:** Separates control plane routing logic from the forwarding data plane, enabling programmatic SDN control.
5. **Inputs:** OpenFlow 1.3 event messages (`EventOFPSwitchFeatures`, `EventOFPPacketIn`).
6. **Outputs:** `OFPFlowMod` messages installing flow entries, `OFPPacketOut` forwarding packets.
7. **Files, Classes, and Functions:**
   - File: [`controller/ryu_controller.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/controller/ryu_controller.py)
   - Classes: `SlicingController(app_manager.RyuApp)`
   - Functions: `switch_features_handler()`, `add_flow()`, `packet_in_handler()`
8. **Step-by-Step Execution Flow:**
   1. On handshake, `switch_features_handler()` installs a table-miss entry (`priority=0`) sending unknown packets to controller.
   2. Packet arrives at switch with unknown destination $\rightarrow$ sent to controller as `OFPPacketIn`.
   3. Controller extracts `eth.src`, `eth.dst`, and `in_port`, recording `mac_to_port[dpid][src] = in_port`.
   4. If destination MAC is known, controller installs a flow rule (`priority=1`) matching `in_port` and `eth_dst`.
   5. Controller sends `OFPPacketOut` to forward the current packet.
9. **Important Variables and Data Structures:**
   - `mac_to_port`: Dictionary mapping datapath ID to `{mac_address: ingress_port}`.
   - `OFPFlowMod`: OpenFlow modification message containing match criteria and action instructions.
10. **Mathematical Formulas:** N/A (Algorithmic L2 lookup and flow installation).
11. **Worked Example:**
    - Host `H1` (MAC `00:00:00:00:00:01`) pings `H4` (MAC `00:00:00:00:00:04`).
    - First packet triggers `PacketIn` on `S1`. `S1` records `H1` is on port 1.
    - Since `H4` is unknown, packet is flooded. `H4` replies on port 4.
    - Controller installs rule: `in_port=1, eth_dst=H4 -> output=4`. Subsequent packets bypass controller.
12. **Why Chosen vs. Alternatives:**
    - Chosen: Ryu Framework with OpenFlow 1.3.
    - Alternatives: OpenDaylight, ONOS, POX.
    - Trade-offs: OpenDaylight/ONOS are heavyweight Java platforms requiring high RAM; POX only supports OpenFlow 1.0. Ryu is pure Python, lightweight, and supports OpenFlow 1.3.
13. **Failure Cases & Limitations:**
    - *Critical Distinction:* The current controller is an **L2 MAC-learning switch only**. It does **not** currently implement dynamic OpenFlow 1.3 meter modifications (`OFPMeterMod`) or queue assignments.
14. **Connection to Other Modules:**
    - Connects directly to switches from Module 01 via TCP port 6633.
    - Target for dynamic rate actuation in Phase 10.
15. **Tests Covering It:** Live Mininet `pingall` tests with 0% loss.
16. **Implementation Evidence:** Code in `controller/ryu_controller.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: What is the role of Ryu in this project?* A: It acts as the centralized SDN controller managing OpenFlow switches via OpenFlow 1.3.
    - *Q2: What is the table-miss flow entry?* A: A lowest-priority (`priority=0`) wildcard rule that forwards unhandled packets to the controller.
    - *Q3: Does the current controller enforce AI bandwidth allocations?* A: No, the current implementation handles L2 MAC learning; dynamic meter/queue actuation is planned for Phase 10.
    - *Q4: What port does Ryu listen on?* A: Standard OpenFlow TCP port 6633.
    - *Q5: How does the controller prevent infinite packet-in flooding?* A: By installing proactive bidirectional flow entries with `priority=1` once destination MACs are learned.

---

## Module 02: Network Telemetry Collector

1. **Module Number and Name:** Module 02 — Network Telemetry Collector
2. **Purpose in One Sentence:** Gathers non-invasive active and passive network metrics (RTT latency, packet loss, bottleneck throughput, queue backlog) and serializes them to CSV.
3. **The Problem It Solves:** AI models cannot make decisions without accurate, real-time observational state from the data plane.
4. **Why Needed:** Provides the continuous observational foundation for context extraction.
5. **Inputs:** Switch interface statistics (`/sys/class/net/s1-eth4/statistics/`), Linux `tc` queue output, ICMP echo probes via `mnexec`.
6. **Outputs:** `TelemetryRecord` dataclass instances and persisted records in `data/telemetry.csv`.
7. **Files, Classes, and Functions:**
   - File: [`telemetry/monitor.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/monitor.py)
   - Classes: `TelemetryRecord`, `NetworkTelemetryCollector`
   - Functions: `parse_ping_output()`, `parse_tc_queue_output()`, `calculate_rates()`, `log_to_csv()`, `collect()`
8. **Step-by-Step Execution Flow:**
   1. `read_port_counters()` reads raw RX and TX bytes from sysfs.
   2. `read_queue_occupancy()` executes `tc -s qdisc show dev s1-eth4` and parses backlogged packets.
   3. `probe_urllc_latency()` discovers H1's process PID and executes `mnexec -a <PID> ping -c 1 10.0.0.4`.
   4. `calculate_rates()` calculates differential throughput over the elapsed time interval $\Delta t$.
   5. Populates `TelemetryRecord` and appends to CSV.
9. **Important Variables and Data Structures:**
   - `TelemetryRecord`: Dataclass storing timestamp, interface, latency, loss, bytes, throughput, rate, queue.
   - `h1_pid`: Operating system PID of Mininet host H1.
   - Sentinel: `-1.0 ms` latency and `100.0%` loss on dropped probes.
10. **Mathematical Formulas:**
    $$\text{Throughput (Mbps)} = \frac{\Delta \text{TX Bytes} \times 8}{\Delta t \times 1,000,000}$$
    $$\text{Traffic Rate (Mbps)} = \frac{(\Delta \text{TX Bytes} + \Delta \text{RX Bytes}) \times 8}{\Delta t \times 1,000,000}$$
11. **Worked Example:**
    - Previous TX bytes: $10,000,000$, Current TX bytes: $11,250,000$, $\Delta t = 1.0\text{ s}$.
    - $\Delta \text{TX} = 1,250,000\text{ bytes}$.
    - $\text{Throughput} = \frac{1,250,000 \times 8}{1.0 \times 1,000,000} = \frac{10,000,000}{1,000,000} = 10.0\text{ Mbps}$.
12. **Why Chosen vs. Alternatives:**
    - Passive sysfs counters + active probing.
    - Alternative: sFlow / NetFlow / OpenFlow port stats polling.
    - Trade-off: sFlow samples packets probabilistically; OpenFlow stats polling creates control plane messaging overhead. Sysfs reading is $O(1)$ kernel memory access.
13. **Failure Cases & Limitations:**
    - Mininet host namespace isolation: A standard ping from the root shell fails. Solved using `mnexec -a <PID> ping`.
    - Dropped probes return sentinel `-1.0 ms` rather than raising an exception.
14. **Connection to Other Modules:**
    - Observes Module 01 data plane.
    - Passes `TelemetryRecord` to Module 03 (Context Builder).
15. **Tests Covering It:** [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py) (15 unit tests passing).
16. **Implementation Evidence:** Tested and working in `telemetry/monitor.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: How does the monitor ping inside Mininet host H1?* A: It queries H1's Linux PID and runs `mnexec -a <PID> ping` inside H1's isolated network namespace.
    - *Q2: How is throughput calculated without injecting probe traffic?* A: By reading raw byte counters from Linux sysfs (`/sys/class/net/s1-eth4/statistics/`) and computing the time derivative.
    - *Q3: What happens if a ping probe drops completely?* A: It returns safe sentinel values (`-1.0 ms` latency, `100.0%` loss) to avoid crashing the control loop.
    - *Q4: What is the unit of queue occupancy?* A: Number of packets currently backlogged in the egress buffer, parsed from `tc`.
    - *Q5: Does throughput calculation handle counter wrap-around?* A: Yes, if current bytes < previous bytes, delta resets safely to zero.

---

## Module 03: Context & Feature Extraction

1. **Module Number and Name:** Module 03 — Context & Feature Extraction
2. **Purpose in One Sentence:** Converts raw telemetry into a normalized, bounded 6-dimensional context vector $\mathbf{x}_t \in \mathbb{R}^6$ with temporal latency trend velocity.
3. **The Problem It Solves:** Raw network metrics have wildly incompatible numerical scales ($10\text{ ms}$, $10\text{ Mbps}$, $50\text{ pkts}$, $100\%$). Feeding unnormalized features into linear regression causes large numbers to dominate learning.
4. **Why Needed:** Prepares balanced mathematical inputs for the SRA-LinUCB ridge regression engine.
5. **Inputs:** `TelemetryRecord` dataclass or dictionary from Module 02.
6. **Outputs:** 1D NumPy array $\mathbf{x}_t = [x_0, x_1, x_2, x_3, x_4, x_5]^T \in \mathbb{R}^6$.
7. **Files, Classes, and Functions:**
   - File: [`ai/context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/context_builder.py)
   - Classes: `ContextBuilder`
   - Functions: `build_context()`, `reset()`
8. **Step-by-Step Execution Flow:**
   1. Extracts raw latency, loss, throughput, and queue depth.
   2. Sets $x_0 = 1.0$ (bias term).
   3. Sanitizes sentinel: if latency is $-1.0$, sets $x_1 = 1.0$ and $x_5 = 1.0$.
   4. Normalizes latency against 50 ms ceiling: $x_1 = \min(1.0, \text{lat} / 50.0)$.
   5. Normalizes throughput against 10 Mbps bottleneck: $x_2 = \min(1.0, \text{tput} / 10.0)$.
   6. Normalizes queue against 50 packets limit: $x_3 = \min(1.0, \text{queue} / 50.0)$.
   7. Computes temporal trend velocity: $x_4 = \text{clip}((\text{lat}_t - \text{lat}_{t-1})/10.0, -1.0, 1.0)$.
   8. Normalizes loss: $x_5 = \text{loss} / 100.0$.
9. **Important Variables and Data Structures:**
   - `max_latency`: 50.0 ms.
   - `max_throughput`: 10.0 Mbps.
   - `max_queue`: 50.0 packets.
   - `prev_latency`: Historical state for discrete derivative calculation.
10. **Mathematical Formulas:**
    $$\mathbf{x}_t = \left[1.0, \; \min\left(1.0, \frac{L_t}{50}\right), \; \min\left(1.0, \frac{T_t}{10}\right), \; \min\left(1.0, \frac{Q_t}{50}\right), \; \text{clip}\left(\frac{L_t - L_{t-1}}{10}, -1, 1\right), \; \frac{P_t}{100}\right]^T$$
11. **Worked Example:**
    - Raw Telemetry: Latency = $25.0\text{ ms}$, Throughput = $5.0\text{ Mbps}$, Queue = $10\text{ pkts}$, Previous Latency = $15.0\text{ ms}$, Loss = $0.0\%$.
    - $x_0 = 1.0$
    - $x_1 = 25.0 / 50.0 = 0.50$
    - $x_2 = 5.0 / 10.0 = 0.50$
    - $x_3 = 10.0 / 50.0 = 0.20$
    - $x_4 = (25.0 - 15.0) / 10.0 = +1.0$ (congestion rising)
    - $x_5 = 0.0 / 100.0 = 0.0$
    - Vector: $\mathbf{x}_t = [1.0, 0.50, 0.50, 0.20, 1.0, 0.0]^T$.
12. **Why Chosen vs. Alternatives:**
    - Chosen: Bounded clipping $[0.0, 1.0]$ with temporal velocity.
    - Alternative: Standard Z-score standardization ($z = (x - \mu)/\sigma$).
    - Trade-off: Z-score requires offline dataset statistics $(\mu, \sigma)$ which are unknown in live online streaming. Bounded scaling works instantly online.
13. **Failure Cases & Limitations:**
    - If sentinel $-1.0$ is passed without sanitization, linear regression would treat negative latency as extremely good. Module 03 explicitly sanitizes $-1.0 \rightarrow 1.0$ (worst-case).
14. **Connection to Other Modules:**
    - Ingests `TelemetryRecord` from Module 02.
    - Passes $\mathbf{x}_t$ to Module 04 (SRA-LinUCB).
15. **Tests Covering It:** [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py) (17 unit tests passing).
16. **Implementation Evidence:** Code in `ai/context_builder.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: Why is $x_0$ always 1.0?* A: It acts as the intercept/bias term for linear ridge regression.
    - *Q2: Why is latency normalized to 50 ms when SLA is 15 ms?* A: To prevent the feature from saturating at 1.0 immediately upon minor congestion, giving the AI dynamic visibility into severe congestion.
    - *Q3: What does a negative $x_4$ value mean?* A: Latency is decreasing relative to the previous sample; the network is de-congesting.
    - *Q4: What happens on the very first sample when there is no previous latency?* A: $x_4$ defaults to 0.0 (neutral trend).
    - *Q5: How are dropped ping probes sanitized?* A: Negative latency is mapped to $x_1 = 1.0$ (maximum latency) and $x_5 = 1.0$ (100% loss).

---

## Module 04: SRA-LinUCB Decision Engine

1. **Module Number and Name:** Module 04 — SRA-LinUCB Decision Engine
2. **Purpose in One Sentence:** Evaluates the 6D context vector online using Security- and Risk-Aware Linear Upper Confidence Bound to propose candidate bandwidth adjustments.
3. **The Problem It Solves:** Pure exploration in standard contextual bandits picks risky bandwidth increases during stress just to reduce uncertainty. SRA-LinUCB introduces a risk penalty to suppress risky actions during congestion.
4. **Why Needed:** Drives dynamic optimization while maintaining awareness of physical link stress.
5. **Inputs:** Context vector $\mathbf{x}_t \in \mathbb{R}^6$, exploration parameter $\alpha$, risk coefficient $\lambda$, external rewards.
6. **Outputs:** Candidate action $a^* \in \{0, 1, 2\}$ and detailed scoring diagnostics.
7. **Files, Classes, and Functions:**
   - File: [`ai/linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/linucb.py)
   - Classes: `SRALinUCB`
   - Functions: `estimate_theta()`, `compute_standard_ucb()`, `compute_context_risk()`, `compute_risk_adjustment()`, `select_action()`, `update()`
8. **Step-by-Step Execution Flow:**
   1. For each arm $a \in \{0, 1, 2\}$, computes estimated parameters $\hat{\boldsymbol{\theta}}_a = \mathbf{A}_a^{-1} \mathbf{b}_a$ via `np.linalg.solve()`.
   2. Computes mean reward: $\mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a$.
   3. Computes uncertainty bonus: $\alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t}$.
   4. Computes Context Risk: $R(\mathbf{x}_t) = 0.4 x_1 + 0.3 x_3 + 0.2 \max(0, x_4) + 0.1 x_5$.
   5. Applies risk adjustment: $\text{Score}_a = \text{UCB}_a - \lambda \rho_a R(\mathbf{x}_t)$.
   6. Selects $a^* = \arg\max_a \text{Score}_a$.
9. **Important Variables and Data Structures:**
   - Actions: `0: DECREASE_EMBB` ($\rho_0 = -1.0$), `1: MAINTAIN` ($\rho_1 = 0.0$), `2: INCREASE_EMBB` ($\rho_2 = +1.0$).
   - $\mathbf{A}_a \in \mathbb{R}^{6 \times 6}$: Precision covariance matrix initialized to identity $\mathbf{I}_6$.
   - $\mathbf{b}_a \in \mathbb{R}^6$: Reward-weighted context accumulator initialized to zeros.
   - $\alpha = 1.0$, $\lambda = 0.5$.
10. **Mathematical Formulas:**
    $$\text{Score}_a(\mathbf{x}_t) = \mathbf{x}_t^T \hat{\boldsymbol{\theta}}_a + \alpha \sqrt{\mathbf{x}_t^T \mathbf{A}_a^{-1} \mathbf{x}_t} - \lambda \rho_a R(\mathbf{x}_t)$$
    $$\mathbf{A}_a \leftarrow \mathbf{A}_a + \mathbf{x}_t \mathbf{x}_t^T, \quad \mathbf{b}_a \leftarrow \mathbf{b}_a + r_t \mathbf{x}_t$$
11. **Worked Example:**
    - Assume initial state ($\mathbf{A}_a = \mathbf{I}_6, \mathbf{b}_a = \mathbf{0} \Rightarrow \hat{\boldsymbol{\theta}}_a = \mathbf{0}$).
    - Let $\mathbf{x}_t = [1.0, 0.4, 0.5, 0.2, 0.5, 0.0]^T$. Then $\|\mathbf{x}_t\|_2^2 = 1 + 0.16 + 0.25 + 0.04 + 0.25 + 0 = 1.70$.
    - UCB uncertainty bonus = $\alpha \sqrt{\mathbf{x}_t^T \mathbf{I}^{-1} \mathbf{x}_t} = 1.0 \times \sqrt{1.70} \approx 1.3038$.
    - Context Risk $R(\mathbf{x}_t) = 0.4(0.4) + 0.3(0.2) + 0.2(0.5) + 0.1(0) = 0.16 + 0.06 + 0.10 = 0.32$.
    - For Action 0 ($\rho_0 = -1.0$): Penalty term is $-0.5(-1.0)(0.32) = +0.16$. Score = $1.3038 + 0.16 = \mathbf{1.4638}$.
    - For Action 1 ($\rho_1 = 0.0$): Score = $1.3038 - 0.0 = \mathbf{1.3038}$.
    - For Action 2 ($\rho_2 = +1.0$): Penalty term is $-0.5(+1.0)(0.32) = -0.16$. Score = $1.3038 - 0.16 = \mathbf{1.1438}$.
    - Candidate Action chosen: **Action 0 (`DECREASE_EMBB`)**. The risk penalty successfully steered the AI toward safety!
12. **Why Chosen vs. Alternatives:**
    - Chosen: SRA-LinUCB.
    - Alternatives: Deep Q-Networks (DQN), PPO, standard LinUCB.
    - Trade-offs: Deep RL requires thousands of training steps and high inference latency. Standard LinUCB explores aggressively during congestion. SRA-LinUCB updates in closed form and dampens risk.
13. **Failure Cases & Limitations:**
    - LinUCB assumes a linear relationship between context and expected reward. Non-linear saturation must be handled by feature normalization and the guardrail.
14. **Connection to Other Modules:**
    - Receives $\mathbf{x}_t$ from Module 03.
    - Sends candidate action to Module 06 (Guardrail).
    - Receives online parameter updates from Module 08 (Feedback Learner).
15. **Tests Covering It:** [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py) (11 unit tests passing).
16. **Implementation Evidence:** Code in `ai/linucb.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: Why use `np.linalg.solve()` instead of `np.linalg.inv()`?* A: `solve` uses direct LU/Cholesky decomposition, which is faster and avoids floating-point precision loss.
    - *Q2: What is the physical meaning of $\rho_a$?* A: The physical congestion risk profile of the action: $-1.0$ for decreasing eMBB (de-congesting), $0.0$ for maintaining, and $+1.0$ for increasing eMBB (congestion risk).
    - *Q3: What happens when $\lambda = 0$?* A: The algorithm reduces exactly to standard risk-neutral LinUCB.
    - *Q4: What happens if $\alpha$ is set very high?* A: The agent prioritizes exploration over exploitation, heavily favoring actions with high uncertainty.
    - *Q5: Is the candidate action directly executed on the switch?* A: No, it is strictly a proposal that must be vetted by Module 06 Guardrail first.

---

## Module 05: Security & Overhead Profiling

1. **Module Number and Name:** Module 05 — Security & Overhead Profiling
2. **Purpose in One Sentence:** Models the cryptographic encapsulation delay and throughput penalty of secure network slices (WireGuard) and probes system interfaces.
3. **The Problem It Solves:** Slices carrying sensitive data require end-to-end encryption, but encryption adds byte overhead and CPU latency that can push URLLC traffic past its 15.0 ms SLA.
4. **Why Needed:** Informs the guardrail of added crypto delay so safety verifications do not breach SLAs when security is activated.
5. **Inputs:** Security operational mode (`OFF`/`ON`), WireGuard kernel status (`wg show wg0`), overhead metrics.
6. **Outputs:** `SecurityState` dataclass instances and `SecurityOverheadReport`.
7. **Files, Classes, and Functions:**
   - Files: [`security/security_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_config.py), [`security/security_metrics.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/security_metrics.py), [`security/wireguard_adapter.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/security/wireguard_adapter.py)
   - Classes: `SecurityState`, `SecurityMode`, `SecurityProtocol`, `SecurityMetrics`, `WireGuardAdapter`
   - Functions: `calculate_latency_overhead()`, `calculate_throughput_penalty()`, `compare_security_off_on()`, `get_status()`
8. **Step-by-Step Execution Flow:**
   1. `SecurityState` tracks mode, risk level, and crypto overhead.
   2. Configured defaults specify $\Delta_{\text{crypto}} = 1.2\text{ ms}$, throughput penalty $= 0.5\text{ Mbps}$, header overhead $= 32\text{ bytes}$.
   3. `WireGuardAdapter.get_status()` safely queries local WireGuard tools (`wg`) via subprocess, falling back gracefully if uninstalled.
   4. The `is_measured` flag distinguishes genuine empirical kernel measurements from simulated project defaults.
9. **Important Variables and Data Structures:**
   - `SecurityState`: Dataclass holding mode, risk, protocol, latency overhead, throughput penalty, `is_measured`.
   - `WIREGUARD_TRANSPORT_HEADER_BYTES`: 32 bytes (20 IP + 8 UDP + 4 WG header).
10. **Mathematical Formulas:**
    $$\Delta \text{Latency} = \text{Lat}_{\text{ON}} - \text{Lat}_{\text{OFF}}$$
    $$\text{Relative Latency \%} = \frac{\text{Lat}_{\text{ON}} - \text{Lat}_{\text{OFF}}}{\text{Lat}_{\text{OFF}}} \times 100$$
11. **Worked Example:**
    - Baseline latency without security: $10.15\text{ ms}$.
    - Latency with WireGuard enabled: $11.35\text{ ms}$.
    - Absolute Overhead: $11.35 - 10.15 = 1.20\text{ ms}$.
    - Relative Overhead: $(1.20 / 10.15) \times 100 = 11.82\%$.
12. **Why Chosen vs. Alternatives:**
    - Chosen: WireGuard profile with graceful simulation fallback.
    - Alternatives: IPsec, OpenVPN.
    - Trade-offs: IPsec and OpenVPN run complex multi-state daemons with heavy CPU context-switching overhead. WireGuard is in-kernel, modern, fast, and uses state-of-the-art ChaCha20-Poly1305 cryptography.
13. **Failure Cases & Limitations:**
    - If running on Windows or non-root Linux where `wg` is unavailable, `WireGuardAdapter` returns clean fallback metadata without throwing exceptions.
14. **Connection to Other Modules:**
    - Provides `SecurityState` to Module 06 (Guardrail) to calculate effective latency.
    - Provides `is_measured` flag to Module 08 (Reward Engine) to prevent fabricating unverified reward terms.
15. **Tests Covering It:** [`tests/test_security.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) (13 unit tests passing).
16. **Implementation Evidence:** Code in `security/`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: Why does encryption matter in dynamic network slicing?* A: Encryption adds packet header overhead (32 bytes) and cryptographic processing delay ($\approx 1.2\text{ ms}$) that can cause unexpected SLA breaches if ignored.
    - *Q2: What is the purpose of the `is_measured` flag?* A: It distinguishes genuine physical kernel measurements from configured simulation baselines.
    - *Q3: What happens if WireGuard is not installed on the host?* A: `WireGuardAdapter` catches the exception and returns a graceful fallback dictionary with `available: False`.
    - *Q4: What is the configured default latency overhead for WireGuard?* A: $1.2\text{ ms}$.
    - *Q5: Does this module contain an active threat attack detector?* A: No, it models security states, risk scores, and crypto overhead profiles; it is not an Intrusion Detection System.

---

## Module 06: Deterministic SLA & Security Guardrail

1. **Module Number and Name:** Module 06 — Deterministic SLA & Security Guardrail
2. **Purpose in One Sentence:** Acts as an un-bypassable gatekeeper that evaluates candidate actions against 6 hard capacity, latency, loss, and security gates, deterministically repairing over-budget requests.
3. **The Problem It Solves:** Statistical machine learning models cannot provide mathematical safety guarantees. Module 06 prevents unsafe candidate allocations from reaching physical flow tables.
4. **Why Needed:** Enforces the core architectural invariant: *"Never let AI optimize at the cost of a critical SLA."*
5. **Inputs:** Candidate action (integer, string, or allocation dict), observed context/telemetry, optional `SecurityState`, `allow_repair` flag.
6. **Outputs:** Validation dictionary: `approved` (bool), `action` (dict or None), `reason` (str), `violations` (list), `is_repaired` (bool), `metadata` (dict).
7. **Files, Classes, and Functions:**
   - Files: [`guardrail/guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/guardrail.py), [`guardrail/sla_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/guardrail/sla_config.py)
   - Classes: `SLASecurityGuardrail`, `GuardrailConfig`, `DiscreteAction`, `GuardrailViolation`
   - Functions: `validate()`, `map_candidate_action()`, `resolve_effective_latency()`, `_attempt_deterministic_repair()`
8. **Step-by-Step Execution Flow:**
   1. Validates and normalizes context dictionary or `TelemetryRecord`.
   2. Maps candidate action into canonical allocation dictionary (`URLLC`, `eMBB`, `BE`).
   3. **Gate 1:** Checks total bandwidth capacity ($\sum \le 10.0\text{ Mbps}$).
   4. **Gate 2:** Checks URLLC minimum reservation ($B_{\text{URLLC}} \ge 3.0\text{ Mbps}$).
   5. **Gate 3:** Resolves effective latency (adding crypto delay if not already included) and checks $\le 15.0\text{ ms}$.
   6. **Gate 4:** Checks packet loss ($\le 1.0\%$).
   7. **Gate 5:** Checks security risk score ($\le 0.70$).
   8. **Gate 6:** Checks crypto latency overhead ($\le 5.0\text{ ms}$).
   9. If violations exist and `allow_repair=True`, executes `_attempt_deterministic_repair()`.
9. **Important Variables and Data Structures:**
   - `GuardrailConfig`: Holds thresholds (10.0 Mbps, 15.0 ms SLA, 3.0 Mbps URLLC min, 1.0% loss, 0.70 risk).
   - `GuardrailViolation`: Enums for standard violation types.
10. **Mathematical Formulas:**
    $$\text{Effective Latency} = \text{Raw Latency} + (\Delta_{\text{crypto}} \text{ if not included})$$
    $$\text{Repaired } B_{\text{URLLC}} = \max(B_{\text{candidate, URLLC}}, 3.0\text{ Mbps})$$
    $$\text{Repaired } B_{\text{eMBB}} = \min(B_{\text{candidate, eMBB}}, 10.0 - B_{\text{URLLC}} - 0.5)$$
    $$\text{Repaired } B_{\text{BE}} = 10.0 - B_{\text{URLLC}} - B_{\text{eMBB}}$$
11. **Worked Example (Deterministic Repair from Test Suite):**
    - Candidate Action: Requests URLLC = 4.0 Mbps, eMBB = 7.0 Mbps, BE = 2.0 Mbps.
    - Total requested: $4.0 + 7.0 + 2.0 = 13.0\text{ Mbps} > 10.0\text{ Mbps}$ ($\rightarrow$ `CAPACITY_EXCEEDED`).
    - Repair Logic:
      - URLLC is preserved at $\max(4.0, 3.0) = 4.0\text{ Mbps}$.
      - Remaining link capacity = $10.0 - 4.0 = 6.0\text{ Mbps}$.
      - eMBB is capped at $6.0 - 0.5\text{ (BE floor)} = 5.5\text{ Mbps}$.
      - BE receives remainder = $10.0 - 4.0 - 5.5 = 0.5\text{ Mbps}$.
    - Repaired Allocation: `{URLLC: 4.0, eMBB: 5.5, BE: 0.5}` (Total = $10.0\text{ Mbps}$). Approved as repaired!
12. **Why Chosen vs. Alternatives:**
    - Chosen: Pre-execution deterministic gatekeeper with repair.
    - Alternative: Reward penalty only.
    - Trade-off: Reward penalty occurs post-execution after damage is done. Guardrail guarantees zero physical breaches.
13. **Failure Cases & Limitations:**
    - If external physical latency exceeds 15.0 ms (e.g., physical fiber cut), deterministic bandwidth repair cannot fix external latency. The guardrail rejects the action and reports `URLLC_LATENCY_VIOLATION`.
14. **Connection to Other Modules:**
    - Intercepts candidate action from Module 04.
    - Ingests `SecurityState` from Module 05.
    - Outputs approved/repaired safe allocation to Module 07 / Actuator.
    - Provides execution outcome status to Module 08 (Feedback Learner).
15. **Tests Covering It:** [`tests/test_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) (14 tests) and [`tests/test_pipeline_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) (7 tests).
16. **Implementation Evidence:** Code in `guardrail/guardrail.py`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: What are the 6 immutable guardrail gates?* A: Link capacity ($\le 10\text{M}$), URLLC minimum reservation ($\ge 3\text{M}$), URLLC latency ($\le 15\text{ms}$), packet loss ($\le 1\%$), security risk ($\le 0.70$), and crypto overhead ($\le 5\text{ms}$).
    - *Q2: What is the difference between rejecting and repairing an action?* A: Rejection blocks the action completely; repair mathematically scales down eMBB and BE to fit within capacity while strictly preserving URLLC.
    - *Q3: Can deterministic repair override an external latency breach?* A: No, repair only applies to allocation overload; environmental SLA breaches (latency, loss) cannot be repaired and are rejected.
    - *Q4: How does the guardrail prevent double-counting crypto delay?* A: It checks the `latency_includes_security` flag; if False, it adds crypto overhead; if True, it avoids adding it again.
    - *Q5: What happens if the guardrail itself crashes?* A: Safe SDN architecture mandates a "fail-safe" default: hold current safe allocations or revert to static partitioning (3/5/2 Mbps).

---

## Module 08: Closed-Loop Reward Engine & Feedback Learner

1. **Module Number and Name:** Module 08 — Closed-Loop Reward Engine & Feedback Learner
2. **Purpose in One Sentence:** Computes continuous multi-objective performance rewards and updates SRA-LinUCB ridge regression statistics strictly based on executed actions.
3. **The Problem It Solves:** Closes the online learning loop. Without causal attribution, penalizing rejected actions would corrupt the AI's model with false negative feedback for actions never executed.
4. **Why Needed:** Enables the bandit to learn from physical network outcomes over time without distorting mathematical parameters.
5. **Inputs:** Post-action network state (`TelemetryRecord`), candidate action, executed action, guardrail validation dictionary, optional `SecurityState`.
6. **Outputs:** Scalar reward $r_t \in \mathbb{R}$, updated bandit matrices $\mathbf{A}_a, \mathbf{b}_a$, execution diagnostics.
7. **Files, Classes, and Functions:**
   - Files: [`feedback/reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/reward.py), [`feedback/learner.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/learner.py)
   - Classes: `RewardEngine`, `RewardConfig`, `FeedbackLearner`
   - Functions: `compute_reward()`, `process_feedback()`, `calculate_reward()`
8. **Step-by-Step Execution Flow:**
   1. `extract_metrics()` standardizes post-action latency, throughput, and loss.
   2. Computes normalized throughput, operational latency, and packet loss.
   3. If latency $> 15.0\text{ ms}$, computes quadratic penalty barrier: $\min(5.0, ((\text{lat} - 15.0)/15.0)^2)$.
   4. If `security_state.is_measured == True`, adds security overhead term.
   5. Computes scalar reward: $r_t = w_{\text{tput}} \tilde{T} - w_{\text{lat}} \tilde{L} - w_{\text{loss}} \tilde{P} - w_{\text{sla}} \text{Penalty}_{\text{SLA}} - w_{\text{sec}} \tilde{S}$.
   6. **Causal Attribution:**
      - If rejected: skips update (`updated_arm = None`).
      - If repaired: updates executed repaired arm.
      - If approved: updates candidate arm.
9. **Important Variables and Data Structures:**
   - Weights: $w_{\text{tput}} = 1.0$, $w_{\text{lat}} = 1.0$, $w_{\text{loss}} = 2.0$, $w_{\text{sla}} = 5.0$, $w_{\text{sec}} = 0.5$.
   - Quadratic barrier cap: $5.0$.
10. **Mathematical Formulas:**
    $$r_t = 1.0 \tilde{T}_t - 1.0 \tilde{L}_t - 2.0 \tilde{P}_t - 5.0 \cdot \text{Penalty}_{\text{SLA}}(t) - 0.5 \tilde{S}_t$$
    $$\mathbf{A}_{\text{executed}} \leftarrow \mathbf{A}_{\text{executed}} + \mathbf{x}_t \mathbf{x}_t^T, \quad \mathbf{b}_{\text{executed}} \leftarrow \mathbf{b}_{\text{executed}} + r_t \mathbf{x}_t$$
11. **Worked Example:**
    - Telemetry: Throughput = $8.0\text{ Mbps}$, Latency = $12.0\text{ ms}$, Loss = $0.0\%$.
    - $\tilde{T} = 8.0 / 10.0 = 0.80$.
    - Operational span = $[10.0, 15.0]$. $\tilde{L} = (12.0 - 10.0) / (15.0 - 10.0) = 2.0 / 5.0 = 0.40$.
    - $\tilde{P} = 0.0$.
    - Latency $\le 15.0\text{ ms} \Rightarrow \text{Penalty}_{\text{SLA}} = 0.0$.
    - Reward: $r_t = 1.0(0.80) - 1.0(0.40) - 0 - 0 = \mathbf{+0.40}$ (healthy positive reward).
12. **Why Chosen vs. Alternatives:**
    - Continuous multi-objective formulation with quadratic barrier.
    - Alternative: Binary $+1 / -1$ reward.
    - Trade-off: Binary rewards fail to capture fine-grained queuing changes before the SLA is breached.
13. **Failure Cases & Limitations:**
    - If feedback is attributed to the candidate arm instead of the executed arm, the AI learns incorrect causal relationships. Solved by Causal Safe Attribution in `FeedbackLearner`.
14. **Connection to Other Modules:**
    - Ingests post-action telemetry from Module 02.
    - Ingests guardrail outcome from Module 06.
    - Calls `update()` on Module 04 (SRA-LinUCB).
15. **Tests Covering It:** [`feedback/test_reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_reward.py) (8 tests), [`feedback/test_learner.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_learner.py) (4 tests), [`tests/test_feedback.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_feedback.py) (5 tests).
16. **Implementation Evidence:** Code in `feedback/`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: What is Causal Safe Attribution?* A: The principle that model parameters are updated strictly for the action that was actually executed on the network, never for rejected candidate actions.
    - *Q2: Why is the SLA penalty quadratic instead of linear?* A: To create a steep mathematical barrier that imposes severe penalties as latency breaches the 15 ms limit.
    - *Q3: When is the security overhead term included in the reward?* A: Strictly when `is_measured == True`, preventing fabrication of unverified penalty signals.
    - *Q4: What is the maximum SLA violation penalty?* A: It is capped at 5.0 (applied fully during connection loss or probe drop).
    - *Q5: Does the reward function enforce safety?* A: No, reward is a soft behavioral feedback signal for machine learning; the Guardrail is the hard safety gatekeeper.

---

## Module 09: Evaluation & Comparative Benchmarking

1. **Module Number and Name:** Module 09 — Evaluation & Comparative Benchmarking
2. **Purpose in One Sentence:** Implements a trace-driven FIFO queuing simulation benchmark comparing Static, Unsafe Dynamic, and Proposed AI-Safe systems across a standardized 20-step dynamic workload.
3. **The Problem It Solves:** Proves scientifically whether the proposed AI-Safe system outperforms traditional static slicing and unconstrained AI.
4. **Why Needed:** Generates empirical datasets, 24-column CSV logs, summary metric tables, and visual time-series plots.
5. **Inputs:** Synthetic dynamic workload profile (20 discrete time steps with an eMBB surge at steps 8–11).
6. **Outputs:** 3 CSV files (`static_results.csv`, `dynamic_results.csv`, `proposed_results.csv`), 3 PNG plots (`latency.png`, `throughput.png`, `comparison.png`), and summary tables.
7. **Files, Classes, and Functions:**
   - Files: [`experiments/static_baseline.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/static_baseline.py), [`experiments/dynamic_baseline.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/dynamic_baseline.py), [`experiments/proposed_system.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/proposed_system.py), [`experiments/run_experiments.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/experiments/run_experiments.py)
   - Functions: `run_simulation()`, `load_csv_data()`, `compute_metrics()`, `plot_latency_comparison()`, `plot_throughput_comparison()`
8. **Step-by-Step Execution Flow:**
   1. Executes Experiment 1 (Static Slicing: fixed 3/5/2 Mbps).
   2. Executes Experiment 2 (Unsafe Dynamic LinUCB: $\lambda = 0.0$, Guardrail disabled).
   3. Executes Experiment 3 (Proposed AI-Safe: SRA-LinUCB $\lambda = 0.5$ + Module 06 Guardrail + Module 08 Feedback).
   4. Writes 24-column CSV files to `results/`.
   5. Computes summary metrics directly from CSV data.
   6. Renders high-resolution plots using Matplotlib.
9. **Important Variables and Data Structures:**
   - Workload: 20 time steps. Off-peak (1–7), Surge (8–11: eMBB demands 8.5 Mbps), Recovery (12–20).
   - Packet serialization time: $1.20\text{ ms/packet}$ ($12,000\text{ bits} / 10\text{ Mbps}$).
   - 24-column schema tracking offered, allocated, throughput, drops, queue, simulated RTT, and decisions.
10. **Mathematical Formulas:**
    $$\Delta Q = \frac{(\text{Admitted Load} - 10.0\text{ Mbps}) \times 10^6 \times \Delta t}{12,000\text{ bits}}$$
    $$RTT_{\text{sim}} = 10.15\text{ ms} + (Q \times 1.20\text{ ms}) + \Delta_{\text{crypto}}$$
11. **Worked Example (Step 11 Congestion in Unsafe AI):**
    - AI allocates $9.0\text{ Mbps}$ to eMBB.
    - Total admitted traffic = $1.0\text{ (URLLC)} + 8.5\text{ (eMBB)} + 2.0\text{ (BE)} = 11.5\text{ Mbps}$.
    - Surplus load = $11.5 - 10.0 = 1.5\text{ Mbps}$.
    - Delta packets = $\frac{1.5 \times 10^6 \times 1.0\text{ s}}{12,000\text{ bits}} = 125\text{ packets/s} \times 0.1\text{ s} \approx 16.67\text{ packets}$.
    - Simulated Latency = $10.15 + (16.67 \times 1.20) = \mathbf{30.15\text{ ms}}$ ($\gg 15.0\text{ ms}$ SLA, Breach!).
12. **Why Chosen vs. Alternatives:**
    - First-principles fluid queuing simulation.
    - Alternative: Pure random numbers or subjective scores.
    - Trade-off: Fluid queuing grounds every millisecond of latency in physical MTU packet serialization physics.
13. **Failure Cases & Limitations:**
    - *Critical Distinction:* Module 09 is a **trace-driven simulation model**, not a live Mininet traffic experiment. It validates mathematical invariants under identical trace workloads.
14. **Connection to Other Modules:**
    - Integrates Modules 02, 03, 04, 05, 06, and 08 in a closed loop.
15. **Tests Covering It:** [`tests/test_experiments.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_experiments.py) (7 invariant tests passing).
16. **Implementation Evidence:** Datasets and plots in `results/`.
17. **Top 5 Viva Questions & Answers:**
    - *Q1: Are Module 09 results live Mininet measurements?* A: No, they are derived from a first-principles FIFO queuing simulation model under identical 20-step trace workloads.
    - *Q2: Where does the $1.20\text{ ms}$ queuing delay per packet come from?* A: A standard 1500-byte MTU packet contains 12,000 bits. On a 10 Mbps bottleneck, transmission delay is $12,000 / 10,000,000 = 1.20\text{ ms}$.
    - *Q3: What happened to Unsafe AI during the surge?* A: It greedily allocated 9.0 Mbps to eMBB, causing queue accumulation ($16.67\text{ pkts}$) and spiking latency to 30.15 ms (SLA breach).
    - *Q4: How did the Proposed AI-Safe system perform during the same surge?* A: The guardrail repaired the allocation, capping eMBB at 6.5 Mbps, resulting in 0 SLA breaches and max latency of 12.51 ms.
    - *Q5: What is the 99th-percentile (p99) latency?* A: The latency value below which 99% of samples fall; captures tail latency that averages hide.
