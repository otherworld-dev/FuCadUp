# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors
# SPDX-FileNotice: Part of the FreeCAD project.

"""GUI tests for the Linear and Polar Pattern tools.

The tools start sized to what they copy, pick features and directions by clicking
in the view, and drive distance, angle and count from handles and boxes in the view.

To run tests:
    FreeCAD -t TestPatternPanel
"""

import os
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
    SO_SWITCH_NONE = extrude.TestExtrudeDrag.SO_SWITCH_NONE
    _switches_above_arrow = extrude.TestExtrudeDrag._switches_above_arrow
    _arrow_hidden = extrude.TestExtrudeDrag._arrow_hidden
    _boxes = gizmo_labels.GizmoLabelCase._boxes
    _path_is_on = staticmethod(gizmo_labels.GizmoLabelCase._path_is_on)

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
        """Press and release Escape in the 3D view, with a real gap between them
        (a physical key stays down for roughly 100 ms), not back-to-back."""

        QtWidgets.QApplication.sendEvent(
            self.viewport,
            QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier),
        )
        self._process_events(150)
        QtWidgets.QApplication.sendEvent(
            self.viewport,
            QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier),
        )
        self._process_events(300)

    @staticmethod
    def _tr(context, text):
        return QtCore.QCoreApplication.translate(context, text)

    # -- the task panel's width ----------------------------------------------

    def _tasks_viewport(self, widget):
        """The part of the task panel in sight: the viewport of the scroll area the
        widget sits in, which never scrolls sideways (TaskPanel).

        Taken from the widget's own parents rather than from
        QAbstractScrollArea.viewport(): PySide ties the wrapper that hands out to the
        scroll area's own wrapper, so it reads as deleted once that one is let go,
        though the viewport itself lives on."""

        child, parent = widget, widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QtWidgets.QAbstractScrollArea):
                return child
            child, parent = parent, parent.parentWidget()
        self.fail("the widget is not in a scroll area")

    def _task_view(self, widget):
        """The Tasks panel (Gui::TaskView::TaskView) the widget sits in."""

        parent = widget.parentWidget()
        while parent is not None:
            if parent.metaObject().className() == "Gui::TaskView::TaskView":
                return parent
            parent = parent.parentWidget()
        self.fail("the widget is not in the Tasks panel")

    def _narrow_the_tasks_panel(self, widget):
        """Makes the Tasks panel the widget sits in as narrow as it goes, and lets it
        widen again after the test. The cap is put on the panel itself, so it holds
        whether its dock is in the main window or in an overlay (where the main window's
        resizeDocks() has no say)."""

        tasks = self._task_view(widget)
        narrowest = tasks.minimumWidth() or tasks.minimumSizeHint().width()
        self.addCleanup(self._cap_width, tasks, tasks.maximumWidth())
        self._cap_width(tasks, narrowest)

    def _cap_width(self, widget, width):
        widget.setMaximumWidth(width)
        self._process_events(300)

    @staticmethod
    def _save_grab(widget, name):
        """Keeps a picture of widget for a person to look at, when FUCAD_TEST_GRAB_DIR
        names a folder for it."""

        folder = os.environ.get("FUCAD_TEST_GRAB_DIR")
        if folder:
            widget.grab().save(os.path.join(folder, name))

    def _assert_inside_the_panel(self, widgets):
        """Each (name, widget) is shown and ends inside the part of the task panel in
        sight; anything past its right edge is cut off, as the panel never scrolls
        sideways."""

        for name, widget in widgets:
            self.assertIsNotNone(widget, f"there is no {name}")
            self.assertTrue(widget.isVisible(), f"{name} is hidden")
            viewport = self._tasks_viewport(widget)
            right = widget.mapTo(viewport, QtCore.QPoint(widget.width(), 0)).x()
            self.assertLessEqual(
                right,
                viewport.width(),
                f"{name} ends at {right} px, past the panel's edge at {viewport.width()} px",
            )


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

    def test_a_quick_pick_turns_direction_2_on_sized_to_the_feature(self):
        """Direction 2 starts the same whichever way it is first filled."""

        menu = self._direction_field(2).findChild(QtWidgets.QToolButton, "pickFieldMenu").menu()
        wanted = self._tr("PartDesignGui::TaskTransformedParameters", "Base Y-axis")
        next(action for action in menu.actions() if action.text() == wanted).trigger()
        self._process_events(300)
        self.assertEqual(getattr(self.pattern.Direction2[0], "Role", ""), "Y_Axis")
        self.assertEqual(self.pattern.Occurrences2, 2)
        self.assertEqual(self.pattern.Mode2, "Spacing")
        # The Pad is 6 mm along Y: 1.5 x 6.
        self.assertAlmostEqual(self._value(self.pattern.Offset2), 9.0)
        values = self._direction_widget(2).findChild(QtWidgets.QWidget, "valuesRow")
        self.assertTrue(values.isVisible())

    def test_a_whole_body_pattern_sizes_direction_2_from_the_body(self):
        """Whole-body mode has nothing in Originals to size Direction 2 from
        (getOriginals() is empty once TransformMode is Whole shape), so starting
        Direction 2 must fall back to the base shape instead - the same fallback
        getStartPoint() already uses - rather than the 10 mm default for an
        empty list."""

        self._find_widget("optionWholeBody").setChecked(True)
        self._process_events(300)
        self.assertEqual(self.pattern.TransformMode, "Whole shape")

        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        self.assertEqual(self.pattern.Mode2, "Spacing")
        # The Pad is 6 mm along Y: 1.5 x 6.
        self.assertAlmostEqual(self._value(self.pattern.Offset2), 9.0)

    def test_a_pick_leaves_the_preview_showing_what_it_showed(self):
        """The Preview panel's "Show final result" decides whether the pattern or the
        feature before it is shown; a pick shows the originals only while it lasts."""

        before = (self.pattern.Visibility, self.pad.Visibility)
        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        self.assertFalse(self._direction_field(2).property("active"))
        self.assertEqual((self.pattern.Visibility, self.pad.Visibility), before)

    def test_nothing_runs_off_the_narrowest_tasks_panel(self):
        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        first, second = self._direction_widget(1), self._direction_widget(2)
        self._narrow_the_tasks_panel(first)
        self._save_grab(self._task_view(first), "pattern-panel-narrow-linear.png")
        field = self._direction_field(2)
        self._assert_inside_the_panel(
            [
                ("Direction 2's quick picks", field.findChild(QtWidgets.QToolButton, "pickFieldMenu")),
                ("Direction 2's reverse button", field.findChild(QtWidgets.QToolButton, "pickFieldReverse")),
                ("Direction 2's clear button", field.findChild(QtWidgets.QToolButton, "pickFieldClear")),
                ("Direction 1's count", first.findChild(QtWidgets.QSpinBox, "spinOccurrences")),
                ("Direction 2's count", second.findChild(QtWidgets.QSpinBox, "spinOccurrences")),
            ]
        )


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

    def test_the_summary_follows_an_external_change_to_originals(self):
        """updateFeaturesField() used to run only from the panel's own paths, so an
        undo, a Python edit or a deleted feature left the summary showing stale
        labels. A Python edit to Originals is the cheapest of those three to drive
        here; all three go through the same property change, observed the same way."""

        cylinder = self._add_cylinder()
        self._run("PartDesign_LinearPattern")
        self.pattern.Originals = [self.pad, cylinder]
        self._process_events(300)
        self.assertEqual(
            self._features_field().property("summary"),
            f"{self.pad.Label}, {cylinder.Label}",
        )

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

    def test_a_feature_of_another_body_is_not_taken(self):
        other_body = self.doc.addObject("PartDesign::Body", "OtherBody")
        box = self.doc.addObject("PartDesign::AdditiveBox", "Box")
        other_body.addObject(box)
        self.doc.recompute()
        self._run("PartDesign_LinearPattern")
        self._click(self._features_field())
        FreeCADGui.Selection.addSelection(self.doc.Name, box.Name, "Face1")
        self._process_events(300)
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

    def test_escape_on_the_features_field_keeps_the_tool_open(self):
        self._run("PartDesign_LinearPattern")
        field = self._features_field()
        self._click(field)
        self._escape()
        self.assertFalse(field.property("active"))
        self.assertIsNotNone(FreeCADGui.Control.activeTaskDialog())


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


class TestLinearArrows(PatternPanelCase):
    """Each direction of a linear pattern has an arrow to drag, with its value on it."""

    # The Pad's bounding box centre, where the arrows start; the first copy is 15 mm along X.
    BASE = FreeCAD.Vector(5.0, 3.0, 5.0)

    def setUp(self):
        super().setUp()
        self._run("PartDesign_LinearPattern")
        self._refresh_view_widgets()
        self.view.viewIsometric()
        self.view.fitAll()
        self._process_events(300)

    def _tip(self):
        return self.BASE + FreeCAD.Vector(self._value(self.pattern.Offset), 0.0, 0.0)

    def _distance_boxes(self):
        return [box for box in self._boxes() if "°" not in box.text()]

    def _arrow_grip(self):
        """A point on the arrow near its tip, found by asking the scene what is under it."""

        from pivy import coin

        manager = self.viewer.getSoRenderManager()
        tip, base = self._pixels(self._tip()), self._pixels(self.BASE)
        for along in (0.0, 0.03, 0.06, 0.1, 0.15, 0.2):
            pixels = (tip[0] + (base[0] - tip[0]) * along, tip[1] + (base[1] - tip[1]) * along)
            pick = coin.SoRayPickAction(manager.getViewportRegion())
            pick.setPoint(coin.SbVec2s(int(pixels[0]), int(pixels[1])))
            pick.setRadius(6)
            pick.setPickAll(True)
            pick.apply(manager.getSceneGraph())
            picked = pick.getPickedPointList()
            for index in range(picked.getLength()):
                path = picked[index].getPath()
                for depth in range(path.getLength()):
                    if path.getNode(depth).getTypeId().getName().getString() == "SoLinearDraggerContainer":
                        return self._qt_pos(pixels)
        self.fail("the arrow is not under any of the points tried")

    def _drag_arrow_by(self, millimetres, hold_ms=0):
        """Press on the arrow and pull it along X by millimetres, keep the button down
        for hold_ms, then let go. Returns whether the arrow was hidden after each move
        (and after the hold), while the button was still down."""

        switches = self._switches_above_arrow()
        grip = self._arrow_grip()
        start = self._qt_pos(self._pixels(self.BASE))
        end = self._qt_pos(self._pixels(self.BASE + FreeCAD.Vector(10.0, 0.0, 0.0)))
        per_mm = (end - start) / 10.0
        self._mouse(QtCore.QEvent.MouseMove, grip, QtCore.Qt.NoButton, QtCore.Qt.NoButton)
        self._process_events()
        self._mouse(QtCore.QEvent.MouseButtonPress, grip, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        self._process_events(100)
        pos = grip
        hidden = []
        try:
            for step in range(1, 6):
                pos = grip + per_mm * (millimetres * step / 5.0)
                self._mouse(QtCore.QEvent.MouseMove, pos, QtCore.Qt.NoButton, QtCore.Qt.LeftButton)
                self._process_events(60)
                hidden.append(self._arrow_hidden(switches))
            if hold_ms:
                self._process_events(hold_ms)
                hidden.append(self._arrow_hidden(switches))
        finally:
            self._mouse(QtCore.QEvent.MouseButtonRelease, pos, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)
            self._process_events(300)
        return hidden

    def test_the_arrow_carries_the_spacing_in_a_box(self):
        self.assertTrue(self._wait(lambda: len(self._distance_boxes()) == 1))
        self.assertAlmostEqual(self._distance_boxes()[0].property("rawValue"), 15.0)

    def test_dragging_the_arrow_changes_the_spacing(self):
        self._drag_arrow_by(-5.0)
        self.assertLess(abs(self._value(self.pattern.Offset) - 10.0), 1.0)

    def test_dragging_the_arrow_to_its_base_keeps_it_under_the_pointer(self):
        """Pulled back past its base, the spacing reaches zero and the pattern breaks;
        the arrow stays under the pointer until it is let go, as on Extrude."""

        # Held long enough at the end for the preview to recompute under the drag
        hidden = self._drag_arrow_by(-16.0, hold_ms=400)
        self.assertFalse(any(hidden), f"the arrow was hidden while dragged: {hidden}")
        offset = self._value(self.pattern.Offset)
        self.assertTrue(0.0 <= offset <= 15.0, f"the spacing ended at {offset}")
        if not self.pattern.isValid():
            self.assertTrue(self._arrow_hidden(self._switches_above_arrow()))

    def test_clicking_the_arrow_turns_the_pattern_round(self):
        grip = self._arrow_grip()
        self._mouse(QtCore.QEvent.MouseButtonPress, grip, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        self._process_events(100)
        self._mouse(QtCore.QEvent.MouseButtonRelease, grip, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)
        self._process_events(300)
        self.assertTrue(self.pattern.Reversed)

    def test_in_total_length_mode_the_box_holds_the_total_length(self):
        combo = self._direction_widget(1).findChild(QtWidgets.QComboBox, "comboMode")
        combo.setCurrentIndex(0)
        combo.activated.emit(0)
        self._process_events(300)
        self.assertTrue(self._wait(lambda: len(self._distance_boxes()) == 1))
        self.assertAlmostEqual(self._distance_boxes()[0].property("rawValue"), 30.0)

    def test_the_arrows_hide_while_a_field_is_being_picked_in(self):
        switches = self._switches_above_arrow()
        self._click(self._direction_field(1))
        self.assertTrue(self._arrow_hidden(switches))
        self.assertEqual(self._distance_boxes(), [])

    def test_direction_2_has_no_arrow_until_it_is_picked(self):
        self.assertEqual(len(self._distance_boxes()), 1)
        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        self.assertTrue(self._wait(lambda: len(self._distance_boxes()) == 2))

    def test_the_gaps_after_the_first_keep_their_own_labels(self):
        """Only the first gap's label is replaced by the arrow's box."""

        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoDatumLabel"))
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        paths = search.getPaths()
        gap_labels = [
            paths[index]
            for index in range(paths.getLength())
            if paths[index].getTail().getName() != "GizmoValueLabel" and self._path_is_on(paths[index])
        ]
        # Three copies make two gaps; the first is the arrow's.
        self.assertEqual(len(gap_labels), 1)

    def test_the_preview_follows_a_change_within_a_quarter_second(self):
        count = self._direction_widget(1).findChild(QtWidgets.QSpinBox, "spinOccurrences")
        # One click on the up arrow. The box is a Gui::UIntSpinBox, which keeps its count
        # shifted by INT_MIN inside QSpinBox; Python only reaches QSpinBox::setValue(int),
        # so setValue(4) would clamp to the top and ask for 2147483647 copies.
        count.stepUp()
        self.assertEqual(self.pattern.Occurrences, 4)
        self._process_events(250)
        self.assertAlmostEqual(self.pattern.Shape.Volume, 4 * PAD_VOLUME, places=3)


class TestCountBoxes(PatternPanelCase):
    """The number of copies sits in a box just past each arrow."""

    BASE = TestLinearArrows.BASE
    _tip = TestLinearArrows._tip
    _distance_boxes = TestLinearArrows._distance_boxes
    _wait_for_focus = gizmo_labels.GizmoLabelCase._wait_for_focus
    _value_labels_off = gizmo_labels.GizmoLabelCase._value_labels_off
    _labels = gizmo_labels.GizmoLabelCase._labels

    def setUp(self):
        super().setUp()
        self._run("PartDesign_LinearPattern")
        self._refresh_view_widgets()
        self.view.viewIsometric()
        self.view.fitAll()
        self._process_events(300)

    def _count_boxes(self):
        main = FreeCADGui.getMainWindow()
        return [
            box
            for box in main.findChildren(QtWidgets.QAbstractSpinBox, COUNT_BOX_NAME)
            if box.isVisible()
        ]

    def _first_count_box(self):
        self.assertTrue(self._wait(lambda: len(self._count_boxes()) == 1), "no count box")
        return self._count_boxes()[0]

    def test_the_arrow_has_a_box_with_the_number_of_copies(self):
        self.assertAlmostEqual(self._first_count_box().property("rawValue"), 3.0)

    def test_the_count_reads_as_a_whole_number(self):
        self.assertEqual(self._first_count_box().text().strip(), "3")

    def test_typing_in_the_count_box_sets_the_number_of_copies(self):
        box = self._first_count_box()
        box.setFocus(QtCore.Qt.OtherFocusReason)
        self._wait_for_focus(box)
        self._select_all(box)
        self._type(box, "5")
        self._process_events(300)
        self.assertEqual(self.pattern.Occurrences, 5)

    def test_enter_in_the_count_box_finishes_the_pattern(self):
        box = self._first_count_box()
        box.setFocus(QtCore.Qt.OtherFocusReason)
        self._wait_for_focus(box)
        self._select_all(box)
        self._type(box, "4")
        self._press(box, QtCore.Qt.Key_Return)
        self.assertTrue(self._wait(lambda: FreeCADGui.Control.activeTaskDialog() is None))
        self.assertEqual(self.pattern.Occurrences, 4)

    def test_the_count_box_leaves_the_arrow_free(self):
        self.assertFalse(self._dragger_under(self._first_count_box(), "SoLinearDraggerContainer"))

    def test_tab_runs_distance_then_count_for_each_direction(self):
        self._click(self._direction_field(2))
        self._pick(self._edge_along(FreeCAD.Vector(0, 1, 0)))
        self.assertTrue(self._wait(lambda: len(self._count_boxes()) == 2))
        distances = self._distance_boxes()
        counts = self._count_boxes()
        by_value = lambda boxes, value: next(
            box for box in boxes if abs(box.property("rawValue") - value) < 1e-6
        )
        order = [
            by_value(distances, 15.0),  # Direction 1's spacing
            by_value(counts, 3.0),      # Direction 1's copies
            by_value(distances, 9.0),   # Direction 2's spacing
            by_value(counts, 2.0),      # Direction 2's copies
        ]
        order[0].setFocus(QtCore.Qt.OtherFocusReason)
        self._wait_for_focus(order[0])
        for current, following in zip(order, order[1:] + order[:1]):
            self._press(current, QtCore.Qt.Key_Tab)
            self._wait_for_focus(following)

    def test_no_count_boxes_when_values_in_the_view_are_off(self):
        self._value_labels_off()
        self._close_editing()
        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pattern.Name)
        self._process_events(300)
        self.assertEqual(self._count_boxes(), [])

    def test_a_shown_labels_points_never_fall_short_for_its_type(self):
        """SoDatumLabel::GLRender warns "Too few points to render distance label" once
        a shown DISTANCE-type label has fewer than 2 points (SoDatumLabel.cpp). Coin's
        own default handler prints that straight past FreeCAD's Console (the bridge in
        Gui::Application.cpp's messageHandlerCoin is only installed when FC_DEBUG is
        set, i.e. never in a release build), so this checks the state that would cause
        it rather than the printed text. A count box sits at 0 mm of travel for as
        long as it is shown, so this state is permanent for it, not transient."""

        for label in self._labels():
            if label.datumtype.getValue() == gizmo_labels.DISTANCE:
                self.assertGreaterEqual(
                    label.pnts.getNum(),
                    2,
                    "a shown distance label with fewer than 2 points warns on every redraw",
                )

    def test_a_three_digit_count_fits_beside_the_times_mark(self):
        """QuantitySpinBox only widens for a leading action's icon when told to (see
        QuantitySpinBox::sizeHintForDigits's addIconSpace guard: it adds iconHeight,
        fontMetrics().height(), to the box only if addIconSpace was set) so a count
        box that skips that opt-in is sized for its digits alone, and the "x" mark
        (drawn in that same iconHeight square) crops them instead of sitting beside
        them. QLineEdit::textMargins() does not reflect the space Qt reserves for a
        leading action internally, so the box's own width is compared against the
        digits plus that reservation directly, the same way the C++ side does."""

        self.pattern.Occurrences = 100
        self.doc.recompute()
        self._close_editing()
        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pattern.Name)
        self._process_events(300)
        box = self._first_count_box()
        self.assertEqual(box.text().strip(), "100")
        edit = box.findChild(QtWidgets.QLineEdit)
        fm = QtGui.QFontMetrics(edit.font())
        icon_reserved = fm.height()  # Gui::QuantitySpinBox's iconHeight
        needed = fm.horizontalAdvance(edit.text()) + icon_reserved
        self.assertGreaterEqual(box.width(), needed, "the x mark crops a 3-digit count")

    def test_the_count_boxes_stop_at_a_thousand_copies(self):
        """The panel caps each direction's copies, and the box in the view takes the same
        range; the property itself is left uncapped for old documents and scripts.
        Only the ranges are read here: a large count is never typed or set."""

        for number in (1, 2):
            count = self._direction_widget(number).findChild(QtWidgets.QSpinBox, "spinOccurrences")
            # A Gui::UIntSpinBox keeps its range shifted by INT_MIN inside QSpinBox (see
            # TestLinearArrows.test_the_preview_follows_a_change_within_a_quarter_second),
            # and has no unsigned "maximum" property of its own for Python to read
            self.assertEqual(count.maximum() + 2**31, 1000, f"Direction {number}'s count")
        self.assertAlmostEqual(self._first_count_box().property("maximum"), 1000.0)

    def test_an_old_documents_count_above_the_cap_still_shows(self):
        """A document saved before the panel capped copies at 1000 can carry a
        higher count. Set here the way a load from disk would leave it - the
        property holds 1200 but nothing is touched - rather than by simply
        assigning Occurrences and opening the panel: ViewProviderTransformed::
        setEdit calls recomputeFeature(false), which forces a real recompute
        whenever mustExecute() is true, no matter that RecomputesFrozen is set
        (Document::recomputeFeature's recursive path always passes force=true).
        A freshly touched Occurrences would make mustExecute() true and so
        recompute all 1200 copies; purgeTouched() after setting it keeps this
        test from ever doing that, matching a document that was already this
        way when it was last saved. RecomputesFrozen is set too, belt and
        braces, and restored after."""

        def unfreeze():
            # tearDown() (closeDocument) runs before an addCleanup callback, so by here
            # self.doc's wrapper may already be a dead reference - even reading .Name
            # off it raises, so the only safe check is to try the write and let a dead
            # document's ReferenceError pass.
            try:
                self.doc.RecomputesFrozen = False
            except ReferenceError:
                pass

        self.doc.RecomputesFrozen = True
        self.addCleanup(unfreeze)

        self._close_editing()
        self.pattern.Occurrences = 1200
        self.pattern.purgeTouched()
        self.assertEqual(
            self.pattern.getStatusString(),
            "Valid",
            "the pattern is touched: opening the panel would recompute 1200 copies",
        )

        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pattern.Name)
        self._process_events(300)

        box = self._direction_widget(1).findChild(QtWidgets.QSpinBox, "spinOccurrences")
        # Same INT_MIN shift as test_the_count_boxes_stop_at_a_thousand_copies above
        self.assertEqual(box.value() + 2**31, 1200, "the panel clamped an old document's count")
        self.assertGreaterEqual(box.maximum() + 2**31, 1200, "the panel's maximum did not widen")

        # Close with Cancel: resetEdit()/closeDialog() never call accept(), so
        # apply() never runs and nothing is written back or recomputed.
        self._close_editing()


class TestPolarHandle(PatternPanelCase):
    """A polar pattern's angle is turned with a handle, and its copies counted beside it."""

    _count_boxes = TestCountBoxes._count_boxes
    _wait_for_focus = gizmo_labels.GizmoLabelCase._wait_for_focus

    # The handle turns about the point level with the Pad's bounding box centre
    # (TestLinearArrows.BASE) on the sketch's N_Axis (straight up through the origin);
    # RADIAL is the vector from there out to the start point, where the handle's arm
    # sits at 0 (and 360) degrees.
    PIVOT = FreeCAD.Vector(0.0, 0.0, 5.0)
    RADIAL = TestLinearArrows.BASE - PIVOT

    def setUp(self):
        super().setUp()
        self._run("PartDesign_PolarPattern")
        self._refresh_view_widgets()
        self.view.viewIsometric()
        self.view.fitAll()
        self._process_events(300)

    def _angle_boxes(self):
        return [box for box in self._boxes() if "°" in box.text()]

    def _handle_shown(self):
        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoRotationDraggerContainer"))
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        paths = search.getPaths()
        return any(self._path_is_on(paths[index]) for index in range(paths.getLength()))

    def test_a_polar_pattern_has_a_rotation_handle(self):
        self.assertTrue(self._wait(self._handle_shown), "no rotation handle in the view")

    def test_the_handle_carries_the_total_angle_in_a_box(self):
        self.assertTrue(self._wait(lambda: len(self._angle_boxes()) == 1))
        self.assertAlmostEqual(self._angle_boxes()[0].property("rawValue"), 360.0)

    def test_the_handle_has_a_count_box(self):
        self.assertTrue(self._wait(lambda: len(self._count_boxes()) == 1))
        self.assertAlmostEqual(self._count_boxes()[0].property("rawValue"), 4.0)

    def test_typing_an_angle_turns_the_pattern(self):
        self.assertTrue(self._wait(lambda: len(self._angle_boxes()) == 1))
        box = self._angle_boxes()[0]
        box.setFocus(QtCore.Qt.OtherFocusReason)
        self._wait_for_focus(box)
        self._select_all(box)
        self._type(box, "90")
        self._process_events(300)
        self.assertAlmostEqual(self._value(self.pattern.Angle), 90.0)

    def test_tab_goes_from_the_angle_to_the_count(self):
        self.assertTrue(self._wait(lambda: len(self._count_boxes()) == 1))
        angle, count = self._angle_boxes()[0], self._count_boxes()[0]
        angle.setFocus(QtCore.Qt.OtherFocusReason)
        self._wait_for_focus(angle)
        self._press(angle, QtCore.Qt.Key_Tab)
        self._wait_for_focus(count)

    def test_the_handle_hides_while_the_axis_is_being_picked(self):
        self.assertTrue(self._wait(self._handle_shown))
        self._click(self._direction_field(1))
        self.assertFalse(self._handle_shown())

    def test_nothing_runs_off_the_narrowest_tasks_panel(self):
        axis = self._direction_widget(1)
        self._narrow_the_tasks_panel(axis)
        self._save_grab(self._task_view(axis), "pattern-panel-narrow-polar.png")
        field = self._direction_field(1)
        self._assert_inside_the_panel(
            [
                ("the axis's quick picks", field.findChild(QtWidgets.QToolButton, "pickFieldMenu")),
                ("the axis's reverse button", field.findChild(QtWidgets.QToolButton, "pickFieldReverse")),
                ("the times mark", axis.findChild(QtWidgets.QLabel, "labelTimes")),
                ("the count", axis.findChild(QtWidgets.QSpinBox, "spinOccurrences")),
            ]
        )

    # -- dragging ----------------------------------------------------------

    def _rendered_arm_length(self):
        """The handle arm's actual on-screen length, in document units.

        The rotator arm sits at ``max(minRadius, radius / geometryScale)`` in its own
        pre-scale local frame (SoRotatorArrow::notify, Gizmo.cpp), so at typical view
        distances the ``minRadius`` floor (8 local units, RadialGizmo's default) wins
        over the pattern's own geometric radius (here, RADIAL's length, under 6 mm) -
        the rendered arm is longer than RADIAL, by the view's own auto-scale. Reading
        pivotPosition and geometryScale back from the scene, rather than assuming
        RADIAL's own length, keeps this independent of that (view-dependent) scale.
        """

        container = self._handle_container()
        dragger = container.getPart("dragger", False)
        rotator = dragger.getPart("rotator", False)
        pivot_y = rotator.getField("pivotPosition").getValue().getValue()[1]
        scale_y = rotator.getField("geometryScale").getValue().getValue()[1]
        return pivot_y * scale_y

    def _handle_container(self):
        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoRotationDraggerContainer"))
        search.setInterest(coin.SoSearchAction.FIRST)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        path = search.getPath()
        self.assertIsNotNone(path, "the handle is not in the scene")
        return path.getTail()

    def _handle_grip(self, value, arm_length):
        """A point on the handle's arm at the given angle, found by asking the scene
        what is under it, the way _arrow_grip does for the linear arrows."""

        from pivy import coin

        manager = self.viewer.getSoRenderManager()
        direction = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), value).multVec(self.RADIAL)
        direction.normalize()
        tip, base = self._pixels(self.PIVOT + direction * arm_length), self._pixels(self.PIVOT)
        for along in (0.0, 0.03, 0.06, 0.1, 0.15, 0.2):
            pixels = (tip[0] + (base[0] - tip[0]) * along, tip[1] + (base[1] - tip[1]) * along)
            pick = coin.SoRayPickAction(manager.getViewportRegion())
            pick.setPoint(coin.SbVec2s(int(pixels[0]), int(pixels[1])))
            pick.setRadius(6)
            pick.setPickAll(True)
            pick.apply(manager.getSceneGraph())
            picked = pick.getPickedPointList()
            for index in range(picked.getLength()):
                path = picked[index].getPath()
                for depth in range(path.getLength()):
                    name = path.getNode(depth).getTypeId().getName().getString()
                    if name == "SoRotationDraggerContainer":
                        return self._qt_pos(pixels)
        self.fail("the handle is not under any of the points tried")

    def _drag_handle_towards(self, start_value, target_value, steps=6, hold_ms=0):
        """Press on the handle at start_value and pull it, in small steps, to
        target_value. Returns whether the handle was hidden after each step (and
        after the hold), while the button was still down."""

        axis = FreeCAD.Vector(0, 0, 1)
        arm_length = self._rendered_arm_length()

        def screen_for(value):
            direction = FreeCAD.Rotation(axis, value).multVec(self.RADIAL)
            direction.normalize()
            return self._qt_pos(self._pixels(self.PIVOT + direction * arm_length))

        grip = self._handle_grip(start_value, arm_length)
        self._mouse(QtCore.QEvent.MouseMove, grip, QtCore.Qt.NoButton, QtCore.Qt.NoButton)
        self._process_events()
        self._mouse(QtCore.QEvent.MouseButtonPress, grip, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        self._process_events(100)
        pos = grip
        hidden = []
        try:
            for step in range(1, steps + 1):
                value = start_value + (target_value - start_value) * step / steps
                pos = screen_for(value)
                self._mouse(QtCore.QEvent.MouseMove, pos, QtCore.Qt.NoButton, QtCore.Qt.LeftButton)
                self._process_events(60)
                hidden.append(not self._handle_shown())
            if hold_ms:
                self._process_events(hold_ms)
                hidden.append(not self._handle_shown())
        finally:
            self._mouse(QtCore.QEvent.MouseButtonRelease, pos, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)
            self._process_events(300)
        return hidden

    def test_dragging_the_handle_towards_zero_keeps_it_under_the_pointer(self):
        """Dragging the angle down to 0 makes the pattern throw ("Pattern angle can't
        be null"); the 100 ms recompute must not hide the handle out from under a drag
        still holding it, the same guard the linear arrows have (TestLinearArrows).
        Started from a smaller angle than the pattern's default 360 degrees, so the
        drag only has to cover a small, unambiguous arc: SoRotationDragger measures
        each move as the shortest arc from the press point, so a turn approaching a
        full 360 degrees (as dragging down from the default would need) cannot be
        driven reliably this way."""

        self.pattern.Angle = 20.0
        self.doc.recompute()
        self._close_editing()
        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pattern.Name)
        self._process_events(300)
        self.assertTrue(self._wait(self._handle_shown))

        hidden = self._drag_handle_towards(20.0, -10.0, hold_ms=400)
        self.assertFalse(any(hidden), f"the handle was hidden while dragged: {hidden}")

    # -- reversed ------------------------------------------------------------

    def _handle_arc_normal(self):
        """The handle's current arc-normal direction, in world space (the direction
        SoRotationDraggerContainer.rotation carries local Z to)."""

        container = self._handle_container()
        quat = container.getField("rotation").getValue().getValue()
        return FreeCAD.Rotation(*quat).multVec(FreeCAD.Vector(0, 0, 1))

    def test_a_reversed_pattern_turns_its_handle_the_other_way(self):
        """PolarPatternExtension::getRotation() already reverses the axis when
        Reversed is set, the same direction updateSpacingLabels uses - the handle's
        arc normal should follow that, unreversed a second time."""

        self.pattern.Reversed = True
        self.doc.recompute()
        self._close_editing()
        FreeCADGui.getDocument(self.doc.Name).setEdit(self.pattern.Name)
        self._process_events(300)
        self.assertTrue(self._wait(self._handle_shown))

        normal = self._handle_arc_normal()
        self.assertLess((normal - FreeCAD.Vector(0, 0, -1)).Length, 1e-4)

    def test_clicking_the_handle_turns_the_pattern_round(self):
        """As on the linear arrows (TestLinearArrows.
        test_clicking_the_arrow_turns_the_pattern_round), letting go without moving
        toggles Reversed rather than dragging - and the handle's own arc normal must
        follow suit in the same panel, not just after a reopen."""

        self.assertTrue(self._wait(self._handle_shown))
        arm_length = self._rendered_arm_length()
        grip = self._handle_grip(0.0, arm_length)
        self._mouse(QtCore.QEvent.MouseButtonPress, grip, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        self._process_events(100)
        self._mouse(QtCore.QEvent.MouseButtonRelease, grip, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)
        self._process_events(300)
        self.assertTrue(self.pattern.Reversed)

        normal = self._handle_arc_normal()
        self.assertLess((normal - FreeCAD.Vector(0, 0, -1)).Length, 1e-4)


class TestMultiTransformStep(PatternPanelCase):
    """A pattern step inside a MultiTransform gets the new panel, but no handles."""

    def setUp(self):
        super().setUp()
        self.multi = self.doc.addObject("PartDesign::MultiTransform", "MultiTransform")
        self.multi.Originals = [self.pad]
        self.step = self.doc.addObject("PartDesign::LinearPattern", "LinearPattern")
        self.step.Direction = (self.sketch, ["H_Axis"])
        self.step.Length = 30.0
        self.step.Occurrences = 2
        self.multi.Transformations = [self.step]
        self.body.addObject(self.multi)
        self.doc.recompute()
        FreeCADGui.getDocument(self.doc.Name).setEdit(self.multi.Name)
        self._process_events(300)
        steps = self._find_widget("listTransformFeatures")
        self.assertIsNotNone(steps, "the MultiTransform panel did not open")
        steps.setCurrentRow(0)
        steps.activated.emit(steps.model().index(0, 0))
        self._process_events(300)
        self.assertIsNotNone(
            self._direction_widget(1), "the step's own pattern panel did not open"
        )

    def test_the_step_shows_the_direction_field(self):
        field = self._direction_field(1)
        self.assertIsNotNone(field, "the step's own pattern panel did not open")
        self.assertTrue(field.isVisible())

    def test_the_step_has_no_features_field_of_its_own(self):
        field = self._find_widget("pickFeatures")
        self.assertTrue(field is None or not field.isVisible())

    def test_the_step_has_no_handles(self):
        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoLinearDraggerContainer"))
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        self.assertEqual(search.getPaths().getLength(), 0)
