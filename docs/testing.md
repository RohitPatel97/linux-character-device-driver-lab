# Testing and validation boundaries

[Project overview](../README.md)

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

The native ABI probe in [`tests/abi_probe.c`](../tests/abi_probe.c) includes the
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
| Stats sampled before acquiring the lock can mix I/O totals from different operations | Capture I/O totals and logical size within the device mutex | Linux integration `test_stats_totals_are_coherent_during_writes`: bytes written equal 8 times operations during fixed-width writes; see the current [verification log](verification-log.md) |
| Source-contract test still expected an obsolete cleanup label | Align the check and lifecycle diagram with publication after device-node creation | `test_cleanup_labels_are_reverse_ordered`: current failure labels appear in reverse acquisition order |
| One `bash -n` call with several filenames checks only the first script | Invoke Bash separately for every discovered script | Shell checker regression: a malformed later script fails even without ShellCheck |
| Independent Python ABI constants can pass tests after the C header changes | Compile the shared C header and compare actual command values and wire payloads | `make check-abi`: five native C/Python comparisons |

See [`tests/test_client_io.py`](../tests/test_client_io.py) for host regression
cases and [`docs/verification-log.md`](verification-log.md) for the exact
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

The suite can run against a loaded module in the disposable VM described below.
Its recorded outcome belongs in the verification log. The Python suite itself
does not load/unload the module or inject faulting user pages; the VM runner
and native fault harness cover those operations separately.

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
| Device busy during unload | QEMU Linux guest | Removal fails while a descriptor is open; module remains intact |
| Repeated load/unload | Linux test host | No stale class or `/dev` node after each cycle |
| Partial user-copy fault | Linux fault-injection test | Short I/O or `EFAULT`; `last_error=-EFAULT` |
| Raspberry Pi GPIO polarity | Physical Pi + meter/scope | Safe initial level and requested transitions |
| Raspberry Pi I2C transfer/NACK | Physical Pi + target/analyzer | Correct frame or adapter-provided errno |

Linux runtime and fault-injection rows are exercised by the VM job. Their
observed outcomes are recorded separately from host-only checks. Physical
hardware rows still require external validation.
Record commands, kernel version, commit, results, and logs in
[`docs/verification-log.md`](verification-log.md).


## Disposable Linux VM

On Ubuntu 24.04 x86_64, install the VM tools and a matching generic kernel/image
pair. The test itself is unprivileged on the host; installing packages and
making the packaged kernel image readable need administrator privileges.

```bash
sudo apt-get update
sudo apt-get install build-essential python3 kmod linux-image-generic linux-headers-generic qemu-system-x86 busybox-static cpio
kdir="$(find /usr/src -maxdepth 1 -type d -name 'linux-headers-*-generic' | sort -V | tail -n 1)"
make module KDIR="$kdir"
version="$(modinfo -F vermagic kernel/simple_char.ko | awk '{print $1}')"
mkdir -p build
sudo install -m 644 "/boot/vmlinuz-$version" build/vmlinuz
make check-vm KDIR="$kdir" KERNEL_IMAGE=build/vmlinuz
```

The runner creates a temporary initramfs containing the test module, BusyBox,
Bash, Python, clients, and test files. QEMU uses software emulation, two vCPUs,
512 MiB RAM, no network, and no host filesystem sharing. The guest mounts its
own devtmpfs/proc/sysfs and loads the module with GPIO/I2C disabled.

The guest runs the eight Python integration cases, both client smoke tests,
and `build/user-copy-faults /dev/simple_char --allow-clear`. The C harness maps
two pages and protects the second with `PROT_NONE`. Four cases cover entirely
inaccessible and cross-page read/write buffers. They allow a short prefix or
`EFAULT`, since the copy granularity depends on the architecture. Each checks
file-position advancement, coherent byte/operation counters, `last_error`,
and preservation of data outside the committed prefix.

Lifecycle checks reject invalid capacities, verify busy removal without forced
unloading, run 25 load/unload cycles, and preserve an unexpected device-path
symlink. Kernel diagnostics are checked for BUG/WARNING/Oops/KASAN/panic output.
A 240-second host timeout prevents a hung guest from passing. Success requires
`SIMPLE_CHAR_VM_PASS` and no failure marker; the full serial log is saved as
`build/vm-console.log` and uploaded by CI as `vm-console`.

CI builds the driver against the exact kernel image booted in the VM. It runs
once for each PR update and on pushes to `main`; superseded runs are cancelled.
The VM job covers one x86_64 kernel configuration. It does not validate electrical
GPIO signals, a physical I2C target, 32-bit compatibility execution, every kernel
version, or performance. The [verification log](verification-log.md) records
observed results rather than treating a configured job as completed evidence.

Implementation references: [QEMU direct Linux boot](https://www.qemu.org/docs/master/system/linuxboot.html)
and the [Linux initramfs format](https://www.kernel.org/doc/html/latest/driver-api/early-userspace/buffer-format.html).
