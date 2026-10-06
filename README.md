# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

## 1. Project Structure

```text
AI-Safe-Dynamic-Slicing/
│
├── README.md
├── requirements.txt
│
├── config/
├── topology/
│   └── topology.py
├── controller/
│   └── ryu_controller.py
├── telemetry/
├── slicing/
├── ai/
├── security/
├── guardrail/
├── experiments/
├── data/
└── results/
```

The folders will be developed module-by-module. Do not create or modify another member's module until the work is divided.

---

## 2. Project Modules

The complete project contains **9 modules**:

| No. | Module | Purpose | Current Status |
|---|---|---|---|
| 01 | **SDN Network & Slicing** | Mininet + OVS topology and traffic slices | ✅ Implemented |
| 02 | **Network Telemetry** | Collect latency, throughput, loss, queue/utilization | ⏳ Next |
| 03 | **Context & Feature** | Convert telemetry into AI input/context | ⏳ Pending |
| 04 | **SRA-LinUCB AI** | Select dynamic resource-allocation actions | ⏳ Pending |
| 05 | **Security** | Security protection and security overhead measurement | ⏳ Pending |
| 06 | **SLA & Security Guardrail** | Validate AI actions before execution | ⏳ Pending |
| 07 | **SDN Control** | Ryu + OpenFlow control of OVS | ✅ Implemented |
| 08 | **Feedback & Learning** | Use network results to update the AI | ⏳ Pending |
| 09 | **Evaluation & Comparison** | Compare static, dynamic and safe-dynamic approaches | ⏳ Pending |

### Current project flow

```text
Network / Slices
       ↓
   Telemetry
       ↓
Context & Features
       ↓
  SRA-LinUCB
       ↓
SLA/Security Guardrail
       ↓
  Ryu Controller
       ↓
     OVS
       ↓
     Network
       ↓
Performance Feedback
       └────────→ AI
```

---

## 3. What Is Already Implemented

### Module 01 — SDN Network & Slicing

Current network:

```text
H1 ─┐
H2 ─┤
H3 ─┤
    S1 ═════════ S2
               ├─ H4
               ├─ H5
               └─ H6
```

Traffic classes:

```text
H1 ↔ H4 → URLLC
H2 ↔ H5 → eMBB
H3 ↔ H6 → Best Effort
```

The S1-S2 link is configured as:

```text
Bandwidth = 10 Mbps
Delay     = 5 ms
```

### Module 07 — SDN Control

Current controller:

```text
Ryu
  ↓
OpenFlow 1.3
  ↓
Open vSwitch
```

The Ryu controller currently performs basic MAC-learning forwarding.

Basic connectivity has been tested successfully using:

```bash
pingall
```

with:

```text
0% dropped
```

A preliminary congestion experiment has also been completed to verify that heavy eMBB traffic can increase URLLC latency.

---

# 4. Development Environment

We use:

```text
Windows
   ↓
WSL2 Ubuntu
   ↓
VS Code
   ↓
AI-Safe-Dynamic-Slicing
```

**Important:** Mininet, OVS and Ryu should be run inside the WSL Ubuntu environment.

---

# 5. Open the Project in VS Code
create your own branch inside main branch and push relate code to your bracnch .
 

Open WSL terminal and run:

```bash
cd ~/AI-Safe-Dynamic-Slicing
```

Then:

```bash
code .
```

VS Code should open the project in the WSL environment.

---

# 6. Activate Python Environment

This project uses a separate Python environment because the current Ryu setup uses Python 3.9.

```bash
pyenv activate ryu-3.9
```

Verify:

```bash
python --version
```

Expected:

```text
Python 3.9.18
```

Verify Ryu:

```bash
ryu-manager --version
```

Expected:

```text
Ryu 4.34
```

---

# 7. Required Software

The current setup uses:

```text
Python 3.9.18
Ryu 4.34
Mininet 2.3.0
Open vSwitch 3.3.9
OpenFlow 1.3
iperf3 3.16
Git
VS Code
WSL2 Ubuntu
```

Verify the main tools:

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

---

# 8. Project Dependencies

Once the project `requirements.txt` is updated with the dependencies for the upcoming modules, install them using:

```bash
python -m pip install -r requirements.txt
```

Do not install random packages unless they are required by the module being developed.

---

# 9. Run the Current Implemented System

## Terminal 1 — Ryu Controller

```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
ryu-manager controller/ryu_controller.py
```

Keep this terminal running.

## Terminal 2 — Mininet

Open another WSL terminal:

```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
```

If an old Mininet instance exists:

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

# 10. Test the Current Network

Inside Mininet:

```bash
pingall
```

Expected:

```text
0% dropped
```

Test the three traffic paths:

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

# 11. Git Workflow

Before starting work:

```bash
git pull
```

After completing and testing your assigned module:

```bash
git add .
git commit -m "Describe your change"
git push
```

Always pull before starting work and push only tested changes.

---

## Important

This README only explains the **project structure, modules, current implementation, and common setup**.

The detailed implementation tasks will be assigned separately to the three team members.
