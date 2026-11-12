#!/bin/bash
#
# show-bluetooth-menubar.sh — show the Bluetooth icon in the menu bar for every local user.
#
# Writes the Control Center ByHost preference (Bluetooth = 18 means "show in menu bar") into
# each user's home. Takes effect at the user's next login (or after `killall ControlCenter`).
# Fleet runs scripts as root, so each write runs as the owning user.

logFile="/Library/Logs/Config_ShowBluetoothMenubar.log"

fLog() {
  printf '%s: %s\n' "$(date)" "$1" | /usr/bin/tee -a "${logFile}"
}

fLog "***Start*** show-bluetooth-menubar"

for userHome in /Users/*; do
  userName="$(/usr/bin/basename "${userHome}")"
  [ "${userName}" = "Shared" ] && continue
  if [ -d "${userHome}/Library/Preferences" ]; then
    fLog "Enabling Bluetooth menu bar icon for ${userName}"
    /usr/bin/sudo -u "${userName}" /usr/bin/defaults write "${userHome}/Library/Preferences/ByHost/com.apple.controlcenter.plist" Bluetooth -int 18
  else
    fLog "${userHome} skipped (no Library/Preferences)"
  fi
done

fLog "***Done***"
exit 0
