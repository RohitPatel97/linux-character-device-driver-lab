#!/usr/bin/env bash
set -Eeuo pipefail

# Guard the destructive lifecycle tests against accidental host invocation.
if [[ ! -f /init || ! -d /project ]] || ! grep -qw 'simple_char_test_vm=1' /proc/cmdline; then
  echo "vm-tests.sh runs only inside the disposable project initramfs" >&2
  exit 2
fi

assert_unloaded() {
  [[ ! -e /dev/simple_char && ! -L /dev/simple_char ]]
  [[ ! -d /sys/module/simple_char && ! -d /sys/class/simple_char ]]
}

assert_unloaded
for size in 1 1048577; do
  if insmod kernel/simple_char.ko "buffer_size=${size}"; then
    echo "invalid capacity unexpectedly loaded" >&2
    exit 1
  fi
  assert_unloaded
done
echo "PASS: invalid module parameters leave no resources"

bash scripts/load.sh --buffer-size 16384
bash scripts/smoke-test.sh
python3 -m tests.linux_integration --device /dev/simple_char --allow-clear
./build/user-copy-faults /dev/simple_char --allow-clear

exec 9<>/dev/simple_char
if rmmod simple_char; then
  echo "unload unexpectedly succeeded with an open descriptor" >&2
  exit 1
fi
[[ -d /sys/module/simple_char && -c /dev/simple_char ]]
exec 9>&-
bash scripts/unload.sh
assert_unloaded
echo "PASS: busy module remains loaded until the descriptor closes"

bash scripts/repeat-load-unload.sh 25
assert_unloaded

ln -s /dev/null /dev/simple_char
if bash scripts/unload.sh; then
  echo "symlink cleanup unexpectedly reported success" >&2
  exit 1
fi
[[ -L /dev/simple_char ]]
rm -- /dev/simple_char
assert_unloaded
echo "PASS: unload preserves an unexpected symlink"
