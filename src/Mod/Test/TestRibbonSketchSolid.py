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

"""GUI regression tests for the SOLID tab while a sketch is being edited.

Fusion keeps its SOLID tab usable from inside a sketch: clicking Extrude there
finishes the sketch and extrudes it. The SKETCH context tab of the workspace
definition names the command that finishes its mode, so while it is pushed the
buttons of the ordinary tabs stand in for their commands: a click runs that
finish command first and then the command itself.

The commands that take a profile start with the finished sketch selected, so
Extrude goes straight to extruding it; the others start with nothing selected.
The stand-ins carry no shortcut, so E, H, F and Q keep meaning what the sketch
makes them mean (TestPartDesignLetters guards the commands themselves).

To run tests:
    FreeCAD -t TestRibbonSketchSolid
"""

import time
import unittest

import FreeCAD
import FreeCADGui
import Part
from PySide import QtCore, QtWidgets

MAIN_WINDOW_PARAMS = "User parameter:BaseApp/Preferences/MainWindow"

# Tab ids of src/Gui/Ribbon/Workspaces/Design.json, shown untranslated in English.
SOLID_TAB = "SOLID"
SKETCH_TAB = "SKETCH"

# Object names RibbonButton::setPrimary() gives a command button.
RIBBON_BUTTON_NAMES = ("RibbonButton", "RibbonPrimaryButton")


class TestRibbonSketchSolid(unittest.TestCase):
    """The SOLID tab has to work from inside a sketch, the way Fusion's does."""

    def setUp(self):
        self.doc = None

        if not FreeCAD.ParamGet(MAIN_WINDOW_PARAMS).GetBool("UseRibbon", True):
            raise unittest.SkipTest("The ribbon shell is switched off in this build")

        self.window = FreeCADGui.getMainWindow()
        if self.window is None:
            raise unittest.SkipTest("No main window in this test environment")

        self.tab_bar = self.window.findChild(QtWidgets.QTabBar, "RibbonTabBar")
        if self.tab_bar is None:
            raise unittest.SkipTest("The ribbon shell is not installed in this test environment")

        FreeCADGui.activateWorkbench("PartDesignWorkbench")

        self.doc = FreeCAD.newDocument("TestRibbonSketchSolid")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)

        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.doc.recompute()

        view = FreeCADGui.activeView()
        if view is None:
            self._discard_document()
            raise unittest.SkipTest("No 3D view in this test environment")
        view.setActiveObject("pdbody", self.body)

        plane = self._origin_plane("XY_Plane")
        if plane is None:
            self._discard_document()
            self.fail("The body's origin has no XY_Plane")

        # A closed rectangle clear of the sketch's vertical axis, so that both an
        # extrusion and a revolution about that axis have a valid profile.
        self.sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = [(plane, "")]
        self.sketch.MapMode = "FlatFace"
        corners = [
            FreeCAD.Vector(10, 0, 0),
            FreeCAD.Vector(20, 0, 0),
            FreeCAD.Vector(20, 10, 0),
            FreeCAD.Vector(10, 10, 0),
        ]
        for start, end in zip(corners, corners[1:] + corners[:1]):
            self.sketch.addGeometry(Part.LineSegment(start, end), False)
        self.doc.recompute()

        self._process_events()

    def tearDown(self):
        if self.doc is not None:
            gui_doc = FreeCADGui.getDocument(self.doc.Name)
            if gui_doc is not None and gui_doc.getInEdit() is not None:
                gui_doc.resetEdit()
        if FreeCADGui.Control.activeTaskDialog() is not None:
            FreeCADGui.Control.closeDialog()
        self._process_events()

        FreeCADGui.Selection.clearSelection()
        self._discard_document()
        self._process_events()

    # -- helpers ---------------------------------------------------------

    def _discard_document(self):
        """Close the test document, if it is still open.

        setUp has to call this itself on every path that gives up, since tearDown
        never runs when setUp raises.
        """

        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None

    def _origin_plane(self, name):
        for feature in self.body.Origin.OriginFeatures:
            if feature.Name.startswith(name):
                return feature
        return None

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _wait_until(self, predicate, timeout_ms=3000):
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            if predicate():
                return True
            if time.monotonic() >= deadline:
                return False
            self._process_events(20)

    def _tab_index(self, title):
        for index in range(self.tab_bar.count()):
            if self.tab_bar.tabText(index) == title:
                return index
        return -1

    def _sketch_in_edit(self):
        in_edit = FreeCADGui.ActiveDocument.getInEdit()
        return in_edit is not None and in_edit.Object == self.sketch

    def _enter_sketch_edit(self):
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        self.assertTrue(
            self._wait_until(self._sketch_in_edit), "Expected the sketch to enter edit mode"
        )
        self.assertTrue(
            self._wait_until(lambda: self._tab_index(SKETCH_TAB) >= 0),
            "Expected editing the sketch to push the SKETCH context tab",
        )

    def _show_solid_tab(self):
        index = self._tab_index(SOLID_TAB)
        self.assertGreaterEqual(index, 0, "Expected a SOLID tab on the ribbon")
        self.tab_bar.setCurrentIndex(index)
        self._process_events()

    def _visible_button(self, command, timeout_ms=3000):
        """The ribbon button on screen that runs ``command``, or None."""

        def find():
            for button in self.window.findChildren(QtWidgets.QToolButton):
                if button.objectName() not in RIBBON_BUTTON_NAMES:
                    continue
                if button.property("command") == command and button.isVisible():
                    return button
            return None

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            button = find()
            if button is not None or time.monotonic() >= deadline:
                return button
            self._process_events(20)

    def _solid_button_while_sketching(self, command):
        self._enter_sketch_edit()
        self._show_solid_tab()

        button = self._visible_button(command)
        self.assertIsNotNone(button, "Expected a SOLID tab button for " + command)
        return button

    def _features(self, type_id):
        return [obj for obj in self.doc.Objects if obj.isDerivedFrom(type_id)]

    class _ModalCloser:
        """Close whatever modal widget appears, so a question cannot hang the test.

        A QMessageBox spins its own event loop, so the only way back out is a timer
        that keeps firing inside that loop.
        """

        def __init__(self, interval_ms=20):
            self.closed = []
            self.timer = QtCore.QTimer()
            self.timer.setInterval(interval_ms)
            self.timer.timeout.connect(self._close_one)

        def _close_one(self):
            modal = QtWidgets.QApplication.activeModalWidget()
            if modal is not None:
                self.closed.append(type(modal).__name__)
                modal.close()

        def __enter__(self):
            self.timer.start()
            return self

        def __exit__(self, *exc):
            self.timer.stop()
            return False

    # -- tests -----------------------------------------------------------

    def test_extrude_button_is_live_while_sketching(self):
        """The command stands down for the sketch; its SOLID button must not."""

        button = self._solid_button_while_sketching("PartDesign_Extrude")
        self.assertTrue(button.isEnabled(), "Extrude must be clickable from inside a sketch")

    def test_solid_buttons_leave_the_letters_to_the_sketch(self):
        """A stand-in with a shortcut would take E back from the sketch's Equal."""

        button = self._solid_button_while_sketching("PartDesign_Extrude")
        self.assertTrue(
            button.defaultAction().shortcut().isEmpty(),
            "A SOLID button must not answer a key while a sketch is being edited",
        )

    def test_extrude_while_sketching_extrudes_that_sketch(self):
        button = self._solid_button_while_sketching("PartDesign_Extrude")
        button.click()

        self.assertTrue(
            self._wait_until(lambda: not self._sketch_in_edit()),
            "Clicking Extrude must finish the sketch",
        )
        self.assertTrue(
            self._wait_until(lambda: len(self._features("PartDesign::Pad")) == 1),
            "Expected Extrude to start on the sketch that was just finished, "
            "without asking for a profile",
        )
        self.assertEqual(self._features("PartDesign::Pad")[0].Profile[0], self.sketch)

    def test_revolve_while_sketching_asks_nothing(self):
        """The sketch's task dialog must be gone before Revolve runs, or Revolve asks to close it."""

        button = self._solid_button_while_sketching("PartDesign_Revolve")
        with self._ModalCloser() as closer:
            button.click()
            revolved = self._wait_until(
                lambda: len(self._features("PartDesign::Revolution")) == 1
            )

        self.assertEqual(closer.closed, [], "Revolve must not ask anything on its way in")
        self.assertTrue(revolved, "Expected Revolve to start on the sketch that was just finished")
        self.assertEqual(self._features("PartDesign::Revolution")[0].Profile[0], self.sketch)

    def test_other_commands_start_with_nothing_selected(self):
        """Only the profile commands are handed the sketch; a datum plane is not attached to it."""

        button = self._solid_button_while_sketching("PartDesign_Plane")
        button.click()

        self.assertTrue(
            self._wait_until(lambda: not self._sketch_in_edit()),
            "Clicking Offset Plane must finish the sketch",
        )
        self.assertTrue(
            self._wait_until(lambda: len(self._features("PartDesign::Plane")) == 1),
            "Expected Offset Plane to create a datum plane",
        )
        support = self._features("PartDesign::Plane")[0].AttachmentSupport
        self.assertNotIn(
            self.sketch,
            [reference[0] for reference in support],
            "The finished sketch must only be handed to the commands that take a profile",
        )
