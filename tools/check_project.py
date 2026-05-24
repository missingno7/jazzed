from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    targets = [
        "jazz1_dos_level_editor.py",
        "jazzed_editor",
        "tests",
        "tools",
    ]
    print("+ python -m compileall", " ".join(targets))
    ok = compileall.compile_dir(ROOT / "jazzed_editor", quiet=1)
    ok = compileall.compile_file(str(ROOT / "jazz1_dos_level_editor.py"), quiet=1) and ok
    ok = compileall.compile_dir(ROOT / "tests", quiet=1) and ok
    ok = compileall.compile_dir(ROOT / "tools", quiet=1) and ok
    if not ok:
        return 1

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    run([
        sys.executable,
        "-c",
        "from jazzed_editor.raw.codecs import signed_byte; "
        "from jazzed_editor.raw.models import BulletDefinition; "
        "print('import_ok', signed_byte(255), BulletDefinition(0, '', bytes(20)).xspeeds)",
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
