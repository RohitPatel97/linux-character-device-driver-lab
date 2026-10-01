# Verification log

This file records observed verification results and retains templates for
validation that has not been performed. The repository does not claim Linux
module-load or Raspberry Pi hardware validation until an actual result is
entered below. Host tests, mocked syscalls, compilation, and physical validation
are separate evidence categories.

## Host-only tests

### 2026-10-01 validation tooling update

| Field | Value |
|---|---|
| Date | 2026-10-01 America/Los_Angeles |
| Published implementation commit | `998a71718660f46bfdca8de35761a45d60e8838e` |
| Local platform/runtime | Windows / bundled CPython 3.12.14 |
| Local command/result | `python -m unittest discover -s tests -v`: PASS, 32 tests in 0.013 seconds; zero skipped |
| CI platform | GitHub Actions Ubuntu 24.04, x86_64 |
| CI tool versions | GCC 13.3.0 (`13.3.0-6ubuntu2~24.04.1`), Python 3.12.3, Bash 5.2.21, ShellCheck 0.9.0 |
| CI command | `make check` |
| CI observed result | PASS: C client compilation; 32 portable tests (0.009 s); five compiled C/Python ABI checks (0.001 s); syntax checks and ShellCheck; three shell regressions (0.031 s) |
| Local transcript | [`test-results/host-tests-2026-10-01.txt`](test-results/host-tests-2026-10-01.txt) |
| CI evidence | [Run 36889639768](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/36889639768); [retained excerpt](test-results/ci-checks-2026-10-01.txt) |

The shell regression reproduces the old batched `bash -n` command returning
success despite an invalid second script, then requires the fixed checker to
fail on that script. The native ABI checks compile the shared C header and
compare all ioctl values, struct sizes, and representative wire bytes with the
actual Python client. Unique layout-only sentinels in the stats probe are test
data, not observations from the driver or physical hardware.

The first CI attempt at `3a490a9` failed the new shell fixtures because their
`dirname` shim did not handle `--`; the corrected fixture passed at `998a717`.
The portable tests, native ABI checks, and kernel build already passed in that
first attempt. WSL/Bash/native Linux compilation remain unavailable locally;
the new native and shell cases were executed in CI. These results establish no
module-load, 32-bit compatibility execution, or physical GPIO/I2C validation.

### 2026-09-04 reliability update

| Field | Value |
|---|---|
| Date | 2026-09-04 |
| Source | Local working tree before GitHub publication |
| Platform/runtime | Windows; bundled CPython runtime |
| Command | `python -m unittest discover -s tests -v` |
| Baseline | 19 tests: one error because a source-contract test expected an obsolete cleanup label |
| Updated result | PASS — 32 tests in 0.006 seconds; no skipped host tests |
| Coverage added | 13 real-client tests with injected short I/O, EOF, errno failures, descriptor lifecycle failures, and concurrent positional writes |
| Evidence | [`test-results/host-tests-2026-09-04.txt`](test-results/host-tests-2026-09-04.txt) |

The new eight-case `tests/linux_integration.py` suite was authored but not run
against a loaded module. WSL reported that Windows Subsystem for Linux is not
installed; no Linux distro, matching headers, or test device was available.
The Windows result does not establish kernel compilation, Linux runtime
correctness, or GPIO/I2C electrical behavior. The kernel stats-lock change
subsequently compiled in the successful CI run below; its loaded-module
behavior still requires the opt-in Linux integration run.

### 2026-09-04 published CI host checks

| Field | Value |
|---|---|
| Date | 2026-09-04 America/Los_Angeles; CI logs dated 2026-09-05 UTC |
| Published commit | `721e08928ce16ff4dca6a7b16c50957bb57e443b` |
| Runner | GitHub Actions, Ubuntu 24.04 |
| Command | `make check` |
| Observed result | PASS — host-checks job succeeded; 32 Python host tests passed in 0.007 seconds, C client compiled, and configured shell checks passed |
| Evidence | [GitHub Actions run 33936329861](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/33936329861) |

These tests exercise the reference model, UAPI encoding, source contracts, and
actual Python client logic with injected syscall responses. They do not execute
the kernel module or inject faults into actual kernel user-copy operations.
The historical shell-check result records the checks as implemented at that
commit; it does not establish that every script received a Bash syntax check.

### Earlier baseline record

| Field | Value |
|---|---|
| Date | 2026-08-26 |
| Commit | Local working tree; repository not yet initialized/committed |
| Platform/Python | Microsoft Windows 11 Home build 26200 / CPython 3.12.13 |
| Command | Bundled Python runtime: `-m unittest discover -s tests -v` |
| Result | PASS — 19 tests; latest run completed in 0.007 seconds |
| Log/artifact | [`test-results/host-tests-2026-08-26.txt`](test-results/host-tests-2026-08-26.txt) |

## Kernel compilation

### 2026-10-01 validation tooling update

| Field | Value |
|---|---|
| Published implementation commit | `998a71718660f46bfdca8de35761a45d60e8838e` |
| Runner | GitHub Actions Ubuntu 24.04, x86_64 |
| Kernel headers | `/usr/src/linux-headers-6.8.0-146-generic` |
| Compiler | `gcc-13 (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| Commands | `make module KDIR=/usr/src/linux-headers-6.8.0-146-generic`; `modinfo kernel/simple_char.ko` |
| Observed result | PASS: module compiled and metadata inspection succeeded |
| `modinfo` vermagic | `6.8.0-146-generic SMP preempt mod_unload modversions` |
| Evidence | [CI run 36889639768](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/36889639768); [retained excerpt](test-results/ci-checks-2026-10-01.txt) |

The compiler executable-name warning described below also occurred here, with
identical compiler versions. No module was loaded by either job.

### 2026-09-04 published baseline

| Field | Value |
|---|---|
| Date | 2026-09-04 America/Los_Angeles; CI logs dated 2026-09-05 UTC |
| Published commit | `721e08928ce16ff4dca6a7b16c50957bb57e443b` |
| Runner | GitHub Actions, Ubuntu 24.04 |
| Kernel headers | `/usr/src/linux-headers-6.8.0-139-generic` |
| Compiler | `gcc-13 (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0` |
| Commands | `make module KDIR=/usr/src/linux-headers-6.8.0-139-generic`; `modinfo kernel/simple_char.ko` |
| Observed result | PASS — module compilation and `modinfo` succeeded; both CI jobs passed |
| `modinfo` vermagic | `6.8.0-139-generic SMP preempt mod_unload modversions` |
| Evidence | [GitHub Actions run 33936329861](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/33936329861) |

The build emitted a compiler-name warning: the module used `gcc-13`, whereas
the kernel compiler was named `x86_64-linux-gnu-gcc-13`. Both reported the
identical version above. This records successful compilation against that
specific header tree, not a loaded-module test or validation across the full
intended kernel-version range. The GitHub-hosted CI jobs did not load the
module, run the eight device integration cases, or validate GPIO/I2C hardware.

## Linux VM load/unload

| Field | Value |
|---|---|
| Date/operator | _not tested_ |
| Machine/kernel | _not tested_ |
| Signed module/Secure Boot state | _not tested_ |
| Commands | `scripts/load.sh`, `scripts/smoke-test.sh`, `scripts/repeat-load-unload.sh` |
| Expected | Device works and no stale state remains |
| Observed | _not tested_ |
| Sanitized log | _not tested_ |

## Raspberry Pi GPIO

Status: **not tested on physical hardware**.

Record board revision, GPIO numbering source, header pin, electrical load,
active polarity, instrument, initial/high/low/unload measurements, and logs.

## Raspberry Pi I2C

Status: **not tested on physical hardware**.

Record board revision, adapter, target part/address, register semantics,
analyzer or independent-read evidence, successful transfer, NACK failure, and
cleanup result.
