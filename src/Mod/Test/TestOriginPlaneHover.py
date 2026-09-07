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

"""GUI regression tests for hovering the planes of a local coordinate system.

Each origin plane is drawn as a quarter square that grows to the full square while
it is hovered or selected. All origin planes pick "on top" of the rest of the scene,
so Coin reports every one of them at the same depth and cannot use distance to tell
them apart. The grown square therefore must not take part in picking, otherwise the
plane that grew keeps the highlight after the cursor has moved onto its neighbour.

To run tests:
    FreeCAD -t TestOriginPlaneHover
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"

NO_BUTTON = QtCore.Qt.NoButton
NO_MODIFIER = QtCore.Qt.NoModifier
OTHER_FOCUS_REASON = QtCore.Qt.OtherFocusReason
MOUSE_MOVE = QtCore.QEvent.MouseMove

# Gap between the axes and a plane's quarter, see ViewProviderPlane::updatePlaneSize.
QUARTER_OFFSET = 8.0


class TestOriginPlaneHover(unittest.TestCase):
    """Moving the cursor between origin planes must always highlight the plane under it."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestOriginPlaneHover")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.lcs = self.doc.addObject("App::LocalCoordinateSystem", "LCS")
        self.doc.recompute()
        self.lcs.ViewObject.Visibility = True
        for datum in self.lcs.OriginFeatures:
            datum.ViewObject.Visibility = True

        self._process_events(50)
        try:
            self._refresh_view_widgets(timeout_ms=3000)
        except RuntimeError as exc:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None
            raise unittest.SkipTest(
                "3D view widget wrapping is unavailable in this test environment: " + str(exc)
            )

        self.viewer.setEnabledNaviCube(False)
        self.view.setAxisCross(False)
        self.view.setCameraType("Orthographic")
        self._aim_camera_at_origin()
        self._locate_planes()
        # Warm up: the first mouse move after a view is created can land before its
        # first frame, so park the cursor on empty space until picking answers.
        for _ in range(3):
            self._send_mouse_move(self._screen_point(self.empty_space))
            self._process_events()

    def tearDown(self):
        FreeCADGui.Selection.clearPreselection()
        FreeCADGui.Selection.clearSelection()
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtGui.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _refresh_view_widgets(self, timeout_ms=1000):
        """Grab the live 3D view of the test document and its viewport widget.

        Right after a document switch the active view can still be the previous
        document's window on its way out, so the view is re-fetched on each try.
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

    def _aim_camera_at_origin(self, direction=FreeCAD.Vector(-1.0, -1.0, -1.0)):
        """Look at the origin along ``direction``, by default from the (+X, +Y, +Z) octant.

        Seen from there the full XZ square projects across the YZ quarter, which is
        the layout in which the highlight used to get stuck on the XZ plane.
        """

        from pivy import coin

        direction = FreeCAD.Vector(direction).normalize()
        camera = self.view.getCameraNode()
        camera.orientation.setValue(
            coin.SbRotation(
                coin.SbVec3f(0.0, 0.0, -1.0),
                coin.SbVec3f(direction.x, direction.y, direction.z),
            )
        )
        # Fitting the view is what recomputes the clipping planes; without it the
        # datums that were not rendered yet stay clipped away.
        self.view.fitAll()
        self._refresh_view_widgets()
        self.viewport.setFocus(OTHER_FOCUS_REASON)
        self._process_events()
        self._process_events()
        self._wait_for_camera_to_settle()

        rotation = self.view.getCameraOrientation()
        self.screen_right = rotation.multVec(FreeCAD.Vector(1.0, 0.0, 0.0))
        self.screen_up = rotation.multVec(FreeCAD.Vector(0.0, 1.0, 0.0))

        self._wait_for_view_to_settle()

    def _origin_on_screen(self):
        """Widget position of the world origin.

        The viewer reports device pixels measured from the bottom-left corner.
        """

        px, py = self.view.getPointOnScreen(FreeCAD.Vector(0.0, 0.0, 0.0))
        dpr = self._device_pixel_ratio()
        return QtCore.QPointF(px / dpr, self.viewport.height() - py / dpr)

    def _wait_for_view_to_settle(self, timeout_ms=3000):
        """Wait until the viewport size and the projected origin stop changing.

        The MDI window can still be laid out after the camera has settled, which
        would shift every projected target.
        """

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        previous = (self.viewport.size(), self._origin_on_screen())
        while True:
            self._process_events(100)
            self._refresh_view_widgets()
            current = (self.viewport.size(), self._origin_on_screen())
            if current == previous:
                return
            if time.monotonic() >= deadline:
                self.fail("The 3D view kept changing size after the camera was set")
            previous = current

    def _device_pixel_ratio(self):
        if hasattr(self.viewport, "devicePixelRatioF"):
            return self.viewport.devicePixelRatioF()
        return float(self.viewport.devicePixelRatio())

    def _camera_state(self):
        camera = self.view.getCameraNode()
        position = FreeCAD.Vector(*camera.position.getValue().getValue())
        orientation = self.view.getCameraOrientation()
        height = camera.height.getValue()
        return position, orientation, height

    def _wait_for_camera_to_settle(self, timeout_ms=3000):
        """Let the animated view change finish before reading the camera."""

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
                self.fail("The camera kept moving after the view was fitted")
            previous = current

    def _locate_planes(self):
        """Work out where the planes are, in the datum's own units.

        The coordinate system keeps a constant size on screen (SoShapeScale), so one
        datum unit is one widget pixel times the LocalCoordinateSystemSize preference.
        """

        params = FreeCAD.ParamGet(VIEW_PARAMS)
        size = (
            params.GetFloat("DatumPlaneSize", 62.0) * params.GetFloat("DatumScale", 100.0) / 100.0
        )
        scale = params.GetFloat("LocalCoordinateSystemSize", 1.0)
        mid = (QUARTER_OFFSET + size) / 2.0 * scale
        far = 2.0 * size * scale

        self.xy_quarter = FreeCAD.Vector(mid, mid, 0.0)
        self.xz_quarter = FreeCAD.Vector(mid, 0.0, mid)
        self.yz_quarter = FreeCAD.Vector(0.0, mid, mid)
        # Low on the XZ quarter and far from the Z axis: seen from the (+X, -Y, +Z)
        # octant this lies in front of the XY quarter on screen.
        self.xz_low_right = FreeCAD.Vector(
            (size - 12.0) * scale, 0.0, (QUARTER_OFFSET + 7.0) * scale
        )
        # Inside the full XZ square but outside its quarter, and clear of every other datum.
        self.xz_grown_only = FreeCAD.Vector(-mid, 0.0, mid)
        self.empty_space = FreeCAD.Vector(-far, 0.0, far)
        self.empty_space_above = FreeCAD.Vector(0.0, far, far)

    def _screen_point(self, world):
        """Widget position of a point given in datum units relative to the origin."""

        origin = self._origin_on_screen()
        return QtCore.QPoint(
            round(origin.x() + world.dot(self.screen_right)),
            round(origin.y() - world.dot(self.screen_up)),
        )

    def _send_mouse_move(self, pos):
        self._refresh_view_widgets()
        app = QtGui.QApplication.instance()
        event = QtGui.QMouseEvent(
            MOUSE_MOVE,
            pos,
            self.viewport.mapToGlobal(pos),
            NO_BUTTON,
            NO_BUTTON,
            NO_MODIFIER,
        )
        app.sendEvent(self.viewport, event)

    def _hover(self, world):
        """Move the cursor onto ``world`` and return the name of the preselected datum.

        A move can arrive before the view has rendered its first frame on a busy
        machine, in which case nothing is picked; give it a couple more chances.
        """

        for attempt in range(3):
            self._send_mouse_move(self._screen_point(world))
            self._process_events()
            picked = self._preselected_datum()
            if picked is not None:
                return picked
            self._process_events(100)
        return None

    def _is_drawn_grown(self, name):
        """A quarter lies entirely in the positive octant; the full square does not."""

        box = FreeCADGui.getDocument(self.doc.Name).getObject(name).getBoundingBox()
        return min(box.XMin, box.YMin, box.ZMin) < -1e-4

    def _assert_only_grown(self, grown):
        for name in ("XY_Plane", "XZ_Plane", "YZ_Plane"):
            self.assertEqual(
                self._is_drawn_grown(name),
                name == grown,
                f"{name} should be {'grown' if name == grown else 'a quarter'}",
            )

    def _preselected_datum(self):
        preselection = FreeCADGui.Selection.getPreselection()
        if not preselection.ObjectName:
            return None
        obj = self.doc.getObject(preselection.ObjectName)
        subnames = preselection.SubElementNames
        if not subnames or not subnames[0]:
            return obj.Name
        resolved = obj.getSubObject(subnames[0], 1)
        return resolved.Name if resolved else None

    # -- tests -----------------------------------------------------------

    def test_hover_moves_from_the_xz_plane_to_the_yz_plane(self):
        self.assertEqual(self._hover(self.xz_quarter), "XZ_Plane")
        self.assertEqual(self._hover(self.yz_quarter), "YZ_Plane")

    def test_hover_moves_from_the_xy_plane_to_the_yz_plane(self):
        # XY comes first in the scene graph, so it used to win every overlap.
        self.assertEqual(self._hover(self.xy_quarter), "XY_Plane")
        self.assertEqual(self._hover(self.yz_quarter), "YZ_Plane")

    def test_hover_moves_from_the_yz_plane_to_the_xz_plane(self):
        self.assertEqual(self._hover(self.yz_quarter), "YZ_Plane")
        self.assertEqual(self._hover(self.xz_quarter), "XZ_Plane")

    def test_grown_plane_does_not_extend_its_hover_region(self):
        self.assertEqual(self._hover(self.xz_quarter), "XZ_Plane")
        self.assertIsNone(self._hover(self.xz_grown_only))

    def test_leaving_the_planes_clears_the_highlight(self):
        self.assertEqual(self._hover(self.xz_quarter), "XZ_Plane")
        self.assertIsNone(self._hover(self.empty_space))

    def test_overlapping_quarters_pick_the_plane_in_front(self):
        """From the (+X, -Y, +Z) octant, FreeCAD's isometric view, the lower part of the
        XZ quarter overlaps the XY quarter on screen with XZ in front. All origin planes
        pick "on top", so Coin cannot order them by depth itself; the plane in front
        must still win over the one that comes first in the scene graph."""
        self._aim_camera_at_origin(FreeCAD.Vector(-1.0, 1.0, -1.0))
        self.assertEqual(self._hover(self.xz_low_right), "XZ_Plane")
        self.assertEqual(self._hover(self.xy_quarter), "XY_Plane")
        self.assertEqual(self._hover(self.xz_low_right), "XZ_Plane")

    def test_flick_from_a_plane_to_empty_space_clears_the_highlight(self):
        """A single move event from inside the overlap straight to empty space must
        clear the highlight; a real flick delivers only a couple of events."""
        self._aim_camera_at_origin(FreeCAD.Vector(-1.0, 1.0, -1.0))
        self.assertEqual(self._hover(self.xz_low_right), "XZ_Plane")
        self.assertIsNone(self._hover(self.empty_space_above))
        self._assert_only_grown(None)

    def test_repeated_hovering_keeps_exactly_one_plane_grown(self):
        planes = (
            ("XY_Plane", self.xy_quarter),
            ("YZ_Plane", self.yz_quarter),
            ("XZ_Plane", self.xz_quarter),
        )
        origin = FreeCAD.Vector(0.0, 0.0, 0.0)
        for cycle in range(4):
            for name, target in planes:
                self.assertEqual(self._hover(target), name, f"cycle {cycle}")
                self._assert_only_grown(name)
                if cycle % 2:
                    # Cross the origin on the way to the next plane, as a real mouse does.
                    self._hover(origin)
                    self._assert_only_grown(None)
