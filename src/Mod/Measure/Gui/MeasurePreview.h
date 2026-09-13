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

#include <optional>

#include <QObject>
#include <QPointer>
#include <QString>
#include <QTimer>

#include <App/MeasureManager.h>
#include <Base/Vector3D.h>
#include <Gui/Selection/Selection.h>

class SoCoordinate3;
class SoSwitch;
class SoTranslation;

namespace Gui
{
class SoFrameLabel;
class View3DInventorViewer;
}  // namespace Gui

namespace MeasureGui
{

/// While the Measure tool is open: the value of what is under the cursor, in the 3D view.
///
/// Hovering one item shows its own value (length, radius or area); with one item picked,
/// hovering a second shows the distance or angle between the two. Nothing is added to the
/// document: the value is worked out with the same geometry handlers the measurements use
/// and drawn as a temporary label that cannot be picked.
class MeasurePreview: public QObject, public Gui::SelectionObserver
{
    Q_OBJECT

public:
    /// The Coin node name of the preview's text label
    static constexpr const char* labelName = "MeasurePreviewLabel";

    MeasurePreview();
    ~MeasurePreview() override;

private:
    struct Preview
    {
        QString text;
        Base::Vector3d at;
        std::optional<std::pair<Base::Vector3d, Base::Vector3d>> line;
    };

    void onSelectionChanged(const Gui::SelectionChanges& msg) override;
    void refresh();
    void clear();
    void show(const Preview& preview);
    bool attachTo(Gui::View3DInventorViewer* active);
    void detach();

    static std::optional<Preview> compute(App::MeasureSelection selection);
    static std::optional<Preview> single(App::SubObjectT item, const std::string& kind);
    static std::optional<Preview> distance(App::MeasureSelection selection, const std::string& kind);
    static std::optional<Preview> angle(App::MeasureSelection selection);

    QTimer timer;
    QPointer<Gui::View3DInventorViewer> viewer;
    SoSwitch* root;
    SoSwitch* lineSwitch;
    SoCoordinate3* lineCoords;
    SoTranslation* labelPlace;
    Gui::SoFrameLabel* label;
};

}  // namespace MeasureGui
