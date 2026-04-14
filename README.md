# Static Routing Using SDN Controller

## Problem Statement

In traditional networks, each router independently runs distributed routing protocols (OSPF, RIP, BGP) to compute forwarding paths. This decentralized approach makes it difficult to enforce specific routing policies or guarantee deterministic paths.

**This project implements centralized static routing using Software-Defined Networking (SDN)**, where a POX OpenFlow controller installs predefined flow rules on Open vSwitch instances simulated in Mininet. The controller dictates the exact path every packet takes — no dynamic route computation, no flooding, no learning.

### What This Project Demonstrates
- **Controller–switch interaction**: Switches connect to the POX controller, which installs flow rules via OpenFlow
- **Flow rule design (match–action)**: Each rule matches on destination IP/ARP and outputs to a specific port
- **Packet-in event handling**: ARP requests are handled by the controller using proxy ARP
- **Static routing behavior**: Deterministic, predefined paths verified through latency measurements

## Network Topology

```
    h1(10.0.0.1) ─── s1 ──────── s2 ─── h2(10.0.0.2)
                      │            │
                     s3 ────────  s4
                      │            │
                 h3(10.0.0.3)   h4(10.0.0.4)
```

### Component Details

| Component | Details |
|-----------|---------|
| Switches | s1 (dpid=1), s2 (dpid=2), s3 (dpid=3), s4 (dpid=4) |
| Hosts | h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3), h4 (10.0.0.4) |
| Links | 10 Mbps bandwidth, 5ms delay per inter-switch hop |
| Controller | POX (OpenFlow 1.0) on 127.0.0.1:6633 |

### Port Mappings

| Switch | Port 1 | Port 2 | Port 3 |
|--------|--------|--------|--------|
| s1 | h1 | s2 | s3 |
| s2 | s1 | h2 | s4 |
| s3 | s1 | h3 | s4 |
| s4 | s2 | s3 | h4 |

### Design Justification

A **4-switch mesh** topology was chosen because:
1. **Multiple possible paths exist** between hosts, making static route selection meaningful (e.g., h1→h4 could go s1→s2→s4 or s1→s3→s4 — the controller picks one)
2. **Hop count varies** (1-hop vs 2-hop paths), enabling clear latency comparison to prove routes are followed
3. **Non-trivial routing** — the controller must make routing decisions beyond simple direct forwarding
4. **Manageable complexity** — complex enough to demonstrate SDN concepts, simple enough to verify correctness

## Static Routes Defined

| Source | Destination | Path | Hops |
|--------|-------------|------|------|
| h1 | h2 | s1 → s2 | 1 |
| h1 | h3 | s1 → s3 | 1 |
| h1 | h4 | s1 → s3 → s4 | 2 |
| h2 | h3 | s2 → s1 → s3 | 2 |
| h2 | h4 | s2 → s4 | 1 |
| h3 | h4 | s3 → s4 | 1 |

All routes are **bidirectional** — reverse paths use the same switches.

**Note:** h1→h4 is deliberately routed via s3 (bottom path) instead of s2 (top path) to demonstrate that the controller enforces specific paths regardless of topology shortcuts.

## Controller Logic

### Flow Rule Design (Match–Action)

Each switch receives flow rules with two components:

**IP Forwarding Rules (priority=100):**
- **Match**: `dl_type=0x0800` (IPv4) + `nw_dst=<destination IP>`
- **Action**: `set_dl_dst=<destination MAC>` + `output:<port>`

**ARP Forwarding Rules (priority=100):**
- **Match**: `dl_type=0x0806` (ARP) + `nw_dst=<target IP>`
- **Action**: `output:<port>` (same port as IP rule)

**Table-miss Rule (priority=0):**
- **Match**: Any unmatched packet
- **Action**: Send to controller (`output:CONTROLLER`)

### Event Handling

| Event | Handler | Purpose |
|-------|---------|---------|
| `ConnectionUp` | `_handle_ConnectionUp` | Installs all static flow rules when a switch connects |
| `PacketIn` | `_handle_PacketIn` | Handles ARP requests via proxy ARP replies |

### Proxy ARP Mechanism

Since static routes don't support broadcast flooding, the controller acts as a **proxy ARP responder**:
1. Host sends ARP Request: "Who has 10.0.0.4? Tell 10.0.0.1"
2. Controller intercepts via `PacketIn` event
3. Controller looks up MAC for 10.0.0.4 → `00:00:00:00:00:04`
4. Controller sends ARP Reply directly back to the requesting host
5. No broadcast needed — avoids storms in the static routing setup

## Prerequisites

- **OS**: Ubuntu 18.04/20.04/22.04 (or WSL2 on Windows)
- **Mininet**: `sudo apt install mininet`
- **Open vSwitch**: `sudo apt install openvswitch-switch`
- **iperf**: `sudo apt install iperf`
- **POX Controller**: `git clone https://github.com/noxrepo/pox.git ~/pox`
- **Wireshark** (optional): `sudo apt install wireshark`

## Setup & Execution Steps

### Step 1: Clone this repository
```bash
git clone https://github.com/<your-username>/sdn-static-routing.git
cd sdn-static-routing
```

### Step 2: Install POX controller
```bash
cd ~
git clone https://github.com/noxrepo/pox.git
```

### Step 3: Copy controller to POX
```bash
cp static_routing_controller.py ~/pox/ext/
```

### Step 4: Start POX controller (Terminal 1)
```bash
cd ~/pox
python3 pox.py log.level --DEBUG static_routing_controller
```
**Expected**: You should see "Static Routing Controller Initialized"

### Step 5: Start Mininet topology (Terminal 2)
```bash
sudo python3 topology.py
```
**Expected**: You should see the topology diagram and `mininet>` prompt.
Check Terminal 1 — it should show flow rules being installed on s1, s2, s3, s4.

### Step 6: Test connectivity
```bash
mininet> pingall
```
**Expected**: 0% dropped (12/12 received)

### Step 7: Run performance tests
```bash
mininet> sh bash performance_test.sh
```

### Step 8: Run validation tests (Terminal 3)
```bash
sudo bash run_tests.sh
```

## Test Scenarios

### Scenario 1: Normal Connectivity & Path Validation

**Goal**: Verify all hosts communicate and packets follow defined static routes.

**Tests**:
1. **pingall** — All 6 host pairs reach each other with 0% packet loss
2. **Latency comparison** — 1-hop paths (h1→h2) show ~10ms RTT, 2-hop paths (h1→h4) show ~20ms RTT
3. **Flow table inspection** — Each switch has 8 forwarding rules (4 IP + 4 ARP) plus table-miss
4. **Path verification** — Flow rules confirm h1→h4 traffic goes out port 3 on s1 (toward s3, not s2)

**Expected output**:
```
mininet> pingall
*** Ping: testing ping reachability
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
```

### Scenario 2: Regression Test — Rule Reinstallation

**Goal**: Ensure that after deleting and reinstalling flow rules, behavior remains identical.

**Steps**:
1. Record flow rule count on all switches (BEFORE)
2. Ping h1→h4 — should succeed
3. Delete all flows: `ovs-ofctl del-flows s1` (repeat for s2, s3, s4)
4. Ping h1→h4 — should **fail** (proves flows were actually deleted)
5. Reconnect switches to controller (triggers `ConnectionUp` → rules reinstalled)
6. Ping h1→h4 — should succeed again
7. Compare flow rule counts: BEFORE == AFTER

**Expected**: All rules reinstalled identically, connectivity fully restored.

## Performance Observations & Analysis

| Metric | h1→h2 (1 hop) | h1→h4 (2 hops) | Analysis |
|--------|---------------|-----------------|----------|
| Avg RTT | ~10ms | ~20ms | Each hop adds 5ms delay × 2 directions |
| Throughput | ~9.5 Mbps | ~9.0 Mbps | Slight reduction due to extra switch processing |
| Packet Loss | 0% | 0% | All static routes correctly configured |
| Flow Rules/Switch | 9 | 9 | 4 IP + 4 ARP + 1 table-miss per switch |

**Key Observations**:
- **Latency scales linearly with hop count**: 2-hop paths show exactly ~2× the RTT of 1-hop paths, confirming packets traverse the defined static route
- **Throughput is stable**: Both paths achieve close to the 10 Mbps link limit, proving flow rules are efficiently installed in the switch data plane (not going through the controller)
- **Zero packet loss**: Proves all flow rules are correctly configured and ARP resolution works properly via proxy ARP

## File Structure

```
sdn-static-routing/
├── README.md                          # This documentation
├── static_routing_controller.py       # POX controller with static flow rules
├── topology.py                        # Mininet topology (4 switches, 4 hosts)
├── run_tests.sh                       # Automated test script (Scenarios 1 & 2)
├── performance_test.sh                # Performance measurement script
└── screenshots/                       # Proof of execution
    ├── controller_startup.png         # Controller logs showing rule installation
    ├── pingall_result.png             # 0% dropped result
    ├── latency_comparison.png         # 1-hop vs 2-hop RTT
    ├── iperf_result.png               # Throughput measurement
    ├── flow_tables.png                # ovs-ofctl dump-flows output
    ├── regression_test.png            # Delete → fail → reinstall → pass
    └── wireshark_capture.png          # OpenFlow + ICMP packets
```

## How to Capture Screenshots

```bash
# Controller logs (Terminal 1 after switches connect)
# → Screenshot the flow rule installation messages

# Ping all (Mininet CLI)
mininet> pingall

# Latency comparison
mininet> h1 ping -c 10 h2
mininet> h1 ping -c 10 h4

# Throughput
mininet> iperf h1 h2
mininet> iperf h1 h4

# Flow tables
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-ofctl dump-flows s2
mininet> sh ovs-ofctl dump-flows s3
mininet> sh ovs-ofctl dump-flows s4

# Wireshark (Terminal 3)
sudo wireshark &
# Select interface: s1-eth2
# Filter: openflow_v1 || icmp
# Then run: mininet> h1 ping -c 5 h2
```

## References

1. POX SDN Controller - [https://github.com/noxrepo/pox](https://github.com/noxrepo/pox)
2. Mininet Walkthrough - [http://mininet.org/walkthrough/](http://mininet.org/walkthrough/)
3. OpenFlow 1.0 Specification - [https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf](https://opennetworking.org/wp-content/uploads/2013/04/openflow-spec-v1.0.0.pdf)
4. Open vSwitch Manual - [https://docs.openvswitch.org/en/latest/](https://docs.openvswitch.org/en/latest/)
5. POX Wiki - [https://noxrepo.github.io/pox-doc/html/](https://noxrepo.github.io/pox-doc/html/)

## Author

**[Your Name]**
**[Roll Number]**
[University / Course Name]
SDN Mininet Simulation Project — Static Routing (Orange Problem)
