# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

## 1. Project Overview

This project develops an **AI-driven dynamic network slicing system for Software-Defined Networks (SDN)**.

The main goal is to dynamically allocate network resources among different traffic classes while protecting critical traffic from SLA violations and considering security-related performance overhead.

The project follows the principle:

> **Let AI optimize the network, but do not let AI optimize at the cost of a critical SLA.**

The final system is planned as a closed-loop architecture:

```text
Network Traffic
      ↓
SDN Network & Network Slices
      ↓
Network Telemetry
      ↓
Context / Feature Extraction
      ↓
SRA-LinUCB AI
      ↓
Candidate Resource + Security Action
      ↓
SLA & Security Guardrail
      ↓
   SAFE / UNSAFE
    ↓       ↓
 Execute   Reject / Repair
    ↓
Ryu SDN Controller
    ↓
OpenFlow
    ↓
OVS / Mininet Network
    ↓
Performance Measurement
    ↓
Feedback & Learning
    └──────────────→ AI
```

---

# 2. Problem Being Solved

A shared network carries different types of traffic with different requirements.

For our project, we model three slices:

| Slice | Hosts | Traffic Type | Main Requirement |
|---|---|---|---|
| URLLC | H1 ↔ H4 | Critical / low-latency | Low latency |
| eMBB | H2 ↔ H5 | High-bandwidth | High throughput |
| Best Effort | H3 ↔ H6 | Normal traffic | Remaining resources |

A problem occurs when high-bandwidth eMBB traffic consumes shared network capacity.

For example:

```text
eMBB burst
    ↓
Shared bottleneck becomes congested
    ↓
Queue increases
    ↓
URLLC packets wait longer
    ↓
URLLC latency increases
    ↓
Critical SLA may be violated
```

The project therefore aims to use a lightweight AI controller to adapt resource allocation while an independent safety layer prevents unsafe decisions.

---

# 3. Main Project Components

The complete project is divided into nine modules:

```text
01. SDN Network & Slicing
02. Network Telemetry
03. Context & Feature
04. SRA-LinUCB AI
05. Security
06. SLA & Security Guardrail
07. SDN Control
08. Feedback & Learning
09. Evaluation & Comparison
```

## Module 01 — SDN Network & Slicing

Creates the software-defined network using:

- Mininet
- Open vSwitch (OVS)
- OpenFlow 1.3
- Three logical traffic classes

Current topology:

```text
 H1 ─┐
 H2 ─┤
 H3 ─┤
     S1 ═════════ S2
 H4 ─┤            ├─ H4
 H5 ─┤            ├─ H5
 H6 ─┘            └─ H6
```

More accurately, H1/H2/H3 connect to S1 and H4/H5/H6 connect to S2.

The S1-S2 link is intentionally configured as a **10 Mbps bottleneck with 5 ms delay** to create a controlled congestion environment.

### Current status

**Implemented and tested.**

---

# 4. Module 07 — SDN Control

The SDN control plane uses:

- Ryu Controller
- OpenFlow 1.3
- MAC-learning based forwarding

The controller receives packets from OVS when necessary, learns source MAC addresses, determines the output port for known destinations, and installs forwarding flows.

Basic flow:

```text
Host
 ↓
OVS
 ↓
OpenFlow
 ↓
Ryu Controller
 ↓
Forwarding Decision
 ↓
OVS
 ↓
Destination Host
```

### Current status

**Basic controller implementation completed and tested.**

The network was tested using:

```bash
pingall
```

and achieved:

```text
0% dropped
```

This confirms that the basic Mininet + OVS + Ryu forwarding setup is working.

---

# 5. Current Experimental Network

The current topology contains:

```text
Hosts:
H1 = URLLC source
H2 = eMBB source
H3 = Best-Effort source

H4 = URLLC destination
H5 = eMBB destination
H6 = Best-Effort destination

Switches:
S1
S2

Controller:
Ryu

Protocol:
OpenFlow 1.3
```

Traffic mapping:

```text
H1 ───────── H4     URLLC
H2 ───────── H5     eMBB
H3 ───────── H6     Best Effort
```

The S1-S2 link is configured as:

```text
Bandwidth = 10 Mbps
Delay     = 5 ms
```

This bottleneck allows us to study congestion and its effect on critical traffic.

---

# 6. Initial Congestion Experiment Already Completed

We tested eMBB traffic using iperf3.

Example:

```bash
h5 iperf3 -s -D
h2 iperf3 -c 10.0.0.5 -t 20 -b 9M
```

The eMBB traffic achieved approximately:

```text
9 Mbps
```

We then ran URLLC traffic simultaneously:

```bash
h4 iperf3 -s -D
h1 ping -i 0.1 -c 200 h4 &
h2 iperf3 -c 10.0.0.5 -t 20 -b 9M
```

The experiment demonstrated that heavy eMBB traffic can significantly increase URLLC latency.

Observed experimental result:

```text
URLLC packet loss   = 0%
Average latency     ≈ 29.88 ms
Maximum latency     ≈ 122.44 ms
Minimum latency     ≈ 10.09 ms
```

These values are from our Mininet experiment and are **experimental results, not universal network standards**.

Our project currently uses **15 ms as an experimental URLLC SLA boundary** for evaluating the safety mechanism.

Therefore:

```text
Latency ≤ 15 ms
      ↓
Safe region

Latency > 15 ms
      ↓
SLA risk / violation
```

This experiment establishes the baseline problem that the AI-driven dynamic slicing system is intended to address.

---

# 7. Planned AI Component — SRA-LinUCB

The project uses:

**Security- and Risk-Aware LinUCB (SRA-LinUCB)**

It is a lightweight contextual-bandit approach.

The AI observes the current network context and selects a candidate resource-allocation action.

Example context:

```text
x_t = [
    eMBB throughput,
    packet loss,
    URLLC latency,
    queue occupancy,
    traffic rate,
    latency trend,
    security risk,
    security overhead
]
```

Example actions:

```text
A1 → Increase eMBB allocation
A2 → Maintain allocation
A3 → Decrease eMBB allocation
```

Security level can later be included as part of the action:

```text
Low
Medium
High
```

The important design principle is:

```text
AI proposes an action
        ↓
Safety layer validates it
        ↓
Only safe actions are executed
```

The AI should not directly bypass the safety layer.

---

# 8. Planned SLA & Security Guardrail

The safety layer checks whether an AI-generated action could violate important constraints.

Example checks:

```text
Bandwidth constraint
        +
URLLC latency constraint
        +
Packet-loss constraint
        +
Security-risk constraint
        +
Security-overhead constraint
```

Decision:

```text
Candidate AI Action
        ↓
   Safety Check
     /       \
  SAFE      UNSAFE
   ↓          ↓
Execute    Reject/Repair
```

This provides explicit protection instead of relying only on an AI reward function.

---

# 9. Planned Security Component

The security component will study the trade-off between network protection and network performance.

A practical candidate is an encrypted tunnel such as WireGuard.

The experiments will compare:

```text
Security OFF
     vs
Security ON
```

Measurements can include:

- latency
- throughput
- packet loss
- encryption/tunnel overhead
- CPU/processing overhead where measurable

The purpose is not to invent a new encryption method, but to measure how security protection affects network performance and incorporate that effect into safe resource allocation.

---

# 10. Planned Feedback & Learning

The final system will operate as a closed loop:

```text
Observe
   ↓
Decide
   ↓
Validate
   ↓
Act
   ↓
Measure
   ↓
Learn
   ↓
Repeat
```

The actual network performance after an action will be used to calculate a reward and update the LinUCB model.

---

# 11. Planned Evaluation

The final evaluation will compare three approaches:

### A. Static Slicing

Fixed resource allocation.

```text
Traffic changes
     ↓
Allocation remains fixed
```

### B. Dynamic AI Without Safety

```text
Telemetry
   ↓
LinUCB
   ↓
Action
   ↓
Network
```

This demonstrates the benefit of AI adaptation but also allows us to study the risk of unsafe decisions.

### C. Proposed Safe Dynamic Slicing

```text
Telemetry
   ↓
SRA-LinUCB
   ↓
SLA/Security Guardrail
   ↓
Safe Action
   ↓
Network
```

Main evaluation metrics:

- URLLC latency
- eMBB throughput
- packet loss
- resource utilization
- SLA violation count/duration
- recovery time
- security overhead
- processing overhead where measurable

---

# 12. Current Project Status

## Completed

```text
✓ Project repository created
✓ WSL2 development environment
✓ VS Code connected to WSL
✓ Python/Ryu environment configured
✓ Mininet installed
✓ Open vSwitch installed
✓ iperf3 installed
✓ Mininet topology implemented
✓ OpenFlow 1.3 configured
✓ Ryu controller implemented
✓ Basic MAC-learning forwarding implemented
✓ Three traffic classes configured
✓ 10 Mbps bottleneck created
✓ eMBB throughput experiment completed
✓ URLLC + eMBB congestion experiment completed
✓ Preliminary latency/throughput measurements obtained
```

## In Progress / Next

```text
→ Automated Network Telemetry
→ CSV telemetry storage
→ Context / feature extraction
→ SRA-LinUCB implementation
→ SLA & Security Guardrail
→ Security experiment
→ Feedback and learning loop
→ Static vs Dynamic vs Safe-Dynamic evaluation
→ Graphs and final analysis
→ Dashboard / final integration
```

---

# 13. Development Environment

The project is developed on **Windows using WSL2 Ubuntu**.

VS Code is connected to the WSL environment.

Recommended setup:

```text
Windows
   ↓
WSL2
   ↓
Ubuntu
   ↓
VS Code
   ↓
AI-Safe-Dynamic-Slicing/
```

This is important because Mininet and Open vSwitch are Linux-based tools.

---

# 14. Opening the Project in VS Code

From the WSL terminal:

```bash
cd ~/AI-Safe-Dynamic-Slicing
code .
```

VS Code should open the project using the WSL environment.

The terminal inside VS Code should show a Linux/WSL shell.

---

# 15. Python Environment

Ryu 4.34 has compatibility problems with newer Python versions, so this project uses a dedicated Python environment:

```text
Environment: ryu-3.9
Python:      3.9.18
Ryu:         4.34
```

Activate it:

```bash
pyenv activate ryu-3.9
```

Check:

```bash
python --version
```

Expected:

```text
Python 3.9.18
```

Check Ryu:

```bash
ryu-manager --version
```

Expected:

```text
ryu-manager 4.34
```

---

# 16. Required Software

Install/configure the following:

| Tool | Purpose |
|---|---|
| Python 3.9 | Ryu-compatible environment |
| Ryu 4.34 | SDN controller |
| Mininet 2.3.0 | Network emulation |
| Open vSwitch 3.3.9 | SDN data plane |
| OpenFlow 1.3 | Controller-switch communication |
| iperf3 3.16 | Traffic generation |
| Git | Version control |
| VS Code | Development |
| WSL2 Ubuntu | Linux environment |

Additional Python packages can be added as the AI/telemetry modules are implemented.

---

# 17. Verify the Installation

Run:

```bash
python --version
```

```bash
ryu-manager --version
```

```bash
sudo mn --version
```

```bash
sudo ovs-vsctl --version
```

```bash
iperf3 --version
```

Expected versions used in the current setup:

```text
Python     3.9.18
Ryu        4.34
Mininet    2.3.0
OVS        3.3.9
iperf3     3.16
```

---

# 18. Project Structure

Current/target repository structure:

```text
AI-Safe-Dynamic-Slicing/
│
├── README.md
├── requirements.txt
│
├── config/
│
├── topology/
│   └── topology.py
│
├── controller/
│   └── ryu_controller.py
│
├── telemetry/
│   └── monitor.py              # planned
│
├── slicing/
│   └── slice_config.py         # planned/under development
│
├── ai/
│   └── ...                     # planned
│
├── security/
│   └── ...                     # planned
│
├── guardrail/
│   └── ...                     # planned
│
├── experiments/
│   └── ...                     # planned
│
├── data/
│   └── telemetry.csv           # generated later
│
└── results/
    └── ...                     # generated later
```

Do not assume a module is complete just because its folder exists. The current implemented core is the topology and Ryu controller; the remaining modules will be developed incrementally.

---

# 19. Running the Current System

## Terminal 1 — Start Ryu

Activate the environment:

```bash
pyenv activate ryu-3.9
```

From the project directory:

```bash
cd ~/AI-Safe-Dynamic-Slicing
```

Start the controller:

```bash
ryu-manager controller/ryu_controller.py
```

Keep this terminal running.

---

## Terminal 2 — Start Mininet

Open another WSL terminal.

Activate the environment:

```bash
pyenv activate ryu-3.9
```

Go to the project:

```bash
cd ~/AI-Safe-Dynamic-Slicing
```

Clean old Mininet state if required:

```bash
sudo mn -c
```

Start the topology:

```bash
sudo "$(pyenv which python)" topology/topology.py
```

You should reach:

```text
mininet>
```

---

# 20. Basic Network Test

At the Mininet prompt:

```bash
pingall
```

Expected:

```text
0% dropped
```

Test individual traffic classes:

```bash
h1 ping -c 3 h4
```

```bash
h2 ping -c 3 h5
```

```bash
h3 ping -c 3 h6
```

---

# 21. eMBB Throughput Test

Start the server:

```bash
h5 iperf3 -s -D
```

Run the eMBB client:

```bash
h2 iperf3 -c 10.0.0.5 -t 20 -b 9M
```

The current bottleneck should allow approximately 9 Mbps.

---

# 22. URLLC + eMBB Congestion Test

Start the URLLC server:

```bash
h4 iperf3 -s -D
```

Start URLLC ping:

```bash
h1 ping -i 0.1 -c 200 h4 &
```

Then, as a separate Mininet command, start eMBB traffic:

```bash
h2 iperf3 -c 10.0.0.5 -t 20 -b 9M
```

This creates the controlled congestion experiment.

---

# 23. Important Mininet Cleanup

If Mininet reports errors such as:

```text
RTNETLINK answers: File exists
```

exit/stop the current Mininet session and run from the normal WSL terminal:

```bash
sudo mn -c
```

Then start the topology again.

Do not run `sudo mn -c` inside the `mininet>` prompt.

---

# 24. Team Development Rule

Before modifying another person's module:

1. Pull the latest code.
2. Understand the module interface.
3. Do not overwrite working code unnecessarily.
4. Keep module inputs/outputs clearly defined.
5. Commit changes with meaningful messages.
6. Test the module before pushing.

Example:

```bash
git pull
```

```bash
git add .
```

```bash
git commit -m "Implement telemetry collection"
```

```bash
git push
```

---

# 25. Overall Development Roadmap

```text
PHASE 1
SDN Network + Slicing
        ↓
PHASE 2
Ryu SDN Control
        ↓
PHASE 3
Network Telemetry
        ↓
PHASE 4
Context / Feature Extraction
        ↓
PHASE 5
SRA-LinUCB AI
        ↓
PHASE 6
SLA & Security Guardrail
        ↓
PHASE 7
Security Integration
        ↓
PHASE 8
Feedback & Learning
        ↓
PHASE 9
Static vs Dynamic vs Safe Dynamic
        ↓
PHASE 10
Graphs / Analysis / Dashboard
        ↓
FINAL SYSTEM
```

---

# 26. What Has Been Proven So Far

The current implementation has already demonstrated:

```text
Windows + WSL2
      ↓
Mininet
      ↓
OVS
      ↓
OpenFlow 1.3
      ↓
Ryu Controller
      ↓
Three Traffic Classes
      ↓
10 Mbps Bottleneck
      ↓
eMBB Traffic
      ↓
URLLC Traffic
      ↓
Congestion
      ↓
Significant URLLC Latency Increase
```

This is the **baseline foundation** for the AI-driven safe dynamic network slicing system.

The next development stage is to replace manual observation with an automated telemetry pipeline and then connect that telemetry to the SRA-LinUCB decision and safety layers.
