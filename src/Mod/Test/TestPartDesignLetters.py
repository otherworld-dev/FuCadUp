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

"""GUI regression tests for the PartDesign single-letter modelling commands.

E, H, F and Q are bound to PartDesign_Extrude, PartDesign_Hole, PartDesign_Fillet
and PartDesign_PressPull with a shortcut priority that outranks the Sketcher's own
letters, so E used to mean Extrude rather than Equal even from inside a sketch.
The modelling commands therefore have to report themselves inactive for as long as
a task dialog owns the panel, and become available again once it closes.

Press/Pull also has to say something when there is no solid to push or pull,
instead of quietly building a face feature that stands on nothing.

To run tests:
    FreeCAD -t TestPartDesignLetters
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

# The four commands the fork binds to E, H, F and Q.
LETTER_COMMANDS = (
    "PartDesign_Extrude",
    "PartDesign_Hole",
    "PartDesign_Fillet",
    "PartDesign_PressPull",
)


class TestPartDesignLetters(unittest.TestCase):
    """The modelling letters must yield to the sketch that owns the task panel."""

    def setUp(self):
        FreeCADGui.activateWorkbench("PartDesignWorkbench")

        self.doc = FreeCAD.newDocument("TestPartDesignLetters")
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

        self.sketch = self.body.newObject("Sketcher::SketchObject", "Sketch")
        self.sketch.AttachmentSupport = [(plane, "")]
        self.sketch.MapMode = "FlatFace"
        self.doc.recompute()

        self._process_events()

    def tearDown(self):
        gui_doc = FreeCADGui.getDocument(self.doc.Name) if self.doc is not None else None
        if gui_doc is not None and gui_doc.getInEdit() is not None:
            gui_doc.resetEdit()
        if FreeCADGui.Control.activeTaskDialog() is not None:
            FreeCADGui.Control.closeDialog()
        self._process_events()

        FreeCADGui.Selection.clearSelection()
        self._discard_document()

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
        app = QtGui.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _wait_until(self, predicate, timeout_ms=2000):
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            if predicate():
                return True
            if time.monotonic() >= deadline:
                return False
            self._process_events(20)

    def _command_states(self):
        return {name: FreeCADGui.Command.get(name).isActive() for name in LETTER_COMMANDS}

    def _enter_sketch_edit(self):
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        self.assertTrue(
            self._wait_until(lambda: FreeCADGui.ActiveDocument.getInEdit() is not None),
            "Expected the sketch to enter edit mode",
        )
        self.assertTrue(
            self._wait_until(lambda: FreeCADGui.Control.activeTaskDialog() is not None),
            "Expected the Sketcher task dialog to own the task panel",
        )

    def _leave_sketch_edit(self):
        FreeCADGui.ActiveDocument.resetEdit()
        self.assertTrue(
            self._wait_until(lambda: FreeCADGui.Control.activeTaskDialog() is None),
            "Expected resetEdit() to close the Sketcher task dialog",
        )

    class _ModalCloser:
        """Close whatever modal widget appears, so a warning cannot hang the test.

        A QMessageBox spins its own event loop, so the only way back out is a timer
        that keeps firing inside that loop.
        """

        def __init__(self, interval_ms=20):
            self.closed = []
            self.timer = QtCore.QTimer()
            self.timer.setInterval(interval_ms)
            self.timer.timeout.connect(self._close_one)

        def _close_one(self):
            modal = QtGui.QApplication.activeModalWidget()
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

    def test_letters_are_inactive_while_a_sketch_is_edited(self):
        self._enter_sketch_edit()

        for name, active in self._command_states().items():
            self.assertFalse(active, f"{name} must not fire while a sketch is being edited")

    def test_letters_are_active_again_after_reset_edit(self):
        self._enter_sketch_edit()
        self._leave_sketch_edit()

        for name, active in self._command_states().items():
            self.assertTrue(active, f"{name} must work again once the sketch is closed")

    def test_letters_are_active_with_a_plain_document(self):
        for name, active in self._command_states().items():
            self.assertTrue(active, f"{name} must be available with a document open")

    def test_press_pull_with_nothing_to_work_on_warns_and_creates_nothing(self):
        """The body holds no solid yet, so Q has no face to push or pull.

        It used to build the face feature on a null tip, which meant the command
        returned without a word and without anything to show for the key press.
        """

        FreeCADGui.Selection.clearSelection()
        before = [obj.Name for obj in self.doc.Objects]

        with self._ModalCloser() as closer:
            FreeCADGui.runCommand("PartDesign_PressPull")
            self._process_events(100)

        self.assertEqual(
            [obj.Name for obj in self.doc.Objects],
            before,
            "Press/Pull must not create a feature when there is nothing to work on",
        )
        self.assertIn(
            "QMessageBox",
            closer.closed,
            "Press/Pull must say why it did nothing instead of returning silently",
        )
