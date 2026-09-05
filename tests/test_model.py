from __future__ import annotations

import errno
import threading
import unittest

from tests.model import DeviceModel


class DeviceModelTests(unittest.TestCase):
    def test_roundtrip_and_counters(self) -> None:
        device = DeviceModel(capacity=32)
        with device.open() as handle:
            self.assertEqual(handle.write(b"kernel-space"), 12)
            handle.seek(0)
            self.assertEqual(handle.read(32), b"kernel-space")

        stats = device.snapshot()
        self.assertEqual(stats.open_count, 1)
        self.assertEqual(stats.open_handles, 0)
        self.assertEqual(stats.read_ops, 1)
        self.assertEqual(stats.write_ops, 1)
        self.assertEqual(stats.bytes_read, 12)
        self.assertEqual(stats.bytes_written, 12)
        self.assertEqual(stats.data_size, 12)

    def test_bounded_short_write_then_enospc(self) -> None:
        device = DeviceModel(capacity=4)
        with device.open() as handle:
            self.assertEqual(handle.write(b"abcdef"), 4)
            with self.assertRaises(OSError) as raised:
                handle.write(b"x")
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertEqual(device.snapshot().last_error, -errno.ENOSPC)

    def test_clear_requires_writable_handle(self) -> None:
        device = DeviceModel()
        with device.open(writable=False) as handle:
            with self.assertRaises(OSError) as raised:
                handle.clear()
        self.assertEqual(raised.exception.errno, errno.EBADF)

    def test_disabled_hardware_is_safe_by_default(self) -> None:
        device = DeviceModel()
        with device.open(raw_io=True) as handle:
            with self.assertRaises(OSError) as gpio_error:
                handle.gpio_set(1)
            with self.assertRaises(OSError) as i2c_error:
                handle.i2c_write_register(0x10, 0xAB)
        self.assertEqual(gpio_error.exception.errno, errno.EOPNOTSUPP)
        self.assertEqual(i2c_error.exception.errno, errno.EOPNOTSUPP)

    def test_hardware_hooks_require_raw_io_capability(self) -> None:
        device = DeviceModel(gpio_enabled=True, i2c_enabled=True)
        with device.open(raw_io=False) as handle:
            with self.assertRaises(OSError) as raised:
                handle.gpio_set(1)
        self.assertEqual(raised.exception.errno, errno.EPERM)

    def test_hardware_hooks_require_writable_handle(self) -> None:
        device = DeviceModel(gpio_enabled=True, i2c_enabled=True)
        with device.open(writable=False, raw_io=True) as handle:
            with self.assertRaises(OSError) as raised:
                handle.gpio_set(1)
        self.assertEqual(raised.exception.errno, errno.EBADF)

    def test_parameterized_hardware_model(self) -> None:
        device = DeviceModel(gpio_enabled=True, i2c_enabled=True)
        with device.open(raw_io=True) as handle:
            handle.gpio_set(1)
            handle.i2c_write_register(0x20, 0x55)
        self.assertEqual(device.snapshot().gpio_value, 1)
        self.assertEqual(device.i2c_log, [(0x20, 0x55)])

    def test_mutex_prevents_torn_concurrent_writes(self) -> None:
        segments = 8
        width = 32
        device = DeviceModel(capacity=segments * width)
        barrier = threading.Barrier(segments)

        def writer(index: int) -> None:
            with device.open() as handle:
                barrier.wait()
                handle.seek(index * width)
                self.assertEqual(handle.write(bytes([65 + index]) * width), width)

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(segments)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())

        with device.open(writable=False) as reader:
            result = reader.read(segments * width)
        expected = b"".join(bytes([65 + index]) * width for index in range(segments))
        self.assertEqual(result, expected)

    def test_zero_length_operations_do_not_increment_counters(self) -> None:
        device = DeviceModel()
        with device.open() as handle:
            self.assertEqual(handle.write(b""), 0)
            self.assertEqual(handle.read(0), b"")
        stats = device.snapshot()
        self.assertEqual(stats.read_ops, 0)
        self.assertEqual(stats.write_ops, 0)


if __name__ == "__main__":
    unittest.main()
