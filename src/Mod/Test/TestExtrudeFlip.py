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

import collections
import math
import time
import unittest

import FreeCAD
import FreeCADGui
import Part
import Sketcher
from PySide import QtCore, QtGui, QtWidgets

# PartDesign::FeatureAddSub::OperationType, see src/Mod/PartDesign/App/FeatureAddSub.h.
JOIN = 0
CUT = 1
INTERSECT = 2
NEW_BODY = 3

# ui->sidesMode, see TaskExtrudeParameters::translateSidesList.
ONE_SIDED = 0
SYMMETRIC = 2

# The two halves of the operation combo's tooltip. They are asked for the way Qt asks
# for them, so the assertions hold whatever language the tests run in.
UI_TOOLTIP = "How the extrusion is combined with the existing solid"
COLOUR_HINT = (
    "The preview is coloured by operation: green adds, red removes, yellow keeps the overlap"
)


class ExtrudePanelCase(unittest.TestCase):
    """A 10 mm Pad of a 10 x 6 rectangle in its task panel, with the widgets the tests drive."""

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

    def _task_panel(self):
        """The TaskExtrudeParameters box the length field lives in.

        PySide has no wrapper for the C++ class, so it comes back as a plain QWidget
        and its methods have to be reached through the meta object.
        """

        widget = self.lengthEdit
        while widget is not None:
            meta = widget.metaObject()
            if meta.indexOfMethod("setLengthDragActive(int,bool)") >= 0:
                return widget
            widget = widget.parent()
        return None

    def _set_drag_active(self, active, side=0):
        """Report a length drag starting or finishing, the way the dragger does."""

        panel = self._task_panel()
        self.assertIsNotNone(panel, "could not reach the extrude task panel")
        try:
            invoked = QtCore.QMetaObject.invokeMethod(
                panel,
                "setLengthDragActive",
                QtCore.Qt.DirectConnection,
                QtCore.Q_ARG(int, int(side)),
                QtCore.Q_ARG(bool, bool(active)),
            )
        except TypeError:
            invoked = QtCore.QMetaObject.invokeMethod(
                panel,
                "setLengthDragActive",
                QtCore.Q_ARG(int, int(side)),
                QtCore.Q_ARG(bool, bool(active)),
            )
        self.assertTrue(invoked, "setLengthDragActive could not be invoked")
        self._process_events()

    def _length(self):
        length = self.pad.Length
        return float(getattr(length, "Value", length))

    def _swatch_colour(self, index):
        icon = self.operationMode.itemIcon(index)
        self.assertFalse(icon.isNull(), f"operation {index} has no colour swatch")
        image = icon.pixmap(12, 12).toImage()
        return image.pixelColor(image.width() // 2, image.height() // 2)


class TestExtrudeFlip(ExtrudePanelCase):
    """A length dragged or typed past the profile turns the extrude around exactly once."""

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
        """The hint goes below what the .ui file already said, not instead of it."""

        lines = self.operationMode.toolTip().split("\n")
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            lines[0],
            QtCore.QCoreApplication.translate(
                "PartDesignGui::TaskPadPocketParameters", UI_TOOLTIP
            ),
        )
        self.assertEqual(
            lines[1],
            QtCore.QCoreApplication.translate(
                "PartDesignGui::TaskExtrudeParameters", COLOUR_HINT
            ),
        )

    # -- the drag path ---------------------------------------------------

    def test_a_drag_flips_once_per_crossing_and_is_forgotten_when_it_ends(self):
        """The gizmo's own path: a start, a run of raw values, then a finish.

        This is where the bug lived. The arrow keeps reporting the same negative
        distance while the pointer stays past the profile, and the crossing it made is
        that drag's own business: a value arriving afterwards must not undo it.
        """

        self._set_drag_active(True)

        self._set_raw_length(-3.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)

        for raw in (-5.0, -7.0):
            self._set_raw_length(raw)
            self.assertEqual(self.operationMode.currentIndex(), CUT)
            self.assertTrue(self.pad.Reversed)
            self.assertAlmostEqual(self._length(), abs(raw))

        # Dragged back over the profile within the same drag: it turns around again.
        self._set_raw_length(2.0)
        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertFalse(self.pad.Reversed)

        # And out the far side once more, where the drag is released.
        self._set_raw_length(-4.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)
        self._set_drag_active(False)

        # A distance typed after the drag is a fresh start, not a crossing.
        self._set_raw_length(9.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 9.0)

    def test_a_new_drag_does_not_inherit_the_last_one_s_crossing(self):
        self._set_drag_active(True)
        self._set_raw_length(-5.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self._set_drag_active(False)

        # The arrow now points the other way, so the next drag pulls positive first.
        self._set_drag_active(True)
        self._set_raw_length(8.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)
        self.assertTrue(self.pad.Reversed)
        self.assertAlmostEqual(self._length(), 8.0)

        # Only crossing zero within this drag turns it around.
        self._set_raw_length(-2.0)
        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertFalse(self.pad.Reversed)
        self._set_drag_active(False)

    def test_a_symmetric_extrude_has_nothing_to_turn_around(self):
        """It grows both ways at once, so a crossing is a no-op there."""

        sidesMode = self._find_widget("sidesMode")
        self.assertIsNotNone(sidesMode)
        sidesMode.setCurrentIndex(SYMMETRIC)
        self._process_events()
        self.assertFalse(self.checkBoxReversed.isEnabled())

        self._set_raw_length(-5.0)

        self.assertEqual(self.operationMode.currentIndex(), JOIN)
        self.assertFalse(self.pad.Reversed)
        self.assertFalse(self.checkBoxReversed.isChecked())
        self.assertAlmostEqual(self._length(), 5.0)


class TestExtrudeDrag(ExtrudePanelCase):
    """The length arrow dragged through the profile in the 3D view.

    The tests above feed the panel the values a drag would send. These press on the
    arrow itself and move the pointer, because the arrow lives in the scene graph and
    what happens to it during a crossing only shows up there: a recompute that failed
    on the way past zero used to hide the gizmos under a dragger that still held the
    mouse, and Coin then measured the next motion in a frame collapsed to the world
    origin.
    """

    # The Pad starts 10 mm long, so the arrow stands on the profile's centre with its
    # tip 10 mm up.
    ARROW_BASE = FreeCAD.Vector(5.0, 3.0, 0.0)
    ARROW_TIP = FreeCAD.Vector(5.0, 3.0, 10.0)
    # Pointer heights above the profile, in mm, walked through zero. The snap step is
    # 0.5 mm, so the pointer lands on exactly zero on its way past.
    THROUGH_THE_PROFILE = [
        8.0, 6.0, 4.0, 2.0, 1.0, 0.6, 0.2, -0.2, -0.6, -1.0, -1.4, -1.8, -2.2, -2.6, -3.0
    ]
    SNAP_TOLERANCE = 0.5
    SO_SWITCH_NONE = -1

    DragStep = collections.namedtuple(
        "DragStep", "height length operation reversed valid hidden"
    )

    def setUp(self):
        super().setUp()
        self._refresh_view_widgets()
        self._settle_view()

    # -- helpers ---------------------------------------------------------

    def _refresh_view_widgets(self, timeout_ms=1000):
        """The live 3D view of the test document and its viewport widget.

        Right after a document switch the active view can still be the previous one
        on its way out, so it is fetched again on every try.
        """

        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
            try:
                self.view = FreeCADGui.getDocument(self.doc.Name).ActiveView
                self.viewer = self.view.getViewer()
                self.viewport = self.view.graphicsView().viewport()
                self.viewport.rect()
                return
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                self._process_events(20)

    def _settle_view(self, timeout_ms=4000):
        """Look at the pad from the isometric side and wait for the camera to stop."""

        self.view.viewIsometric()
        self.view.fitAll()
        deadline = time.monotonic() + timeout_ms / 1000.0
        previous = None
        still = 0
        while still < 3:
            self._process_events(100)
            current = (self.viewport.size(), self._pixels(self.ARROW_TIP))
            still = still + 1 if current == previous else 0
            previous = current
            if time.monotonic() >= deadline:
                self.fail("the 3D view did not settle")

    def _pixels(self, point):
        """Where ``point`` lands in the view, in Coin's device pixels from the bottom left."""

        return self.view.getPointOnScreen(point)

    def _qt_pos(self, pixels):
        """The Qt widget position for Coin device pixels."""

        ratio = self.viewport.devicePixelRatioF()
        return QtCore.QPointF(pixels[0] / ratio, self.viewport.height() - pixels[1] / ratio)

    def _arrow_grip(self):
        """A point on the length arrow, found by asking the scene what is under it."""

        from pivy import coin

        manager = self.viewer.getSoRenderManager()
        tip = self._pixels(self.ARROW_TIP)
        base = self._pixels(self.ARROW_BASE)
        for along in (0.0, 0.03, 0.06, 0.1, 0.15):
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
                    if name == "SoLinearDraggerContainer":
                        return pixels
        self.fail("the length arrow is not under any of the points tried")

    def _switches_above_arrow(self):
        """The switches on the arrow's path from the scene root; one of them hides the gizmos."""

        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoLinearDraggerContainer"))
        search.setInterest(coin.SoSearchAction.FIRST)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        path = search.getPath()
        self.assertIsNotNone(path, "the length arrow is not in the scene")
        switches = [
            coin.cast(path.getNode(depth), "SoSwitch")
            for depth in range(path.getLength())
            if path.getNode(depth).isOfType(coin.SoSwitch.getClassTypeId())
        ]
        self.assertTrue(switches, "expected a switch above the arrow")
        return switches

    def _arrow_hidden(self, switches):
        return any(switch.whichChild.getValue() == self.SO_SWITCH_NONE for switch in switches)

    def _mouse(self, kind, pos, button, buttons):
        event = QtGui.QMouseEvent(
            kind,
            pos,
            self.viewport.mapToGlobal(pos.toPoint()),
            button,
            buttons,
            QtCore.Qt.NoModifier,
        )
        QtWidgets.QApplication.instance().sendEvent(self.viewport, event)

    def _drag_arrow(self, heights):
        """Press on the arrow and drag its tip to each height in turn, in mm above the profile.

        One record per step says what the extrude looked like once that move had been
        handled. The button is released at the end whatever happens.
        """

        switches = self._switches_above_arrow()
        grip = self._qt_pos(self._arrow_grip())
        base_y = self._qt_pos(self._pixels(self.ARROW_BASE)).y()
        tip_y = self._qt_pos(self._pixels(self.ARROW_TIP)).y()
        per_mm = (base_y - tip_y) / 10.0
        self._mouse(QtCore.QEvent.MouseMove, grip, QtCore.Qt.NoButton, QtCore.Qt.NoButton)
        self._process_events()
        self._mouse(QtCore.QEvent.MouseButtonPress, grip, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton)
        self._process_events(100)
        steps = []
        pos = grip
        try:
            for height in heights:
                pos = QtCore.QPointF(grip.x(), grip.y() + (10.0 - height) * per_mm)
                self._mouse(QtCore.QEvent.MouseMove, pos, QtCore.Qt.NoButton, QtCore.Qt.LeftButton)
                self._process_events(100)
                steps.append(
                    self.DragStep(
                        height,
                        self._length(),
                        self.operationMode.currentIndex(),
                        bool(self.pad.Reversed),
                        self.pad.isValid(),
                        self._arrow_hidden(switches),
                    )
                )
        finally:
            self._mouse(QtCore.QEvent.MouseButtonRelease, pos, QtCore.Qt.LeftButton, QtCore.Qt.NoButton)
            self._process_events(100)
        self.assertLess(steps[0].length, 10.0, "the arrow did not take the drag")
        return steps

    def _preview_z_range(self):
        """The lowest and highest z the previews on screen reach."""

        from pivy import coin

        manager = self.viewer.getSoRenderManager()
        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoPreviewShape"))
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(manager.getSceneGraph())
        paths = search.getPaths()
        self.assertGreater(paths.getLength(), 0, "no preview in the scene")
        bounds = coin.SoGetBoundingBoxAction(manager.getViewportRegion())
        lowest, highest = math.inf, -math.inf
        for index in range(paths.getLength()):
            bounds.apply(paths[index])
            box = bounds.getBoundingBox()
            if box.isEmpty():
                continue
            lowest = min(lowest, box.getMin()[2])
            highest = max(highest, box.getMax()[2])
        return lowest, highest

    # -- tests -----------------------------------------------------------

    def test_the_arrow_keeps_its_footing_past_the_profile(self):
        """Every move below the profile reports the cut the pointer is over, never a jump."""

        steps = self._drag_arrow(self.THROUGH_THE_PROFILE)
        below = [step for step in steps if step.height <= -self.SNAP_TOLERANCE]
        self.assertTrue(below)
        for step in below:
            with self.subTest(height=step.height):
                self.assertEqual(step.operation, CUT)
                self.assertTrue(step.reversed)
                self.assertLessEqual(
                    abs(step.length - abs(step.height)),
                    self.SNAP_TOLERANCE,
                    f"length {step.length} for a pointer {step.height} mm from the profile",
                )

    def test_passing_the_profile_never_breaks_the_extrude(self):
        """Landing on zero on the way past is not a zero-length extrude."""

        steps = self._drag_arrow(self.THROUGH_THE_PROFILE)
        broken = [step.height for step in steps if not step.valid or step.length <= 0.0]
        self.assertEqual(broken, [], "the extrude was left broken at these pointer heights")

    def test_the_arrow_stays_visible_while_it_is_dragged_past_the_profile(self):
        steps = self._drag_arrow(self.THROUGH_THE_PROFILE)
        hidden = [step.height for step in steps if step.hidden]
        self.assertEqual(hidden, [], "the gizmos were hidden at these pointer heights")

    def test_a_failing_recompute_does_not_hide_an_arrow_being_dragged(self):
        """The gizmos hide on a failed recompute, except under an arrow that holds the mouse."""

        switches = self._switches_above_arrow()
        # A direction across the profile cannot be extruded along, so every recompute fails.
        self.pad.UseCustomVector = True
        self.pad.Direction = FreeCAD.Vector(1.0, 0.0, 0.0)
        self._set_drag_active(True)
        self._set_raw_length(5.0)
        self.assertFalse(self.pad.isValid(), "the extrude was expected to fail")
        # Crossing the profile re-places the gizmos while the extrude is still broken.
        self._set_raw_length(-5.0)
        self.assertFalse(self._arrow_hidden(switches), "the arrow was hidden mid-drag")

        self._set_drag_active(False)
        self.assertTrue(
            self._arrow_hidden(switches), "a broken extrude keeps its gizmos once the drag is over"
        )

    def test_a_cut_with_nothing_to_cut_shows_only_its_tool(self):
        """Nothing is removed from an empty body, so nothing but the tool is previewed."""

        self._set_raw_length(3.0)
        self._set_raw_length(-1.0)
        self.assertEqual(self.operationMode.currentIndex(), CUT)

        lowest, highest = self._preview_z_range()
        self.assertAlmostEqual(lowest, -1.0, places=3)
        self.assertLessEqual(highest, 1e-6, "the join's preview was left on screen above the profile")

    def test_turning_a_cut_back_into_a_join_drops_the_tool_preview(self):
        self._set_raw_length(-1.0)
        self._set_raw_length(3.0)
        self.assertEqual(self.operationMode.currentIndex(), JOIN)

        lowest, highest = self._preview_z_range()
        self.assertAlmostEqual(highest, 3.0, places=3)
        self.assertGreaterEqual(
            lowest, -1e-6, "the cut's tool preview was left on screen below the profile"
        )
