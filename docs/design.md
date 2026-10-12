# Driver design and I/O contract

[Project overview](../README.md)

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

## Repeatable lifecycle

Initialization either reaches a published device or unwinds every earlier
resource. Exit runs the same resource order in reverse.

```mermaid
stateDiagram-v2
    [*] --> AllocateState
    AllocateState --> AllocateBuffer
    AllocateBuffer --> AllocateWriteBuffer
    AllocateWriteBuffer --> GPIO: optional opt-in
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
    ReleaseGPIO --> ZeroAndFreeWriteBuffer
    ZeroAndFreeWriteBuffer --> ZeroAndFreeBuffer
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

## Write-path allocation tradeoff

A capacity-sized staging buffer is allocated once during module initialization
and reused while holding the device mutex. The write syscall no longer calls
`kvmalloc`/`kvfree`; allocation failures occur at load time. `copy_from_user`
still targets staging memory so its zero-filled uncopied tail cannot overwrite
live data. Only successfully copied bytes are committed, then the attempted
staging range is wiped. Cleanup wipes and frees both allocations.

The persistent allocation is twice the configured capacity: 8 KiB at the default
4 KiB capacity, up to 2 MiB at maximum capacity, plus device metadata. This trades
bounded memory for removal of per-write allocation/free operations. There is no
measured throughput or latency claim.
