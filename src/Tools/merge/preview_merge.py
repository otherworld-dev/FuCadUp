#!/usr/bin/env python3
"""Show what merging an upstream branch would cost, without touching anything.

git can work the whole merge out in a temporary index, so the conflict list is
available in seconds and before any decision is made. Run this first: a handful
of conflicts is an hour's work, thirty is a day's, and knowing which it is
decides whether to merge now or set time aside.

    python src/Tools/merge/preview_merge.py [--upstream upstream/main] [--branch HEAD]
"""

import argparse
import collections
import subprocess
import sys


def git(*args, check=True):
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    )
    if check and result.returncode != 0 and not result.stdout:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="upstream/main")
    parser.add_argument("--branch", default="HEAD")
    args = parser.parse_args()

    base = git("merge-base", args.branch, args.upstream).stdout.strip()
    if not base:
        sys.exit(f"no common ancestor between {args.branch} and {args.upstream}")

    ahead = git("rev-list", "--count", f"{base}..{args.branch}").stdout.strip()
    behind = git("rev-list", "--count", f"{base}..{args.upstream}").stdout.strip()
    prs = git(
        "log", "--merges", "--format=%s", f"{base}..{args.upstream}"
    ).stdout.count("Merge pull request")

    print(f"merge base   : {base[:10]}")
    print(f"ours ahead   : {ahead} commits")
    print(f"upstream new : {behind} commits ({prs} merged PRs)")

    # merge-tree does the whole three-way merge in a temporary index. It exits
    # non-zero on conflicts, which is the normal case here, so ignore the status
    # and read the output: first line is the tree, then the conflicted paths.
    tree_run = git(
        "merge-tree", "--write-tree", "--name-only", args.upstream, args.branch,
        check=False,
    )
    lines = tree_run.stdout.splitlines()
    if not lines:
        sys.exit(f"merge-tree produced nothing:\n{tree_run.stderr.strip()}")

    conflicts = []
    for line in lines[1:]:
        if not line.strip():
            break  # blank line ends the path list; prose follows
        conflicts.append(line.strip())

    if not conflicts:
        print("\nno conflicts - this should merge clean")
        return 0

    translations = [c for c in conflicts if "/translations/" in c or c.endswith(".ts")]
    real = [c for c in conflicts if c not in translations]

    print(f"\nconflicts    : {len(conflicts)} files "
          f"({len(real)} code, {len(translations)} translations)")

    by_area = collections.Counter()
    for path in real:
        parts = path.split("/")
        area = "/".join(parts[:3]) if path.startswith("src/Mod/") else "/".join(parts[:2])
        by_area[area] += 1

    print("\nby area:")
    for area, count in by_area.most_common():
        print(f"  {count:>3}  {area}")

    print("\nconflicting files:")
    for path in real:
        print(f"  {path}")

    print(f"\nrough guide: under 10 is an hour, 25+ is a day. "
          f"Merge on a branch, then run check_merge.py before building.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
