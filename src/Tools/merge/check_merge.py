#!/usr/bin/env python3
"""Audit a resolved upstream merge before building it.

This looks for changes of ours that went missing in the resolution, and for line
endings that no longer match upstream. Neither shows up as a conflict, and
neither necessarily stops the build, so both are easy to ship by accident.

    python src/Tools/merge/check_merge.py [--upstream upstream/main]

What it reports:

  GONE      a file this fork had changed is not in the merged tree under any
            path it could have moved to. Either it was deliberately deleted, or
            the resolution lost it.

  LOST      the merged file is byte-identical to upstream's, so the resolution
            took their side wholesale and dropped ours.

  THINNED   most of the lines this fork added to a file are no longer there.
            Some loss is legitimate where upstream restructured around us, so a
            low figure is a prompt to look rather than a verdict.

  ENDINGS   line endings that disagree with upstream's for that file. Most of
            this tree is CRLF while upstream drifts to LF file by file, and
            matching them is what keeps the next diff readable.

What it does not cover, so build and run the tests afterwards regardless:

  - a declaration kept whose definition upstream's refactor removed, or the
    reverse. That is what the compiler is for, and it has caught real ones.
  - whether a resolution is semantically right. Both sides can merge cleanly
    into something that satisfies neither.

Exits non-zero if anything needs looking at.
"""

import argparse
import os
import subprocess
import sys

# Below this share of our added lines surviving, a file is worth a look.
THINNED_AT = 0.5

# ...but only once a file has enough added lines for the share to mean anything.
# A two-line branding tweak that upstream reworded reads as nought per cent kept,
# which is noise rather than signal.
MIN_ADDED = 4


def git(*args, check=True):
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def blob(rev, path):
    """The committed (or staged) bytes for a path, or None if it is not there.

    Always bytes as git stores them, never as the working tree renders them:
    git converts line endings on checkout, so reading from disk would report
    every LF file in the repository as a mismatch.
    """
    spec = f":{path}" if rev == ":0" else f"{rev}:{path}"
    result = subprocess.run(["git", "show", spec], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def renames(base, tip):
    """Map of old path -> new path for files renamed between two revisions."""
    moved = {}
    for line in git("diff", "-M", "--name-status", base, tip).splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) == 3:
            moved[parts[1]] = parts[2]
    return moved


def directory_moves(moved):
    """Directory renames inferred from file renames.

    Upstream renaming a directory while we renamed a file inside it produces a
    path neither map gives on its own, which is exactly how a lost file hides.
    """
    dirs = {}
    for old, new in moved.items():
        old_dir, new_dir = os.path.dirname(old), os.path.dirname(new)
        if old_dir and new_dir and old_dir != new_dir:
            dirs[old_dir] = new_dir
    return dirs


def candidates(path, up_moved, our_moved, up_dirs):
    """Every path the merged file could reasonably be living at, best guess first."""
    found = [path]
    for mapping in (up_moved, our_moved):
        if path in mapping:
            found.append(mapping[path])

    # Our rename of a file combined with upstream's rename of its directory.
    ours = our_moved.get(path, path)
    for old_dir, new_dir in up_dirs.items():
        if ours.startswith(old_dir + "/"):
            found.append(new_dir + ours[len(old_dir):])
        if path.startswith(old_dir + "/"):
            relocated = new_dir + path[len(old_dir):]
            found.append(relocated)
            if relocated in our_moved:
                found.append(our_moved[relocated])

    seen, unique = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def endings(data):
    crlf = data.count(b"\r\n")
    return crlf, data.count(b"\n") - crlf


def classify(data):
    """CRLF, LF or mixed - the shape, ignoring counts, for comparing two files."""
    crlf, lf = endings(data)
    if lf == 0 and crlf:
        return "CRLF"
    if crlf == 0 and lf:
        return "LF"
    return "mixed"


def describe(data):
    crlf, lf = endings(data)
    shape = classify(data)
    return shape if shape != "mixed" else f"mixed ({crlf} CRLF / {lf} LF)"


def added_lines(base_data, ours_data):
    """The non-blank lines this fork added to a file."""
    base_lines = set((base_data or b"").splitlines())
    return [
        line for line in ours_data.splitlines()
        if line.strip() and line not in base_lines
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="upstream/main")
    parser.add_argument("--ours", default="HEAD",
                        help="the pre-merge tip; taken from HEAD's first parent after a merge")
    args = parser.parse_args()

    ours_rev = args.ours
    if ours_rev == "HEAD":
        parents = git("rev-list", "--parents", "-n", "1", "HEAD").split()
        if len(parents) >= 3:  # sha, first parent, second parent
            ours_rev = parents[1]

    base = git("merge-base", ours_rev, args.upstream).strip()
    up_moved = renames(base, args.upstream)
    our_moved = renames(base, ours_rev)
    up_dirs = directory_moves(up_moved)

    changed = [
        p for p in git("diff", "--name-only", base, ours_rev).splitlines()
        if p.strip() and "/translations/" not in p
    ]

    print(f"comparing against base {base[:10]}")
    print(f"{len(changed)} files this fork changed; upstream renamed {len(up_moved)} "
          f"of its own ({len(up_dirs)} directories)\n")

    gone, lost, thinned, eol = [], [], [], []

    for path in changed:
        ours_data = blob(ours_rev, path)
        if ours_data is None:
            continue  # we deleted it ourselves; nothing of ours left to lose

        now = where = None
        for candidate in candidates(path, up_moved, our_moved, up_dirs):
            now = blob(":0", candidate) or blob("HEAD", candidate)
            if now is not None:
                where = candidate
                break

        if now is None:
            gone.append(path)
            continue

        if b"\x00" in now[:8000]:
            continue  # binary

        base_data = blob(base, path)
        up_data = blob(args.upstream, where) or blob(args.upstream, path)

        if up_data is not None and ours_data != up_data and now == up_data:
            lost.append((path, where))
            continue

        mine = added_lines(base_data, ours_data)
        if len(mine) >= MIN_ADDED:
            surviving = set(now.splitlines())
            kept = sum(1 for line in mine if line in surviving)
            if kept / len(mine) < THINNED_AT:
                thinned.append((path, where, kept, len(mine)))

        if up_data is not None and classify(up_data) != classify(now):
            eol.append((where, describe(base_data or b""),
                        describe(up_data), describe(now)))

    def report(title, rows, render):
        if rows:
            print(f"{title} ({len(rows)}):")
            for row in rows:
                print(render(row))
            print()

    report("GONE - not found under any path it could have moved to", gone,
           lambda p: f"  {p}")
    report("LOST - resolved to upstream's version, our change is gone", lost,
           lambda r: f"  {r[0]}" + (f"   -> {r[1]}" if r[1] != r[0] else ""))
    report("THINNED - most of our added lines are missing", thinned,
           lambda r: f"  {r[1]}   kept {r[2]}/{r[3]} added lines")
    report("ENDINGS - do not match upstream", eol,
           lambda r: f"  {r[0]}\n      was {r[1]} / upstream {r[2]} / now {r[3]}")

    tail = ("\nStill build and run the tests: this does not catch a declaration whose\n"
            "definition upstream removed, nor a resolution that is merely wrong.")

    if not (gone or lost or thinned or eol):
        print("clean: nothing dropped, endings match upstream" + tail)
        return 0

    print("Review each of the above. A LOST or THINNED file usually means a hunk was")
    print("resolved with 'theirs' where it should have combined both sides." + tail)
    return 1


if __name__ == "__main__":
    sys.exit(main())
