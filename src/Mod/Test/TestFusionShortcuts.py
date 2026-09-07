"""Fusion letter shortcuts resolve without a chord wait and yield to sketch tools.

To run tests:
    FreeCAD -t TestFusionShortcuts
"""
import unittest
import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets


class TestFusionShortcuts(unittest.TestCase):
    def setUp(self):
        self.doc = FreeCAD.newDocument("FusionShortcuts")
        FreeCADGui.activateWorkbench("PartDesignWorkbench")

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)

    def _shortcut_of(self, command):
        action = FreeCADGui.Command.get(command).getAction()[0]
        return action.shortcut().toString()

    def test_palette_has_priority_over_chords(self):
        # FreeCADGui.ShortcutManager is not exposed to Python, so read the
        # priority ShortcutManager::setPriority wrote straight from the
        # parameter group it uses (ShortcutManager.cpp: hShortcuts is
        # ".../Preferences/Shortcut", hPriorities is its "Priorities" group).
        hPriorities = FreeCAD.ParamGet(
            "User parameter:BaseApp/Preferences/Shortcut/Priorities"
        )
        prio = hPriorities.GetInt("Std_CommandPalette")
        self.assertGreater(prio, 0)

    def test_coincident_and_symmetric_left_bare_letters(self):
        self.assertNotEqual(self._shortcut_of("Sketcher_ConstrainCoincidentUnified"), "C")
        self.assertNotEqual(self._shortcut_of("Sketcher_ConstrainSymmetric"), "S")
        self.assertEqual(self._shortcut_of("Sketcher_CreateCircle"), "C")

    def test_placement_and_measure_inactive_inside_sketch(self):
        body = self.doc.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.AttachmentSupport = (self.doc.getObject("XY_Plane"), [""])
        sketch.MapMode = "FlatFace"
        self.doc.recompute()
        FreeCADGui.Selection.addSelection(body)
        FreeCADGui.ActiveDocument.setEdit(sketch.Name)
        QtWidgets.QApplication.processEvents()
        try:
            self.assertFalse(FreeCADGui.Command.get("Std_Placement").isActive())
            self.assertFalse(FreeCADGui.Command.get("Std_Measure").isActive())
        finally:
            FreeCADGui.ActiveDocument.resetEdit()
