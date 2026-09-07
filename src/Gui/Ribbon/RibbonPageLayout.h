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

#include <QLayout>
#include <QList>
#include <QRect>
#include <QSize>

#include <FCGlobal.h>

class QLayoutItem;
class QWidget;

namespace Gui
{
namespace Ribbon
{

class RibbonPage;
class RibbonPanel;

/**
 * Lays out the panels of a ribbon page in one row: leading panels packed to
 * the left, trailing panels packed to the right, and whatever is left over as
 * a gap between them.
 *
 * When the page is narrower than the panels want, width is taken from the
 * rightmost leading panel first, then from the one before it, and only then
 * from the trailing panels, so that the panels a workspace leads with keep
 * their buttons the longest. No panel is ever given less than its minimum,
 * which is what stops the buttons inside it from piling up on one another;
 * the panel folds the buttons that no longer fit into its caption drop-down.
 *
 * Narrower still than the captions alone need, panels leave the page in the
 * same order and the page's overflow button takes their place, listing each
 * of them; the page is told which ones through RibbonPage::setCollapsedPanels().
 * @author FuCad contributors
 */
class GuiExport RibbonPageLayout: public QLayout
{
public:
    /// \a overflowButton is the page's; the layout only places and shows it.
    RibbonPageLayout(RibbonPage* page, QWidget* overflowButton);
    ~RibbonPageLayout() override;

    /// Appends \a panel to the leading or the trailing group.
    void addPanel(RibbonPanel* panel, bool trailing);

    void addItem(QLayoutItem* item) override;
    int count() const override;
    QLayoutItem* itemAt(int index) const override;
    QLayoutItem* takeAt(int index) override;
    Qt::Orientations expandingDirections() const override;
    QSize sizeHint() const override;
    /// The overflow button alone: every panel can leave the page.
    QSize minimumSize() const override;
    void setGeometry(const QRect& rect) override;

private:
    struct Entry
    {
        QLayoutItem* item;
        RibbonPanel* panel;
        bool trailing;
    };

    QList<Entry> entries;
    RibbonPage* page;
    QWidget* overflowButton;
    QList<RibbonPanel*> collapsed;

    Q_DISABLE_COPY(RibbonPageLayout)
};

}  // namespace Ribbon
}  // namespace Gui
