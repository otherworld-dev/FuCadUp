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

"""GUI regression tests for FuCadUp's Fusion-branded defaults (usability Task 5).

To run tests:
    FreeCAD -t TestFuCadDefaults
"""

import time
import unittest

import FreeCAD
import FreeCADGui

VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"
WEBSITES_PARAMS = "User parameter:BaseApp/Preferences/Websites"

FUSION_STYLE = "Gui::FusionNavigationStyle"


class TestNavigationStyleDefault(unittest.TestCase):
    """A fresh install (no NavigationStyle entry yet) must land on the Fusion style,
    not the upstream CAD style FreeCAD ships with."""

    def setUp(self):
        self.view_params = FreeCAD.ParamGet(VIEW_PARAMS)
        # Save whatever the user already had configured, if anything, and remove
        # the entry so the C++ default (View3DSettings.cpp) is what answers.
        self._had_value = "NavigationStyle" in self.view_params.GetStrings()
        self._saved_value = self.view_params.GetString("NavigationStyle", "")
        self.view_params.RemString("NavigationStyle")
        self.doc = None

    def tearDown(self):
        if self._had_value:
            self.view_params.SetString("NavigationStyle", self._saved_value)
        else:
            self.view_params.RemString("NavigationStyle")
        if self.doc is not None:
            FreeCAD.closeDocument(self.doc.Name)

    def _active_view(self, timeout_ms=2000):
        """A view freshly created for a new document can briefly still be None
        while the document/GUI machinery finishes wiring it up."""

        deadline = time.monotonic() + (timeout_ms / 1000.0)
        while True:
            gui_doc = FreeCADGui.getDocument(self.doc.Name)
            view = gui_doc.ActiveView
            if view is not None:
                return view
            if time.monotonic() >= deadline:
                self.fail("No active 3D view appeared for the new document")
            FreeCADGui.updateGui()
            time.sleep(0.02)

    def test_navigation_style_defaults_to_fusion_when_absent(self):
        self.doc = FreeCAD.newDocument("TestFuCadDefaultsNavigation")

        view = self._active_view()

        self.assertEqual(
            view.getNavigationType(),
            FUSION_STYLE,
            "A new view with no NavigationStyle preference set must default to "
            "the Fusion navigation style (View3DSettings.cpp), not the upstream "
            "CAD style",
        )


class TestReportBugUrl(unittest.TestCase):
    """"Report an Issue" must point at this fork's tracker, not FreeCAD's.

    Std_ReportBug's URL only exists as a C++ string literal inside
    CommandStd.cpp: it is not exposed as a status tip, a whatsThis, or any
    other Python-observable property of the command's QAction (its status
    tip is the generic "Opens the bugtracker to report an issue"), and it is
    never pre-populated into a parameter that Python could read either -- the
    "IssuesPage" parameter is only ever written, with the URL as its value,
    as a side effect of the command actually running.

    So the only way to observe the real value is to run the command and
    capture what it hands to the OS's browser launcher. Gui::OpenURLInBrowser
    does this through Python's own "webbrowser" module (see
    src/Gui/OnlineDocumentation.cpp), so replacing that module's "open"
    function for the duration of the call intercepts the URL without ever
    spawning a real browser.
    """

    def setUp(self):
        self.websites_params = FreeCAD.ParamGet(WEBSITES_PARAMS)
        self._had_value = "IssuesPage" in self.websites_params.GetStrings()
        self._saved_value = self.websites_params.GetString("IssuesPage", "")
        self.websites_params.RemString("IssuesPage")

    def tearDown(self):
        if self._had_value:
            self.websites_params.SetString("IssuesPage", self._saved_value)
        else:
            self.websites_params.RemString("IssuesPage")

    def test_report_bug_opens_the_fork_tracker(self):
        import webbrowser

        opened_urls = []
        original_open = webbrowser.open
        webbrowser.open = lambda url, *args, **kwargs: opened_urls.append(url)
        try:
            FreeCADGui.runCommand("Std_ReportBug", 0)
        finally:
            webbrowser.open = original_open

        self.assertTrue(opened_urls, "Std_ReportBug did not open any URL")
        self.assertIn(
            "otherworld-dev/FuCadUp",
            opened_urls[0],
            "Std_ReportBug must open this fork's issue tracker, not FreeCAD/FreeCAD's",
        )

        # activated() also persists what it opened, so the fork's URL becomes
        # the parameter's effective value from here on.
        self.assertIn("otherworld-dev/FuCadUp", self.websites_params.GetString("IssuesPage", ""))


class TestDatumScaleDefault(unittest.TestCase):
    """A fresh install must draw the origin bigger than upstream draws it.

    Asserted as a ratio against the scale upstream ships rather than against a
    number, so the test says what the default is for -- an origin you can hit when
    you are picking a plane to sketch on -- without restating the sizes ViewParams
    multiplies together to get there.
    """

    def setUp(self):
        self.view_params = FreeCAD.ParamGet(VIEW_PARAMS)
        # Save whatever the user already had, then remove it so the C++ default
        # (ViewParams.cpp) is what answers.
        self._had_value = "DatumScale" in self.view_params.GetFloats()
        self._saved_value = self.view_params.GetFloat("DatumScale", 0.0)
        self.view_params.RemFloat("DatumScale")

    def tearDown(self):
        if self._had_value:
            self.view_params.SetFloat("DatumScale", self._saved_value)
        else:
            self.view_params.RemFloat("DatumScale")

    def drawnExtent(self, name):
        """How far an origin plane reaches, in a document made just now.

        A new document each time because ViewProviderPlane reads the scale as it
        attaches: the handler that resizes what is already on screen runs delayed,
        so a plane built before the parameter moved keeps the size it was built at.
        """
        from pivy import coin

        doc = FreeCAD.newDocument(name)
        try:
            FreeCADGui.ActiveDocument = FreeCADGui.getDocument(doc.Name)
            lcs = doc.addObject("App::LocalCoordinateSystem", "LCS")
            doc.recompute()
            lcs.ViewObject.Visibility = True
            FreeCADGui.updateGui()

            plane = doc.getObject("XY_Plane")
            self.assertIsNotNone(plane, "the coordinate system grew no XY plane")

            action = coin.SoGetBoundingBoxAction(coin.SbViewportRegion(1000, 1000))
            action.apply(plane.ViewObject.RootNode)
            return action.getBoundingBox().getMax().getValue()[0]
        finally:
            FreeCAD.closeDocument(doc.Name)

    def test_the_origin_is_drawn_three_times_the_size_upstream_draws_it(self):
        by_default = self.drawnExtent("TestFuCadDefaultsDatumScaleDefault")

        self.view_params.SetFloat("DatumScale", 100.0)
        upstream = self.drawnExtent("TestFuCadDefaultsDatumScaleUpstream")

        self.assertGreater(upstream, 0.0, "the plane is drawn with no extent at all")
        self.assertAlmostEqual(
            by_default,
            3.0 * upstream,
            delta=0.5,
            msg="a fresh install draws the origin plane out to %.1f, where upstream's "
            "scale gives %.1f: the default is not three times it"
            % (by_default, upstream),
        )
