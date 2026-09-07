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

"""GUI regression tests for the Sketcher snap feedback and its way out of a sketch.

Three things are checked here:

* Snapping the pointer onto the grid draws a glyph, and the glyph goes away again
  once the pointer travels back between the grid lines. Point snaps (the origin, a
  vertex, a crossing) already drew one; the grid, the axes and a curve did not, so
  the pointer moved on its own with nothing on screen to explain it.
* Dragging existing geometry does not step from grid line to grid line. The grid
  pulls the pointer while a tool is drawing, but a drag is an adjustment of what is
  already there and has to follow the pointer.
* The way out of a sketch is reachable: Sketcher_LeaveSketch carries a shortcut of
  its own, its tooltip no longer promises that Escape leaves the sketch, and the
  Grid and Snap panels stay available while a tool is drawing.

To run tests:
    FreeCAD -t TestSketcherSnapFeedback
"""

import math
import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

SNAP_PARAMS = "User parameter:BaseApp/Preferences/Mod/Sketcher/Snap"

NO_BUTTON = QtCore.Qt.NoButton
LEFT_BUTTON = QtCore.Qt.LeftButton
NO_MODIFIER = QtCore.Qt.NoModifier
OTHER_FOCUS_REASON = QtCore.Qt.OtherFocusReason
MOUSE_MOVE = QtCore.QEvent.MouseMove
MOUSE_PRESS = QtCore.QEvent.MouseButtonPress
MOUSE_RELEASE = QtCore.QEvent.MouseButtonRelease

# Sketch units between grid lines, and the zoom the tests work at: a pitch of 40
# device pixels leaves a snap band of a third of the pitch on each side of a line,
# comfortably wider than the pixel a projected point rounds to.
GRID_SIZE = 10.0
TARGET_PITCH_PX = 40.0
GRID_SNAP_TOLERANCE = 15.0
SNAP_RADIUS = 8.0

# Pointer travel of the drag tests, in device pixels. Short enough that the grid
# would pull the dragged point back onto the line it started on.
DRAG_TRAVEL_PX = 6.0


class TestSketcherSnapFeedback(unittest.TestCase):
    """A sketch in edit mode on the XY plane, seen square-on at a known zoom."""

    def setUp(self):
        self._override_snap_parameters()

        self.doc = FreeCAD.newDocument("TestSketcherSnapFeedback")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.doc.recompute()

        self._process_events(50)
        try:
            self._refresh_view_widgets(timeout_ms=3000)
        except RuntimeError as exc:
            self._abandon_set_up()
            raise unittest.SkipTest(
                "3D view widget wrapping is unavailable in this test environment: " + str(exc)
            )

        # tearDown does not run for a set-up that raises, so from here on a skip - or a
        # failure out of one of the waits - has to hand back the document and the
        # preferences itself.
        try:
            self._prepare_the_sketch_view()
        except Exception:
            self._abandon_set_up()
            raise

    def _prepare_the_sketch_view(self):
        self.viewer.setEnabledNaviCube(False)
        self.view.setAxisCross(False)
        self.view.setCameraType("Orthographic")

        view_object = self.sketch.ViewObject
        view_object.GridAuto = False
        view_object.GridSize = GRID_SIZE
        view_object.ShowGrid = True
        # A constraint born mid-drag would move the point for reasons of its own.
        view_object.Autoconstraints = False

        FreeCADGui.activateWorkbench("SketcherWorkbench")
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name, 0)
        self._process_events(100)
        self._wait_for_camera_to_settle()
        self._refresh_view_widgets()
        self.viewport.setFocus(OTHER_FOCUS_REASON)
        self._zoom_until_the_grid_is_readable()
        self._wait_for_view_to_settle()
        self._require_a_square_on_view()

    def tearDown(self):
        self._leave_edit_mode()
        self._restore_snap_parameters()
        self._discard_document()

    # -- set-up helpers --------------------------------------------------

    def _leave_edit_mode(self):
        try:
            FreeCADGui.ActiveDocument.resetEdit()
        except Exception:  # noqa: BLE001 - the document may already be gone
            pass
        self._process_events(50)

    def _abandon_set_up(self):
        """Undo a half-finished set-up, which tearDown will never be called to do."""

        self._leave_edit_mode()
        self._restore_snap_parameters()
        self._discard_document()

    def _override_snap_parameters(self):
        self.params = FreeCAD.ParamGet(SNAP_PARAMS)
        self.saved_bools = {
            name: self.params.GetBool(name, True)
            for name in ("Snap", "SnapToObjects", "SnapToGrid")
        }
        self.saved_floats = {
            "GridSnapTolerance": self.params.GetFloat("GridSnapTolerance", GRID_SNAP_TOLERANCE),
            "SnapRadius": self.params.GetFloat("SnapRadius", SNAP_RADIUS),
        }
        for name in self.saved_bools:
            self.params.SetBool(name, True)
        self.params.SetFloat("GridSnapTolerance", GRID_SNAP_TOLERANCE)
        self.params.SetFloat("SnapRadius", SNAP_RADIUS)

    def _restore_snap_parameters(self):
        for name, value in self.saved_bools.items():
            self.params.SetBool(name, value)
        for name, value in self.saved_floats.items():
            self.params.SetFloat(name, value)

    def _discard_document(self):
        if getattr(self, "doc", None) is not None:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtGui.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _refresh_view_widgets(self, timeout_ms=1000):
        """Grab the live 3D view of the test document and its viewport widget.

        Right after a document switch the active view can still be the previous
        document window on its way out, so the view is re-fetched on each try.
        """

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            try:
                self.view = FreeCADGui.getDocument(self.doc.Name).ActiveView
                self.viewer = self.view.getViewer()
                graphics_view = self.view.graphicsView()
                viewport = graphics_view.viewport()
                viewport.rect()
                self.graphics_view = graphics_view
                self.viewport = viewport
                return
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                self._process_events(20)

    def _camera_state(self):
        camera = self.view.getCameraNode()
        position = FreeCAD.Vector(*camera.position.getValue().getValue())
        orientation = self.view.getCameraOrientation()
        height = camera.height.getValue()
        return position, orientation, height

    def _wait_for_camera_to_settle(self, timeout_ms=3000):
        """Let the animated swing onto the sketch plane finish before reading the camera."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        previous = self._camera_state()
        while True:
            self._process_events(100)
            current = self._camera_state()
            if (
                (previous[0] - current[0]).Length <= 1e-3
                and previous[1].isSame(current[1], 1e-4)
                and abs(previous[2] - current[2]) <= 1e-3
            ):
                return
            if time.monotonic() >= deadline:
                self.fail("The camera kept moving after the sketch was opened")
            previous = current

    def _wait_for_view_to_settle(self, timeout_ms=3000):
        """Wait until the viewport size and the projected origin stop changing."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        previous = (self.viewport.size(), self._project(0.0, 0.0))
        while True:
            self._process_events(100)
            self._refresh_view_widgets()
            current = (self.viewport.size(), self._project(0.0, 0.0))
            if current == previous:
                return
            if time.monotonic() >= deadline:
                self.fail("The 3D view kept changing size after the sketch was opened")
            previous = current

    def _zoom_until_the_grid_is_readable(self):
        """Put the sketch origin in the middle of the view at a known grid pitch."""

        from pivy import coin

        camera = self.view.getCameraNode()
        pitch = GRID_SIZE / self._units_per_pixel()
        camera.height = max(1e-6, camera.height.getValue() * pitch / TARGET_PITCH_PX)
        position = camera.position.getValue().getValue()
        camera.position.setValue(coin.SbVec3f(0.0, 0.0, position[2]))
        self._process_events(100)

    def _require_a_square_on_view(self):
        """The tests read pixels along the sketch axes, so the view must be square-on."""

        ox, oy = self._project(0.0, 0.0)
        x_axis = self._project(GRID_SIZE, 0.0)
        y_axis = self._project(0.0, GRID_SIZE)
        if (
            abs(x_axis[1] - oy) > 1.0
            or abs(y_axis[0] - ox) > 1.0
            or x_axis[0] <= ox
            or y_axis[1] <= oy
        ):
            raise unittest.SkipTest("The sketch plane is not seen square-on in this environment")

        pitch = GRID_SIZE / self._units_per_pixel()
        if pitch < 24.0:
            raise unittest.SkipTest("The 3D view is too small to draw a readable grid")

    # -- geometry of the view --------------------------------------------

    def _device_pixel_ratio(self):
        if hasattr(self.viewport, "devicePixelRatioF"):
            return self.viewport.devicePixelRatioF()
        return float(self.viewport.devicePixelRatio())

    def _project(self, u, v):
        """Device pixels, measured from the bottom-left corner, of a sketch point."""

        px, py = self.view.getPointOnScreen(FreeCAD.Vector(u, v, 0.0))
        return float(px), float(py)

    def _units_per_pixel(self):
        origin = self._project(0.0, 0.0)
        along_x = self._project(GRID_SIZE, 0.0)
        distance = math.hypot(along_x[0] - origin[0], along_x[1] - origin[1])
        if distance <= 0.0:
            raise unittest.SkipTest("The 3D view does not project the sketch plane")
        return GRID_SIZE / distance

    def _widget_point(self, u, v):
        px, py = self._project(u, v)
        dpr = self._device_pixel_ratio()
        return QtCore.QPoint(int(round(px / dpr)), int(round(self.viewport.height() - py / dpr)))

    def _grid_tolerance(self):
        """How far, in sketch units, the grid reaches for the pointer."""

        units_per_pixel = self._units_per_pixel()
        pitch_px = GRID_SIZE / units_per_pixel
        return min(GRID_SNAP_TOLERANCE, pitch_px / 3.0) * units_per_pixel

    def _grid_point(self):
        """A grid intersection well clear of the origin and of both axes."""

        return 2.0 * GRID_SIZE, 2.0 * GRID_SIZE

    def _require_on_screen(self, points):
        rect = self.viewport.rect().adjusted(20, 20, -20, -20)
        for u, v in points:
            if not rect.contains(self._widget_point(u, v)):
                raise unittest.SkipTest("The 3D view is too small to hold the test sketch")

    # -- driving the pointer ---------------------------------------------

    def _send_mouse_event(self, event_type, pos, button, buttons):
        self._refresh_view_widgets()
        app = QtGui.QApplication.instance()
        global_pos = self.viewport.mapToGlobal(pos)
        event = QtGui.QMouseEvent(event_type, pos, global_pos, button, buttons, NO_MODIFIER)
        app.sendEvent(self.viewport, event)

    def _move_pointer(self, u, v, wait_ms=50):
        self._send_mouse_event(MOUSE_MOVE, self._widget_point(u, v), NO_BUTTON, NO_BUTTON)
        self._process_events(wait_ms)

    def _start_line_tool(self):
        FreeCADGui.runCommand("Sketcher_CreateLine", 0)
        self._process_events(100)

    # -- reading the snap glyph ------------------------------------------

    def _find_edit_node(self, name):
        from pivy import coin

        search = coin.SoSearchAction()
        search.setName(coin.SbName(name))
        search.setInterest(coin.SoSearchAction.FIRST)
        search.setSearchingAll(True)
        search.apply(self.sketch.ViewObject.RootNode)
        path = search.getPath()
        return path.getTail() if path else None

    def _snap_marker(self):
        """Where the snap glyph is drawn, or None while no glyph is on screen."""

        marker = self._find_edit_node("SnapMarkerSet")
        if marker is None:
            self.fail("The sketch edit scene graph has no SnapMarkerSet node")
        if marker.numPoints.getValue() < 1:
            return None
        coordinate = self._find_edit_node("SnapMarkerCoordinate")
        self.assertIsNotNone(coordinate, "A snap glyph must come with its coordinate")
        point = coordinate.point.getValues()[0].getValue()
        return point[0], point[1]

    def _snap_marker_index(self):
        """Which bitmap the snap glyph is currently drawn with."""

        marker = self._find_edit_node("SnapMarkerSet")
        self.assertIsNotNone(marker, "The sketch edit scene graph has no SnapMarkerSet node")
        field = marker.markerIndex
        values = field.getValues() if hasattr(field, "getValues") else [field.getValue()]
        self.assertTrue(len(values), "A snap glyph has to name the bitmap it uses")
        return int(values[0])

    def _built_in_marker_indices(self, family):
        """The indices Coin names itself, for the handful of sizes it ships bitmaps for.

        FreeCAD registers the larger bitmaps at run time and their indices have no name, so
        this comes back empty whenever the glyph landed on one of those.
        """

        from pivy import coin

        indices = set()
        for size in (5, 7, 9):
            name = "{}_{}_{}".format(family, size, size)
            if hasattr(coin.SoMarkerSet, name):
                indices.add(int(getattr(coin.SoMarkerSet, name)))
        return indices

    def _snapped_marker_at(self, u, v, message):
        """Move the pointer to (u, v) and return the glyph, retrying the first frame."""

        for _ in range(3):
            self._move_pointer(u, v)
            marker = self._snap_marker()
            if marker is not None:
                return marker
            self._process_events(100)
        self.fail(message)
        return None

    # -- dragging --------------------------------------------------------

    def _reset_line(self, start, end):
        import Part

        if self.sketch.GeometryCount:
            self.sketch.delGeometry(0)
        self.sketch.addGeometry(
            Part.LineSegment(
                FreeCAD.Vector(start[0], start[1], 0.0),
                FreeCAD.Vector(end[0], end[1], 0.0),
            ),
            False,
        )
        self.doc.recompute()
        self._process_events(50)

    def _drag_end_point(self, grab, travel_px):
        """Press on the sketch point at grab, pull it travel_px along +X, release."""

        press = self._widget_point(*grab)
        target = QtCore.QPoint(
            press.x() + int(round(travel_px / self._device_pixel_ratio())), press.y()
        )

        # Preselect the point first: a press only starts a drag on what is under it.
        self._send_mouse_event(MOUSE_MOVE, press, NO_BUTTON, NO_BUTTON)
        self._process_events(50)
        self._send_mouse_event(MOUSE_MOVE, press, NO_BUTTON, NO_BUTTON)
        self._process_events(50)

        self._send_mouse_event(MOUSE_PRESS, press, LEFT_BUTTON, LEFT_BUTTON)
        self._process_events(50)
        # The first move past the ignored distance only starts the drag; the second
        # one is the first that moves anything.
        self._send_mouse_event(MOUSE_MOVE, target, NO_BUTTON, LEFT_BUTTON)
        self._process_events(50)
        self._send_mouse_event(MOUSE_MOVE, target, NO_BUTTON, LEFT_BUTTON)
        self._process_events(50)
        self._send_mouse_event(MOUSE_RELEASE, target, LEFT_BUTTON, NO_BUTTON)
        self._process_events(150)

        return self.sketch.Geometry[0].EndPoint

    # -- tests -----------------------------------------------------------

    def test_snapping_to_the_grid_draws_a_marker_of_its_own(self):
        grid_x, grid_y = self._grid_point()
        half = GRID_SIZE / 2.0
        # Half a cell out on both axes, so the grid cannot reach it and only the vertex can.
        vertex = (grid_x + half, grid_y + half)
        far_end = (vertex[0] + GRID_SIZE, vertex[1])
        self._require_on_screen([(grid_x, grid_y), vertex, far_end])
        offset = 0.35 * self._grid_tolerance()

        self._reset_line(vertex, far_end)
        self._start_line_tool()

        marker = self._snapped_marker_at(
            grid_x + offset,
            grid_y + offset,
            "Snapping the pointer onto a grid intersection must draw a marker",
        )
        grid_index = self._snap_marker_index()
        self.assertAlmostEqual(marker[0], grid_x, delta=0.01)
        self.assertAlmostEqual(marker[1], grid_y, delta=0.01)

        # One glyph for every kind of snap would say no more than none at all: catching a
        # vertex has to look different from settling onto a grid line.
        caught = self._snapped_marker_at(
            vertex[0], vertex[1], "Snapping the pointer onto a vertex must draw a marker"
        )
        vertex_index = self._snap_marker_index()
        self.assertAlmostEqual(caught[0], vertex[0], delta=0.01)
        self.assertAlmostEqual(caught[1], vertex[1], delta=0.01)

        self.assertNotEqual(
            grid_index,
            vertex_index,
            "the grid and a vertex must not be marked with the same glyph",
        )

        # Both glyphs pick their size by the same rule out of the same table, so when the
        # vertex landed on a size Coin names, the grid glyph can be named exactly too.
        if vertex_index in self._built_in_marker_indices("SQUARE_FILLED"):
            self.assertIn(
                grid_index,
                self._built_in_marker_indices("SQUARE_LINE"),
                "the grid snap must be marked with an outlined square",
            )

    def test_the_marker_goes_away_between_the_grid_lines(self):
        grid_x, grid_y = self._grid_point()
        half = GRID_SIZE / 2.0
        self._require_on_screen([(grid_x, grid_y), (grid_x + half, grid_y + half)])
        offset = 0.35 * self._grid_tolerance()

        self._start_line_tool()
        self._snapped_marker_at(
            grid_x + offset, grid_y + offset, "The grid snap must draw a marker to begin with"
        )

        self._move_pointer(grid_x + half, grid_y + half)
        self.assertIsNone(
            self._snap_marker(),
            "The marker must go away once the pointer travels between the grid lines",
        )

    def test_dragging_a_point_does_not_step_along_the_grid(self):
        grid_x, grid_y = self._grid_point()
        start = (grid_x, grid_y)
        other = (grid_x - GRID_SIZE, grid_y)
        self._require_on_screen([start, other])

        travel = DRAG_TRAVEL_PX * self._units_per_pixel()
        self.assertLess(
            travel,
            self._grid_tolerance(),
            "the drag has to stay inside the pull of the grid line it starts on",
        )

        # A drag with the grid snap switched off is what every drag should do.
        self.params.SetBool("SnapToGrid", False)
        self._reset_line(other, start)
        free = self._drag_end_point(start, DRAG_TRAVEL_PX)
        self.assertGreater(
            abs(free.x - grid_x),
            0.5 * travel,
            "the point was never dragged, so the test would prove nothing",
        )

        # Park the pointer well away so the next press is not read as a double click.
        self._move_pointer(grid_x, grid_y - GRID_SIZE, wait_ms=400)

        self.params.SetBool("SnapToGrid", True)
        self._reset_line(other, start)
        snapped = self._drag_end_point(start, DRAG_TRAVEL_PX)

        self.assertAlmostEqual(
            snapped.x,
            free.x,
            delta=0.01,
            msg="dragging a point must not step from grid line to grid line",
        )
        self.assertAlmostEqual(snapped.y, free.y, delta=0.01)

    def test_grid_and_snap_stay_available_while_a_tool_draws(self):
        """A lock, not a verification.

        Both toggles already answered yes mid-tool before this change - the helper they used
        never looked at the running handler, whatever its name says. The test is here so that
        a future tightening of either isActive() cannot quietly take the Grid and Snap panels
        away from someone halfway through drawing.
        """

        grid_x, grid_y = self._grid_point()
        self._require_on_screen([(grid_x, grid_y)])
        offset = 0.35 * self._grid_tolerance()

        self._start_line_tool()
        # A snap marker is only ever drawn by a running tool, so this both proves the
        # tool is drawing and sets up the state the toggles used to be refused in.
        self._snapped_marker_at(
            grid_x + offset, grid_y + offset, "The line tool must be drawing for this test"
        )

        self.assertTrue(
            FreeCADGui.Command.get("Sketcher_Snap").isActive(),
            "The Snap panel must stay available while a tool is drawing",
        )
        self.assertTrue(
            FreeCADGui.Command.get("Sketcher_Grid").isActive(),
            "The Grid panel must stay available while a tool is drawing",
        )


class TestSketcherLeaveSketch(unittest.TestCase):
    """Leaving a sketch has to be reachable, and has to say so honestly."""

    def setUp(self):
        FreeCADGui.activateWorkbench("SketcherWorkbench")
        self.command = FreeCADGui.Command.get("Sketcher_LeaveSketch")
        if self.command is None:
            raise unittest.SkipTest("The Sketcher commands are not registered")

    def test_leave_sketch_has_a_shortcut_of_its_own(self):
        shortcut = self.command.getShortcut()
        self.assertNotEqual(shortcut, "", "Leaving a sketch needs a keyboard shortcut")
        self.assertEqual(
            FreeCADGui.Command.listByShortcut(shortcut),
            ["Sketcher_LeaveSketch"],
            "The shortcut for leaving a sketch must not be shared with another command",
        )

    def test_leave_sketch_does_not_promise_that_escape_leaves(self):
        tooltip = self.command.getInfo()["toolTip"]
        self.assertNotIn(
            "Escape",
            tooltip,
            "Escape stops the running tool, so the tooltip must not offer it as the way out",
        )


if __name__ == "__main__":
    unittest.main()
