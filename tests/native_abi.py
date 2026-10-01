"""Compare a compiled C UAPI probe with the real Python client; no device needed.

Run ``make check-abi`` on Linux, or supply a compiled probe with
``python3 -m tests.native_abi --probe /path/to/abi-probe``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import unittest

from user import simple_char_client as client


class NativeAbiTests(unittest.TestCase):
    probe = Path(__file__).resolve().parents[1] / "build" / "abi-probe"

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(cls.probe)], check=True, capture_output=True, text=True, timeout=10
        )
        cls.native = json.loads(result.stdout)

    def test_struct_sizes_match_c_header(self) -> None:
        for name, layout in (
            ("stats_size", client.STATS_STRUCT),
            ("gpio_size", client.GPIO_STRUCT),
            ("i2c_size", client.I2C_STRUCT),
        ):
            with self.subTest(struct=name):
                self.assertEqual(self.native[name], layout.size)

    def test_ioctl_numbers_match_c_header(self) -> None:
        for name, operation in (
            ("get_stats", client.IOC_GET_STATS),
            ("clear", client.IOC_CLEAR),
            ("gpio_set", client.IOC_GPIO_SET),
            ("i2c_write_reg", client.IOC_I2C_WRITE_REG),
        ):
            with self.subTest(ioctl=name):
                self.assertEqual(self.native[name], operation)

    def test_stats_wire_layout_and_decoder_match_c_header(self) -> None:
        raw = bytes.fromhex(self.native["stats_hex"])
        # Distinct 64-bit counters catch swapped fields and accidental narrowing;
        # negative errno checks the signed field as well as its byte offset.
        # Unique flag/reserved sentinels test layout, not valid device values.
        counters = tuple((index << 32) + index for index in range(1, 6))
        self.assertEqual(
            raw, client.STATS_STRUCT.pack(*counters, 123, 4096, 7, -28, 11, 12, 13, 14)
        )
        self.assertEqual(
            client.Stats.unpack(raw),
            client.Stats(*counters, 123, 4096, 7, -28, True, 12, True),
        )

    def test_gpio_wire_layout_matches_c_header(self) -> None:
        self.assertEqual(bytes.fromhex(self.native["gpio_hex"]), client.GPIO_STRUCT.pack(1))

    def test_i2c_wire_layout_matches_c_header(self) -> None:
        self.assertEqual(
            bytes.fromhex(self.native["i2c_hex"]), client.I2C_STRUCT.pack(0xab, 0xcd)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", type=Path, default=NativeAbiTests.probe)
    args = parser.parse_args(argv)
    NativeAbiTests.probe = args.probe.resolve()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeAbiTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
