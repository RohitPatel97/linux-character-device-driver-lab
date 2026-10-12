# Linux Character Device Driver

[![CI](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/workflows/ci.yml)

A Linux kernel module exposing `/dev/simple_char`: bounded positional I/O,
mutex-protected shared data, safe user/kernel copies, and a fixed-width ioctl
ABI. Includes C and Python clients, lifecycle scripts, and reproducible tests.
Optional GPIO/I2C hooks remain disabled unless explicitly enabled.

## Project status

The core memory-device project is implemented and validated in an x86_64 Linux
VM. [October 12 CI](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/38287500842)
passed on kernel `6.8.0-146-generic` at implementation commit `c23a68f`.

| Evidence | Status |
|---|---|
| Portable host tests | 32 passed |
| Compiled C/Python ABI checks | Five passed |
| Shell checker regressions | Three passed |
| C client, script lint, kernel compilation and `modinfo` | Passed in CI |
| Loaded-module integration | Eight passed in QEMU |
| Protected-page read/write faults | Four passed; short copies preserved untouched data |
| Lifecycle and cleanup | 25 cycles, invalid parameters, busy unload, and symlink preservation passed |
| Physical Raspberry Pi GPIO/I2C and 32-bit compatibility execution | Not validated |

[Verification evidence](docs/verification-log.md) records the tested commits,
commands, kernel versions, and results. [WORKFLOW.md](WORKFLOW.md) tracks changes
and remaining validation. Host tests, virtual-machine execution, and physical
hardware results are separate evidence categories.

## Run the host checks

Python 3.11+ is sufficient for the portable suite; no device or root access is
needed. On Windows, use `python` or `py -3` if `python3` is unavailable.

```bash
git clone https://github.com/RohitPatel97/linux-character-device-driver-lab.git
cd linux-character-device-driver-lab
python3 -m unittest discover -s tests -v
```

For all host checks on Debian/Ubuntu:

```bash
sudo apt-get update
sudo apt-get install build-essential python3 shellcheck
make check
```

This builds the C client and fault harness, compares the Python client against
the compiled C header, and checks every shell script. It never loads a module.

## Build and try the device

Use a disposable Linux test machine with headers matching its running kernel.
The following path keeps hardware disabled and erases the shared RAM buffer:

```bash
sudo apt-get install build-essential python3 linux-headers-"$(uname -r)"
make all
sudo bash scripts/load.sh
sudo ./user/simple-char-cli roundtrip "hello from C"
sudo python3 user/simple_char_client.py roundtrip "hello from Python"
sudo ./user/simple-char-cli stats
sudo bash scripts/unload.sh
```

The module is pinned while a descriptor is open; close clients before unloading.
For non-root client access, signing/Secure Boot, alternate header trees, and
hardware parameters, see the [usage guide](docs/usage.md).

## Test a loaded module in a disposable VM

`make check-vm` boots an isolated x86_64 Linux guest using QEMU software
emulation. It uses no host disk mounts or network interfaces and never inserts
the module into the host kernel. The guest runs:

- Both C and Python smoke tests and eight device integration cases.
- Four read/write tests using inaccessible user pages, checking transferred
  bytes, file position, counters, errno, and preservation of untouched data.
- Invalid-capacity cleanup, busy-device removal, 25 load/unload cycles, and
  preservation of an unexpected symlink at the device path.

See [VM setup and commands](docs/testing.md#disposable-linux-vm) for dependencies
and a matching kernel image/header pair. CI retains `vm-console` artifacts and
requires an explicit success marker after all checks finish.

## Behavior and design

```mermaid
flowchart LR
    C[C and Python clients] --> D[/dev/simple_char]
    D --> M[Mutex-protected buffer and write staging]
    D --> S[Fixed-width statistics and ioctl ABI]
    D --> H[Optional privileged GPIO / I2C]
```

| Operation | Contract |
|---|---|
| `read` | Read from file position to logical end; return zero at EOF |
| `write` | Bounded by capacity; short write at the boundary, then `ENOSPC` |
| `llseek` | Positions from zero through capacity |
| `CLEAR` | Requires a writable descriptor; zero data and reset caller position |
| `GET_STATS` | Snapshot counters, size, capacity, errors, and hook state |
| GPIO/I2C ioctls | Require an enabled hook, writable descriptor, and `CAP_SYS_RAWIO` |

Capacity defaults to 4 KiB and is configurable from 64 bytes to 1 MiB. The write
path reuses one capacity-sized staging buffer under the mutex, removing
per-write allocation/free operations while preserving partial-copy semantics.
Persistent buffer memory is 8 KiB by default, up to 2 MiB. No throughput or
latency improvement is claimed without benchmark evidence.

The Python client uses `pread`/`pwrite`, preserving shared descriptor position.
`PartialWriteError` reports committed bytes and the next offset after a later
syscall fails. See [client examples](docs/usage.md#clients) and the
[full I/O, concurrency, and cleanup design](docs/design.md).

## Find the implementation

| Path | Purpose |
|---|---|
| [`kernel/simple_char.c`](kernel/simple_char.c) | Driver and reverse-order resource cleanup |
| [`include/uapi/simple_char_ioctl.h`](include/uapi/simple_char_ioctl.h) | Shared fixed-width ioctl definitions |
| [`user/`](user/) | C CLI and Python client |
| [`scripts/`](scripts/) | Build, lifecycle, and disposable VM runners |
| [`tests/`](tests/) | Host models, client regressions, ABI checks, actual-device tests |
| [`docs/testing.md`](docs/testing.md) | Test commands, regression matrix, and validation limits |
| [`docs/hardware-bringup.md`](docs/hardware-bringup.md) | Physical GPIO/I2C bring-up checklist |

## Scope

This is an educational memory-device portfolio project. It stores one shared
byte array, loses data on unload, and provides no per-user isolation, blocking
reads, `poll`/`epoll`, `mmap`, or DKMS installer. Kernel support is limited to the
versions recorded in the verification log; 5.15+ is the intended review range.

GPIO uses legacy global numbering; production hardware drivers should bind via
Device Tree descriptors and the I2C core. Physical board validation remains a
separate task. See [contribution guidance](CONTRIBUTING.md),
[security policy](SECURITY.md), and [change history](CHANGELOG.md).

MIT repository license; the kernel module declares `Dual MIT/GPL`.
