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

"""GUI regression tests for turning an extrude around through its profile.

Dragging the length arrow of a Pad past the profile means the material that was
being added is now being taken away, so the task panel swaps Join for Cut and
turns the extrusion around. The gizmo reports the same negative distance on every
mouse move while the pointer stays on the far side, so the swap has to happen once
per crossing of zero and not once per event.

To run tests:
    FreeCAD -t TestExtrudeFlip
"""

import time
import unittest

import FreeCAD
import FreeCADGui
import Part
import Sketcher
from PySide import QtCore, QtWidgets

# PartDesign::FeatureAddSub::OperationType, see src/Mod/PartDesign/App/FeatureAddSub.h.
JOIN = 0
CUT = 1
INTERSECT = 2
NEW_BODY = 3


class TestExtrudeFlip(unittest.TestCase):
    """A length dragged or typed past the profile turns the extrude around exactly once."""

    def setUp(self):
        try:
            main_window = FreeCADGui.getMainWindow()
        except (AttributeError, RuntimeError):
            main_window = None
        if main_window is None:
            raise unittest.SkipTest("The extrude task panel needs a main window")

        self.doc = FreeCAD.newDocument("TestExtrudeFlip")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)

        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = (self.doc.XY_Plane, [""])
        self.sketch.MapMode = "FlatFace"
        self.body.addObject(self.sketch)
        self._draw_rectangle(self.sketch, 10.0, 6.0)
        self.doc.recompute()

        self.pad = self.doc.addObject("PartDesign::Pad", "Pad")
        self.pad.Profile = self.sketch
        self.pad.Length = 10.0
        self.body.addObject(self.pad)
        self.doc.recompute()
        self._process_events()

        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pad.Name)
        self._process_events(100)

        self.lengthEdit = self._find_widget("lengthEdit")
        self.operationMode = self._find_widget("operationMode")
        self.checkBoxReversed = self._find_widget("checkBoxReversed")
        if self.lengthEdit is None or self.operationMode is None:
            self._close_editing()
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None
            raise unittest.SkipTest("The Pad task panel did not open in this test environment")

    def tearDown(self):
        self._close_editing()
        if self.doc is not None and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _close_editing(self):
        try:
            FreeCADGui.getDocument(self.doc.Name).resetEdit()
        except (AttributeError, RuntimeError, NameError):
            pass
        self._process_events()
        if FreeCADGui.Control.activeDialog() is not None:
            FreeCADGui.Control.closeDialog()
            self._process_events()
        # Reap the closed panel now, so the next one's widgets are the only ones
        # answering to these object names.
        QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)

    @staticmethod
    def _draw_rectangle(sketch, width, height):
        """A closed rectangle, the smallest profile a Pad will accept."""

        corners = [
            FreeCAD.Vector(0.0, 0.0, 0.0),
            FreeCAD.Vector(width, 0.0, 0.0),
            FreeCAD.Vector(width, height, 0.0),
            FreeCAD.Vector(0.0, height, 0.0),
        ]
        first = int(sketch.GeometryCount)
        for index in range(4):
            sketch.addGeometry(
                Part.LineSegment(corners[index], corners[(index + 1) % 4]), False
            )
        for index in range(4):
            sketch.addConstraint(
                Sketcher.Constraint(
                    "Coincident", first + index, 2, first + (index + 1) % 4, 1
                )
            )

    @staticmethod
    def _find_widget(name):
        """The task panel lives in a dock of the main window, not in a dialog."""

        main = FreeCADGui.getMainWindow()
        fallback = None
        for widget in main.findChildren(QtWidgets.QWidget, name):
            if widget.isVisible():
                return widget
            if fallback is None:
                fallback = widget
        return fallback

    def _set_raw_length(self, value):
        self.lengthEdit.setProperty("rawValue", float(value))
        self._process_events()

    def _length(self):
        length = self.pad.Length
        return float(getattr(length, "Value", length))

    def _swatch_colour(self, index):
        icon = self.operationMode.itemIcon(index)
        self.assertFalse(icon.isNull(), f"operation {index} has no colour swatch")
        image = icon.pixmap(12, 12).toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2)

    # -- tests -----------------------------------------------------------

    def test_a_negative_length_turns_the_pad_into_a_cut(self):
        self._set_raw_length(-5.0)

        self.assertEqual(self.pad.Type, "Length")
        self.assertAlmostEqual(self._length(), 5.0)
        self.assertTrue(self.pad.Reversed)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        # The panel never shows the negative that got us here.
        self.assertAlmostEqual(self.lengthEdit.property("rawValue"), 5.0)

    def test_the_operation_flips_once_per_crossing_not_once_per_event(self):
        """The gizmo resends the same negative on every mouse move."""

        self._set_raw_length(-5.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)

        self._set_raw_length(-7.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 7.0)

        self._set_raw_length(-9.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 9.0)

    def test_coming_back_over_the_profile_restores_the_operation(self):
        self._set_raw_length(-5.0)
        self._set_raw_length(-7.0)

        self._set_raw_length(3.0)

        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertFalse(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 3.0)

    def test_repeated_crossings_alternate(self):
        for step, (raw, operation, reversed_) in enumerate(
            [
                (-3.0, CUT, True),
                (-5.0, CUT, True),
                (-7.0, CUT, True),
                (2.0, JOIN, False),
                (4.0, JOIN, False),
                (-1.0, CUT, True),
                (6.0, JOIN, False),
            ]
        ):
            with self.subTest(step=step, raw=raw):
                self._set_raw_length(raw)
                self.assertEqual(self.operationMode.currentIndex(), operation)
                self.assertEqual(bool(self.pad.Reversed), reversed_)
                self.assertAlmostEqual(self._length(), abs(raw))

    def test_a_cut_typed_negative_becomes_a_join(self):
        self.operationMode.setCurrentIndex(CUT)
        self._process_events()
        self.assertFalse(self.pad.Reversed)

        self._set_raw_length(-4.0)

        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 4.0)

    def test_intersect_only_turns_around(self):
        """Intersect has no opposite, so a crossing may only reverse it."""

        self.operationMode.setCurrentIndex(INTERSECT)
        self._process_events()

        self._set_raw_length(-5.0)

        self.assertEqual(self.operationMode.currentIndex(), INTERSECT)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 5.0)

        self._set_raw_length(-8.0)
        self.assertEqual(self.operationMode.currentIndex(), INTERSECT)
        self.assertTrue(self.pad.Reversed)

        self._set_raw_length(2.0)
        self.assertEqual(self.operationMode.currentIndex(), INTERSECT)
        self.assertFalse(self.pad.Reversed)

    def test_new_body_only_turns_around(self):
        self.operationMode.setCurrentIndex(NEW_BODY)
        self._process_events()

        self._set_raw_length(-5.0)

        self.assertEqual(self.operationMode.currentIndex(), NEW_BODY)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 5.0)

    def test_an_up_to_mode_never_flips(self):
        """Only a plain distance can cross the profile."""

        changeMode = self._find_widget("changeMode")
        self.assertIsNotNone(changeMode)
        changeMode.setCurrentIndex(1)  # Through all
        self._process_events()

        self._set_raw_length(-5.0)

        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertFalse(self.pad.Reversed)

    def test_every_operation_carries_a_colour_swatch(self):
        self.assertEqual(self.operationMode.count(), 4)

        join = self._swatch_colour(JOIN)
        cut = self._swatch_colour(CUT)
        intersect = self._swatch_colour(INTERSECT)
        newBody = self._swatch_colour(NEW_BODY)

        # Join adds, Cut removes and Intersect keeps the overlap, so the three
        # read as three different colours. A new body is added material too.
        self.assertNotEqual(join.rgb(), cut.rgb())
        self.assertNotEqual(join.rgb(), intersect.rgb())
        self.assertNotEqual(cut.rgb(), intersect.rgb())
        self.assertEqual(join.rgb(), newBody.rgb())

    def test_the_operation_combo_explains_the_preview_colours(self):
        tooltip = self.operationMode.toolTip()
        self.assertTrue(tooltip)
        # The colour hint is added below whatever the .ui file already said.
        self.assertIn("\n", tooltip)
        self.assertTrue(tooltip.split("\n")[-1].strip())
