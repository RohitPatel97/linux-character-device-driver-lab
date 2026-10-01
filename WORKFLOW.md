# Linux character device project workflow

Publication target: `linux-character-device-driver-lab`.
This is the ongoing work record for the portfolio project described in
[`README.md`](README.md). Record completed work with commands and observed
results before updating resume claims.

## Verification tooling update — 2026-10-01

- **Problem:** `bash -n` was invoked with several filenames, so Bash parsed only
  the first file. With ShellCheck absent, a syntax error in a later script could
  pass. Python-only ABI constants also did not compare against the compiled C
  header, and the documentation still treated successful CI compilation as
  pending.
- **Solution:** syntax-check each script individually; add a C UAPI probe and
  five C/Python ABI comparisons; include three isolated shell-checker
  regressions in `make check`; record CI tool versions; update the README's
  quick start, check targets, and evidence boundaries.
- **Regression cases:** a valid-first/invalid-second fixture reproduces the old
  syntax-check false success and must fail with the fixed checker; spaced paths
  and ShellCheck failures are covered. Native ABI checks compare actual C ioctl
  values, structure sizes, and byte layouts, including 64-bit counters and a
  signed errno.
- **Observed local result:** 32 portable host tests passed, zero skipped, in
  0.013 seconds on Windows. New Python runners compile successfully. The shell
  runner explicitly exits 2 when Bash is unavailable. See the
  [host transcript](docs/test-results/host-tests-2026-10-01.txt).
- **Remaining limits:** new native ABI and shell execution await Linux CI at
  this point in the record. WSL is still not installed locally. Loaded-module,
  faulting-user-page, 32-bit compatibility, and physical GPIO/I2C validation
  remain unperformed.
- **Published commit and CI:** to be recorded after this update is pushed and
  the Linux checks complete.

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
| Kernel compile | `make module KDIR=/usr/src/linux-headers-6.8.0-139-generic` | Passed in published GitHub CI; not run locally |
| Real device integration | `sudo python3 -m tests.linux_integration --device /dev/simple_char --allow-clear` | Authored, not run against a loaded module |

See [`docs/verification-log.md`](docs/verification-log.md) and the
[host test transcript excerpt](docs/test-results/host-tests-2026-09-04.txt).
The host suite tests the reference model, UAPI encoding, source contracts, and
actual Python client logic with injected syscalls. It does not execute the
kernel module. The September 4 update was published as
[`721e08928ce16ff4dca6a7b16c50957bb57e443b`](https://github.com/RohitPatel97/linux-character-device-driver-lab/commit/721e08928ce16ff4dca6a7b16c50957bb57e443b).
[CI run 33936329861](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/33936329861)
passed the C client build, 32 host tests, configured shell checks, kernel-module
compilation, and `modinfo`. The verification log records the exact compiler and
header versions and the historical shell-checker's coverage limit.

## Next three tasks

1. On a disposable Linux VM, build for its running kernel and run the eight
   integration cases with both hardware hooks disabled. Acceptance: all eight
   pass, 25 load/unload cycles leave no stale resources, and removal while a
   descriptor is open fails as busy then succeeds after closure. Retain logs,
   kernel version, commands, and commit.
2. Add actual Linux user-copy fault tests on the disposable VM. Acceptance:
   faulting pages produce short I/O or `EFAULT` as appropriate, committed bytes
   and untouched data are verified, and counters/`last_error` match the result.
   Keep this evidence distinct from injected Python syscall responses.
3. On a Raspberry Pi with documented wiring and an appropriate test target,
   execute [`docs/hardware-bringup.md`](docs/hardware-bringup.md); record GPIO
   polarity and I2C success/NACK evidence before claiming hardware validation.
   Acceptance: board/wiring and measurement method documented, safe initial
   and cleanup levels observed, and successful transfer plus controlled adapter
   error recorded.

## Resume evidence boundary

Supported now: C/Linux device-driver implementation, bounded I/O, mutex
synchronization, fixed-width ioctl ABI, Python clients, injected client syscall
failures, regression testing, concurrency tests, 32 passing portable host tests,
and kernel compilation/metadata inspection in GitHub CI.

Pending actual evidence: loaded-module integration, kernel user-copy fault
injection, 32-bit compatibility execution, Raspberry Pi bring-up, GPIO signals,
I2C bus transfers, and performance claims.

Future updates must record the problem, solution, regression case, observed
result, remaining limits, and published commit before expanding resume claims.
