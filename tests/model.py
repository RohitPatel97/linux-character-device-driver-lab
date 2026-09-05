"""Thread-safe user-space model of the driver's observable buffer behavior."""

from __future__ import annotations

import dataclasses
import errno
import threading


@dataclasses.dataclass(frozen=True)
class ModelStats:
    open_count: int
    open_handles: int
    read_ops: int
    write_ops: int
    bytes_read: int
    bytes_written: int
    data_size: int
    capacity: int
    last_error: int
    gpio_enabled: bool
    gpio_value: int
    i2c_enabled: bool


class DeviceModel:
    """Reference model used where loading an out-of-tree module is impossible."""

    def __init__(
        self,
        capacity: int = 4096,
        *,
        gpio_enabled: bool = False,
        i2c_enabled: bool = False,
    ):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._buffer = bytearray(capacity)
        self._length = 0
        self._lock = threading.Lock()
        self._open_count = 0
        self._open_handles = 0
        self._read_ops = 0
        self._write_ops = 0
        self._bytes_read = 0
        self._bytes_written = 0
        self._last_error = 0
        self._gpio_enabled = gpio_enabled
        self._gpio_value = 0
        self._i2c_enabled = i2c_enabled
        self.i2c_log: list[tuple[int, int]] = []

    def open(self, *, writable: bool = True, raw_io: bool = False) -> "Handle":
        with self._lock:
            self._open_count += 1
            self._open_handles += 1
        return Handle(self, writable=writable, raw_io=raw_io)

    def _error(self, number: int, message: str) -> OSError:
        self._last_error = -number
        return OSError(number, message)

    def snapshot(self) -> ModelStats:
        with self._lock:
            return ModelStats(
                open_count=self._open_count,
                open_handles=self._open_handles,
                read_ops=self._read_ops,
                write_ops=self._write_ops,
                bytes_read=self._bytes_read,
                bytes_written=self._bytes_written,
                data_size=self._length,
                capacity=self.capacity,
                last_error=self._last_error,
                gpio_enabled=self._gpio_enabled,
                gpio_value=self._gpio_value,
                i2c_enabled=self._i2c_enabled,
            )


class Handle:
    def __init__(self, device: DeviceModel, *, writable: bool, raw_io: bool):
        self._device = device
        self._writable = writable
        self._raw_io = raw_io
        self._position = 0
        self._closed = False

    def __enter__(self) -> "Handle":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("handle is closed")

    def close(self) -> None:
        if self._closed:
            return
        with self._device._lock:
            self._device._open_handles -= 1
        self._closed = True

    def seek(self, position: int) -> int:
        self._ensure_open()
        with self._device._lock:
            if not 0 <= position <= self._device.capacity:
                raise self._device._error(errno.EINVAL, "invalid offset")
            self._position = position
        return position

    def read(self, count: int) -> bytes:
        self._ensure_open()
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return b""
        with self._device._lock:
            available = max(0, self._device._length - self._position)
            amount = min(count, available)
            payload = bytes(
                self._device._buffer[self._position : self._position + amount]
            )
            self._position += amount
            if amount:
                self._device._read_ops += 1
                self._device._bytes_read += amount
            return payload

    def write(self, payload: bytes) -> int:
        self._ensure_open()
        if not self._writable:
            with self._device._lock:
                raise self._device._error(errno.EBADF, "handle is read-only")
        if not payload:
            return 0
        with self._device._lock:
            if self._position >= self._device.capacity:
                raise self._device._error(errno.ENOSPC, "buffer is full")
            amount = min(len(payload), self._device.capacity - self._position)
            end = self._position + amount
            self._device._buffer[self._position : end] = payload[:amount]
            self._position = end
            self._device._length = max(self._device._length, end)
            self._device._write_ops += 1
            self._device._bytes_written += amount
            if amount < len(payload):
                self._device._last_error = -errno.ENOSPC
            return amount

    def clear(self) -> None:
        self._ensure_open()
        if not self._writable:
            with self._device._lock:
                raise self._device._error(errno.EBADF, "handle is read-only")
        with self._device._lock:
            self._device._buffer[:] = bytes(self._device.capacity)
            self._device._length = 0
            self._position = 0

    def gpio_set(self, value: int) -> None:
        self._ensure_open()
        with self._device._lock:
            if not self._writable:
                raise self._device._error(errno.EBADF, "handle is read-only")
            if not self._device._gpio_enabled:
                raise self._device._error(errno.EOPNOTSUPP, "GPIO hook is disabled")
            if not self._raw_io:
                raise self._device._error(errno.EPERM, "CAP_SYS_RAWIO is required")
            if value not in (0, 1):
                raise self._device._error(errno.EINVAL, "GPIO value must be 0 or 1")
            self._device._gpio_value = value

    def i2c_write_register(self, register: int, value: int) -> None:
        self._ensure_open()
        with self._device._lock:
            if not self._writable:
                raise self._device._error(errno.EBADF, "handle is read-only")
            if not self._device._i2c_enabled:
                raise self._device._error(errno.EOPNOTSUPP, "I2C hook is disabled")
            if not self._raw_io:
                raise self._device._error(errno.EPERM, "CAP_SYS_RAWIO is required")
            if not 0 <= register <= 0xFF or not 0 <= value <= 0xFF:
                raise self._device._error(errno.EINVAL, "I2C values must be 8-bit")
            self._device.i2c_log.append((register, value))
