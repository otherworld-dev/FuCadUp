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

#include <QWidget>

#include <FCGlobal.h>

class QHBoxLayout;
class QLabel;
class QMenu;
class QMenuBar;
class QMouseEvent;
class QResizeEvent;
class QToolButton;

namespace Gui
{
namespace Ribbon
{

/**
 * The strip above the ribbon tabs: the application menu button and the
 * quick-access buttons.
 *
 * The app bar also hosts the application's one and only QMenuBar. The bar is
 * never installed into the QMainWindow menu slot, because the ribbon container
 * occupies it; MainWindow::menuBar() hands out the bar living here so that
 * MenuManager keeps driving the menus unchanged.
 *
 * With the system frame gone it is also the title bar: it carries the document
 * name, the buttons that minimise, maximise and close, and it is what a drag
 * moves the window by.
 * @author FuCad contributors
 */
class GuiExport AppBar: public QWidget
{
    Q_OBJECT

public:
    explicit AppBar(QWidget* parent = nullptr);
    ~AppBar() override = default;

    QMenuBar* menuBar() const;

protected:
    void resizeEvent(QResizeEvent* event) override;
    void mousePressEvent(QMouseEvent* event) override;
    void mouseDoubleClickEvent(QMouseEvent* event) override;
    bool eventFilter(QObject* watched, QEvent* event) override;

private:
    void createMenuButton();
    void createQuickAccess();
    void createTitle();
    void createWindowControls();
    void refreshMenu();
    void refreshTitle();
    /// Swaps the maximise button between maximising and restoring.
    void refreshWindowState();
    /// Whether \a pos is over the bar itself rather than one of its controls.
    bool isBackgroundAt(const QPoint& pos) const;

    QHBoxLayout* barLayout;
    QMenuBar* appMenuBar;
    QToolButton* menuButton;
    QMenu* menuButtonMenu;
    /// All null unless the app bar is also the title bar.
    QLabel* titleLabel;
    QToolButton* maximizeButton;

    Q_DISABLE_COPY(AppBar)
};

}  // namespace Ribbon
}  // namespace Gui
