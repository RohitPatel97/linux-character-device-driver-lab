#!/usr/bin/env bash
set -Eeuo pipefail

device_node="/dev/simple_char"

if ((EUID != 0)); then
  echo "unload.sh must run as root (use sudo)" >&2
  exit 1
fi

if [[ -d /sys/module/simple_char ]]; then
  rmmod simple_char
else
  echo "simple_char is not loaded"
fi

for _ in {1..50}; do
  [[ ! -e "${device_node}" && ! -L "${device_node}" ]] && break
  sleep 0.1
done

# Remove only a stale character node with the exact expected name, and only
# after sysfs confirms the module is gone. Regular files and symlinks are never
# touched.
if [[ ! -d /sys/module/simple_char && -c "${device_node}" ]]; then
  rm -f -- "${device_node}"
fi

if [[ -e "${device_node}" || -L "${device_node}" || -d /sys/class/simple_char ]]; then
  echo "cleanup incomplete: device state remains" >&2
  exit 1
fi

echo "simple_char unloaded cleanly"
