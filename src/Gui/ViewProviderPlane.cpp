/***************************************************************************
 *   Copyright (c) 2012 Jürgen Riegel <juergen.riegel@web.de>              *
 *   Copyright (c) 2015 Alexander Golubev (Fat-Zer) <fatzer2@gmail.com>    *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#include <Inventor/nodes/SoAsciiText.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoDrawStyle.h>
#include <Inventor/nodes/SoFaceSet.h>
#include <Inventor/nodes/SoIndexedLineSet.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoPickStyle.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoShapeHints.h>
#include <Inventor/nodes/SoTranslation.h>
#include <Inventor/nodes/SoSwitch.h>
#include <Inventor/SbColor.h>

#include <App/Datums.h>
#include <App/Document.h>
#include <Gui/ViewParams.h>

#include "ViewProviderPlane.h"
#include "ViewProviderCoordinateSystem.h"

#include <Utilities.h>
#include <Base/Tools.h>
#include <Inventor/SoPickedPoint.h>
#include <Inventor/events/SoEvent.h>
#include <Inventor/nodes/SoFontStyle.h>


using namespace Gui;

PROPERTY_SOURCE(Gui::ViewProviderPlane, Gui::ViewProviderDatum)


ViewProviderPlane::ViewProviderPlane()
    : SelectionObserver(true)
{
    sPixmap = "Std_Plane";
    lineThickness = 1.0;

    pLabel = new SoAsciiText();
}

ViewProviderPlane::~ViewProviderPlane() = default;

void ViewProviderPlane::attach(App::DocumentObject* obj)
{
    ViewProviderDatum::attach(obj);

    std::string role = getRole();

    SoSeparator* sep = getDatumRoot();

    // Setup colors
    // Can't use transparency because of https://github.com/FreeCAD/FreeCAD/issues/18395
    // When this issue is fixed then we can use the below and remove the material here
    // and faceSeparator...
    // ShapeAppearance.setTransparency(0.8);
    auto material = new SoMaterial();
    material->transparency.setValue(0.85f);

    if (!role.empty()) {
        ShapeAppearance.setDiffuseColor(getColor(role));
    }

    SbColor color = ShapeAppearance.getDiffuseColor().asValue<SbColor>();
    material->ambientColor.setValue(color);
    material->diffuseColor.setValue(color);

    auto ps = new SoPickStyle();
    ps->style.setValue(SoPickStyle::SHAPE_ON_TOP);

    pCoords = new SoCoordinate3();
    sep->addChild(pCoords);
    sep->addChild(material);
    sep->addChild(ps);

    // The outline and face grow to the full square while the plane is hovered or selected.
    // That growth is feedback only and must not take part in picking: every origin plane
    // picks "on top", so Coin reports them all at the same depth and a grown plane that
    // overlaps its neighbour on screen would keep winning the pick by scene graph order,
    // leaving the highlight stuck on it. Picking is done by an invisible quarter instead.
    auto feedbackOnly = new SoPickStyle();
    feedbackOnly->style.setValue(SoPickStyle::UNPICKABLE);

    static const int32_t lines[6] = {0, 1, 2, 3, 0, -1};

    auto lineSeparator = new SoSeparator();
    lineSeparator->addChild(feedbackOnly);
    auto pLines = new SoIndexedLineSet();
    pLines->coordIndex.setNum(6);
    pLines->coordIndex.setValues(0, 6, lines);

    lineSeparator->addChild(pLines);
    sep->addChild(lineSeparator);

    // add semi transparent face
    auto faceSeparator = new SoSeparator();
    faceSeparator->addChild(feedbackOnly);
    sep->addChild(faceSeparator);

    // disable backface culling and render with two-sided lighting
    auto shapeHints = new SoShapeHints();
    shapeHints->vertexOrdering = SoShapeHints::COUNTERCLOCKWISE;
    shapeHints->shapeType = SoShapeHints::UNKNOWN_SHAPE_TYPE;
    faceSeparator->addChild(shapeHints);

    auto faceSet = new SoFaceSet();
    auto vertexProperty = new SoVertexProperty();
    vertexProperty->vertex.connectFrom(&pCoords->point);
    faceSet->vertexProperty.setValue(vertexProperty);
    faceSeparator->addChild(faceSet);

    // The pickable extent: an invisible copy of the quarter (face and outline) that keeps
    // its size whatever the plane currently draws.
    auto pickSeparator = new SoSeparator();
    auto invisible = new SoDrawStyle();
    invisible->style.setValue(SoDrawStyle::INVISIBLE);
    pickSeparator->addChild(invisible);
    pPickCoords = new SoCoordinate3();
    pickSeparator->addChild(pPickCoords);
    auto pickOutline = new SoIndexedLineSet();
    pickOutline->coordIndex.setNum(6);
    pickOutline->coordIndex.setValues(0, 6, lines);
    pickSeparator->addChild(pickOutline);
    pickSeparator->addChild(new SoFaceSet());
    sep->addChild(pickSeparator);

    pTextTranslation = new SoTranslation();
    sep->addChild(pTextTranslation);

    pLabel->string.setValue(getLabelText(role).c_str());
    pLabel->justification = SoAsciiText::RIGHT;
    labelSwitch = new SoSwitch();
    setLabelVisibility(false);

    auto font = new SoFontStyle();
    font->size = 10.0;
    font->style = SoFontStyle::BOLD;
    font->family = SoFontStyle::SANS;

    auto labelMaterial = static_cast<SoMaterial*>(material->copy());
    labelMaterial->transparency = 0.0;

    labelSwitch->addChild(font);
    labelSwitch->addChild(labelMaterial);
    labelSwitch->addChild(pTextTranslation);
    labelSwitch->addChild(pLabel);

    updatePlaneSize();

    sep->addChild(labelSwitch);

    handlers.addDelayedHandler(
        ViewParams::instance()->getHandle(),
        {"DatumLineSize", "DatumScale"},
        [this](ParameterGrp::handle) { updatePlaneSize(); }
    );

    updatePlaneSize();
}

void ViewProviderPlane::setLabelVisibility(bool val)
{
    labelSwitch->whichChild = val ? SO_SWITCH_ALL : SO_SWITCH_NONE;
}

void ViewProviderPlane::onSelectionChanged(const SelectionChanges& msg)
{
    bool isSelectedOrHoveredBefore = isSelected || isHovered;

    if (msg.Type == Gui::SelectionChanges::ClrSelection) {
        isSelected = false;
    }

    auto obj = getObject();
    if (!obj) {
        return;
    }
    auto doc = obj->getDocument();
    if (!doc) {
        return;
    }
    const char* nameInDoc = getObject()->getNameInDocument();

    if (nameInDoc && strcmp(msg.pDocName, doc->getName()) == 0
        && strcmp(msg.pObjectName, nameInDoc) == 0) {
        isSelected = Gui::Selection().isSelected(getObject());
        isHovered = Gui::Selection().getPreselection().Object.getSubObject() == getObject()
            || Gui::Selection().getPreselection().Object.getObject() == getObject();
    }

    bool isSelectedOrHovered = isSelected || isHovered;

    if (isSelectedOrHoveredBefore != isSelectedOrHovered) {
        updatePlaneSize();
    }
}

void ViewProviderPlane::updatePlaneSize()
{
    if (!pcObject->isAttachedToDocument()) {
        return;
    }

    const auto params = ViewParams::instance();

    const float size = params->getDatumPlaneSize() * Base::fromPercent(params->getDatumScale());
    const float offset = 8.0F;

    const SbVec3f quarter[4] = {
        SbVec3f(size, size, 0),
        SbVec3f(size, offset, 0),
        SbVec3f(offset, offset, 0),
        SbVec3f(offset, size, 0),
    };
    const SbVec3f full[4] = {
        SbVec3f(size, size, 0),
        SbVec3f(size, -size, 0),
        SbVec3f(-size, -size, 0),
        SbVec3f(-size, size, 0),
    };

    // An origin plane (one with a role) shows its quarter and grows to the full square while
    // hovered or selected; any other plane always shows the full square. Only the quarter is
    // ever pickable, so the growth cannot change which plane is under the cursor.
    const bool hasRole = !getRole().empty();
    const bool isSelectedOrHovered = isSelected || isHovered;
    const SbVec3f* drawn = (hasRole && !isSelectedOrHovered) ? quarter : full;
    const SbVec3f* pickable = hasRole ? quarter : full;

    pTextTranslation->translation.setValue(drawn[0] / 2 - SbVec3f(2, 6, 0));  // NOLINT
    pCoords->point.setNum(4);
    pCoords->point.setValues(0, 4, drawn);
    pPickCoords->point.setNum(4);
    pPickCoords->point.setValues(0, 4, pickable);
}

unsigned long ViewProviderPlane::getColor(const std::string& role) const
{
    auto planesRoles = App::LocalCoordinateSystem::PlaneRoles;
    if (role == planesRoles[0]) {
        return ViewParams::instance()->getAxisZColor();  // XY-plane
    }
    else if (role == planesRoles[1]) {
        return ViewParams::instance()->getAxisYColor();  // XZ-plane
    }
    else if (role == planesRoles[2]) {
        return ViewParams::instance()->getAxisXColor();  // YZ-plane
    }
    return 0;
}

std::string ViewProviderPlane::getLabelText(const std::string& role) const
{
    auto planesRoles = App::LocalCoordinateSystem::PlaneRoles;
    if (role == planesRoles[0]) {
        return "XY";
    }
    else if (role == planesRoles[1]) {
        return "XZ";
    }
    else if (role == planesRoles[2]) {
        return "YZ";
    }
    return getObject()->getNameInDocument();
}

std::string ViewProviderPlane::getRole() const
{
    // Note: Role property of App::Plane is not set yet when attaching.
    const char* name = pcObject->getNameInDocument();
    if (!name) {
        return "";
    }

    auto planesRoles = App::LocalCoordinateSystem::PlaneRoles;
    if (strncmp(name, planesRoles[0], strlen(planesRoles[0])) == 0) {
        return planesRoles[0];
    }
    else if (strncmp(name, planesRoles[1], strlen(planesRoles[1])) == 0) {
        return planesRoles[1];
    }
    else if (strncmp(name, planesRoles[2], strlen(planesRoles[2])) == 0) {
        return planesRoles[2];
    }

    return "";
}
