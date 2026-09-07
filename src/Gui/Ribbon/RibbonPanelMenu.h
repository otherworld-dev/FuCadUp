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


#pragma once

#include <QMenu>
#include <QPoint>
#include <QPointer>
#include <QString>

#include <FCGlobal.h>

class QAction;
class QActionEvent;
class QMimeData;
class QMouseEvent;

namespace Gui
{
namespace Ribbon
{

/**
 * The drop-down under a panel caption: the panel's full command set, from
 * which an entry can be dragged onto the panel row to show it as a button.
 *
 * An entry is a drag source only when it has been tagged with the command it
 * stands for, see tagCommand(); untagged entries (the variants of a group
 * command, say) are plain menu entries. A submenu made with addSubmenu() is a
 * drop-down of the same kind, so what it lists can be dragged too.
 * @author FuCad contributors
 */
class GuiExport RibbonPanelMenu: public QMenu
{
    Q_OBJECT

public:
    /// The mime type a dragged entry carries; see createMimeData().
    static const char* mimeType();

    /**
     * Packs the panel \a panelKey and the \a command into the payload a drag
     * hands over, which readMimeData() unpacks on the other side.
     */
    static QMimeData* createMimeData(const QString& panelKey, const QString& command);
    /// False when \a data does not carry a ribbon entry.
    static bool readMimeData(const QMimeData* data, QString& panelKey, QString& command);

    /// Names the command \a action stands for, which makes it a drag source.
    static void tagCommand(QAction* action, const QString& command);
    /// The command \a action was tagged with, or an empty string.
    static QString commandOf(const QAction* action);

    /**
     * A menu entry that carries \a label but triggers \a source, so that the
     * ribbon can name a command the way Fusion does without renaming the action
     * the rest of the application shares. The proxy follows the state of the
     * original, which the command framework keeps up to date.
     */
    static QAction* createProxyAction(QAction* source, const QString& label, QObject* parent);

    /**
     * A top-level drop-down for the panel \a panelKey; \a parent owns it.
     */
    RibbonPanelMenu(const QString& panelKey, QWidget* parent);
    ~RibbonPanelMenu() override = default;

    /// Adds a submenu whose entries are draggable like this menu's.
    RibbonPanelMenu* addSubmenu(const QString& title);
    /// Like addSubmenu(), but inserted ahead of \a before.
    RibbonPanelMenu* insertSubmenu(QAction* before, const QString& title);

Q_SIGNALS:
    /// An action was added to or removed from the menu.
    void entriesChanged();
    /// A drag from one of the entries began; dragFinished() follows once it ends.
    void dragStarted();
    void dragFinished();

protected:
    void actionEvent(QActionEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;

private:
    RibbonPanelMenu(const QString& panelKey, RibbonPanelMenu* root, const QString& title);

    void startDrag(QAction* action);

    QString panelKey;
    /// The top-level drop-down, which is hidden when a drag starts so that the
    /// row it may be dropped on is uncovered.
    QPointer<RibbonPanelMenu> root;
    QPointer<QAction> pressedAction;
    QPoint pressPosition;

    Q_DISABLE_COPY(RibbonPanelMenu)
};

}  // namespace Ribbon
}  // namespace Gui
