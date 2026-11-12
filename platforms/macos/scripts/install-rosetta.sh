#!/bin/bash
#
# install-rosetta.sh — ensure Rosetta 2 is installed on Apple Silicon Macs.
#
# Paired with the "macOS - Rosetta 2 installed" policy (rosetta-installed.yml): a host fails
# that policy when it is a macOS 27+ Apple Silicon machine missing the Rosetta runtime, and
# Fleet then runs this script.
#
# Success is the runtime file, not softwareupdate's exit code: `softwareupdate
# --install-rosetta` can exit 0 without installing anything (for example when Apple's
# catalogue is unreachable). The check below is the same condition the policy tests, so the
# script and the policy always agree and Fleet does not re-run it forever.
#
# It may run during provisioning while the network is still settling, hence one retry.
# Idempotent: exits 0 on Intel or when Rosetta is already present.

logFile="/Library/Logs/Config_InstallRosetta.log"
rosettaRuntime="/Library/Apple/usr/libexec/oah/libRosettaRuntime"
retryDelay=30      # seconds; one pause between the two attempts
attempts=2

fLog() {
  printf '%s: %s\n' "$(date)" "$1" | /usr/bin/tee -a "${logFile}"
}

# The one condition that counts, and the one the policy queries.
haveRosetta() {
  [ -f "${rosettaRuntime}" ]
}

# Extra signal for the log only — never a success gate. If the runtime file is present but
# translation does not work yet, a restart is usually what is outstanding, and gating on this
# would fail a host that is in fact fine.
logTranslationState() {
  if /usr/bin/arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
    fLog "Translation check: x86_64 binaries run."
  else
    fLog "Translation check: x86_64 execution not working yet — a restart is probably outstanding."
  fi
}

fLog "***Start*** install-rosetta"

# Apple Silicon only — Rosetta does not apply to Intel. hw.optional.arm64 is the
# definitive test and is unaffected by binary translation.
if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" != "1" ]; then
  fLog "Not Apple Silicon — nothing to do."
  exit 0
fi

if haveRosetta; then
  fLog "Rosetta already installed — nothing to do."
  exit 0
fi

attempt=1
while [ "${attempt}" -le "${attempts}" ]; do
  fLog "Installing Rosetta 2 (attempt ${attempt} of ${attempts})..."

  # Output is teed so the catalogue error, if there is one, lands in the log. The exit code of
  # this pipeline is deliberately ignored: it is tee's, and softwareupdate's own is not
  # trustworthy either. The verification below is what decides.
  /usr/sbin/softwareupdate --install-rosetta --agree-to-license 2>&1 | /usr/bin/tee -a "${logFile}"

  if haveRosetta; then
    fLog "Rosetta runtime present after attempt ${attempt}."
    logTranslationState
    fLog "***End*** install-rosetta (success)"
    exit 0
  fi

  if [ "${attempt}" -lt "${attempts}" ]; then
    fLog "Runtime still absent — waiting ${retryDelay}s and retrying. The host may still be provisioning."
    sleep "${retryDelay}"
  fi

  attempt=$((attempt + 1))
done

fLog "Rosetta install FAILED — ${rosettaRuntime} still absent after ${attempts} attempts."
fLog "***End*** install-rosetta (failure)"
exit 1
