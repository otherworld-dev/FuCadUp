// SPDX-License-Identifier: LGPL-2.1-or-later
/****************************************************************************
 *                                                                          *
 *   This file is part of FreeCAD.                                          *
 *                                                                          *
 *   FreeCAD is free software: you can redistribute it and/or modify it     *
 *   under the terms of the GNU Lesser General Public License as            *
 *   published by the Free Software Foundation, either version 2.1 of the   *
 *   License, or (at your option) any later version.                        *
 *                                                                          *
 *   FreeCAD is distributed in the hope that it will be useful, but         *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of             *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU       *
 *   Lesser General Public License for more details.                        *
 *                                                                          *
 *   You should have received a copy of the GNU Lesser General Public       *
 *   License along with FreeCAD. If not, see                                *
 *   <https://www.gnu.org/licenses/>.                                       *
 *                                                                          *
 ***************************************************************************/

#pragma once

#include <memory>

#include <QObject>
#include <QPointer>

#include <Inventor/SbVec3f.h>

#include <Base/Placement.h>
#include <Base/Unit.h>

#include <FCGlobal.h>

namespace Gui
{
class EditableDatumLabel;
class View3DInventorViewer;

/// A gizmo's value shown in the 3D view: a dimension with an editable box on it.
///
/// Geometry is given in the gizmos' own frame (the editing transform they are attached
/// under) and converted to the global frame the label is drawn in.
class GuiExport GizmoValueLabel: public QObject
{
    Q_OBJECT

public:
    /// The Coin node name every gizmo value label carries
    static constexpr const char* nodeName = "GizmoValueLabel";
    /// The object name every gizmo value box carries
    static constexpr const char* boxName = "GizmoValueBox";

    GizmoValueLabel(
        View3DInventorViewer* viewer,
        const Base::Placement& editPlacement,
        const Base::Unit& unit
    );
    ~GizmoValueLabel() override;

    /// A distance of travel from base along dir (a negative travel points back along dir)
    void showDistance(const SbVec3f& base, const SbVec3f& dir, float travel);
    /// An arc of sweep radians about axis through centre, at radius, starting at zeroRay
    void showAngle(
        const SbVec3f& centre,
        const SbVec3f& axis,
        const SbVec3f& zeroRay,
        float sweep,
        float radius
    );

    /// Puts value in the box, unless the box already holds it, so typed text is left alone
    void setValue(double value);
    void setShown(bool shown);
    bool isShown() const;
    void focus();
    bool hasFocus() const;

Q_SIGNALS:
    void valueEdited(double value);
    void accepted();
    void cancelled();
    void tabbed(bool backwards);
    void focusLeft();

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    Base::Vector3d toGlobalPoint(const SbVec3f& point) const;
    Base::Vector3d toGlobalDirection(const SbVec3f& direction) const;
    Base::Vector3d towardsViewer() const;

    QPointer<View3DInventorViewer> viewer;
    Base::Placement editPlacement;
    Base::Unit unit;
    std::unique_ptr<EditableDatumLabel> label;
    bool shown = false;
};

}  // namespace Gui
