#!/usr/bin/env python3
"""Python client for the simple_char Linux character device."""

from __future__ import annotations

import argparse
import dataclasses
import errno
import json
import os
import struct
import sys
from typing import Final

try:
    import fcntl
except ModuleNotFoundError:  # Allows ABI/model tests to import on non-Linux hosts.
    fcntl = None  # type: ignore[assignment]

DEFAULT_DEVICE: Final = "/dev/simple_char"
IOC_MAGIC: Final = 0xB7

# Linux asm-generic ioctl encoding, used by x86_64 and arm64 (Raspberry Pi OS
# 64-bit). The fixed-width UAPI contains no pointers and is compat-safe.
_IOC_NRBITS: Final = 8
_IOC_TYPEBITS: Final = 8
_IOC_SIZEBITS: Final = 14
_IOC_NRSHIFT: Final = 0
_IOC_TYPESHIFT: Final = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT: Final = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT: Final = _IOC_SIZESHIFT + _IOC_SIZEBITS
_IOC_WRITE: Final = 1
_IOC_READ: Final = 2

STATS_STRUCT: Final = struct.Struct("=QQQQQIIiiIIII")
GPIO_STRUCT: Final = struct.Struct("=I")
I2C_STRUCT: Final = struct.Struct("=II")


def _ioc(direction: int, ioctl_type: int, number: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (ioctl_type << _IOC_TYPESHIFT)
        | (number << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


IOC_GET_STATS: Final = _ioc(_IOC_READ, IOC_MAGIC, 0x01, STATS_STRUCT.size)
IOC_CLEAR: Final = _ioc(0, IOC_MAGIC, 0x02, 0)
IOC_GPIO_SET: Final = _ioc(_IOC_WRITE, IOC_MAGIC, 0x03, GPIO_STRUCT.size)
IOC_I2C_WRITE_REG: Final = _ioc(_IOC_WRITE, IOC_MAGIC, 0x04, I2C_STRUCT.size)


def _ioctl(
    descriptor: int,
    operation: int,
    argument: int | bytes | bytearray = 0,
    mutate: bool = False,
) -> int | bytes:
    if fcntl is None:
        raise OSError(errno.ENOSYS, "fcntl.ioctl is available only on Unix/Linux")
    if argument == 0 and not mutate:
        return fcntl.ioctl(descriptor, operation)
    return fcntl.ioctl(descriptor, operation, argument, mutate)


@dataclasses.dataclass(frozen=True)
class Stats:
    open_count: int
    read_ops: int
    write_ops: int
    bytes_read: int
    bytes_written: int
    data_size: int
    capacity: int
    open_handles: int
    last_error: int
    gpio_enabled: bool
    gpio_value: int
    i2c_enabled: bool

    @classmethod
    def unpack(cls, payload: bytes) -> "Stats":
        values = STATS_STRUCT.unpack(payload)
        return cls(
            open_count=values[0],
            read_ops=values[1],
            write_ops=values[2],
            bytes_read=values[3],
            bytes_written=values[4],
            data_size=values[5],
            capacity=values[6],
            open_handles=values[7],
            last_error=values[8],
            gpio_enabled=bool(values[9]),
            gpio_value=values[10],
            i2c_enabled=bool(values[11]),
        )


class PartialWriteError(OSError):
    """A write failed after committing a prefix; retry only the remaining bytes."""

    def __init__(self, cause: OSError, *, bytes_written: int, offset: int):
        self.bytes_written = bytes_written
        self.next_offset = offset + bytes_written
        super().__init__(
            cause.errno,
            f"{cause.strerror or str(cause)}; committed {bytes_written} bytes; "
            f"next offset {self.next_offset}",
        )


class SimpleCharClient:
    """Small context-managed wrapper around ``/dev/simple_char``."""

    def __init__(self, path: str = DEFAULT_DEVICE, *, writable: bool = True):
        self.path = path
        self.writable = writable
        self._descriptor: int | None = None

    def __enter__(self) -> "SimpleCharClient":
        if self._descriptor is not None:
            raise RuntimeError("client is already open")
        if not all(hasattr(os, name) for name in ("pread", "pwrite", "O_CLOEXEC")):
            raise OSError(errno.ENOSYS, "device access requires Linux positional I/O")
        flags = os.O_RDWR if self.writable else os.O_RDONLY
        self._descriptor = os.open(self.path, flags | os.O_CLOEXEC)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._descriptor is not None:
            descriptor = self._descriptor
            self._descriptor = None
            # close() may release an fd even when it reports failure; do not
            # retain a number that a later open could reuse.
            os.close(descriptor)

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise RuntimeError("client is not open")
        return self._descriptor

    def seek(self, offset: int = 0) -> int:
        return os.lseek(self.descriptor, offset, os.SEEK_SET)

    def write(self, payload: bytes, *, offset: int = 0) -> int:
        """Write all bytes at an explicit offset without changing file position.

        PartialWriteError preserves progress when a later syscall fails. A
        multi-syscall write is not a transaction with respect to other writers.
        """
        if offset < 0:
            raise ValueError("offset must be non-negative")
        descriptor = self.descriptor
        view = memoryview(payload)
        total = 0
        while total < len(view):
            try:
                written = os.pwrite(descriptor, view[total:], offset + total)
                if written == 0:
                    raise OSError(errno.EIO, "device returned a zero-byte write")
            except OSError as error:
                if total:
                    raise PartialWriteError(
                        error, bytes_written=total, offset=offset
                    ) from error
                raise
            total += written
        return total

    def read(self, count: int, *, offset: int = 0) -> bytes:
        if count < 0:
            raise ValueError("count must be non-negative")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        descriptor = self.descriptor
        chunks: list[bytes] = []
        remaining = count
        while remaining:
            chunk = os.pread(descriptor, remaining, offset + count - remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def stats(self) -> Stats:
        payload = bytearray(STATS_STRUCT.size)
        _ioctl(self.descriptor, IOC_GET_STATS, payload, True)
        return Stats.unpack(payload)

    def clear(self) -> None:
        _ioctl(self.descriptor, IOC_CLEAR)

    def gpio_set(self, value: int) -> None:
        if value not in (0, 1):
            raise ValueError("GPIO value must be 0 or 1")
        _ioctl(self.descriptor, IOC_GPIO_SET, GPIO_STRUCT.pack(value))

    def i2c_write_register(self, register: int, value: int) -> None:
        if not 0 <= register <= 0xFF or not 0 <= value <= 0xFF:
            raise ValueError("I2C register and value must fit in 8 bits")
        _ioctl(
            self.descriptor,
            IOC_I2C_WRITE_REG,
            I2C_STRUCT.pack(register, value),
        )


def _parse_byte(text: str) -> int:
    value = int(text, 0)
    if not 0 <= value <= 0xFF:
        raise argparse.ArgumentTypeError("expected an integer from 0 to 255")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=DEFAULT_DEVICE)
    commands = parser.add_subparsers(dest="command", required=True)

    write_parser = commands.add_parser("write", help="write UTF-8 text")
    write_parser.add_argument("text")

    read_parser = commands.add_parser("read", help="read bytes from offset zero")
    read_parser.add_argument("count", nargs="?", type=int, default=4096)

    roundtrip_parser = commands.add_parser("roundtrip", help="clear/write/read/compare")
    roundtrip_parser.add_argument("text")

    commands.add_parser("stats", help="print driver counters as JSON")
    commands.add_parser("clear", help="clear the in-kernel buffer")

    gpio_parser = commands.add_parser("gpio", help="set the opt-in GPIO hook")
    gpio_parser.add_argument("value", type=int, choices=(0, 1))

    i2c_parser = commands.add_parser("i2c", help="write one I2C register")
    i2c_parser.add_argument("register", type=_parse_byte)
    i2c_parser.add_argument("value", type=_parse_byte)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    writable = args.command not in {"read", "stats"}

    try:
        with SimpleCharClient(args.device, writable=writable) as client:
            if args.command == "write":
                client.write(args.text.encode())
            elif args.command == "read":
                if args.count < 0:
                    raise ValueError("count must be non-negative")
                sys.stdout.buffer.write(client.read(args.count))
            elif args.command == "roundtrip":
                expected = args.text.encode()
                client.clear()
                client.write(expected)
                actual = client.read(len(expected))
                if actual != expected:
                    raise RuntimeError(
                        f"roundtrip mismatch: wrote {len(expected)}, read {len(actual)}"
                    )
                print(f"roundtrip ok: {len(expected)} bytes")
            elif args.command == "stats":
                print(json.dumps(dataclasses.asdict(client.stats()), indent=2))
            elif args.command == "clear":
                client.clear()
            elif args.command == "gpio":
                client.gpio_set(args.value)
            elif args.command == "i2c":
                client.i2c_write_register(args.register, args.value)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"simple-char: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
