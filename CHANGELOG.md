# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Python buffer I/O uses `pread`/`pwrite` so concurrent users of one descriptor
  do not race through a shared file position.
- Kernel statistics capture related I/O totals and logical size while holding
  the device mutex.
- Context-manager entry rejects an already-open client; close invalidates the
  descriptor even when the syscall reports an error.
- Corrected the lifecycle source-contract test and diagram to match the
  existing callback-publication order.

### Added

- `PartialWriteError` exposes committed-byte count, next offset, and original
  errno when an all-bytes write fails after partial progress.
- Thirteen client regression tests with injected syscall failures, short I/O,
  EOF, descriptor lifecycle errors, and concurrent positional writes.
- Eight explicitly opted-in real Linux device integration cases. These remain
  unrun until a loaded-module test environment is available.
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
