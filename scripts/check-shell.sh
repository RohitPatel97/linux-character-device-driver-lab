#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

mapfile -d '' scripts < <(find "${script_dir}" -maxdepth 1 -type f -name '*.sh' -print0)
for script in "${scripts[@]}"; do
  bash -n "${script}"
done

if command -v shellcheck >/dev/null 2>&1; then
  shellcheck "${scripts[@]}"
else
  echo "shellcheck not installed; bash syntax check passed" >&2
fi

