#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FuCad contributors
# SPDX-FileNotice: Part of the FreeCAD project.

"""Collect the ribbon's user-visible strings out of the workspace definitions.

The ribbon is described by ``src/Gui/Ribbon/Workspaces/*.json`` rather than by
source, and every caption it shows goes through
``QCoreApplication::translate("Ribbon", ...)`` (``translateRibbon`` in
``src/Gui/Ribbon/RibbonManager.cpp``). ``lupdate`` reads source, not data, so it
never sees those strings and a translator is given nothing to translate. This
script writes them into a generated C++ file as ``QT_TRANSLATE_NOOP`` entries,
which ``lupdate`` does read, so the "Ribbon" context ends up carrying exactly the
strings the ribbon can show.

The keys collected are the ones ``translateRibbon`` is actually called with:

* ``tabs[].id`` and ``contextTabs[].id`` - the strip titles
  (``RibbonManager.cpp`` lines 285 and 648; the id doubles as the title, and
  stays the untranslated lookup key everywhere else)
* ``...panels[].caption`` - the panel captions (line 724)
* ``...panels[].items[].label`` and ``...panels[].menu[].label`` - the button and
  menu-entry labels (lines 730, 820 and 841)

Nothing else in the file reaches a user: ``command``, ``workbench``,
``initWorkbench``, ``align``, ``optional``, ``primary`` and the ``commands``
lists are identifiers, and the document's own ``name`` ("Design") is never
displayed. A menu item that carries no ``label`` falls back to its command's own
text, which ``lupdate`` already finds in the command's source.

Usage::

    python src/Tools/ribbon_strings.py            # rewrite RibbonStrings.cpp
    python src/Tools/ribbon_strings.py --check    # exit 1 if it is out of date

Run it from anywhere; paths default to the tree this script lives in.
"""

import argparse
import json
import os
import re
import sys

HEADER = """\
/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/

// GENERATED FILE - DO NOT EDIT.
//
// Rebuild it with:
//     python src/Tools/ribbon_strings.py
// and check it with:
//     python src/Tools/ribbon_strings.py --check
//
// The ribbon's tab titles, panel captions and button labels live in
// Ribbon/Workspaces/*.json, which lupdate never reads; RibbonManager.cpp shows
// them through QCoreApplication::translate("Ribbon", ...). Listing them here as
// QT_TRANSLATE_NOOP puts them in front of lupdate under that same context, so a
// translator sees them. Nothing reads the array - it exists to be scanned.
//
// TestRibbonStrings.py fails if this file and the JSON disagree.

// QT_TRANSLATE_NOOP comes from qglobal.h, which <QtGlobal> is the header for.
#include <QtGlobal>


namespace
{
// NOLINTNEXTLINE(modernize-avoid-c-arrays,cppcoreguidelines-avoid-c-arrays)
[[maybe_unused]] const char* const ribbonStrings[] = {
"""

FOOTER = """};
}  // namespace
"""


def _labels(entries):
    """The ``label`` of every entry of an ``items`` or ``menu`` array."""

    for entry in entries or []:
        if isinstance(entry, dict):
            label = entry.get("label")
            if label:
                yield label


def strings_of_workspace(document):
    """Every user-visible string of one parsed workspace definition."""

    found = []
    for key in ("tabs", "contextTabs"):
        for tab in document.get(key) or []:
            if not isinstance(tab, dict):
                continue
            if tab.get("id"):
                found.append(tab["id"])
            for panel in tab.get("panels") or []:
                if not isinstance(panel, dict):
                    continue
                if panel.get("caption"):
                    found.append(panel["caption"])
                found.extend(_labels(panel.get("items")))
                found.extend(_labels(panel.get("menu")))

    return found


def collect_strings(workspaces_dir):
    """Every user-visible string of every workspace, unique and sorted."""

    found = []
    for name in sorted(os.listdir(workspaces_dir)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(workspaces_dir, name), encoding="utf-8") as handle:
            found.extend(strings_of_workspace(json.load(handle)))

    return sorted(set(found))


def escape(text):
    """\\a text as the body of a C++ string literal."""

    return text.replace("\\", "\\\\").replace('"', '\\"')


def render(strings):
    """The whole generated file for \\a strings."""

    body = "".join(
        '    QT_TRANSLATE_NOOP("Ribbon", "{}"),\n'.format(escape(text)) for text in strings
    )
    return HEADER + body + FOOTER


#: One QT_TRANSLATE_NOOP entry, wherever the formatter has put its line breaks.
ENTRY = re.compile(r'QT_TRANSLATE_NOOP\s*\(\s*"Ribbon"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')


def strings_in_generated(text):
    """The strings a generated file lists, in the order it lists them.

    Read back with the same escaping ``render`` applies, so the comparison is of
    strings rather than of literals, and matched across the whole text rather than
    line by line so that reformatting the file cannot hide an entry.
    """

    return [unescape(match.group(1)) for match in ENTRY.finditer(text)]


def unescape(literal):
    """The inverse of \\a escape."""

    out = []
    escaped = False
    for char in literal:
        if escaped:
            out.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            out.append(char)

    return "".join(out)


def source_root():
    """The ``src`` directory this script lives in."""

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    src = source_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workspaces",
        default=os.path.join(src, "Gui", "Ribbon", "Workspaces"),
        help="directory holding the workspace .json files",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(src, "Gui", "Ribbon", "RibbonStrings.cpp"),
        help="the C++ file to write",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the output is not what would be written",
    )
    args = parser.parse_args(argv)

    strings = collect_strings(args.workspaces)

    if args.check:
        # Compared as strings rather than as bytes, so that reformatting the file
        # (clang-format runs over src/Gui) is not reported as being out of date.
        try:
            with open(args.output, encoding="utf-8", newline="") as handle:
                current = strings_in_generated(handle.read())
        except OSError as exc:
            print("{}: {}".format(args.output, exc), file=sys.stderr)
            return 1
        if current != strings:
            missing = sorted(set(strings) - set(current))
            extra = sorted(set(current) - set(strings))
            print(
                "{} is out of date; rerun {} to regenerate it. "
                "missing: {}; no longer in the workspaces: {}".format(
                    args.output, os.path.relpath(os.path.abspath(__file__)), missing, extra
                ),
                file=sys.stderr,
            )
            return 1
        return 0

    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(render(strings))
    print("wrote {}".format(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
