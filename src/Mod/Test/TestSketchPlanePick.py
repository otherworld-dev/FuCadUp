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

"""GUI regression tests for picking a sketch plane straight from the 3D view.

Create Sketch with nothing selected used to build the sketch first and then open
the attachment editor, so the plane had to be clicked and then confirmed. It now
waits for one click on a planar face, datum plane or origin plane and opens the
sketch on it, the way Fusion does. The attachment editor stays reachable through
the "Always open attachment dialog" preference (and Shift).

To run tests:
    FreeCAD -t TestSketchPlanePick
"""

import time
import unittest

import FreeCAD
import FreeCADGui
import Part
from PySide import QtCore, QtGui

PARTDESIGN_PARAMS = "User parameter:BaseApp/Preferences/Mod/PartDesign"
ATTACHMENT_PREF = "NewSketchUseAttachmentDialog"

PICKER_WIDGET = "PartDesignGui__TaskSketchPlanePick"
ATTACHER_WIDGET = "PartGui__TaskAttacher"


class TestSketchPlanePick(unittest.TestCase):
    """Create Sketch must open on the first planar thing that is clicked."""

    def setUp(self):
        FreeCADGui.activateWorkbench("PartDesignWorkbench")

        self.params = FreeCAD.ParamGet(PARTDESIGN_PARAMS)
        self.saved_attachment_pref = self.params.GetBool(ATTACHMENT_PREF, False)
        self.params.SetBool(ATTACHMENT_PREF, False)

        self.doc = FreeCAD.newDocument("TestSketchPlanePick")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        self.body = None

        if FreeCADGui.activeView() is None:
            self._discard_document()
            raise unittest.SkipTest("No 3D view in this test environment")

        FreeCADGui.Selection.clearSelection()
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
        self.params.SetBool(ATTACHMENT_PREF, self.saved_attachment_pref)

    # -- helpers ---------------------------------------------------------

    def _discard_document(self):
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)
            self.doc = None

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtGui.QApplication.instance()
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

    def _make_body(self):
        self.body = self.doc.addObject("PartDesign::Body", "Body")
        self.doc.recompute()
        FreeCADGui.activeView().setActiveObject("pdbody", self.body)
        self._process_events()
        return self.body

    def _add_cylinder(self):
        """A solid with one curved face and two flat ones, so the gate can be tested."""

        cylinder = self.body.newObject("PartDesign::AdditiveCylinder", "Cylinder")
        cylinder.Radius = 10
        cylinder.Height = 20
        self.doc.recompute()
        self._process_events()
        return cylinder

    @staticmethod
    def _face_names(feature, planar):
        names = []
        for index, face in enumerate(feature.Shape.Faces):
            if isinstance(face.Surface, Part.Plane) == planar:
                names.append("Face%d" % (index + 1))
        return names

    def _origin_plane(self, name):
        for feature in self.body.Origin.OriginFeatures:
            if feature.Name.startswith(name):
                return feature
        self.fail("The body's origin has no %s" % name)

    def _origin_plane_subname(self, plane):
        return "%s.%s." % (self.body.Origin.Name, plane.Name)

    def _origin_shown(self):
        """The planes are hidden through their coordinate system, not one by one."""
        return self.body.Origin.ViewObject.Visibility

    def _sketches(self):
        return [obj for obj in self.doc.Objects if obj.TypeId == "Sketcher::SketchObject"]

    def _bodies(self):
        return [obj for obj in self.doc.Objects if obj.TypeId == "PartDesign::Body"]

    @staticmethod
    def _task_widget(name):
        return FreeCADGui.getMainWindow().findChild(QtGui.QWidget, name)

    def _run_create_sketch(self):
        FreeCADGui.runCommand("PartDesign_NewSketch", 0)
        self._process_events()

    def _start_pick(self):
        self._run_create_sketch()
        self.assertTrue(
            self._wait_until(lambda: self._task_widget(PICKER_WIDGET) is not None),
            "Expected the plane picker to own the task panel",
        )

    def _send_escape_to_view(self):
        view = FreeCADGui.getDocument(self.doc.Name).ActiveView
        viewport = view.graphicsView().viewport()
        app = QtGui.QApplication.instance()
        for event_type in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
            event = QtGui.QKeyEvent(event_type, QtCore.Qt.Key_Escape, QtCore.Qt.NoModifier)
            app.sendEvent(viewport, event)
        self._process_events()

    def _assert_sketch_opened_on(self, support_object, support_sub):
        self.assertTrue(
            self._wait_until(lambda: len(self._sketches()) == 1),
            "Expected exactly one sketch after the pick",
        )
        sketch = self._sketches()[0]
        self.assertEqual(sketch.MapMode, "FlatFace")
        (obj, subs), = sketch.AttachmentSupport
        self.assertEqual(len(subs), 1, "One reference is all a FlatFace sketch needs")
        if support_sub:
            self.assertEqual(obj.Name, support_object.Name)
            self.assertEqual(subs[0], support_sub)
        else:
            # An origin plane picked in the 3D view is stored through its coordinate
            # system, as "Origin" + "XZ_Plane.", so compare what the reference resolves to.
            resolved = obj.getSubObject(subs[0], 1) if subs[0] else obj
            self.assertEqual(resolved.Name, support_object.Name)
        self.assertTrue(
            self._wait_until(
                lambda: FreeCADGui.ActiveDocument.getInEdit() is not None
                and FreeCADGui.ActiveDocument.getInEdit().Object.Name == sketch.Name
            ),
            "Expected the new sketch to be in edit mode",
        )
        self.assertIsNone(self._task_widget(PICKER_WIDGET), "The picker should have closed")
        return sketch

    # -- tests -----------------------------------------------------------

    def test_create_sketch_without_selection_waits_for_a_pick(self):
        self._make_body()
        self.assertFalse(self._origin_shown(), "A fresh body keeps its origin hidden")

        self._start_pick()

        self.assertIsNone(
            self._task_widget(ATTACHER_WIDGET), "The attachment editor must not open"
        )
        self.assertEqual(self._sketches(), [], "No sketch may exist before the pick")
        self.assertTrue(self._origin_shown(), "The origin planes must be shown while picking")

    def test_picking_an_origin_plane_opens_the_sketch_on_it(self):
        self._make_body()
        xz_plane = self._origin_plane("XZ_Plane")
        self._start_pick()

        FreeCADGui.Selection.addSelection(
            self.doc.Name, self.body.Name, self._origin_plane_subname(xz_plane)
        )

        self._assert_sketch_opened_on(xz_plane, "")
        self.assertFalse(self._origin_shown(), "The origin planes must be hidden again")

    def test_picking_a_flat_face_opens_the_sketch_on_it(self):
        self._make_body()
        cylinder = self._add_cylinder()
        flat = self._face_names(cylinder, planar=True)[0]
        self._start_pick()

        FreeCADGui.Selection.addSelection(self.doc.Name, cylinder.Name, flat)

        self._assert_sketch_opened_on(cylinder, flat)

    def test_a_curved_face_cannot_be_picked(self):
        self._make_body()
        cylinder = self._add_cylinder()
        curved = self._face_names(cylinder, planar=False)[0]
        self._start_pick()

        FreeCADGui.Selection.addSelection(self.doc.Name, cylinder.Name, curved)
        self._process_events(200)

        self.assertEqual(
            FreeCADGui.Selection.getSelectionEx(), [], "The gate must refuse a curved face"
        )
        self.assertEqual(self._sketches(), [], "No sketch may be created on a curved face")
        self.assertIsNotNone(self._task_widget(PICKER_WIDGET), "The picker must stay open")

    def test_a_sketch_cannot_be_picked_as_the_plane(self):
        self._make_body()
        xy_plane = self._origin_plane("XY_Plane")
        existing = self.body.newObject("Sketcher::SketchObject", "Existing")
        existing.AttachmentSupport = [(xy_plane, "")]
        existing.MapMode = "FlatFace"
        self.doc.recompute()
        self._start_pick()

        FreeCADGui.Selection.addSelection(self.doc.Name, existing.Name)
        self._process_events(200)

        self.assertEqual(FreeCADGui.Selection.getSelectionEx(), [])
        self.assertEqual(len(self._sketches()), 1, "Only the pre-existing sketch may exist")
        self.assertIsNotNone(self._task_widget(PICKER_WIDGET), "The picker must stay open")

    def test_cancelling_the_pick_undoes_the_body_it_created(self):
        self.assertEqual(self._bodies(), [])
        self._start_pick()
        self.assertEqual(len(self._bodies()), 1, "Create Sketch makes the first body")
        self.body = self._bodies()[0]
        self.assertTrue(self._origin_shown(), "The new body's origin planes are offered")

        FreeCADGui.Control.activeTaskDialog().reject()
        self._process_events()

        self.assertTrue(
            self._wait_until(lambda: self._task_widget(PICKER_WIDGET) is None),
            "Cancel must close the picker",
        )
        self.assertEqual(self._sketches(), [])
        self.assertEqual(self._bodies(), [], "The body made for the sketch must be undone")
        self.assertIsNone(FreeCADGui.Control.activeTaskDialog())

    def test_escape_in_the_3d_view_cancels_the_pick(self):
        self._make_body()
        self._start_pick()
        self.assertTrue(self._origin_shown())

        self._send_escape_to_view()

        self.assertTrue(
            self._wait_until(lambda: self._task_widget(PICKER_WIDGET) is None),
            "Escape in the 3D view must close the picker",
        )
        self.assertEqual(self._sketches(), [])
        self.assertEqual(len(self._bodies()), 1, "A pre-existing body must survive a cancel")
        self.assertFalse(self._origin_shown(), "The origin planes must be hidden again")

    def test_closing_the_document_while_picking_is_harmless(self):
        self._make_body()
        self._start_pick()

        self._discard_document()
        self._process_events()

        self.assertIsNone(self._task_widget(PICKER_WIDGET))
        self.assertIsNone(FreeCADGui.Control.activeTaskDialog())

    def test_preselected_flat_face_skips_the_pick(self):
        self._make_body()
        cylinder = self._add_cylinder()
        flat = self._face_names(cylinder, planar=True)[-1]
        FreeCADGui.Selection.addSelection(self.doc.Name, cylinder.Name, flat)

        self._run_create_sketch()

        self.assertIsNone(self._task_widget(PICKER_WIDGET), "Nothing to pick: no picker")
        self._assert_sketch_opened_on(cylinder, flat)

    def test_preference_keeps_the_attachment_editor(self):
        self._make_body()
        self.params.SetBool(ATTACHMENT_PREF, True)

        self._run_create_sketch()

        self.assertTrue(
            self._wait_until(lambda: self._task_widget(ATTACHER_WIDGET) is not None),
            "The preference must bring back the attachment editor",
        )
        self.assertIsNone(self._task_widget(PICKER_WIDGET))
        self.assertEqual(len(self._sketches()), 1, "The editor works on an existing sketch")
