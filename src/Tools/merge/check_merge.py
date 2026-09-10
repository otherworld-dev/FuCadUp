#!/usr/bin/env python3
"""Audit a resolved upstream merge before building it.

Two things go wrong quietly when resolving a large merge, and neither shows up
as a conflict or a compile error:

  lost      a file this fork had changed comes out byte-identical to upstream,
            meaning the resolution took upstream's side wholesale and dropped
            our change. The build stays green and the feature is simply gone.

  endings   most of this tree is CRLF while upstream is drifting to LF file by
            file. An edit written back with the wrong ending turns the next
            diff into whole-file noise. The rule is to match whatever upstream
            has for that file, since that is what keeps future merges quiet.

Run after resolving every conflict and before building:

    python src/Tools/merge/check_merge.py [--upstream upstream/main]

Exits non-zero if anything needs looking at.
"""

import argparse
import subprocess
import sys


def git(*args, check=True):
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, errors="replace"
    )
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def blob(rev, path):
    """The committed (or staged) bytes for a path, or None if it is not there.

    Always bytes as git stores them, never as the working tree renders them.
    """
    spec = f"{rev}:{path}" if rev != ":0" else f":{path}"
    result = subprocess.run(["git", "show", spec], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def endings(data):
    crlf = data.count(b"\r\n")
    return crlf, data.count(b"\n") - crlf


def classify(data):
    """CRLF, LF, or mixed - the shape, for comparing two files.

    Deliberately ignores the counts: a file that gained a line is still the same
    shape as the one it came from, and upstream having twenty LF lines where we
    have twenty-one is not a line-ending problem.
    """
    crlf, lf = endings(data)
    if lf == 0 and crlf:
        return "CRLF"
    if crlf == 0 and lf:
        return "LF"
    return "mixed"


def describe(data):
    """The same thing for a human, with the counts that make mixed meaningful."""
    crlf, lf = endings(data)
    shape = classify(data)
    return shape if shape != "mixed" else f"mixed ({crlf} CRLF / {lf} LF)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="upstream/main")
    parser.add_argument("--ours", default="HEAD",
                        help="the pre-merge tip; defaults to HEAD's first parent when merging")
    args = parser.parse_args()

    # During a merge, HEAD is still our pre-merge tip. Afterwards it is the merge
    # commit, whose first parent is what we had before.
    ours = args.ours
    if ours == "HEAD":
        parents = git("rev-list", "--parents", "-n", "1", "HEAD").split()
        if len(parents) >= 3:  # a merge commit: sha, parent1, parent2
            ours = parents[1]

    base = git("merge-base", ours, args.upstream).strip()
    changed = [
        p for p in git("diff", "--name-only", base, ours).splitlines()
        if p.strip() and "/translations/" not in p
    ]

    print(f"comparing against base {base[:10]}; "
          f"{len(changed)} files this fork changed since then\n")

    lost, eol = [], []
    for path in changed:
        ours_blob = blob(ours, path)
        up_blob = blob(args.upstream, path)
        if ours_blob is None:
            continue  # we deleted it; nothing of ours left to lose

        # Read the resolved content from the index rather than the working tree:
        # git converts line endings on checkout, so working-tree bytes would flag
        # every LF file in the repository as a mismatch. The index holds what will
        # actually be committed, during a merge and after one alike.
        now = blob(":0", path) or blob("HEAD", path)
        if now is None:
            continue  # deleted by the merge, which is a deliberate resolution

        if b"\x00" in now[:8000]:
            continue  # binary

        # Our change survived only if the result still differs from upstream,
        # unless upstream happens to agree with us already.
        if up_blob is not None and ours_blob != up_blob and now == up_blob:
            lost.append(path)

        # Endings should follow upstream where upstream has the file at all.
        if up_blob is not None and classify(up_blob) != classify(now):
            eol.append((path, describe(ours_blob), describe(up_blob), describe(now)))

    if lost:
        print(f"LOST - resolved to upstream's version, our change is gone ({len(lost)}):")
        for path in lost:
            print(f"  {path}")
        print()

    if eol:
        print(f"LINE ENDINGS - do not match upstream ({len(eol)}):")
        for path, was, want, got in eol:
            print(f"  {path}\n      was {was} / upstream {want} / now {got}")
        print()

    if not lost and not eol:
        print("clean: nothing dropped, endings match upstream")
        return 0

    print("Review each of the above. A LOST file usually means a hunk was resolved")
    print("with 'theirs' when it should have combined both sides.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
