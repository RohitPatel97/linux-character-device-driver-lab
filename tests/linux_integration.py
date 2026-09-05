"""Opt-in checks for a loaded simple_char module; clears its shared RAM buffer.

Run on an otherwise idle Linux test device with both hardware hooks disabled:
python3 -m tests.linux_integration --device /dev/simple_char --allow-clear
"""

from __future__ import annotations

import argparse
import errno
import os
import stat
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from user.simple_char_client import PartialWriteError, SimpleCharClient


class LinuxDeviceTests(unittest.TestCase):
    device_path: str | None = None

    def setUp(self) -> None:
        if self.device_path is None:
            self.skipTest("requires explicit --device and --allow-clear")
        self.device = self.enterContext(SimpleCharClient(self.device_path))
        stats = self.device.stats()
        self.assertFalse(stats.gpio_enabled, "run with enable_gpio=0")
        self.assertFalse(stats.i2c_enabled, "run with enable_i2c=0")
        self.assertGreaterEqual(stats.capacity, 64)
        self.assertLessEqual(stats.capacity, 1024 * 1024)
        self.capacity = stats.capacity
        self.device.clear()

    def tearDown(self) -> None:
        if hasattr(self, "device"):
            self.device.clear()

    def test_roundtrip_and_zero_filled_gap(self) -> None:
        self.assertEqual(self.device.write(b"abc", offset=5), 3)
        self.assertEqual(self.device.read(32), b"\x00" * 5 + b"abc")
        self.assertEqual(self.device.read(1, offset=8), b"")

    def test_capacity_failure_preserves_written_prefix(self) -> None:
        with self.assertRaises(PartialWriteError) as raised:
            self.device.write(b"ABCDE", offset=self.capacity - 3)
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertEqual(raised.exception.bytes_written, 3)
        self.assertEqual(raised.exception.next_offset, self.capacity)
        self.assertEqual(self.device.read(3, offset=self.capacity - 3), b"ABC")

    def test_seek_outside_capacity_fails(self) -> None:
        with self.assertRaises(OSError) as raised:
            self.device.seek(self.capacity + 1)
        self.assertEqual(raised.exception.errno, errno.EINVAL)

    def test_clear_requires_writable_descriptor(self) -> None:
        with SimpleCharClient(self.device_path, writable=False) as reader:
            with self.assertRaises(OSError) as raised:
                reader.clear()
        self.assertEqual(raised.exception.errno, errno.EBADF)

    def test_hardware_hooks_are_disabled(self) -> None:
        for operation in (lambda: self.device.gpio_set(0), lambda: self.device.i2c_write_register(0, 0)):
            with self.assertRaises(OSError) as raised:
                operation()
            self.assertEqual(raised.exception.errno, errno.EOPNOTSUPP)

    def test_positional_io_preserves_shared_file_position(self) -> None:
        self.device.seek(17)
        self.device.write(b"data", offset=0)
        self.assertEqual(self.device.read(4), b"data")
        self.assertEqual(os.lseek(self.device.descriptor, 0, os.SEEK_CUR), 17)

    def test_concurrent_writers_using_one_descriptor(self) -> None:
        barrier = threading.Barrier(4)

        def writer(index: int) -> None:
            barrier.wait(timeout=5)
            for _ in range(100):
                self.device.write(bytes([65 + index]) * 16, offset=index * 16)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(writer, index) for index in range(4)]
            for future in futures:
                future.result(timeout=30)
        self.assertEqual(self.device.read(64), b"A" * 16 + b"B" * 16 + b"C" * 16 + b"D" * 16)

    def test_stats_totals_are_coherent_during_writes(self) -> None:
        baseline = self.device.stats()
        barrier = threading.Barrier(2)

        def writer() -> None:
            barrier.wait(timeout=5)
            for _ in range(2000):
                self.device.write(b"12345678")

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(writer)
            barrier.wait(timeout=5)
            for _ in range(2000):
                snapshot = self.device.stats()
                operations = snapshot.write_ops - baseline.write_ops
                transferred = snapshot.bytes_written - baseline.bytes_written
                self.assertEqual(transferred, operations * 8)
                self.assertEqual(snapshot.data_size, 8 if operations else 0)
            future.result(timeout=30)
        final = self.device.stats()
        self.assertEqual(final.write_ops - baseline.write_ops, 2000)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True)
    parser.add_argument("--allow-clear", action="store_true", help="acknowledge test buffer erasure")
    args = parser.parse_args(argv)
    if not args.allow_clear:
        parser.error("--allow-clear is required: tests erase the device's shared buffer")
    if sys.platform != "linux":
        parser.error("a Linux host with the loaded module is required")
    try:
        if not stat.S_ISCHR(os.stat(args.device).st_mode):
            parser.error("--device must identify the simple_char character device")
        with SimpleCharClient(args.device) as probe:
            snapshot = probe.stats()
            if snapshot.gpio_enabled or snapshot.i2c_enabled:
                parser.error("reload the module with both hardware hooks disabled")
    except OSError as error:
        parser.error(str(error))
    LinuxDeviceTests.device_path = args.device
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LinuxDeviceTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
