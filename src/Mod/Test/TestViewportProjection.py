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

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

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
        test proves nothing, so a second shape is tried before failing loudly. Ends in
        a real assertion, not skipTest(): a window manager that refuses both resizes
        must not turn a test that needs a tall (or wide) view silently green."""
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

        self.assertTrue(
            is_right_shape(achieved),
            "the window manager gave a %dx%d viewport, not the %s shape this test needs"
            % (achieved[0], achieved[1], "tall" if wanted_tall else "wide"),
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

    # -- helpers for driving real mouse/keyboard events -------------------------

    def _viewport_widget(self, timeout_ms=1000):
        """The QWidget synthetic mouse/keyboard events must be delivered to for
        NavigationStyle/SoQTQuarterAdaptor to see them, same widget TestNavigationStyles
        drives. Retries like TestRubberbandSelection._refresh_view_widgets: this call
        can be transiently dead right after _shape_view's resize."""
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            try:
                widget = self.view.graphicsView().viewport()
                widget.rect()
                return widget
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                self._pump(20)

    def _device_pixel_ratio(self, widget):
        if hasattr(widget, "devicePixelRatioF"):
            return widget.devicePixelRatioF()
        return float(widget.devicePixelRatio())

    def _to_widget_point(self, pixel):
        """Coin device pixel (origin bottom-left, as _viewport_pixels()/
        getPointOnViewport use) to a widget-local logical QPoint (origin top-left),
        the same conversion TestRubberbandSelection._to_qpoint uses."""
        widget = self._viewport_widget()
        _width, height = self._viewport_pixels()
        scale = self._device_pixel_ratio(widget)
        x = int(round(pixel[0] / scale))
        y = int(round((height - pixel[1] - 1) / scale))
        return QtCore.QPoint(x, y)

    def _post(self, widget, event_type, pos, button, buttons, modifiers=QtCore.Qt.NoModifier):
        app = QtWidgets.QApplication.instance()
        event = QtGui.QMouseEvent(
            event_type, pos, widget.mapToGlobal(pos), button, buttons, modifiers
        )
        app.sendEvent(widget, event)

    def _press_orbit(self, pixel, modifiers):
        """Move to, then press, an orbit button at `pixel` (Coin device px) and hold
        it - exactly the press that fires NavigationStyle::saveCursorPosition and,
        through setViewingMode(DRAGGING), shows the rotation-centre indicator at the
        point it just computed. Returns (widget, pos) so the caller can release."""
        widget = self._viewport_widget()
        widget.setFocus(QtCore.Qt.OtherFocusReason)
        pos = self._to_widget_point(pixel)
        no_button = QtCore.Qt.NoButton
        middle = QtCore.Qt.MiddleButton
        self._post(widget, QtCore.QEvent.MouseMove, pos, no_button, no_button, modifiers)
        self._pump(20)
        self._post(widget, QtCore.QEvent.MouseButtonPress, pos, middle, middle, modifiers)
        self._pump(50)
        return widget, pos

    def _release_orbit(self, widget, pos, modifiers):
        self._post(
            widget,
            QtCore.QEvent.MouseButtonRelease,
            pos,
            QtCore.Qt.MiddleButton,
            QtCore.Qt.NoButton,
            modifiers,
        )
        self._pump(50)

    def _drag_pan(self, start_pixel, end_pixel, steps=4):
        """Drag the middle mouse button from `start_pixel` to `end_pixel` (Coin
        device px) - press, several intermediate moves, release - the same event
        sequence TestNavigationStyles._drag uses to exercise
        FusionNavigationStyle's middle-drag pan (test_middle_drag_pans), which
        is the public API this drives NavigationStyle::panCamera through."""
        widget = self._viewport_widget()
        widget.setFocus(QtCore.Qt.OtherFocusReason)
        no_button = QtCore.Qt.NoButton
        middle = QtCore.Qt.MiddleButton

        start = self._to_widget_point(start_pixel)
        end = self._to_widget_point(end_pixel)

        self._post(widget, QtCore.QEvent.MouseMove, start, no_button, no_button)
        self._pump(20)
        self._post(widget, QtCore.QEvent.MouseButtonPress, start, middle, middle)
        self._pump(50)
        for step in range(1, steps + 1):
            point = QtCore.QPoint(
                start.x() + (end.x() - start.x()) * step // steps,
                start.y() + (end.y() - start.y()) * step // steps,
            )
            self._post(widget, QtCore.QEvent.MouseMove, point, no_button, middle)
            self._pump(20)
        self._post(widget, QtCore.QEvent.MouseButtonRelease, end, middle, no_button)
        self._pump(50)

    def _rotation_center_indicator(self):
        """The world-space rotation centre NavigationStyle::saveCursorPosition just
        set, read back via the small sphere View3DInventorViewer::showRotationCenter/
        changeRotationCenterPosition place in the scene graph while DRAGGING - an
        SoTranslation named "translation" holding rotationCenter itself, not a
        screen projection of it. Returns None if the indicator is not there."""
        from pivy import coin

        search = coin.SoSearchAction()
        search.setType(coin.SoType.fromName("SoTranslation"))
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(self.viewer.getSoRenderManager().getSceneGraph())
        paths = search.getPaths()
        for i in range(paths.getLength()):
            node = paths[i].getTail()
            if node.getName().getString() == "translation":
                v = node.translation.getValue().getValue()
                return FreeCAD.Vector(v[0], v[1], v[2])
        return None

    # -- navigation: the orbit pivot NavigationStyle::saveCursorPosition sets ---

    def test_focal_point_at_cursor_orbit_pivots_under_the_cursor_in_a_tall_view(self):
        """NavigationStyle::saveCursorPosition (FocalPointAtCursor, :1594) built its
        volume from cam->getViewVolume(ratio) with no 1/ratio scale, then intersected
        the focal plane with a plain-normalized cursor ray - pulling the pivot toward
        the view centre by the view's own aspect ratio in a tall window. Independently
        verified against getPointOnFocalPlane, which is already paired with the
        aspect-corrected getNormalizedPosition()."""
        self._shape_view(700, 1300)
        # Hidden so SoRayPickAction can't hit it and short-circuit into
        # ScenePointAtCursor before the FocalPointAtCursor branch ever runs.
        self.doc.Box.ViewObject.Visibility = False
        self._pump(100)

        params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        original_mode = params.GetInt("RotationMode", 0)
        original_nav = self.view.getNavigationType()
        self.addCleanup(params.SetInt, "RotationMode", original_mode)
        self.addCleanup(self.view.setNavigationType, original_nav)
        self.view.setNavigationType("Gui::FusionNavigationStyle")
        params.SetInt("RotationMode", 1)  # ScenePointAtCursor | FocalPointAtCursor
        self._pump(50)

        width, height = self._viewport_pixels()
        press_pixel = (int(width * 0.82), int(height * 0.12))  # off-centre, near the top
        expected = FreeCAD.Vector(self.view.getPointOnFocalPlane(*press_pixel))
        # Guards against a leftover pickable (a prior test's object, the grid) silently
        # diverting saveCursorPosition into ScenePointAtCursor instead of the branch
        # under test - hiding the box is not enough on its own if something else is there.
        self.assertIsNone(
            self.view.getObjectInfo(press_pixel),
            "something is pickable at the press point, so this would exercise "
            "ScenePointAtCursor instead of FocalPointAtCursor",
        )

        widget, pos = self._press_orbit(press_pixel, QtCore.Qt.ShiftModifier)
        try:
            actual = self._rotation_center_indicator()
            self.assertIsNotNone(actual, "the rotation-centre indicator never appeared")
            self.assertLess(
                (actual - expected).Length,
                0.1,
                "orbit pivot landed at %s but the cursor was over %s"
                % (tuple(actual), tuple(expected)),
            )
        finally:
            self._release_orbit(widget, pos, QtCore.Qt.ShiftModifier)

    def test_arrow_key_pan_moves_the_same_ratio_on_both_axes_in_a_tall_view(self):
        """SoQTQuarterAdaptor::moveCameraScreen (:661) built its volume from
        getGLWidget()->width() / getGLWidget()->height() - an integer division that
        truncated to 1 for every ordinary wide window (1 <= aspect < 2) and to 0 in
        a tall one (Coin then substitutes the camera's own square aspectRatio) - and
        applied no 1/aspect scale either way, so a pan moved too little along
        whichever axis the view's own aspect ratio expands: up/down in a tall view,
        left/right in a wide one. This test only exercises the tall-view half (the
        ratio it checks is symmetric, so a tall-view pass does not by itself prove
        the wide-view case - see the "Feel changes" section of the task report).
        Independently verified: a fixed 0.1 normalized step should move the camera
        1/aspect times further along the view's tall axis than its narrow one,
        because the mapped volume is taller in world units than it is wide."""
        achieved = self._shape_view(700, 1300)
        aspect = achieved[0] / float(achieved[1])
        widget = self._viewport_widget()
        widget.setFocus(QtCore.Qt.OtherFocusReason)
        self._pump(50)

        def press(key):
            before = FreeCAD.Vector(*self.view.getCameraNode().position.getValue().getValue())
            for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
                QtWidgets.QApplication.sendEvent(
                    widget, QtGui.QKeyEvent(kind, key, QtCore.Qt.NoModifier)
                )
            self._pump(50)
            after = FreeCAD.Vector(*self.view.getCameraNode().position.getValue().getValue())
            return (after - before).Length

        right = press(QtCore.Qt.Key_Right)
        self.assertGreater(right, 1e-6, "a right-arrow pan produced no camera movement")
        up = press(QtCore.Qt.Key_Up)

        self.assertAlmostEqual(
            up / right,
            1.0 / aspect,
            delta=0.15,
            msg=(
                "an up-arrow pan moved %.4f%% of a right-arrow pan, expected about "
                "%.1f%% (1/aspect) in a %dx%d view"
            )
            % (100.0 * up / right, 100.0 / aspect, achieved[0], achieved[1]),
        )

    def test_panning_follows_the_pointer_in_a_tall_view(self):
        """A pan drag moves the scene by what the pointer moved, whatever the view's
        shape. Pins NavigationStyle's aspect handling (lookAtPoint :604, panCamera
        :936, setupPanningPlane :965 as of the pre-refactor HEAD) before it is
        collapsed onto Gui::mappedViewVolume.

        Drives a real middle-button drag through FusionNavigationStyle - the same
        public API TestNavigationStyles.test_middle_drag_pans exercises, via
        setupPanningPlane (BUTTON3 press) and panCamera (the drag's Location2Events)
        - rather than calling either directly, so the whole event path is under
        test exactly as a user's drag would hit it. Independently verified: with a
        pure-translation orthographic pan, every point in the scene moves by the
        same screen-space delta, so the box corner's calibrated pixel before and
        after the drag must differ by exactly the drag's own pixel distance."""
        self._shape_view(700, 1300)
        point = FreeCAD.Vector(10, 6, 4)
        before = self._calibrated_pixel(point)

        original_nav = self.view.getNavigationType()
        self.addCleanup(self.view.setNavigationType, original_nav)
        self.view.setNavigationType("Gui::FusionNavigationStyle")
        self._pump(50)

        start_pixel = (300, 750)
        dx, dy = 90, -70  # Coin device px, y up
        end_pixel = (start_pixel[0] + dx, start_pixel[1] + dy)
        self._drag_pan(start_pixel, end_pixel)

        after = self._calibrated_pixel(point)
        actual_dx = after[0] - before[0]
        actual_dy = after[1] - before[1]
        error = ((actual_dx - dx) ** 2 + (actual_dy - dy) ** 2) ** 0.5
        self.assertLess(
            error,
            TOLERANCE_PX,
            "dragging the pointer by (%d, %d) px moved the scene by (%.1f, %.1f) px"
            % (dx, dy, actual_dx, actual_dy),
        )

    # -- the projection itself -------------------------------------------------

    def test_a_point_projects_where_it_is_rendered_in_a_wide_view(self):
        self._assert_projects_where_rendered((1400, 700), FreeCAD.Vector(10, 6, 4))

    def test_a_point_projects_where_it_is_rendered_in_a_tall_view(self):
        self._assert_projects_where_rendered((700, 1300), FreeCAD.Vector(10, 6, 4))

    def test_a_point_projects_where_it_is_rendered_in_a_square_view(self):
        self._assert_projects_where_rendered((1000, 1000), FreeCAD.Vector(10, 6, 4))

    def test_the_centre_of_the_view_projects_to_the_centre_in_a_tall_view(self):
        """A smoke check, not evidence for the aspect fix: SbViewVolume::scale() scales
        the volume about its own centre, so the focal point projects to the viewport's
        centre whether or not the 1/aspect correction is applied - this assertion
        passes identically with the pre-fix bug present or absent. It needs no
        calibration, which is exactly why it cannot detect an aspect-scaling defect;
        it only guards against a gross axis/sign error. See
        test_a_point_projects_where_it_is_rendered_in_a_tall_view for a test that
        actually fails on one."""
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

    def test_get_point_on_focal_plane_and_project_point_to_line_agree_in_a_tall_view(self):
        """Not evidence that either path is aspect-correct - only that the two
        screen->world paths agree with each other. getPointOnFocalPlane (:3920) and
        projectPointToLine (:4088) both build their ray from the same
        getNormalizedPosition() and the same zero-argument (unmapped) view volume, so
        the focal-plane point lies on the picking ray by construction, at any aspect,
        correct or not: this cannot fail for an aspect defect in either function.

        What it does pin down is real: if someone "fixes" one of the two functions
        onto the mapped volume without the other, the pair falls out of agreement and
        this test catches it - a genuine hazard now that this branch's mapped-volume
        convention exists alongside the original, unmapped one the two of them share.

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
