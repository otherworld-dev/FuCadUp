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

"""GUI regression tests for the mouse mappings of 3D navigation styles.

To run tests:
    FreeCAD -t TestNavigationStyles
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

FUSION_STYLE = "Gui::FusionNavigationStyle"

NO_BUTTON = QtCore.Qt.NoButton
LEFT_BUTTON = QtCore.Qt.LeftButton
MIDDLE_BUTTON = QtCore.Qt.MiddleButton
RIGHT_BUTTON = QtCore.Qt.RightButton
NO_MODIFIER = QtCore.Qt.NoModifier
CONTROL_MODIFIER = QtCore.Qt.ControlModifier
SHIFT_MODIFIER = QtCore.Qt.ShiftModifier
OTHER_FOCUS_REASON = QtCore.Qt.OtherFocusReason
MOUSE_MOVE = QtCore.QEvent.MouseMove
MOUSE_PRESS = QtCore.QEvent.MouseButtonPress
MOUSE_RELEASE = QtCore.QEvent.MouseButtonRelease

# Coin stores the camera in single precision, so allow for float noise well below
# anything a real pan, orbit or zoom produces.
ROTATION_TOLERANCE = 1e-4
DISTANCE_TOLERANCE = 1e-3


class ViewerTestCase(unittest.TestCase):
    """Shared set-up: one document with an orthographic, widget-backed 3D view."""

    def setUp(self):
        self.doc = FreeCAD.newDocument("TestNavigationStyles")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)

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
        self._refresh_view()

    def tearDown(self):
        # A context menu holds the mouse and the keyboard until it is dismissed,
        # so one left open by a test would swallow the events of the next.
        self._close_popups()
        FreeCADGui.Selection.clearSelection()
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _refresh_view(self):
        self.view.viewIsometric()
        self.view.fitAll()
        self._refresh_view_widgets()
        self.viewport.setFocus(OTHER_FOCUS_REASON)
        self._process_events()
        self._process_events()
        self._wait_for_camera_to_settle()

    def _wait_for_camera_to_settle(self, timeout_ms=3000):
        """Let the animated view change finish before taking a camera snapshot."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        previous = self._camera_state()
        while True:
            self._process_events(100)
            current = self._camera_state()
            if self._same_camera_state(previous, current):
                return
            if time.monotonic() >= deadline:
                self.fail("The camera kept moving after the view was reset")
            previous = current

    @staticmethod
    def _same_camera_state(first, second):
        return (
            (first[0] - second[0]).Length <= DISTANCE_TOLERANCE
            and first[1].isSame(second[1], ROTATION_TOLERANCE)
            and abs(first[2] - second[2]) <= DISTANCE_TOLERANCE
        )

    def _close_popups(self, attempts=5):
        app = QtGui.QApplication.instance()
        for _ in range(attempts):
            popup = app.activePopupWidget()
            if popup is None:
                return
            popup.close()
            self._process_events(10)

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

    def _send_mouse_event(self, event_type, pos, button, buttons, modifiers):
        self._refresh_view_widgets()
        app = QtGui.QApplication.instance()
        global_pos = self.viewport.mapToGlobal(pos)
        QtGui.QCursor.setPos(global_pos)
        event = QtGui.QMouseEvent(
            event_type,
            pos,
            global_pos,
            button,
            buttons,
            modifiers,
        )
        app.sendEvent(self.viewport, event)

    def _drag(self, button, modifiers=NO_MODIFIER, steps=4):
        """Press ``button`` near the centre of the view and drag it diagonally."""

        start = self.viewport.rect().center() + QtCore.QPoint(-60, 30)
        end = start + QtCore.QPoint(120, -40)

        self._send_mouse_event(MOUSE_MOVE, start, NO_BUTTON, NO_BUTTON, modifiers)
        self._process_events(10)
        self._send_mouse_event(MOUSE_PRESS, start, button, button, modifiers)
        self._process_events(10)
        for step in range(1, steps + 1):
            point = QtCore.QPoint(
                start.x() + (end.x() - start.x()) * step // steps,
                start.y() + (end.y() - start.y()) * step // steps,
            )
            self._send_mouse_event(MOUSE_MOVE, point, NO_BUTTON, button, modifiers)
            self._process_events(10)
        self._send_mouse_event(MOUSE_RELEASE, end, button, NO_BUTTON, modifiers)
        self._process_events()

    def _click(self, button, modifiers=NO_MODIFIER):
        """Press and release ``button`` in the middle of the view without moving."""

        where = self.viewport.rect().center()
        self._send_mouse_event(MOUSE_PRESS, where, button, button, modifiers)
        self._process_events(10)
        self._send_mouse_event(MOUSE_RELEASE, where, button, NO_BUTTON, modifiers)
        self._process_events()

    def _camera_state(self):
        camera = self.view.getCameraNode()
        position = FreeCAD.Vector(*camera.position.getValue().getValue())
        orientation = self.view.getCameraOrientation()
        height = camera.height.getValue()
        return position, orientation, height

    def assertCameraMoved(self, before, after):
        self.assertGreater(
            (after[0] - before[0]).Length,
            DISTANCE_TOLERANCE,
            "Expected the camera position to move",
        )

    def assertCameraStayedPut(self, before, after):
        self.assertLessEqual(
            (after[0] - before[0]).Length,
            DISTANCE_TOLERANCE,
            "Expected the camera position to stay where it was",
        )

    def assertCameraTurned(self, before, after):
        self.assertFalse(
            before[1].isSame(after[1], ROTATION_TOLERANCE),
            "Expected the camera orientation to change",
        )

    def assertCameraKeptOrientation(self, before, after):
        self.assertTrue(
            before[1].isSame(after[1], ROTATION_TOLERANCE),
            "Expected the camera orientation to stay the same",
        )

    def assertCameraZoomed(self, before, after):
        self.assertGreater(
            abs(after[2] - before[2]),
            DISTANCE_TOLERANCE,
            "Expected the orthographic camera height to change",
        )

    def assertCameraKeptZoom(self, before, after):
        self.assertLessEqual(
            abs(after[2] - before[2]),
            DISTANCE_TOLERANCE,
            "Expected the orthographic camera height to stay the same",
        )

    def assertNoPopup(self, message):
        self.assertIsNone(QtGui.QApplication.instance().activePopupWidget(), message)


class TestFusionNavigationStyle(ViewerTestCase):
    """The Fusion style copies the default mouse preset of Autodesk Fusion:
    middle button pans, Shift + middle orbits, Ctrl + Shift + middle zooms.

    A mouse without a usable middle button would leave the view stuck, so the
    right button carries the same three moves: on its own it orbits, with Shift
    it pans and with Ctrl it zooms. A right click that does not drag still opens
    the context menu, which is the only thing the right button used to do."""

    def _use_fusion(self):
        self.view.setNavigationType(FUSION_STYLE)
        self.assertEqual(self.view.getNavigationType(), FUSION_STYLE)
        self._refresh_view()

    def test_fusion_style_is_registered(self):
        self.assertIn(FUSION_STYLE, self.view.listNavigationTypes())

    def test_middle_drag_pans(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(MIDDLE_BUTTON)

        after = self._camera_state()
        self.assertCameraMoved(before, after)
        self.assertCameraKeptOrientation(before, after)
        self.assertCameraKeptZoom(before, after)

    def test_shift_middle_drag_orbits(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(MIDDLE_BUTTON, SHIFT_MODIFIER)

        after = self._camera_state()
        self.assertCameraTurned(before, after)
        self.assertCameraKeptZoom(before, after)

    def test_ctrl_shift_middle_drag_zooms(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(MIDDLE_BUTTON, CONTROL_MODIFIER | SHIFT_MODIFIER)

        after = self._camera_state()
        self.assertCameraZoomed(before, after)
        self.assertCameraKeptOrientation(before, after)

    def test_right_drag_orbits(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(RIGHT_BUTTON)

        after = self._camera_state()
        self.assertCameraTurned(before, after)
        self.assertCameraKeptZoom(before, after)
        self.assertNoPopup("A right drag must orbit rather than open the context menu")

    def test_shift_right_drag_pans(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(RIGHT_BUTTON, SHIFT_MODIFIER)

        after = self._camera_state()
        self.assertCameraMoved(before, after)
        self.assertCameraKeptOrientation(before, after)
        self.assertCameraKeptZoom(before, after)
        self.assertNoPopup("A Shift + right drag must pan rather than open the context menu")

    def test_ctrl_right_drag_zooms(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(RIGHT_BUTTON, CONTROL_MODIFIER)

        after = self._camera_state()
        self.assertCameraZoomed(before, after)
        self.assertCameraKeptOrientation(before, after)
        self.assertNoPopup("A Ctrl + right drag must zoom rather than open the context menu")

    def test_right_click_opens_the_context_menu(self):
        self._use_fusion()
        before = self._camera_state()

        self._click(RIGHT_BUTTON)

        after = self._camera_state()
        self.assertIsNotNone(
            QtGui.QApplication.instance().activePopupWidget(),
            "A right click that does not drag must still open the context menu",
        )
        self.assertCameraStayedPut(before, after)
        self.assertCameraKeptOrientation(before, after)
        self.assertCameraKeptZoom(before, after)

    def test_left_drag_leaves_camera_alone(self):
        self._use_fusion()
        before = self._camera_state()

        self._drag(LEFT_BUTTON)

        after = self._camera_state()
        self.assertCameraStayedPut(before, after)
        self.assertCameraKeptOrientation(before, after)
        self.assertCameraKeptZoom(before, after)


class TestNavigationIndicator(ViewerTestCase):
    """The status-bar mouse indicator (Tux) must offer every registered style."""

    def _indicator_actions(self):
        try:
            import NavigationIndicatorGui
        except ImportError as exc:
            raise unittest.SkipTest("The Tux navigation indicator is unavailable") from exc
        return [
            action
            for action in NavigationIndicatorGui.gStyle.actions()
            if action.data() != "Undefined  "
        ]

    def test_indicator_offers_every_registered_style(self):
        offered = {action.data() for action in self._indicator_actions()}
        for style in self.view.listNavigationTypes():
            self.view.setNavigationType(style)
            if self.view.getNavigationType() != style:
                continue  # abstract helper types are listed but cannot be selected
            with self.subTest(style=style):
                self.assertIn(style, offered)

    def test_indicator_styles_have_light_and_dark_icons(self):
        prefix = "Indicator_Navigation"
        for action in self._indicator_actions():
            with self.subTest(style=action.data()):
                name = action.objectName()
                self.assertTrue(name.startswith(prefix), name)
                stem = ":/icons/Navigation" + name[len(prefix) :]
                for variant in ("_light.svg", "_dark.svg"):
                    self.assertTrue(
                        QtCore.QFile.exists(stem + variant),
                        "Missing icon resource " + stem + variant,
                    )
                self.assertFalse(
                    action.icon().pixmap(16, 16).isNull(),
                    "The indicator icon for " + action.data() + " did not render",
                )
