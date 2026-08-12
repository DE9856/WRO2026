#!/usr/bin/env bash
#
# disable_wifi.sh
# WRO 2026 Future Engineers — physically-run-once setup script for the
# Raspberry Pi that disables onboard Wi-Fi at the OS/boot-config level.
#
# WHY THIS EXISTS
#   WRO §11.10 prohibits any active RF/Bluetooth/Wi-Fi during a round.
#   docs/index.html's rules-compliance matrix claims "Pi's onboard Wi-Fi
#   disabled in /boot/config.txt" -- but until this script existed, that
#   was a doc-only claim with no runnable artifact backing it, which is
#   exactly the kind of gap the WRO §7 hard-copy/GitHub review process is
#   meant to catch. This script is that missing artifact: a judge (or
#   the team, before a vehicle check) can read exactly what it does
#   instead of trusting a sentence in a build guide.
#
# WHAT IT DOES
#   Appends `dtoverlay=disable-wifi` (and, for completeness,
#   `dtoverlay=disable-bt`, since WRO also prohibits Bluetooth) to
#   /boot/config.txt or /boot/firmware/config.txt, whichever exists on
#   this Pi OS version, if the overlay line is not already present.
#   Idempotent: safe to re-run.
#
# WHAT IT DELIBERATELY DOES NOT DO
#   - It does not remove/uninstall any wireless hardware. HC-05/ESP8266
#     modules mentioned in docs/index.html's competition-day checklist
#     must still be PHYSICALLY removed from the board -- no script can
#     do that.
#   - It does not run automatically. This is a one-time setup step the
#     team runs on the actual Pi, not part of main.py's runtime.
#
# USAGE
#   sudo bash setup/disable_wifi.sh
#   sudo reboot
#   # Verify:
#   iwconfig 2>&1 | grep -i "no wireless" || echo "WARNING: wlan interface still present"
#
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "This script edits /boot/config.txt and must be run with sudo." >&2
  echo "Usage: sudo bash setup/disable_wifi.sh" >&2
  exit 1
fi

CONFIG_TXT=""
for candidate in /boot/firmware/config.txt /boot/config.txt; do
  if [[ -f "${candidate}" ]]; then
    CONFIG_TXT="${candidate}"
    break
  fi
done

if [[ -z "${CONFIG_TXT}" ]]; then
  echo "Could not find /boot/config.txt or /boot/firmware/config.txt." >&2
  echo "This script is intended to run ON the Raspberry Pi itself, not on a" >&2
  echo "development laptop -- if you're prepping an SD card image on another" >&2
  echo "machine, mount the boot partition and point CONFIG_TXT at it manually." >&2
  exit 1
fi

echo "Using boot config: ${CONFIG_TXT}"

add_overlay_if_missing() {
  local overlay_line="$1"
  if grep -qxF "${overlay_line}" "${CONFIG_TXT}"; then
    echo "  already present: ${overlay_line}"
  else
    echo "  appending: ${overlay_line}"
    printf '\n# WRO 2026 -- Future Engineers -- disable onboard wireless (WRO 11.10)\n%s\n' \
      "${overlay_line}" >> "${CONFIG_TXT}"
  fi
}

add_overlay_if_missing "dtoverlay=disable-wifi"
add_overlay_if_missing "dtoverlay=disable-bt"

echo
echo "Done. A reboot is required for this to take effect:"
echo "  sudo reboot"
echo
echo "After reboot, verify with:"
echo "  iwconfig            # should report 'no wireless extensions' for wlan0"
echo "  bluetoothctl show   # should fail to find a controller"
echo
echo "Reminder (not automated by this script -- see docs/index.html Section 12):"
echo "  - Physically remove any HC-05 / ESP8266 / other RF module from the board."
echo "  - Judges may inspect the vehicle and code to confirm wireless is unused (WRO 11.10)."
