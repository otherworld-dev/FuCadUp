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

#include <QList>
#include <QPointer>
#include <QWidget>

#include <FCGlobal.h>

class QMenu;
class QToolButton;

namespace Gui
{
namespace Ribbon
{

class RibbonPageLayout;
class RibbonPanel;

/**
 * The page behind a ribbon tab: a row of panels, and an overflow button for
 * the panels that a page narrower than their captions cannot show.
 *
 * RibbonPageLayout decides which panels fit; the ones that do not are hidden
 * and listed, each as a submenu of its own drop-down, under the overflow
 * button that then appears at the end of the leading panels.
 * @author FuCad contributors
 */
class GuiExport RibbonPage: public QWidget
{
    Q_OBJECT

public:
    explicit RibbonPage(QWidget* parent = nullptr);
    ~RibbonPage() override = default;

    /// Appends \a panel to the leading or the trailing group; the page owns it.
    void addPanel(RibbonPanel* panel, bool trailing);

    /**
     * The buttons the keyboard can reach, in reading order: the panels on the
     * page from left to right, with the overflow button where it sits.
     */
    QList<QToolButton*> keyboardButtons() const;

    /// Told by the layout which panels it had to take off the page.
    void setCollapsedPanels(const QList<RibbonPanel*>& panels);

private:
    void fillOverflowMenu();

    RibbonPageLayout* pageLayout;
    QToolButton* overflowButton;
    QMenu* overflowMenu;
    QList<QPointer<RibbonPanel>> collapsed;

    Q_DISABLE_COPY(RibbonPage)
};

}  // namespace Ribbon
}  // namespace Gui
