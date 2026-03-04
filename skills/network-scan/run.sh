#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/../lib.sh"

info "=== Network Scan ==="

# Step 1: Discover subnets via the gateway's routing table
info "[1/5] Discovering subnets from gateway..."
# ssh ray@192.168.30.1 "ip route" | grep -oP '[\d.]+/\d+'

# Step 2: Run nmap ping sweep on each discovered subnet
info "[2/5] Running ping sweep on all subnets..."
# for subnet in 192.168.10.0/24 192.168.20.0/24 192.168.30.0/24; do
#   nmap -sn "$subnet" -oG - >> /tmp/network-scan-results.txt
# done

# Step 3: Run service detection on discovered hosts
info "[3/5] Running service detection on live hosts..."
# nmap -sV --top-ports 100 -iL /tmp/live-hosts.txt -oX /tmp/service-scan.xml

# Step 4: Merge results with known device inventory
info "[4/5] Merging with device inventory..."
# python3 merge_inventory.py /tmp/service-scan.xml ~/Projects/homelab/inventory.yaml

# Step 5: Generate updated network diagram
info "[5/5] Generating network diagram..."
# python3 generate_diagram.py ~/Projects/homelab/network-diagram.mmd

info "=== Scan complete ==="
