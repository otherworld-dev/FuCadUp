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

"""GUI regression tests for where a sketch reports how constrained it is.

The same report used to show twice while a sketch was open: on the chip over the
top of the view and on the first line of the Sketch Edit panel. Only the panel's
copy could be clicked, to select whatever the report is about, so the chip could
not simply replace it. The chip now takes the same clicks, and the panel keeps its
line only while the chip is switched off, so the report and what it selects are
never lost either way.

To run tests:
    FreeCAD -t TestSketchStatusChip
"""

import time
import unittest

import FreeCAD
import FreeCADGui
import Part
from FreeCAD import Vector
from PySide import QtCore, QtGui, QtWidgets

from PinnedPreferences import PinnedPreferences

SKETCHER_PARAMS = "User parameter:BaseApp/Preferences/Mod/Sketcher"
CHIP_NAME = "SketchStatusChip"
# The panel's report, see src/Gui/TaskView/TaskSolverMessages.ui.
PANEL_STATUS = ("labelStatus", "labelStatusLink")


class SketchStatusTestCase(unittest.TestCase):
    """Opens a sketch holding one free line, so the report says it is under-constrained."""

    show_chip = True

    def setUp(self):
        self.window = FreeCADGui.getMainWindow()
        if self.window is None:
            raise unittest.SkipTest("No main window in this test environment")

        pins = PinnedPreferences(
            SKETCHER_PARAMS, {"ShowStatusChip": ("bool", self.show_chip)}
        ).pin()
        self.addCleanup(pins.restore)

        self.doc = FreeCAD.newDocument("TestSketchStatusChip")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.sketch.addGeometry(Part.LineSegment(Vector(0, 0, 0), Vector(10, 5, 0)), False)
        self.doc.recompute()

        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        self._wait_for(lambda: FreeCADGui.Control.activeDialog(), "the sketch never opened")
        self._process_events(200)

    def tearDown(self):
        FreeCADGui.Selection.clearSelection()
        if FreeCADGui.ActiveDocument is not None:
            FreeCADGui.ActiveDocument.resetEdit()
        self._process_events()
        FreeCAD.closeDocument(self.doc.Name)
        self._process_events()

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _wait_for(self, condition, message, timeout=5.0):
        deadline = time.monotonic() + timeout
        while not condition():
            if time.monotonic() >= deadline:
                self.fail(message)
            self._process_events(20)

    def _visible(self, object_name):
        for widget in QtWidgets.QApplication.instance().allWidgets():
            if widget.objectName() == object_name and widget.isVisible():
                return widget
        return None


class TestTheChipCarriesTheReport(SketchStatusTestCase):
    """While the chip is on, it is the one place the report is shown and clicked."""

    def test_the_panel_leaves_the_report_to_the_chip(self):
        self._wait_for(lambda: self._visible(CHIP_NAME), "the chip never appeared")
        for name in PANEL_STATUS:
            self.assertIsNone(self._visible(name), "the panel still shows its " + name)

    def test_the_chip_takes_a_click_while_there_is_something_to_select(self):
        chip = self._visible(CHIP_NAME)
        self.assertIsNotNone(chip, "the chip never appeared")
        self.assertFalse(
            chip.testAttribute(QtCore.Qt.WA_TransparentForMouseEvents),
            "clicks on the chip fall through to the view behind it",
        )

    def test_clicking_the_chip_selects_what_is_unconstrained(self):
        chip = self._visible(CHIP_NAME)
        self.assertIsNotNone(chip, "the chip never appeared")
        FreeCADGui.Selection.clearSelection()

        centre = chip.rect().center()
        app = QtWidgets.QApplication.instance()
        for kind in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
            event = QtGui.QMouseEvent(
                kind,
                QtCore.QPointF(centre),
                QtCore.QPointF(chip.mapToGlobal(centre)),
                QtCore.Qt.LeftButton,
                (
                    QtCore.Qt.LeftButton
                    if kind == QtCore.QEvent.MouseButtonPress
                    else QtCore.Qt.NoButton
                ),
                QtCore.Qt.NoModifier,
            )
            app.sendEvent(chip, event)
        self._process_events(100)

        selected = FreeCADGui.Selection.getSelectionEx()
        self.assertTrue(
            selected and selected[0].SubElementNames,
            "clicking the chip selected nothing, where the free line should be selected",
        )


class TestThePanelKeepsTheReportWithoutTheChip(SketchStatusTestCase):
    """Switch the chip off and the panel's line is the report again."""

    show_chip = False

    def test_the_panel_shows_the_report(self):
        self.assertIsNone(self._visible(CHIP_NAME), "the chip showed although it is switched off")
        label = self._visible(PANEL_STATUS[0])
        self.assertIsNotNone(label, "the panel hides its report with no chip to take its place")


if __name__ == "__main__":
    unittest.main()
