#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cycles="${1:-10}"

if [[ ! "${cycles}" =~ ^[1-9][0-9]*$ ]]; then
  echo "usage: sudo bash scripts/repeat-load-unload.sh [positive-cycle-count]" >&2
  exit 2
fi
if ((EUID != 0)); then
  echo "repeat-load-unload.sh must run as root (use sudo)" >&2
  exit 1
fi

for ((cycle = 1; cycle <= cycles; cycle++)); do
  echo "cycle ${cycle}/${cycles}: load"
  bash "${script_dir}/load.sh"
  [[ -c /dev/simple_char ]]
  echo "cycle ${cycle}/${cycles}: unload"
  bash "${script_dir}/unload.sh"
  [[ ! -e /dev/simple_char ]]
done

echo "completed ${cycles} clean load/unload cycles"

