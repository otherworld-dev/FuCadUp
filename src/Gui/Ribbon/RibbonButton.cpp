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

#include <QAction>
#include <QActionEvent>
#include <QEvent>
#include <QList>
#include <QMenu>
#include <QSize>
#include <QSizePolicy>
#include <QStringList>
#include <QWidgetAction>

#include <Base/Console.h>
#include <Base/Exception.h>
#include <Gui/Action.h>
#include <Gui/Application.h>
#include <Gui/Command.h>

#include "RibbonButton.h"
#include "RibbonPanelMenu.h"


using namespace Gui;
using namespace Gui::Ribbon;

namespace
{
constexpr int largeIconExtent = 30;
// Fusion draws the command icons alone and names them only on hover, so the
// button is a square around the icon rather than a column with a label.
constexpr int largeButtonHeight = 40;
constexpr int largeButtonMinimumWidth = 40;
constexpr int largeButtonMaximumWidth = 40;
constexpr int menuIndicatorWidth = 12;
constexpr int smallIconExtent = 16;
constexpr int smallButtonHeight = 24;
constexpr int smallButtonWidth = 26;

}  // namespace


RibbonButton::RibbonButton(QWidget* parent)
    : QToolButton(parent)
{
    setObjectName(QStringLiteral("RibbonButton"));
    setAutoRaise(true);
    // A toolbar is one tab stop, not one per button, and the ribbon holds far
    // too many buttons to sit in the tab chain. RibbonBar puts the keyboard on
    // a button with setFocus(), which works whatever the policy says.
    setFocusPolicy(Qt::NoFocus);
    setPopupMode(QToolButton::DelayedPopup);
}

void RibbonButton::actionEvent(QActionEvent* event)
{
    QToolButton::actionEvent(event);

    // Qt copies text and tooltip back from the action every time the action
    // changes, the enabled state included, and Command::testActive toggles that
    // after every selection change. The ribbon's own naming has to survive it.
    if (event->type() == QEvent::ActionChanged && event->action() == defaultAction()) {
        if (!ribbonText.isEmpty()) {
            setText(ribbonText);
        }
        if (!ribbonToolTip.isEmpty()) {
            setToolTip(ribbonToolTip);
        }
    }
}

QString RibbonButton::command() const
{
    return commandName;
}

bool RibbonButton::splitsExplicitCommands() const
{
    return explicitSubCommands;
}

void RibbonButton::setPrimary(bool primary)
{
    setObjectName(
        primary ? QStringLiteral("RibbonPrimaryButton") : QStringLiteral("RibbonButton")
    );
}

QAction* RibbonButton::resolveAction(const QString& command)
{
    if (command.isEmpty() || !Application::Instance) {
        return nullptr;
    }

    CommandManager& manager = Application::Instance->commandManager();
    Command* cmd = manager.getCommandByName(command.toLatin1().constData());
    if (!cmd) {
        return nullptr;
    }

    cmd->initAction();
    Gui::Action* action = cmd->getAction();
    return action ? action->action() : nullptr;
}

void RibbonButton::followGroupMenu(ActionGroup* group, QMenu* menu)
{
    if (!group || !menu) {
        return;
    }

    QObject::connect(menu, &QMenu::aboutToShow, group, [group, menu]() {
        Q_EMIT group->aboutToShow(menu);
    });
    QObject::connect(menu, &QMenu::aboutToHide, group, [group, menu]() {
        Q_EMIT group->aboutToHide(menu);
    });
}

bool RibbonButton::setCommand(
    const QString& command,
    const QString& label,
    const QStringList& subCommands,
    ButtonSize size,
    bool quiet
)
{
    if (!Application::Instance) {
        return false;
    }

    CommandManager& manager = Application::Instance->commandManager();
    Command* cmd = manager.getCommandByName(command.toLatin1().constData());
    if (!cmd) {
        if (quiet) {
            Base::Console().log(
                "Ribbon: '%s' is not available, its module is not loaded\n",
                command.toUtf8().constData()
            );
        }
        else {
            Base::Console().warning(
                "Ribbon: skipping unknown command '%s'\n",
                command.toUtf8().constData()
            );
        }
        return false;
    }

    cmd->initAction();
    Gui::Action* guiAction = cmd->getAction();
    if (!guiAction || !guiAction->action()) {
        Base::Console().warning(
            "Ribbon: command '%s' provides no action\n",
            command.toUtf8().constData()
        );
        return false;
    }

    setDefaultAction(guiAction->action());
    commandName = command;
    applySize(size);

    if (size == ButtonSize::Large) {
        // The name is not drawn, so it has to lead the tooltip: hovering is the only
        // way to find out what an icon does. The label arrives translated from the
        // workspace definition and commandMenuText() is translated by the command
        // framework, so the comparison below is between two strings of the running
        // language.
        const QString caption = label.isEmpty() ? Action::commandMenuText(cmd) : label;
        ribbonText = caption;
        setText(caption);

        const QString description = guiAction->action()->toolTip();
        if (description.isEmpty()) {
            ribbonToolTip = caption;
        }
        else if (description.contains(caption)) {
            // FreeCAD's tooltip already opens with the command's own name.
            ribbonToolTip = description;
        }
        else {
            // Only differs when the ribbon renames the command, and the separator
            // has to match the format Qt infers for the rest of the tooltip.
            const bool rich = description.trimmed().startsWith(QLatin1Char('<'));
            ribbonToolTip =
                caption + (rich ? QLatin1String("<br/>") : QLatin1String("\n")) + description;
        }

        setToolTip(ribbonToolTip);
    }

    QList<QAction*> children;
    for (const QString& subCommand : subCommands) {
        if (QAction* action = resolveAction(subCommand)) {
            // Named so that the entry can be dragged onto the row once the
            // button has folded into the caption drop-down.
            RibbonPanelMenu::tagCommand(action, subCommand);
            children.append(action);
        }
        else if (quiet) {
            Base::Console().log(
                "Ribbon: sub-command '%s' of '%s' is not available\n",
                subCommand.toUtf8().constData(),
                command.toUtf8().constData()
            );
        }
        else {
            Base::Console().warning(
                "Ribbon: skipping unknown sub-command '%s' of '%s'\n",
                subCommand.toUtf8().constData(),
                command.toUtf8().constData()
            );
        }
    }

    explicitSubCommands = !children.isEmpty();

    ActionGroup* group = nullptr;
    if (children.isEmpty()) {
        group = qobject_cast<ActionGroup*>(guiAction);
        if (group) {
            children = group->actions();
        }
    }

    if (!children.isEmpty()) {
        auto* menu = new QMenu(this);
        menu->addActions(children);
        followGroupMenu(group, menu);
        setMenu(menu);

        if (isSettingsMenu(children)) {
            // Nothing in the menu is a command, so a plain click has nothing better to
            // do than open it and the user is spared aiming at the arrow.
            setPopupMode(QToolButton::InstantPopup);
        }
        else {
            setPopupMode(QToolButton::MenuButtonPopup);

            // The drop-down arrow is carved out of the button, so the icon keeps its
            // size only if the button grows by that much.
            setMinimumWidth(minimumWidth() + menuIndicatorWidth);
            setMaximumWidth(maximumWidth() + menuIndicatorWidth);
        }
    }

    return true;
}

bool RibbonButton::isSettingsMenu(const QList<QAction*>& children)
{
    // Grid, Snap and the like hang a panel of checkboxes and spin boxes off the button
    // instead of a list of alternative commands to pick between.
    return std::all_of(children.cbegin(), children.cend(), [](const QAction* action) {
        return qobject_cast<const QWidgetAction*>(action) != nullptr;
    });
}

void RibbonButton::applySize(ButtonSize size)
{
    switch (size) {
        case ButtonSize::Large:
            setToolButtonStyle(Qt::ToolButtonIconOnly);
            setIconSize(QSize(largeIconExtent, largeIconExtent));
            setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
            setMinimumSize(QSize(largeButtonMinimumWidth, largeButtonHeight));
            setMaximumSize(QSize(largeButtonMaximumWidth, largeButtonHeight));
            break;
        case ButtonSize::Small:
            setToolButtonStyle(Qt::ToolButtonIconOnly);
            setIconSize(QSize(smallIconExtent, smallIconExtent));
            setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
            setMinimumSize(QSize(smallButtonWidth, smallButtonHeight));
            setMaximumSize(QSize(smallButtonWidth, smallButtonHeight));
            break;
        default:
            throw Base::RuntimeError("RibbonButton: unhandled button size");
    }
}

#include "moc_RibbonButton.cpp"
