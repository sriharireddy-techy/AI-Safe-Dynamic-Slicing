from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel
import time


class StaticBaselineTopo(Topo):

    def build(self):
        s1 = self.addSwitch('s1', failMode='standalone')
        s2 = self.addSwitch('s2', failMode='standalone')

        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')

        h4 = self.addHost('h4', ip='10.0.0.4/24')
        h5 = self.addHost('h5', ip='10.0.0.5/24')
        h6 = self.addHost('h6', ip='10.0.0.6/24')

        self.addLink(h1, s1)
        self.addLink(h2, s1)
        self.addLink(h3, s1)

        self.addLink(h4, s2)
        self.addLink(h5, s2)
        self.addLink(h6, s2)

        # Fixed bottleneck: 10 Mbps, 5 ms
        self.addLink(
            s1,
            s2,
            cls=TCLink,
            bw=10,
            delay='5ms'
        )


def measure_urllc_latency(h1):
    result = h1.cmd("ping -c 10 10.0.0.4")

    print("\nURLLC Latency Test:")
    print(result)

    # Extract average latency
    avg_latency = None

    for line in result.splitlines():
        if "rtt min/avg/max/mdev" in line:
            values = line.split("=")[1].strip()
            avg_latency = float(values.split("/")[1])

    # SLA limit = 15 ms
    sla_limit = 15.0

    if avg_latency is not None:
        if avg_latency > sla_limit:
            sla_violations = 1
        else:
            sla_violations = 0

        print(f"Average URLLC Latency: {avg_latency:.3f} ms")
        print(f"SLA Limit: {sla_limit:.1f} ms")
        print(f"SLA Violations: {sla_violations}")

def measure_embb_throughput(h2, h5):
    print("\neMBB Throughput Test:")

    # Start iperf server on H5
    h5.cmd("iperf -s -D")
    time.sleep(1)

    # Send traffic from H2 to H5
    result = h2.cmd("iperf -c 10.0.0.5 -t 5")

    print(result)

    # Stop iperf server
    h5.cmd("killall iperf")


def run_experiment():

    topo = StaticBaselineTopo()

    net = Mininet(
        topo=topo,
        controller=None,
        switch=OVSSwitch,
        autoSetMacs=True
    )

    net.start()

    print("\n==============================")
    print("STATIC BASELINE EXPERIMENT")
    print("==============================")
    print("URLLC : H1 <-> H4")
    print("eMBB  : H2 <-> H5")
    print("BE    : H3 <-> H6")
    print("Bottleneck : 10 Mbps / 5 ms")
    print("==============================\n")

    print("Testing connectivity...")
    net.pingAll()

    # Measure URLLC latency
    measure_urllc_latency(net.get('h1'))

    # Measure eMBB throughput
    measure_embb_throughput(
        net.get('h2'),
        net.get('h5')
    )

    time.sleep(2)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    run_experiment()