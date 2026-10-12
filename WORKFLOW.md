# Linux character device project workflow

Publication target: `linux-character-device-driver-lab`.
This is the ongoing work record for the portfolio project described in
[`README.md`](README.md). Record completed work with commands and observed
results before updating resume claims.

## Runtime completion and optimization — 2026-10-12

- **Problem:** loaded-module and actual user-copy fault behavior had never been
  exercised. Every write allocated and freed temporary memory while holding the
  device mutex. Unload cleanup could remove a symlink to a character device.
- **Solution:** reuse a mutex-protected staging buffer allocated at module load;
  preserve symlinks during unload; add a disposable QEMU Linux guest to CI with
  matching kernel/image headers, no network or host filesystem mounts, and
  retained console evidence. Avoid duplicate push/PR CI runs.
- **Regression cases:** eight real-device integration cases, four protected-page
  read/write fault cases, invalid-parameter cleanup, busy-device removal,
  25 load/unload cycles, and unexpected-symlink preservation.
- **Observed result:** all 40 host checks passed in CI (32 portable tests, five
  native ABI comparisons, three shell regressions), as did kernel compilation
  and `modinfo`. The x86_64 QEMU guest booted Linux `6.8.0-146-generic`; eight
  device tests passed in 0.332 seconds, all four user-copy fault cases passed,
  both clients round-tripped, and all lifecycle checks passed. Cross-page reads
  and writes each transferred 32 bytes; fully inaccessible pages returned
  `EFAULT` without progress. No BUG/WARNING/Oops/KASAN/panic was reported.
- **Published implementation:**
  [`c23a68fd4b3b753b9065f5e3880115e46146921c`](https://github.com/RohitPatel97/linux-character-device-driver-lab/commit/c23a68fd4b3b753b9065f5e3880115e46146921c);
  [successful CI run 38287500842](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/38287500842).
  Retained [VM console](docs/test-results/vm-tests-2026-10-12.txt) and
  [CI excerpt](docs/test-results/ci-checks-2026-10-12.txt).
- **Optimization tradeoff:** writes perform no heap allocation after module
  initialization, in exchange for one additional capacity-sized buffer (4 KiB
  by default, at most 1 MiB). No throughput improvement is claimed without a
  benchmark.
- **Remaining limits:** physical GPIO/I2C and 32-bit compatibility execution
  require separate environments. Performance remains unmeasured; VM execution
  covers one x86_64 kernel configuration. WSL is still unavailable locally.
- **Documentation:** reduced the README from its long reference format to a
  concise project guide, preserving design, usage, and testing details in
  `docs/design.md`, `docs/usage.md`, and `docs/testing.md`.

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
- **Observed Linux result:** `make check` passed all 40 cases: 32 portable
  tests, five compiled C/Python ABI comparisons, and three shell regressions.
  C client compilation, script syntax checks, and ShellCheck passed. Kernel
  compilation and `modinfo` passed with Ubuntu 24.04 headers
  `6.8.0-146-generic`. The initial CI run caught a missing `--` option delimiter
  handler in the test fixture's `dirname` shim; the fixture was corrected before
  the successful run. See the [CI excerpt](docs/test-results/ci-checks-2026-10-01.txt).
- **Remaining limits:** WSL is still not installed locally. Loaded-module,
  faulting-user-page, 32-bit compatibility, and physical GPIO/I2C validation
  remain unperformed. Native ABI results cover the CI host's x86_64 ABI.
- **Published implementation commit:**
  [`998a71718660f46bfdca8de35761a45d60e8838e`](https://github.com/RohitPatel97/linux-character-device-driver-lab/commit/998a71718660f46bfdca8de35761a45d60e8838e).
  Both jobs passed in
  [CI run 36889639768](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/36889639768).

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

## September 4 baseline evidence and commands

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

## Core completion and optional next validation

The memory-device implementation, host verification, loaded-module integration,
actual user-copy faults, and lifecycle acceptance criteria are complete for the
recorded VM. Optional validation beyond that scope:

1. On a Raspberry Pi with documented wiring and an appropriate test target,
   execute [`docs/hardware-bringup.md`](docs/hardware-bringup.md); record GPIO
   polarity and I2C success/NACK evidence before claiming hardware validation.
   Acceptance: board/wiring and measurement method documented, safe initial
   and cleanup levels observed, and successful transfer plus controlled adapter
   error recorded.
2. Run a 32-bit client against a 64-bit kernel. Acceptance: ioctl payloads,
   error propagation, and buffer I/O pass with compat mode, with compiler and
   kernel configuration recorded.
3. Measure write-path performance only if making performance claims. Acceptance:
   identical hardware/kernel/workloads, before/after results, repeated trials,
   and the persistent-memory tradeoff are recorded.

## Resume evidence boundary

Supported now: C/Linux device-driver implementation, bounded I/O, mutex
synchronization, fixed-width ioctl ABI, Python clients, injected client syscall
failures, regression testing, concurrency tests, 32 passing portable host tests,
five native C/Python ABI checks, three shell-checker regressions, kernel
compilation/metadata inspection, eight loaded-device cases, four actual
protected-page faults, and 25 lifecycle cycles in a QEMU Linux guest.

Pending actual evidence: 32-bit compatibility execution, Raspberry Pi bring-up,
GPIO signals, I2C bus transfers, and performance claims.

Future updates must record the problem, solution, regression case, observed
result, remaining limits, and published commit before expanding resume claims.
