"""Exercise the real client against controlled syscall results, not the model."""

from __future__ import annotations

import errno
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import call, patch

from user import simple_char_client as client


class ClientIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.device = client.SimpleCharClient()
        self.device._descriptor = 31

    def test_short_writes_advance_explicit_offset_and_payload(self) -> None:
        with patch.object(client.os, "pwrite", create=True, side_effect=[2, 1, 3]) as write:
            self.assertEqual(self.device.write(b"abcdef", offset=7), 6)
        self.assertEqual(
            [(fd, bytes(payload), offset) for fd, payload, offset in (entry.args for entry in write.call_args_list)],
            [(31, b"abcdef", 7), (31, b"cdef", 9), (31, b"def", 10)],
        )

    def test_capacity_error_preserves_committed_prefix(self) -> None:
        failure = OSError(errno.ENOSPC, "buffer is full")
        with patch.object(client.os, "pwrite", create=True, side_effect=[3, failure]):
            with self.assertRaises(client.PartialWriteError) as raised:
                self.device.write(b"abcde", offset=61)
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertEqual(raised.exception.bytes_written, 3)
        self.assertEqual(raised.exception.next_offset, 64)
        self.assertIs(raised.exception.__cause__, failure)

    def test_first_write_failure_remains_original_errno(self) -> None:
        failure = OSError(errno.EFAULT, "bad address")
        with patch.object(client.os, "pwrite", create=True, side_effect=failure):
            with self.assertRaises(OSError) as raised:
                self.device.write(b"x")
        self.assertIs(raised.exception, failure)

    def test_zero_write_fails_without_spinning(self) -> None:
        with patch.object(client.os, "pwrite", create=True, return_value=0) as write:
            with self.assertRaises(OSError) as raised:
                self.device.write(b"x")
        self.assertEqual(raised.exception.errno, errno.EIO)
        self.assertEqual(write.call_count, 1)

    def test_zero_write_after_progress_preserves_prefix(self) -> None:
        with patch.object(client.os, "pwrite", create=True, side_effect=[1, 0]):
            with self.assertRaises(client.PartialWriteError) as raised:
                self.device.write(b"ab", offset=4)
        self.assertEqual(raised.exception.errno, errno.EIO)
        self.assertEqual(raised.exception.bytes_written, 1)
        self.assertEqual(raised.exception.next_offset, 5)

    def test_read_combines_short_reads_and_stops_at_eof(self) -> None:
        with patch.object(client.os, "pread", create=True, side_effect=[b"ab", b"c", b""]) as read:
            self.assertEqual(self.device.read(10, offset=5), b"abc")
        self.assertEqual(read.call_args_list, [call(31, 10, 5), call(31, 8, 7), call(31, 7, 8)])

    def test_read_error_is_not_reported_as_successful_eof(self) -> None:
        with patch.object(client.os, "pread", create=True, side_effect=[b"a", OSError(errno.EIO, "I/O error")]):
            with self.assertRaises(OSError) as raised:
                self.device.read(4)
        self.assertEqual(raised.exception.errno, errno.EIO)

    def test_zero_length_io_performs_no_syscalls(self) -> None:
        with patch.object(client.os, "pread", create=True) as read, patch.object(client.os, "pwrite", create=True) as write:
            self.assertEqual(self.device.read(0), b"")
            self.assertEqual(self.device.write(b""), 0)
        read.assert_not_called()
        write.assert_not_called()

    def test_invalid_offsets_and_counts_fail_before_io(self) -> None:
        with patch.object(client.os, "pread", create=True) as read, patch.object(client.os, "pwrite", create=True) as write:
            for operation in (
                lambda: self.device.read(-1),
                lambda: self.device.read(1, offset=-1),
                lambda: self.device.write(b"x", offset=-1),
            ):
                with self.assertRaises(ValueError):
                    operation()
        read.assert_not_called()
        write.assert_not_called()

    def test_shared_descriptor_writers_keep_their_offsets(self) -> None:
        buffer = bytearray(64)
        lock = threading.Lock()
        barrier = threading.Barrier(4)

        def pwrite(descriptor: int, payload: memoryview, offset: int) -> int:
            # Force each client write to span several syscalls.
            amount = min(3, len(payload))
            with lock:
                buffer[offset:offset + amount] = payload[:amount]
            return amount

        def writer(index: int) -> None:
            barrier.wait(timeout=5)
            self.assertEqual(self.device.write(bytes([65 + index]) * 16, offset=index * 16), 16)

        with patch.object(client.os, "pwrite", create=True, side_effect=pwrite), patch.object(client.os, "lseek", side_effect=AssertionError("unexpected shared-position change")):
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(writer, index) for index in range(4)]
                for future in futures:
                    future.result(timeout=10)
        self.assertEqual(bytes(buffer), b"A" * 16 + b"B" * 16 + b"C" * 16 + b"D" * 16)

    def test_nested_context_does_not_leak_another_descriptor(self) -> None:
        with patch.object(client.os, "open") as open_device:
            with self.assertRaisesRegex(RuntimeError, "already open"):
                self.device.__enter__()
        open_device.assert_not_called()

    def test_close_failure_invalidates_descriptor(self) -> None:
        with patch.object(client.os, "close", side_effect=OSError(errno.EIO, "close failed")) as close:
            with self.assertRaises(OSError):
                self.device.__exit__(None, None, None)
            self.device.__exit__(None, None, None)
        close.assert_called_once_with(31)
        with self.assertRaisesRegex(RuntimeError, "not open"):
            _ = self.device.descriptor

    def test_closed_client_rejects_even_empty_io(self) -> None:
        self.device._descriptor = None
        for operation in (lambda: self.device.read(0), lambda: self.device.write(b"")):
            with self.assertRaisesRegex(RuntimeError, "not open"):
                operation()


if __name__ == "__main__":
    unittest.main()
