#!/bin/bash
# Remediation for "Linux - Firewall on and blocks incoming connections"
# (platforms/linux/policies/firewall-enabled.yml).
#
# Turns on ufw with the defaults CIS Ubuntu 24.04 section 4.2 asks for: deny
# incoming, allow outgoing, deny routed, loopback rules (4.2.4), and no
# iptables-persistent beside ufw (4.2.2). ICMP and related/established traffic
# are accepted by ufw's packaged before.rules.
#
# Safe to repeat: ufw skips rules that already exist, and existing rules are
# never removed (no `ufw reset`), so a rule IT or the user added survives.
# Does not open any port: a host that needs one gets its rule from the control
# that needs it. Before the firewall goes on, the script logs every service
# listening on a non-loopback address, so you can see what default-deny cuts
# off. Roll it out behind a pilot label first.

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

DEFAULTS=/etc/default/ufw

apt_get() {
    apt-get -o DPkg::Lock::Timeout=240 "$@"
}

echo "Firewall: current state"
if command -v ufw >/dev/null; then
    ufw status verbose || true
else
    echo "  ufw not installed"
fi

if ! dpkg-query -W -f='${Status}' ufw 2>/dev/null | grep -q 'install ok installed'; then
    echo "Firewall: installing ufw"
    apt_get update -q || echo "Warning: apt-get update failed; using cached lists."
    apt_get install --assume-yes -q ufw
fi

# CIS 4.2.2: iptables-persistent restores its own rule set at boot, beside
# ufw's, so the effective rules are no longer the ones ufw reports.
if dpkg-query -W -f='${Status}' iptables-persistent 2>/dev/null | grep -q 'install ok installed'; then
    echo "Firewall: removing iptables-persistent (CIS 4.2.2)"
    apt_get purge --assume-yes -q iptables-persistent
fi

# The audit trail of what default-deny cuts off: services listening on
# non-loopback addresses before the firewall goes on.
echo "Firewall: TCP and UDP listeners on non-loopback addresses (now blocked unless a rule allows them):"
ss -H -ltun 2>/dev/null | awk '$5 !~ /^(127\.|\[::1\]|\[::ffff:127\.)/ {print "  " $1, $5}' || true

if grep -q '^[[:space:]]*IPV6=' "$DEFAULTS"; then
    sed -i -E 's/^[[:space:]]*IPV6=.*/IPV6=yes/' "$DEFAULTS"
else
    echo 'IPV6=yes' >> "$DEFAULTS"
fi

echo "Firewall: default policies"
ufw default deny incoming
ufw default allow outgoing
ufw default deny routed

echo "Firewall: loopback rules (CIS 4.2.4)"
ufw allow in on lo
ufw allow out on lo
ufw deny in from 127.0.0.0/8
ufw deny in from ::1

echo "Firewall: turning on"
ufw --force enable
systemctl enable --now ufw.service

echo "Firewall: new state"
ufw status verbose
echo "Firewall: done"
