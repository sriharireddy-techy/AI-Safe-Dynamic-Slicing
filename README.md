# AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

## Project Overview

This project develops an AI-driven SDN network slicing framework that dynamically allocates network resources while protecting critical traffic from SLA violations.

The system uses a lightweight contextual-bandit approach, SRA-LinUCB, together with SLA and security guardrails.

## Current Implementation

- Mininet-based network emulation
- Open vSwitch data plane
- Ryu SDN controller
- OpenFlow 1.3
- URLLC, eMBB and Best-Effort traffic classes
- iperf3 traffic generation
- Basic SDN forwarding using MAC learning

## Architecture

Network Traffic
        ↓
Mininet + Open vSwitch
        ↓
Ryu Controller
        ↓
Telemetry
        ↓
SRA-LinUCB
        ↓
SLA + Security Guardrail
        ↓
Dynamic Network Slicing

## Technology Stack

- Python
- Mininet
- Open vSwitch
- Ryu
- OpenFlow 1.3
- iperf3
- NumPy
- Pandas
- Matplotlib

## Project Status

### Completed
- SDN environment setup
- Mininet topology
- Open vSwitch integration
- Ryu controller integration
- OpenFlow 1.3
- Basic forwarding
- URLLC/eMBB/Best-Effort traffic classes

### In Progress
- Network telemetry
- Static slicing baseline
- Dynamic resource allocation

### Planned
- SRA-LinUCB
- SLA safety guardrail
- Security-aware resource allocation
- Dynamic slicing evaluation
- Performance comparison