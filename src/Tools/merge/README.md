# Merging FreeCAD upstream

FuCadUp tracks FreeCAD's `main`. Upstream lands roughly 85 commits a week, so
the gap grows quickly and the cost of closing it grows faster than the gap does.

## Cadence

Merge weekly. Conflicts do not scale linearly with how long you wait: at a week
they are mostly two branches adding a line to the same `CMakeLists.txt`, but at
a month both sides have had time to restructure the same code, and a file that
has been reorganised on both sides cannot be merged at all — it has to be taken
from upstream and have our changes reapplied by hand.

For reference, the 2026-09-10 merge covered four weeks (359 commits, 68 merged
PRs) and produced 24 conflicts, two of which were total rewrites.

## The steps

```sh
git fetch upstream main

# 1. Cost first, before deciding anything. Touches nothing.
python src/Tools/merge/preview_merge.py

# 2. Merge on a branch, never on main.
git checkout -b merge/upstream-$(date +%Y-%m)
git merge upstream/main

# 3. Resolve, then audit before building: both of these failures are silent.
python src/Tools/merge/check_merge.py

# 4. Submodules move with upstream.
git submodule update --init --recursive

# 5. Build and test (see the test note below), then fast-forward main.
```

## What the audit catches

`check_merge.py` looks for two things that neither git nor the compiler will
tell you about:

- **A dropped change.** A file this fork had modified comes out byte-identical
  to upstream, because a hunk was resolved with "theirs" when it should have
  combined both sides. The build stays green and the feature is quietly gone.
  This caught a real one in the 2026-09-10 merge: upstream keys `isGroove` on
  `getAddSubType()`, which changes with the operation here, and taking their
  line back would have made the revolution mode list shift under the user.

- **Line endings.** Most of this tree is CRLF; upstream is drifting to LF file
  by file. Match whatever upstream has for a given file — that is what stops the
  next merge seeing the whole file as changed.

## Where conflicts keep coming from

Roughly 440 source files differ from upstream. These are the ones upstream also
changes often, so they are worth checking first:

| Area | Ours |
| --- | --- |
| `Mod/Sketcher/Gui/ViewProviderSketch.cpp`, `EditModeCoinManager.cpp` | snapping, face preselection |
| `Gui/View3DInventorViewer.cpp`, `Gui/SoFCDB.cpp` | viewport grid, Fusion navigation style |
| `Gui/Application.cpp`, `App/Application.cpp` | ribbon, startup |
| `Mod/PartDesign/App/Feature*.cpp` | the merged additive/subtractive operation model |
| `*/CMakeLists.txt` | both sides adding files |

The PartDesign ones are structural rather than accidental. Making one tool both
additive and subtractive is the point of the fork, so every upstream change to
those features touches it. Expect that cost rather than trying to remove it.

## Testing after a merge

Qt's widget tests need the platform plugin on the environment or they fail in a
way that looks like a real breakage:

```sh
export QT_PLUGIN_PATH=$PWD/.pixi/envs/default/Library/lib/qt6/plugins
export QT_QPA_PLATFORM_PLUGIN_PATH=$QT_PLUGIN_PATH/platforms
pixi run -- ctest --test-dir build/release --output-on-failure
pixi run -- build/release/bin/FuCadUpCmd.exe -t TestPartDesignApp
pixi run -- build/release/bin/FuCadUp.exe -t TestTimeline
```

Judge a GUI suite by its `Ran N tests` line rather than by the exit code alone.

If a run dies, `src/Tools/read_crash_report.py --latest` prints the most recent
crash report, and the exception code usually places the fault on its own.
