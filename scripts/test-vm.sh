#!/usr/bin/env bash
set -Eeuo pipefail

if (($# != 1)) || [[ ! -r "$1" ]]; then
  echo "usage: bash scripts/test-vm.sh /path/to/readable/vmlinuz (matching the built module)" >&2
  exit 2
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
kernel_image="$(realpath -- "$1")"
cd -- "${repo_root}"
python3 scripts/build-vm-initramfs.py build/test-initramfs.cpio.gz

# Software emulation needs neither /dev/kvm nor privileged host module loading.
# No disks, host directories, network interfaces, or credentials enter the VM.
timeout 240s qemu-system-x86_64 \
  -machine accel=tcg -cpu max -m 512M -smp 2 \
  -kernel "${kernel_image}" -initrd build/test-initramfs.cpio.gz \
  -append "console=ttyS0 rdinit=/init panic=-1 quiet simple_char_test_vm=1" \
  -display none -serial stdio -monitor none -nic none -no-reboot \
  | tee build/vm-console.log
grep -qx 'SIMPLE_CHAR_VM_PASS' <(tr -d '\r' < build/vm-console.log)
if grep -q 'SIMPLE_CHAR_VM_FAIL' build/vm-console.log; then
  exit 1
fi
