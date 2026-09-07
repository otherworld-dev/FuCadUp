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

"""GUI regression tests for PartDesign task panel titles matching the ribbon.

The ribbon (src/Gui/Ribbon/Workspaces/Design.json) labels PartDesign_Extrude
"Extrude", PartDesign_Thickness "Shell" and PartDesign_LinearPattern "Rectangular
Pattern". Opening the task panel to edit the underlying Pad, Pocket, Thickness or
LinearPattern feature must show the same name, not the legacy "Pad Parameters" /
"Pocket Parameters", "Thickness Parameters" or "Linear Pattern Parameters" wording.

To run tests:
    FreeCAD -t TestPartDesignDialogTitles
"""

import unittest

import FreeCAD
import FreeCADGui
import Part
import Sketcher
from PySide import QtWidgets


def _rectangle_sketch(doc, body, name, corner=(0.0, 0.0), size=(10.0, 10.0)):
    """A minimal closed-wire sketch on the XY plane, suitable as a Pad/Pocket profile."""

    xmin, ymin = corner
    xmax, ymax = xmin + size[0], ymin + size[1]
    sketch = doc.addObject("Sketcher::SketchObject", name)
    body.addObject(sketch)
    geometry = [
        Part.LineSegment(FreeCAD.Vector(xmin, ymin, 0), FreeCAD.Vector(xmax, ymin, 0)),
        Part.LineSegment(FreeCAD.Vector(xmax, ymin, 0), FreeCAD.Vector(xmax, ymax, 0)),
        Part.LineSegment(FreeCAD.Vector(xmax, ymax, 0), FreeCAD.Vector(xmin, ymax, 0)),
        Part.LineSegment(FreeCAD.Vector(xmin, ymax, 0), FreeCAD.Vector(xmin, ymin, 0)),
    ]
    sketch.addGeometry(geometry, False)
    sketch.addConstraint(
        [
            Sketcher.Constraint("Coincident", 0, 2, 1, 1),
            Sketcher.Constraint("Coincident", 1, 2, 2, 1),
            Sketcher.Constraint("Coincident", 2, 2, 3, 1),
            Sketcher.Constraint("Coincident", 3, 2, 0, 1),
            Sketcher.Constraint("Horizontal", 0),
            Sketcher.Constraint("Horizontal", 2),
            Sketcher.Constraint("Vertical", 1),
            Sketcher.Constraint("Vertical", 3),
        ]
    )
    return sketch


class TestPartDesignDialogTitles(unittest.TestCase):
    """The task panel opened for a feature must be titled like its ribbon command.

    PartDesign_Extrude covers both PartDesign::Pad and PartDesign::Pocket (it adds or
    removes material from the same kind of profile depending on the selection), so
    both of their task panels must read "Extrude", matching the ribbon and
    TaskExtrudeParameters's own dialog, not the legacy "Pad Parameters" /
    "Pocket Parameters" wording.
    """

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestPartDesignDialogTitles")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.body = self.doc.addObject("PartDesign::Body", "Body")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _task_panel_titles(self):
        """Visible text of every task-box header currently open in the Tasks dock."""

        FreeCADGui.updateGui()
        QtWidgets.QApplication.instance().processEvents()
        tasks = FreeCADGui.getMainWindow().findChild(QtWidgets.QWidget, "Tasks")
        self.assertIsNotNone(tasks, "Could not find the 'Tasks' dock widget")
        return [
            button.text() for button in tasks.findChildren(QtWidgets.QToolButton) if button.text()
        ]

    def _assert_task_panel_title(self, feature, expected):
        """Edit ``feature`` and assert its task box header reads ``expected``."""

        started = FreeCADGui.ActiveDocument.setEdit(feature.Name)
        self.assertTrue(started, f"Could not start editing {feature.Name}")
        try:
            titles = self._task_panel_titles()
            self.assertIn(
                expected, titles, f"Expected task panel titled {expected!r}, found {titles!r}"
            )
        finally:
            FreeCADGui.ActiveDocument.resetEdit()

    # -- tests -------------------------------------------------------------------

    def test_pad_title_matches_the_ribbons_extrude(self):
        sketch = _rectangle_sketch(self.doc, self.body, "PadSketch")
        self.doc.recompute()
        pad = self.doc.addObject("PartDesign::Pad", "Pad")
        self.body.addObject(pad)
        pad.Profile = sketch
        pad.Length = 10.0
        self.doc.recompute()
        self._assert_task_panel_title(pad, "Extrude")

    def test_pocket_title_matches_the_ribbons_extrude(self):
        pad_sketch = _rectangle_sketch(self.doc, self.body, "PadSketch")
        self.doc.recompute()
        pad = self.doc.addObject("PartDesign::Pad", "Pad")
        self.body.addObject(pad)
        pad.Profile = pad_sketch
        pad.Length = 1.0
        pad.Reversed = True
        self.doc.recompute()

        pocket_sketch = _rectangle_sketch(
            self.doc, self.body, "PocketSketch", corner=(2.5, 2.5), size=(5.0, 5.0)
        )
        self.doc.recompute()
        pocket = self.doc.addObject("PartDesign::Pocket", "Pocket")
        self.body.addObject(pocket)
        pocket.Profile = pocket_sketch
        pocket.Length = 1.0
        self.doc.recompute()
        self._assert_task_panel_title(pocket, "Extrude")

    def test_thickness_title_matches_the_ribbons_shell(self):
        box = self.doc.addObject("PartDesign::AdditiveBox", "Box")
        self.body.addObject(box)
        box.Length = 10.0
        box.Width = 10.0
        box.Height = 10.0
        self.doc.recompute()
        thickness = self.doc.addObject("PartDesign::Thickness", "Thickness")
        self.body.addObject(thickness)
        thickness.Base = (box, ["Face1"])
        thickness.Value = 1.0
        self.doc.recompute()
        self._assert_task_panel_title(thickness, "Shell")

    def test_linear_pattern_title_matches_the_ribbons_rectangular_pattern(self):
        box = self.doc.addObject("PartDesign::AdditiveBox", "Box")
        self.body.addObject(box)
        box.Length = 10.0
        box.Width = 10.0
        box.Height = 10.0
        self.doc.recompute()
        pattern = self.doc.addObject("PartDesign::LinearPattern", "LinearPattern")
        self.body.addObject(pattern)
        pattern.Originals = [box]
        pattern.Direction = (self.doc.X_Axis, [""])
        pattern.Length = 90.0
        pattern.Occurrences = 3
        self.doc.recompute()
        self._assert_task_panel_title(pattern, "Rectangular Pattern")


if __name__ == "__main__":
    unittest.main()
