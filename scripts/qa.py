"""Cross-platform VerityGraph quality gate.

Use `python scripts/qa.py` for fast checks and `python scripts/qa.py --e2e`
for the containerized browser journey as well.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Sequence


def run(command: Sequence[str]) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)


def executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        raise SystemExit(f"Required executable not found on PATH: {name}")
    return resolved


def wait_for(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status < 500:
                    return
        except OSError:
            time.sleep(2)
    raise SystemExit(f"Timed out waiting for {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2e", action="store_true", help="Run Docker + Playwright journey")
    args = parser.parse_args()

    python = sys.executable
    npm = executable("npm")

    run([python, "-m", "ruff", "check", "backend", "scripts"])
    run([python, "-m", "pytest", "backend/tests", "-q"])
    run([npm, "--prefix", "frontend", "install"])
    run([npm, "--prefix", "frontend", "run", "build"])

    if not args.e2e:
        print("\nFast QA passed. Add --e2e for the full browser gate.")
        return 0

    docker = executable("docker")
    try:
        run([docker, "compose", "up", "-d", "--build"])
        wait_for("http://localhost:3000")
        run([npm, "--prefix", "e2e", "install"])
        run([npm, "--prefix", "e2e", "exec", "playwright", "install", "chromium"])
        run([npm, "--prefix", "e2e", "test"])
    finally:
        subprocess.run([docker, "compose", "down", "--remove-orphans"], check=False)

    print("\nFull VerityGraph QA passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
