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
from PySide import QtCore, QtGui, QtWidgets

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

    def _click(self, widget):
        """A left click in the middle of a widget."""

        from PySide import QtGui

        centre = QtCore.QPointF(widget.rect().center())
        for kind, buttons in (
            (QtCore.QEvent.MouseButtonPress, QtCore.Qt.LeftButton),
            (QtCore.QEvent.MouseButtonRelease, QtCore.Qt.NoButton),
        ):
            event = QtGui.QMouseEvent(
                kind, centre, widget.mapToGlobal(centre.toPoint()),
                QtCore.Qt.LeftButton, buttons, QtCore.Qt.NoModifier,
            )
            QtWidgets.QApplication.sendEvent(widget, event)
        self._process_events(100)

    def _direction_widget(self, number):
        return self._find_widget(f"patternDirection{number}")

    def _direction_field(self, number):
        return self._direction_widget(number).findChild(QtWidgets.QFrame, "pickDirection")

    def _edge_along(self, axis):
        """The name of a straight Pad edge running along axis."""

        for index, edge in enumerate(self.pad.Shape.Edges):
            direction = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
            if direction.Length > 1e-6 and abs(abs(direction.normalize().dot(axis)) - 1.0) < 1e-6:
                return f"Edge{index + 1}"
        self.fail(f"the Pad has no edge along {axis}")

    def _pick(self, subname, obj=None):
        """What a click on an element in the view does to the selection."""

        FreeCADGui.Selection.addSelection(self.doc.Name, (obj or self.pad).Name, subname)
        self._process_events(300)

    def _escape(self):
        for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            QtWidgets.QApplication.sendEvent(
                self.viewport, QtGui.QKeyEvent(kind, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
            )
        self._process_events(300)

    @staticmethod
    def _tr(context, text):
        return QtCore.QCoreApplication.translate(context, text)


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


class TestDirectionFields(PatternPanelCase):
    """Directions are picked in fields, not chosen from a drop-down with a special item."""

    def setUp(self):
        super().setUp()
        self._run("PartDesign_LinearPattern")

    def test_the_direction_field_names_the_sketch_axis(self):
        field = self._direction_field(1)
        self.assertEqual(
            field.property("summary"),
            self._tr("PartDesignGui::TaskTransformedParameters", "Horizontal sketch axis"),
        )

    def test_the_quick_picks_offer_axes_but_no_select_reference_item(self):
        menu = self._direction_field(1).findChild(QtWidgets.QToolButton, "pickFieldMenu").menu()
        texts = [action.text() for action in menu.actions()]
        self.assertIn(self._tr("PartDesignGui::TaskTransformedParameters", "Base Y-axis"), texts)
        self.assertNotIn(
            self._tr("PartDesignGui::TaskTransformedParameters", "Select reference…"), texts
        )

    def test_a_quick_pick_sets_the_direction(self):
        menu = self._direction_field(1).findChild(QtWidgets.QToolButton, "pickFieldMenu").menu()
        wanted = self._tr("PartDesignGui::TaskTransformedParameters", "Base Y-axis")
        next(action for action in menu.actions() if action.text() == wanted).trigger()
        self._process_events(300)
        self.assertEqual(getattr(self.pattern.Direction[0], "Role", ""), "Y_Axis")

    def test_the_reverse_button_turns_the_direction_round(self):
        self._click(self._direction_field(1).findChild(QtWidgets.QToolButton, "pickFieldReverse"))
        self.assertTrue(self.pattern.Reversed)

    def test_clicking_the_field_waits_for_an_edge(self):
        field = self._direction_field(1)
        self._click(field)
        self.assertTrue(field.property("active"))
        edge = self._edge_along(FreeCAD.Vector(0, 1, 0))
        self._pick(edge)
        self.assertEqual(self.pattern.Direction[0], self.pad)
        self.assertEqual(self.pattern.Direction[1], [edge])
        self.assertFalse(field.property("active"))

    def test_direction_2_starts_empty_and_says_how_to_add_one(self):
        field = self._direction_field(2)
        self.assertEqual(
            field.property("summary"),
            self._tr("PartDesignGui::TaskPatternParameters", "Click an edge to add"),
        )
        values = self._direction_widget(2).findChild(QtWidgets.QWidget, "valuesRow")
        self.assertFalse(values.isVisible())

    def test_picking_an_edge_turns_direction_2_on_sized_to_the_feature(self):
        self._click(self._direction_field(2))
        edge = self._edge_along(FreeCAD.Vector(0, 1, 0))
        self._pick(edge)
        self.assertEqual(self.pattern.Direction2[1], [edge])
        self.assertEqual(self.pattern.Occurrences2, 2)
        self.assertEqual(self.pattern.Mode2, "Spacing")
        # The Pad is 6 mm along Y: 1.5 x 6.
        self.assertAlmostEqual(self._value(self.pattern.Offset2), 9.0)
        values = self._direction_widget(2).findChild(QtWidgets.QWidget, "valuesRow")
        self.assertTrue(values.isVisible())

    def test_the_cross_turns_direction_2_off_again(self):
        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        self._click(self._direction_field(2).findChild(QtWidgets.QToolButton, "pickFieldClear"))
        self.assertIsNone(self.pattern.Direction2)
        self.assertEqual(self.pattern.Occurrences2, 1)


class TestFeaturesField(PatternPanelCase):
    """What is copied is picked in a field too, and can never become nothing."""

    def _features_field(self):
        return self._find_widget("pickFeatures")

    def _add_cylinder(self):
        cylinder = self.doc.addObject("PartDesign::AdditiveCylinder", "Cylinder")
        self.body.addObject(cylinder)
        cylinder.Radius = 2.0
        cylinder.Height = 4.0
        cylinder.Placement.Base = FreeCAD.Vector(30.0, 3.0, 0.0)
        self.doc.recompute()
        return cylinder

    def test_the_field_names_the_features_being_copied(self):
        self._run("PartDesign_LinearPattern")
        self.assertEqual(self._features_field().property("summary"), self.pad.Label)

    def test_the_old_feature_list_is_gone(self):
        self._run("PartDesign_LinearPattern")
        self.assertFalse(self._find_widget("listWidgetFeatures").isVisible())

    def test_clicks_add_and_remove_features(self):
        cylinder = self._add_cylinder()
        self._run("PartDesign_LinearPattern")
        field = self._features_field()
        self._click(field)
        self.assertTrue(field.property("active"))
        self._pick("Face1", cylinder)
        self.assertEqual(self.pattern.Originals, [self.pad, cylinder])
        self._pick("Face1", self.pad)
        self.assertEqual(self.pattern.Originals, [cylinder])
        self.assertTrue(field.property("active"), "the Features field stays on for more clicks")

    def test_the_last_feature_stays(self):
        self._run("PartDesign_LinearPattern")
        self._click(self._features_field())
        self._pick("Face1")
        self.assertEqual(self.pattern.Originals, [self.pad])

    def test_the_whole_body_option_copies_the_body(self):
        self._run("PartDesign_LinearPattern")
        self._find_widget("optionWholeBody").setChecked(True)
        self._process_events(300)
        self.assertEqual(self.pattern.TransformMode, "Whole shape")
        self.assertFalse(self._features_field().isEnabled())

    def test_only_one_field_is_active_at_a_time(self):
        self._run("PartDesign_LinearPattern")
        self._click(self._features_field())
        self._click(self._direction_field(1))
        self.assertFalse(self._features_field().property("active"))
        self.assertTrue(self._direction_field(1).property("active"))

    def test_escape_turns_a_field_off_and_keeps_the_tool_open(self):
        self._run("PartDesign_LinearPattern")
        field = self._direction_field(1)
        self._click(field)
        self._escape()
        self.assertFalse(field.property("active"))
        # Control.activeDialog() reports whether a dialog is active, as a bool.
        self.assertTrue(FreeCADGui.Control.activeDialog())


class TestNothingSelected(PatternPanelCase):
    """With nothing selected the tool asks for the feature to copy before it makes anything."""

    PICK_PANEL = "PartDesignGui__TaskPatternFeaturePick"

    def test_the_tool_asks_for_a_feature_first(self):
        self._run("PartDesign_LinearPattern", select_pad=False)
        self.assertIs(self.body.Tip, self.pad, "a pattern was made before anything was picked")
        self.assertIsNotNone(self._find_widget(self.PICK_PANEL))

    def test_clicking_a_feature_starts_the_pattern_with_it(self):
        self._run("PartDesign_LinearPattern", select_pad=False)
        self._pick("Face1")
        self.assertTrue(self._wait(lambda: self.body.Tip is not self.pad), "no pattern was made")
        pattern = self.body.Tip
        self.assertEqual(pattern.TypeId, "PartDesign::LinearPattern")
        self.assertEqual(pattern.Originals, [self.pad])
        self.assertAlmostEqual(self._value(pattern.Offset), 15.0)
        self.assertTrue(self._wait(lambda: self._find_widget("pickFeatures") is not None))
        self.assertTrue(self._find_widget("pickFeatures").property("active"))

    def test_escape_before_picking_makes_nothing(self):
        self._run("PartDesign_PolarPattern", select_pad=False)
        self._escape()
        # Control.activeDialog() reports whether a dialog is active, as a bool,
        # not the dialog itself (that's activeTaskDialog()).
        self.assertTrue(self._wait(lambda: not FreeCADGui.Control.activeDialog()))
        self.assertIs(self.body.Tip, self.pad)
        self.assertEqual(
            [obj for obj in self.doc.Objects if obj.TypeId == "PartDesign::PolarPattern"], []
        )
