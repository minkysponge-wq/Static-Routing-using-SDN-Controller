#!/usr/bin/env python3
"""
Static Routing SDN Project - Custom Mininet Topology
=====================================================
Creates a 4-switch, 4-host mesh topology for demonstrating
static routing with a POX SDN controller.

Topology:
    h1(10.0.0.1) --- s1 ------- s2 --- h2(10.0.0.2)
                      |           |
                     s3 -------- s4
                      |           |
                 h3(10.0.0.3)   h4(10.0.0.4)

Port Mappings:
    s1: port1=h1, port2=s2, port3=s3
    s2: port1=s1, port2=h2, port3=s4
    s3: port1=s1, port2=h3, port3=s4
    s4: port1=s2, port2=s3, port3=h4

Link Properties:
    All switch-to-switch links: 10 Mbps, 5ms delay
    (Enables meaningful latency/throughput measurements)

Usage:
    sudo python3 topology.py

Author: [Your Name]
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


class StaticRoutingTopo(Topo):
    """Custom 4-switch mesh topology for static routing."""

    def build(self):
        # ── Create Switches ──────────────────────────────────
        # Each switch gets a unique datapath ID (dpid)
        info("*** Creating switches\n")
        s1 = self.addSwitch('s1', dpid='0000000000000001')
        s2 = self.addSwitch('s2', dpid='0000000000000002')
        s3 = self.addSwitch('s3', dpid='0000000000000003')
        s4 = self.addSwitch('s4', dpid='0000000000000004')

        # ── Create Hosts ─────────────────────────────────────
        # Each host gets a static IP and MAC address
        info("*** Creating hosts\n")
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')

        # ── Host-to-Switch Links ─────────────────────────────
        info("*** Creating host links\n")
        self.addLink(h1, s1, port2=1)   # h1 <-> s1:port1
        self.addLink(h2, s2, port2=2)   # h2 <-> s2:port2
        self.addLink(h3, s3, port2=2)   # h3 <-> s3:port2
        self.addLink(h4, s4, port2=3)   # h4 <-> s4:port3

        # ── Switch-to-Switch Links ───────────────────────────
        # TCLink adds bandwidth limits and delay for realistic testing
        info("*** Creating switch-to-switch links\n")
        self.addLink(s1, s2, port1=2, port2=1,
                     cls=TCLink, bw=10, delay='5ms')   # s1:p2 <-> s2:p1
        self.addLink(s1, s3, port1=3, port2=1,
                     cls=TCLink, bw=10, delay='5ms')   # s1:p3 <-> s3:p1
        self.addLink(s2, s4, port1=3, port2=1,
                     cls=TCLink, bw=10, delay='5ms')   # s2:p3 <-> s4:p1
        self.addLink(s3, s4, port1=3, port2=2,
                     cls=TCLink, bw=10, delay='5ms')   # s3:p3 <-> s4:p2


def run_topology():
    """Start the Mininet network with remote POX controller."""
    setLogLevel('info')

    info("*** Creating network\n")
    topo = StaticRoutingTopo()
    net = Mininet(
        topo=topo,
        controller=None,           # Use remote controller
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False          # We assign MACs manually
    )

    # Connect to POX controller running on localhost:6633
    info("*** Adding remote controller (POX on 127.0.0.1:6633)\n")
    net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6633
    )

    net.start()

    # Print topology reference
    info("\n")
    info("╔══════════════════════════════════════════════════════╗\n")
    info("║         STATIC ROUTING SDN - NETWORK RUNNING        ║\n")
    info("╠══════════════════════════════════════════════════════╣\n")
    info("║                                                      ║\n")
    info("║  h1(.0.1) ─── s1 ──────── s2 ─── h2(.0.2)          ║\n")
    info("║                │            │                        ║\n")
    info("║               s3 ────────  s4                        ║\n")
    info("║                │            │                        ║\n")
    info("║  h3(.0.3)     ╵  h4(.0.4) ╵                         ║\n")
    info("║                                                      ║\n")
    info("╠══════════════════════════════════════════════════════╣\n")
    info("║  TEST COMMANDS:                                      ║\n")
    info("║    pingall                    All-to-all ping        ║\n")
    info("║    h1 ping -c 5 h2           Direct path test        ║\n")
    info("║    h1 ping -c 5 h4           Multi-hop path test     ║\n")
    info("║    iperf h1 h2               Throughput (direct)     ║\n")
    info("║    iperf h1 h4               Throughput (multi-hop)  ║\n")
    info("║    sh ovs-ofctl dump-flows s1   View flow table      ║\n")
    info("╚══════════════════════════════════════════════════════╝\n\n")

    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == '__main__':
    run_topology()
