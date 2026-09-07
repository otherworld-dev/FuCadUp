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

"""GUI regression tests for the Fusion-style ribbon.

A ribbon button renames the command it runs: the MODIFY panel of the SOLID tab
calls PartDesign_Thickness "Shell", the way Fusion does. Qt copies text and
tooltip back from the default action on every QEvent::ActionChanged, and
Command::testActive toggles the enabled state of every action after each
selection change, so without an actionEvent() override of its own the button
loses that name the first time the user clicks anything.

The ribbon replaces the toolbars, so it also has to be reachable without a
mouse. It behaves like one toolbar rather than like a hundred tab stops: the tab
strip is the only stop in the tab chain, Down steps from it onto the page, Left
and Right walk the buttons of that page, Up returns to the strip and Esc hands
the keyboard back to the view. The command palette carries a cursor of the same
kind across its tile grid, and needs an entry somewhere a mouse can find it.

To run tests:
    FreeCAD -t TestRibbon
"""

import time
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets

MAIN_WINDOW_PARAMS = "User parameter:BaseApp/Preferences/MainWindow"

# The MODIFY panel of the SOLID tab, see src/Gui/Ribbon/Workspaces/Design.json.
RENAMED_COMMAND = "PartDesign_Thickness"
RIBBON_CAPTION = "Shell"

# The SELECT panel offers the palette, which is in no menu of its own.
PALETTE_COMMAND = "Std_CommandPalette"
PALETTE_CAPTION = "Search Commands"

# Object names RibbonButton::setPrimary() gives a command button.
RIBBON_BUTTON_NAMES = ("RibbonButton", "RibbonPrimaryButton")
# Plus the panel caption drop-down, which the arrow keys also walk over.
RIBBON_PAGE_BUTTON_NAMES = RIBBON_BUTTON_NAMES + ("RibbonPanelCaptionButton",)


class TestRibbon(unittest.TestCase):
    """The ribbon has to keep its own captions and stay reachable by keyboard."""

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

        self.action = FreeCADGui.Command.get(RENAMED_COMMAND).getAction()[0]
        self.was_enabled = self.action.isEnabled()
        self.button = self._wait_for_button(self.action)
        self.assertIsNotNone(
            self.button, "Expected a ribbon button bound to " + RENAMED_COMMAND
        )

    def tearDown(self):
        action = getattr(self, "action", None)
        if action is not None:
            action.setEnabled(self.was_enabled)
            self._process_events()

    # -- helpers ---------------------------------------------------------

    def _process_events(self, wait_ms=50):
        FreeCADGui.updateGui()
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        time.sleep(wait_ms / 1000.0)
        app.processEvents()

    def _buttons_for(self, action):
        """Every ribbon command button whose default action is ``action``."""

        found = []
        for button in self.window.findChildren(QtWidgets.QToolButton):
            if button.objectName() not in RIBBON_BUTTON_NAMES:
                continue
            default = button.defaultAction()
            if default is not None and default == action:
                found.append(button)
        return found

    def _wait_for_button(self, action, timeout_ms=3000):
        """The page of a tab is only built the first time the tab is shown."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            buttons = self._buttons_for(action)
            if buttons:
                return buttons[0]
            if time.monotonic() >= deadline:
                return None
            self._process_events(20)

    def _toggle_enabled(self):
        """Do to the action what Command::testActive does on a selection change."""

        enabled = self.action.isEnabled()
        self.action.setEnabled(not enabled)
        self._process_events()
        self.action.setEnabled(enabled)
        self._process_events()

    def _send_key(self, widget, key):
        event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier)
        QtWidgets.QApplication.instance().sendEvent(widget, event)

    def _focus_widget(self):
        """The widget the keyboard sits on.

        QApplication.focusWidget() is empty while the main window is not the
        active window, which is normal on an unattended test machine; the
        window's own focus child is set by setFocus() either way.
        """

        return QtWidgets.QApplication.focusWidget() or self.window.focusWidget()

    def _tiles(self, palette):
        return palette.findChildren(QtWidgets.QToolButton, "CommandPaletteTile")

    def _current_tile(self, palette):
        """The tile the palette's own keyboard cursor sits on."""

        for tile in self._tiles(palette):
            if tile.property("current"):
                return tile
        return None

    # -- tests -----------------------------------------------------------

    def test_ribbon_caption_survives_an_enabled_toggle(self):
        """Qt re-copies the action text on ActionChanged; the ribbon name must win."""

        self.assertEqual(self.button.text(), RIBBON_CAPTION)
        self._toggle_enabled()
        self.assertEqual(self.button.text(), RIBBON_CAPTION)

    def test_ribbon_tooltip_survives_an_enabled_toggle(self):
        """The name is not drawn on the button, so the tooltip has to lead with it."""

        self.assertTrue(
            self.button.toolTip().startswith(RIBBON_CAPTION),
            "Expected the tooltip to open with " + RIBBON_CAPTION,
        )
        self._toggle_enabled()
        self.assertTrue(
            self.button.toolTip().startswith(RIBBON_CAPTION),
            "Expected the tooltip to still open with " + RIBBON_CAPTION,
        )

    def test_ribbon_tab_strip_takes_keyboard_focus(self):
        """The strip is the ribbon's single tab stop, so it must be in the chain."""

        self.assertNotEqual(self.tab_bar.focusPolicy(), QtCore.Qt.NoFocus)

    def test_arrow_keys_walk_the_ribbon_from_the_tab_strip(self):
        """Down enters the page, Left and Right walk it, Up returns to the strip."""

        self.tab_bar.setFocus(QtCore.Qt.OtherFocusReason)
        self._process_events()
        self.assertEqual(
            self._focus_widget(), self.tab_bar, "Expected the tab strip to take focus"
        )

        self._send_key(self.tab_bar, QtCore.Qt.Key_Down)
        self._process_events()
        first = self._focus_widget()
        self.assertIn(
            first.objectName(),
            RIBBON_PAGE_BUTTON_NAMES,
            "Expected Down to put the keyboard on a button of the page",
        )

        self._send_key(first, QtCore.Qt.Key_Right)
        self._process_events()
        second = self._focus_widget()
        self.assertIn(
            second.objectName(),
            RIBBON_PAGE_BUTTON_NAMES,
            "Expected Right to stay inside the page",
        )
        self.assertNotEqual(second, first, "Expected Right to move to another button")

        self._send_key(second, QtCore.Qt.Key_Up)
        self._process_events()
        self.assertEqual(
            self._focus_widget(), self.tab_bar, "Expected Up to return to the tab strip"
        )

    def test_command_palette_has_a_ribbon_entry(self):
        """The palette answers a shortcut only; nothing else points at it."""

        palette = FreeCADGui.Command.get(PALETTE_COMMAND)
        self.assertIsNotNone(palette, "Expected " + PALETTE_COMMAND + " to be registered")

        button = self._wait_for_button(palette.getAction()[0])
        self.assertIsNotNone(button, "Expected a ribbon button for " + PALETTE_COMMAND)
        self.assertEqual(button.text(), PALETTE_CAPTION)

    def test_palette_arrow_keys_move_the_current_tile(self):
        """The palette grid carries a cursor of its own, marked current=true."""

        FreeCADGui.runCommand(PALETTE_COMMAND)
        self._process_events()

        palette = self.window.findChild(QtWidgets.QWidget, "CommandPalette")
        self.assertIsNotNone(palette, "Expected the command palette to open")

        try:
            search = palette.findChild(QtWidgets.QLineEdit, "CommandPaletteSearch")
            self.assertIsNotNone(search, "Expected the palette to have a search field")

            # A query fills the grid from every registered command, so the test
            # does not depend on what happens to be pinned or recently used.
            search.setText("std")
            self._process_events()

            runnable = [tile for tile in self._tiles(palette) if tile.isEnabled()]
            if len(runnable) < 2:
                raise unittest.SkipTest("Fewer than two runnable commands in the palette")

            self._send_key(search, QtCore.Qt.Key_Down)
            self._process_events()
            first = self._current_tile(palette)
            self.assertIsNotNone(first, "Expected Down to step into the tile grid")

            self._send_key(search, QtCore.Qt.Key_Right)
            self._process_events()
            second = self._current_tile(palette)
            self.assertIsNotNone(second, "Expected Right to keep a tile current")
            self.assertNotEqual(second, first, "Expected Right to move the tile cursor")
        finally:
            palette.hide()
            self._process_events()
