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


#include <algorithm>
#include <cmath>
#include <vector>

#include <Inventor/SbColor.h>
#include <Inventor/SoRenderManager.h>
#include <Inventor/nodes/SoCamera.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoLightModel.h>
#include <Inventor/nodes/SoLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoPickStyle.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoTransparencyType.h>
#include <Inventor/nodes/SoVertexProperty.h>

#include <Base/Console.h>
#include <Base/UnitsApi.h>

#include "Inventor/SoFCBoundingBox.h"
#include "View3DInventorViewer.h"
#include "ViewportGrid.h"


using namespace Gui;

namespace
{
// The sketch grid's defaults, so that the two grids agree where one takes over
// from the other.
constexpr double metricBaseSpacing = 10.0;
// 1 inch, so that the grid steps in whole inches rather than decimal
// millimetres while the user works in an imperial unit schema.
constexpr double imperialBaseSpacing = 25.4;
constexpr int subdivision = 10;

/// 10 mm for a metric unit schema, 25.4 mm (1 in) for an imperial one.
double baseSpacingForUnitSchema()
{
    const std::string basicLengthUnit = Base::UnitsApi::getBasicLengthUnit();
    if (basicLengthUnit == "in" || basicLengthUnit == "ft") {
        return imperialBaseSpacing;
    }
    return metricBaseSpacing;
}
constexpr int pixelThreshold = 15;
// How far beyond the visible area the lines reach, so that a pan of less than
// a tenth of the view needs no rebuild.
constexpr double extentFactor = 1.5;
constexpr float focalPointMoveFraction = 0.1F;
// Past this the grid would be a solid sheet, so it is left out instead.
constexpr int maximumLines = 4000;
// The lines are nudged off the plane on the side away from the camera by this
// fraction of the visible extent, so that a face lying on the plane wins the
// depth test cleanly instead of flickering against them.
constexpr float zOffsetFactor = 0.001F;

constexpr float minorGrey = 0.55F;
constexpr float minorTransparency = 0.8F;
constexpr float majorGrey = 0.65F;
constexpr float majorTransparency = 0.55F;

SoMaterial* makeMaterial(float grey, float transparency)
{
    auto* material = new SoMaterial;
    material->diffuseColor.setValue(SbColor(grey, grey, grey));
    material->transparency.setValue(transparency);
    return material;
}
}  // namespace


double ViewportGridLayout::spacingFor(
    double baseSpacing,
    int subdivision,
    double visibleExtent,
    int viewportPixels,
    int pixelThreshold
)
{
    if (baseSpacing <= 0.0) {
        return 1.0;
    }

    const int lines = viewportPixels / std::max(1, pixelThreshold);
    if (visibleExtent <= 0.0 || lines <= 0) {
        return baseSpacing;
    }

    // A subdivision of one cannot serve as a scale factor, so the sketch grid
    // steps by ten in that case and this follows suit.
    const int factor = subdivision <= 1 ? 10 : subdivision;
    const double exponent
        = 1.0 + std::floor(std::log(visibleExtent / lines / baseSpacing) / std::log(factor));
    const double spacing = baseSpacing * std::pow(factor, exponent);

    if (!std::isfinite(spacing) || spacing <= 0.0) {
        return baseSpacing;
    }

    return spacing;
}

ViewportGridLayout ViewportGridLayout::covering(
    double spacing,
    int subdivision,
    double centerX,
    double centerY,
    double extent
)
{
    ViewportGridLayout layout;
    layout.spacing = spacing;
    layout.subdivision = std::max(1, subdivision);

    const double half = extent / 2.0;
    layout.firstX = static_cast<int>(std::floor((centerX - half) / spacing));
    layout.lastX = static_cast<int>(std::ceil((centerX + half) / spacing));
    layout.firstY = static_cast<int>(std::floor((centerY - half) / spacing));
    layout.lastY = static_cast<int>(std::ceil((centerY + half) / spacing));

    return layout;
}

bool ViewportGridLayout::isMajor(int index) const
{
    return index % subdivision == 0;
}

double ViewportGridLayout::position(int index) const
{
    return index * spacing;
}

int ViewportGridLayout::lineCount() const
{
    return (lastX - firstX + 1) + (lastY - firstY + 1);
}


ViewportGrid::ViewportGrid(View3DInventorViewer* viewer)
    : viewer(viewer)
    , root(new SoSeparator)
    , baseSpacing(baseSpacingForUnitSchema())
{
    root->ref();
    root->setName("ViewportGrid");

    cameraSensor.setFunction(&ViewportGrid::cameraChanged);
    cameraSensor.setData(this);
}

ViewportGrid::~ViewportGrid()
{
    cameraSensor.detach();
    root->removeAllChildren();
    root->unref();
}

SoSeparator* ViewportGrid::getNode() const
{
    return root;
}

void ViewportGrid::setEnabled(bool on)
{
    if (enabled == on) {
        return;
    }

    enabled = on;
    rebuild();
}

bool ViewportGrid::isEnabled() const
{
    return enabled;
}

void ViewportGrid::setSuspended(bool on)
{
    if (suspended == on) {
        return;
    }

    suspended = on;
    rebuild();
}

void ViewportGrid::attachCamera()
{
    SoCamera* camera = viewer ? viewer->getSoRenderManager()->getCamera() : nullptr;

    if (cameraSensor.getAttachedNode() != camera) {
        cameraSensor.detach();
        if (camera) {
            cameraSensor.attach(camera);
        }
    }

    rebuild();
}

void ViewportGrid::syncViewport()
{
    if (!viewer) {
        return;
    }

    // Switching between orthographic and perspective replaces the camera; the
    // sensor lets go of the dead one by itself, and the next frame picks up
    // its successor here.
    if (!cameraSensor.getAttachedNode()) {
        attachCamera();
        return;
    }

    short width = 0;
    short height = 0;
    viewer->getViewportRegion().getViewportSizePixels().getValue(width, height);
    if (width == lastViewportWidth && height == lastViewportHeight) {
        return;
    }

    rebuild();
}

void ViewportGrid::cameraChanged(void* data, SoSensor*)
{
    static_cast<ViewportGrid*>(data)->rebuild(true);
}

bool ViewportGrid::shouldDraw() const
{
    return enabled && !suspended && viewer;
}

bool ViewportGrid::cameraBelowPlane() const
{
    SoCamera* camera = viewer->getSoRenderManager()->getCamera();
    return camera && camera->position.getValue()[2] < 0.0F;
}

bool ViewportGrid::cameraMovedEnough()
{
    const float maxDimension = viewer->getMaxDimension();
    const SbVec3f focalPoint = viewer->getFocalPoint();
    const bool below = cameraBelowPlane();

    const bool zoomed = std::fabs(maxDimension - lastMaxDimension) > 0.0F;
    const bool panned
        = (focalPoint - lastFocalPoint).length() > focalPointMoveFraction * maxDimension;
    const bool crossedPlane = below != lastCameraBelowPlane;

    if (!zoomed && !panned && !crossedPlane) {
        return false;
    }

    lastMaxDimension = maxDimension;
    lastFocalPoint = focalPoint;
    lastCameraBelowPlane = below;
    return true;
}

void ViewportGrid::clear()
{
    root->removeAllChildren();
}

void ViewportGrid::rebuild(bool cameraDriven)
{
    // Remembered whatever happens next, so that syncViewport() only comes
    // back once the size actually changes.
    short width = 0;
    short height = 0;
    if (viewer) {
        viewer->getViewportRegion().getViewportSizePixels().getValue(width, height);
    }
    lastViewportWidth = width;
    lastViewportHeight = height;

    if (!shouldDraw() || !viewer->getSoRenderManager()->getCamera()) {
        clear();
        return;
    }

    // Always refresh the remembered camera state, so that a rebuild forced
    // for another reason still leaves the sensor comparing against the
    // present camera.
    const bool moved = cameraMovedEnough();
    if (cameraDriven && !moved) {
        return;
    }

    if (width <= 0 || height <= 0) {
        // Not laid out yet; syncViewport() brings the rebuild back once the
        // view has pixels to fill.
        clear();
        return;
    }

    const float maxDimension = viewer->getMaxDimension();
    const SbVec3f focalPoint = viewer->getFocalPoint();

    const double spacing = ViewportGridLayout::spacingFor(
        baseSpacing,
        subdivision,
        maxDimension,
        std::max(width, height),
        pixelThreshold
    );
    const ViewportGridLayout layout = ViewportGridLayout::covering(
        spacing,
        subdivision,
        focalPoint[0],
        focalPoint[1],
        extentFactor * maxDimension
    );

    clear();

    if (layout.lineCount() > maximumLines) {
        if (!tooDenseNotified) {
            Base::Console().log("Viewport grid: too dense for this view, left out until it clears\n");
            tooDenseNotified = true;
        }
        return;
    }
    tooDenseNotified = false;

    const float z = (lastCameraBelowPlane ? 1.0F : -1.0F) * zOffsetFactor * maxDimension;
    addLines(layout, false, z);
    addLines(layout, true, z);
}

void ViewportGrid::addLines(const ViewportGridLayout& layout, bool major, float z)
{
    const auto minX = static_cast<float>(layout.position(layout.firstX));
    const auto maxX = static_cast<float>(layout.position(layout.lastX));
    const auto minY = static_cast<float>(layout.position(layout.firstY));
    const auto maxY = static_cast<float>(layout.position(layout.lastY));

    std::vector<SbVec3f> vertices;
    vertices.reserve(2 * static_cast<size_t>(layout.lineCount()));

    for (int i = layout.firstX; i <= layout.lastX; ++i) {
        if (layout.isMajor(i) != major) {
            continue;
        }
        const auto x = static_cast<float>(layout.position(i));
        vertices.emplace_back(x, minY, z);
        vertices.emplace_back(x, maxY, z);
    }

    for (int j = layout.firstY; j <= layout.lastY; ++j) {
        if (layout.isMajor(j) != major) {
            continue;
        }
        const auto y = static_cast<float>(layout.position(j));
        vertices.emplace_back(minX, y, z);
        vertices.emplace_back(maxX, y, z);
    }

    if (vertices.empty()) {
        return;
    }

    const int lineCount = static_cast<int>(vertices.size()) / 2;

    // In INCLUDE mode the group still counts for the render manager's
    // clipping planes, which have to reach the grid in an otherwise empty
    // document, while "fit all" excludes it by marking its own bounding box
    // action, so the model is what gets framed.
    auto* group = new SoSkipBoundingGroup;
    group->mode = SoSkipBoundingGroup::INCLUDE_BBOX;

    // The separator keeps the drawing state below from leaking into the
    // scene that follows the grid.
    auto* separator = new SoSeparator;

    auto* transparencyType = new SoTransparencyType;
    transparencyType->value = SoTransparencyType::DELAYED_BLEND;

    // The lines are a flat tint, not a lit surface.
    auto* lightModel = new SoLightModel;
    lightModel->model = SoLightModel::BASE_COLOR;

    auto* drawStyle = new SoDrawStyle;
    drawStyle->lineWidth = 1;

    auto* pickStyle = new SoPickStyle;
    pickStyle->style = SoPickStyle::UNPICKABLE;

    auto* vertexProperty = new SoVertexProperty;
    vertexProperty->vertex.setValues(0, static_cast<int>(vertices.size()), vertices.data());

    auto* lines = new SoLineSet;
    lines->vertexProperty = vertexProperty;
    lines->numVertices.setNum(lineCount);
    int32_t* counts = lines->numVertices.startEditing();
    std::fill(counts, counts + lineCount, 2);
    lines->numVertices.finishEditing();

    separator->addChild(transparencyType);
    separator->addChild(lightModel);
    separator->addChild(
        makeMaterial(major ? majorGrey : minorGrey, major ? majorTransparency : minorTransparency)
    );
    separator->addChild(drawStyle);
    separator->addChild(pickStyle);
    separator->addChild(lines);

    group->addChild(separator);
    root->addChild(group);
}
