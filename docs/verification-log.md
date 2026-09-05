# Verification log

This file is intentionally an evidence template. The repository does not claim
Linux module-load or Raspberry Pi hardware validation until an actual result is
entered below.

## Host-only tests

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
requires the configured CI compile and the opt-in Linux integration run.

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

| Field | Value |
|---|---|
| Date | _not recorded_ |
| Commit | _not recorded_ |
| Distribution/kernel headers | _not recorded_ |
| Compiler | _not recorded_ |
| Command | `make module KDIR=...` |
| Result | _not recorded_ |
| `modinfo`/CI link | _not recorded_ |

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
