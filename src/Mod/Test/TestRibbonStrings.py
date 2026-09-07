# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors
# SPDX-FileNotice: Part of the FreeCAD project.

################################################################################
#                                                                              #
#   FreeCAD is free software: you can redistribute it and/or modify            #
#   it under the terms of the GNU Lesser General Public License as             #
#   published by the Free Software Foundation, either version 2.1              #
#   of the License, or (at your option) any later version.                     #
#                                                                              #
#   FreeCAD is distributed in the hope that it will be useful,                 #
#   but WITHOUT ANY WARRANTY; without even the implied warranty                #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.                    #
#   See the GNU Lesser General Public License for more details.                #
#                                                                              #
#   You should have received a copy of the GNU Lesser General Public           #
#   License along with FreeCAD. If not, see https://www.gnu.org/licenses       #
#                                                                              #
################################################################################

"""The ribbon's translatable strings are the ones its workspace definitions hold.

The ribbon shows the tab titles, panel captions and button labels of
src/Gui/Ribbon/Workspaces/*.json through QCoreApplication::translate("Ribbon", ...),
but lupdate reads source and not data, so a translator would never be offered them.
src/Tools/ribbon_strings.py copies them into src/Gui/Ribbon/RibbonStrings.cpp as
QT_TRANSLATE_NOOP entries, which lupdate does read.

Nothing rebuilds that file automatically, so this test is what stops a JSON edit
from silently dropping a string out of the translation catalogue: it re-runs the
generator's own collection over the JSON and compares the result with what the
generated file lists.

No GUI is needed - the test reads files.

To run tests:
    FreeCAD -t TestRibbonStrings
"""

import importlib.util
import os
import unittest

GENERATOR = os.path.join("src", "Tools", "ribbon_strings.py")
WORKSPACES = os.path.join("src", "Gui", "Ribbon", "Workspaces")
GENERATED = os.path.join("src", "Gui", "Ribbon", "RibbonStrings.cpp")


def _find_source_tree():
    """The checkout this build came from, or None when it is not next to us.

    An installed FreeCAD carries neither the JSON nor the generator, so the test
    can only run from a source tree or from a build directory inside one. The
    search walks up from this file, which covers both the source copy and the copy
    the build installs under Mod/Test.
    """

    directory = os.path.dirname(os.path.abspath(__file__))
    while True:
        if all(
            os.path.exists(os.path.join(directory, part))
            for part in (GENERATOR, WORKSPACES, GENERATED)
        ):
            return directory

        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


def _load_generator(root):
    """Import src/Tools/ribbon_strings.py from \\a root under its own name."""

    path = os.path.join(root, GENERATOR)
    spec = importlib.util.spec_from_file_location("ribbon_strings", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRibbonStrings(unittest.TestCase):
    """RibbonStrings.cpp must list exactly the strings the workspaces can show."""

    def setUp(self):
        self.root = _find_source_tree()
        if self.root is None:
            raise unittest.SkipTest(
                "No source tree above {} holds {}, {} and {}".format(
                    os.path.dirname(os.path.abspath(__file__)), GENERATOR, WORKSPACES, GENERATED
                )
            )
        self.generator = _load_generator(self.root)

    def _from_the_json(self):
        return self.generator.collect_strings(os.path.join(self.root, WORKSPACES))

    def _from_the_generated_file(self):
        with open(os.path.join(self.root, GENERATED), encoding="utf-8", newline="") as handle:
            return self.generator.strings_in_generated(handle.read())

    def test_the_generated_file_is_not_empty(self):
        """A silently empty collection would make every other assert here vacuous."""

        self.assertGreater(len(self._from_the_json()), 100)

    def test_the_generated_file_matches_the_workspaces(self):
        """Regenerate with: python src/Tools/ribbon_strings.py"""

        wanted = set(self._from_the_json())
        found = set(self._from_the_generated_file())

        missing = sorted(wanted - found)
        extra = sorted(found - wanted)
        self.assertEqual(
            (missing, extra),
            ([], []),
            "{} is out of date - rerun 'python {}'. Missing: {}. No longer in the "
            "workspaces: {}.".format(GENERATED, GENERATOR, missing, extra),
        )

    def test_every_string_is_listed_once(self):
        """A duplicate would give lupdate the same source string twice."""

        found = self._from_the_generated_file()
        self.assertEqual(len(found), len(set(found)))

    def test_the_generated_file_says_how_to_rebuild_it(self):
        """Whoever a failure above lands on has to be told what to run."""

        with open(os.path.join(self.root, GENERATED), encoding="utf-8", newline="") as handle:
            head = handle.read(4096)

        self.assertIn("GENERATED FILE", head)
        self.assertIn("ribbon_strings.py", head)
