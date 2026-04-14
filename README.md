SDN Static Routing System

Overview
A Mininet-based SDN routing system using a POX controller. The controller installs predefined flow rules to enforce specific packet paths instead of shortest-path routing.

Topology:

```
h1 (10.0.0.1) ── s1 ── s2 ── h2 (10.0.0.2)
                     │      │
                     s3 ─── s4
                     │      │
                h3 (10.0.0.3)   h4 (10.0.0.4)
```

Files
File                         Purpose
static_routing_controller.py  POX controller – static routing logic
topology.py                  Mininet topology (4 switches, 4 hosts)
performance_test.sh          Latency and throughput analysis
run_tests.sh                 Validation and regression testing

---

Setup

1. Install dependencies

```
sudo apt install mininet openvswitch-switch iperf -y
```

2. Install POX

```
cd ~
git clone https://github.com/noxrepo/pox.git
```

3. Copy the controller

```
cp static_routing_controller.py ~/pox/ext/
```

---

Running

Terminal 1 – Start the POX controller

```
cd ~/pox
python3 pox.py log.level --DEBUG static_routing_controller
```

You should see: Static Routing Controller Initialized

Terminal 2 – Start Mininet topology

```
sudo python3 topology.py
```

---

Manual Tests (Mininet CLI)

```
mininet> pingall                  # All hosts reachable
mininet> h1 ping -c 5 h2          # 1-hop path (~10 ms)
mininet> h1 ping -c 5 h4          # 2-hop path (~20 ms)
```

---

Check Flow Rules

```
mininet> sh ovs-ofctl dump-flows s1
```

Example:

```
nw_dst=10.0.0.4 → output:s1-eth3
```

This shows traffic to h4 is forwarded via s3, not the shortest path.

---

Automated Tests

Terminal 3 (controller + Mininet must be running):

```
sudo bash run_tests.sh
```

Test scenarios:

* All hosts can communicate (normal operation)
* Flow rules exist on all switches
* Deleting rules breaks connectivity
* Reinstalling rules restores connectivity

---

Performance Analysis

```
mininet> sh bash performance_test.sh
```

Observations:

* 1-hop paths ≈ 10 ms RTT
* 2-hop paths ≈ 20 ms RTT
* Latency increases with hop count

---

How it works

Packet arrives at switch
│
▼
Match flow rule (destination IP)
│
▼
Controller-installed rule decides output port
│
▼
Packet forwarded along predefined path

Example:

* h1 → h4 follows s1 → s3 → s4
* Not shortest path, but controller-defined path

---

Modifying Routes

Edit `static_routing_controller.py` and update the routing table:

```
ROUTING_TABLE = {
    (1, '10.0.0.4'): 3,
    ...
}
```

Restart the controller after changes.

---

Expected Output

```
pingall → 0% packet loss  

h1 → h2 RTT ≈ 10 ms  
h1 → h4 RTT ≈ 20 ms  

Flow tables show correct output ports  
```

---

Conclusion

The project demonstrates static routing using SDN, where a controller enforces predefined paths through explicit flow rules. Network behavior is validated using latency measurements and flow table inspection.
