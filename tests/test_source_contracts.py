from __future__ import annotations

import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "kernel" / "simple_char.c").read_text(encoding="utf-8")


class KernelSourceContractTests(unittest.TestCase):
    def test_user_copies_use_kernel_helpers(self) -> None:
        self.assertIn("copy_to_user", SOURCE)
        self.assertIn("copy_from_user", SOURCE)
        self.assertNotRegex(SOURCE, r"memcpy\s*\([^,]+__user")

    def test_shared_state_is_mutex_protected(self) -> None:
        self.assertIn("struct mutex lock", SOURCE)
        self.assertGreaterEqual(SOURCE.count("mutex_lock_interruptible"), 6)
        self.assertGreaterEqual(SOURCE.count("mutex_unlock"), 6)

    def test_cleanup_labels_are_reverse_ordered(self) -> None:
        labels = [
            "error_destroy_device:",
            "error_destroy_class:",
            "error_unregister_region:",
            "error_cleanup_i2c:",
            "error_cleanup_gpio:",
            "error_free_buffer:",
            "error_free_device:",
        ]
        offsets = [SOURCE.index(label) for label in labels]
        self.assertEqual(offsets, sorted(offsets))

    def test_hardware_defaults_are_opt_in(self) -> None:
        self.assertRegex(SOURCE, r"static bool enable_gpio;")
        self.assertRegex(SOURCE, r"static bool enable_i2c;")
        self.assertGreaterEqual(SOURCE.count("capable(CAP_SYS_RAWIO)"), 2)

    def test_character_device_lifecycle_is_complete(self) -> None:
        for token in (
            "alloc_chrdev_region",
            "cdev_add",
            "class_create",
            "device_create",
            "device_destroy",
            "class_destroy",
            "cdev_del",
            "unregister_chrdev_region",
        ):
            with self.subTest(token=token):
                self.assertIn(token, SOURCE)

    def test_uapi_uses_no_raw_pointers(self) -> None:
        header = (ROOT / "include" / "uapi" / "simple_char_ioctl.h").read_text(
            encoding="utf-8"
        )
        self.assertNotRegex(header, re.compile(r"\bvoid\s*\*"))
        self.assertIn("__u64", header)
        self.assertIn("__u32", header)


if __name__ == "__main__":
    unittest.main()
