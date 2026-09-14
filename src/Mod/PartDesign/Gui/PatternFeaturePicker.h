// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <functional>
#include <QPointer>

#include <Gui/Selection/Selection.h>
#include <Gui/TaskView/TaskDialog.h>

class SoEventCallback;

namespace App
{
class DocumentObject;
}
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
 * Waits for one click on an additive or subtractive feature of the body, so a pattern
 * run with nothing selected starts from what the user clicks, the way Create Sketch
 * waits for its plane (see TaskDlgSketchPlanePick, which this follows).
 *
 * A standalone pattern with nothing to copy cannot exist: it would be taken for a
 * MultiTransform step (Transformed::isMultiTransformChild), so the pattern is only made
 * once there is a feature. Esc in the 3D view, Cancel and closing the document end the
 * wait without one.
 */
class TaskDlgPatternFeaturePick: public Gui::TaskView::TaskDialog, public Gui::SelectionObserver
{
    Q_OBJECT

public:
    /// Runs once the dialog has left the task panel; the feature is null after a cancel.
    using DoneHandler = std::function<void(App::DocumentObject* feature)>;

    TaskDlgPatternFeaturePick(
        PartDesign::Body* body,
        const QString& title,
        const char* iconName,
        DoneHandler onDone
    );
    ~TaskDlgPatternFeaturePick() override;

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
    DoneHandler onDone;
    App::DocumentObject* feature {nullptr};
    bool opened {false};
    bool pickScheduled {false};
    bool documentClosing {false};
    QPointer<Gui::View3DInventorViewer> viewer;
};

}  // namespace PartDesignGui
