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

"""GUI regression tests for the vocabulary the shell puts on screen.

A workbench is an implementation detail of the core this forks from, so no
workbench name belongs in the shell. Two places used to leak one. The block at
the left of the ribbon held the core's own workbench chooser, so it read
"Part Design" whilst the tab beside it read SOLID, two names for one mode. And
a tab the workspace does not describe is generated from the active workbench
and titled after it, so hiding a tab without care puts the workbench name back
on screen in place of the one that was removed.

The workspace block therefore names the workspace the ribbon loaded, and never
follows the workbench. The tabs that are only command lists over an upstream
workbench are not offered by default, but the tab defined for one comes back
whilst its workbench is active, which keeps the generated tab from appearing in
its place.

The start page is held to the same rule, being the first screen a user meets.

To run tests:
    FreeCAD -t TestShellVocabulary
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtWidgets

MAIN_WINDOW_PARAMS = "User parameter:BaseApp/Preferences/MainWindow"

# src/Gui/Ribbon/Workspaces/Design.json carries this as its "name".
WORKSPACE_NAME = "Design"

# The tab the fork has designed, and one it has not, see the same file.
DESIGNED_TAB = "SOLID"
PASSTHROUGH_TAB = "MESH"
PASSTHROUGH_WORKBENCH = "MeshWorkbench"

# Every tab that is only a command list over an upstream workbench.
PASSTHROUGH_TABS = ("SURFACE", "MESH", "DRAWING", "MANUFACTURE", "SIMULATION")

# What the workspace block must never show, being workbench menu text.
WORKBENCH_NAMES = ("Part Design", "Sketcher", "Mesh")


class RibbonWorkspaceTestCase(unittest.TestCase):
    """Shared setup for the tests that read the ribbon's own chrome."""

    def setUp(self):
        if not FreeCAD.ParamGet(MAIN_WINDOW_PARAMS).GetBool("UseRibbon", True):
            raise unittest.SkipTest("The ribbon shell is switched off in this build")

        self.window = FreeCADGui.getMainWindow()
        if self.window is None:
            raise unittest.SkipTest("No main window in this test environment")

        self.tab_bar = self.window.findChild(QtWidgets.QTabBar, "RibbonTabBar")
        if self.tab_bar is None:
            raise unittest.SkipTest("The ribbon shell is not installed in this test environment")

        FreeCADGui.activateWorkbench("PartDesignWorkbench")
        self._process_events()

    def tearDown(self):
        FreeCADGui.activateWorkbench("PartDesignWorkbench")
        self._process_events()

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _tab_titles(self):
        return [self.tab_bar.tabText(i) for i in range(self.tab_bar.count())]

    def _wait_for_tab(self, title, present=True, timeout_ms=3000):
        """Tabs are rebuilt on a queued refresh, so give the strip time."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            titles = self._tab_titles()
            if (title in titles) == present:
                return titles
            if time.monotonic() >= deadline:
                return titles
            self._process_events(20)

    def _workspace_texts(self):
        """Every piece of text the workspace block shows the user."""

        block = self.window.findChild(QtWidgets.QWidget, "RibbonWorkspaceBlock")
        if block is None:
            return None

        texts = []
        for child in block.findChildren(QtWidgets.QWidget):
            if isinstance(child, QtWidgets.QComboBox):
                texts.append(child.currentText())
            elif isinstance(child, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
                texts.append(child.text())
        return [text for text in texts if text]


class TestWorkspaceBlock(RibbonWorkspaceTestCase):
    """The block at the left of the ribbon names a workspace, not a workbench."""

    def test_the_block_names_the_workspace(self):
        texts = self._workspace_texts()
        self.assertIsNotNone(texts, "Expected a RibbonWorkspaceBlock in the ribbon")
        self.assertIn(
            WORKSPACE_NAME.upper(),
            [text.upper() for text in texts],
            "The workspace block should name the loaded workspace, showed " + repr(texts),
        )

    def test_the_block_shows_no_workbench_name(self):
        texts = self._workspace_texts()
        self.assertIsNotNone(texts, "Expected a RibbonWorkspaceBlock in the ribbon")
        shown = [text.upper() for text in texts]
        for name in WORKBENCH_NAMES:
            self.assertNotIn(
                name.upper(),
                shown,
                "The workspace block showed the workbench name " + repr(name),
            )

    def test_the_block_does_not_follow_the_active_workbench(self):
        before = self._workspace_texts()
        self.assertIsNotNone(before, "Expected a RibbonWorkspaceBlock in the ribbon")

        FreeCADGui.activateWorkbench(PASSTHROUGH_WORKBENCH)
        self._process_events(200)

        self.assertEqual(
            before,
            self._workspace_texts(),
            "Switching workbench changed what the workspace block shows",
        )


class TestPassthroughTabs(RibbonWorkspaceTestCase):
    """Tabs that only list an upstream workbench's commands stay out of the way."""

    def test_the_designed_tab_is_offered(self):
        self.assertIn(DESIGNED_TAB, self._tab_titles())

    def test_passthrough_tabs_are_not_offered_by_default(self):
        titles = self._tab_titles()
        for title in PASSTHROUGH_TABS:
            self.assertNotIn(
                title,
                titles,
                "Expected the passthrough tab " + title + " to be hidden by default",
            )

    def test_a_passthrough_tab_returns_whilst_its_workbench_is_active(self):
        FreeCADGui.activateWorkbench(PASSTHROUGH_WORKBENCH)
        titles = self._wait_for_tab(PASSTHROUGH_TAB, present=True)

        self.assertIn(
            PASSTHROUGH_TAB,
            titles,
            "The defined tab should come back whilst its workbench is active",
        )

    def test_no_tab_is_generated_from_the_workbench_name(self):
        FreeCADGui.activateWorkbench(PASSTHROUGH_WORKBENCH)
        titles = self._wait_for_tab(PASSTHROUGH_TAB, present=True)

        menu_text = FreeCADGui.getWorkbench(PASSTHROUGH_WORKBENCH).MenuText
        self.assertNotIn(
            menu_text,
            titles,
            "A tab titled after the workbench appeared instead of the defined one",
        )

    def test_a_passthrough_tab_leaves_again_with_its_workbench(self):
        FreeCADGui.activateWorkbench(PASSTHROUGH_WORKBENCH)
        self._wait_for_tab(PASSTHROUGH_TAB, present=True)

        FreeCADGui.activateWorkbench("PartDesignWorkbench")
        titles = self._wait_for_tab(PASSTHROUGH_TAB, present=False)

        self.assertNotIn(
            PASSTHROUGH_TAB,
            titles,
            "The passthrough tab stayed behind after its workbench was left",
        )


class TestStartPage(unittest.TestCase):
    """The page shown before any document is open names no workbench either."""

    def setUp(self):
        if FreeCADGui.getMainWindow() is None:
            raise unittest.SkipTest("No main window in this test environment")

        self.start_view = self._find_start_view()
        opened_here = self.start_view is None
        if self.start_view is None:
            # A test run opens no document, so nothing has asked for the page yet.
            FreeCADGui.runCommand("Start_Start")
            deadline = time.monotonic() + 5.0
            while self.start_view is None and time.monotonic() < deadline:
                FreeCADGui.updateGui()
                QtWidgets.QApplication.instance().processEvents()
                time.sleep(0.05)
                self.start_view = self._find_start_view()

        self.assertIsNotNone(self.start_view, "Could not open the start page")
        self.opened_here = opened_here

    def tearDown(self):
        # Leaves the window list as it was found. Note that once the page has
        # been built the process prints "QWaitCondition: Destroyed while
        # threads are still waiting" on the way out whether it is closed here
        # or not, which is the file card loader, not this test.
        if getattr(self, "opened_here", False) and self.start_view is not None:
            self.start_view.close()
            FreeCADGui.updateGui()
            QtWidgets.QApplication.instance().processEvents()

    @staticmethod
    def _find_start_view():
        for widget in QtWidgets.QApplication.instance().allWidgets():
            if widget.metaObject().className() == "StartGui::StartView":
                return widget
        return None

    def test_the_start_page_names_no_workbench(self):
        offenders = [
            label.text()
            for label in self.start_view.findChildren(QtWidgets.QLabel)
            if "workbench" in label.text().lower()
        ]
        self.assertEqual(
            [],
            offenders,
            "The start page still names a workbench: " + repr(offenders),
        )


if __name__ == "__main__":
    unittest.main()
