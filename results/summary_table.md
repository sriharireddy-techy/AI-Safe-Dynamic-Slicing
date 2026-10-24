# Simulation Benchmark Performance Summary Table

> **Note:** Results are derived from the trace-driven FIFO queuing simulation model (10.0 Mbps bottleneck).

| Metric | Static Slicing (Fixed) | Dynamic Slicing (Unsafe LinUCB) | Proposed System (AI-Safe) |
| :--- | :--- | :--- | :--- |
| **URLLC Mean Simulated RTT** | 10.15 ms | 11.15 ms | **11.07 ms** |
| **URLLC 99th-Percentile RTT** | 10.15 ms | **26.35 ms** *(breach)* | **12.51 ms** *(safe)* |
| **eMBB Mean Throughput** | 4.02 Mbps | 4.24 Mbps | **4.19 Mbps** |
| **eMBB Peak Throughput** | 5.00 Mbps | 8.50 Mbps | **6.50 Mbps** |
| **URLLC Packet Loss** | 0.0% | 0.0% | **0.0%** |
| **SLA Violations (Count / %)** | 0 (0.0%) | **1 (5.0%)** | **0 (0.0%)** |
| **Congestion Recovery Time** | 0.0 s | 1.0 s | **0.0 s** |
| **Guardrail Repaired Actions** | 0 (N/A) | 0 (Disabled) | **3 (Active)** |
| **Security Overhead Mode** | N/A | Ignored | Simulated (1.2 ms) |
| **Deterministic Safety Guard** | No | No | **Yes (Module 6)** |
