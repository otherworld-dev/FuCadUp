# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI tests for FuCadUp's view cube (Gui::SoViewCube) and the cube style setting.

To run tests:
    FuCadUp -t TestViewCube
"""

import time
import unittest

import FreeCAD
import FreeCADGui

NAVICUBE_PARAMS = "User parameter:BaseApp/Preferences/NaviCube"


def process_events(wait_ms=30):
    from PySide import QtWidgets

    FreeCADGui.updateGui()
    QtWidgets.QApplication.instance().processEvents()
    time.sleep(wait_ms / 1000.0)
    QtWidgets.QApplication.instance().processEvents()


class ViewCubeTestBase(unittest.TestCase):
    """A fresh document and 3D view, with the cube style put back afterwards."""

    def setUp(self):
        self.group = FreeCAD.ParamGet(NAVICUBE_PARAMS)
        self._had_style = "CubeStyle" in self.group.GetInts()
        self._style = self.group.GetInt("CubeStyle", 0)
        self.doc = FreeCAD.newDocument("TestViewCube")
        self.view = self._active_view()
        self.viewer = self.view.getViewer()
        process_events()

    def tearDown(self):
        if self._had_style:
            self.group.SetInt("CubeStyle", self._style)
        else:
            self.group.RemInt("CubeStyle")
        FreeCAD.closeDocument(self.doc.Name)

    def _active_view(self, timeout=2.0):
        deadline = time.monotonic() + timeout
        while True:
            view = FreeCADGui.getDocument(self.doc.Name).ActiveView
            if view is not None:
                return view
            if time.monotonic() >= deadline:
                self.fail("no 3D view appeared for the test document")
            process_events(20)

    def cube_node(self):
        root = self.viewer.getNaviCubeNode()
        self.assertIsNotNone(root, "the viewer has no navigation cube")
        self.assertEqual(
            root.getNumChildren(), 2, "the cube root should hold a callback and the cube node"
        )
        return root.getChild(1)

    def cube_type(self):
        return self.cube_node().getTypeId().getName().getString()


class TestCubeStyle(ViewCubeTestBase):
    def test_a_fresh_install_uses_the_fucadup_cube(self):
        self.group.RemInt("CubeStyle")
        process_events()
        self.assertEqual(self.cube_type(), "SoViewCube")

    def test_the_style_swaps_live(self):
        self.group.SetInt("CubeStyle", 1)
        process_events()
        self.assertEqual(self.cube_type(), "SoNaviCube", "Classic did not bring the old cube back")
        self.group.SetInt("CubeStyle", 0)
        process_events()
        self.assertEqual(self.cube_type(), "SoViewCube", "FuCadUp did not come back")

    def test_the_new_cube_gets_the_controllers_values(self):
        self.group.SetInt("CubeStyle", 0)
        self.view.viewIsometric()
        for _ in range(20):
            process_events()
        cube = self.cube_node()
        self.assertGreater(
            cube.viewportRect.getValue()[2], 0.0, "the controller never gave the cube a viewport"
        )
        # InactiveOpacity differs between profiles, so only check the cube is drawn at all.
        self.assertGreater(cube.opacity.getValue(), 0.0)

    def test_a_swapped_in_cube_is_drawn_straight_away(self):
        """The node swapped in gets the controller's viewport and state without a mouse move."""
        self.group.SetInt("CubeStyle", 1)
        process_events()
        self.group.SetInt("CubeStyle", 0)
        for _ in range(5):
            process_events()
        self.assertEqual(self.cube_type(), "SoViewCube")
        self.assertGreater(self.cube_node().viewportRect.getValue()[2], 0.0)
