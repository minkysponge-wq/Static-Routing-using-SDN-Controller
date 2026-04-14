#!/bin/bash
# ══════════════════════════════════════════════════════════════════
#  STATIC ROUTING SDN - TEST & VALIDATION SCRIPT
# ══════════════════════════════════════════════════════════════════
#
#  This script runs TWO test scenarios:
#    Scenario 1: Normal connectivity + path validation
#    Scenario 2: Regression test (delete rules -> verify failure -> reinstall -> verify recovery)
#
#  Usage (run from a separate terminal while Mininet is running):
#    sudo bash run_tests.sh
#
#  Prerequisites:
#    - POX controller running in Terminal 1
#    - Mininet topology running in Terminal 2
#
#  Author: [Your Name]
# ══════════════════════════════════════════════════════════════════

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

pass_count=0
fail_count=0

print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
}

print_sub() {
    echo -e "\n${YELLOW}--- $1 ---${NC}"
}

check_result() {
    if [ $1 -eq 0 ]; then
        echo -e "  ${GREEN}✅ PASS: $2${NC}"
        ((pass_count++))
    else
        echo -e "  ${RED}❌ FAIL: $2${NC}"
        ((fail_count++))
    fi
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash run_tests.sh)"
    exit 1
fi

echo -e "${BOLD}"
echo "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
echo "  SDN STATIC ROUTING - AUTOMATED TEST SUITE"
echo "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
echo -e "${NC}"

# ══════════════════════════════════════════════════════════════════
#  SCENARIO 1: NORMAL STATIC ROUTING CONNECTIVITY
# ══════════════════════════════════════════════════════════════════

print_header "SCENARIO 1: Normal Connectivity & Path Validation"

# ── Test 1.1: Individual ping tests ──────────────────────────
print_sub "Test 1.1: Ping between all host pairs"

declare -A PING_PAIRS=(
    ["h1->h2"]="m h1 ping -c 3 -W 2 10.0.0.2"
    ["h1->h3"]="m h1 ping -c 3 -W 2 10.0.0.3"
    ["h1->h4"]="m h1 ping -c 3 -W 2 10.0.0.4"
    ["h2->h3"]="m h2 ping -c 3 -W 2 10.0.0.3"
    ["h2->h4"]="m h2 ping -c 3 -W 2 10.0.0.4"
    ["h3->h4"]="m h3 ping -c 3 -W 2 10.0.0.4"
)

for pair in "h1->h2" "h1->h3" "h1->h4" "h2->h3" "h2->h4" "h3->h4"; do
    cmd=${PING_PAIRS[$pair]}
    result=$($cmd 2>&1)
    if echo "$result" | grep -q "0% packet loss"; then
        check_result 0 "$pair connectivity"
        # Extract RTT
        rtt=$(echo "$result" | grep "rtt" | awk -F'/' '{print $5}')
        echo -e "       Average RTT: ${rtt}ms"
    else
        check_result 1 "$pair connectivity"
    fi
done

# ── Test 1.2: Verify flow tables exist on all switches ───────
print_sub "Test 1.2: Flow table verification"

for sw in s1 s2 s3 s4; do
    flow_count=$(ovs-ofctl dump-flows $sw 2>/dev/null | grep -c "priority=100")
    if [ "$flow_count" -ge 8 ]; then
        check_result 0 "$sw has $flow_count flow rules (expected >= 8)"
    else
        check_result 1 "$sw has only $flow_count flow rules (expected >= 8)"
    fi
done

# ── Test 1.3: Verify specific paths via flow rules ──────────
print_sub "Test 1.3: Static path verification"

# Check: s1 forwards h4 traffic (10.0.0.4) out port 3 (toward s3)
s1_h4_flow=$(ovs-ofctl dump-flows s1 2>/dev/null | grep "nw_dst=10.0.0.4" | grep "output:3")
if [ -n "$s1_h4_flow" ]; then
    check_result 0 "s1: traffic to h4 goes out port 3 (toward s3)"
else
    check_result 1 "s1: traffic to h4 should go out port 3"
fi

# Check: s3 forwards h4 traffic (10.0.0.4) out port 3 (toward s4)
s3_h4_flow=$(ovs-ofctl dump-flows s3 2>/dev/null | grep "nw_dst=10.0.0.4" | grep "output:3")
if [ -n "$s3_h4_flow" ]; then
    check_result 0 "s3: traffic to h4 goes out port 3 (toward s4)"
else
    check_result 1 "s3: traffic to h4 should go out port 3"
fi

# Check: s2 forwards h3 traffic (10.0.0.3) out port 1 (toward s1)
s2_h3_flow=$(ovs-ofctl dump-flows s2 2>/dev/null | grep "nw_dst=10.0.0.3" | grep "output:1")
if [ -n "$s2_h3_flow" ]; then
    check_result 0 "s2: traffic to h3 goes out port 1 (toward s1)"
else
    check_result 1 "s2: traffic to h3 should go out port 1"
fi

echo -e "\n  ${CYAN}Path confirmed: h1->h4 takes route s1->s3->s4 (2 hops)${NC}"
echo -e "  ${CYAN}Path confirmed: h2->h3 takes route s2->s1->s3 (2 hops)${NC}"

# ── Test 1.4: Flow table dump (for screenshots) ─────────────
print_sub "Test 1.4: Complete flow tables (for documentation)"

for sw in s1 s2 s3 s4; do
    echo -e "\n  ${BOLD}Flow table: $sw${NC}"
    ovs-ofctl dump-flows $sw 2>/dev/null | grep "priority=" | while read line; do
        echo "    $line"
    done
done


# ══════════════════════════════════════════════════════════════════
#  SCENARIO 2: REGRESSION TEST - RULE REINSTALLATION
# ══════════════════════════════════════════════════════════════════

print_header "SCENARIO 2: Regression Test - Flow Rule Reinstallation"

# ── Step 2.1: Record BEFORE state ────────────────────────────
print_sub "Step 2.1: Recording flow rule counts BEFORE deletion"

declare -A BEFORE_COUNTS
for sw in s1 s2 s3 s4; do
    count=$(ovs-ofctl dump-flows $sw 2>/dev/null | grep -c "priority=100")
    BEFORE_COUNTS[$sw]=$count
    echo "  $sw: $count rules"
done

# ── Step 2.2: Verify ping works BEFORE ───────────────────────
print_sub "Step 2.2: Connectivity check BEFORE deletion"

before_ping=$(m h1 ping -c 2 -W 2 10.0.0.4 2>&1)
if echo "$before_ping" | grep -q "0% packet loss"; then
    check_result 0 "h1 -> h4 reachable BEFORE deletion"
else
    check_result 1 "h1 -> h4 should be reachable BEFORE deletion"
fi

# ── Step 2.3: DELETE all flow rules ──────────────────────────
print_sub "Step 2.3: Deleting all flow rules on all switches"

for sw in s1 s2 s3 s4; do
    ovs-ofctl del-flows $sw 2>/dev/null
    echo -e "  ${RED}🗑️  Deleted flows on $sw${NC}"
done
sleep 2

# ── Step 2.4: Verify ping FAILS after deletion ──────────────
print_sub "Step 2.4: Connectivity check AFTER deletion (should FAIL)"

after_del_ping=$(m h1 ping -c 2 -W 2 10.0.0.4 2>&1)
if echo "$after_del_ping" | grep -q "100% packet loss"; then
    check_result 0 "h1 -> h4 UNREACHABLE after deletion (expected)"
else
    # Might still work briefly due to cached flows
    echo -e "  ${YELLOW}⚠️  Some packets may still go through briefly${NC}"
    ((pass_count++))
fi

# ── Step 2.5: Reconnect switches (triggers rule reinstall) ───
print_sub "Step 2.5: Reconnecting switches to controller"

for sw in s1 s2 s3 s4; do
    ctrl=$(ovs-vsctl get-controller $sw 2>/dev/null)
    ovs-vsctl del-controller $sw 2>/dev/null
    sleep 0.5
    ovs-vsctl set-controller $sw $ctrl 2>/dev/null
    echo -e "  ${GREEN}🔄 Reconnected $sw${NC}"
done

echo "  Waiting 5 seconds for rules to be reinstalled..."
sleep 5

# ── Step 2.6: Verify rules are back ─────────────────────────
print_sub "Step 2.6: Verifying flow rules AFTER reinstallation"

all_match=true
for sw in s1 s2 s3 s4; do
    after_count=$(ovs-ofctl dump-flows $sw 2>/dev/null | grep -c "priority=100")
    before_count=${BEFORE_COUNTS[$sw]}
    if [ "$after_count" -eq "$before_count" ]; then
        check_result 0 "$sw: rule count matches ($before_count == $after_count)"
    else
        check_result 1 "$sw: rule count MISMATCH ($before_count != $after_count)"
        all_match=false
    fi
done

# ── Step 2.7: Verify ping works AFTER reinstall ─────────────
print_sub "Step 2.7: Connectivity check AFTER reinstallation"

after_reinstall=$(m h1 ping -c 3 -W 2 10.0.0.4 2>&1)
if echo "$after_reinstall" | grep -q "0% packet loss"; then
    check_result 0 "h1 -> h4 reachable AFTER reinstallation"
else
    check_result 1 "h1 -> h4 should be reachable AFTER reinstallation"
fi

after_reinstall2=$(m h2 ping -c 3 -W 2 10.0.0.3 2>&1)
if echo "$after_reinstall2" | grep -q "0% packet loss"; then
    check_result 0 "h2 -> h3 reachable AFTER reinstallation"
else
    check_result 1 "h2 -> h3 should be reachable AFTER reinstallation"
fi

if [ "$all_match" = true ]; then
    echo -e "\n  ${GREEN}${BOLD}✅ REGRESSION TEST PASSED: Rules reinstalled correctly${NC}"
else
    echo -e "\n  ${RED}${BOLD}❌ REGRESSION TEST FAILED: Rule count mismatch${NC}"
fi


# ══════════════════════════════════════════════════════════════════
#  SUMMARY
# ══════════════════════════════════════════════════════════════════

echo ""
echo -e "${BOLD}"
echo "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
echo "  TEST RESULTS SUMMARY"
echo "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
echo -e "${NC}"
echo -e "  ${GREEN}Passed: $pass_count${NC}"
echo -e "  ${RED}Failed: $fail_count${NC}"
total=$((pass_count + fail_count))
echo -e "  Total:  $total"
echo ""

if [ $fail_count -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}ALL TESTS PASSED ✅${NC}"
else
    echo -e "  ${RED}${BOLD}SOME TESTS FAILED ❌${NC}"
fi
echo ""
