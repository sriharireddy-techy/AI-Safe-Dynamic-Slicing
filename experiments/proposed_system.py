from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel

import time
import re


from telemetry.monitor import NetworkTelemetryCollector
from ai.context_builder import ContextBuilder
from ai.linucb import SRALinUCB
from feedback.reward import calculate_reward
URLLC_SLA_LIMIT = 15.0
MIN_EMBB_LIMIT = 2.0
MAX_EMBB_LIMIT = 9.0
class ProposedSystemTopo(Topo):
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

        # Shared bottleneck between the two switches
        self.addLink(
            s1, s2,
            cls=TCLink,
            bw=10,
            delay="5ms"
        )
        


def apply_guardrail(action, current_limit_mbps, urllc_latency_ms):
    """
    Check the AI action before applying it to the network.
    """

    # If URLLC latency is too high, protect URLLC
    if urllc_latency_ms >= URLLC_SLA_LIMIT:
        print("GUARDRAIL: URLLC SLA at risk!")

        if action == 2:  # INCREASE_EMBB
            print("GUARDRAIL: Blocked eMBB increase.")
            action = 1  # MAINTAIN

    # Prevent bandwidth limits from exceeding safe bounds
    proposed_limit = current_limit_mbps

    if action == 0:       # DECREASE_EMBB
        proposed_limit -= 2.0
    elif action == 2:     # INCREASE_EMBB
        proposed_limit += 2.0

    proposed_limit = max(
        MIN_EMBB_LIMIT,
        min(MAX_EMBB_LIMIT, proposed_limit)
    )

    print(f"Guardrail-approved action: {action}")
    print(f"Approved eMBB limit: {proposed_limit:.1f} Mbps")

    return action, proposed_limit
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
        f"Applied eMBB limit: "
        f"{current_limit_mbps:.1f} -> {new_limit:.1f} Mbps"
    )

    if result.strip():
        print("Traffic-control output:", result.strip())

    return new_limit
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

def run_experiment():
    net = None

    try:
        print("\n==============================")
        print("EXPERIMENT 3: PROPOSED SYSTEM")
        print("==============================")

        topo = ProposedSystemTopo()
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

        collector = NetworkTelemetryCollector(
            interface="s1-eth4",
            h1_ip="10.0.0.1",
            h4_ip="10.0.0.4"
        )

        context_builder = ContextBuilder()

        # Risk-aware LinUCB
        agent = SRALinUCB(
            risk_lambda=0.5
        )

        current_limit_mbps = 6.0

        print("\nMeasuring baseline eMBB throughput...")
        baseline_throughput = measure_embb_throughput(h2, h5)

        if baseline_throughput is None:
            print("Baseline throughput measurement failed.")
            return

        print("\nCollecting telemetry...")
        record = collector.collect()
        context = context_builder.build_context(record)

        print(f"URLLC latency: {record.urllc_latency_ms:.3f} ms")
        print(f"URLLC packet loss: {record.urllc_packet_loss:.1f}%")

        # Step 1: AI selects an action
        action, diagnostics = agent.select_action(context)

        print("\nAI selected:", diagnostics["selected_action_name"])

        # Step 2: Guardrail checks the action
        approved_action, approved_limit = apply_guardrail(
            action,
            current_limit_mbps,
            record.urllc_latency_ms
        )

        # Step 3: Apply the approved action
        current_limit_mbps = apply_embb_action(
            h2,
            approved_action,
            current_limit_mbps
    )

        if abs(current_limit_mbps - approved_limit) > 0.01:
            raise RuntimeError(
                f"Guardrail limit mismatch: approved={approved_limit}, "
                f"applied={current_limit_mbps}"
    )

        print("\nMeasuring post-action eMBB throughput...")
        adjusted_throughput = measure_embb_throughput(h2, h5)

        if adjusted_throughput is None:
            print("Post-action throughput measurement failed.")
            return

# Step 4: Measure the new network state
        time.sleep(1)
        new_record = collector.collect()

        print(f"\nPost-action URLLC latency: "
              f"{new_record.urllc_latency_ms:.3f} ms")
        print(f"Post-action packet loss: "
              f"{new_record.urllc_packet_loss:.1f}%")
        print(f"Applied eMBB limit: {current_limit_mbps:.1f} Mbps")

        # Step 5: Calculate reward and update the agent
        previous_state = {
            "urllc_latency": record.urllc_latency_ms,
            "embb_throughput": baseline_throughput,
            "packet_loss": record.urllc_packet_loss,
        }

        new_state = {
            "urllc_latency": new_record.urllc_latency_ms,
            "embb_throughput": adjusted_throughput,
            "packet_loss": new_record.urllc_packet_loss,
        }

        reward = calculate_reward(
            previous_state,
            approved_action,
            new_state
        )

        agent.update(approved_action, context, reward)

        print(f"Reward: {reward:.2f}")
        print("LinUCB updated with feedback.")
        print("AI diagnostics:", diagnostics)

    finally:
        if net is not None:
            net.stop()
def test_guardrail():
    print("\nTesting guardrail...")

    # Test 1: Normal latency — decrease action
    action, limit = apply_guardrail(0, 6.0, 10.0)
    assert action == 0 and limit == 4.0
    print("Test 1 passed")

    # Test 2: SLA at risk — block increase
    action, limit = apply_guardrail(2, 6.0, 16.0)
    assert action == 1 and limit == 6.0
    print("Test 2 passed")

    # Test 3: Minimum bandwidth boundary
    action, limit = apply_guardrail(0, 2.0, 10.0)
    assert limit == 2.0
    print("Test 3 passed")



if __name__ == "__main__":
    setLogLevel("info")
    run_experiment()