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


#include <string>

#include <QByteArray>
#include <QCoreApplication>
#include <QTimer>

#include <App/Application.h>
#include <App/Document.h>
#include <App/DocumentObject.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/Document.h>
#include <Gui/Selection/Selection.h>
#include <Gui/ViewProviderDocumentObject.h>

#include "FinishModeAction.h"
#include "RibbonButton.h"


using namespace Gui;
using namespace Gui::Ribbon;

namespace
{

/**
 * The object the active document is editing, by document and object name, so
 * that it can be found again once the edit is over. False when there is none.
 */
bool editedObject(std::string& document, std::string& object)
{
    Gui::Document* doc = Application::Instance->activeDocument();
    auto* viewProvider = doc ? dynamic_cast<ViewProviderDocumentObject*>(doc->getInEdit()) : nullptr;
    App::DocumentObject* edited = viewProvider ? viewProvider->getObject() : nullptr;
    const char* name = edited ? edited->getNameInDocument() : nullptr;
    if (!name) {
        return false;
    }

    document = edited->getDocument()->getName();
    object = name;
    return true;
}

}  // namespace


FinishModeAction::FinishModeAction(
    QAction* source,
    const QString& finishCommand,
    bool keepEdited,
    QObject* parent
)
    : QAction(source->icon(), source->text(), parent)
    , source(source)
    , finish(RibbonButton::resolveAction(finishCommand))
    , finishCommand(finishCommand)
    , keepEdited(keepEdited)
{
    // The shortcut is left behind on purpose: the mode keeps the keys.
    setToolTip(source->toolTip());
    setStatusTip(source->statusTip());
    setWhatsThis(source->whatsThis());
    setCheckable(source->isCheckable());
    followSource();

    connect(source, &QAction::changed, this, [this]() { followSource(); });
    if (finish) {
        connect(finish, &QAction::changed, this, [this]() { followSource(); });
    }
    connect(this, &QAction::triggered, this, [this]() { run(); });
}

void FinishModeAction::followSource()
{
    if (!source) {
        return;
    }

    // Not the text: a ribbon label given to the stand-in has to survive.
    setIcon(source->icon());
    setChecked(source->isChecked());
    setEnabled(source->isEnabled() || (finish && finish->isEnabled()));
}

void FinishModeAction::run()
{
    if (!source) {
        return;
    }

    // The mode is over already, as on a page that has not been rebuilt yet, so
    // the command runs as it is.
    if (!finish || !finish->isEnabled()) {
        source->trigger();
        return;
    }

    std::string document;
    std::string object;
    const bool handOver = keepEdited && editedObject(document, object);

    // Queued: finishing the mode drops its context tab, which builds the page this
    // action belongs to again, so nothing below may refer to the action itself.
    QPointer<QAction> target = source;
    const QByteArray finishName = finishCommand.toLatin1();
    QTimer::singleShot(0, QCoreApplication::instance(), [target, finishName, handOver, document, object]() {
        Application::Instance->commandManager().runCommandByName(finishName.constData());

        // Queued again, so that the mode's task dialog is gone by the time the
        // command asks whether it may run.
        QTimer::singleShot(0, QCoreApplication::instance(), [target, handOver, document, object]() {
            Selection().clearSelection();
            if (handOver) {
                App::Document* doc = App::GetApplication().getDocument(document.c_str());
                if (doc && doc->getObject(object.c_str())) {
                    Selection().addSelection(document.c_str(), object.c_str());
                }
            }

            // The command framework refreshes enabled states on a timer, and the
            // source has to know now that the mode no longer holds it back.
            Application::Instance->commandManager().testActive();
            if (target && target->isEnabled()) {
                target->trigger();
            }
        });
    });
}
