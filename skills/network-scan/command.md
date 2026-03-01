# Network Scan

Perform a full scan of all home network subnets.

## Steps

1. SSH to the gateway and discover all routed subnets
2. Run nmap ping sweeps across each subnet to find live hosts
3. Run service detection on discovered hosts
4. Merge scan results with the known device inventory
5. Generate an updated Mermaid network diagram

Execute: `~/Projects/claude-superpowers/skills/network-scan/run.sh`
