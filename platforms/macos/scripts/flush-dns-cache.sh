#!/bin/bash
#
# flush-dns-cache.sh — flush the macOS DNS cache.
#
# Admin-run: list it under the fleet's controls.scripts and run it on demand from the host
# page (Actions > Run script). Use when a host still resolves a stale address after a DNS,
# VPN or network change. Fleet runs scripts as root, so no sudo.
#
# -HUP makes mDNSResponder drop its cache and keep running (gentler than a full restart).

/usr/bin/dscacheutil -flushcache
/usr/bin/killall -HUP mDNSResponder || exit 1
echo "DNS cache flushed"
