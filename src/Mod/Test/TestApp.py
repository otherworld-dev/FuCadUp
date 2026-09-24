# ***************************************************************************
# *   Copyright (c) 2002 Juergen Riegel <juergen.riegel@web.de>             *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************/

import FreeCAD
import faulthandler
import os
import sys
import unittest

# ---------------------------------------------------------------------------
# define the functions to test the FreeCAD base code
# ---------------------------------------------------------------------------


def tryLoadingTest(testName):
    "Loads and returns testName, or a failing TestCase if unsuccessful."

    try:
        return unittest.defaultTestLoader.loadTestsFromName(testName)

    except ImportError:

        class LoadFailed(unittest.TestCase):
            def __init__(self, testName):
                # setattr() first, because TestCase ctor checks for methodName.
                setattr(self, "failed_to_load_" + testName, self._runTest)
                super(LoadFailed, self).__init__("failed_to_load_" + testName)
                self.testName = testName

            def __name__(self):
                return "Loading " + self.testName

            def _runTest(self):
                self.fail("Couldn't load " + self.testName)

        return LoadFailed(testName)


def All():
    # Registered tests
    tests = FreeCAD.__unit_test__

    suite = unittest.TestSuite()

    for test in tests:
        suite.addTest(tryLoadingTest(test))

    return suite


def PrintAll():
    # Registered tests
    tests = FreeCAD.__unit_test__

    suite = unittest.TestSuite()

    FreeCAD.Console.PrintMessage("\nRegistered test units:\n\n")
    for test in tests:
        FreeCAD.Console.PrintMessage(("%s\n" % test))
    FreeCAD.Console.PrintMessage("\nPlease choose one or use 0 for all\n")

    return suite


def TestText(s):
    s = unittest.defaultTestLoader.loadTestsFromName(s)
    r = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    retval = r.run(s)
    # Flushing to make sure the stream is written to the console
    # before the wrapping process stops executing. Without this line
    # executing the tests from command line did not show stats
    # and proper traceback in some cases.
    sys.stdout.flush()
    return retval


# Kept open for the life of the run: faulthandler writes to the file descriptor, not to
# the Python object, and would lose it to garbage collection.
_watchdogFile = None


def _armWatchdog():
    """Dump every thread's stack to FREECAD_TEST_WATCHDOG_FILE once the run has taken
    FREECAD_TEST_WATCHDOG seconds.

    A runner that kills a hung test run (.github/scripts/run_gui_tests.py) otherwise
    learns only that it hung, not where. The dump comes from a thread of its own, so
    it still works while the main thread is blocked inside native code, and it goes
    to a file because in the GUI sys.stderr is the Report view, which has no file
    descriptor.
    """
    global _watchdogFile
    try:
        seconds = float(os.environ.get("FREECAD_TEST_WATCHDOG", "0"))
    except ValueError:
        return
    path = os.environ.get("FREECAD_TEST_WATCHDOG_FILE")
    if seconds <= 0 or not path:
        return
    _watchdogFile = open(path, "w")
    faulthandler.dump_traceback_later(seconds, file=_watchdogFile)


def RunConfiguredTextTest():
    _armWatchdog()
    test_cases = FreeCAD.ConfigGet("TestCase").split(",")
    if len(test_cases) == 1:
        return TestText(test_cases[0])
    suite = unittest.TestSuite()
    for tc in test_cases:
        suite.addTest(tryLoadingTest(tc))
    r = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    sys.stdout.flush()
    return r.run(suite)


def Test(s):
    TestText(s)


def testAll():
    r = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    return r.run(All())


def testUnit():
    TestText(unittest.TestLoader().loadTestsFromName("UnitTests"))


def testDocument():
    suite = unittest.TestSuite()
    suite.addTest(unittest.defaultTestLoader.loadTestsFromName("Document"))
    TestText(suite)
