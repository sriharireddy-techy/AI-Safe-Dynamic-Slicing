
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel
from feedback.reward import calculate_reward

import time
import re

from telemetry.monitor import NetworkTelemetryCollector
from ai.context_builder import ContextBuilder
from ai.linucb import SRALinUCB


class DynamicBaselineTopo(Topo):
    def build(self):
        s1 = self.addSwitch("s1", failMode="standalone")
        s2 = self.addSwitch("s2", failMode="standalone")

        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")
        h4 = self.addHost("h4", ip="10.0.0.4/24")
        h5 = self.addHost("h5", ip="10.0.0.5/24")
        h6 = self.addHost("h6", ip="10.0.0.6/24")

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)
        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h6, s2)

        self.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")



    

    
def measure_embb_throughput(h2, h5):
    port = 5002

    # Start the server in the background and retain its process
    server = h5.popen(
        ["iperf", "-s", "-p", str(port)],
        stdout=open("/tmp/iperf_server.log", "w"),
        stderr=-2
    )
    time.sleep(1)

    if server.poll() is not None:
        print("ERROR: iperf server exited.")
        print(h5.cmd("cat /tmp/iperf_server.log"))
        return None

    result = h2.cmd(
        f"iperf -c 10.0.0.5 -p {port} -t 3"
    )

    # Stop this exact server process
    server.terminate()
    try:
        server.wait(timeout=2)
    except Exception:
        server.kill()
        server.wait()

    matches = re.findall(r"([\d.]+)\s+Mbits/sec", result)

    if not matches:
        print("ERROR: Could not measure throughput.")
        print(result)
        return None

    throughput = float(matches[-1])
    print(f"Measured eMBB throughput: {throughput:.2f} Mbps")
    return throughput

    


def apply_embb_action(h2, action, current_limit_mbps):
    if action == 0:       # DECREASE_EMBB
        new_limit = max(2.0, current_limit_mbps - 2.0)
    elif action == 1:     # MAINTAIN
        new_limit = current_limit_mbps
    elif action == 2:     # INCREASE_EMBB
        new_limit = min(9.0, current_limit_mbps + 2.0)
    else:
        raise ValueError(f"Unknown AI action: {action}")

    result = h2.cmd(
        f"tc qdisc replace dev h2-eth0 root tbf "
        f"rate {new_limit}mbit burst 32kb latency 100ms"
    )

    print(
        f"eMBB limit: {current_limit_mbps:.1f} -> "
        f"{new_limit:.1f} Mbps"
    )

    if result.strip():
        print("Traffic-control output:", result.strip())

    return new_limit


def run_experiment():
    net = None

    try:
        print("\n==============================")
        print("DYNAMIC BASELINE EXPERIMENT")
        print("==============================")

        topo = DynamicBaselineTopo()
        net = Mininet(
            topo=topo,
            controller=None,
            switch=OVSSwitch,
            autoSetMacs=True
        )
        net.start()

        h1 = net.get("h1")
        h2 = net.get("h2")
        h5 = net.get("h5")

        print("\nTesting connectivity...")
        net.pingAll()

        print("\nMeasuring eMBB baseline throughput...")
        baseline_throughput = measure_embb_throughput(h2, h5)
        if baseline_throughput is None:
            print("Baseline measurement failed; stopping experiment.")
            return

        collector = NetworkTelemetryCollector(
            interface="s1-eth4",
            h1_ip="10.0.0.1",
            h4_ip="10.0.0.4"
        )
        context_builder = ContextBuilder()
        agent = SRALinUCB(risk_lambda=0.0)

        print("\nCollecting initial telemetry...")
        record = collector.collect()
        context = context_builder.build_context(record)

        print(f"URLLC latency: {record.urllc_latency_ms:.3f} ms")
        print(f"URLLC packet loss: {record.urllc_packet_loss:.1f}%")
        print(f"Bottleneck throughput: {record.throughput_mbps:.3f} Mbps")
        print(f"Queue occupancy: {record.queue_occupancy} packets")
        previous_state = {
            "urllc_latency": record.urllc_latency_ms,
            "embb_throughput": baseline_throughput,
            "packet_loss": record.urllc_packet_loss,
    }

        action, diagnostics = agent.select_action(context)
        print("\nAI selected:", diagnostics["selected_action_name"])

        current_limit_mbps = 6.0
        current_limit_mbps = apply_embb_action(
            h2, action, current_limit_mbps
        )

        print("\nMeasuring eMBB throughput after AI action...")
        adjusted_throughput = measure_embb_throughput(h2, h5)
        if adjusted_throughput is None:
            print("Post-action measurement failed; result is invalid.")
            return
        print("\nCollecting post-action telemetry...")
        new_record = collector.collect()

        new_state = {
            "urllc_latency": new_record.urllc_latency_ms,
            "embb_throughput": adjusted_throughput,
            "packet_loss": new_record.urllc_packet_loss,
    }

        reward = calculate_reward(previous_state, action, new_state)
        agent.update(action, context, reward)

        print(f"LinUCB updated with reward: {reward:.2f}")

        print(f"Post-action URLLC latency: {new_state['urllc_latency']:.3f} ms")
        print(f"Post-action packet loss: {new_state['packet_loss']:.1f}%")
        print(f"Calculated reward: {reward:.2f}")

        print("\n========== RESULTS ==========")
        print(f"Baseline eMBB throughput: {baseline_throughput:.2f} Mbps")
        print(f"Post-action eMBB throughput: {adjusted_throughput:.2f} Mbps")
        print(f"Applied eMBB limit: {current_limit_mbps:.1f} Mbps")
        print(f"URLLC SLA limit: 15.0 ms")
        print("AI diagnostics:", diagnostics)

    finally:
        if net is not None:
            net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run_experiment()
