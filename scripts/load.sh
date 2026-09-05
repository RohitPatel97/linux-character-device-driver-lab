#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
module_path="${repo_root}/kernel/simple_char.ko"
device_node="/dev/simple_char"
buffer_size=4096
enable_gpio=0
gpio_num=-1
gpio_active_low=0
enable_i2c=0
i2c_bus=-1
i2c_addr=0

usage() {
  cat <<'USAGE'
Usage: sudo bash scripts/load.sh [OPTIONS]

  --module PATH           Module path (default: kernel/simple_char.ko)
  --buffer-size BYTES     64..1048576 (default: 4096)
  --enable-gpio           Opt in to the GPIO hook
  --gpio-num NUMBER       Legacy global GPIO number
  --gpio-active-low       Invert logical output
  --enable-i2c            Opt in to the I2C hook
  --i2c-bus NUMBER        I2C adapter number
  --i2c-addr ADDRESS      7-bit address, decimal or 0x-prefixed
  -h, --help              Show help

Hardware hooks remain disabled unless their --enable flag is present.
USAGE
}

is_decimal() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

is_signed_decimal() {
  [[ "$1" =~ ^-?[0-9]+$ ]]
}

while (($#)); do
  case "$1" in
    --module)
      (($# >= 2)) || { echo "--module requires a value" >&2; exit 2; }
      module_path="$2"
      shift 2
      ;;
    --buffer-size)
      (($# >= 2)) || { echo "--buffer-size requires a value" >&2; exit 2; }
      buffer_size="$2"
      shift 2
      ;;
    --enable-gpio)
      enable_gpio=1
      shift
      ;;
    --gpio-num)
      (($# >= 2)) || { echo "--gpio-num requires a value" >&2; exit 2; }
      gpio_num="$2"
      shift 2
      ;;
    --gpio-active-low)
      gpio_active_low=1
      shift
      ;;
    --enable-i2c)
      enable_i2c=1
      shift
      ;;
    --i2c-bus)
      (($# >= 2)) || { echo "--i2c-bus requires a value" >&2; exit 2; }
      i2c_bus="$2"
      shift 2
      ;;
    --i2c-addr)
      (($# >= 2)) || { echo "--i2c-addr requires a value" >&2; exit 2; }
      i2c_addr="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ((EUID != 0)); then
  echo "load.sh must run as root (use sudo)" >&2
  exit 1
fi
if [[ ! -f "${module_path}" ]]; then
  echo "module not found: ${module_path}; run make module first" >&2
  exit 1
fi
if ! is_decimal "${buffer_size}"; then
  echo "buffer size must be a decimal value from 64 through 1048576" >&2
  exit 2
fi
buffer_size=$((10#${buffer_size}))
if ((buffer_size < 64 || buffer_size > 1048576)); then
  echo "buffer size must be a decimal value from 64 through 1048576" >&2
  exit 2
fi
if ! is_signed_decimal "${gpio_num}" || ! is_signed_decimal "${i2c_bus}"; then
  echo "GPIO and I2C bus numbers must be decimal integers" >&2
  exit 2
fi
if [[ "${gpio_num}" == -* ]]; then
  gpio_num_digits="${gpio_num#-}"
  gpio_num=$(( -(10#${gpio_num_digits}) ))
else
  gpio_num=$((10#${gpio_num}))
fi
if [[ "${i2c_bus}" == -* ]]; then
  i2c_bus_digits="${i2c_bus#-}"
  i2c_bus=$(( -(10#${i2c_bus_digits}) ))
else
  i2c_bus=$((10#${i2c_bus}))
fi
if [[ ! "${i2c_addr}" =~ ^(0[xX][0-9a-fA-F]+|[0-9]+)$ ]]; then
  echo "I2C address must be decimal or 0x-prefixed hexadecimal" >&2
  exit 2
fi
if [[ "${i2c_addr}" =~ ^0[xX] ]]; then
  i2c_addr=$((16#${i2c_addr:2}))
else
  i2c_addr=$((10#${i2c_addr}))
fi
if ((enable_gpio == 1 && gpio_num < 0)); then
  echo "--enable-gpio requires a non-negative --gpio-num" >&2
  exit 2
fi
if ((enable_i2c == 1)); then
  if ((i2c_bus < 0 || i2c_addr < 3 || i2c_addr > 119)); then
    echo "--enable-i2c requires a non-negative bus and a 7-bit address from 0x03 to 0x77" >&2
    exit 2
  fi
fi
if [[ -d /sys/module/simple_char ]]; then
  echo "simple_char is already loaded; unload it before changing parameters" >&2
  exit 1
fi
if [[ -e "${device_node}" || -L "${device_node}" ]]; then
  echo "refusing to load while an existing path occupies ${device_node}" >&2
  exit 1
fi

parameters=(
  "buffer_size=${buffer_size}"
  "enable_gpio=${enable_gpio}"
  "gpio_num=${gpio_num}"
  "gpio_active_low=${gpio_active_low}"
  "enable_i2c=${enable_i2c}"
  "i2c_bus=${i2c_bus}"
  "i2c_addr=${i2c_addr}"
)

insmod "${module_path}" "${parameters[@]}"

for _ in {1..50}; do
  [[ -c "${device_node}" && -e /sys/class/simple_char/simple_char/dev ]] && break
  sleep 0.1
done

if [[ ! -c "${device_node}" || ! -e /sys/class/simple_char/simple_char/dev ]]; then
  echo "module loaded but ${device_node} did not appear; rolling back" >&2
  rmmod simple_char || true
  exit 1
fi

echo "loaded simple_char at ${device_node}"
cat /sys/class/simple_char/simple_char/dev
