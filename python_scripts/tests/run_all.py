#!/usr/bin/env python3
"""
Run every test_*.py in this directory and exit non-zero if any fails.

These suites were written alongside the fixes they cover and lived outside
the repo until now, which meant CI could not run them and a later edit could
silently undo a safety guarantee. That already happened once: a change to
check_remote_stop's contract left a stale expectation in test_bot_control.py
that nothing would have caught.

Each suite is a standalone script that prints its own summary and exits
non-zero on failure, so this runner just executes them as subprocesses --
no pytest dependency, and one failing suite cannot abort the others.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Some suites import the real bot modules, which is slow but not unbounded.
PER_SUITE_TIMEOUT = 300


def main() -> int:
    suites = sorted(HERE.glob("test_*.py"))
    if not suites:
        print("no test suites found", file=sys.stderr)
        return 1

    failures: list[tuple[str, str]] = []
    for suite in suites:
        print(f"\n{'=' * 70}\n{suite.name}\n{'=' * 70}", flush=True)
        try:
            proc = subprocess.run(
                [sys.executable, str(suite)], cwd=HERE,
                capture_output=True, text=True, timeout=PER_SUITE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"TIMEOUT after {PER_SUITE_TIMEOUT}s")
            failures.append((suite.name, f"timed out after {PER_SUITE_TIMEOUT}s"))
            continue

        out = (proc.stdout or "") + (proc.stderr or "")
        print(out.rstrip())
        if proc.returncode != 0:
            failures.append((suite.name, f"exit code {proc.returncode}"))

    print(f"\n{'=' * 70}")
    print(f"{len(suites) - len(failures)}/{len(suites)} suites passed")
    for name, why in failures:
        print(f"  FAILED: {name} ({why})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
