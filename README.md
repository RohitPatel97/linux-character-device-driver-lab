# Linux Character Device Driver

[![CI](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/workflows/ci.yml)

A compact, reviewable Linux loadable kernel module that exposes
`/dev/simple_char`. It demonstrates character-device
fundamentals: dynamic device-number allocation, bounded positional I/O,
mutex-protected shared state, safe user/kernel copies, stable fixed-width
ioctls, explicit error propagation, and reverse-order cleanup.

Optional Raspberry Pi GPIO and I2C integration points are parameterized,
disabled by default, and gated by `CAP_SYS_RAWIO`. The repository also includes
C and Python clients, repeatable lifecycle scripts, a udev policy, a host-only
reference model, and CI that builds against Ubuntu kernel headers.

See [`WORKFLOW.md`](WORKFLOW.md) for completed work, recorded verification,
and the next three tasks.

> Verified October 1, 2026: **40 passing checks** (32 portable host tests,
> five native C/Python ABI checks, and three shell-checker regressions), a C
> client build, ShellCheck, and kernel-module compilation plus `modinfo` in
> [GitHub Actions](https://github.com/RohitPatel97/linux-character-device-driver-lab/actions/runs/36889639768)
> at commit `998a717`. That build used Ubuntu 24.04 and Linux
> `6.8.0-146-generic` headers. Module loading and Raspberry Pi GPIO/I2C hardware
> validation remain **pending**; the eight real-device cases are authored but
> unrun. See the [verification log](docs/verification-log.md) for exact evidence.

## Try the checks without loading a module

Clone the repository and run the portable Python suite on Windows, macOS, or
Linux (Python 3.11+):

```bash
git clone https://github.com/RohitPatel97/linux-character-device-driver-lab.git
cd linux-character-device-driver-lab
python3 -m unittest discover -s tests -v
```

On Windows, use `python` or `py -3` if `python3` is unavailable. For the full
unprivileged checks on Debian/Ubuntu:

```bash
sudo apt-get install build-essential python3 shellcheck
make check
```

`make check` builds the C client, runs the portable suite, compares a compiled
C UAPI probe with the Python client, and checks the shell scripts and checker
regressions. It needs no kernel headers, device node, or module load. The C ABI
comparison targets Linux architectures using asm-generic ioctl encoding,
including x86_64 and arm64.

## Why this is useful

- Provides a small end-to-end example rather than an isolated kernel snippet.
- Makes every acquired resource visible in the corresponding failure unwind.
- Preserves ordinary `read(2)`, `write(2)`, and `llseek(2)` behavior.
- Handles partial `copy_to_user` / `copy_from_user` results as short I/O.
- Gives reviewers executable evidence without requiring privileged CI runners.
- Keeps physical I/O unavailable unless an operator deliberately enables it.

## Architecture

```mermaid
flowchart LR
    subgraph User[User space]
        C[C CLI]
        P[Python client]
        T[Host-only model tests]
    end

    subgraph Kernel[Kernel space]
        V[file_operations\nopen/read/write/llseek/ioctl]
        M[mutex-protected\nbounded buffer]
        S[atomic counters +\nfixed-width stats ABI]
        G[optional GPIO hook]
        I[optional I2C hook]
    end

    C -->|syscalls| D[/dev/simple_char]
    P -->|syscalls| D
    D --> V
    V --> M
    V --> S
    V -->|CAP_SYS_RAWIO + opt-in| G
    V -->|CAP_SYS_RAWIO + opt-in| I
    T -. mirrors observable semantics .-> M
```

The in-kernel buffer is one shared device resource. Each open file has its own
file position. A single interruptible mutex covers buffer contents, logical
length, and hardware operations; related I/O counters are sampled under that
same lock. Open/close counts and `last_error` are independently sampled
diagnostics. The module owner recorded in `file_operations` prevents removal while a file is
open.

## Repository layout

```text
.
├── .github/workflows/ci.yml          Ubuntu client/test and module-build jobs
├── include/uapi/simple_char_ioctl.h  Shared fixed-width userspace ABI
├── kernel/
│   ├── Kbuild
│   └── simple_char.c                 Module implementation
├── packaging/
│   ├── modprobe/simple_char.conf.example
│   ├── modules-load/simple_char.conf
│   └── udev/99-simple-char.rules
├── scripts/
│   ├── build.sh
│   ├── check-shell.sh
│   ├── load.sh
│   ├── repeat-load-unload.sh
│   ├── setup-udev.sh
│   ├── smoke-test.sh
│   └── unload.sh
├── tests/                            Model, client, native ABI, and shell tests
├── user/
│   ├── simple_char_cli.c             Native client
│   └── simple_char_client.py         Standard-library Python client
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
└── Makefile
```

## I/O contract

The default capacity is 4,096 bytes and may be set from 64 bytes through 1 MiB
at load time. The buffer begins empty.

- `read`: returns bytes between the file position and the logical data length;
  returns `0` at EOF.
- `write`: writes between the file position and capacity; a write that crosses
  the boundary is a short write, and a write at capacity returns `ENOSPC`.
- `llseek`: accepts positions from zero through capacity.
- zero-length I/O: returns zero and does not change counters.
- `CLEAR`: zeros the complete allocation, sets logical length and the caller's
  file position to zero, and requires a writable descriptor.

The kernel never dereferences a user pointer directly. It uses
`copy_to_user()` and `copy_from_user()`, accounts for bytes those helpers did
not copy, returns `EFAULT` if nothing was transferred, and otherwise reports a
short operation.

### Ioctl ABI

All payloads use `__u32`, `__s32`, and `__u64`; there are no raw pointers or
native-width integers. This makes the layout stable for 32-bit compatibility.

| Command | Access | Purpose | Important failures |
|---|---:|---|---|
| `GET_STATS` | read | Snapshot opens, operations, bytes, size, capacity, last error, and hook state | `EFAULT`, interrupted lock |
| `CLEAR` | write | Zero the buffer and reset length/position | `EBADF`, interrupted lock |
| `GPIO_SET` | write + privileged | Set logical 0/1 on the opted-in line | `EBADF`, `EOPNOTSUPP`, `EPERM`, `EINVAL`, `EFAULT` |
| `I2C_WRITE_REG` | write + privileged | SMBus byte-data write to an opted-in client | adapter errno, `EBADF`, `EOPNOTSUPP`, `EPERM`, `EINVAL`, `EFAULT` |

`last_error` is a diagnostic snapshot, not a replacement for the errno returned
to the calling process.

## Build

Prerequisites on Debian or Ubuntu:

```bash
sudo apt-get update
sudo apt-get install build-essential linux-headers-"$(uname -r)" python3
make all
```

This produces `kernel/simple_char.ko` and `user/simple-char-cli`. To build
against a different prepared header tree:

```bash
make module KDIR=/path/to/linux-headers
make client
```

Kernel modules must be built for the kernel that will load them. Secure Boot
systems may also require the `.ko` to be signed with an enrolled key.

## Safe quick start (memory device only)

Hardware remains off in this path.

```bash
make all
sudo bash scripts/setup-udev.sh       # one-time optional access policy
sudo bash scripts/load.sh             # enable_gpio=0, enable_i2c=0

./user/simple-char-cli roundtrip "hello from C"
python3 user/simple_char_client.py roundtrip "hello from Python"
./user/simple-char-cli stats

sudo bash scripts/unload.sh
```

Direct shell I/O also works, although `echo` adds a newline:

```bash
printf 'abc' | sudo tee /dev/simple_char >/dev/null
sudo dd if=/dev/simple_char bs=3 count=1 status=none
```

The udev rule assigns mode `0660` to group `simplechar` and adds `uaccess` for
the active local session. Add only trusted users to that group; access permits
reading and modifying the shared kernel buffer. Re-login after group changes.

## Clients

Both clients return nonzero on syscall/ioctl failure and preserve the kernel's
error message.

```bash
./user/simple-char-cli --help
./user/simple-char-cli write "payload"
./user/simple-char-cli read 128
./user/simple-char-cli clear
./user/simple-char-cli stats

python3 user/simple_char_client.py --help
python3 user/simple_char_client.py write "payload"
python3 user/simple_char_client.py read 128
python3 user/simple_char_client.py stats
```

The Python client computes Linux asm-generic ioctl values used by x86_64 and
arm64. A non-asm-generic architecture should generate its ioctl numbers from
the shared C header instead.

The Python `read()` and `write()` methods use `pread`/`pwrite` with explicit
offsets. They leave the descriptor's shared file position unchanged, so two
threads using one open client can target different ranges without a
`seek`/I/O race. Keep the client open until those threads finish. Overlapping
writes and multi-syscall operations are still not transactions.

If a write commits a prefix and a later syscall fails, `PartialWriteError`
preserves the original `errno`, `bytes_written`, and `next_offset`. For
example, writing five bytes three bytes before capacity commits three bytes
and raises `ENOSPC` with `bytes_written=3`. A failure on the first syscall
remains the original `OSError`.

```python
from user.simple_char_client import PartialWriteError, SimpleCharClient

with SimpleCharClient() as device:
    try:
        device.write(b"ABCDE", offset=device.stats().capacity - 3)
    except PartialWriteError as error:
        print(error.errno, error.bytes_written, error.next_offset)
```

## Repeatable lifecycle

Initialization either reaches a published device or unwinds every earlier
resource. Exit runs the same resource order in reverse.

```mermaid
stateDiagram-v2
    [*] --> AllocateState
    AllocateState --> AllocateBuffer
    AllocateBuffer --> GPIO: optional opt-in
    GPIO --> I2C: optional opt-in
    I2C --> DeviceNumber
    DeviceNumber --> Class
    Class --> DeviceNode
    DeviceNode --> Cdev
    Cdev --> Ready
    Ready --> DeleteCdev: rmmod
    DeleteCdev --> DestroyDevice
    DestroyDevice --> DestroyClass
    DestroyClass --> ReleaseNumber
    ReleaseNumber --> ReleaseI2C
    ReleaseI2C --> ReleaseGPIO
    ReleaseGPIO --> ZeroAndFreeBuffer
    ZeroAndFreeBuffer --> [*]
```

Fallible initialization stages have reverse-order `goto` unwind paths.
`cdev_add()` publishes callbacks last, after the class and node exist; no
fallible allocation follows successful publication. `load.sh` rolls back if
`/dev/simple_char` does not appear. `unload.sh`
waits for removal and only deletes a stale node when it is a character device
with the exact expected path and the module is absent.

To exercise this on a disposable Linux test host:

```bash
make all
sudo bash scripts/repeat-load-unload.sh 25
dmesg | tail -n 100
```

If `rmmod` reports `EBUSY`, close processes holding the device (for example,
inspect with `sudo lsof /dev/simple_char`) and retry. The script never forces
removal.

## GPIO and I2C hooks (advanced, opt-in)

Do not enable either hook until you have checked the board schematic, voltage,
pin ownership, active polarity, I2C bus number, target address, and target
register map. A wrong choice can damage hardware or collide with another
driver.

GPIO example (the number is a **Linux global GPIO number**, not necessarily a
header pin or BCM number):

```bash
sudo bash scripts/load.sh --enable-gpio --gpio-num 23
sudo ./user/simple-char-cli gpio 1
sudo ./user/simple-char-cli gpio 0
sudo bash scripts/unload.sh
```

I2C example, only after confirming bus `1`, target address `0x20`, and the
device's register protocol:

```bash
sudo bash scripts/load.sh --enable-i2c --i2c-bus 1 --i2c-addr 0x20
sudo ./user/simple-char-cli i2c 0x01 0x7f
sudo bash scripts/unload.sh
```

Enabling GPIO requests exclusive ownership and drives logical zero during load
and cleanup. Enabling I2C reserves the requested 7-bit address with a dummy
client. Initialization fails cleanly if a line/address is invalid or already
owned. Hardware ioctls additionally require `CAP_SYS_RAWIO`, even if ordinary
buffer access is allowed by udev.

The GPIO number interface is intentionally a small demonstration hook. A
production Raspberry Pi driver should normally bind through Device Tree and
obtain a named descriptor with `devm_gpiod_get()`; a production I2C peripheral
driver should declare supported devices and bind through the I2C core. See
[`docs/hardware-bringup.md`](docs/hardware-bringup.md) for the validation
checklist and evidence template.

## Concurrency and security choices

- One mutex makes each individual buffer read/write atomic with respect to
  other buffer operations and prevents torn writes.
- `mutex_lock_interruptible()` lets blocked callers receive a signal instead of
  becoming unkillable.
- Capacity is validated before allocation and cannot change while loaded.
- User-controlled counts and offsets are range-checked before pointer
  arithmetic.
- The UAPI contains no kernel pointers and the compat ioctl uses identical
  fixed-width layouts.
- Hardware is off by default, requested explicitly, and privileged separately
  from device-file permissions.
- The unload path zeros buffer contents with `memzero_explicit()` before free.
- No world-writable rule, debugfs interface, arbitrary kernel address, or
  arbitrary-length allocation is exposed.

This module is educational portfolio code, not a security boundary. It has no
per-user data isolation, message framing, blocking/poll semantics, or audit log.

## Verification

### Host-only tests (no root and no module load)

```bash
python3 -m unittest discover -s tests -v
# or build the C client plus all checks
make check
```

| Command | Coverage | Requirements |
|---|---|---|
| `python3 -m unittest discover -s tests -v` | 32 model, Python ABI, client syscall, and source-contract cases | Python 3.11+; portable |
| `make check-abi` | Five comparisons against the compiled C header: sizes, ioctl numbers, stats decoding, GPIO and I2C wire layouts | Linux C compiler, userspace Linux headers, Python |
| `make check-shell` | Syntax-check every script, run ShellCheck when installed, and run three checker regressions | Bash, standard Unix tools, Python; CI installs ShellCheck |
| `make check` | All checks above plus the native C client build | Linux development tools; no kernel headers |

The native ABI probe in [`tests/abi_probe.c`](tests/abi_probe.c) includes the
same UAPI header as the driver and C client. Python compares the actual C ioctl
values and serialized request/statistics payloads, including distinct 64-bit
counters and a negative errno. This catches header/client drift that separate
hard-coded Python expectations can miss. It verifies the build host's ABI;
it does not establish 32-bit compatibility on a 64-bit kernel.

The shell regressions run in temporary directories without root or a device.
They reproduce the old one-file-only syntax check, reject a malformed later
script, exercise filenames containing spaces and the no-ShellCheck fallback,
and verify that ShellCheck failures reach the caller.

The deterministic model covers boundary behavior, EOF, zero-length operations,
clear permissions, disabled/privileged hardware paths, counters, and concurrent
non-torn writes. ABI tests validate struct sizes and ioctl encodings. Source
contract tests confirm the safety helpers and lifecycle primitives remain
present. These tests support code review; they do not emulate Linux scheduling,
faulting user pages, a real I2C controller, or electrical GPIO behavior.

The client syscall tests execute the actual Python client with injected short
reads/writes, EOF, `ENOSPC`, `EFAULT`, and zero-progress responses. A shared
descriptor test forces several syscalls per write across four threads and
checks the final buffer. These are client regression tests, not a substitute
for running the kernel module.

### Problems, fixes, and executable cases

| Problem | Solution | Test and expected result |
|---|---|---|
| `seek` followed by I/O lets another thread change a shared descriptor's offset | Use positional Python I/O; advance explicit offsets after short transfers | `test_shared_descriptor_writers_keep_their_offsets`: four 16-byte regions contain their exact payloads |
| A short write followed by `ENOSPC` hides bytes already committed | Raise `PartialWriteError` with errno, prefix length, and next offset | `test_capacity_error_preserves_committed_prefix`: 3 of 5 bytes committed at offset 61, next offset 64 |
| A zero-byte write can leave a retry loop making no progress | Stop with `EIO`, retaining any earlier progress | `test_zero_write_fails_without_spinning` and `test_zero_write_after_progress_preserves_prefix` |
| Short reads and EOF can truncate or repeat data | Accumulate chunks and advance the positional offset | `test_read_combines_short_reads_and_stops_at_eof`: returns `abc` using offsets 5, 7, and 8 |
| Nested context entry can leak an open descriptor | Reject entry while already open; invalidate descriptor before close | `test_nested_context_does_not_leak_another_descriptor` and `test_close_failure_invalidates_descriptor` |
| Stats sampled before acquiring the lock can mix I/O totals from different operations | Capture I/O totals and logical size within the device mutex | Linux integration `test_stats_totals_are_coherent_during_writes`: bytes written equal 8 times operations during fixed-width writes; **not yet run** |
| Source-contract test still expected an obsolete cleanup label | Align the check and lifecycle diagram with publication after device-node creation | `test_cleanup_labels_are_reverse_ordered`: current failure labels appear in reverse acquisition order |
| One `bash -n` call with several filenames checks only the first script | Invoke Bash separately for every discovered script | Shell checker regression: a malformed later script fails even without ShellCheck |
| Independent Python ABI constants can pass tests after the C header changes | Compile the shared C header and compare actual command values and wire payloads | `make check-abi`: five native C/Python comparisons |

See [`tests/test_client_io.py`](tests/test_client_io.py) for host regression
cases and [`docs/verification-log.md`](docs/verification-log.md) for the exact
observed results.

### Opt-in Linux device integration

Eight integration cases exercise the actual syscalls and ioctls against a
loaded module: sparse roundtrip, capacity/progress errors, invalid seek,
read-only clear rejection, disabled hardware, unchanged descriptor position,
concurrent shared-descriptor writes, and coherent stats. The suite requires
an explicit buffer-clear acknowledgement and is excluded from normal host
discovery. Stop other clients first; unrelated writes invalidate counter
assertions. Both hardware hooks must be disabled.

```bash
make all
sudo bash scripts/load.sh
sudo python3 -m tests.linux_integration --device /dev/simple_char --allow-clear
sudo bash scripts/unload.sh
```

This suite is implemented but has **not been executed against a loaded Linux
module** in the recorded Windows environment. It does not load/unload the
module itself, inject faulting user pages, or validate physical hardware.

### Test and failure matrix

| Scenario | Automated here | Expected observation |
|---|---:|---|
| Buffer roundtrip and counters | Host model | Exact payload; byte/op totals advance |
| Concurrent writes | Host model | Complete, non-torn fixed segments |
| Capacity boundary | Host model | Short write, then `ENOSPC` |
| Disabled hardware | Host model | `EOPNOTSUPP` |
| Missing raw-I/O privilege | Host model | `EPERM` |
| UAPI size/ioctl values and field layout | Python tests + compiled C probe | 72-byte stats, matching commands, and matching wire payloads |
| C warnings + script lint | GitHub Actions | Clean client compile and ShellCheck |
| Kernel API compatibility | GitHub Actions | `.ko` compiles against Ubuntu generic headers |
| Invalid module parameter | Linux test host | `insmod` fails; no class/node remains |
| Device busy during unload | Linux test host | `rmmod` returns `EBUSY`; module remains intact |
| Repeated load/unload | Linux test host | No stale class or `/dev` node after each cycle |
| Partial user-copy fault | Linux fault-injection test | Short I/O or `EFAULT`; `last_error=-EFAULT` |
| Raspberry Pi GPIO polarity | Physical Pi + meter/scope | Safe initial level and requested transitions |
| Raspberry Pi I2C transfer/NACK | Physical Pi + target/analyzer | Correct frame or adapter-provided errno |

Rows marked “Linux test host,” “fault-injection,” or physical hardware require
external validation and are not represented as completed by this repository.
Record commands, kernel version, commit, results, and logs in
[`docs/verification-log.md`](docs/verification-log.md).

## CI

`.github/workflows/ci.yml` has two unprivileged jobs:

1. build the C client, run Python tests and native C/Python ABI comparisons,
   parse every shell script, run ShellCheck, and test the shell checker;
2. install Ubuntu generic headers, compile the out-of-tree module, and inspect
   its metadata with `modinfo`.

GitHub-hosted runners do not load the module. Loading arbitrary modules is not
required to verify that the source compiles.

## Troubleshooting

- `Kernel build directory not found`: install headers matching the target
  kernel or supply `KDIR` explicitly.
- `Key was rejected by service`: Secure Boot rejected an unsigned module; sign
  it with an enrolled Machine Owner Key or use an authorized test machine.
- `/dev/simple_char` never appears`: confirm devtmpfs/udev is running and inspect
  `dmesg`; `load.sh` will unload the module on this failure.
- `Operation not permitted` for GPIO/I2C: run with `CAP_SYS_RAWIO` (normally
  root) and confirm the hook was enabled at load time.
- `Device or resource busy` during load: the GPIO or I2C address is likely owned
  by another driver. Do not force it; inspect the active Device Tree/drivers.
- `No space left on device`: seek/clear the buffer or reload with a larger valid
  `buffer_size`.

## Scope and limitations

- Linux kernel 5.15+ is the intended review/build range; CI provides the exact
  compiler evidence for its current Ubuntu header version.
- No DKMS installer is included; rebuild after kernel upgrades.
- The device stores one shared byte array in RAM and loses it on unload.
- `poll`, `epoll`, async notification, `mmap`, and blocking reads are out of
  scope.
- The GPIO module parameter uses legacy global numbering for a concise
  parameterized demonstration; Device Tree descriptors are preferable.
- Only SMBus byte-data I2C writes are exposed, intentionally avoiding a general
  raw-bus proxy.
- Real kernel-load, Raspberry Pi, GPIO, and I2C results must be added only after
  they are actually observed.

## License

MIT for the repository; the kernel module declares `Dual MIT/GPL` so it can use
GPL-only kernel interfaces if required by a target kernel configuration. See
[`LICENSE`](LICENSE).
