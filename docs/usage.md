# Build, clients, and hardware hooks

[Project overview](../README.md)

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

sudo ./user/simple-char-cli roundtrip "hello from C"
sudo python3 user/simple_char_client.py roundtrip "hello from Python"
sudo ./user/simple-char-cli stats

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
[`docs/hardware-bringup.md`](hardware-bringup.md) for the validation
checklist and evidence template.

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
