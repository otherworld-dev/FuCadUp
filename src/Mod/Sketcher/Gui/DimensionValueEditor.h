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

#include <Base/Placement.h>
#include <Base/Unit.h>

class QLineEdit;

namespace Gui
{
class EditableDatumLabel;
class QuantitySpinBox;
class SoDatumLabel;
class View3DInventorViewer;
}  // namespace Gui

namespace Sketcher
{
class SketchObject;
}

namespace SketcherGui
{

/// Whether dimension values are typed in the 3D view rather than in a dialog
/// (preference Mod/Sketcher/EditDimensionsInView)
bool editDimensionsInView();

/// A box on a sketch dimension's own label to type its value in, in place of EditDatumDialog.
///
/// Enter applies the typed value as its own undo step, Esc closes without applying and
/// losing the keyboard applies a valid typed value. Right-click offers Reference,
/// Radius/Diameter, Name and the full dialog. The editor deletes itself once finished.
class DimensionValueEditor: public QObject
{
    Q_OBJECT

public:
    /// The object name the value box carries
    static constexpr const char* boxName = "SketchDimensionBox";

    DimensionValueEditor(
        Gui::View3DInventorViewer* viewer,
        const Base::Placement& sketchPlacement,
        Sketcher::SketchObject* sketch,
        int constraint,
        const Gui::SoDatumLabel& shownLabel
    );
    ~DimensionValueEditor() override;

    int constraintIndex() const;
    /// Closes the box, first applying a valid typed value when apply is true
    void finish(bool apply);

protected:
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    void copyLabel(const Gui::SoDatumLabel& shownLabel);
    /// Selects the whole value, so typing replaces it, unless the user has started typing
    void selectValue();
    bool constraintStillThere() const;
    void applyValue();
    void showMenu(const QPoint& globalPos);
    void makeReference();
    void swapRadiusDiameter();
    void rename();
    void openDialog();
    int openTransaction(const char* name) const;

    Sketcher::SketchObject* sketch;
    int constraint;
    // What the constraint was when the box opened, to notice another one taking its index
    int type {};
    int first {};
    int firstPos {};
    int second {};
    int secondPos {};
    int third {};
    int thirdPos {};
    Base::Unit unit;
    std::unique_ptr<Gui::EditableDatumLabel> label;
    QPointer<Gui::QuantitySpinBox> box;
    QPointer<QLineEdit> edit;
    bool typed = false;
    bool swapType = false;
    bool menuOpen = false;
    bool finished = false;
};

}  // namespace SketcherGui
