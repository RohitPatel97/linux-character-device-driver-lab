# Linux character device project workflow

Publication target: `linux-character-device-driver-lab`.
This is the ongoing work record for the portfolio project described in
[`README.md`](README.md). Record completed work with commands and observed
results before updating resume claims.

## Completed reliability update — 2026-09-04

- Replaced the Python client's `seek`/I/O sequence with positional
  `pread`/`pwrite`, preserving shared descriptor position across callers.
- Added `PartialWriteError` with original errno, committed prefix length, and
  next offset after a later syscall fails. Zero-progress writes return `EIO`.
- Rejected nested client entry and invalidated descriptors before closing.
- Moved related kernel I/O-counter and size snapshots under the device mutex.
- Corrected a stale lifecycle source-contract assertion and the README's
  lifecycle diagram to match the existing callback-publication order.
- Added 13 client syscall regression tests and eight separately opted-in
  Linux integration cases, plus a README problem/solution/test matrix.

## Evidence and commands

| Check | Command | Observed result |
|---|---|---|
| Original host suite | `python -m unittest discover -s tests -v` | 19 cases; one stale lifecycle-label error |
| Updated host suite | `python -m unittest discover -s tests -v` | 32 passed, zero skipped, 0.006 seconds |
| Linux environment availability | `wsl.exe --list --quiet` | WSL reported not installed; no Linux runtime available |
| Kernel compile | `make module KDIR=/path/to/prepared/linux-headers` | Not run locally; CI job configured |
| Real device integration | `sudo python3 -m tests.linux_integration --device /dev/simple_char --allow-clear` | Authored, not run against a loaded module |

See [`docs/verification-log.md`](docs/verification-log.md) and the
[host test transcript excerpt](docs/test-results/host-tests-2026-09-04.txt).
The host suite tests the reference model, UAPI encoding, source contracts, and
actual Python client logic with injected syscalls. It does not execute the
kernel module. Publication and GitHub Actions outcomes should be appended
after they are observed.

## Next three tasks

1. Record the published commit and successful GitHub Actions client, script,
   and kernel-header build results, including the exact compiler/header
   versions and run link in the verification log.
2. On a disposable Linux VM, build for its running kernel, run the eight
   integration cases with both hardware hooks disabled, then exercise
   repeated load/unload and busy-device behavior. Preserve sanitized logs.
3. On a Raspberry Pi with documented wiring and an appropriate test target,
   execute [`docs/hardware-bringup.md`](docs/hardware-bringup.md); record GPIO
   polarity and I2C success/NACK evidence before claiming hardware validation.

## Resume evidence boundary

Supported now: C/Linux device-driver implementation, bounded I/O, mutex
synchronization, fixed-width ioctl ABI, Python clients, fault injection,
regression testing, concurrency tests, and 32 passing host tests.

Pending actual evidence: successful kernel build, loaded-module integration,
Raspberry Pi bring-up, GPIO signals, I2C bus transfers, and performance claims.
