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

#include <QApplication>
#include <QLabel>
#include <QTimer>
#include <QVBoxLayout>

#include <Inventor/events/SoKeyboardEvent.h>
#include <Inventor/nodes/SoEventCallback.h>

#include <App/Application.h>
#include <App/Datums.h>
#include <App/Document.h>
#include <Gui/Application.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Control.h>
#include <Gui/Document.h>
#include <Gui/InputHint.h>
#include <Gui/MainWindow.h>
#include <Gui/View3DInventor.h>
#include <Gui/View3DInventorViewer.h>
#include <Mod/Part/App/Part2DObject.h>
#include <Mod/PartDesign/App/Body.h>

#include "SketchPlanePicker.h"
#include "ReferenceSelection.h"

using namespace PartDesignGui;

namespace
{

/// Lets through only what a FlatFace sketch can sit on: planar faces, datum planes
/// and the origin planes of the body the sketch is going into.
class SketchPlaneGate: public ReferenceSelection
{
public:
    explicit SketchPlaneGate(PartDesign::Body* body)
        : ReferenceSelection(nullptr, planarFaces())
        , body(body)
    {}

    bool allow(App::Document* document, App::DocumentObject* object, const char* subName) override
    {
        if (!object || !body || document != body->getDocument()) {
            return false;
        }
        // ReferenceSelection treats a sketch as a face, but nothing is sketched on a
        // sketch here: that route needs the attachment editor.
        if (object->isDerivedFrom<Part::Part2DObject>()) {
            return false;
        }
        if (object->isDerivedFrom<App::DatumElement>()) {
            return object->isDerivedFrom<App::Plane>() && body->hasObject(object, true);
        }
        return ReferenceSelection::allow(document, object, subName);
    }

private:
    static AllowSelectionFlags planarFaces()
    {
        AllowSelectionFlags flags;
        flags.setFlag(AllowSelection::FACE);
        flags.setFlag(AllowSelection::PLANAR);
        flags.setFlag(AllowSelection::OTHERBODY);
        return flags;
    }

    PartDesign::Body* body;
};

Gui::View3DInventorViewer* viewerOf(App::Document* document)
{
    if (auto* guiDocument = Gui::Application::Instance->getDocument(document)) {
        if (auto* view = dynamic_cast<Gui::View3DInventor*>(guiDocument->getActiveView())) {
            return view->getViewer();
        }
    }
    if (auto* view = qobject_cast<Gui::View3DInventor*>(Gui::getMainWindow()->activeWindow())) {
        return view->getViewer();
    }
    return nullptr;
}

}  // namespace

TaskDlgSketchPlanePick::TaskDlgSketchPlanePick(
    PartDesign::Body* body,
    PickHandler onPick,
    DoneHandler onDone
)
    : Gui::TaskView::TaskDialog()
    , Gui::SelectionObserver(/* attach = */ false)
    , body(body)
    , onPick(std::move(onPick))
    , onDone(std::move(onDone))
{
    setDocumentName(body->getDocument()->getName());
    setAutoCloseOnDeletedDocument(true);

    auto* panel = new QWidget();
    panel->setObjectName(QStringLiteral("PartDesignGui__TaskSketchPlanePick"));
    panel->setWindowTitle(tr("Create Sketch"));
    auto* layout = new QVBoxLayout(panel);
    auto* hint = new QLabel(
        tr("Select a planar face, datum plane or origin plane to sketch on."),
        panel
    );
    hint->setWordWrap(true);
    layout->addWidget(hint);
    addTaskBox(Gui::BitmapFactory().pixmap("Sketcher_NewSketch"), panel);
}

TaskDlgSketchPlanePick::~TaskDlgSketchPlanePick()
{
    // Nothing that happens while tidying up may schedule another pick.
    detachSelection();

    if (viewer) {
        viewer->removeEventCallback(
            SoKeyboardEvent::getClassTypeId(),
            &TaskDlgSketchPlanePick::handleKeyboardCB,
            this
        );
    }
    if (opened) {
        Gui::Selection().rmvSelectionGate();
        if (auto* mainWindow = Gui::getMainWindow()) {
            mainWindow->hideHints();
        }
    }

    // Like TaskDlgAttacher, the follow-up runs from here: the dialog has already left
    // the task panel, so the sketch's own editor is free to take it. A document on
    // its way out takes its pending command with it, so there is nothing to do then.
    if (onDone && !documentClosing) {
        onDone(sketch);
    }
}

void TaskDlgSketchPlanePick::open()
{
    opened = true;
    // Only a shown dialog listens: a pick must never build a sketch for a dialog
    // the task panel turned away.
    attachSelection();
    Gui::Selection().addSelectionGate(new SketchPlaneGate(body));

    viewer = viewerOf(body->getDocument());
    if (viewer) {
        viewer->addEventCallback(
            SoKeyboardEvent::getClassTypeId(),
            &TaskDlgSketchPlanePick::handleKeyboardCB,
            this
        );
    }

    using enum Gui::InputHint::UserInput;
    Gui::getMainWindow()->showHints({
        {.message = tr("%1 select a face or plane"), .sequences = {MouseLeft}},
        {.message = tr("%1 cancel"), .sequences = {KeyEscape}},
    });
}

bool TaskDlgSketchPlanePick::accept()
{
    // Only a successful pick accepts this dialog; there is no OK button.
    return sketch != nullptr;
}

bool TaskDlgSketchPlanePick::reject()
{
    sketch = nullptr;
    return true;
}

void TaskDlgSketchPlanePick::autoClosedOnDeletedDocument()
{
    documentClosing = true;
}

void TaskDlgSketchPlanePick::onSelectionChanged(const Gui::SelectionChanges& msg)
{
    if (msg.Type != Gui::SelectionChanges::AddSelection || pickScheduled) {
        return;
    }
    // Build on the selection once it has settled: opening the sketch clears the
    // selection again, which must not happen from inside this notification.
    pickScheduled = true;
    QTimer::singleShot(0, this, [this]() { tryPick(); });
}

void TaskDlgSketchPlanePick::tryPick()
{
    pickScheduled = false;
    App::DocumentObject* picked = onPick ? onPick() : nullptr;
    if (!picked) {
        // Not something a sketch can sit on: keep waiting for the next click.
        Gui::Selection().clearSelection();
        return;
    }

    sketch = picked;
    Gui::Control().accept(body->getDocument());
}

void TaskDlgSketchPlanePick::cancel()
{
    QPointer<TaskDlgSketchPlanePick> self(this);
    App::Document* document = body->getDocument();
    QTimer::singleShot(0, [self, document]() {
        Gui::TaskView::TaskDialog* active = Gui::Control().activeDialog(document);
        if (self && active == static_cast<Gui::TaskView::TaskDialog*>(self.data())) {
            Gui::Control().reject(document);
        }
    });
}

void TaskDlgSketchPlanePick::handleKeyboardCB(void* userdata, SoEventCallback* cb)
{
    auto* self = static_cast<TaskDlgSketchPlanePick*>(userdata);
    const SoEvent* ev = cb->getEvent();
    if (!ev || !ev->isOfType(SoKeyboardEvent::getClassTypeId())) {
        return;
    }
    const auto* ke = static_cast<const SoKeyboardEvent*>(ev);
    if (ke->getKey() != SoKeyboardEvent::ESCAPE) {
        return;
    }
    cb->setHandled();

    // Cancel on the release, and never while a mouse button is down: Coin can crash
    // when Esc interrupts a drag (see ViewProvider::eventCallback).
    if (ke->getState() != SoButtonEvent::UP || QApplication::mouseButtons() != Qt::NoButton) {
        return;
    }
    self->cancel();
}

#include "moc_SketchPlanePicker.cpp"
