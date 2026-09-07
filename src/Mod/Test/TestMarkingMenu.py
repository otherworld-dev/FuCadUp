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

"""GUI regression tests for the radial menu a right-click opens in the 3D view.

Three things have to hold whatever the cursor happens to be over. Letting go
between two entries must not run one of them, because a ring the size of a
screen is easy to miss and a command run by accident is worse than a menu that
stays up. The view commands must sit in the same four directions every time, so
that reaching for Fit All is a habit rather than a read. And the row that heads
the menu must name the object the entries below it came from.

To run tests:
    FreeCAD -t TestMarkingMenu
"""

import math
import unittest

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui

from TestNavigationStyles import (
    FUSION_STYLE,
    MOUSE_MOVE,
    MOUSE_PRESS,
    MOUSE_RELEASE,
    NO_BUTTON,
    RIGHT_BUTTON,
    ViewerTestCase,
)

try:
    import Part
except ImportError:
    Part = None

VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"

# The ring keeps its first four slots for the view commands, laid out in compass
# order: north, east, south, west, and then the diagonals.
NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3

# Far enough out of the dead zone in the middle to count as a direction, and well
# short of the boxes, which sit 100 px away across and 124 px up and down.
REACH = 60


class MarkingMenuTestCase(ViewerTestCase):
    """A document with one box, seen with the Fusion style and the ring turned on."""

    def setUp(self):
        if Part is None:
            raise unittest.SkipTest("The Part module is unavailable")

        super().setUp()

        self.box = self.doc.addObject("Part::Box", "Box")
        self.doc.recompute()

        self.params = FreeCAD.ParamGet(VIEW_PARAMS)
        self.marking_menu_was = self.params.GetBool("UseMarkingMenu", True)
        self.params.SetBool("UseMarkingMenu", True)

        self.view.setNavigationType(FUSION_STYLE)
        self._refresh_view()

    def tearDown(self):
        self._close_popups()
        FreeCADGui.Selection.clearPreselection()
        self.params.SetBool("UseMarkingMenu", self.marking_menu_was)
        super().tearDown()

    # -- helpers ---------------------------------------------------------

    def _hover(self, pos):
        """Move the cursor to ``pos`` in the viewport and return what it picked.

        A move can arrive before the view has drawn its first frame, in which case
        nothing is picked at all; give it a couple more chances.
        """

        for _ in range(3):
            self._refresh_view_widgets()
            self._post(self.viewport, MOUSE_MOVE, pos, NO_BUTTON, NO_BUTTON)
            self._process_events()
            name = FreeCADGui.Selection.getPreselection().ObjectName
            if name:
                return name
        return None

    def _over_the_box(self):
        """Hover the middle of the view, where the fitted box is, and say so."""

        centre = self.viewport.rect().center()
        self.assertEqual(
            self._hover(centre),
            self.box.Name,
            "The fitted box should be under the middle of the view",
        )
        return centre

    def _over_nothing(self):
        """Hover a corner of the view, which the fitted box does not reach."""

        corner = QtCore.QPoint(12, 12)
        self._hover(corner)
        self.assertEqual(
            FreeCADGui.Selection.getPreselection().ObjectName,
            "",
            "The corner of the view should be empty",
        )
        return corner

    def _open_menu(self, pos):
        """Right-click at ``pos`` in the viewport and return the popup it opened."""

        self._close_popups()
        self._refresh_view_widgets()
        self._post(self.viewport, MOUSE_PRESS, pos, RIGHT_BUTTON, RIGHT_BUTTON)
        self._process_events(10)
        self._post(self.viewport, MOUSE_RELEASE, pos, RIGHT_BUTTON, NO_BUTTON)
        self._process_events()

        popup = QtGui.QApplication.activePopupWidget()
        self.assertIsNotNone(popup, "A right click in the 3D view should open a menu")
        return popup

    def _open_ring(self, pos):
        """Right-click at ``pos`` and return the ring, rather than a plain list."""

        ring = self._open_menu(pos)
        self.assertEqual(
            ring.objectName(),
            "MarkingMenu",
            "The right click should have opened the ring, not a plain menu",
        )
        return ring

    def _still_open(self, popup):
        try:
            return popup.isVisible()
        except RuntimeError:
            # Closing the ring deletes it, so its wrapper stops answering.
            return False

    @staticmethod
    def _point_at(centre, degrees, reach):
        radians = math.radians(degrees)
        return QtCore.QPoint(
            centre.x() + round(reach * math.cos(radians)),
            centre.y() - round(reach * math.sin(radians)),
        )

    # -- tests -----------------------------------------------------------

    def test_release_between_two_entries_keeps_the_ring_open(self):
        ring = self._open_ring(self._over_nothing())
        centre = ring.rect().center()
        # Half way between the entry pointing east and the one pointing north
        # east, so that neither of them is under the cursor.
        between = self._point_at(centre, 22.5, REACH)

        self._post(ring, MOUSE_RELEASE, between, RIGHT_BUTTON, NO_BUTTON)
        self._process_events()

        self.assertTrue(
            self._still_open(ring),
            "Letting go between two entries must leave the ring up, not run one of them",
        )

    def test_release_in_the_middle_closes_the_ring(self):
        ring = self._open_ring(self._over_nothing())

        self._post(ring, MOUSE_RELEASE, ring.rect().center(), RIGHT_BUTTON, NO_BUTTON)
        self._process_events()

        self.assertFalse(
            self._still_open(ring),
            "Letting go without leaving the middle should cancel the ring",
        )

    def test_view_commands_keep_their_directions(self):
        ring = self._open_ring(self._over_nothing())
        empty = list(ring.property("sectorCommands"))
        self._close_popups()

        ring = self._open_ring(self._over_the_box())
        hovered = list(ring.property("sectorCommands"))
        self._close_popups()

        for slots, what in ((empty, "nothing"), (hovered, "a box")):
            with self.subTest(hovering=what):
                self.assertEqual(slots[NORTH], "Std_ViewFitAll")
                self.assertEqual(slots[EAST], "Std_ViewIsometric")
                # Home is the standard view of the south slot; a menu without it
                # falls back to the front view.
                self.assertIn(slots[SOUTH], ("Std_ViewHome", "Std_ViewFront"))
                self.assertEqual(slots[WEST], "Std_ViewFitSelection")

        self.assertEqual(
            empty[: WEST + 1],
            hovered[: WEST + 1],
            "The view commands must not move because something is under the cursor",
        )

    def test_header_names_the_hovered_object(self):
        self.params.SetBool("UseMarkingMenu", False)

        menu = self._open_menu(self._over_the_box())
        self.assertNotEqual(menu.objectName(), "MarkingMenu")
        header = menu.actions()[0]

        self.assertEqual(header.objectName(), "ContextMenuHeader")
        self.assertFalse(header.isEnabled(), "The header is a label, not an entry")
        self.assertTrue(
            header.text().startswith(self.box.Label),
            "The header should name the object the entries came from, got " + header.text(),
        )

    def test_header_falls_back_when_nothing_is_selected_or_hovered(self):
        self.params.SetBool("UseMarkingMenu", False)

        menu = self._open_menu(self._over_nothing())
        self.assertNotEqual(menu.objectName(), "MarkingMenu")
        header = menu.actions()[0]

        self.assertEqual(header.objectName(), "ContextMenuHeader")
        self.assertEqual(
            header.text(),
            QtCore.QCoreApplication.translate("QObject", "Nothing selected"),
        )


if __name__ == "__main__":
    unittest.main()
