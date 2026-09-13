# SPDX-License-Identifier: LGPL-2.1-or-later

"""GUI tests for typing a sketch dimension's value in the 3D view.

Placing a dimension, or editing one, opens a box on the dimension's own label instead of
the modal datum dialog: Enter applies the value, Esc keeps the dimension as it is, and
leaving the sketch applies what was typed.
"""

import FreeCAD
import Part
import Sketcher
from PySide import QtCore, QtGui, QtWidgets
from SketcherTests.GuiTestCase import FreeCADGui, SketcherGuiTestCase

SKETCHER_PARAMS = "User parameter:BaseApp/Preferences/Mod/Sketcher"
# SketcherGui::DimensionValueEditor::boxName
BOX_NAME = "SketchDimensionBox"


class TestSketchDimensionBox(SketcherGuiTestCase):
    """A 10 mm line in an open sketch, ready to be dimensioned."""

    def setUp(self):
        super().setUp()
        self._set_param("ShowDialogOnDistanceConstraint", True)
        self._set_param("EditDimensionsInView", True)

        FreeCADGui.activateWorkbench("SketcherWorkbench")
        self.doc = FreeCAD.newDocument("TestSketchDimensionBox")
        self.sketch = self.doc.addObject("Sketcher::SketchObject", "Sketch")
        self.sketch.addGeometry(
            Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0)), False
        )
        self.doc.recompute()

        main = FreeCADGui.getMainWindow()
        main.show()
        main.raise_()
        main.activateWindow()
        FreeCADGui.ActiveDocument.setEdit(self.sketch.Name)
        self.flush_gui(200)

    # -- helpers ---------------------------------------------------------

    def _set_param(self, name, value):
        params = FreeCAD.ParamGet(SKETCHER_PARAMS)
        had = name in params.GetBools()
        old = params.GetBool(name, True)
        params.SetBool(name, value)

        def restore():
            if had:
                params.SetBool(name, old)
            else:
                params.RemBool(name)

        self.addCleanup(restore)

    def boxes(self):
        main = FreeCADGui.getMainWindow()
        return [
            box
            for box in main.findChildren(QtWidgets.QAbstractSpinBox, BOX_NAME)
            if box.isVisible()
        ]

    def wait_for_box(self):
        self.assertTrue(
            self.wait_until(lambda: len(self.boxes()) == 1, timeout_ms=2000),
            f"expected one dimension box, saw {len(self.boxes())}",
        )
        return self.boxes()[0]

    def wait_for_focus(self, box):
        self.assertTrue(
            self.wait_until(box.hasFocus, timeout_ms=2000), "the dimension box did not get the keyboard"
        )

    def place_length_dimension(self):
        """Dimension the line through its command, the way a user would with it selected."""

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, "Edge1")
        FreeCADGui.runCommand("Sketcher_ConstrainDistance")
        self.flush_gui(150)
        self.assertEqual(len(self.sketch.Constraints), 1, "the distance was not placed")
        return 0

    def type_into(self, box, text):
        box.findChild(QtWidgets.QLineEdit).selectAll()
        for ch in text:
            self.key_click(box, QtCore.Qt.Key(ord(ch.upper())), ch)

    def value(self, index):
        return float(self.sketch.Constraints[index].Value)

    # -- placing ---------------------------------------------------------

    def test_placing_a_dimension_opens_a_focused_box_with_its_length(self):
        self.place_length_dimension()
        box = self.wait_for_box()
        self.assertAlmostEqual(box.property("rawValue"), 10.0)
        self.wait_for_focus(box)

    def test_enter_applies_the_typed_value(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.type_into(box, "25")
        self.key_click(box, QtCore.Qt.Key_Return)
        self.flush_gui(150)
        self.assertAlmostEqual(self.value(index), 25.0)
        self.assertEqual(self.boxes(), [])

    def test_the_value_is_undone_before_the_dimension(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.type_into(box, "25")
        self.key_click(box, QtCore.Qt.Key_Return)
        self.flush_gui(150)

        self.doc.undo()
        self.flush_gui(150)
        self.assertEqual(len(self.sketch.Constraints), 1, "undo took the dimension away with its value")
        self.assertAlmostEqual(self.value(index), 10.0)

    def test_escape_keeps_the_dimension_as_measured(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.type_into(box, "25")
        self.key_click(box, QtCore.Qt.Key_Escape)
        self.flush_gui(150)
        self.assertEqual(len(self.sketch.Constraints), 1)
        self.assertAlmostEqual(self.value(index), 10.0)
        self.assertEqual(self.boxes(), [])
        self.assertIsNotNone(FreeCADGui.ActiveDocument.getInEdit(), "Esc in the box left the sketch")

    def test_units_can_be_typed(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.type_into(box, "1 in")
        self.key_click(box, QtCore.Qt.Key_Return)
        self.flush_gui(150)
        self.assertAlmostEqual(self.value(index), 25.4, places=6)

    # -- editing ---------------------------------------------------------

    def test_editing_an_existing_dimension_opens_the_box(self):
        index = self.sketch.addConstraint(Sketcher.Constraint("Distance", 0, 7.0))
        self.doc.recompute()
        self.flush_gui(150)

        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, f"Constraint{index + 1}")
        FreeCADGui.runCommand("Sketcher_ChangeDimensionConstraint")
        box = self.wait_for_box()
        self.assertAlmostEqual(box.property("rawValue"), 7.0)

        self.type_into(box, "9")
        self.key_click(box, QtCore.Qt.Key_Return)
        self.flush_gui(150)
        self.assertAlmostEqual(self.value(index), 9.0)

    def test_reference_from_the_box_menu(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.wait_for_focus(box)

        chosen = []

        def choose():
            menu = QtWidgets.QApplication.activePopupWidget()
            if menu is None:
                return
            for action in menu.actions():
                if action.text() == "Reference":
                    chosen.append(action.text())
                    action.trigger()
                    break
            menu.close()

        QtCore.QTimer.singleShot(300, choose)
        edit = box.findChild(QtWidgets.QLineEdit)
        centre = edit.rect().center()
        event = QtGui.QContextMenuEvent(QtGui.QContextMenuEvent.Mouse, centre, edit.mapToGlobal(centre))
        QtWidgets.QApplication.sendEvent(edit, event)
        self.flush_gui(200)

        self.assertEqual(chosen, ["Reference"], "the box's menu had no Reference entry")
        self.assertFalse(self.sketch.Constraints[index].Driving)
        self.assertEqual(self.boxes(), [])

    def test_leaving_the_sketch_applies_what_was_typed(self):
        index = self.place_length_dimension()
        box = self.wait_for_box()
        self.type_into(box, "30")
        FreeCADGui.ActiveDocument.resetEdit()
        self.flush_gui(200)
        self.assertAlmostEqual(self.value(index), 30.0)
        self.assertEqual(self.boxes(), [])

    def test_with_the_setting_off_the_dialog_opens_instead(self):
        self._set_param("EditDimensionsInView", False)
        seen = []

        def dismiss():
            dialog = QtWidgets.QApplication.activeModalWidget()
            if dialog is not None:
                seen.append(dialog.windowTitle())
                dialog.reject()

        QtCore.QTimer.singleShot(400, dismiss)
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(self.doc.Name, self.sketch.Name, "Edge1")
        FreeCADGui.runCommand("Sketcher_ConstrainDistance")
        self.flush_gui(150)

        self.assertEqual(len(seen), 1, "the datum dialog did not open")
        self.assertEqual(self.boxes(), [])
