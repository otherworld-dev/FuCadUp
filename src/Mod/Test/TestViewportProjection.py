# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 FreeCAD contributors
# SPDX-FileNotice: Part of the FreeCAD project.

"""Tests that a world point projects to the pixel where it was rendered.

The 3D view's shape is not fixed: Adam works over Remote Desktop, so the view
follows the client window and can be taller than it is wide. Coin expands the
camera's view volume by 1/aspect in that case (viewportMapping ADJUST_CAMERA),
which is why a tall window shows more scene rather than a squashed one. Code that
projects a point without repeating that expansion works in a different space from
the one that was rendered and picked. These tests pin the projection down at three
viewport shapes so a regression shows up wherever the window happens to be.
"""

import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

TOLERANCE_PX = 1.5


class ViewportProjectionCase(unittest.TestCase):
    """A document with one measurable point and a view we can reshape."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("ViewportProjection")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        box = self.doc.addObject("Part::Box", "Box")
        box.Length, box.Width, box.Height = 10.0, 6.0, 4.0
        self.doc.recompute()
        self.view = FreeCADGui.activeView()
        self.view.setCameraType("Orthographic")  # viewIsometric() sets orientation, not type
        self.view.viewIsometric()
        self.view.fitAll()
        self._pump(300)
        self.viewer = self.view.getViewer()
        self._original_window_size = FreeCADGui.getMainWindow().size()
        self.addCleanup(self._close)
        self.addCleanup(self._restore_window_size)

    def _close(self):
        try:
            FreeCAD.closeDocument(self.doc.Name)
        except (ReferenceError, RuntimeError, NameError):
            pass

    def _restore_window_size(self):
        """_shape_view leaves the main window resized towards whatever the last test
        asked for; left alone, that hands the next GUI test class in this process a
        window shape it never asked for - e.g. the tall shape these tests need would
        look like a real regression to a class that itself checks it isn't tall
        (Task 6's pattern grip tests, which are exactly the ones that fail in a tall
        window). Registered after _close, so addCleanup's LIFO order runs this first,
        resizing while the document and its camera still exist - resizing after
        _close raised a caught-but-logged "Could not find reference to 3D View
        camera" exception during development, which this ordering avoids."""
        FreeCADGui.getMainWindow().resize(self._original_window_size)
        self._pump(300)

    def _pump(self, ms=100):
        loop = QtCore.QEventLoop()
        QtCore.QTimer.singleShot(ms, loop.quit)
        loop.exec_()

    def _viewport_pixels(self):
        size = self.viewer.getSoRenderManager().getViewportRegion().getViewportSizePixels()
        return int(size[0]), int(size[1])

    def _shape_view(self, width, height):
        """Reshape the 3D view towards width x height logical px; return the achieved
        device-pixel size. Tries the main window first, then - if the window manager
        won't give the wanted orientation that way (e.g. a maximised or tiled window
        manager) - resizes the MDI sub-window directly instead of skipping: a skipped
        test proves nothing, so a second shape is tried before giving up."""
        window = FreeCADGui.getMainWindow()
        window.resize(width, height)
        self._pump(400)
        self.view.fitAll()
        self._pump(300)
        achieved = self._viewport_pixels()
        wanted_tall = height > width

        def is_right_shape(size):
            got_tall = size[1] > size[0]
            return wanted_tall == got_tall

        if not is_right_shape(achieved):
            mdi_area = window.findChild(QtWidgets.QMdiArea)
            sub_window = mdi_area.activeSubWindow() if mdi_area is not None else None
            if sub_window is not None:
                sub_window.resize(width, height)
                self._pump(400)
                self.view.fitAll()
                self._pump(300)
                achieved = self._viewport_pixels()

        if not is_right_shape(achieved):
            self.skipTest(
                "the window manager gave a %dx%d viewport, not the %s shape this test needs"
                % (achieved[0], achieved[1], "tall" if wanted_tall else "wide")
            )
        return achieved

    def _calibrated_pixel(self, point):
        """Where `point` lands, in Coin device pixels, computed independently of the
        function under test: `projectPointToLine` is paired with getNormalizedPosition(),
        which applies the aspect adjustment in normalized pixel space, and is correct at
        any viewport shape. With an orthographic camera screen position is an affine
        function of world position, so the view's own centre pixel plus one step along
        each pixel axis inverts that map exactly."""
        width, height = (float(v) for v in self._viewport_pixels())
        ox, oy = int(width / 2.0), int(height / 2.0)
        step = max(1, int(min(width, height) / 4.0))

        def world_at(pixel):
            near, _far = self.view.projectPointToLine(int(pixel[0]), int(pixel[1]))
            return near

        base = world_at((ox, oy))
        along_x = world_at((ox + step, oy)) - base
        along_y = world_at((ox, oy + step)) - base

        target = FreeCAD.Vector(point) - base
        gxx, gxy = along_x.dot(along_x), along_x.dot(along_y)
        gyx, gyy = along_y.dot(along_x), along_y.dot(along_y)
        rx, ry = target.dot(along_x), target.dot(along_y)
        det = gxx * gyy - gxy * gyx
        if abs(det) < 1e-9:
            self.fail("the view's own projection could not be calibrated")
        a = (rx * gyy - ry * gxy) / det
        b = (gxx * ry - gyx * rx) / det
        return (ox + a * step, oy + b * step)

    def _round_trip_error(self, point):
        """How far, in mm, getPointOnViewport's screen->world round trip misses `point`
        by: project it to a pixel, unproject that pixel back to world space via
        projectPointToLine (the already-correct path), and compare against the world
        point obtained by unprojecting the *independently calibrated* pixel instead.
        Zero only when getPointOnViewport is the exact inverse of the screen->world
        path - which every consumer of it relies on. Reused by Tasks 4 and 5."""
        pixel = self.view.getPointOnViewport(point.x, point.y, point.z)
        near, _far = self.view.projectPointToLine(int(pixel[0]), int(pixel[1]))
        expected_pixel = self._calibrated_pixel(point)
        back = self.view.projectPointToLine(
            int(round(expected_pixel[0])), int(round(expected_pixel[1]))
        )[0]
        return (near - back).Length

    def _assert_projects_where_rendered(self, shape, point):
        achieved = self._shape_view(*shape)
        expected = self._calibrated_pixel(point)
        actual = self.view.getPointOnViewport(point.x, point.y, point.z)
        dx, dy = actual[0] - expected[0], actual[1] - expected[1]
        self.assertLess(
            (dx * dx + dy * dy) ** 0.5,
            TOLERANCE_PX,
            "in a %dx%d viewport, %s projected to %s but was rendered at (%.1f, %.1f)"
            % (achieved[0], achieved[1], point, tuple(actual), expected[0], expected[1]),
        )

    # -- the projection itself -------------------------------------------------

    def test_a_point_projects_where_it_is_rendered_in_a_wide_view(self):
        self._assert_projects_where_rendered((1400, 700), FreeCAD.Vector(10, 6, 4))

    def test_a_point_projects_where_it_is_rendered_in_a_tall_view(self):
        self._assert_projects_where_rendered((700, 1300), FreeCAD.Vector(10, 6, 4))

    def test_a_point_projects_where_it_is_rendered_in_a_square_view(self):
        self._assert_projects_where_rendered((1000, 1000), FreeCAD.Vector(10, 6, 4))

    def test_the_centre_of_the_view_projects_to_the_centre_in_a_tall_view(self):
        """The one case needing no calibration at all: whatever the view's shape, the
        camera's focal point is rendered at the middle of the viewport."""
        achieved = self._shape_view(700, 1300)
        focal = self.view.getCameraNode().position.getValue()
        direction = self.view.getViewDirection()  # exposed on the view, not the viewer
        distance = self.view.getCameraNode().focalDistance.getValue()
        centre = FreeCAD.Vector(focal[0], focal[1], focal[2]) + direction * distance
        actual = self.view.getPointOnViewport(centre.x, centre.y, centre.z)
        self.assertAlmostEqual(actual[0], achieved[0] / 2.0, delta=2.0)
        self.assertAlmostEqual(actual[1], achieved[1] / 2.0, delta=2.0)

    # -- the round trip consumers rely on --------------------------------------

    def test_projecting_and_unprojecting_returns_the_same_point_in_a_tall_view(self):
        """getPointOnViewport must be the exact inverse of the screen->world path,
        because that is what every consumer round-trips against."""
        self._shape_view(700, 1300)
        point = FreeCAD.Vector(10, 6, 4)
        error = self._round_trip_error(point)
        self.assertLess(
            error,
            0.2,
            "the round trip landed %.3f mm away from where the point is rendered" % error,
        )

    def test_the_screen_to_world_path_is_correct_in_a_tall_view(self):
        """Documents that getPointOnFocalPlane already honours the view's shape: it is
        paired with getNormalizedPosition(), unlike getPointOnViewport. Expected to pass
        before any fix - if it ever fails, the convention moved.

        Asserts the focal-plane point's perpendicular distance from the picking ray at
        the same pixel, rather than a signed dot product against one particular
        sideways axis: a signed value is < 0.2 for every negative deviation too, so it
        can never actually fail. The perpendicular-distance form (|AP x AB| / |AB|,
        the standard point-to-line distance) catches a drift in any direction, not
        only "more positive along this axis", and is what "on the ray" actually
        means."""
        achieved = self._shape_view(700, 1300)
        centre_pixel = (int(achieved[0] / 2), int(achieved[1] / 2))
        on_plane = FreeCAD.Vector(self.view.getPointOnFocalPlane(*centre_pixel))
        near, far = self.view.projectPointToLine(*centre_pixel)
        ray = far - near
        ray_length = ray.Length
        if ray_length < 1e-9:
            self.fail("the picking ray at the centre pixel had zero length")
        offset = on_plane - near
        perpendicular = offset.cross(ray).Length / ray_length
        self.assertLess(
            perpendicular,
            0.2,
            "the focal-plane point is %.3f mm off the picking ray at the centre pixel"
            % perpendicular,
        )


if __name__ == "__main__":
    unittest.main()
