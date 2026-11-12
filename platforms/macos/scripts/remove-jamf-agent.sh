#!/bin/bash
#
# remove-jamf-agent.sh — submit a final inventory to Jamf (best effort), then remove the
#   Jamf agent.
#
# Run by the "macOS - Jamf agent removed" policy (jamf-agent-removed.yml), which only fails
# (and so only runs this) once the host's MDM enrolment already points at Fleet.
#
# `jamf removeFramework` removes the AGENT (binary, LaunchDaemons/Agents,
# /Library/Application Support/JAMF, keychain items). It does NOT remove the Jamf MDM
# enrolment profile; that must be gone before Fleet's MDM can enrol. This is cleanup after
# the MDM handover, not the migration step itself.
#
# `jamf recon` usually fails here (Jamf MDM comms are gone); its exit code is ignored.
#
# The agent is located by absolute path, never via PATH: PATH differs between an interactive
# shell and Fleet's script runner. Success is verified by checking the binary is gone, and a
# non-zero exit lets the policy retry on its next run.

set -u

log() { /bin/echo "$(/bin/date '+%Y-%m-%d %H:%M:%S') remove-jamf-agent: $*"; }

# --- locate the agent --------------------------------------------------------------------
# Checked in order, taking the first that is actually executable. PATH is not consulted: it
# differs between an interactive shell and Fleet's script runner, which is what broke the
# previous version.
jamf_binary=""
for candidate in /usr/local/bin/jamf /usr/sbin/jamf /usr/local/jamf/bin/jamf; do
  if [ -x "$candidate" ]; then
    jamf_binary="$candidate"
    break
  fi
done

if [ -z "$jamf_binary" ]; then
  log "no Jamf agent found — nothing to remove"
  exit 0
fi
log "found Jamf agent at $jamf_binary"

# --- final inventory (best-effort) -------------------------------------------------------
log "attempting a final recon (expected to fail if Jamf MDM is already gone)"
if "$jamf_binary" recon >/dev/null 2>&1; then
  log "recon submitted"
else
  log "recon failed — continuing, this does not block removal"
fi

# --- remove the agent --------------------------------------------------------------------
log "running removeFramework"
if ! "$jamf_binary" removeFramework >/dev/null 2>&1; then
  log "ERROR: removeFramework reported failure"
fi

# --- verify, and let the exit code drive the retry ---------------------------------------
# Do not trust removeFramework's own exit code: check the binary is actually gone. The policy
# re-runs this on its next interval while it still fails, so a non-zero exit here is the retry.
still=""
for candidate in /usr/local/bin/jamf /usr/sbin/jamf /usr/local/jamf/bin/jamf; do
  [ -e "$candidate" ] && still="$still $candidate"
done

if [ -n "$still" ]; then
  log "FAILED — Jamf agent still present at:$still"
  exit 1
fi

log "Jamf agent removed"
exit 0
