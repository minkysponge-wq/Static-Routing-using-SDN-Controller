# SDN Static Routing using Mininet and POX

## Problem Statement

This project demonstrates static routing in Software Defined Networking (SDN) using a POX controller. The controller installs predefined flow rules to control packet forwarding across the network.

---

## Objective

* Implement controller-based routing instead of shortest-path routing
* Install explicit flow rules using OpenFlow
* Validate routing behavior using ping and flow table inspection

---

## Topology

```
h1 ─ s1 ─ s2 ─ h2
      │      │
      s3 ─── s4
      │      │
     h3      h4
```

---

## Setup and Execution

### Start Controller

```bash
cd ~/pox
python3 pox.py log.level --DEBUG static_routing_controller
```

### Run Mininet

```bash
sudo python3 topology.py
```

### Test Network

```bash
pingall
h1 ping -c 5 h2
h1 ping -c 5 h4
```

---

## Expected Output

* `pingall` results in 0% packet loss
* h1 to h2 latency is approximately 10 ms (1 hop)
* h1 to h4 latency is approximately 20 ms (2 hops)

Latency increases with hop count, confirming that packets follow predefined static routes.

---

## Flow Rule Verification

```bash
sh ovs-ofctl dump-flows s1
```

Example:

```
nw_dst=10.0.0.4 → output:s1-eth3
```

Traffic destined for h4 is forwarded via s3, demonstrating that the controller enforces a specific path rather than the shortest path.

---

## Validation

* Flow rules determine packet forwarding behavior
* Removing flow rules disrupts connectivity
* Reinstalling rules restores network functionality

---

## Proof of Execution

Include the following:

* Ping results (pingall, h1 to h2, h1 to h4)
* Flow table outputs
* Performance test results (optional)

---

## Conclusion

The project demonstrates that an SDN controller can enforce predefined routing paths using flow rules. Network behavior is validated through latency measurements and flow table analysis.
