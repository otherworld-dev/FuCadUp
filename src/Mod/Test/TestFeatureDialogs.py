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

"""GUI regression tests for what a feature dialog asks the user for.

Editing a pad used to put thirteen controls on screen. Three of them are there
for whoever is debugging the feature rather than modelling with it: the Preview
box, which every PartDesign dialog carries because the base task dialog builds
one, and the "Recompute on change" box that each feature's own form repeats.
Two more, the direction vector and the box that ties the length to the sketch
normal, only mean anything once a direction other than the sketch normal has
been chosen, and were shown whether one had been or not.

The diagnostics are kept behind a preference rather than removed, so the escape
hatch survives for a model slow enough to need it. The direction vector follows
the direction that was actually picked.

To run tests:
    FreeCAD -t TestFeatureDialogs
"""

import time
import unittest

import FreeCAD
import FreeCADGui
import Part
from FreeCAD import Vector
from PySide import QtWidgets

PARTDESIGN_PARAMS = "User parameter:BaseApp/Preferences/Mod/PartDesign"
DIAGNOSTICS_KEY = "ShowFeatureDiagnostics"

# The Preview box the base task dialog builds, see TaskFeatureParameters.cpp.
PREVIEW_BOXES = ("showFinalCheckBox", "showTransparentPreviewCheckBox")
# Each feature form's own copy, see TaskPadPocketParameters.ui and its siblings.
RECOMPUTE_BOX = "checkBoxUpdateView"
# The direction vector and the box that ties the length to the sketch normal.
DIRECTION_GROUP = "groupBoxDirection"
ALONG_NORMAL_BOX = "checkBoxAlongDirection"
DIRECTION_COMBO = "directionCB"


class FeatureDialogTestCase(unittest.TestCase):
    """Opens a pad for editing, which is the dialog every other one follows."""

    def setUp(self):
        self.window = FreeCADGui.getMainWindow()
        if self.window is None:
            raise unittest.SkipTest("No main window in this test environment")

        self.params = FreeCAD.ParamGet(PARTDESIGN_PARAMS)
        self.had_diagnostics = self.params.GetBool(DIAGNOSTICS_KEY, False)

        self.doc = FreeCAD.newDocument("FeatureDialogs")
        body = self.doc.addObject("PartDesign::Body", "Body")
        sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        body.addObject(sketch)
        sketch.AttachmentSupport = [(self.doc.getObject("XY_Plane"), "")]
        sketch.MapMode = "FlatFace"
        corners = [(-20, -15), (20, -15), (20, 15), (-20, 15)]
        for index, start in enumerate(corners):
            end = corners[(index + 1) % len(corners)]
            sketch.addGeometry(
                Part.LineSegment(Vector(start[0], start[1], 0), Vector(end[0], end[1], 0)),
                False,
            )

        self.pad = self.doc.addObject("PartDesign::Pad", "Pad")
        self.pad.Profile = sketch
        self.pad.Length = 10
        body.addObject(self.pad)
        self.doc.recompute()
        self._process_events()

    def tearDown(self):
        try:
            if FreeCADGui.Control.activeDialog():
                FreeCADGui.Control.closeDialog()
                self._process_events()
        finally:
            self.params.SetBool(DIAGNOSTICS_KEY, self.had_diagnostics)
            FreeCAD.closeDocument(self.doc.Name)
            self._process_events()

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _open_pad_dialog(self):
        FreeCADGui.ActiveDocument.setEdit(self.pad, 0)
        deadline = time.monotonic() + 5.0
        while not FreeCADGui.Control.activeDialog() and time.monotonic() < deadline:
            self._process_events(20)
        self.assertTrue(FreeCADGui.Control.activeDialog(), "The pad dialog did not open")
        self._process_events(100)

    def _visible(self, object_name):
        """The named widget if the dialog is showing it, otherwise None."""

        for widget in self.window.findChildren(QtWidgets.QWidget, object_name):
            if widget.isVisible():
                return widget
        return None


class TestDiagnosticControls(FeatureDialogTestCase):
    """The controls for debugging a feature stay out of the modelling dialog."""

    def test_the_preview_box_is_not_offered_by_default(self):
        self._open_pad_dialog()
        for name in PREVIEW_BOXES:
            self.assertIsNone(
                self._visible(name),
                "The pad dialog still shows the preview control " + name,
            )

    def test_recompute_on_change_is_not_offered_by_default(self):
        self._open_pad_dialog()
        self.assertIsNone(
            self._visible(RECOMPUTE_BOX),
            "The pad dialog still shows Recompute on change",
        )

    def test_the_preference_brings_the_diagnostics_back(self):
        self.params.SetBool(DIAGNOSTICS_KEY, True)
        self._open_pad_dialog()

        self.assertIsNotNone(
            self._visible(RECOMPUTE_BOX),
            "Recompute on change should return with the preference set",
        )
        for name in PREVIEW_BOXES:
            self.assertIsNotNone(
                self._visible(name),
                "The preview control " + name + " should return with the preference set",
            )


class TestDirectionControls(FeatureDialogTestCase):
    """The direction vector follows the direction that was actually chosen."""

    def test_the_vector_is_hidden_while_the_sketch_normal_is_used(self):
        self._open_pad_dialog()

        self.assertIsNone(
            self._visible(DIRECTION_GROUP),
            "The direction vector is shown for an extrude along the sketch normal",
        )
        self.assertIsNone(
            self._visible(ALONG_NORMAL_BOX),
            "The along-sketch-normal box is shown when nothing else is on offer",
        )

    def test_the_vector_appears_once_a_direction_is_chosen(self):
        self._open_pad_dialog()

        combo = self._visible(DIRECTION_COMBO)
        self.assertIsNotNone(combo, "The pad dialog should still offer a direction")
        self.assertGreater(combo.count(), 1, "Expected a direction beyond the sketch normal")

        # setCurrentIndex alone changes the text without telling anyone: the dialog
        # listens for activated, which only a user choosing an entry emits.
        combo.setCurrentIndex(combo.count() - 1)
        combo.activated.emit(combo.currentIndex())
        self._process_events(150)

        self.assertIsNotNone(
            self._visible(DIRECTION_GROUP),
            "The direction vector should appear once a custom direction is chosen",
        )


if __name__ == "__main__":
    unittest.main()
