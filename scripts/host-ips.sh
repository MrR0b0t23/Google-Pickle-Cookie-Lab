#!/usr/bin/env bash
# List host IPv4 addresses that a local VM is likely to reach you on.
# Run this on the machine that runs Docker (not inside the VM).
set -euo pipefail

echo "Candidate LAB_BIND_IP values (virtual network bridges first):"
echo

if command -v ifconfig >/dev/null 2>&1 && [[ "$(uname)" == "Darwin" ]]; then
  ifconfig | awk '
    /^[a-z]/ { iface = $1; sub(":", "", iface) }
    /inet / && $2 != "127.0.0.1" {
      kind = "other"
      if (iface ~ /^bridge|^vmnet|^vboxnet/) kind = "VM network  <- likely what you want"
      else if (iface ~ /^en/) kind = "LAN (reachable by other devices on your network!)"
      printf "  %-10s %-16s %s\n", iface, $2, kind
    }'
else
  ip -4 -o addr show | awk '$4 !~ /^127\./ {
    split($4, a, "/"); kind = "other"
    if ($2 ~ /^virbr|^vmnet|^vboxnet|^br-/) kind = "VM network  <- likely what you want"
    printf "  %-10s %-16s %s\n", $2, a[1], kind }'
fi

cat <<'EOF'

To confirm, run `ip route` inside the attacker VM. On a NAT network the
"default via" address is usually the host, e.g. "default via 192.168.60.2"
means the host is 192.168.60.1 on VMware (VMware uses .2 as the NAT gateway).
EOF
