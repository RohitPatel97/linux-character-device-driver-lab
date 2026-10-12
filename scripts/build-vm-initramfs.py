#!/usr/bin/env python3
"""Pack a disposable Linux test root; never mount or load modules on the host."""

from __future__ import annotations

import argparse
import gzip
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def build(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vm-root-", dir=output.parent) as directory:
        root = Path(directory).resolve()

        def copy(source: Path, destination: str | None = None) -> None:
            target = root / (destination or str(source)).lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=True)

        def elf(source: Path, destination: str | None = None) -> None:
            copy(source, destination)
            result = subprocess.run(
                ["ldd", str(source)], check=True, capture_output=True, text=True
            )
            if "not found" in result.stdout:
                raise RuntimeError(f"missing runtime library for {source}: {result.stdout}")
            for library in re.findall(r"(/[^\s()]+)", result.stdout):
                copy(Path(library))

        for name in ("dev", "proc", "sys", "tmp", "bin", "usr/bin", "project"):
            (root / name).mkdir(parents=True, exist_ok=True)
        busybox = Path(shutil.which("busybox") or "/bin/busybox")
        copy(busybox, "/bin/busybox")  # CI installs busybox-static.
        applets = subprocess.check_output([str(busybox), "--list"], text=True).split()
        for applet in applets:
            (root / "bin" / applet).symlink_to("busybox")
        (root / "usr/bin/env").symlink_to("/bin/busybox")
        elf(Path("/bin/bash"))
        elf(Path(sys.executable), "/usr/bin/python3")
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        stdlib = root / "usr/lib" / version
        shutil.copytree(
            sysconfig.get_path("stdlib"), stdlib,
            ignore=shutil.ignore_patterns("__pycache__", "test", "tests", "site-packages"),
        )
        # ldd resolves transitive dependencies for extension modules as well.
        for extension in Path(sysconfig.get_path("stdlib")).rglob("*.so"):
            result = subprocess.run(["ldd", str(extension)], check=True, capture_output=True, text=True)
            if "not found" in result.stdout:
                raise RuntimeError(f"missing extension library: {extension}")
            for library in re.findall(r"(/[^\s()]+)", result.stdout):
                copy(Path(library))
        for name in ("user", "tests", "scripts"):
            shutil.copytree(ROOT / name, root / "project" / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        copy(ROOT / "kernel/simple_char.ko", "/project/kernel/simple_char.ko")
        elf(ROOT / "user/simple-char-cli", "/project/user/simple-char-cli")
        elf(ROOT / "build/user-copy-faults", "/project/build/user-copy-faults")
        copy(ROOT / "scripts/vm-init.sh", "/init")
        (root / "init").chmod(0o755)
        paths = [".", *(str(path.relative_to(root)) for path in sorted(root.rglob("*")))]
        archive = subprocess.run(
            ["cpio", "--null", "-o", "--format=newc", "--owner=0:0"],
            input=("\0".join(paths) + "\0").encode(), cwd=root,
            capture_output=True, check=True,
        )
        with gzip.open(output, "wb", compresslevel=1) as compressed:
            compressed.write(archive.stdout)
    print(f"Created {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("build this initramfs on Linux")
    build(args.output.resolve())
