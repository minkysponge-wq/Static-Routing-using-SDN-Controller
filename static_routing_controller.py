#!/usr/bin/env python3
"""
Static Routing SDN Controller (POX)
=====================================
Implements static routing by installing predefined OpenFlow flow rules
on each switch via the POX controller. No dynamic learning or flooding.

Topology Reference:
    h1(10.0.0.1) --- s1 ------- s2 --- h2(10.0.0.2)
          (port1)  (p2   p1)  (port2)
                    (p3)       (p3)
                     |           |
                    (p1)       (p1)
                    s3 -------- s4
                   (p2) (p3 p2)(p3)
                     |           |
                h3(10.0.0.3)   h4(10.0.0.4)

Defined Static Routes:
    h1 <-> h2 : s1 -> s2             (direct top path)
    h1 <-> h3 : s1 -> s3             (direct left path)
    h1 <-> h4 : s1 -> s3 -> s4       (L-shaped via bottom)
    h2 <-> h3 : s2 -> s1 -> s3       (reverse L via top-left)
    h2 <-> h4 : s2 -> s4             (direct right path)
    h3 <-> h4 : s3 -> s4             (direct bottom path)

Usage:
    1. Copy this file into ~/pox/ext/
    2. Run: cd ~/pox && python3 pox.py log.level --DEBUG static_routing_controller

Author: [Your Name]
"""

from pox.core import core
from pox.lib.util import dpid_to_str
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr, EthAddr
from pox.lib.packet import ethernet, arp, ipv4

log = core.getLogger()


# ══════════════════════════════════════════════════════════════════
#  CONFIGURATION: Host Mappings & Static Routing Table
# ══════════════════════════════════════════════════════════════════

# Map each host IP to its MAC address
HOST_MAC = {
    '10.0.0.1': '00:00:00:00:00:01',  # h1
    '10.0.0.2': '00:00:00:00:00:02',  # h2
    '10.0.0.3': '00:00:00:00:00:03',  # h3
    '10.0.0.4': '00:00:00:00:00:04',  # h4
}

# Static Routing Table
# Key:   (switch_dpid, destination_ip)
# Value: output_port
#
# Each entry tells a specific switch which port to use
# for forwarding packets destined to a given IP address.
ROUTING_TABLE = {
    # ── Switch s1 (dpid=1) ──────────────────────────────
    (1, '10.0.0.1'): 1,  # To h1: port 1 (directly connected)
    (1, '10.0.0.2'): 2,  # To h2: port 2 -> s2
    (1, '10.0.0.3'): 3,  # To h3: port 3 -> s3
    (1, '10.0.0.4'): 3,  # To h4: port 3 -> s3 -> s4

    # ── Switch s2 (dpid=2) ──────────────────────────────
    (2, '10.0.0.1'): 1,  # To h1: port 1 -> s1
    (2, '10.0.0.2'): 2,  # To h2: port 2 (directly connected)
    (2, '10.0.0.3'): 1,  # To h3: port 1 -> s1 -> s3
    (2, '10.0.0.4'): 3,  # To h4: port 3 -> s4

    # ── Switch s3 (dpid=3) ──────────────────────────────
    (3, '10.0.0.1'): 1,  # To h1: port 1 -> s1
    (3, '10.0.0.2'): 1,  # To h2: port 1 -> s1 -> s2
    (3, '10.0.0.3'): 2,  # To h3: port 2 (directly connected)
    (3, '10.0.0.4'): 3,  # To h4: port 3 -> s4

    # ── Switch s4 (dpid=4) ──────────────────────────────
    (4, '10.0.0.1'): 2,  # To h1: port 2 -> s3 -> s1
    (4, '10.0.0.2'): 1,  # To h2: port 1 -> s2
    (4, '10.0.0.3'): 2,  # To h3: port 2 -> s3
    (4, '10.0.0.4'): 3,  # To h4: port 3 (directly connected)
}


# ══════════════════════════════════════════════════════════════════
#  CONTROLLER CLASS
# ══════════════════════════════════════════════════════════════════

class StaticRoutingController(object):
    """
    POX controller that installs static flow rules on switches
    when they connect, and handles ARP via proxy replies.

    Event Handling:
        ConnectionUp -> Install all flow rules on the connecting switch
        PacketIn     -> Handle ARP requests with proxy ARP replies
    """

    def __init__(self):
        # Register to listen for OpenFlow events
        core.openflow.addListeners(self)
        log.info("========================================")
        log.info(" Static Routing Controller Initialized")
        log.info("========================================")

    # ── EVENT: Switch connects to controller ─────────────────
    def _handle_ConnectionUp(self, event):
        """
        Triggered when a switch establishes connection with the controller.

        Actions:
          1. Install static IP forwarding rules (match: dst IP -> action: output port)
          2. Install ARP forwarding rules (same paths as IP)
          3. Install table-miss rule (unmatched packets -> send to controller)
        """
        dpid = event.dpid
        connection = event.connection

        log.info("──────────────────────────────────────")
        log.info("Switch s%s connected (dpid=%s)", dpid, dpid_to_str(event.dpid))

        # Step 1: Install IP forwarding rules
        self._install_ip_routes(connection, dpid)

        # Step 2: Install ARP forwarding rules
        self._install_arp_rules(connection, dpid)

        # Step 3: Table-miss rule (priority=0, lowest)
        # Any packet not matching other rules gets sent to controller
        miss_msg = of.ofp_flow_mod()
        miss_msg.priority = 0
        miss_msg.actions.append(
            of.ofp_action_output(port=of.OFPP_CONTROLLER)
        )
        connection.send(miss_msg)
        log.info("  [s%s] Table-miss rule installed", dpid)

        log.info("  [s%s] All %d flow rules installed successfully",
                 dpid, self._count_rules(dpid))
        log.info("──────────────────────────────────────\n")

    def _install_ip_routes(self, connection, dpid):
        """
        Install IPv4 static forwarding rules on a switch.

        Match:  dl_type = 0x0800 (IPv4), nw_dst = destination IP
        Action: Set destination MAC + output to specific port
        """
        for (sw_dpid, dst_ip), out_port in ROUTING_TABLE.items():
            if sw_dpid != dpid:
                continue

            dst_mac = HOST_MAC[dst_ip]

            # Build OpenFlow flow_mod message
            msg = of.ofp_flow_mod()
            msg.priority = 100            # Higher than table-miss (0)
            msg.idle_timeout = 0          # Never expire (static)
            msg.hard_timeout = 0          # Never expire (static)

            # Match: IPv4 packets destined for this IP
            msg.match.dl_type = 0x0800    # EtherType = IPv4
            msg.match.nw_dst = IPAddr(dst_ip)

            # Action 1: Rewrite destination MAC to correct host MAC
            msg.actions.append(
                of.ofp_action_dl_addr.set_dst(EthAddr(dst_mac))
            )
            # Action 2: Forward packet out the designated port
            msg.actions.append(
                of.ofp_action_output(port=out_port)
            )

            connection.send(msg)
            log.info("  [s%s] IP Route:  dst=%s -> port %s (mac=%s)",
                     dpid, dst_ip, out_port, dst_mac)

    def _install_arp_rules(self, connection, dpid):
        """
        Install ARP forwarding rules on a switch.
        ARP packets follow the same output ports as IP packets.

        Match:  dl_type = 0x0806 (ARP), nw_dst = target IP
        Action: Output to same port as corresponding IP rule
        """
        for (sw_dpid, dst_ip), out_port in ROUTING_TABLE.items():
            if sw_dpid != dpid:
                continue

            msg = of.ofp_flow_mod()
            msg.priority = 100
            msg.idle_timeout = 0
            msg.hard_timeout = 0

            # Match: ARP packets targeting this IP
            msg.match.dl_type = 0x0806    # EtherType = ARP
            msg.match.nw_dst = IPAddr(dst_ip)

            # Action: Forward out the same port as IP traffic
            msg.actions.append(
                of.ofp_action_output(port=out_port)
            )

            connection.send(msg)
            log.info("  [s%s] ARP Rule: dst=%s -> port %s",
                     dpid, dst_ip, out_port)

    def _count_rules(self, dpid):
        """Count how many rules were installed for this switch."""
        count = 0
        for (sw_dpid, _) in ROUTING_TABLE:
            if sw_dpid == dpid:
                count += 2  # One IP rule + one ARP rule per destination
        return count + 1    # Plus the table-miss rule

    # ── EVENT: Packet sent to controller (table-miss) ────────
    def _handle_PacketIn(self, event):
        """
        Triggered when a switch sends a packet to the controller.
        This happens when no flow rule matches the packet (table-miss).

        We handle:
          - ARP Requests: Reply with proxy ARP (we know all host MACs)
          - Other packets: Log a warning (should not happen with correct rules)
        """
        packet_data = event.parsed
        if not packet_data:
            return

        dpid = event.dpid
        in_port = event.port

        # Check if it's an ARP packet
        arp_pkt = packet_data.find('arp')
        if arp_pkt is not None:
            self._handle_arp(event, arp_pkt, dpid, in_port)
            return

        # Log unexpected packets (indicates missing flow rule)
        ip_pkt = packet_data.find('ipv4')
        if ip_pkt is not None:
            log.warning("  [s%s] UNEXPECTED PacketIn: %s -> %s (port=%s)",
                        dpid, ip_pkt.srcip, ip_pkt.dstip, in_port)

    def _handle_arp(self, event, arp_pkt, dpid, in_port):
        """
        Handle ARP requests using Proxy ARP.

        Instead of flooding ARP requests (which causes broadcast storms
        in a static routing setup), the controller replies directly
        with the correct MAC address.

        Process:
          1. Receive ARP Request ("Who has 10.0.0.4?")
          2. Look up target MAC from HOST_MAC table
          3. Build and send ARP Reply with correct MAC
        """
        # Only handle ARP Requests (opcode = 1)
        if arp_pkt.opcode != arp.REQUEST:
            return

        target_ip = str(arp_pkt.protodst)
        target_mac = HOST_MAC.get(target_ip)

        if target_mac is None:
            log.warning("  [s%s] ARP for unknown IP: %s", dpid, target_ip)
            return

        log.info("  [s%s] ARP: Who has %s? Tell %s -> Reply: %s",
                 dpid, target_ip, arp_pkt.protosrc, target_mac)

        # Build ARP Reply packet
        arp_reply = arp()
        arp_reply.hwtype = arp_pkt.hwtype
        arp_reply.prototype = arp_pkt.prototype
        arp_reply.hwlen = arp_pkt.hwlen
        arp_reply.protolen = arp_pkt.protolen
        arp_reply.opcode = arp.REPLY
        arp_reply.hwsrc = EthAddr(target_mac)    # "I am this MAC"
        arp_reply.hwdst = arp_pkt.hwsrc          # Send to requester
        arp_reply.protosrc = IPAddr(target_ip)    # "I have this IP"
        arp_reply.protodst = arp_pkt.protosrc     # Requester's IP

        # Wrap ARP in Ethernet frame
        eth_reply = ethernet()
        eth_reply.type = ethernet.ARP_TYPE
        eth_reply.src = EthAddr(target_mac)
        eth_reply.dst = arp_pkt.hwsrc
        eth_reply.payload = arp_reply

        # Send reply back out the same port the request came in on
        msg = of.ofp_packet_out()
        msg.data = eth_reply.pack()
        msg.actions.append(of.ofp_action_output(port=in_port))
        msg.in_port = event.port
        event.connection.send(msg)


# ══════════════════════════════════════════════════════════════════
#  POX LAUNCH FUNCTION
# ══════════════════════════════════════════════════════════════════

def launch():
    """
    Entry point called by POX framework.
    Usage: python3 pox.py log.level --DEBUG static_routing_controller
    """
    core.registerNew(StaticRoutingController)
    log.info("Static Routing Controller module loaded")
