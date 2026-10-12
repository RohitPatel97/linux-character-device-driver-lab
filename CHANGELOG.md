# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Runtime completion — 2026-10-12

- Reuse a capacity-sized write staging buffer allocated at module load, removing
  allocation/free operations from each write while preserving partial-copy
  behavior. Persistent buffer memory doubles; no speedup is claimed without
  benchmark evidence.
- Add a disposable QEMU guest that boots the kernel matching the built module,
  runs the eight device integration cases, four protected-page copy-fault cases,
  both clients, invalid-parameter cleanup, busy unload, and 25 lifecycle cycles.
- Preserve unexpected symlinks during unload, with a VM regression case.
- Retain VM console artifacts and require a success marker plus clean kernel
  diagnostics. Avoid duplicate CI jobs for a branch push and its pull request.
- Reduce the README to a short project guide; preserve design, usage, and testing
  details in dedicated documentation files.

### Changed

- Shell syntax checking now invokes Bash once per file, so a malformed later
  script cannot pass through the no-ShellCheck fallback.
- `make check` now includes compiled C/Python UAPI comparisons and shell-checker
  regressions. CI records host tool versions for reproducible evidence.
- README includes a portable verification quick start, individual check targets,
  and the previously published kernel-build evidence.
- Python buffer I/O uses `pread`/`pwrite` so concurrent users of one descriptor
  do not race through a shared file position.
- Kernel statistics capture related I/O totals and logical size while holding
  the device mutex.
- Context-manager entry rejects an already-open client; close invalidates the
  descriptor even when the syscall reports an error.
- Corrected the lifecycle source-contract test and diagram to match the
  existing callback-publication order.

### Added

- A C UAPI probe and five native ABI checks for sizes, ioctl values, statistics
  decoding, and GPIO/I2C wire layouts; no loaded module is needed.
- Three unprivileged shell-checker regressions for later-file syntax errors,
  paths containing spaces, optional ShellCheck, and linter failure propagation.
- `PartialWriteError` exposes committed-byte count, next offset, and original
  errno when an all-bytes write fails after partial progress.
- Thirteen client regression tests with injected syscall failures, short I/O,
  EOF, descriptor lifecycle errors, and concurrent positional writes.
- Eight explicitly opted-in real Linux device integration cases, now executed
  in the recorded disposable QEMU guest.
- A README problem/solution/test matrix and updated verification evidence.

### Planned

- Record Linux VM load/unload evidence after it is actually collected.
- Record Raspberry Pi GPIO/I2C evidence after controlled hardware validation.

## [1.0.0] - 2026-08-26

### Added

- Dynamically registered `/dev/simple_char` loadable kernel module.
- Bounded, positional, mutex-protected reads and writes with partial-copy
  handling.
- Fixed-width stats, clear, GPIO, and I2C ioctls.
- Opt-in, parameterized, capability-gated GPIO and I2C hooks.
- C and Python clients.
- Build, load, unload, repeated lifecycle, smoke-test, and udev setup scripts.
- Host-only concurrency/boundary model tests and UAPI/source-contract tests.
- GitHub Actions jobs for client checks and Ubuntu kernel-header compilation.
- Design, hardware bring-up, verification, security, and contribution docs.
