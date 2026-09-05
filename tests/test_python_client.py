from __future__ import annotations

import dataclasses
import unittest

from user import simple_char_client as client


class PythonClientAbiTests(unittest.TestCase):
    def test_fixed_width_stats_layout(self) -> None:
        self.assertEqual(client.STATS_STRUCT.size, 72)
        self.assertEqual(client.GPIO_STRUCT.size, 4)
        self.assertEqual(client.I2C_STRUCT.size, 8)

    def test_ioctl_numbers_match_asm_generic_encoding(self) -> None:
        self.assertEqual(client.IOC_GET_STATS, 0x8048B701)
        self.assertEqual(client.IOC_CLEAR, 0x0000B702)
        self.assertEqual(client.IOC_GPIO_SET, 0x4004B703)
        self.assertEqual(client.IOC_I2C_WRITE_REG, 0x4008B704)

    def test_stats_decoder(self) -> None:
        raw = client.STATS_STRUCT.pack(
            7, 3, 4, 100, 200, 12, 4096, 2, -28, 1, 0, 1, 0
        )
        stats = client.Stats.unpack(raw)
        self.assertEqual(stats.open_count, 7)
        self.assertEqual(stats.last_error, -28)
        self.assertTrue(stats.gpio_enabled)
        self.assertTrue(stats.i2c_enabled)
        self.assertEqual(dataclasses.asdict(stats)["capacity"], 4096)

    def test_byte_parser_supports_decimal_and_hex(self) -> None:
        self.assertEqual(client._parse_byte("255"), 255)
        self.assertEqual(client._parse_byte("0x2a"), 42)


if __name__ == "__main__":
    unittest.main()

