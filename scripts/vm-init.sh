#!/bin/sh
# PID 1 in the disposable initramfs only; the host never executes this script.
[ "$$" -eq 1 ] || { echo "vm-init.sh must be the guest's PID 1" >&2; exit 2; }
export PATH=/bin:/usr/bin
mount -t devtmpfs devtmpfs /dev
exec </dev/console >/dev/console 2>&1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
export PYTHONHOME=/usr
export PYTHONDONTWRITEBYTECODE=1
cd /project || exit 1

echo "VM kernel: $(uname -r)"
if bash scripts/vm-tests.sh; then
  if dmesg | grep -E 'BUG:|WARNING:|Oops:|KASAN:|Kernel panic'; then
    echo SIMPLE_CHAR_VM_FAIL
  else
    echo SIMPLE_CHAR_VM_PASS
  fi
else
  dmesg
  echo SIMPLE_CHAR_VM_FAIL
fi
poweroff -f
