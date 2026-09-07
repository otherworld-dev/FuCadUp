/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/


#pragma once

#include <string>

#include <Inventor/SbVec3f.h>
#include <Inventor/sensors/SoNodeSensor.h>

#include <Base/Parameter.h>
#include <FCGlobal.h>

class SoSeparator;
class SoSensor;

namespace Gui
{

class View3DInventorViewer;

/**
 * The spacing a grid starts from, in millimetres: 10 mm under a metric unit
 * schema, 25.4 mm (one inch) under an imperial one, so that an imperial user
 * gets whole inches rather than decimal millimetres.
 *
 * Both grids read it - the viewport grid here and the sketch grid's GridSize
 * default (Mod/Sketcher/Gui/ViewProviderSketch.cpp) - so that the sketch grid
 * does not change pitch under the user at the moment it takes over from this one.
 */
GuiExport double gridBaseSpacing();

/**
 * gridBaseSpacing() written the way Base::Quantity::parse() reads it, for use as
 * the default of a parameter that stores a length as text.
 */
GuiExport std::string gridBaseSpacingText();

/**
 * The lines of the viewport grid, worked out from numbers alone so that the
 * arithmetic can be checked without a viewer.
 *
 * Lines are addressed by integer index: line i lies at i * spacing, and index
 * zero is the axis through the origin.
 * @author FuCad contributors
 */
struct GuiExport ViewportGridLayout
{
    double spacing {1.0};
    int subdivision {10};
    int firstX {0};
    int lastX {0};
    int firstY {0};
    int lastY {0};

    /**
     * The spacing that keeps neighbouring lines at least \a pixelThreshold
     * pixels apart when \a visibleExtent model units span \a viewportPixels:
     * \a baseSpacing scaled by a power of \a subdivision, the rule the sketch
     * grid follows so that the two agree when one takes over from the other.
     */
    static double spacingFor(
        double baseSpacing,
        int subdivision,
        double visibleExtent,
        int viewportPixels,
        int pixelThreshold
    );

    /// The lines that cover a square of side \a extent centred on (\a centerX, \a centerY).
    static ViewportGridLayout covering(
        double spacing,
        int subdivision,
        double centerX,
        double centerY,
        double extent
    );

    /// Every subdivision-th line, counted from the origin, is a major line.
    bool isMajor(int index) const;
    double position(int index) const;
    /// Lines in both directions together.
    int lineCount() const;
};

/**
 * An adaptive grid on the XY plane through the origin, drawn in the 3D view
 * the way Fusion draws its modelling grid.
 *
 * The grid follows the camera: it is rebuilt whenever the view zooms or pans
 * far enough for its lines to change, and its spacing steps by powers of ten so
 * that the lines never crowd. It takes part in the depth test, so a body
 * resting on the plane sits on top of it, but it is neither pickable nor part
 * of the bounding box that "fit all" frames.
 *
 * The viewer owns one grid and hangs its node into the scene; whether it shows
 * is the user's preference, and it is held back while a sketch draws a grid of
 * its own.
 * @author FuCad contributors
 */
class GuiExport ViewportGrid: public ParameterGrp::ObserverType
{
public:
    explicit ViewportGrid(View3DInventorViewer* viewer);
    ~ViewportGrid() override;

    ViewportGrid(const ViewportGrid&) = delete;
    ViewportGrid& operator=(const ViewportGrid&) = delete;

    /// The node that carries the lines; the grid keeps ownership of it.
    SoSeparator* getNode() const;

    /// The user's choice of whether the grid is drawn at all.
    void setEnabled(bool on);
    bool isEnabled() const;

    /**
     * Held back while something in the view draws a grid of its own, as a
     * sketch in edit mode does, so that the two never show at once.
     */
    void setSuspended(bool on);

    /// Follows the viewer's current camera; call again once the camera has been replaced.
    void attachCamera();

    /**
     * Catches up with what the camera sensor never sees: the viewport gaining
     * a size or changing it, and the camera being replaced under the sensor.
     * Cheap enough to call before every frame, and a no-op while nothing has
     * changed.
     */
    void syncViewport();

    /**
     * Rebuilds the lines for the current camera. A rebuild the camera sensor
     * asks for is skipped while the camera has not moved enough to change
     * them, so that orbiting stays cheap.
     */
    void rebuild(bool cameraDriven = false);

    /// The unit schema changed, so the base spacing is due to be read again.
    void OnChange(ParameterGrp::SubjectType& rCaller, ParameterGrp::MessageType reason) override;

private:
    static void cameraChanged(void* data, SoSensor* sensor);

    bool shouldDraw() const;
    bool cameraBelowPlane() const;
    /// Refreshes the remembered camera state and says whether it changed enough to matter.
    bool cameraMovedEnough();
    void clear();
    void addLines(const ViewportGridLayout& layout, bool major, float z);

    View3DInventorViewer* viewer;
    SoSeparator* root;
    SoNodeSensor cameraSensor;
    /// Watched for "UserSchema", which is how the unit schema changes.
    ParameterGrp::handle unitParameters;
    /// 10 mm for a metric unit schema, 25.4 mm (1 in) for an imperial one.
    double baseSpacing;
    /// Set by the observer, acted on by the next syncViewport(); see OnChange().
    bool baseSpacingStale {false};
    bool enabled {true};
    bool suspended {false};
    SbVec3f lastFocalPoint {0.0F, 0.0F, 0.0F};
    float lastMaxDimension {0.0F};
    bool lastCameraBelowPlane {false};
    short lastViewportWidth {0};
    short lastViewportHeight {0};
    bool tooDenseNotified {false};
};

}  // namespace Gui
