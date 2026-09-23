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

#include <vector>

#include <QString>
#include <QStringList>
#include <QWidget>

#include <FCGlobal.h>

class QLineEdit;
class QListWidget;
class QListWidgetItem;
class QScreen;

namespace Gui
{
namespace Ribbon
{

/**
 * The popup that switches workbench in two clicks, or from the keyboard.
 *
 * It opens under the ribbon's workspace block, or wherever Std_WorkbenchSwitcher
 * (Ctrl+Shift+W) asks, with a filter field above one list: the ribbon's own
 * areas first in tab order, then the last workbenches used, then every other
 * enabled workbench from A to Z. Typing narrows the list to the matches and Enter
 * switches to the first, so a workbench is a shortcut and a few letters away.
 *
 * A workbench the ribbon has a tab for is named after that tab (SOLID rather
 * than Part Design), the way the rest of the shell names it; one without a tab
 * keeps its own name, having no other.
 * @author FuCad contributors
 */
class GuiExport WorkbenchSwitcher: public QWidget
{
    Q_OBJECT

public:
    /// A workbench the ribbon has a tab for, and that tab's title.
    struct Area
    {
        QString workbench;
        QString title;
    };

    /// The one and only instance, created on first use.
    static WorkbenchSwitcher* instance();
    static void destruct();

    /**
     * Notes that \a workbench became active, so that the Recent section can offer
     * it again. Works before the switcher has ever been shown.
     */
    static void noteWorkbenchUsed(const QString& workbench);
    /// The workbenches used most recently, the latest first.
    static QStringList recentWorkbenches();

    /// The ribbon's areas, in tab order. RibbonManager keeps these current.
    void setAreas(const std::vector<Area>& areas);
    /// The name the shell shows for \a workbench: its area's title, or its own.
    QString titleFor(const QString& workbench) const;

    /**
     * Shows the switcher under \a anchor, or under the mouse cursor when there
     * is none, with the caret in the filter field.
     */
    void popUp(QWidget* anchor);

protected:
    void keyPressEvent(QKeyEvent* event) override;
    /// Lets the filter field hand Up, Down and Enter to the list.
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    WorkbenchSwitcher();

    /// Fills the list for what the filter field holds.
    void rebuild();
    /// Sizes the switcher to the rows listed, within \a screen's height.
    void fitToList(const QScreen* screen);
    void addCaption(const QString& text);
    void addWorkbench(const QString& workbench, const QString& active);
    /// Moves the list's current row by \a step, over the captions.
    void moveCurrent(int step);
    /// Switches to the workbench on \a item, if it names one.
    void activate(QListWidgetItem* item);

    QLineEdit* filter {nullptr};
    QListWidget* list {nullptr};
    std::vector<Area> areas;

    static WorkbenchSwitcher* _instance;
};

}  // namespace Ribbon
}  // namespace Gui
