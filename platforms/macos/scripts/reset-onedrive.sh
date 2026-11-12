#!/bin/bash
#
# reset-onedrive.sh — reset the Microsoft OneDrive client, to recover from a broken
#   sync or a stuck account state.
#
# Published as a self-service ("packageless") software item — the end user runs it
# from Fleet Desktop > Self-service. Fleet runs scripts as root; the OneDrive reset
# must run in the console user's context, so we invoke it via launchctl asuser.

logFile="/Library/Logs/Config_ResetOneDrive.log"

fLog() {
  printf '%s: %s\n' "$(date)" "$1" | /usr/bin/tee -a "${logFile}"
}

resetCmd="/Applications/OneDrive.app/Contents/Resources/ResetOneDriveAppStandalone.command"

fLog "***Start*** reset-onedrive"

if [ ! -x "${resetCmd}" ]; then
  fLog "OneDrive reset command not found — is OneDrive installed? Nothing to do."
  exit 0
fi

loggedInUser="$(/usr/bin/stat -f%Su /dev/console)"
if [ -z "${loggedInUser}" ] || [ "${loggedInUser}" = "root" ]; then
  fLog "No console user logged in — nothing to do."
  exit 0
fi
uid="$(/usr/bin/id -u "${loggedInUser}")"

fLog "Resetting OneDrive for ${loggedInUser}."
/bin/launchctl asuser "${uid}" /usr/bin/sudo -u "${loggedInUser}" "${resetCmd}"

fLog "***Done***"
exit 0
