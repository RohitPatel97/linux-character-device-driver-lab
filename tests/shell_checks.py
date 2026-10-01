"""Unprivileged shell-checker regressions; requires Bash, never loads a module.

Run separately from portable host discovery: python3 -m tests.shell_checks
"""

from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class ShellCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        if BASH is None:
            self.fail("shell checker regressions require Bash on PATH")
        self.bash = str(Path(BASH).resolve())
        self.directory = self.enterContext(
            tempfile.TemporaryDirectory(prefix="simple char shell checks ")
        )
        self.root = Path(self.directory)
        self.scripts = self.root / "scripts with spaces"
        self.commands = self.root / "commands with spaces"
        self.scripts.mkdir()
        self.commands.mkdir()
        self.checker = self.scripts / "check-shell.sh"
        self.checker.write_bytes((ROOT / "scripts" / "check-shell.sh").read_bytes())
        self.first = self.scripts / "a valid script.sh"
        self.later = self.scripts / "z later script.sh"
        self.first.write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
        self.later.write_text("#!/usr/bin/env bash\ntrue\n", encoding="utf-8")
        self.ordered_scripts = [self.first, self.later, self.checker]

        # A private PATH guarantees the fallback is exercised even on CI hosts
        # with ShellCheck installed. All fixture scripts use the real Bash.
        (self.commands / "bash").symlink_to(self.bash)
        self.write_command("dirname", 'printf "%s\\n" "${1%/*}"\n')
        paths = " ".join(shlex.quote(str(path)) for path in self.ordered_scripts)
        self.write_command("find", f"printf '%s\\0' {paths}\n")
        self.environment = os.environ.copy()
        self.environment["PATH"] = str(self.commands)
        self.environment["LC_ALL"] = "C"
        self.environment.pop("BASH_ENV", None)
        self.environment.pop("ENV", None)

    def write_command(self, name: str, body: str) -> None:
        command = self.commands / name
        command.write_text(f"#!{self.bash}\n{body}", encoding="utf-8")
        command.chmod(0o755)

    def run_command(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            arguments,
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def run_checker(self) -> subprocess.CompletedProcess[str]:
        return self.run_command([self.bash, str(self.checker)])

    def test_invalid_later_script_fails_without_shellcheck(self) -> None:
        self.later.write_text("#!/usr/bin/env bash\nif then\n", encoding="utf-8")

        # Reproduce the old command first: later filenames are arguments, so
        # Bash incorrectly reports success despite the second script's error.
        old_command = self.run_command(
            [self.bash, "-n", *(str(path) for path in self.ordered_scripts)]
        )
        self.assertEqual(old_command.returncode, 0, old_command.stderr)

        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(self.later), result.stderr)
        self.assertIn("syntax error", result.stderr)
        self.assertNotIn("bash syntax check passed", result.stderr)

    def test_valid_scripts_with_spaces_pass_without_shellcheck(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "shellcheck not installed; bash syntax check passed", result.stderr
        )

    def test_shellcheck_receives_all_paths_and_failure_propagates(self) -> None:
        self.write_command("shellcheck", "printf '%s\\n' \"$@\"\nexit 7\n")
        result = self.run_checker()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertEqual(
            result.stdout.splitlines(), [str(path) for path in self.ordered_scripts]
        )
        self.assertNotIn("shellcheck not installed", result.stderr)


def main() -> int:
    if BASH is None:
        print(
            "shell checker regressions require Bash on PATH; run this suite on a Bash-equipped host",
            file=sys.stderr,
        )
        return 2
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ShellCheckerTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
