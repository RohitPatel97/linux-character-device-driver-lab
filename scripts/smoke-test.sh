#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
c_client="${repo_root}/user/simple-char-cli"
python_client="${repo_root}/user/simple_char_client.py"

[[ -c /dev/simple_char ]] || { echo "/dev/simple_char is not present" >&2; exit 1; }
[[ -x "${c_client}" ]] || { echo "C client is not built; run make client" >&2; exit 1; }

"${c_client}" roundtrip "c-client-smoke"
python3 "${python_client}" roundtrip "python-client-smoke"
"${c_client}" stats

