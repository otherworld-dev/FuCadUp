#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""
run_gui_tests.py

List registered tests via `FuCadUp -t` and run each registered module in its own process, using
the specified FuCadUp executable.

Modules are deliberately not filtered by name. The GUI binary is what registers the suites that
need a display, and this fork's own suites are named TestRibbon, TestTimeline, TestPatternPanel
and so on, so selecting for a 'Gui' substring silently skipped every one of them.

Each module gets a process of its own and a time limit. Running them all through a single
`FuCadUp -t 0` meant one module that hung held up every module after it, and because output
reached the log in batches there was no telling which module it had been. A module that runs past
its limit is killed along with anything it started and reported as hung, and the rest carry on.

A module is also failed if it prints no test total. A GUI binary that cannot start its Python side
prints a traceback, runs nothing and still exits 0, so the exit code alone cannot tell a pass from
a module that verified nothing.

Usage:
  run_gui_tests.py [FUCAD_EXEC] [--timeout SECONDS] [--only MODULE ...]

If FUCAD_EXEC is omitted the script falls back to 'FuCadUp' on PATH.
If FUCAD_EXEC is a directory containing bin/FuCadUp, that binary is used.
If FUCAD_EXEC is an executable path, it is used directly.
--only runs just the named modules, which is handy when working on one by hand.

This script returns 0 if every module passed, and 1 if any failed, hung or ran nothing.
"""

from __future__ import annotations
import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# unittest prints "Ran 1 test" as well as "Ran 12 tests", so the s is optional.
TEST_TOTAL = re.compile(r"^Ran \d+ tests?\b", re.MULTILINE)
TEST_FAILURE = re.compile(r"^FAILED \(", re.MULTILINE)

# Long enough for the slowest suite seen so far, which is a minute or two, with plenty to spare.
DEFAULT_MODULE_TIMEOUT = 600

OUTCOMES = ("passed", "failed", "hung", "ran nothing")


def find_executable(arg: str | None) -> str:
    """Return the FuCadUp executable path to use.

    If `arg` is None or empty, returns the plain name 'FuCadUp' which will be looked up on PATH. If
    `arg` is a directory and contains `bin/FuCadUp` that binary will be returned. If `arg` is a file
    path it is returned as-is. Otherwise the original argument is returned.

    Common use cases: use the FuCadUp binary from a build directory or an installed FuCadUp prefix.
    """
    if not arg:
        return "FuCadUp"
    p = Path(arg)
    if p.is_dir():
        candidate = p / "bin" / "FuCadUp"
        if candidate.exists():
            return str(candidate)
    if p.is_file():
        return str(p)
    # fallback: return as-is (may be on PATH)
    return arg


def validate_executable(path: str) -> tuple[bool, str]:
    """Return (ok, message). Checks if the executable exists or is likely on PATH.

    This is best effort: if a bare name is given (e.g. 'FuCadUp') we can't stat it here, so we
    accept it but warn. If the path points to a file, we check executability. Also warn if the name
    looks like the CLI-only 'FuCadUpCmd'.
    """
    p = Path(path)
    if p.is_file():
        if not os.access(str(p), os.X_OK):
            return False, f"File exists but is not executable: {path}"
        if p.name.endswith("FuCadUpCmd"):
            return (
                True,
                (
                    "Warning: executable looks like 'FuCadUpCmd' (CLI); GUI tests require the GUI "
                    "binary 'FuCadUp'."
                ),
            )
        return True, ""
    # Bare name or non-existent path: accept but warn
    if p.name.endswith("FuCadUpCmd"):
        return (
            True,
            (
                "Warning: executable name looks like 'FuCadUpCmd' (CLI); GUI tests require the GUI "
                "binary 'FuCadUp'."
            ),
        )
    return True, ""


def run_and_capture(cmd: list[str]) -> tuple[int, str]:
    """Run `cmd` and return (returncode, combined stdout+stderr string).

    If the executable is not found a return code of 127 is returned and a small error string is
    provided as output to aid diagnosis.
    """
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
        )
        return proc.returncode, proc.stdout
    except FileNotFoundError:
        return 127, f"Executable not found: {cmd[0]}\n"


def parse_registered_tests(output: str) -> list[str]:
    """Parse output from `FuCadUp -t` and return a list of registered test unit names.

    The function looks for the section starting with the literal 'Registered test units:' and
    then collects non-empty, stripped lines from that point onwards as test names.
    """
    lines = output.splitlines()
    tests: list[str] = []
    started = False
    for ln in lines:
        if not started:
            if "Registered test units:" in ln:
                started = True
            continue
        s = ln.strip()
        if not s:
            # allow blank lines but keep going
            continue
        tests.append(s)
    return tests


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill `proc` and anything it started.

    Killing the binary alone can leave a helper it spawned holding the output pipe open, and then
    reading what the module printed would wait for ever. On POSIX the module runs in a session of
    its own, so the whole group goes at once.
    """
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
    proc.kill()


def run_module(fucad_exec: str, module: str, timeout: float) -> tuple[int, str, bool]:
    """Run one test module in its own process and return (returncode, output, timed_out)."""
    try:
        proc = subprocess.Popen(
            [fucad_exec, "-t", module],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            start_new_session=(os.name == "posix"),
        )
    except FileNotFoundError:
        return 127, f"Executable not found: {fucad_exec}\n", False

    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out or "", False
    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        out, _ = proc.communicate()
        return proc.returncode, out or "", True


def classify(returncode: int, output: str, timed_out: bool) -> str:
    """Name what happened to one module: passed, failed, hung or ran nothing."""
    if timed_out:
        return "hung"
    if not TEST_TOTAL.search(output):
        return "ran nothing"
    if returncode != 0 or TEST_FAILURE.search(output):
        return "failed"
    return "passed"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run each registered FuCadUp test module.")
    parser.add_argument("fucad_exec", nargs="?", default=None, help="FuCadUp binary or build dir")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_MODULE_TIMEOUT,
        help="seconds a module may run before it is killed and reported as hung",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="MODULE",
        help="run only this module; may be given more than once",
    )
    return parser.parse_args(argv[1:])


def main(argv: list[str]) -> int:
    """Entry point: run every registered test module, each in a process of its own.

    Returns 0 if every module passed and 1 if any failed, hung or ran nothing.
    """
    args = parse_args(argv)
    fucad_exec = find_executable(args.fucad_exec)

    print(f"Using FuCadUp executable: {fucad_exec}")

    ok, msg = validate_executable(fucad_exec)
    if msg:
        print(msg, file=sys.stderr)
    if not ok:
        print(f"Aborting: invalid FuCadUp executable: {fucad_exec}", file=sys.stderr)
        return 3

    code, out = run_and_capture([fucad_exec, "-t"])
    if code != 0:
        print(
            f"Warning: listing tests returned exit code {code}; attempting to parse output anyway",
            file=sys.stderr,
        )

    tests = parse_registered_tests(out)
    if not tests:
        # An empty list is a binary that could not list its tests, not a clean run.
        print(out)
        print("::error::No registered test modules were found, so nothing was verified.")
        return 1

    if args.only:
        unknown = [name for name in args.only if name not in tests]
        if unknown:
            print("::error::Not registered: " + ", ".join(unknown))
            return 1
        tests = [name for name in tests if name in args.only]

    print(f"Running {len(tests)} registered test modules, {args.timeout:.0f}s each at most:")
    for t in tests:
        print("  ", t)
    sys.stdout.flush()

    results: dict[str, list[str]] = {outcome: [] for outcome in OUTCOMES}
    for mod in tests:
        # Flushed as it goes: a log that arrives in batches cannot say where a run stopped.
        print(f"\nRunning tests for module: {mod}", flush=True)
        started = time.monotonic()
        rc, out, timed_out = run_module(fucad_exec, mod, args.timeout)
        elapsed = time.monotonic() - started
        print(out, flush=True)

        outcome = classify(rc, out, timed_out)
        results[outcome].append(mod)
        print(f"Module {mod}: {outcome} in {elapsed:.0f}s (exit code {rc})", flush=True)
        if outcome == "hung":
            print(f"::error::{mod} was still running after {args.timeout:.0f}s and was killed")
        elif outcome == "ran nothing":
            print(f"::error::{mod} printed no test total, so it verified nothing")
        elif outcome == "failed":
            print(f"::error::{mod} failed")

    print("\nSummary")
    for outcome in OUTCOMES:
        print(f"  {outcome}: {len(results[outcome])}")
        if outcome != "passed":
            for mod in results[outcome]:
                print(f"    {mod}")

    bad = [mod for outcome in OUTCOMES if outcome != "passed" for mod in results[outcome]]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
