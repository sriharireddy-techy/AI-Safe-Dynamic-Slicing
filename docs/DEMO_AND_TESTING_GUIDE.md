# Demonstration, Testing & Troubleshooting Guide
## AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

---

## Table of Contents
1. [Master Test Evidence Table (114/114 Tests)](#1-master-test-evidence-table-114114-tests)
2. [Quick Verification Commands (Windows / Linux)](#2-quick-verification-commands-windows--linux)
3. [Step-by-Step Live Demonstration Script](#3-step-by-step-live-demonstration-script)
4. [Live Mininet / Ryu Testbed Multi-Terminal Setup](#4-live-mininet--ryu-testbed-multi-terminal-setup)
5. [Troubleshooting & Failure Diagnostics](#5-troubleshooting--failure-diagnostics)

---

## 1. Master Test Evidence Table (114/114 Tests)

All 114 tests are executed via `pytest`:

```text
============================= 114 passed in 3.56s =============================
```

| Test Suite File | Modules Covered | Tests | Expected Output | What It Proves | What It Does NOT Prove |
|---|---|:---:|---|---|---|
| [`telemetry/test_telemetry.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/telemetry/test_telemetry.py) | Module 02 (Telemetry) | 15 | `15 passed` | Parses ping output, loss %, interface bytes, tc queue backlog, CSV serialization, sentinel handling. | Does not prove Mininet is running on the host OS during test execution. |
| [`ai/test_context_builder.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_context_builder.py) | Module 03 (Context) | 17 | `17 passed` | Bounded normalization $[0, 1]$, latency velocity trend, sentinel $-1.0 \rightarrow 1.0$ mapping, ceiling clipping. | Does not evaluate bandit decisions. |
| [`ai/test_linucb.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_linucb.py) | Module 04 (SRA-LinUCB) | 11 | `11 passed` | Online ridge regression updates, linear solve via `np.linalg.solve`, SRA risk dampening under stress. | Does not verify switch flow installation. |
| [`ai/test_integration.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/ai/test_integration.py) | M02 $\rightarrow$ M03 $\rightarrow$ M04 | 6 | `6 passed` | End-to-end dataflow from raw telemetry to 6D context to candidate action across healthy/congested transitions. | Does not include guardrail validation. |
| [`tests/test_security.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_security.py) | Module 05 (Security) | 13 | `13 passed` | `SecurityState` validation, crypto delay calculation, `WireGuardAdapter` fallback query, config generation. | Does not create actual Linux kernel WireGuard tunnels. |
| [`tests/test_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_guardrail.py) | Module 06 (Guardrail) | 14 | `14 passed` | Enforces all 6 gates: 10M capacity, 3M URLLC floor, 15ms latency, 1% loss, 0.70 risk, deterministic repair scaling. | Does not enforce rates on physical switches. |
| [`tests/test_pipeline_guardrail.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_pipeline_guardrail.py) | M2 $\rightarrow$ M3 $\rightarrow$ M4 $\rightarrow$ M6 | 7 | `7 passed` | End-to-end closed loop across 7 operational scenarios (healthy, breach, overload, repair, edge cases). | Does not run real traffic generation. |
| [`tests/test_slice_config.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_slice_config.py) | Slicing Config | 5 | `5 passed` | Slice bandwidth floors, capacity ceiling constraints, default validation. | Does not verify data-plane queues. |
| [`feedback/test_reward.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_reward.py) | Module 08 (Reward Engine) | 8 | `8 passed` | Multi-objective reward bounds, quadratic SLA barrier penalty, conditional security overhead inclusion. | Does not update model parameters. |
| [`feedback/test_learner.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_learner.py) | Module 08 (Feedback Learner) | 4 | `4 passed` | Causal arm attribution: updates executed arms, skips rejected arms, convergence behavior. | Does not run inside live Mininet. |
| [`feedback/test_feedback.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/feedback/test_feedback.py) | Module 08 (Package Tests) | 2 | `2 passed` | Package exports and legacy API wrapper sanity. | Does not test complex scenarios. |
| [`tests/test_feedback.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_feedback.py) | Module 08 Integration | 5 | `5 passed` | Safe attribution on rejected/repaired actions, sentinel -1.0 handling, diagnostics breakdown. | Does not run physical switch flows. |
| [`tests/test_experiments.py`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/tests/test_experiments.py) | Module 09 (Experiments) | 7 | `7 passed` | Fluid FIFO queuing physics, buffer overflow, real guardrail intervention, 24-column CSV schema validation. | Does not execute live Mininet traffic. |
| **Total** | **Full Regression Suite** | **114** | **114 passed** | **Complete algorithmic, mathematical, and safety gate correctness.** | **Hardware/physical switch dynamics.** |

---

## 2. Quick Verification Commands (Windows / Linux)

### 1. Run Full 114-Test Suite
```bash
pytest
```

### 2. Run Module 09 Benchmarks (Generates CSVs & Plots)
```bash
python experiments/run_experiments.py
```
*(Executes all 3 experimental baselines, saves CSVs to `results/`, generates plots, and prints summary table).*

### 3. Display Benchmark Table Instantly
```bash
python experiments/run_experiments.py --table-only
```

### 4. Run Interactive 5-Step Pipeline Walkthrough
```bash
python ai/test_pipeline_live.py
```

---

## 3. Step-by-Step Live Demonstration Script

Follow this sequence during your faculty demonstration:

### Step 1: Run Full Test Suite (Proof of Engineering Integrity)
- **Command:** `pytest`
- **What to say:**
  > "We begin by executing our automated regression suite. All 114 unit and integration tests pass with 100% success in under 4 seconds, verifying mathematical normalization, SRA-LinUCB ridge regression, the 6 guardrail gates, deterministic repair, and causal feedback attribution."

### Step 2: Run the 5-Step Live Pipeline Walkthrough
- **Command:** `python ai/test_pipeline_live.py`
- **What to say:**
  > "This walkthrough traces the live dataflow through consecutive control cycles:
  > - In Step 1, under healthy network conditions (10.4 ms latency, 0 pkts in queue), the context vector is extracted and the AI evaluates all three arms.
  > - In Step 2 and 3, as latency surges to 36.5 ms with queue backlog rising to 28 packets, the context risk indicator $R(\mathbf{x}_t)$ surges to 0.66. The SRA penalty heavily suppresses Action 2 (INCREASE_EMBB), naturally steering the AI to select Action 0 (DECREASE_EMBB)."

### Step 3: Run the Module 09 Benchmark Evaluation
- **Command:** `python experiments/run_experiments.py`
- **What to say:**
  > "Here we execute our comparative benchmark under a standardized 20-step dynamic workload. The runner evaluates Static Fixed Slicing, Unsafe LinUCB without safety, and our Proposed AI-Safe System.
  > As seen in the output table:
  > - Static slicing achieves zero SLA breaches but artificially caps eMBB throughput at 5.0 Mbps during the surge.
  > - Unsafe AI explores aggressively, allocating 9.0 Mbps to eMBB at Step 11, causing queue accumulation (16.67 pkts) and spiking latency to 30.15 ms—a direct breach of the 15 ms SLA.
  > - Our Proposed System activates Module 06 Guardrail: it intercepts the overload, repairs the allocation to cap eMBB at 6.5 Mbps, protects the 3.0 Mbps URLLC reservation, and preserves a safe peak latency of 12.51 ms with zero SLA violations."

### Step 4: Show Generated Artifacts in `results/`
- Open and display:
  - [`results/comparison.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/comparison.png) (Bar chart highlighting zero SLA violations).
  - [`results/latency.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/latency.png) (3-panel time series showing latency vs. 15 ms red dashed line).
  - [`results/throughput.png`](file:///C:/Users/Gadi%20Srihari%20Reddy/AI-Safe-Dynamic-Slicing/results/throughput.png) (eMBB bandwidth adaptation timeline).

---

## 4. Live Mininet / Ryu Testbed Multi-Terminal Setup

*(Requires Ubuntu Linux 22.04 LTS or Windows WSL2 with Python 3.9)*

### Terminal 1: Start Ryu SDN Controller (Control Plane)
```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
ryu-manager controller/ryu_controller.py --verbose
```
*Expected Output:* `Switch connected: 1`, `Switch connected: 2`.

### Terminal 2: Start Mininet Network (Data Plane)
```bash
cd ~/AI-Safe-Dynamic-Slicing
pyenv activate ryu-3.9
sudo mn -c   # Clean up residual state
sudo "$(pyenv which python)" topology/topology.py
```
*Expected Output:* `mininet>` prompt with 2 switches and 6 hosts.

### Terminal 3: Traffic Generation in Mininet CLI
In Terminal 2 at the `mininet>` prompt:
```text
# 1. Verify complete network connectivity
mininet> pingall

# 2. Launch iperf3 background servers on sink hosts H4 and H5
mininet> h4 iperf3 -s -D
mininet> h5 iperf3 -s -D

# 3. Inject heavy eMBB traffic surge (H2 -> H5 at 8.5 Mbps)
mininet> h2 iperf3 -c 10.0.0.5 -u -b 8.5M -t 60 &

# 4. Measure live URLLC latency (H1 -> H4)
mininet> h1 ping -i 0.2 -c 50 10.0.0.4
```

### Terminal 4: Start Network Telemetry Monitor
```bash
cd ~/AI-Safe-Dynamic-Slicing
sudo python telemetry/monitor.py
```
*Expected Output:* Continuous streaming output logging to `data/telemetry.csv`.

---

## 5. Troubleshooting & Failure Diagnostics

| Symptom / Error | Root Cause | Solution |
|---|---|---|
| `[Telemetry] Could not find Mininet H1` | Mininet is not running, or H1 was destroyed. | Ensure Mininet CLI is active in Terminal 2 before starting telemetry. |
| `Latency: -1.0 ms, Loss: 100.0%` | Active ping probe timed out or destination is unreachable. | Normal behavior under extreme congestion; verify with `mininet> pingall`. |
| `Address already in use: 6633` | An earlier Ryu or OpenFlow controller instance is still running in the background. | Run `sudo fuser -k 6633/tcp` or `sudo killall ryu-manager`. |
| `Cannot find switch s1-eth4` | Mininet topology was stopped or not started with root privileges. | Run `sudo mn -c` and restart `sudo python topology/topology.py`. |
| `Permission denied on /sys/class/net` | Reading interface statistics requires standard OS read access. | Run the script with appropriate permissions. |
| `Matplotlib deprecation warning` | Third-party matplotlib font warning on Python 3.9. | Harmless warning; run `pytest --disable-warnings` to suppress. |
