# SPDX-License-Identifier: LGPL-2.1-or-later

"""The grids follow the unit schema, however the schema was changed.

Two defects are pinned here:

* The Sketcher grid preference showed a fixed 10 mm when the user had never set it,
  although the sketch grid itself defaults to 1 inch under an imperial schema, and
  pressing OK anywhere in Preferences wrote that 10 mm back, pinning the grid to
  metric from then on.
* The 3D view's grid only watched the "UserSchema" preference. With a document open
  the status-bar unit chooser sets the document's UnitSystem instead, so the grid
  kept its old spacing until something else rebuilt it.

To run tests:
    FreeCAD -t TestGridUnits
"""

import math
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtWidgets

GRID_SIZE_GROUP = "User parameter:BaseApp/Preferences/Mod/Sketcher/General/GridSize"
VIEW_GROUP = "User parameter:BaseApp/Preferences/View"
UNITS_GROUP = "User parameter:BaseApp/Preferences/Units"

METRIC_SPACING = 10.0
IMPERIAL_SPACING = 25.4


def _schema_index(name):
    return FreeCAD.Units.listSchemas().index(name)


def _pump(ms=100):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(ms, loop.quit)
    loop.exec_()


def _is_power_of_ten_times(value, base):
    # The grid's vertices are single-precision floats, so a 0.1 inch step reads back as
    # about 2.53998 mm. Metric and imperial steps differ by log10(2.54) = 0.405, far
    # outside this tolerance.
    ratio = math.log10(value / base)
    return abs(ratio - round(ratio)) < 1e-3


class TestSketchGridPreference(unittest.TestCase):
    """The Grid page of the Sketcher preferences, with GridSize never set by the user."""

    def setUp(self):
        self.group = FreeCAD.ParamGet(GRID_SIZE_GROUP)
        self.saved_grid_size = self.group.GetString("GridSize", "")
        self.saved_schema = FreeCAD.Units.getSchema()
        self.group.RemString("GridSize")

    def tearDown(self):
        FreeCAD.Units.setSchema(self.saved_schema)
        if self.saved_grid_size:
            self.group.SetString("GridSize", self.saved_grid_size)
        else:
            self.group.RemString("GridSize")

    def _with_grid_page(self, check):
        """Open Preferences on the Sketcher Grid page, run check(page), and cancel.

        The dialog is modal, so the check runs from a timer inside its event loop. It is
        always rejected, never accepted, so no other page writes its values into the
        profile; the Grid page's own load and save slots are called directly instead.
        """

        outcome = {}

        def run():
            dialog = QtWidgets.QApplication.activeModalWidget()
            try:
                if dialog is None:
                    outcome["error"] = "Preferences did not open"
                    return
                pages = [
                    widget
                    for widget in dialog.findChildren(QtWidgets.QWidget)
                    if widget.metaObject().className() == "SketcherGui::SketcherSettingsGrid"
                ]
                if not pages:
                    outcome["error"] = "the Sketcher Grid page was not found"
                    return
                try:
                    check(pages[0])
                except Exception as exc:  # noqa: BLE001 - reported after the dialog closes
                    outcome["error"] = exc
            finally:
                if dialog is not None:
                    dialog.reject()

        # A second timer closes whatever modal is left, so a check that never runs
        # cannot leave the test stuck inside exec().
        def give_up():
            dialog = QtWidgets.QApplication.activeModalWidget()
            if dialog is not None:
                outcome.setdefault("error", "the check never ran")
                dialog.reject()

        QtCore.QTimer.singleShot(500, run)
        QtCore.QTimer.singleShot(10000, give_up)
        FreeCADGui.showPreferences("Sketcher", 1)

        error = outcome.get("error")
        if isinstance(error, Exception):
            raise error
        if error:
            self.fail(error)

    @staticmethod
    def _grid_size_box(page):
        box = page.findChild(QtWidgets.QAbstractSpinBox, "gridSize")
        if box is None:
            raise AssertionError("the Grid page has no gridSize box")
        return box

    def test_an_unset_grid_size_shows_the_imperial_default(self):
        FreeCAD.Units.setSchema(_schema_index("ImperialDecimal"))

        def check(page):
            QtCore.QMetaObject.invokeMethod(page, "loadSettings")
            shown = self._grid_size_box(page).property("rawValue")
            self.assertAlmostEqual(shown, IMPERIAL_SPACING, places=6)

        self._with_grid_page(check)

    def test_saving_an_untouched_page_leaves_grid_size_unset(self):
        for schema in ("Internal", "ImperialDecimal"):
            with self.subTest(schema=schema):
                FreeCAD.Units.setSchema(_schema_index(schema))

                def check(page):
                    QtCore.QMetaObject.invokeMethod(page, "loadSettings")
                    QtCore.QMetaObject.invokeMethod(page, "saveSettings")

                self._with_grid_page(check)
                self.assertEqual(
                    self.group.GetString("GridSize", ""),
                    "",
                    "OK on an untouched page must not pin the grid to one unit schema",
                )

    def test_a_changed_grid_size_is_still_saved(self):
        FreeCAD.Units.setSchema(_schema_index("Internal"))

        def check(page):
            QtCore.QMetaObject.invokeMethod(page, "loadSettings")
            self._grid_size_box(page).setProperty("rawValue", 5.0)
            QtCore.QMetaObject.invokeMethod(page, "saveSettings")

        self._with_grid_page(check)
        saved = self.group.GetString("GridSize", "")
        self.assertNotEqual(saved, "", "a grid size the user typed in must be saved")
        self.assertAlmostEqual(FreeCAD.Units.Quantity(saved).Value, 5.0, places=6)


class TestViewportGridFollowsUnits(unittest.TestCase):
    """The 3D view's grid, switched between metric and imperial from the status bar."""

    def setUp(self):
        self.view_params = FreeCAD.ParamGet(VIEW_GROUP)
        self.saved_show_grid = self.view_params.GetBool("ShowGrid", True)
        self.view_params.SetBool("ShowGrid", True)
        self.saved_schema = FreeCAD.Units.getSchema()

        self.doc = FreeCAD.newDocument("GridUnits")
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(self.doc.Name)
        box = self.doc.addObject("Part::Box", "Box")
        box.Length = box.Width = 100.0
        box.Height = 10.0
        self.doc.recompute()
        self.view = FreeCADGui.activeView()
        self.view.setCameraType("Orthographic")
        self.view.viewTop()
        self.view.fitAll()
        _pump(300)

    def tearDown(self):
        FreeCAD.closeDocument(self.doc.Name)
        # The document's UnitSystem took the schema with it; put back what the
        # profile says.
        FreeCAD.Units.setSchema(
            FreeCAD.ParamGet(UNITS_GROUP).GetInt("UserSchema", self.saved_schema)
        )
        self.view_params.SetBool("ShowGrid", self.saved_show_grid)
        _pump(100)

    @staticmethod
    def _unit_chooser():
        for button in FreeCADGui.getMainWindow().findChildren(QtWidgets.QPushButton):
            if button.metaObject().className() == "Gui::DimensionWidget":
                return button
        raise unittest.SkipTest("the status bar has no unit chooser")

    def _choose_schema(self, name):
        index = _schema_index(name)
        for action in self._unit_chooser().menu().actions():
            if action.data() == index:
                action.trigger()
                break
        else:
            self.fail("the unit chooser has no entry for " + name)
        self.view.redraw()
        _pump(300)

    def _grid_spacing(self):
        """The distance between neighbouring grid lines, read from the grid's own nodes."""

        from pivy import coin

        search = coin.SoSearchAction()
        search.setName(coin.SbName("ViewportGrid"))
        search.setInterest(coin.SoSearchAction.FIRST)
        search.setSearchingAll(True)
        search.apply(self.view.getViewer().getSceneGraph())
        path = search.getPath()
        if path is None:
            self.fail("the 3D view has no ViewportGrid node")

        # The vertices sit in each line set's vertexProperty field, which a search
        # action does not descend into, so find the line sets and read the field.
        line_sets = coin.SoSearchAction()
        line_sets.setType(coin.SoLineSet.getClassTypeId())
        line_sets.setInterest(coin.SoSearchAction.ALL)
        line_sets.setSearchingAll(True)
        line_sets.apply(path.getTail())

        xs = set()
        for i in range(line_sets.getPaths().getLength()):
            lines = line_sets.getPaths()[i].getTail()
            vertex_property = lines.vertexProperty.getValue()
            if vertex_property is None:
                continue
            for point in vertex_property.vertex.getValues():
                xs.add(round(point.getValue()[0], 6))
        xs = sorted(xs)
        gaps = [b - a for a, b in zip(xs, xs[1:]) if b - a > 1e-6]
        if not gaps:
            self.fail("the grid has no lines to measure (is it drawn in this view?)")
        return min(gaps)

    def test_the_status_bar_unit_chooser_rebuilds_the_grid(self):
        self._choose_schema("ImperialDecimal")
        spacing = self._grid_spacing()
        self.assertTrue(
            _is_power_of_ten_times(spacing, IMPERIAL_SPACING),
            "with a document in inches the grid steps {} mm, not whole inches".format(spacing),
        )

        self._choose_schema("Internal")
        spacing = self._grid_spacing()
        self.assertTrue(
            _is_power_of_ten_times(spacing, METRIC_SPACING),
            "back in millimetres the grid steps {} mm".format(spacing),
        )
