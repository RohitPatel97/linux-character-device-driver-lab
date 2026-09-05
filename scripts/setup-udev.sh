#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
source_rule="${repo_root}/packaging/udev/99-simple-char.rules"
target_rule="/etc/udev/rules.d/99-simple-char.rules"

if ((EUID != 0)); then
  echo "setup-udev.sh must run as root (use sudo)" >&2
  exit 1
fi

if ! getent group simplechar >/dev/null; then
  groupadd --system simplechar
fi
install -m 0644 -- "${source_rule}" "${target_rule}"
udevadm control --reload-rules
udevadm trigger --subsystem-match=simple_char || true

echo "installed ${target_rule}; add trusted users to group 'simplechar' if needed"

