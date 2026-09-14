# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors
# SPDX-FileNotice: Part of the FreeCAD project.

"""GUI tests for the Linear and Polar Pattern tools.

The tools start sized to what they copy, pick features and directions by clicking
in the view, and drive distance, angle and count from handles and boxes in the view.

To run tests:
    FreeCAD -t TestPatternPanel
"""

import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

import TestExtrudeFlip as extrude
import TestGizmoValueLabels as gizmo_labels

# Gui::GizmoValueLabel::boxName and ::countBoxName.
BOX_NAME = "GizmoValueBox"
COUNT_BOX_NAME = "GizmoCountBox"
PAD_VOLUME = 10.0 * 6.0 * 10.0


class PatternPanelCase(unittest.TestCase):
    """A 10 x 6 x 10 mm Pad in the active Body, ready for a pattern command."""

    # Borrowed rather than inherited, so this suite runs none of their tests again.
    _process_events = extrude.ExtrudePanelCase._process_events
    _close_editing = extrude.ExtrudePanelCase._close_editing
    _draw_rectangle = staticmethod(extrude.ExtrudePanelCase._draw_rectangle)
    _find_widget = staticmethod(extrude.ExtrudePanelCase._find_widget)
    _refresh_view_widgets = extrude.TestExtrudeDrag._refresh_view_widgets
    _pixels = extrude.TestExtrudeDrag._pixels
    _qt_pos = extrude.TestExtrudeDrag._qt_pos
    _mouse = extrude.TestExtrudeDrag._mouse
    _wait = gizmo_labels.GizmoLabelCase._wait
    _press = gizmo_labels.GizmoLabelCase._press
    _type = gizmo_labels.GizmoLabelCase._type
    _select_all = gizmo_labels.GizmoLabelCase._select_all
    _screen_point = gizmo_labels.GizmoLabelCase._screen_point
    _box_centre_on_screen = gizmo_labels.GizmoLabelCase._box_centre_on_screen
    _dragger_under = gizmo_labels.TestGizmoValueLabels._dragger_under

    def setUp(self):
        try:
            main = FreeCADGui.getMainWindow()
        except (AttributeError, RuntimeError):
            main = None
        if main is None:
            raise unittest.SkipTest("The pattern tools need a main window")
        import PartDesignGui  # noqa: F401  registers the PartDesign commands

        self.doc = FreeCAD.newDocument("TestPatternPanel")
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
        self._refresh_view_widgets()
        self.view.setActiveObject("pdbody", self.body)
        main.raise_()
        main.activateWindow()
        self.pattern = None

    def tearDown(self):
        self._close_editing()
        FreeCADGui.Selection.clearSelection()
        if self.doc is not None and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _run(self, command, select_pad=True):
        """Run a pattern command the way the ribbon does and return the new pattern."""

        FreeCADGui.Selection.clearSelection()
        if select_pad:
            FreeCADGui.Selection.addSelection(self.doc.Name, self.pad.Name)
        FreeCADGui.runCommand(command, 0)
        self._process_events(300)
        self.pattern = self.body.Tip
        return self.pattern

    @staticmethod
    def _value(quantity):
        return float(getattr(quantity, "Value", quantity))


class TestStartValues(PatternPanelCase):
    """What the tools start with when a feature is selected."""

    def test_a_linear_pattern_starts_sized_to_its_feature(self):
        pattern = self._run("PartDesign_LinearPattern")
        self.assertEqual(pattern.Mode, "Spacing")
        # The Pad is 10 mm along the sketch's horizontal axis: 1.5 x 10.
        self.assertAlmostEqual(self._value(pattern.Offset), 15.0)
        self.assertEqual(pattern.Occurrences, 3)
        self.assertEqual(pattern.Direction[0], self.sketch)
        self.assertEqual(pattern.Direction[1], ["H_Axis"])

    def test_a_linear_pattern_leaves_its_second_direction_empty(self):
        pattern = self._run("PartDesign_LinearPattern")
        self.assertIsNone(pattern.Direction2)
        self.assertEqual(pattern.Occurrences2, 1)

    def test_the_copies_come_out_whole(self):
        pattern = self._run("PartDesign_LinearPattern")
        self.assertTrue(pattern.isValid(), pattern.getStatusString())
        self.assertAlmostEqual(pattern.Shape.Volume, 3 * PAD_VOLUME, places=3)

    def test_a_body_that_must_stay_one_solid_gets_touching_copies(self):
        self.body.AllowCompound = False
        self.doc.recompute()
        pattern = self._run("PartDesign_LinearPattern")
        self.assertAlmostEqual(self._value(pattern.Offset), 10.0)
        self.assertEqual(len(pattern.Shape.Solids), 1)

    def test_a_polar_pattern_starts_with_four_copies_round_a_full_circle(self):
        pattern = self._run("PartDesign_PolarPattern")
        self.assertAlmostEqual(self._value(pattern.Angle), 360.0)
        self.assertEqual(pattern.Occurrences, 4)
        self.assertEqual(pattern.Axis[0], self.sketch)
        self.assertEqual(pattern.Axis[1], ["N_Axis"])
