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

#include "DimensionValueEditor.h"

#include <functional>
#include <string>

#include <QContextMenuEvent>
#include <QEvent>
#include <QFocusEvent>
#include <QInputDialog>
#include <QKeyEvent>
#include <QLineEdit>
#include <QMenu>
#include <QString>

#include <App/Application.h>
#include <Base/Exception.h>
#include <Base/Parameter.h>
#include <Base/Tools.h>
#include <Gui/Application.h>
#include <Gui/Command.h>
#include <Gui/CommandT.h>
#include <Gui/Document.h>
#include <Gui/EditableDatumLabel.h>
#include <Gui/MainWindow.h>
#include <Gui/Notifications.h>
#include <Gui/QuantitySpinBox.h>
#include <Gui/SoDatumLabel.h>
#include <Mod/Sketcher/App/SketchObject.h>

#include "EditDatumDialog.h"
#include "Utils.h"

using namespace SketcherGui;

bool SketcherGui::editDimensionsInView()
{
    ParameterGrp::handle hGrp = App::GetApplication().GetParameterGroupByPath(
        "User parameter:BaseApp/Preferences/Mod/Sketcher"
    );
    return hGrp->GetBool("EditDimensionsInView", true);
}

DimensionValueEditor::DimensionValueEditor(
    Gui::View3DInventorViewer* viewer,
    const Base::Placement& sketchPlacement,
    Sketcher::SketchObject* sketch,
    int constraint,
    const Gui::SoDatumLabel& shownLabel
)
    : sketch(sketch)
    , constraint(constraint)
    , label(std::make_unique<Gui::EditableDatumLabel>(viewer, sketchPlacement))
{
    const Sketcher::Constraint* constr = sketch->Constraints.getValues()[constraint];
    type = static_cast<int>(constr->Type);
    first = constr->First;
    firstPos = static_cast<int>(constr->FirstPos);
    second = constr->Second;
    secondPos = static_cast<int>(constr->SecondPos);
    third = constr->Third;
    thirdPos = static_cast<int>(constr->ThirdPos);
    bool isAngle = constr->Type == Sketcher::Angle;
    unit = isAngle ? Base::Unit::Angle : Base::Unit::Length;
    double value = isAngle ? Base::toDegrees<double>(constr->getValue()) : constr->getValue();

    copyLabel(shownLabel);
    label->activate();
    // This editor sees the box's keys before EditableDatumLabel does, whose handling is the
    // sketch tools' on-view parameters'
    label->startEdit(value, this, true, true);
    label->setSpinboxValue(value, unit);

    box = label->getSpinBox();
    if (box) {
        box->setObjectName(QString::fromLatin1(boxName));
        // Bound like the dialog's field, so '=' formulas work here too
        box->bind(sketch->Constraints.createPath(constraint));
        edit = box->findChild<QLineEdit*>();
        if (edit) {
            edit->installEventFilter(this);
            connect(edit, &QLineEdit::textEdited, this, [this]() { typed = true; });
        }
    }
}

DimensionValueEditor::~DimensionValueEditor()
{
    // The box is only deleted later, once control is back in the event loop
    if (box) {
        box->hide();
    }
}

int DimensionValueEditor::constraintIndex() const
{
    return constraint;
}

void DimensionValueEditor::copyLabel(const Gui::SoDatumLabel& shownLabel)
{
    // The same geometry as the dimension on screen, so the box lands on its text
    Gui::SoDatumLabel* own = label->label;
    own->datumtype = shownLabel.datumtype.getValue();
    own->param4 = shownLabel.param4.getValue();
    own->param5 = shownLabel.param5.getValue();
    own->param6 = shownLabel.param6.getValue();
    own->param7 = shownLabel.param7.getValue();
    own->param8 = shownLabel.param8.getValue();
    label->setLabelDistance(shownLabel.param1.getValue());
    label->setLabelStartAngle(shownLabel.param2.getValue());
    label->setLabelRange(shownLabel.param3.getValue());

    // An angle is drawn from its first point alone, but the text centre needs two
    int count = shownLabel.pnts.getNum();
    if (count >= 2) {
        label->setPoints(shownLabel.pnts[0], shownLabel.pnts[1]);
    }
    else if (count == 1) {
        label->setPoints(shownLabel.pnts[0], shownLabel.pnts[0]);
    }
}

bool DimensionValueEditor::constraintStillThere() const
{
    // Undo or a deletion can put another constraint at this index
    const auto& constraints = sketch->Constraints.getValues();
    if (constraint < 0 || constraint >= static_cast<int>(constraints.size())) {
        return false;
    }
    const Sketcher::Constraint* constr = constraints[constraint];
    return static_cast<int>(constr->Type) == type && constr->First == first
        && static_cast<int>(constr->FirstPos) == firstPos && constr->Second == second
        && static_cast<int>(constr->SecondPos) == secondPos && constr->Third == third
        && static_cast<int>(constr->ThirdPos) == thirdPos;
}

void DimensionValueEditor::finish(bool apply)
{
    if (finished) {
        return;
    }
    finished = true;

    if (apply && (typed || swapType) && constraintStillThere()) {
        applyValue();
    }

    if (box) {
        box->hide();
    }
    label->deactivate();
    deleteLater();
}

void DimensionValueEditor::applyValue()
{
    if (!box) {
        return;
    }

    bool hasExpression = box->hasExpression();
    if (!hasExpression && !box->hasValidInput()) {
        return;
    }

    int tid = openTransaction(QT_TRANSLATE_NOOP("Command", "Set dimension value"));
    try {
        if (swapType) {
            // As EditDatumDialog does: the number typed is read as the other kind
            Sketcher::Constraint* constr = sketch->Constraints.getValues()[constraint];
            constr->Type = constr->Type == Sketcher::Radius ? Sketcher::Diameter : Sketcher::Radius;
            type = static_cast<int>(constr->Type);
        }

        if (hasExpression) {
            box->apply();
        }
        else {
            Base::Quantity quantity = box->value();
            double datum = quantity.getValue();
            std::string unitString = Base::Tools::escapeQuotesFromString(
                quantity.getUnit().getString()
            );

            performAutoScale(sketch, constraint, datum);
            Gui::cmdAppObjectArgs(
                sketch,
                "setDatum(%i,App.Units.Quantity('%.8g %s'))",
                constraint,
                datum,
                unitString
            );
        }

        Gui::Command::commitCommand(tid);

        // As EditDatumDialog: the expression engine is not reliably told about datum changes
        sketch->ExpressionEngine.execute();
        sketch->solve();
        tryAutoRecompute(sketch);
    }
    catch (const Base::Exception& e) {
        Gui::NotifyUserError(sketch, QT_TRANSLATE_NOOP("Notifications", "Value Error"), e.what());
        Gui::Command::abortCommand(tid);

        // A failed setDatum most likely left the solver's information invalid
        if (sketch->noRecomputes) {
            sketch->solve();
        }
    }
}

bool DimensionValueEditor::eventFilter(QObject* watched, QEvent* event)
{
    bool onBox = (box && watched == box.data()) || (edit && watched == edit.data());
    if (!onBox || finished) {
        return QObject::eventFilter(watched, event);
    }

    switch (event->type()) {
        case QEvent::KeyPress: {
            int key = static_cast<QKeyEvent*>(event)->key();
            if (key == Qt::Key_Return || key == Qt::Key_Enter || key == Qt::Key_Tab) {
                finish(true);
                return true;
            }
            if (key == Qt::Key_Escape) {
                finish(false);
                return true;
            }
            break;
        }
        case QEvent::ContextMenu:
            showMenu(static_cast<QContextMenuEvent*>(event)->globalPos());
            return true;
        case QEvent::FocusOut: {
            Qt::FocusReason reason = static_cast<QFocusEvent*>(event)->reason();
            // A menu, or another window taking the keyboard, is not the user leaving the box
            if (!menuOpen && reason != Qt::ActiveWindowFocusReason
                && reason != Qt::PopupFocusReason) {
                // Let the focus change finish before the box goes away
                QMetaObject::invokeMethod(this, [this]() { finish(true); }, Qt::QueuedConnection);
            }
            break;
        }
        default:
            break;
    }

    return QObject::eventFilter(watched, event);
}

void DimensionValueEditor::showMenu(const QPoint& globalPos)
{
    if (!constraintStillThere()) {
        return;
    }

    const Sketcher::Constraint* constr = sketch->Constraints.getValues()[constraint];
    QMenu menu;
    std::function<void()> chosen;
    auto add = [&menu, &chosen](const QString& text, std::function<void()> action) {
        QAction* item = menu.addAction(text);
        QObject::connect(item, &QAction::triggered, &menu, [&chosen, action]() {
            chosen = action;
        });
    };

    add(tr("Reference"), [this]() { makeReference(); });
    if (constr->Type == Sketcher::Radius || constr->Type == Sketcher::Diameter) {
        bool showsRadius = (constr->Type == Sketcher::Radius) != swapType;
        add(showsRadius ? tr("Diameter") : tr("Radius"), [this]() { swapRadiusDiameter(); });
    }
    add(tr("Name..."), [this]() { rename(); });
    menu.addSeparator();
    add(tr("More..."), [this]() { openDialog(); });

    menuOpen = true;
    menu.exec(globalPos);
    if (chosen) {
        chosen();
    }
    menuOpen = false;

    if (!finished) {
        label->setFocusToSpinbox();
    }
}

void DimensionValueEditor::makeReference()
{
    // A reference dimension takes no value
    finish(false);

    int tid = openTransaction(QT_TRANSLATE_NOOP("Command", "Toggle constraint to driving/reference"));
    try {
        Gui::cmdAppObjectArgs(sketch, "setDriving(%d, False)", constraint);
        Gui::Command::commitCommand(tid);
    }
    catch (const Base::Exception& e) {
        Gui::NotifyUserError(sketch, QT_TRANSLATE_NOOP("Notifications", "Error"), e.what());
        Gui::Command::abortCommand(tid);
    }
    tryAutoRecompute(sketch);
}

void DimensionValueEditor::swapRadiusDiameter()
{
    const Sketcher::Constraint* constr = sketch->Constraints.getValues()[constraint];
    swapType = !swapType;

    // Until another number is typed the circle stays as it is: a radius r is a diameter 2r
    bool storedDiameter = constr->Type == Sketcher::Diameter;
    bool showsDiameter = storedDiameter != swapType;
    double value = constr->getValue();
    if (showsDiameter && !storedDiameter) {
        value *= 2.0;
    }
    else if (!showsDiameter && storedDiameter) {
        value /= 2.0;
    }
    label->setSpinboxValue(value, unit);
}

void DimensionValueEditor::rename()
{
    const Sketcher::Constraint* constr = sketch->Constraints.getValues()[constraint];

    bool ok = false;
    QString name = QInputDialog::getText(
        Gui::getMainWindow(),
        tr("Dimension name"),
        tr("Name (available for expressions):"),
        QLineEdit::Normal,
        QString::fromStdString(constr->Name),
        &ok
    );
    std::string newName = name.trimmed().toStdString();
    if (!ok || newName == constr->Name || !checkConstraintName(sketch, newName)) {
        return;
    }

    int tid = openTransaction(QT_TRANSLATE_NOOP("Command", "Rename sketch constraint"));
    try {
        Gui::cmdAppObjectArgs(sketch, "renameConstraint(%d, u'%s')", constraint, newName.c_str());
        Gui::Command::commitCommand(tid);
    }
    catch (const Base::Exception& e) {
        Gui::NotifyUserError(sketch, QT_TRANSLATE_NOOP("Notifications", "Error"), e.what());
        Gui::Command::abortCommand(tid);
    }
}

void DimensionValueEditor::openDialog()
{
    finish(true);
    if (!constraintStillThere()) {
        return;
    }

    Gui::Document* doc = Gui::Application::Instance->getDocument(sketch->getDocument());
    if (!doc) {
        return;
    }
    int tid = doc->openCommand(QT_TRANSLATE_NOOP("Command", "Modify sketch constraints"));
    EditDatumDialog(tid, sketch, constraint).exec(false);
}

int DimensionValueEditor::openTransaction(const char* name) const
{
    Gui::Document* doc = Gui::Application::Instance->getDocument(sketch->getDocument());
    return doc ? doc->openCommand(name) : 0;
}

#include "moc_DimensionValueEditor.cpp"  // NOLINT
