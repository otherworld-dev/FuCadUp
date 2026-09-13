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

"""GUI tests for the values the Measure tool shows while hovering.

With the tool open, hovering an item shows its own value in the 3D view, and with one
item picked, hovering a second shows the distance or angle between them. Nothing of it
goes into the document.

To run tests:
    FreeCAD -t TestMeasureHover
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtWidgets

# MeasureGui::MeasurePreview::labelName
LABEL_NODE = "MeasurePreviewLabel"
SO_SWITCH_ALL = -3


class TestMeasureHover(unittest.TestCase):
    """A 10 mm Part box with the Measure tool open on it."""

    def setUp(self):
        try:
            main_window = FreeCADGui.getMainWindow()
        except (AttributeError, RuntimeError):
            main_window = None
        if main_window is None:
            raise unittest.SkipTest("The Measure tool needs a main window")

        self.doc = FreeCAD.newDocument("TestMeasureHover")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.box = self.doc.addObject("Part::Box", "Box")
        self.doc.recompute()
        self._process_events(200)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.runCommand("Std_Measure")
        self._process_events(200)
        if FreeCADGui.Control.activeTaskDialog() is None:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None
            raise unittest.SkipTest("The Measure tool did not open in this test environment")

    def tearDown(self):
        FreeCADGui.Selection.clearPreselection()
        FreeCADGui.Selection.clearSelection()
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
        self._process_events()
        if self.doc is not None and self.doc.Name in FreeCAD.listDocuments():
            FreeCAD.closeDocument(self.doc.Name)

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _wait(self, condition, timeout_ms=2000):
        deadline = time.monotonic() + timeout_ms / 1000.0
        while not condition():
            if time.monotonic() >= deadline:
                return False
            self._process_events(20)
        return True

    @staticmethod
    def _path_is_on(path):
        from pivy import coin

        for depth in range(path.getLength() - 1):
            node = path.getNode(depth)
            if node.isOfType(coin.SoSwitch.getClassTypeId()):
                which = coin.cast(node, "SoSwitch").whichChild.getValue()
                if which not in (SO_SWITCH_ALL, path.getIndex(depth + 1)):
                    return False
        return True

    def _shown_values(self):
        """The text of every preview label on screen."""

        from pivy import coin

        viewer = FreeCADGui.getDocument(self.doc.Name).ActiveView.getViewer()
        search = coin.SoSearchAction()
        search.setName(LABEL_NODE)
        search.setInterest(coin.SoSearchAction.ALL)
        search.setSearchingAll(True)
        search.apply(viewer.getSoRenderManager().getSceneGraph())
        paths = search.getPaths()
        values = []
        for index in range(paths.getLength()):
            path = paths[index]
            if self._path_is_on(path):
                # pivy hands back an SbString, whose own iteration is broken
                value = path.getTail().string.get()
                values.append(value.getString() if hasattr(value, "getString") else str(value))
        return values

    def _hover(self, sub):
        FreeCADGui.Selection.setPreselection(self.box, sub)
        self._process_events(100)

    def _wait_for_value(self, *parts):
        def shown():
            values = self._shown_values()
            return len(values) == 1 and all(part in values[0] for part in parts)

        self.assertTrue(
            self._wait(shown), f"expected a value with {parts}, saw {self._shown_values()}"
        )

    # -- tests -----------------------------------------------------------

    def test_hovering_an_edge_shows_its_length(self):
        self._hover("Edge1")
        self._wait_for_value("10", "mm")

    def test_hovering_a_face_shows_its_area(self):
        self._hover("Face1")
        self._wait_for_value("100", "mm")

    def test_after_one_pick_hovering_a_second_shows_the_distance(self):
        FreeCADGui.Selection.addSelection(self.doc.Name, self.box.Name, "Face1")
        self._process_events(150)
        # Face1 is the box's side at x = 0 and Face2 the one at x = 10.
        self._hover("Face2")
        self._wait_for_value("10", "mm")

    def test_after_one_pick_hovering_a_face_at_an_angle_shows_the_angle(self):
        FreeCADGui.Selection.addSelection(self.doc.Name, self.box.Name, "Face1")
        self._process_events(150)
        # Face3 is the side at y = 0, square to Face1.
        self._hover("Face3")
        self._wait_for_value("90", "°")

    def test_moving_off_the_part_clears_the_value(self):
        self._hover("Edge1")
        self._wait_for_value("10")
        FreeCADGui.Selection.clearPreselection()
        self.assertTrue(self._wait(lambda: self._shown_values() == []), "the value stayed on screen")

    def test_hovering_changes_nothing_in_the_document(self):
        objects = len(self.doc.Objects)
        undo = self.doc.UndoCount
        for sub in ("Edge1", "Face1", "Edge5", "Face3"):
            self._hover(sub)
            self._process_events(100)
        self.assertEqual(len(self.doc.Objects), objects)
        self.assertEqual(self.doc.UndoCount, undo)

    def test_closing_the_tool_removes_the_value(self):
        self._hover("Edge1")
        self._wait_for_value("10")
        FreeCADGui.Control.closeDialog()
        self._process_events(150)
        self.assertEqual(self._shown_values(), [])
