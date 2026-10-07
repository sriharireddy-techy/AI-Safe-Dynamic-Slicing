"""
Network Telemetry Module (Module 2)
===================================
AI-Driven Safe Dynamic Network Slicing for SLA-Preserving SDN Networks

This module provides automated, non-invasive collection of network telemetry:
1. Active latency and packet loss probing (URLLC H1 -> H4).
2. Passive Linux/OVS bottleneck interface byte statistics.
3. Queue backlog statistics via Linux Traffic Control (tc).
4. Pure rate/throughput derivation decoupled from I/O.
5. Thread-safe/robust CSV export for AI consumption.

Design Principle:
- Separation of collection (I/O) from calculation (Pure Functions).
- Graceful degradation: Missing network or counters returns safe sentinels
  without crashing the control loop.
"""

import os
import re
import csv
import time
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional, Tuple, Dict, Any


@dataclass
class TelemetryRecord:
    """
    Structured telemetry sample representing the network state at a discrete point in time.
    
    Attributes:
        timestamp: Unix epoch timestamp in seconds.
        interface: Name of the switch bottleneck interface (e.g., 's1-eth4').
        urllc_latency_ms: Measured round-trip latency in milliseconds.
                          Sentinel -1.0 indicates 100% loss or unreachable target.
        urllc_packet_loss: Percentage of lost packets (0.0 to 100.0).
        bottleneck_rx_bytes: Cumulative bytes received on the bottleneck interface.
        bottleneck_tx_bytes: Cumulative bytes transmitted on the bottleneck interface.
        throughput_mbps: Egress transmission rate over the sampling interval (Mbps).
        traffic_rate_mbps: Total bidirectional rate (RX + TX) over the interval (Mbps).
        queue_occupancy: Number of packets currently backlogged in the egress queue.
        embb_throughput: Placeholder for high-bandwidth slice rate (Mbps).
        embb_packet_loss: Placeholder for high-bandwidth slice drop rate (%).
        security_overhead: Placeholder for encryption/security processing delay (ms).
    """
    timestamp: float
    interface: str
    urllc_latency_ms: float
    urllc_packet_loss: float
    bottleneck_rx_bytes: int
    bottleneck_tx_bytes: int
    throughput_mbps: float
    traffic_rate_mbps: float
    queue_occupancy: int
    embb_throughput: float = 0.0
    embb_packet_loss: float = 0.0
    security_overhead: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert the dataclass instance to a serializable dictionary."""
        return asdict(self)


# ============================================================================
# PURE CALCULATION & PARSING FUNCTIONS (Decoupled from OS/Network I/O)
# ============================================================================

def parse_ping_output(ping_stdout: str) -> Tuple[float, float]:
    """
    Parses standard Linux/Unix ping output to extract average latency and packet loss.
    
    Args:
        ping_stdout: Raw string output from `ping -c <count> <target>`.
        
    Returns:
        Tuple of (average_latency_ms, packet_loss_percent):
        - If ping succeeds: (avg_rtt, loss_pct)
        - If 100% loss/unreachable: (-1.0, 100.0)
        - If output is malformed: (-1.0, 100.0)
    """
    if not ping_stdout or not isinstance(ping_stdout, str):
        # Gracefully handle empty or invalid input without raising exceptions
        return -1.0, 100.0

    # 1. Parse packet loss percentage
    # Example pattern: "1 packets transmitted, 1 received, 0% packet loss"
    loss_pattern = r'(\d+(?:\.\d+)?)%\s+packet\s+loss'
    loss_match = re.search(loss_pattern, ping_stdout)
    packet_loss = float(loss_match.group(1)) if loss_match else 100.0

    # If all packets were dropped, latency cannot be computed; return sentinel -1.0
    if packet_loss >= 100.0:
        return -1.0, 100.0

    # 2. Parse round-trip average latency
    # Example pattern: "rtt min/avg/max/mdev = 10.091/29.882/122.441/15.221 ms"
    rtt_pattern = r'rtt\s+min/avg/max/mdev\s*=\s*[\d\.]+/([\d\.]+)/[\d\.]+/[\d\.]+\s*ms'
    rtt_match = re.search(rtt_pattern, ping_stdout)
    
    if rtt_match:
        avg_latency = float(rtt_match.group(1))
        return avg_latency, packet_loss

    # Fallback pattern for alternative ping implementations
    # Example: "round-trip min/avg/max = 10.1/29.8/122.4 ms"
    alt_rtt_pattern = r'round-trip\s+min/avg/max(?:/stddev)?\s*=\s*[\d\.]+/([\d\.]+)/'
    alt_match = re.search(alt_rtt_pattern, ping_stdout)
    if alt_match:
        return float(alt_match.group(1)), packet_loss

    # If packets were received but RTT line was not matched, return sentinel
    return -1.0, packet_loss


def parse_tc_queue_output(tc_stdout: str) -> int:
    """
    Parses output of `tc -s qdisc show dev <iface>` to extract current queue backlog.
    
    Example tc output:
        qdisc htb 1: root refcnt 2 r2q 10 default 0 direct_packets_stat 0
         Sent 1048576 bytes 1024 pkt (dropped 0, overlimits 0 requeues 0)
         backlog 4500b 3p requeues 0
         
    Args:
        tc_stdout: Standard output string from the tc command.
        
    Returns:
        Integer backlog in packets (e.g., 3). If no backlog or error, returns 0.
    """
    if not tc_stdout or not isinstance(tc_stdout, str):
        return 0

    # Match backlog string: "backlog <bytes>b <packets>p"
    # Group 2 extracts the packet count in the queue
    backlog_pattern = r'backlog\s+\d+b\s+(\d+)p'
    match = re.search(backlog_pattern, tc_stdout)
    
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return 0
            
    return 0

def calculate_rates(
    prev_tx: int,
    curr_tx: int,
    prev_rx: int,
    curr_rx: int,
    delta_time: float
) -> Tuple[float, float]:
    """
    Computes transmission throughput and total traffic rate in Megabits per second (Mbps).
    
    Formula:
        Throughput (Mbps) = (Delta TX Bytes * 8 bits/byte) / (Delta Time * 1,000,000 bits/Mb)
        Traffic Rate (Mbps) = ((Delta TX + Delta RX) * 8) / (Delta Time * 1,000,000)
        
    Args:
        prev_tx: Previous transmitted bytes counter.
        curr_tx: Current transmitted bytes counter.
        prev_rx: Previous received bytes counter.
        curr_rx: Current received bytes counter.
        delta_time: Time elapsed in seconds between samples.
        
    Returns:
        Tuple of (throughput_mbps, traffic_rate_mbps).
        Safely returns (0.0, 0.0) if elapsed time is zero or negative,
        or if counters reset.
    """
    if delta_time <= 0.0:
        # Prevent division by zero or negative time intervals
        return 0.0, 0.0

    # Handle counter wrapping or interface reset (curr < prev)
    delta_tx = curr_tx - prev_tx if curr_tx >= prev_tx else 0
    delta_rx = curr_rx - prev_rx if curr_rx >= prev_rx else 0

    # Conversion factor: bytes to bits (x8), divided by bits per Megabit (1e6)
    throughput_mbps = (delta_tx * 8.0) / (delta_time * 1_000_000.0)
    traffic_rate_mbps = ((delta_tx + delta_rx) * 8.0) / (delta_time * 1_000_000.0)

    # Round to 4 decimal places for clean representation and numeric stability
    return round(throughput_mbps, 4), round(traffic_rate_mbps, 4)


# ============================================================================
# DATA LOGGING (CSV Storage)
# ============================================================================

def log_to_csv(record: TelemetryRecord, csv_path: str) -> None:
    """
    Appends a telemetry record to the specified CSV file.
    Creates parent directories and CSV header automatically if the file does not exist.
    
    Args:
        record: TelemetryRecord instance to persist.
        csv_path: Destination path for the CSV log.
    """
    # Ensure target directory exists
    dir_name = os.path.dirname(csv_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    file_exists = os.path.isfile(csv_path) and os.path.getsize(csv_path) > 0

    fieldnames = list(record.to_dict().keys())

    with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            # Write header only once when file is created
            writer.writeheader()
        writer.writerow(record.to_dict())


# ============================================================================
# NETWORK TELEMETRY COLLECTOR CLASS (I/O & State Management)
# ============================================================================

class NetworkTelemetryCollector:
    """
    Collects real-time telemetry from Linux/Mininet network interfaces and hosts.
    
    Stateful tracking:
        Maintains previous timestamp and byte counters to compute differential rates.
    """

    def __init__(
        self,
        interface: str = "s1-eth4",
        h1_ip: str = "10.0.0.1",
        h4_ip: str = "10.0.0.4",
        csv_path: Optional[str] = None
    ):
        """
        Initialize the collector.
        
        Args:
            interface: Name of the bottleneck network interface to monitor (e.g., s1-eth4).
            h1_ip: IP address of URLLC source host H1.
            h4_ip: IP address of URLLC destination host H4.
            csv_path: Optional path to automatically persist samples to CSV.
        """
        self.interface = interface
        self.h1_ip = h1_ip
        self.h4_ip = h4_ip
        self.csv_path = csv_path

        # State tracking for rate derivation
        self.prev_timestamp: Optional[float] = None
        self.prev_rx_bytes: Optional[int] = None
        self.prev_tx_bytes: Optional[int] = None

    def read_port_counters(self) -> Tuple[int, int]:
        """
        Reads raw RX and TX byte counters directly from Linux sysfs.
        
        Returns:
            Tuple of (rx_bytes, tx_bytes). Returns (0, 0) if interface is not found.
        """
        rx_path = f"/sys/class/net/{self.interface}/statistics/rx_bytes"
        tx_path = f"/sys/class/net/{self.interface}/statistics/tx_bytes"

        rx_bytes = 0
        tx_bytes = 0

        try:
            if os.path.exists(rx_path):
                with open(rx_path, 'r', encoding='utf-8') as f:
                    rx_bytes = int(f.read().strip())
        except (IOError, ValueError):
            rx_bytes = 0

        try:
            if os.path.exists(tx_path):
                with open(tx_path, 'r', encoding='utf-8') as f:
                    tx_bytes = int(f.read().strip())
        except (IOError, ValueError):
            tx_bytes = 0

        return rx_bytes, tx_bytes

    def read_queue_occupancy(self) -> int:
        """
        Executes `tc -s qdisc show dev <interface>` and extracts backlogged packets.
        
        Returns:
            Backlogged packet count (0 if tc fails or no backlog exists).
        """
        try:
            # Run tc command with a short timeout to prevent blocking the telemetry loop
            cmd = ["tc", "-s", "qdisc", "show", "dev", self.interface]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False
            )
            if res.returncode == 0:
                return parse_tc_queue_output(res.stdout)
        except (subprocess.SubprocessError, FileNotFoundError):
            # Graceful fallback when tc is unavailable or command fails
            return 0

        return 0

    def probe_urllc_latency(
    self,
    count: int = 1,
    timeout: float = 1.0
) -> Tuple[float, float]:
        """
        Measure H1 -> H4 latency and packet loss from inside
        the Mininet H1 namespace.
        """

        try:
            # Get Mininet H1 process PID
            ps_result = subprocess.run(
                ["ps", "-eo", "pid=,args="],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False
            )

            h1_pid = None

            for line in ps_result.stdout.splitlines():
                line = line.strip()

                if "mininet:h1" in line:
                    parts = line.split(None, 1)

                    if parts:
                        try:
                            h1_pid = int(parts[0])
                            break
                        except ValueError:
                            pass

            if h1_pid is None:
                print("[Telemetry] Could not find Mininet H1")
                return -1.0, 100.0

            # Run ping inside H1 namespace
            cmd = [
                "mnexec",
                "-a",
                str(h1_pid),
                "ping",
                "-c",
                str(count),
                "-W",
                str(int(max(1, timeout))),
                "-n",
                self.h4_ip
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 2.0,
                check=False
            )

            output = (result.stdout or "") + "\n" + (result.stderr or "")

            latency, loss = parse_ping_output(output)

            if latency < 0:
                print("[Telemetry] Ping failed")
                print("[Telemetry] H1 PID:", h1_pid)
                print("[Telemetry] Return code:", result.returncode)
                print("[Telemetry] Output:")
                print(output)

            return latency, loss

        except subprocess.TimeoutExpired:
            print("[Telemetry] Ping timed out")
            return -1.0, 100.0

        except Exception as e:
            print("[Telemetry] Ping error:", e)
            return -1.0, 100.0
    def collect(self) -> TelemetryRecord:
        """
        Executes one full telemetry collection cycle:
        1. Reads current time and raw byte counters.
        2. Queries queue backlog.
        3. Probes latency & loss.
        4. Derives transmission rate (Mbps).
        5. Updates internal state.
        6. Logs to CSV if configured.
        
        Returns:
            TelemetryRecord instance populated with current measurements.
        """
        current_time = time.time()
        curr_rx_bytes, curr_tx_bytes = self.read_port_counters()
        queue_backlog = self.read_queue_occupancy()
        latency_ms, packet_loss = self.probe_urllc_latency()

        # Derive rates if a previous sample exists
        if self.prev_timestamp is not None and self.prev_tx_bytes is not None and self.prev_rx_bytes is not None:
            delta_t = current_time - self.prev_timestamp
            throughput, traffic_rate = calculate_rates(
                prev_tx=self.prev_tx_bytes,
                curr_tx=curr_tx_bytes,
                prev_rx=self.prev_rx_bytes,
                curr_rx=curr_rx_bytes,
                delta_time=delta_t
            )
        else:
            # First sample has no baseline for differential rate
            throughput = 0.0
            traffic_rate = 0.0

        # Update historical state
        self.prev_timestamp = current_time
        self.prev_rx_bytes = curr_rx_bytes
        self.prev_tx_bytes = curr_tx_bytes

        record = TelemetryRecord(
            timestamp=round(current_time, 4),
            interface=self.interface,
            urllc_latency_ms=round(latency_ms, 3) if latency_ms >= 0 else -1.0,
            urllc_packet_loss=round(packet_loss, 2),
            bottleneck_rx_bytes=curr_rx_bytes,
            bottleneck_tx_bytes=curr_tx_bytes,
            throughput_mbps=throughput,
            traffic_rate_mbps=traffic_rate,
            queue_occupancy=queue_backlog
        )

        if self.csv_path:
            log_to_csv(record, self.csv_path)

        return record


# ============================================================================
# STANDALONE EXECUTION / DEMONSTRATION MODE
# ============================================================================

def main():
    """
    Interactive standalone loop for manual testing.
    Collects telemetry every 1.0 second and prints formatted rows to stdout.
    """
    default_csv = os.path.join(os.path.dirname(__file__), "..", "data", "telemetry.csv")
    collector = NetworkTelemetryCollector(
        interface="s1-eth4",
        h1_ip="10.0.0.1",
        h4_ip="10.0.0.4",
        csv_path=default_csv
    )

    print("==================================================================")
    print(" Network Telemetry Monitor Active (Press Ctrl+C to Stop) ")
    print(f" Target Interface: {collector.interface} | Log CSV: {default_csv}")
    print("==================================================================")
    print(f"{'Time':<12} | {'Latency(ms)':<12} | {'Loss(%)':<8} | {'TPut(Mbps)':<11} | {'Rate(Mbps)':<11} | {'Queue(pkts)':<10}")
    print("-" * 75)

    try:
        while True:
            record = collector.collect()
            print(
                f"{record.timestamp:<12.2f} | "
                f"{record.urllc_latency_ms:<12.2f} | "
                f"{record.urllc_packet_loss:<8.1f} | "
                f"{record.throughput_mbps:<11.3f} | "
                f"{record.traffic_rate_mbps:<11.3f} | "
                f"{record.queue_occupancy:<10}"
            )
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Telemetry Monitor Stopped cleanly by user]")


if __name__ == "__main__":
    main()
