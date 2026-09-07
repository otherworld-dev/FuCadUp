// SPDX-License-Identifier: LGPL-2.1-or-later

/**************************************************************************
 *   Copyright (c) 2026 FreeCAD contributors                               *
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

#pragma once

#include <functional>
#include <QPointer>

#include <Gui/Selection/Selection.h>
#include <Gui/TaskView/TaskDialog.h>

class SoEventCallback;

namespace App
{
class Document;
class DocumentObject;
}  // namespace App
namespace Gui
{
class View3DInventorViewer;
}
namespace PartDesign
{
class Body;
}

namespace PartDesignGui
{

/**
 * Waits for one click on a planar face, datum plane or origin plane, so that
 * Create Sketch works the way Fusion does: click the command, click the surface.
 *
 * The dialog owns nothing but the wait. Building the sketch from the selection
 * and tidying up afterwards belong to the caller, which hands them in as
 * callbacks. A pick the handler turns down leaves the dialog open, so the user
 * can simply click something else. Esc in the 3D view, the Cancel button and
 * closing the document all end the wait without a sketch.
 */
class TaskDlgSketchPlanePick: public Gui::TaskView::TaskDialog, public Gui::SelectionObserver
{
    Q_OBJECT

public:
    /// Builds the sketch from the current selection; returns null to keep on picking.
    using PickHandler = std::function<App::DocumentObject*()>;
    /// Runs once the dialog has left the task panel; the sketch is null after a cancel.
    using DoneHandler = std::function<void(App::DocumentObject* sketch)>;

    TaskDlgSketchPlanePick(PartDesign::Body* body, PickHandler onPick, DoneHandler onDone);
    ~TaskDlgSketchPlanePick() override;

    void open() override;
    bool accept() override;
    bool reject() override;
    void autoClosedOnDeletedDocument() override;

    QDialogButtonBox::StandardButtons getStandardButtons() const override
    {
        return QDialogButtonBox::Cancel;
    }
    bool isAllowedAlterDocument() const override
    {
        return false;
    }

    void onSelectionChanged(const Gui::SelectionChanges& msg) override;

private:
    void tryPick();
    void cancel();
    static void handleKeyboardCB(void* userdata, SoEventCallback* cb);

    PartDesign::Body* body;
    PickHandler onPick;
    DoneHandler onDone;
    App::DocumentObject* sketch {nullptr};
    bool opened {false};
    bool pickScheduled {false};
    bool documentClosing {false};
    QPointer<Gui::View3DInventorViewer> viewer;
};

}  // namespace PartDesignGui
